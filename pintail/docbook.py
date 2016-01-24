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
# Free Software Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA
# 02111-1307, USA.

import os
import subprocess

from . import core

class DocBookPage(core.Page, core.ToolsProvider):
    def __init__(self, directory, source_file):
        core.Page.__init__(self, directory, source_file)
        self.page_id = 'index'
        return
        self.stage_page()
        self._tree = etree.parse(self.stage_path)
        etree.XInclude()(self._tree.getroot())
        self.page_id = self._tree.getroot().get('id')
        self.db2html = os.path.join(self.site.tools_path, 'pintail-html-docbook-local.xsl')

    @classmethod
    def build_tools(cls, site):
        db2html = os.path.join(site.yelp_xsl_path, 'xslt', 'docbook', 'html', 'db2html.xsl')

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
        custom_xsl = site.config.get('custom_xsl')
        if custom_xsl is not None:
            custom_xsl = os.path.join(site.topdir, custom_xsl)
            fd.write('<xsl:include href="%s"/>\n' % custom_xsl)
        fd.write('</xsl:stylesheet>')
        fd.close()

        fd = open(os.path.join(site.tools_path, 'pintail-html-docbook.xsl'), 'w')
        fd.write(('<xsl:stylesheet' +
                  ' xmlns:xsl="http://www.w3.org/1999/XSL/Transform"' +
                  ' version="1.0">\n' +
                  '<xsl:import href="%s"/>\n' +
                  '<xsl:include href="%s"/>\n' +
                  '</xsl:stylesheet>\n')
                 % (db2html,
                    'site2html.xsl'))
        fd.close()

    def stage_page(self):
        return
        core.Site._makedirs(self.directory.stage_path)
        subprocess.call(['xmllint', '--xinclude',
                         '-o', self.stage_path,
                         self.source_path])

    def get_cache_data(self):
        return
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
                                info.append(infochild)
                            else:
                                link = etree.Element(infochild.tag)
                                link.set('xref', self.directory.path + xref)
                                for attr in infochild.keys():
                                    if attr != 'xref':
                                        link.set(attr, infochild.get(attr))
                                for linkchild in infochild:
                                    link.append(linkchild)
                                info.append(link)
                        else:
                            info.append(infochild)
                if child.tag == MAL_NS + 'title':
                    ret.append(child)
                elif child.tag == MAL_NS + 'section':
                    ret.append(_get_node_cache(child))
            return ret
        page = _get_node_cache(self._tree.getroot())
        page.set(CACHE_NS + 'href', self.stage_path)
        return page

    def build_html(self):
        self.site.echo('HTML', self.directory.path, self.target_file)
        print(self.source_path)
        subprocess.call(['xsltproc',
                         '--xinclude',
                         '--stringparam', 'mal.site.root',
                         self.site.config.get('site_root') or '/',
                         '-o', self.target_path,
                         self.db2html, self.source_path])

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
            return [DocBookPage(directory, filename)]
        return []
