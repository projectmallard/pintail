# pintail - Build static sites from collections of Mallard documents
# Copyright (c) 2015-2016 Shaun McCance <shaunm@gnome.org>
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

class MallardPage(pintail.site.Page,
                  pintail.site.ToolsProvider,
                  pintail.site.CssProvider):
    def __init__(self, directory, source_file):
        pintail.site.Page.__init__(self, directory, source_file)
        self.stage_page()
        self._tree = etree.parse(self.stage_path)
        etree.XInclude()(self._tree.getroot())
        self._mallard_page_id = self._tree.getroot().get('id')

    @property
    def page_id(self):
        return self._mallard_page_id

    @property
    def searchable(self):
        return True

    @classmethod
    def build_tools(cls, site):
        mal2html = os.path.join(site.yelp_xsl_path, 'xslt', 'mallard', 'html', 'mal2html.xsl')

        fd = open(os.path.join(site.tools_path, 'pintail-html-mallard-local.xsl'), 'w')
        fd.write('<xsl:stylesheet' +
                 ' xmlns:xsl="http://www.w3.org/1999/XSL/Transform"' +
                 ' version="1.0">\n' +
                 '<xsl:import href="pintail-html-mallard.xsl"/>\n')
        html_extension = site.config.get('html_extension') or '.html'
        fd.write('<xsl:param name="html.extension" select="' +
                 "'" + html_extension + "'" + '"/>\n')
        link_extension = site.config.get('link_extension')
        if link_extension is not None:
            fd.write('<xsl:param name="mal.link.extension" select="' +
                     "'" + link_extension + "'" + '"/>\n')
            fd.write('<xsl:param name="pintail.extension.link" select="' +
                     "'" + link_extension + "'" + '"/>\n')
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
            '<xsl:import href="' + xslpath + '/mallard/html/mal2html-page.xsl"/>\n'
            ])
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
        for cache in [site.cache_path]:
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

    def stage_page(self):
        pintail.site.Site._makedirs(self.directory.stage_path)
        subprocess.call(['xmllint', '--xinclude',
                         '-o', self.stage_path,
                         self.source_path])

    def get_cache_data(self):
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
        page = _get_node_cache(self._tree.getroot())
        page.set(CACHE_NS + 'href', self.stage_path)
        return page

    def build_html(self):
        self.site.log('HTML', self.site_id)
        pinfo = self.directory.get_special_path_info()
        cmd = ['xsltproc',
               '--stringparam', 'mal.cache.file', self.site.cache_path,
               '--stringparam', 'pintail.site.dir', self.directory.path,
               '--stringparam', 'pintail.site.root',
               self.site.config.get('site_root') or '/',
               '--stringparam', 'pintail.source.repository',
               pinfo.get('source_repository', ''),
               '--stringparam', 'pintail.source.branch',
               pinfo.get('source_branch', ''),
               '--stringparam', 'pintail.source.directory',
               pinfo.get('source_directory', ''),
               '--stringparam', 'pintail.source.file', self.source_file]
        cmd.extend(pintail.site.XslProvider.get_xsltproc_args('html', self))
        cmd.extend([
            '-o', self.target_path,
            os.path.join(self.site.tools_path, 'pintail-html-mallard-local.xsl'),
            self.stage_path])
        subprocess.call(cmd)


    def get_media(self):
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

    def get_title(self, hint=None):
        res = []
        if hint == 'search':
            res = self._tree.xpath('/mal:page/mal:info/mal:title[@type="search"]',
                                   namespaces=NS_MAP)
            if len(res) == 0:
                res = self._tree.xpath('/mal:page/mal:info/mal:title[@type="text"][@role="search"]',
                                       namespaces=NS_MAP)
        if len(res) == 0:
            res = self._tree.xpath('/mal:page/mal:info/mal:title[@type="text"][not(@role)]',
                                   namespaces=NS_MAP)
        if len(res) == 0:
            res = self._tree.xpath('/mal:page/mal:title', namespaces=NS_MAP)
        if len(res) == 0:
            return ''
        else:
            return res[-1].xpath('string(.)')

    def get_desc(self, hint=None):
        res = []
        if hint == 'search':
            res = self._tree.xpath('/mal:page/mal:info/mal:desc[@type="search"]',
                                   namespaces=NS_MAP)
            if len(res) == 0:
                res = self._tree.xpath('/mal:page/mal:info/mal:desc[@type="text"][@role="search"]',
                                       namespaces=NS_MAP)
        if len(res) == 0:
            res = self._tree.xpath('/mal:page/mal:info/mal:desc[@type="text"][not(@role)]',
                                   namespaces=NS_MAP)
        if len(res) == 0:
            res = self._tree.xpath('/mal:page/mal:info/mal:desc[not(@type)]', namespaces=NS_MAP)
        if len(res) == 0:
            return ''
        else:
            return res[-1].xpath('string(.)')

    def get_content(self, hint=None):
        # FIXME: could be good to have smarter block/inline handling, conditional
        # processing, correct block fallback. Probably should just have a mal2text
        # in yelp-xsl.
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
        return _accumulate_text(self._tree.getroot())

    @classmethod
    def get_pages(cls, directory, filename):
        if filename.endswith('.page'):
            return [MallardPage(directory, filename)]
        return []

