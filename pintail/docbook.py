# pintail - Build static sites from collections of Mallard documents
# Copyright (c) 2015-2020 Shaun McCance <shaunm@gnome.org>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 2 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import os
import subprocess
import shutil
from lxml import etree

import pintail.site

XML_NS = '{http://www.w3.org/XML/1998/namespace}'
XLINK_NS = '{https://www.w3.org/1999/xlink}'
MAL_NS = '{http://projectmallard.org/1.0/}'
SITE_NS = '{http://projectmallard.org/site/1.0/}'
PINTAIL_NS = '{http://pintail.io/}'
DOCBOOK_NS = '{http://docbook.org/ns/docbook}'
DOCBOOK_CHUNKS_ = [
    'appendix', 'article', 'bibliography', 'bibliodiv', 'book', 'chapter', 'colophon',
    'dedication', 'glossary', 'glossdiv', 'index', 'lot', 'part', 'preface', 'refentry',
    'reference', 'sect1', 'sect2', 'sect3', 'sect4', 'sect5', 'section', 'setindex',
    'simplesect', 'toc']
DOCBOOK_CHUNKS = DOCBOOK_CHUNKS_ + [DOCBOOK_NS + el for el in DOCBOOK_CHUNKS_]
DOCBOOK_INFOS = [
    DOCBOOK_NS + 'info', 'appendixinfo', 'articleinfo', 'bibliographyinfo', 'bookinfo',
    'chapterinfo', 'glossaryinfo', 'indexinfo', 'partinfo', 'prefaceinfo', 'refentryinfo',
    'referenceinfo', 'sect1info', 'sect2info', 'sect3info', 'sect4info', 'sect5info',
    'sectioninfo', 'setindexinfo']

