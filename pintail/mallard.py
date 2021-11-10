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

import copy
import os
import subprocess

from lxml import etree

import pintail.site

MAL_NS = '{http://projectmallard.org/1.0/}'
CACHE_NS = '{http://projectmallard.org/cache/1.0/}'
SITE_NS = '{http://projectmallard.org/site/1.0/}'
XML_NS = '{http://www.w3.org/XML/1998/namespace}'
NS_MAP = {
    'mal': 'http://projectmallard.org/1.0/',
    'cache': 'http://projectmallard.org/cache/1.0/'
}

class MallardPage(pintail.site.Page):
    """
    An individual Mallard page in a directory.
    """

    _html_transform = None
    _stack_transforms = {}

    def __init__(self, source, filename):
        super().__init__(source, filename)

        self.stage_page()
        self._tree = etree.parse(self.get_stage_path())
        etree.XInclude()(self._tree.getroot())
        self._mallard_page_id = self._tree.getroot().get('id')
        self._langtrees = {}
        self._notlangs = set()


    def _get_tree(self, lang=None):
        if lang is None or lang in self._notlangs:
            return self._tree
        if lang in self._langtrees:
            return self._langtrees[lang]
        if self.site.translate_page(self, lang):
            return etree.parse(self.get_stage_path(lang))
        self._notlangs.add(lang)
        return self._tree


    @property
    def page_id(self):
        """
        The simple id of the page.

        This is always the `id` attribute of the `page` element,
        regardless of the filename.
        """
        return self._mallard_page_id


    @property
    def searchable(self):
        """
        Whether the page should be added to the search index.
        """
        return True


    def stage_page(self):
        """
        Create a Mallard file in the stage.
        """
        pintail.site.Site._makedirs(self.directory.get_stage_path())
        subprocess.call(['xmllint', '--xinclude',
                         '-o', self.get_stage_path(),
                         self.get_source_path()])


    def get_cache_data(self, lang=None):
        """
        Get XML data to add to the cache, as an lxml.etree.Element object.
        """
        def _get_node_cache(node):
            ret = etree.Element(node.tag)
            ret.text = '\n'
            ret.tail = '\n'
            for attr in node.keys():
                if attr != 'id':
                    ret.set(attr, node.get(attr))
            if node.tag == MAL_NS + 'page':
                ret.set('id', self.site_id)
            elif node.get('id', None) is not None:
                ret.set('id', self.site_id + '#' + node.get('id'))
            ret.set(SITE_NS + 'dir', self.directory.path)
            for child in node:
                if child.tag == MAL_NS + 'info':
                    info = etree.Element(child.tag)
                    ret.append(info)
                    for infochild in child:
                        if infochild.tag == MAL_NS + 'link':
                            xref = infochild.get('xref', None)
                            if xref is None or xref.startswith('/'):
                                info.append(copy.deepcopy(infochild))
                            else:
                                link = etree.Element(infochild.tag)
                                link.set('xref', self.directory.path + xref)
                                for attr in infochild.keys():
                                    if attr != 'xref':
                                        link.set(attr, infochild.get(attr))
                                for linkchild in infochild:
                                    link.append(linkchild)
                                info.append(copy.deepcopy(link))
                        else:
                            info.append(copy.deepcopy(infochild))
                if child.tag == MAL_NS + 'title':
                    ret.append(copy.deepcopy(child))
                elif child.tag == MAL_NS + 'section':
                    ret.append(_get_node_cache(child))
            return ret
        page = _get_node_cache(self._get_tree(lang).getroot())
        page.set(CACHE_NS + 'href', self.get_stage_path(lang))
        return page


    def build_html(self, lang=None):
        """
        Build the HTML file for this page, possibly translated.
        """
        usestacks = (self.site.config.get('mallard_stack_dirs') == 'True')
        if usestacks:
            MallardPage._stack_transforms.setdefault(self.directory, set())
            if lang in MallardPage._stack_transforms[self.directory]:
                return
            MallardPage._stack_transforms[self.directory].add(lang)
            logid = self.directory.path
        else:
            logid = self.site_id
        if lang is not None:
            logid = lang + ' ' + logid
        self.site.log('HTML', logid)

        if MallardPage._html_transform is None:
            MallardPage._html_transform = etree.XSLT(etree.parse(os.path.join(self.site.tools_path,
                                                                              'pintail-html-mallard-local.xsl')))
        args = {}
        args['pintail.format'] = etree.XSLT.strparam('mallard')
        for pair in pintail.site.XslProvider.get_all_xsl_params('html', self, lang=lang):
            args[pair[0]] = etree.XSLT.strparam(pair[1])

        if usestacks:
            pages = [page for page in self.directory.pages if isinstance(page, MallardPage)]
            spath = os.path.join(self.directory.get_stage_path(lang), '__pintail_stack__.stack')
            with open(spath, 'w') as sfile:
                sfile.write('<stack xmlns="http://projectmallard.org/1.0/"')
                sfile.write(' xmlns:xi="http://www.w3.org/2001/XInclude">')
                for page in pages:
                    if lang is not None and self.site.translate_page(page, lang):
                        sfile.write('<xi:include href="' + page.get_stage_path(lang) + '"/>')
                    else:
                        sfile.write('<xi:include href="' + page.get_stage_path() + '"/>')
                sfile.write('</stack>')
            stree = etree.parse(spath)
            etree.XInclude()(stree.getroot())
            MallardPage._html_transform(stree, **args)
            # FIXME but also some params need to become attrs on the cache
        else:
            MallardPage._html_transform(self._get_tree(lang), **args)


    def get_media(self):
        """
        Get a list of referenced media files.

        This implementation looks for any local references in any
        `src` or `href` attributes.
        """
        refs = set()
        def _accumulate_refs(node):
            src = node.get('src', None)
            if src is not None and ':' not in src and src != '#':
                refs.add(src)
            href = node.get('href', None)
            if href is not None and ':' not in href:
                refs.add(href)
            for child in node:
                _accumulate_refs(child)
        _accumulate_refs(self._tree.getroot())
        return refs


    def get_title(self, hint=None, lang=None):
        """
        Get the title of the Mallard page.

        This implementation prefers Mallard text titles. Additionally, it will
        prefer the text title with `role="search"` if `hint` is `"search"`.
        """
        tree = self._get_tree(lang)
        res = []
        if hint == 'search':
            res = tree.xpath('/mal:page/mal:info/mal:title[@type="search"]',
                             namespaces=NS_MAP)
            if len(res) == 0:
                res = tree.xpath('/mal:page/mal:info/mal:title[@type="text"][@role="search"]',
                                 namespaces=NS_MAP)
        if len(res) == 0:
            res = tree.xpath('/mal:page/mal:info/mal:title[@type="text"][not(@role)]',
                             namespaces=NS_MAP)
        if len(res) == 0:
            res = tree.xpath('/mal:page/mal:title', namespaces=NS_MAP)
        if len(res) == 0:
            return ''
        else:
            return res[-1].xpath('string(.)')


    def get_desc(self, hint=None, lang=None):
        """
        Get the desc of the Mallard page.

        This implementation prefers Mallard text descs. Additionally, it will
        prefer the text desc with `role="search"` if `hint` is `"search"`.
        """
        tree = self._get_tree(lang)
        res = []
        if hint == 'search':
            res = tree.xpath('/mal:page/mal:info/mal:desc[@type="search"]',
                             namespaces=NS_MAP)
            if len(res) == 0:
                res = tree.xpath('/mal:page/mal:info/mal:desc[@type="text"][@role="search"]',
                                 namespaces=NS_MAP)
        if len(res) == 0:
            res = tree.xpath('/mal:page/mal:info/mal:desc[@type="text"][not(@role)]',
                             namespaces=NS_MAP)
        if len(res) == 0:
            res = tree.xpath('/mal:page/mal:info/mal:desc[not(@type)]', namespaces=NS_MAP)
        if len(res) == 0:
            return ''
        else:
            return res[-1].xpath('string(.)')


    def get_keywords(self, hint=None, lang=None):
        """
        Get the keywords of the Mallard page.

        This implementation uses the Mallard `keywords` element,
        which is expected to be finalized in Mallard 1.2.
        """
        tree = self._get_tree(lang)
        res = tree.xpath('/mal:page/mal:info/mal:keywords', namespaces=NS_MAP)
        if len(res) == 0:
            return ''
        else:
            return res[-1].xpath('string(.)')


    def get_content(self, hint=None, lang=None):
        """
        Get the full content of the Mallard page.
        """
        # FIXME: could be good to have smarter block/inline handling, conditional
        # processing, correct block fallback. Probably should just have a mal2text
        # in yelp-xsl.
        tree = self._get_tree(lang)
        def _accumulate_text(node):
            ret = ''
            for child in node:
                if not isinstance(child.tag, str):
                    continue
                if node.tag == MAL_NS + 'info':
                    continue
                ret += child.text or ''
                ret += _accumulate_text(child)
                ret += child.tail or ''
            return ret
        return _accumulate_text(tree.getroot())


    @classmethod
    def create_pages(cls, source):
        """
        Create a list of `Page` objects for each Mallard page in a source.

        This method implementation looks for all files with the `.page` extension.
        """
        pages = []
        exclude = (source.site.config.get('exclude_files', source.name) or '').split()
        for filename in os.listdir(source.get_source_path()):
            if filename in exclude:
                continue
            if os.path.isfile(os.path.join(source.get_source_path(), filename)):
                if filename.endswith('.page'):
                    pages.append(MallardPage(source, filename))
        return pages


