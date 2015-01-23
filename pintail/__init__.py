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

import codecs
import configparser
import os
import shutil
import subprocess
import sys

from lxml import etree

MAL_NS = '{http://projectmallard.org/1.0/}'
CACHE_NS = '{http://projectmallard.org/cache/1.0/}'
SITE_NS = '{http://projectmallard.org/site/1.0/}'


class DuplicatePageException(Exception):
    def __init__(self, directory, message):
        self.message = message
        self.parser = directory


class Page:
    def __init__(self, directory, source_file):
        self.site = directory.site
        self.directory = directory
        self.source_file = source_file
        self.source_path = os.path.join(directory.source_path, source_file)
        self.stage_file = source_file
        self.stage_path = os.path.join(directory.stage_path, self.stage_file)
        self.target_extension = '.html'
        self.page_id = None

    @property
    def target_file(self):
        return self.page_id + self.target_extension

    @property
    def target_path(self):
        return os.path.join(self.directory.target_path, self.target_file)

    @property
    def site_id(self):
        return self.directory.path + self.page_id

    def build_stage(self):
        subprocess.call(['xmllint', '--xinclude',
                         '-o', self.stage_path,
                         self.source_path])

    def get_cache_data(self):
        return None

    def build_html(self):
        return

    @classmethod
    def get_pages(cls, directory, filename):
        return []


class MallardPage(Page):
    def __init__(self, directory, source_file):
        Page.__init__(self, directory, source_file)
        self._tree = etree.parse(open(self.source_path))
        etree.XInclude()(self._tree.getroot())
        self.page_id = self._tree.getroot().get('id')

    def get_cache_data(self):
        def _get_node_cache(node):
            ret = etree.Element(node.tag)
            ret.text = '\n'
            ret.tail = '\n'
            if node.tag == MAL_NS + 'page':
                ret.set('id', self.site_id)
            elif node.get('id', None) is not None:
                ret.set('id', self.site_id + '#' + node.get('id'))
            ret.set(SITE_NS + 'dir', self.directory.path)
            for child in node:
                if child.tag in (MAL_NS + 'info', MAL_NS + 'title'):
                    ret.append(child)
                elif child.tag == MAL_NS + 'section':
                    ret.append(_get_node_cache(child))
            return ret
        page = _get_node_cache(self._tree.getroot())
        page.set(CACHE_NS + 'href', self.stage_path)
        return page

    def build_html(self):
        subprocess.call(['xsltproc',
                         '--stringparam', 'mal.cache.file', self.site.cache_path,
                         '--stringparam', 'mal.site.dir', self.directory.path,
                         '--stringparam', 'mal.site.root',
                         self.site.config.get('pintail', 'site_root', fallback='/'),
                         '-o', self.target_path,
                         self.site.xslt_path,
                         self.stage_path])

    @classmethod
    def get_pages(cls, directory, filename):
        if filename.endswith('.page'):
            return [MallardPage(directory, filename)]
        return []


class Directory:
    def __init__(self, site, path):
        self.site = site
        self.path = path
        self.source_path = os.path.join(self.site.topdir,
                                        self.path[1:])
        self.stage_path = os.path.join(self.site.stage_path,
                                       self.path[1:])
        self.target_path = os.path.join(self.site.target_path,
                                        self.path[1:])
        self.subdirs = []
        self.pages = []
        self._by_page_id = {}
        for name in os.listdir(self.source_path):
            if os.path.isdir(os.path.join(self.source_path, name)):
                subpath = self.path + name + '/'
                if self.site.get_ignore_directory(subpath):
                    continue
                subdir = Directory(self.site, subpath)
                self.subdirs.append(subdir)
            else:
                for cls in Page.__subclasses__():
                    for page in cls.get_pages(self, name):
                        if page.page_id in self._by_page_id:
                            raise DuplicatePageException(self,
                                                         'Duplicate page id ' +
                                                         page.page_id)
                        self._by_page_id[page.page_id] = page
                        self.pages.append(page)

    def iter_directories(self):
        yield self
        for subdir in self.subdirs:
            yield from subdir.iter_directories()

    def iter_pages(self):
        for page in self.pages:
            yield page
        for subdir in self.subdirs:
            yield from subdir.iter_pages()

    def build_stage(self):
        os.makedirs(self.stage_path, exist_ok=True)
        for subdir in self.subdirs:
            subdir.build_stage()
        for page in self.pages:
            page.build_stage()

    def build_html(self):
        os.makedirs(self.target_path, exist_ok=True)
        for subdir in self.subdirs:
            subdir.build_html()
        for page in self.pages:
            page.build_html()