class DocBookPage(pintail.site.Page):
    """
    The primary page in a DocBook document.

    A DocBook document can create multiple output files. There is exaclty one
    `DocBookPage` object for each document. It can then have any number of
    `DocBookSubPage` objects, which are stored in `subpages`. The primary page
    does most of the work, including building all HTML, but the subpages exist
    for tracking and search purposes.
    """

    _html_transform = None

    def __init__(self, source, filename):
        self.pbdoctype = None
        self.pbbrand = None
        self.pblang = None

        super().__init__(source, filename)
        self.stage_page()
        self._tree = etree.parse(self.get_stage_path())
        maxdepth = 1
        if self._tree.getroot().tag in ('book', DOCBOOK_NS + 'book'):
            maxdepth = 2
        pi = self._tree.getroot().xpath('string(/processing-instruction("db.chunk.max_depth"))')
        if len(pi) > 0:
            try:
                maxdepth = int(pi)
            except:
                pass
        self.maxdepth = maxdepth

        self._fixed = False
        self._fixid = 1
        def _fixids(node):
            if node.tag in DOCBOOK_CHUNKS:
                chunkid = node.get('id') or node.get(XML_NS + 'id')
                if chunkid is None:
                    if node is self._tree.getroot():
                        chunkid = 'index'
                    else:
                        while self._tree.xpath('count(//*[@id = "%s" or @xml:id = "%s"])' %
                                               ('page' + str(self._fixid), 'page' + str(self._fixid))) > 0:
                            self._fixid += 1
                        chunkid = 'page' + str(self._fixid)
                    if node.tag.startswith(DOCBOOK_NS):
                        node.set(XML_NS + 'id', chunkid)
                    else:
                        node.set('id', chunkid)
                    self._fixed = True
                for child in node:
                    _fixids(child)
        _fixids(self._tree.getroot())
        if self._fixed:
            self._tree.write(self.get_stage_path())

        def _accumulate_pages(node, depth, maxdepth):
            ret = []
            for child in node:
                if child.tag in DOCBOOK_CHUNKS:
                    ret.append(child)
                    if depth < maxdepth:
                        ret.extend(_accumulate_pages(child, depth + 1, maxdepth))
            return ret
        pages = _accumulate_pages(self._tree.getroot(), 1, maxdepth)
        self.subpages = [DocBookSubPage(self, el) for el in pages]
        self._langtrees = {}
        self._notlangs = set()


    def _get_tree(self, lang=None):
        if lang is None or lang in self._notlangs:
            return self._tree
        if lang in self._langtrees:
            return self._langtrees[lang]
        if self.site.translate_page(self, lang):
            self._langtrees[lang] = etree.parse(self.get_stage_path(lang))
            return self._langtrees[lang]
        self._notlangs.add(lang)
        return self._tree


    @property
    def page_id(self):
        """
        The simple id of the page.

        This is always `"index"` for the primary page of a DocBook document,
        regardless of the file name or the value of the `id` attribute.
        """
        return 'index'


    @property
    def searchable(self):
        """
        Whether the page should be added to the search index.
        """
        return True


    def get_title_node(self, node, hint=None):
        """
        Get the title for a node in the DocBook tree.

        This is a utility function to share the `get_title` code between
        `DocBookPage` and `DocBookSubPage`.
        """
        title = ''
        for child in node:
            if child.tag in DOCBOOK_INFOS:
                for info in child:
                    if info.tag in ('title', DOCBOOK_NS + 'title'):
                        title = info.xpath('string(.)')
            elif child.tag in ('title', DOCBOOK_NS + 'title'):
                title = child.xpath('string(.)')
                break
        return title


    def get_title(self, hint=None, lang=None):
        """
        Get the title of the DocBook page.

        This implementation prefers the `title` element in the `info` (or similar)
        element, but will use the primary display title if an info title is not found.
        """
        return self.get_title_node(self._get_tree(lang).getroot(), hint=hint)


    def get_keywords_node(self, node, hint=None):
        """
        Get the keywords for a node in the DocBook tree.

        This is a utility function to share the `get_keywords` code between
        `DocBookPage` and `DocBookSubPage`.
        """
        keywords = ''
        for child in node:
            if child.tag in DOCBOOK_INFOS:
                for info in child:
                    if info.tag in ('keywordset', DOCBOOK_NS + 'keywordset'):
                        for keyword in info:
                            if keyword.tag in ('keyword', DOCBOOK_NS + 'keyword'):
                                if keywords != '':
                                    keywords += ', '
                                keywords += keyword.xpath('string(.)')
                break
        return keywords


    def get_keywords(self, hint=None, lang=None):
        """
        Get the keywords of the DocBook page.

        This implementation looks at the `keywordset` element. It makes a
        comma-separated list from each `keyword` child element.
        """
        return self.get_keywords_node(self._get_tree(lang).getroot(), hint=hint)


    def get_content_node(self, node, hint=None):
        """
        Get the content for a node in the DocBook tree.

        This is a utility function to share the `get_content` code between
        `DocBookPage` and `DocBookSubPage`.
        """
        depth = 0
        parent = node.getparent()
        while parent is not None:
            depth += 1
            parent = parent.getparent()
        def _accumulate_text(node):
            ret = ''
            for child in node:
                if not isinstance(child.tag, str):
                    continue
                if node.tag in DOCBOOK_INFOS:
                    continue
                if depth < self.maxdepth and child.tag in DOCBOOK_CHUNKS:
                    continue
                ret += child.text or ''
                ret += _accumulate_text(child)
                ret += child.tail or ''
            return ret
        return _accumulate_text(node)


    def get_content(self, hint=None, lang=None):
        """
        Get the full content of the DocBook page.

        This implementation tries carefully not to include content from
        subpages in the content for this page.
        """
        return self.get_content_node(self._get_tree(lang).getroot(), hint=hint)


    def _rewrite_publican_xml_file(self, source, target, entfile):
        p = subprocess.Popen(['xmllint', '--dropdtd', source],
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        lines = p.communicate()[0].decode('utf-8').split('\n')
        decl = None
        if lines[0].startswith('<?xml'):
            decl = lines.pop(0)
        el = None
        for line in lines:
            if '<' in line:
                el = line[line.index('<')+1:]
                if el[0] != '!':
                    if ' ' in el:
                        el = el[:el.index(' ')]
                    elif '>' in el:
                        el = el[:el.index('>')]
                    break
        doctype = '<!DOCTYPE %s PUBLIC ' % el
        if self.pbdoctype.startswith('4.'):
            doctype += '"-//OASIS//DTD DocBook XML V%s//EN" ' % self.pbdoctype
            doctype += '"http://www.oasis-open.org/docbook/xml/%s/docbookx.dtd" [\n' % self.pbdoctype
        elif self.pbdoctype.startswith('5.'):
            FIXME
        else:
            FIXME
        if entfile is not None:
            doctype += '<!ENTITY %% BOOK_ENTITIES SYSTEM "%s">\n' % entfile
            doctype += '%BOOK_ENTITIES;\n'
        doctype += ']>\n'
        fd = open(target, 'w')
        if decl is not None:
            fd.write(decl + '\n')
        fd.write(doctype)
        for line in lines:
            fd.write(line + '\n')
        fd.close()


    def _stage_page_publican(self):
        # Publican does some weird things to DocBook, including rewriting the DOCTYPE
        # in a way that lets you write non-well-formed XML that can't be read by any
        # other tool. Pintail can pretend to be Publican.
        pbdir = os.path.join(self.directory.get_stage_path(), '__publican__')
        pintail.site.Site._makedirs(pbdir)

        # Look for the publican.cfg file and extract some values from it.
        cfgdir = self.source.get_source_path()
        cfg = os.path.join(cfgdir, 'publican.cfg')
        while not os.path.exists(cfg):
            if os.path.dirname(cfgdir) == cfgdir:
                break
            cfgdir = os.path.dirname(cfgdir)
            cfg = os.path.join(cfgdir, 'publican.cfg')
        if os.path.exists(cfg):
            for line in open(cfg):
                if line.startswith('brand:'):
                    self.pbbrand = line[line.index(':')+1:].strip()
                if line.startswith('xml_lang:'):
                    self.pblang = line[line.index(':')+1:].strip()

        # Rewrite the DOCTYPE of all .xml files, using a .ent file with the
        # same basename if available. This is the craziness Publican does.
        xmlfiles = []
        entfile = None
        dpath = self.source.get_source_path()
        for xml in os.listdir(dpath):
            if not os.path.isfile(os.path.join(dpath, xml)):
                continue
            if xml.endswith('.xml'):
                xmlfiles.append(xml)
            elif xml == os.path.splitext(self.source_file)[0] + '.ent':
                entfile = xml
                shutil.copyfile(os.path.join(dpath, entfile), os.path.join(pbdir, entfile))
        for xml in xmlfiles:
            self._rewrite_publican_xml_file(os.path.join(dpath, xml),
                                            os.path.join(pbdir, xml),
                                            entfile)

        # Publican also ships "common content", some of which is required
        # for parsing. But even the common content has to be rewritten to
        # reference the .ent file in your repo. We can only do this if we
        # found a brand and language in publican.cfg.
        if self.pbbrand is not None and self.pblang is not None:
            ccdir = os.path.join(pbdir, 'Common_Content')
            pintail.site.Site._makedirs(ccdir)
            branddir = os.path.join('/usr/share/publican/Common_Content/', self.pbbrand, self.pblang)
            commondir = os.path.join('/usr/share/publican/Common_Content/common/', self.pblang)
            brandfiles = [os.path.join(branddir, xml) for xml in os.listdir(branddir)]
            commonfiles = [os.path.join(commondir, xml) for xml in os.listdir(commondir)]
            donefiles = set()
            for filename in brandfiles + commonfiles:
                bname = os.path.basename(filename)
                if bname in donefiles:
                    continue
                if not os.path.isfile(filename):
                    continue
                if filename.endswith('.xml'):
                    donefiles.add(bname)
                    self._rewrite_publican_xml_file(filename,
                                                    os.path.join(ccdir, bname),
                                                    '../' + entfile)

        # Finally, make a baked XML file in the location the rest of Pintail expects.
        subprocess.call(['xmllint', '--xinclude', '--noent', '--loaddtd',
                         '-o', self.get_stage_path(),
                         os.path.join(pbdir, self.source_file)])


    def stage_page(self):
        """
        Create a DocBook file in the stage.

        This implementation adds the entire DocBook document to the stage,
        including all content needed by subpages.
        If the document has been marked as a Publican document with the
        `publican_doctype` config option, this method will do various
        things to the document to try to emulate Publican.
        """
        pintail.site.Site._makedirs(self.directory.get_stage_path())
        self.pbdoctype = self.site.config.get('publican_doctype', self.source.name)
        if self.pbdoctype is not None:
            self._stage_page_publican()
        else:
            subprocess.call(['xmllint', '--xinclude', '--noent',
                             '-o', self.get_stage_path(),
                             self.get_source_path()])


    def get_cache_data(self, lang=None):
        """
        Get XML data to add to the cache, as an lxml.etree.Element object.

        The DocBook cache data is in a `pintail:external` element.
        """
        ret = None
        try:
            ret = etree.Element(PINTAIL_NS + 'external')
            ret.set('id', self.directory.path + 'index')
            ret.set(SITE_NS + 'dir', self.directory.path)
            dbfile = self._get_tree(lang)
            dbfile.xinclude()
            info = None
            title = None
            for child in dbfile.getroot():
                if not isinstance(child.tag, str):
                    continue
                if child.tag == (DOCBOOK_NS + 'info'):
                    info = child
                elif etree.QName(child.tag).namespace is None and child.tag.endswith('info'):
                    info = child
                elif child.tag in ('title', DOCBOOK_NS + 'title'):
                    title = child
                    break
            if title is None and info is not None:
                for child in info:
                    if child.tag in ('title', DOCBOOK_NS + 'title'):
                        title = child
                        break
            if title is not None:
                title = title.xpath('string(.)')
                titlen = etree.Element(MAL_NS + 'title')
                titlen.text = title
                ret.append(titlen)
        except:
            pass
        return ret


    def build_html(self, lang=None):
        """
        Build the HTML file for the entire DocBook document, possibly translated.

        This implementation generates all HTML files for all pages in the document,
        including all subpages. `DocBookSubPage` does not implement `build_html`.
        """
        if lang is None:
            self.site.log('HTML', self.site_id)
        else:
            self.site.log('HTML', lang + ' ' + self.site_id)

        if DocBookPage._html_transform is None:
            DocBookPage._html_transform = etree.XSLT(etree.parse(os.path.join(self.site.tools_path,
                                                                              'pintail-html-docbook-local.xsl')))
        args = {}
        args['pintail.format'] = etree.XSLT.strparam('docbook')
        for pair in pintail.site.XslProvider.get_all_xsl_params('html', self, lang=lang):
            args[pair[0]] = etree.XSLT.strparam(pair[1])
        tree = self._get_tree(lang)
        DocBookPage._html_transform(tree, **args)

        return
        # Leaving in this code to call xsltproc for now. It turns out that using
        # etree.XSLT is slower on each individual run than calling xsltproc, oddly
        # enough. But it gets you performance gains over large numbers of documents
        # by not constantly reparsing the XSLT. This is definitely worthwhile for
        # Mallard. We may find it's not worthwhile for DocBook when tested against
        # real-world sites.

        cmd = ['xsltproc',
               '--xinclude',
               '--stringparam', 'pintail.format', 'docbook']
        cmd.extend(pintail.site.XslProvider.get_xsltproc_args('html', self, lang=lang))
        cmd.extend([
            '-o', self.get_target_path(lang),
            os.path.join(self.site.tools_path, 'pintail-html-docbook-local.xsl'),
            self.get_stage_path(lang)])
        subprocess.call(cmd)


    def get_media(self):
        """
        Get a list of referenced media files in the entire DocBook document.

        This implementation looks for any local references in `fileref` attributes,
        `xlink:href` attributes, and `url` attributes on `ulink` elements.
        It returns references to all media files in the entire document,
        even if they are referenced from a subpage.
        This method also attempts to stage common content provided by Publican
        if the document has been marked as a Publican document with the
        `publican_doctype` config option.
        """
        refs = set()
        def _accumulate_refs(node):
            src = node.get('fileref', None)
            if src is not None and ':' not in src:
                refs.add(src)
            href = node.get(XLINK_NS + 'href', None)
            if href is not None and ':' not in href:
                refs.add(href)
            if node.tag == 'ulink':
                href = node.get('url', None)
                if href is not None and ':' not in href:
                    refs.add(href)
            for child in node:
                _accumulate_refs(child)
        _accumulate_refs(self._tree.getroot())

        # If files don't exist, but Publican provides them, stage them.
        if self.pbbrand is not None and self.pblang is not None:
            for ref in refs:
                if os.path.exists(os.path.join(self.source.get_source_path(), ref)):
                    continue
                stagepath = os.path.join(self.directory.get_stage_path(), ref)
                if os.path.exists(stagepath):
                    continue
                if ref.startswith('Common_Content/'):
                    rref = ref[15:]
                else:
                    continue
                tryref = os.path.join('/usr/share/publican/Common_Content/', self.pbbrand, self.pblang, rref)
                if os.path.exists(tryref):
                    self.site.log('STAGE', self.directory.path + ref)
                    pintail.site.Site._makedirs(os.path.dirname(stagepath))
                    shutil.copyfile(tryref, stagepath)
                    continue
                tryref = os.path.join('/usr/share/publican/Common_Content/common/', self.pblang, rref)
                if os.path.exists(tryref):
                    self.site.log('STAGE', self.directory.path + ref)
                    pintail.site.Site._makedirs(os.path.dirname(stagepath))
                    shutil.copyfile(tryref, stagepath)

        return refs


    @classmethod
    def create_pages(cls, source):
        """
        Create a list of `Page` objects for each output page of a DocBook document.

        If the source uses the `docbook` config option, this method implementation
        will create a `DocBookPage` object for the primary page. A DocBook document
        may create multiple output pages. The primary page will create a list of
        other pages in the document. This method returns a list containing the
        primary page and any subpages it finds.
        """
        dbfile = source.site.config.get('docbook', source.name)
        if dbfile is not None:
            if os.path.exists(os.path.join(source.get_source_path(), dbfile)):
                toppage = DocBookPage(source, dbfile)
                return [toppage] + toppage.subpages
        return []


class DocBookSubPage(pintail.site.Page):
    """
    A subpage in a DocBook document.

    A DocBook document can create multiple output files. There is exaclty one
    `DocBookPage` object for each document. It can then have any number of
    `DocBookSubPage` objects, referenced by the section id. The primary page
    does most of the work, including building all HTML, but the subpages exist
    for tracking and search purposes.
    """

    def __init__(self, db_page, element):
        pintail.site.Page.__init__(self, db_page.source, db_page.source_file)
        self._db_page = db_page
        self._sect_id = element.get('id') or element.get(XML_NS + 'id')


    @property
    def page_id(self):
        """
        The simple id of the page.

        This comes from the `id` attribute of the DocBook element that creates the page.
        """
        return self._sect_id


    @property
    def searchable(self):
        """
        Whether the page should be added to the search index.
        """
        return True


    def get_title(self, hint=None, lang=None):
        """
        Get the title of the DocBook subpage.

        This implementation prefers the `title` element in the `info` (or similar)
        element, but will use the primary display title if an info title is not found.
        """
        el = self._db_page._get_tree(lang).getroot().xpath('//*[@id = "%s" or @xml:id = "%s"]' %
                                                           (self._sect_id, self._sect_id))
        return self._db_page.get_title_node(el[0], hint=hint)


    def get_keywords(self, hint=None, lang=None):
        """
        Get the keywords of the DocBook subpage.

        This implementation looks at the `keywordset` element. It makes a
        comma-separated list from each `keyword` child element.
        """
        el = self._db_page._get_tree(lang).getroot().xpath('//*[@id = "%s" or @xml:id = "%s"]' %
                                                           (self._sect_id, self._sect_id))
        return self._db_page.get_keywords_node(el[0], hint=hint)


    def get_content(self, hint=None, lang=None):
        """
        Get the full content of the DocBook subpage.

        This implementation tries carefully not to include content from further
        subpages in the content for this subpage.
        """
        el = self._db_page._get_tree(lang).getroot().xpath('//*[@id = "%s" or @xml:id = "%s"]' %
                                                           (self._sect_id, self._sect_id))
        return self._db_page.get_content_node(el[0], hint=hint)


class DocBookTools(pintail.site.ToolsProvider, pintail.site.CssProvider):
    """
    A collection of tools for building DocBook pages.

    This class contains class methods for various Pintail extenion points
    that aren't `Page`.
    """

    @classmethod
    def build_tools(cls, site):
        """
        Build tools to be used during the build.

        This method implementation creates wrapper XSLT around the HTML transforms
        from yelp-xsl, the custom XSLT provided for the site, and any additional
        XSLT provided by extensions.
        """
        db2html = os.path.join(site.yelp_xsl_path, 'xslt', 'docbook', 'html', 'db2html.xsl')
        mallink = os.path.join(site.yelp_xsl_path, 'xslt', 'mallard', 'common', 'mal-link.xsl')

        fd = open(os.path.join(site.tools_path, 'pintail-html-docbook-local.xsl'), 'w')
        fd.write('<xsl:stylesheet' +
                 ' xmlns:xsl="http://www.w3.org/1999/XSL/Transform"' +
                 ' version="1.0">\n' +
                 '<xsl:import href="pintail-html-docbook.xsl"/>\n' +
                 '<xsl:param name="db.chunk.extension" select="$pintail.extension.link"/>\n')
        for xsl in site.get_custom_xsl():
            fd.write('<xsl:include href="%s"/>\n' % xsl)
        fd.write('</xsl:stylesheet>')
        fd.close()

        fd = open(os.path.join(site.tools_path, 'pintail-html-docbook.xsl'), 'w')
        fd.write(('<xsl:stylesheet' +
                  ' xmlns:xsl="http://www.w3.org/1999/XSL/Transform"' +
                  ' version="1.0">\n' +
                  '<xsl:import href="%s"/>\n' +
                  '<xsl:import href="%s"/>\n' +
                  '<xsl:include href="%s"/>\n' +
                  '</xsl:stylesheet>\n')
                 % (db2html, mallink, 'pintail-html.xsl'))
        fd.close()


    @classmethod
    def build_css(cls, site):
        """
        Build CSS for DocBook pages in the site.

        This method implementation uses the yelp-xsl stylesheets to generate CSS,
        so it always matches the built HTML files, and can reference params for
        things like colors. It generates a separate CSS file for each language.
        """
        xslpath = os.path.join(site.yelp_xsl_path, 'xslt')

        pintail.site.Site._makedirs(site.tools_path)
        cssxsl = os.path.join(site.tools_path, 'pintail-css-docbook.xsl')
        fd = open(cssxsl, 'w')
        fd.writelines([
            '<xsl:stylesheet',
            ' xmlns:xsl="http://www.w3.org/1999/XSL/Transform"',
            ' xmlns:exsl="http://exslt.org/common"',
            ' extension-element-prefixes="exsl"',
            ' version="1.0">\n',
            '<xsl:import href="' + xslpath + '/common/l10n.xsl"/>\n',
            '<xsl:import href="' + xslpath + '/common/color.xsl"/>\n',
            '<xsl:import href="' + xslpath + '/common/icons.xsl"/>\n',
            '<xsl:import href="' + xslpath + '/common/html.xsl"/>\n',
            '<xsl:import href="' + xslpath + '/docbook/html/db2html-css.xsl"/>\n'
            ])
        fd.write('<xsl:import href="%s"/>\n' % 'pintail-html.xsl')
        for xsl in site.get_custom_xsl():
            fd.write('<xsl:include href="%s"/>\n' % xsl)
        fd.writelines([
            '<xsl:output method="text"/>\n',
            '<xsl:param name="out"/>\n',
            '<xsl:template match="/">\n',
            '<xsl:for-each select="/*">\n',
            '<xsl:variable name="locale">\n',
            ' <xsl:choose>\n',
            '  <xsl:when test="@xml:lang">\n',
            '   <xsl:value-of select="@xml:lang"/>\n',
            '  </xsl:when>\n',
            '  <xsl:when test="@lang">\n',
            '   <xsl:value-of select="@lang"/>\n',
            '  </xsl:when>\n',
            '  <xsl:otherwise>\n',
            '   <xsl:text>C</xsl:text>\n',
            '  </xsl:otherwise>\n',
            ' </xsl:choose>\n',
            '</xsl:variable>\n',
            '<exsl:document href="{$out}" method="text">\n',
            ' <xsl:call-template name="html.css.content"/>\n',
            '</exsl:document>\n',
            '</xsl:for-each>\n',
            '</xsl:template>\n'
            '</xsl:stylesheet>\n'
            ])
        fd.close()

        seenlangs = []
        for page in site.root.iter_pages():
            if not isinstance(page, DocBookPage):
                continue
            for lc in [None] + site.get_langs():
                try:
                    doc = page._get_tree(lc).getroot()
                    lang = doc.get(XML_NS + 'lang', doc.get('lang', 'C'))
                except:
                    continue
                if lang in seenlangs:
                    continue
                seenlangs.append(lang)
                cssfile = 'pintail-docbook-' + lang + '.css'
                csspath = os.path.join(site.target_path, cssfile)
                site.log('CSS', '/' + cssfile)
                subprocess.call(['xsltproc',
                                 '-o', site.target_path,
                                 '--stringparam', 'out', csspath,
                                 cssxsl, page.get_stage_path(lc)])
                custom_css = site.config.get('custom_css')
                if custom_css is not None:
                    custom_css = os.path.join(site.topdir, custom_css)
                    fd = open(csspath, 'a')
                    fd.write(open(custom_css).read())
                    fd.close()