class MallardTools(pintail.site.ToolsProvider,
                   pintail.site.CssProvider,
                   pintail.site.XslProvider):
    """
    A collection of tools for building Mallard pages.

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
        mal2html = os.path.join(site.yelp_xsl_path, 'xslt', 'mallard', 'html', 'mal2html.xsl')

        fd = open(os.path.join(site.tools_path, 'pintail-html-mallard-local.xsl'), 'w')
        fd.write('<xsl:stylesheet' +
                 ' xmlns:xsl="http://www.w3.org/1999/XSL/Transform"' +
                 ' version="1.0">\n' +
                 '<xsl:import href="pintail-html-mallard.xsl"/>\n' +
                 '<xsl:param name="mal.link.extension" select="$pintail.extension.link"/>\n')
        for xsl in site.get_custom_xsl():
            fd.write('<xsl:include href="%s"/>\n' % xsl)
        fd.write('</xsl:stylesheet>')
        fd.close()

        fd = open(os.path.join(site.tools_path, 'pintail-html-mallard.xsl'), 'w')
        fd.write(('<xsl:stylesheet' +
                  ' xmlns:xsl="http://www.w3.org/1999/XSL/Transform"' +
                  ' version="1.0">\n' +
                  '<xsl:import href="%s"/>\n' +
                  '<xsl:include href="%s"/>\n' +
                  '</xsl:stylesheet>\n')
                 % (mal2html, 'pintail-html.xsl'))
        fd.close()


    @classmethod
    def build_css(cls, site):
        """
        Build CSS for Mallard pages in the site.

        This method implementation uses the yelp-xsl stylesheets to generate CSS,
        so it always matches the built HTML files, and can reference params for
        things like colors. It generates a separate CSS file for each language.
        """
        xslpath = os.path.join(site.yelp_xsl_path, 'xslt')

        pintail.site.Site._makedirs(site.tools_path)
        cssxsl = os.path.join(site.tools_path, 'pintail-css-mallard.xsl')
        fd = open(cssxsl, 'w')
        fd.writelines([
            '<xsl:stylesheet',
            ' xmlns:xsl="http://www.w3.org/1999/XSL/Transform"',
            ' xmlns:exsl="http://exslt.org/common"',
            ' xmlns:cache="http://projectmallard.org/cache/1.0/"',
            ' xmlns:mal="http://projectmallard.org/1.0/"',
            ' extension-element-prefixes="exsl"',
            ' version="1.0">\n',
            '<xsl:import href="' + xslpath + '/common/l10n.xsl"/>\n',
            '<xsl:import href="' + xslpath + '/common/color.xsl"/>\n',
            '<xsl:import href="' + xslpath + '/common/icons.xsl"/>\n',
            '<xsl:import href="' + xslpath + '/common/html.xsl"/>\n',
            '<xsl:import href="' + xslpath + '/common/tmpl.xsl"/>\n',
            '<xsl:import href="' + xslpath + '/mallard/html/mal2html-page.xsl"/>\n'
            ])
        fd.write('<xsl:import href="%s"/>\n' % 'pintail-html.xsl')
        for xsl in site.get_custom_xsl():
            fd.write('<xsl:include href="%s"/>\n' % xsl)
        fd.writelines([
            '<xsl:output method="text"/>\n',
            '<xsl:param name="id"/>\n',
            '<xsl:param name="out"/>\n',
            '<xsl:template match="/">\n',
            '<xsl:for-each select="/cache:cache/mal:page[@id=$id]">\n',
            '<xsl:variable name="locale">\n',
            ' <xsl:choose>\n',
            '  <xsl:when test="@xml:lang">\n',
            '   <xsl:value-of select="@xml:lang"/>\n',
            '  </xsl:when>\n',
            '  <xsl:otherwise>\n',
            '   <xsl:text>C</xsl:text>\n',
            '  </xsl:otherwise>\n',
            ' </xsl:choose>\n',
            '</xsl:variable>\n',
            '<exsl:document href="{$out}" method="text">\n',
            ' <xsl:for-each select="document(@cache:href)">\n',
            '  <xsl:call-template name="html.css.content"/>\n',
            ' </xsl:for-each>\n',
            '</exsl:document>\n',
            '</xsl:for-each>\n',
            '</xsl:template>\n'
            '</xsl:stylesheet>\n'
            ])
        fd.close()

        seenlangs = []
        for lang in [None] + site.get_langs():
            cache = site.get_cache_path(lang)
            for page in etree.parse(cache).xpath('/cache:cache/mal:page', namespaces=NS_MAP):
                lang = page.get(XML_NS + 'lang', 'C')
                if lang in seenlangs:
                    continue
                seenlangs.append(lang)
                cssfile = 'pintail-mallard-' + lang + '.css'
                csspath = os.path.join(site.target_path, cssfile)
                site.log('CSS', '/' + cssfile)
                subprocess.call(['xsltproc',
                                 '-o', site.target_path,
                                 '--stringparam', 'id', page.get('id'),
                                 '--stringparam', 'out', csspath,
                                 cssxsl, cache])
                custom_css = site.config.get('custom_css')
                if custom_css is not None:
                    custom_css = os.path.join(site.topdir, custom_css)
                    fd = open(csspath, 'a')
                    fd.write(open(custom_css).read())
                    fd.close()


    @classmethod
    def get_xsl_params(cls, output, obj, lang=None):
        """
        Get a list of XSLT params for Mallard transforms.
        """
        if not (output == 'html' and isinstance(obj, MallardPage)):
            return []
        d = obj.directory
        while d is not None:
            ed = d.site.config.get('editor_mode', d.path)
            if ed == 'False':
                return []
            if ed == 'True':
                return [('mal2html.editor_mode', '1')]
            d = d.parent
        return []

