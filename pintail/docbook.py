# pintail - Build static sites from collections of Mallard documents
# Copyright (c) 2015 Shaun McCance <shaunm@gnome.org>
#
# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU Lesser General Public License as published by the Free
# Software Foundation; either version 2 of the License, or (at your option) any
# later version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE. See the GNU Lesser General Public License for more
# details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program; see the file COPYING.LGPL.  If not, write to the
# Free Software Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA
# 02111-1307, USA.

import os
import subprocess
from lxml import etree

import pintail.site

XML_NS = '{http://www.w3.org/XML/1998/namespace}'
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

class DocBookPage(pintail.site.Page, pintail.site.ToolsProvider, pintail.site.CssProvider):
    def __init__(self, directory, source_file):
        pintail.site.Page.__init__(self, directory, source_file)
        self.stage_page()
        self._tree = etree.parse(self.stage_path)
        def _accumulate_pages(node, depth, maxdepth):
            ret = []
            for child in node:
                if child.tag in DOCBOOK_CHUNKS:
                    ret.append(child)
                    if depth < maxdepth:
                        ret.extend(_accumulate_pages(child, depth + 1, maxdepth))
            return ret
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
        pages = _accumulate_pages(self._tree.getroot(), 1, maxdepth)
        self.subpages = [DocBookSubPage(self, el) for el in pages]

    @property
    def page_id(self):
        return 'index'

    @property
    def searchable(self):
        return True

    def get_title_node(self, node, hint=None):
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

    def get_title(self, hint=None):
        return self.get_title_node(self._tree.getroot(), hint=hint)

    def get_content_node(self, node, hint=None):
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

    def get_content(self, hint=None):
        return self.get_content_node(self._tree.getroot(), hint=hint)

    @classmethod
    def build_tools(cls, site):
        db2html = os.path.join(site.yelp_xsl_path, 'xslt', 'docbook', 'html', 'db2html.xsl')
        mallink = os.path.join(site.yelp_xsl_path, 'xslt', 'mallard', 'common', 'mal-link.xsl')

        fd = open(os.path.join(site.tools_path, 'pintail-html-docbook-local.xsl'), 'w')
        fd.write('<xsl:stylesheet' +
                 ' xmlns:xsl="http://www.w3.org/1999/XSL/Transform"' +
                 ' version="1.0">\n' +
                 '<xsl:import href="pintail-html-docbook.xsl"/>\n')
        html_extension = site.config.get('html_extension') or '.html'
        fd.write('<xsl:param name="html.extension" select="' +
                 "'" + html_extension + "'" + '"/>')
        link_extension = site.config.get('link_extension')
        if link_extension is not None:
            fd.write('<xsl:param name="db.chunk.extension" select="' +
                     "'" + link_extension + "'" + '"/>')
            fd.write('<xsl:param name="pintail.extension.link" select="' +
                     "'" + link_extension + "'" + '"/>\n')
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
            if isinstance(page, DocBookPage):
                try:
                    doc = etree.parse(page.source_path).getroot()
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
                                 cssxsl, page.source_path])
                custom_css = site.config.get('custom_css')
                if custom_css is not None:
                    custom_css = os.path.join(site.topdir, custom_css)
                    fd = open(csspath, 'a')
                    fd.write(open(custom_css).read())
                    fd.close()

    def stage_page(self):
        pintail.site.Site._makedirs(self.directory.stage_path)
        subprocess.call(['xmllint', '--xinclude', '--noent',
                         '-o', self.stage_path,
                         self.source_path])

    def get_cache_data(self):
        ret = None
        try:
            ret = etree.Element(PINTAIL_NS + 'external')
            ret.set('id', self.directory.path + 'index')
            ret.set(SITE_NS + 'dir', self.directory.path)
            dbfile = etree.parse(self.source_path)
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

    def build_html(self):
        self.site.log('HTML', self.site_id)
        cmd = ['xsltproc',
               '--xinclude',
               '--stringparam', 'mal.cache.file', self.site.cache_path,
               '--stringparam', 'pintail.format', 'docbook',
               '--stringparam', 'pintail.site.dir', self.directory.path,
               '--stringparam', 'pintail.site.root',
               self.site.config.get('site_root') or '/']
        cmd.extend(pintail.site.XslProvider.get_xsltproc_args('html', self))
        cmd.extend([
            '-o', self.target_path,
            os.path.join(self.site.tools_path, 'pintail-html-docbook-local.xsl'),
            self.source_path])
        subprocess.call(cmd)

    def get_media(self):
        return []
        refs = set()
        def _accumulate_refs(node):
            src = node.get('src', None)
            if src is not None and ':' not in src:
                refs.add(src)
            href = node.get('href', None)
            if href is not None and ':' not in href:
                refs.add(href)
            for child in node:
                _accumulate_refs(child)
        _accumulate_refs(self._tree.getroot())
        return refs

    @classmethod
    def get_pages(cls, directory, filename):
        dbfile = directory.site.config.get('docbook', directory.path)
        if filename == dbfile:
            toppage = DocBookPage(directory, filename)
            return [toppage] + toppage.subpages
        return []

class DocBookSubPage(pintail.site.Page):
    def __init__(self, db_page, element):
        pintail.site.Page.__init__(self, db_page.directory, db_page.source_file)
        self._db_page = db_page
        self._element = element
        self._sect_id = element.get('id') or element.get(XML_NS + 'id')

    @property
    def page_id(self):
        return self._sect_id

    @property
    def searchable(self):
        return True

    def get_title(self, hint=None):
        return self._db_page.get_title_node(self._element, hint=hint)

    def get_content(self, hint=None):
        return self._db_page.get_content_node(self._element, hint=hint)