class Site:
    def __init__(self, config):
        self.config = configparser.ConfigParser()
        self.config.read(config)
        self.topdir = os.path.dirname(config)
        self.stage_path = os.path.join(self.topdir, '__stage__')
        self.target_path = os.path.join(self.topdir, '__build__')
        self.tools_path = os.path.join(self.topdir, '__tools__')
        self.root = Directory(self, '/')

        self.cache_path = os.path.join(self.tools_path, 'pintail.cache')
        self.xslt_path = os.path.join(self.tools_path, 'pintail.xsl')

    @classmethod
    def init_site(cls, directory):
        cfgfile = os.path.join(directory, 'pintail.cfg')
        if os.path.exists(cfgfile):
            sys.stderr.write('pintail.cfg file already exists\n')
            sys.exit(1)
        from pkg_resources import resource_string
        sample = resource_string(__name__, 'sample.cfg')
        fd = open(cfgfile, 'w')
        fd.write(codecs.decode(sample, 'utf-8'))
        fd.close()


    def build(self):
        self.build_stage()
        self.build_cache()
        self.build_xslt()
        self.build_html()
        self.build_css()

    def build_stage(self):
        if os.path.exists(self.stage_path):
            shutil.rmtree(self.stage_path)
        self.root.build_stage()

    def build_cache(self):
        cache = etree.Element(CACHE_NS + 'cache', nsmap={
            None: 'http://projectmallard.org/1.0/',
            'cache': 'http://projectmallard.org/cache/1.0/',
            'site': 'http://projectmallard.org/site/1.0/'
        })
        for page in self.root.iter_pages():
            cdata = page.get_cache_data()
            if cdata is not None:
                cache.append(cdata)
        os.makedirs(self.tools_path, exist_ok=True)
        cache.getroottree().write(self.cache_path,
                                  pretty_print=True)

    def build_xslt(self):
        mal2html = subprocess.check_output(['pkg-config',
                                            '--variable', 'mal2html',
                                            'yelp-xsl'],
                                           universal_newlines=True)
        mal2html = mal2html.strip()
        if mal2html == '':
            print('FIXME: mal2html not found')
        os.makedirs(self.tools_path, exist_ok=True)

        fd = open(self.xslt_path, 'w')
        fd.write('<xsl:stylesheet' +
                 ' xmlns:xsl="http://www.w3.org/1999/XSL/Transform"' +
                 ' version="1.0">\n' +
                 '<xsl:import href="pintail-site.xsl"/>\n')
        custom_xsl = self.config['pintail'].get('custom_xsl', None)
        if custom_xsl is not None:
            custom_xsl = os.path.join(self.topdir, custom_xsl)
            fd.write('<xsl:include href="%s"/>\n' % custom_xsl)
        fd.write('</xsl:stylesheet>')
        fd.close()

        fd = open(os.path.join(os.path.dirname(self.xslt_path),
                               'pintail-site.xsl'), 'w')
        fd.write(('<xsl:stylesheet' +
                  ' xmlns:xsl="http://www.w3.org/1999/XSL/Transform"' +
                  ' version="1.0">\n' +
                  '<xsl:import href="%s"/>\n' +
                  '<xsl:include href="%s"/>\n' +
                  '</xsl:stylesheet>\n')
                 % (mal2html,
                    'site2html.xsl'))
        fd.close()

        from pkg_resources import resource_string
        site2html = resource_string(__name__, 'site2html.xsl')
        fd = open(os.path.join(os.path.dirname(self.xslt_path),
                               'site2html.xsl'), 'w')
        fd.write(codecs.decode(site2html, 'utf-8'))
        fd.close()

    def build_html(self):
        if os.path.exists(self.target_path):
            shutil.rmtree(self.target_path)
        self.root.build_html()

    def build_css(self):
        xslpath = subprocess.check_output(['pkg-config',
                                           '--variable', 'xsltdir',
                                           'yelp-xsl'],
                                          universal_newlines=True)
        xslpath = xslpath.strip()
        if xslpath == '':
            print('FIXME: yelp-xsl not found')

        os.makedirs(self.tools_path, exist_ok=True)
        cssxsl = os.path.join(self.tools_path, 'pintail-css.xsl')
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
        custom_xsl = self.config['pintail'].get('custom_xsl', None)
        if custom_xsl is not None:
            custom_xsl = os.path.join(self.topdir, custom_xsl)
            fd.write('<xsl:include href="%s"/>\n' % custom_xsl)
        fd.writelines([
            '<xsl:output method="text"/>\n',
            '<xsl:template match="/">\n',
            '<xsl:for-each select="/cache:cache/mal:page[\n',
            ' (@xml:lang and\n',
            '  not(@xml:lang = preceding-sibling::mal:page/@xml:lang)) or\n',
            ' (not(@xml:lang) and\n',
            '  not(preceding-sibling::mal:page[not(@xml:lang)])) ]">\n',
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
            '<exsl:document href="' + self.target_path + '/{$locale}.css" method="text">\n',
            ' <xsl:for-each select="document(@cache:href)">\n',
            '  <xsl:call-template name="html.css.content"/>\n',
            ' </xsl:for-each>\n',
            '</exsl:document>\n',
            '</xsl:for-each>\n',
            '</xsl:template>\n'
            '</xsl:stylesheet>\n'
            ])
        fd.close()

        subprocess.call(['xsltproc',
                         '-o', self.target_path,
                         cssxsl, self.cache_path])

    def get_ignore_directory(self, directory):
        if directory in ('/__stage__/', '/__build__/'):
            return True
        # FIXME: use an ignore key in config
        if directory == '/.git/':
            return True
        return False
