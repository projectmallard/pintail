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

import codecs
import configparser
import copy
import datetime
import glob
import importlib
import logging
import os
import shutil
import subprocess
import sys

from lxml import etree

MAL_NS = '{http://projectmallard.org/1.0/}'
CACHE_NS = '{http://projectmallard.org/cache/1.0/}'
SITE_NS = '{http://projectmallard.org/site/1.0/}'
XML_NS = '{http://www.w3.org/XML/1998/namespace}'
NS_MAP = {
    'mal': 'http://projectmallard.org/1.0/',
    'cache': 'http://projectmallard.org/cache/1.0/'
}


class DuplicatePageException(Exception):
    def __init__(self, directory, message):
        self.message = message
        self.parser = directory


class Extendable:
    """
    The base class for all plugins in Pintail.
    """
    @classmethod
    def iter_subclasses(cls, filter=None):
        """
        Iterate over all subclasses, recursing to any depth.

        This is a convenient way to iterate all plugins of a certain type.
        The optional `filter` parameter lets you provide a name of a function.
        A class will only be yielded if it defines that function explicitly,
        rather than inherits it from a parent class.
        """
        for cls in cls.__subclasses__():
            if filter is None or filter in cls.__dict__:
                yield cls
            yield from cls.iter_subclasses(filter)


class ToolsProvider(Extendable):
    """
    Extension point to provide extra tools to be used during the build.

    This method allows extensions to create any tools or other files they need
    during the build process. This is most frequently used to create XSLT files
    that are either used directly in `build_html`, or are inserted as customizations
    using `XslProvider.get_xsl`.
    """
    @classmethod
    def build_tools(cls, site):
        """
        Build tools to be used during the build.

        Extensions should override this method to create any tools they need
        later in the build process.
        """
        pass


class CssProvider(Extendable):
    """
    Extension point to provide CSS files in the built site.
    """
    @classmethod
    def build_css(cls, site):
        """
        Build CSS for the site.

        Extensions should override tis method to create any CSS files that
        are referenced from built HTML files.
        """
        pass


class XslProvider(Extendable):
    """
    Extension point to provide XSLT or XSLT params.

    This extension point allows you to provide extra XSLT files with `get_xsl`,
    as well as provide XSLT params with `get_xsl_params`. You can implement
    only one or both as needed.
    """

    @classmethod
    def get_xsl(cls, site):
        """
        Get a list of additional XSLT files to include.

        Extensions should implement this method if they have additional XSLT files
        that should get included into the main transformations. It is called by
        `Site.get_custom_xsl` when generating XSLT to build files. If you need to
        generate the XSLT files as well, implement `ToolsProvider`.
        """
        return []


    @classmethod
    def get_xsl_params(cls, output, obj, lang=None):
        """
        Get a list of XSLT params provided by an extension.

        Implementations of this method are called by `get_all_xsl_params`.
        Extensions should use this to provide additional XSLT params.
        The return value is a list of tuples, where each tuple is a pair with
        the param name and the param value. The param value is always a string.

        The `output` parameter is a string specifying the output format. It is
        usually `"html"`, but extensions could create other output formats.

        The `obj` parameter is an object that a transform will be applied to.
        It is usually an instance of a `Page` subclass, but it could be something
        else. Always check `obj` before making assumptions.
        """
        return []


    @classmethod
    def get_all_xsl_params(cls, output, obj, lang=None):
        """
        Get all XSLT params for a transform target.

        This method should not be overridden. It calls `get_xsl_params` on all
        subclasses of `XslProvider`, and it adds various common params that are
        used across all of Pintail. The return value is a list of tuples, where
        each tuple is a pair with the param name and the param value. The param
        value is always a string.

        The `output` parameter is a string specifying the output format. It is
        usually `"html"`, but extensions could create other output formats.

        The `obj` parameter is an object that a transform will be applied to.
        It is usually an instance of a `Page` subclass, but it could be something
        else. Always check `obj` before making assumptions.
        """
        ret = []
        if output == 'html' and hasattr(obj, 'site'):
            html_extension = obj.site.config.get('html_extension') or '.html'
            if lang is None:
                ret.append(('html.extension', '.html'))
            else:
                ret.append(('html.extension', '.html.' + lang))
            link_extension = obj.site.config.get('link_extension') or html_extension
            ret.append(('pintail.extension.link', link_extension))
        if hasattr(obj, 'site'):
            ret.append(('mal.cache.file', obj.site.get_cache_path(lang)))
            if hasattr(obj, 'directory'):
                ret.append(('pintail.site.root', obj.site.config.get_site_root(obj.directory.path)))
            elif isinstance(obj, Directory):
                ret.append(('pintail.site.root', obj.site.config.get_site_root(obj.path)))
            else:
                ret.append(('pintail.site.root', obj.site.config.get_site_root()))
        if hasattr(obj, 'directory'):
            ret.append(('pintail.site.dir', obj.directory.path))
            if output == 'html':
                ret.append(('html.output.prefix', obj.directory.get_target_path(lang)))
        if hasattr(obj, 'source_file'):
            ret.append(('pintail.source.file', obj.source_file))
        now = datetime.datetime.now()
        ret.append(('pintail.date', now.strftime('%Y-%m-%d')))
        ret.append(('pintail.time', now.strftime('%T')))
        for c in XslProvider.iter_subclasses('get_xsl_params'):
            ret.extend(c.get_xsl_params(output, obj, lang))
        return ret


    @classmethod
    def get_xsltproc_args(cls, output, obj, lang=None):
        # Drop this function in the future if we decide to keep DocBook using
        # lxml.etree.XSLT instead of calling xsltproc.
        ret = []
        for pair in cls.get_all_xsl_params(output, obj, lang=lang):
            ret.extend(['--stringparam', pair[0], pair[1]])
        return ret


class Page(Extendable):
    """
    An individual page in a directory.

    Each page belongs to one directory and comes from one source.
    It is uniquely identified in the directory with the `page_id` parameter,
    and it is uniquely identified in the site with the `site_id` parameter.

    The page is the smallest addressable unit in a Pintail site.
    There should be a `Page` object for each output page that you may
    want to link to, translate, or have in the search index.
    In some cases, a single source file creates multiple output pages.
    In those cases, there should be a `Page` object for each output page,
    even though all pages might be built in a single pass.

    A `Page` object is responsible for building output, getting media files,
    and extracting search data. It does this both for the original document
    and for all translations.
    """

    def __init__(self, source, filename):
        self.source = source
        self.directory = source.directory
        self.site = source.site

        self._source_file = filename
        self._search_domains = None


    @property
    def page_id(self):
        """
        The simple id of the page.

        This usually comes from either an id attribute or a base filename,
        and it usually serves as the base filename of the target file.
        Two pages in the same directory cannot have the same id.
        """
        return None


    @property
    def site_id(self):
        """
        The fully qualified site id of the page.

        The site id of a page is the path of the containing directory and the page id.
        It must be unique across the entire site.
        """
        return self.directory.path + self.page_id


    @property
    def site_path(self):
        """
        The full absolute path to the file in the site.

        This is suitable for linking.
        It includes the directory path as well as the site root.
        It also includes the link extension.
        """
        root = self.site.config.get_site_root(self.directory.path)
        ext = self.site.config.get('link_extension')
        if ext is None:
            ext = self.site.config.get('html_extension') or '.html'
        return root + self.site_id[1:] + ext


    @property
    def source_file(self):
        """
        The name of the source file for this page. 
        """
        return self._source_file


    def get_source_path(self):
        """
        The absolute path to the source file for this page.
        """
        return os.path.join(self.source.get_source_path(), self.source_file)


    @property
    def stage_file(self):
        """
        The name of the staged file for this page.
        """
        return self.source_file


    def get_stage_path(self, lang=None):
        """
        The absolute path to the staged file for this page.
        """
        return os.path.join(self.directory.get_stage_path(lang), self.stage_file)


    @property
    def target_file(self):
        """
        The name of the target file for this page.
        """
        return self.page_id + self.target_extension


    def get_target_path(self, lang=None):
        """
        The absolute path to the target file for this page.

        This will often just be the directory's target path plus the target file name.
        However, translation providers may modify the path in various ways.
        """
        return self.site.get_page_target_path(self, lang)


    @property
    def target_extension(self):
        """
        The file extension for output files.
        """
        return self.site.config.get('html_extension') or '.html'


    @property
    def searchable(self):
        """
        Whether the page should be added to the search index.

        This is False by default for the base class,
        but most page extensions should set this to True.
        """
        return False


    def get_cache_data(self, lang=None):
        """
        Get XML data to add to the cache, as an lxml.etree.Element object.

        For most page types, each page should provide information for the cache.
        For formats that use a Mallard-like toolchain, this is usually a `page` element
        containing only certain metadata and child elements.
        For other formats, a `pintail:external` element can be used instead.

        For information on Mallard cache files, see http://projectmallard.org/cache/1.1/
        """
        return None


    def get_media(self):
        """
        Get a list of referenced media files.

        Pages can return a list of images, videos, and other referenced media
        so that it can be copied into the built site automatically. The return
        value is a list of strings, where each string is a relative path. Media
        files should exist in either the page's source or in the stage.
        """
        return []


    def get_title(self, hint=None, lang=None):
        """
        Get the title of the page.

        If the `lang` parameter is not `None`, get a translated title.
        Otherwise, get the title in the source language.
        The `hint` parameter is a string indicating where this title will be used.
        For example, the `"search"` hint is used when the title is used in a search index.
        """
        return ''


    def get_desc(self, hint=None, lang=None):
        """
        Get the desc of the page.

        If the `lang` parameter is not `None`, get a translated desc.
        Otherwise, get the desc in the source language.
        The `hint` parameter is a string indicating where this desc will be used.
        For example, the `"search"` hint is used when the desc is used in a search index.
        """
        return ''


    def get_keywords(self, hint=None, lang=None):
        """
        Get the keywords of the page.

        The return value should be a comma-separated list of keywords.
        If the `lang` parameter is not `None`, get translated keywords.
        Otherwise, get the keywords in the source language.
        The `hint` parameter is a string indicating where these keywords will be used.
        For example, the `"search"` hint is used when the keywords is used in a search index.
        """
        return ''


    def get_content(self, hint=None, lang=None):
        """
        Get the full content of the page.

        This is not expected to be formatted in a way that is pleasant to read.
        It is mostly used for full-text search.
        If the `lang` parameter is not `None`, get translated content.
        Otherwise, get the content in the source language.
        The `hint` parameter is a string indicating where this content will be used.
        For example, the `"search"` hint is used when the content is used in a search index.
        """
        return ''


    def build_html(self, lang=None):
        """
        Build the HTML file for this page, possibly translated.

        Extensions should override this method to create the HTML output
        from source or stage files. If the `lang` parameter is not `None`,
        HTML should be built from the appropriate translated file.
        """
        return


    def get_search_domains(self):
        """
        Get a list of search domains for the page.

        Search domains allow you to restrict where search results come from.
        Each page has its data added to each search domain in its list.
        When a user starts a search from a page, it defaults to searching
        in the page's first domain.

        See the docstring on `Directory.get_search_domains` for more information
        on how search domains work.

        This method looks at the search domains returned by calling
        `get_search_domains` on the containing `Directory` object.
        It includes any domains in that list. For any page-domain mapping,
        it includes just the domain, and only if the page ID matches.
        The return value of this method is a list of strings only.
        """
        if self._search_domains is not None:
            return self._search_domains

        dms = self.directory.get_search_domains()
        if dms[0] == 'none':
            return ['none']
        ret = []
        for dm in dms:
            if isinstance(dm, list):
                if dm[0] == self.page_id:
                    if dm[1] == 'none':
                        return ['none']
                    else:
                        ret.append(dm[1])
            else:
                ret.append(dm)
        return ret


    @classmethod
    def create_pages(cls, source):
        """
        Create a list of `Page` objects for each page in a source.

        This method should be overridden by extensions.
        If this page extension recognizes any files in the source directory,
        or can otherwise create pages for the directory, then it should return
        a list of `Page` objects, one for each page it can provide. Note that
        some formats might create multiple output pages from a single source
        document. In these cases, one `Page` objecct should be created for
        each output page, even if it shares a source file with other pages.
        """
        return []


class Directory(Extendable):
    """
    A directory in the built output.

    Each directory contains one or more sources as `Source` objects.
    For many simple sites, each directory will have one source.
    However, Pintail can merge files from multiple sources into a directory.
    Each directory also has a list of subdirectories and a list of pages.

    The path of a directory represents where it goes in the build output,
    as well as the portion of the URL after the site root.
    We always start and end paths with a slash in Pintail.
    The path also serves as the config key.
    For simple sources, it's also where pages can be found in the source.
    """

    def __init__(self, site, path, *, parent=None):
        self.site = site
        self.path = path
        self.parent = parent
        self.pages = []
        self.subdirs = []
        self.sources = []
        self._search_domains = None
        self.scan_directory()


    @property
    def translation_provider(self):
        """
        Get the translation provider for the directory.

        Currently, this is just the translation provider for the entire site.
        To allow per-directory translation providers in the future, any code
        using translation providers should use this directory property
        whenever possible.
        """
        return self.site.translation_provider


    def get_stage_path(self, lang=None):
        """
        The absolute path to the directory for staged files in this directory.
        """
        return os.path.join(self.site.get_stage_path(lang), self.path[1:])


    def get_target_path(self, lang=None):
        """
        The absolute path to the target directory.

        This will often just be the site's target path plus the directory path.
        However, translation providers may modify the path in various ways.
        """
        return self.site.get_directory_target_path(self, lang)


    def scan_directory(self):
        """
        Scan the directory for sources, subdirectories, and pages.

        This method is responsible for locating all sources for the directory,
        checking those sources for subdirectories, asking all `Page` implementations
        to provide pages for each source, and recursing into subdirectories.
        It is called automatically by __init__.
        """

        # If we've scanned and found sources before, just exit
        if len(self.sources) != 0:
            return
        # If the path corresponds to an actual on-disk directory,
        # make a plain old source from that.
        if os.path.isdir(os.path.join(self.site.srcdir, self.path[1:])):
            self.sources.append(Source(self, self.path))
        # Give each Source extension a chance to provide sources
        # for this directory with this path.
        for cls in Source.iter_subclasses('create_sources'):
            self.sources.extend(cls.create_sources(self, self.path))
        # Finally, if there are additional sources listed in the config,
        # give each Source extension a chance to provide sources for
        # each of those sources.
        for source in (self.site.config.get('sources', self.path) or '').split():
            for cls in Source.iter_subclasses('create_sources'):
                self.sources.extend(cls.create_sources(self, source))

        # Now that we have our sources, look for subdirectories of this
        # directory, using all sources.
        for source in self.sources:
            for name in os.listdir(source.get_source_path()):
                if os.path.isdir(os.path.join(source.get_source_path(), name)):
                    subpath = self.path + name + '/'
                    if self.site.get_ignore_directory(subpath):
                        continue
                    self.subdirs.append(Directory(self.site, subpath, parent=self))

        # Finally, ask each Page extension to provide a list of pages for each source
        by_page_id = {}
        for source in self.sources:
            for cls in Page.iter_subclasses('create_pages'):
                for page in cls.create_pages(source):
                    if page.page_id in by_page_id:
                        raise DuplicatePageException(self,
                                                     'Duplicate page id ' + page.page_id)
                    by_page_id[page.page_id] = page
                    self.pages.append(page)
                    source.pages.append(page)


    def iter_directories(self):
        """
        Iterate over this directory and all subdirectories at any depth.
        """
        yield self
        for subdir in self.subdirs:
            yield from subdir.iter_directories()


    def iter_pages(self):
        """
        Iterate over all pages in this directory and all subdirectories at any depth.
        """
        for page in self.pages:
            yield page
        for subdir in self.subdirs:
            yield from subdir.iter_pages()


    def get_search_domains(self):
        """
        Get a list of search domains for the directory.

        Search domains allow you to restrict where search results come from.
        Each page has its data added to each search domain in its list.
        When a user starts a search from a page, it defaults to searching
        in the page's first domain.

        This method looks at the `search_domains` config option and returns
        a list of search domains or page mappings for search domains.
        Each component in the space-separated list could be a search domain,
        a keyword for a search domain, or a mapping from a page ID to a domain.

        Search domains look like directory paths. They always start with a slash.
        For many directories, the search domain should just be that directory.
        There's even a special keyword for that, `self`. There are four keywords:

        * `self` - The current directory path.
        * `parent` - The primary search domain of the parent directory.
        * `global` - The top directory path, `/`.
        * `none` - No search domain. Pages will not be indexed.

        Components in the domain list can also be page mappings.
        These are of the form `page_id:search_domain`. In these cases,
        the value in the return list will be a list with the page ID and the domain.
        The `get_search_domains` method on `Page` will only include the domains
        that apply to that page.
        """
        if self._search_domains is not None:
            return self._search_domains

        domains = self.site.config.get('search_domain', self.path)
        if domains is None:
            domains = 'parent'
        domains = domains.split()

        def _resolve(domain):
            if domain.startswith('/'):
                return domain
            elif domain == 'self':
                return self.path
            elif domain == 'global':
                return '/'
            elif domain == 'none':
                return 'none'
            elif self.parent is None:
                return '/'
            else:
                return self.parent.get_search_domains()[0]

        for i in range(len(domains)):
            if ':' in domains[i]:
                domains[i] = domains[i].split(':', 1)
                domains[i][1] = _resolve(domains[i][1])
            else:
                domains[i] = _resolve(domains[i])

        if isinstance(domains[0], list):
            domains.prepend(self.parent.get_search_domains[0])

        self._search_domains = domains
        return self._search_domains


    def _maketargetdirs(self):
        Site._makedirs(self.get_target_path())
        if self.translation_provider is not None:
            for lc in self.translation_provider.get_directory_langs(self):
                Site._makedirs(self.get_target_path(lc))


    def build_html(self):
        """
        Build HTML files for pages in this directory and subdirectories.

        This method calls `build_html` on each subdirectory and each page it contains.
        It also queries the translation provider for translations,
        and calls `build_html` on each page with those languages.
        """
        for subdir in self.subdirs:
            subdir.build_html()
        if not self.site.get_filter(self):
            return
        self._maketargetdirs()
        for page in self.pages:
            if not self.site.get_filter(page):
                continue
            page.build_html()
            if self.translation_provider is not None:
                for lc in self.translation_provider.get_directory_langs(self):
                    page.build_html(lc)


    def build_media(self):
        """
        Copy media files into the build directory.

        Each page is expected to be able to provide a list of media files it references.
        Media files could be images or videos, but they could also be any additional files.
        This method looks at all pages in the directory for media files,
        then attempts to copy each of those files into the target directory.
        It looks in both the source trees and the stage,
        so built media files in the stage will be handled here.
        This method also recurses into subdirectories.
        """
        for subdir in self.subdirs:
            subdir.build_media()
        if not self.site.get_filter(self):
            return
        self._maketargetdirs()
        media = {}
        for page in self.pages:
            if not self.site.get_filter(page):
                continue
            # If two pages from different sources provide the file,
            # right now it's completely random which one will win.
            for filename in page.get_media():
                media[filename] = page.source
        for fname in media:
            source = media[fname]
            langs = [None]
            if self.translation_provider is not None:
                langs += self.translation_provider.get_directory_langs(self)
            for lc in langs:
                if lc is not None:
                    tr = self.translation_provider.translate_media(source, fname, lc)
                    if not tr:
                        continue
                    if fname.startswith('/'):
                        # These have to be managed with extra_files for now
                        continue
                    mediasrc = os.path.join(self.get_stage_path(lc), fname)
                    self.site.log('MEDIA', lc + ' ' + self.path + fname)
                else:
                    if fname.startswith('/'):
                        mediasrc = os.path.join(self.site.topdir, fname[1:])
                    else:
                        # The file might be generated, in which case it's in the
                        # stage directory. But we don't stage static media files,
                        # so those are just in the source directory.
                        mediasrc = os.path.join(self.get_stage_path(), fname)
                        if not os.path.exists(mediasrc):
                            mediasrc = os.path.join(source.get_source_path(), fname)
                    self.site.log('MEDIA', self.path + fname)
                target = self.site.get_media_target_path(self, fname, lc)
                Site._makedirs(os.path.dirname(target))
                try:
                    shutil.copyfile(mediasrc, target)
                except:
                    self.site.logger.warn('Could not copy file %s' % fname)


    def build_files(self):
        """
        Copy extra files into the build directory.

        This method looks at the `extra_files` config option for
        additional files that can't be found automatically.
        It treats `extra_files` as a space-separated list of globs.
        Each glob is checked against each source in the directory.
        This method also recurses into subdirectories.
        """
        for subdir in self.subdirs:
            subdir.build_files()
        if not self.site.get_filter(self):
            return
        Site._makedirs(self.get_stage_path())
        globs = self.site.config.get('extra_files', self.path)
        if globs is not None:
            for glb in globs.split():
                for source in self.sources:
                    # This won't do what it should if the path has anything
                    # glob-like in it. Would be nice if glob() could take
                    # a base path that isn't glob-interpreted.
                    files = glob.glob(os.path.join(source.get_source_path(), glb))
                    for fname in files:
                        self.site.log('FILE', self.path + os.path.basename(fname))
                        shutil.copyfile(fname,
                                        os.path.join(self.get_target_path(),
                                                     os.path.basename(fname)))


    def build_feeds(self):
        """
        Build Atom feeds for this directory.

        If the directory lists a file name in the `feed_atom` config option,
        then this method creates an Atom feed from the pages in the directory.
        This method also recurses into subdirectories.
        """
        for subdir in self.subdirs:
            subdir.build_feeds()
        if not self.site.get_filter(self):
            return
        atomfile = self.site.config.get('feed_atom', self.path)
        if atomfile is not None:
            self.site.log('ATOM', self.path + atomfile)

            Site._makedirs(self.site.tools_path)
            for xsltfile in ('pintail-html.xsl', 'pintail-atom.xsl'):
                xsltpath = os.path.join(self.site.tools_path, xsltfile)
                if not os.path.exists(xsltpath):
                    from pkg_resources import resource_string
                    xsltcont = resource_string(__name__, xsltfile)
                    fd = open(xsltpath, 'w')
                    fd.write(codecs.decode(xsltcont, 'utf-8'))
                    fd.close()

            mal2xhtml = os.path.join(self.site.yelp_xsl_path,
                                     'xslt', 'mallard', 'html', 'mal2xhtml.xsl')

            atomxsl = os.path.join(self.site.tools_path, 'pintail-atom-local.xsl')
            fd = open(atomxsl, 'w')
            fd.write('<xsl:stylesheet' +
                     ' xmlns:xsl="http://www.w3.org/1999/XSL/Transform"' +
                     ' version="1.0">\n')
            fd.write('<xsl:import href="' + mal2xhtml + '"/>\n')
            fd.write('<xsl:import href="pintail-atom.xsl"/>\n')
            html_extension = self.site.config.get('html_extension') or '.html'
            fd.write('<xsl:param name="html.extension" select="' +
                     "'" + html_extension + "'" + '"/>\n')
            link_extension = self.site.config.get('link_extension')
            if link_extension is not None:
                fd.write('<xsl:param name="mal.link.extension" select="' +
                         "'" + link_extension + "'" + '"/>\n')
                fd.write('<xsl:param name="pintail.extension.link" select="' +
                         "'" + link_extension + "'" + '"/>\n')
            for xsl in self.site.get_custom_xsl():
                fd.write('<xsl:include href="%s"/>\n' % xsl)
            fd.write('</xsl:stylesheet>')
            fd.close()

            root = self.site.config.get('feed_root', self.path)
            if root is None:
                root = self.site.config.get_site_root(self.path)

            subprocess.call(['xsltproc',
                             '-o', os.path.join(self.get_target_path(), atomfile),
                             '--stringparam', 'pintail.site.dir', self.path,
                             '--stringparam', 'pintail.site.root', root,
                             '--stringparam', 'feed.exclude_styles',
                             self.site.config.get('feed_exclude_styles', self.path) or '',
                             atomxsl, self.site.get_cache_path()])


class Source(Extendable):
    """
    A directory in the source.

    A source represents a source of pages or other files.
    It could be in the actual source tree, in another repository, or entirely virtual.
    Each source belongs to exactly one `Directory` object for the output directory.
    Although it's possible that some on-disk location provides pages for multiple output directories,
    in that case there would be multiple `Source` objects for that location.

    The name of a source is the config key group that defines it.
    For simple sources, this will be the same as the path of the directory it belongs to.
    For other sources, it could be an identifier that doesn't look like a path.
    """
    def __init__(self, directory, name):
        self.directory = directory
        self.name = name
        self.pages = []
        self.site = self.directory.site


    def get_source_path(self):
        """
        The absolute path to the source directory for this source.
        """
        return os.path.join(self.site.topdir, self.directory.path[1:])


    @classmethod
    def create_sources(cls, directory, name):
        """
        Return a list of source objects for a directory and source name.

        This method should be overridden by extensions.
        If this source extension recognizes something special in the directory,
        or in the config keys under the group specified by the name parameter,
        then it should return a (probably singleton) list of sources.
        """
        return []


class Site:
    """
    Base class for an entire Pintail site.
    """
    def __init__(self, config):
        self.topdir = os.path.dirname(config)
        self.srcdir = self.topdir
        self.pindir = os.path.join(self.topdir, '__pintail__')
        self.target_path = os.path.join(self.pindir, 'build')
        self.tools_path = os.path.join(self.pindir, 'tools')

        self.root = None
        self.config = Config(self, config)
        self.verbose = False

        self.yelp_xsl_branch = self.config.get('yelp_xsl_branch') or 'master'
        self.yelp_xsl_dir = 'yelp-xsl@' + self.yelp_xsl_branch.replace('/', '@')
        self.yelp_xsl_path = os.path.join(self.tools_path, self.yelp_xsl_dir)

        self.logger = logging.getLogger('pintail')
        self.logger.addHandler(logging.StreamHandler())

        self._filter = []

        for plugin in (self.config.get('plugins') or '').split():
            importlib.import_module(plugin)

        self.search_provider = None
        search = self.config.get('search_provider')
        if search is not None:
            dot = search.rindex('.')
            searchmod = importlib.import_module(search[:dot])
            searchcls = getattr(searchmod, search[dot+1:])
            self.search_provider = searchcls(self)

        self.translation_provider = None
        trans = self.config.get('translation_provider')
        if trans is not None:
            dot = trans.rindex('.')
            transmod = importlib.import_module(trans[:dot])
            transcls = getattr(transmod, trans[dot+1:])
            self.translation_provider = transcls(self)


    @classmethod
    def init_site(cls, directory):
        """
        Initialize a new site with `pintail init`.

        This is the method called by `pintail init` to create a new site.
        FIXME: Want to contribute with some low-hanging fruit?
        Make this ship sample XSLT and CSS files, and put `custom_xsl` and
        `custom_css` options in the sample `pintail.cfg`.
        """
        cfgfile = os.path.join(directory, 'pintail.cfg')
        if os.path.exists(cfgfile):
            sys.stderr.write('pintail.cfg file already exists\n')
            sys.exit(1)
        from pkg_resources import resource_string
        sample = resource_string(__name__, 'sample.cfg')
        fd = open(cfgfile, 'w')
        fd.write(codecs.decode(sample, 'utf-8'))
        fd.close()


    def set_filter(self, dirs):
        """
        Set a filter for which pages will be built.

        This can be passed to `pintail build` on the command line to build a partial site.
        If the filter ends with a slash, it is a directory. Otherwise, it is a page.
        """
        self._filter = []
        if dirs is None:
            return
        for fdir in dirs:
            if not(fdir.startswith('/')):
                fdir = '/' + fdir
            self._filter.append(fdir)


    def get_filter(self, obj):
        """
        Get whether or not an object meets the filter.

        The object `obj` could be a page or a directory.
        """
        if len(self._filter) == 0:
            return True
        if isinstance(obj, Directory):
            for f in self._filter:
                if f.endswith('/'):
                    if obj.path.startswith(f):
                        return True
                else:
                    if f.startswith(obj.path):
                        return True
        elif isinstance(obj, Page):
            for f in self._filter:
                if f.endswith('/'):
                    if obj.site_id.startswith(f):
                        return True
                else:
                    if obj.site_id == f:
                        return True
        return False


    def get_custom_xsl(self):
        """
        Get all custom XSLT files.

        This returns a list of custom XSLT files that should be included in any
        top-level XSLT files. It includes any files specified in the `custom_xsl`
        config option, as well as any files provided by any loaded `XslProvider`.
        """
        ret = []
        custom_xsl = self.config.get('custom_xsl') or ''
        for x in custom_xsl.split():
            ret.append(os.path.join(self.topdir, x))
        for cls in XslProvider.iter_subclasses('get_xsl'):
            ret.extend(cls.get_xsl(self))
        return ret


    def get_langs(self):
        """
        Get all languages used throughout the site.

        If there is a translation provider, this method calls `get_site_langs`
        on that provider. Otherwise, it returns an empty list.
        """
        if self.translation_provider is not None:
            return self.translation_provider.get_site_langs()
        return []


    def get_source_lang(self):
        """
        Get the language code for the original source language of the site.

        If there is a translation provider, this method calls `get_source_lang`
        on that provider. Otherwise, it returns `en` as a default.
        """
        if self.translation_provider is not None:
            return self.translation_provider.get_source_lang()
        return 'en'


    def get_stage_path(self, lang=None):
        """
        The absolute path to the directory for staged files for this site.
        """
        if lang is not None:
            return os.path.join(self.pindir, 'stage-' + lang)
        else:
            return os.path.join(self.pindir, 'stage')


    def get_cache_path(self, lang=None):
        """
        The absolute path to the Mallard cache file for the site in the language.
        """
        if lang is not None:
            return os.path.join(self.tools_path, 'pintail-' + lang + '.cache')
        else:
            return os.path.join(self.tools_path, 'pintail.cache')


    def get_directory_target_path(self, directory, lang=None):
        """
        The absolute path to where the built files for a directory should go.
        """
        return os.path.join(self.target_path, directory.path[1:])


    def get_page_target_path(self, page, lang=None):
        """
        The absolute path to where the built file for a page should go.
        """
        dirpath = self.get_directory_target_path(page.directory)
        if lang is None:
            return os.path.join(dirpath, page.target_file)
        else:
            return os.path.join(dirpath, page.target_file + '.' + lang)


    def get_media_target_path(self, directory, mediafile, lang=None):
        """
        The absolute path to where a media file should go in the built directory.
        """
        if lang is not None:
            langext = '.' + lang
        else:
            langext = ''
        if mediafile.startswith('/'):
            return os.path.join(self.target_path, mediafile[1:] + langext)
        else:
            return os.path.join(directory.get_target_path(), mediafile + langext)


    def translate_page(self, page, lang):
        """
        Translate a page into a language and return whether it was translated.

        If there is no translation provider, this method just returns `False`.
        Otherwise, it first checks to see if the translated file already exists,
        and if it doesn't, it calls `translate_page` on the translation provider.
        """
        if self.translation_provider is not None:
            if not self.get_filter(page):
                if os.path.exists(page.get_stage_path(lang)):
                    return True
            return page.directory.translation_provider.translate_page(page, lang)
        return False


    def scan_site(self):
        """
        Scan the entire site for directories, sources, and pages.

        This method is responsible for finding all directories, sources, and pages
        throughout the entire site. Most of the work is done by `Directory.scan_directory`.
        This method starts by creating a root directory, which is able to find subdirectories.
        It then looks at special directories defined in the config file, and creates
        directories and parents as necessary for those.

        This method is not called automatically. Ensure you call it before any build methods.
        It is safe to call this method multiple times.
        """
        if self.root is not None:
            return
        if os.path.exists(self.get_stage_path()):
            shutil.rmtree(self.get_stage_path())
        self.root = Directory(self, '/')
        directories = {'/': self.root}
        for directory in self.root.iter_directories():
            directories[directory.path] = directory

        configdirs = [d for d in self.config._config.sections()
                      if d.startswith('/') and d.endswith('/')]
        for path in configdirs:
            if path not in directories:
                parent = directories['/']
                curpath = '/'
                for curpart in path[1:-1].split('/'):
                    curpath = curpath + curpart + '/'
                    if curpath in directories:
                        parent = directories[curpath]
                    else:
                        curdir = Directory(self, curpath, parent=parent)
                        parent.subdirs.append(curdir)
                        directories[curpath] = curdir
                        parent = curdir


    def build(self):
        """
        Build the entire site, including all pages and additional files.
        """
        self.scan_site()
        self.build_cache()
        self.build_tools()
        self.build_html()
        self.build_media()
        self.build_files()
        self.build_feeds()
        self.build_search()
        if len(self._filter) == 0:
            self.build_css()
            self.build_js()


    def build_cache(self):
        """
        Build the Mallard cache files for this site.
        """
        self.scan_site()
        self.log('CACHE', self.get_cache_path())
        cache = etree.Element(CACHE_NS + 'cache', nsmap={
            None: 'http://projectmallard.org/1.0/',
            'cache': 'http://projectmallard.org/cache/1.0/',
            'site': 'http://projectmallard.org/site/1.0/',
            'pintail': 'http://pintail.io/'
        })
        for page in self.root.iter_pages():
            cdata = page.get_cache_data()
            if cdata is not None:
                cache.append(cdata)
        Site._makedirs(self.tools_path)
        cache.getroottree().write(self.get_cache_path(),
                                  pretty_print=True)
        for lang in self.get_langs():
            self.log('CACHE', self.get_cache_path(lang))
            cache = etree.Element(CACHE_NS + 'cache', nsmap={
                None: 'http://projectmallard.org/1.0/',
                'cache': 'http://projectmallard.org/cache/1.0/',
                'site': 'http://projectmallard.org/site/1.0/',
                'pintail': 'http://pintail.io/'
            })
            for page in self.root.iter_pages():
                cdata = page.get_cache_data(lang)
                if cdata is not None:
                    cache.append(cdata)
            cache.getroottree().write(self.get_cache_path(lang),
                                      pretty_print=True)


    def build_tools(self):
        """
        Build all the tools necessary to build the site.

        This method grabs and builds the latest version of yelp-xsl,
        then copies its customizations into `pintail-html.xsl`,
        and finally calls `get_tools` on each `ToolsProvider`.
        """
        Site._makedirs(self.tools_path)
        if os.path.exists(self.yelp_xsl_path):
            if self.config._update:
                self.log('UPDATE', 'https://gitlab.gnome.org/GNOME/yelp-xsl@' + self.yelp_xsl_branch)
                p = subprocess.Popen(['git', 'pull', '-q', '-r', 'origin', self.yelp_xsl_branch],
                                     cwd=os.path.join(self.tools_path,
                                                      'yelp-xsl@' + self.yelp_xsl_branch))
                p.communicate()
        else:
            self.log('CLONE', 'https://gitlab.gnome.org/GNOME/yelp-xsl@' + self.yelp_xsl_branch)
            p = subprocess.Popen(['git', 'clone', '-q',
                                  '-b', self.yelp_xsl_branch, '--single-branch',
                                  'https://gitlab.gnome.org/GNOME/yelp-xsl.git',
                                  self.yelp_xsl_dir],
                                 cwd=self.tools_path)
            p.communicate()
        self.log('BUILD', 'https://gitlab.gnome.org/GNOME/yelp-xsl@' + self.yelp_xsl_branch)
        if os.path.exists(os.path.join(self.yelp_xsl_path, 'localbuild.sh')):
            p = subprocess.Popen([os.path.join(self.yelp_xsl_path, 'localbuild.sh')],
                                 cwd=self.yelp_xsl_path,
                                 stdout=subprocess.DEVNULL,
                                 stderr=subprocess.DEVNULL)
            p.communicate()
        else:
            p = subprocess.Popen([os.path.join(self.yelp_xsl_path, 'autogen.sh')],
                                 cwd=self.yelp_xsl_path,
                                 stdout=subprocess.DEVNULL,
                                 stderr=subprocess.DEVNULL)
            p.communicate()
            p = subprocess.Popen(['make'], cwd=self.yelp_xsl_path, stdout=subprocess.DEVNULL)
            p.communicate()

        from pkg_resources import resource_string
        site2html = resource_string(__name__, 'pintail-html.xsl')
        fd = open(os.path.join(self.tools_path, 'pintail-html.xsl'),
                  'w', encoding='utf-8')
        fd.write(codecs.decode(site2html, 'utf-8'))
        fd.close()

        for cls in ToolsProvider.iter_subclasses('build_tools'):
            cls.build_tools(self)


    def build_html(self):
        """
        Build all HTML files for this site.
        """
        self.scan_site()
        self.root.build_html()


    def build_media(self):
        """
        Copy media files for the entire site.
        """
        self.scan_site()
        self.root.build_media()


    def build_css(self):
        """
        Build all of the CSS for the site.

        This function iterates over all `CssProvider` subclasses and asks them to build CSS.
        """
        self.scan_site()
        for cls in CssProvider.iter_subclasses('build_css'):
            cls.build_css(self)


    def build_js(self):
        """
        Build all JavaScript files for the site.
        """
        self.scan_site()
        jspath = os.path.join(self.yelp_xsl_path, 'js')

        if os.path.exists(os.path.join(jspath, 'jquery.js')):
            self.log('JS', '/jquery.js')
            shutil.copyfile(os.path.join(jspath, 'jquery.js'),
                            os.path.join(self.target_path, 'jquery.js'))

        xslpath = os.path.join(self.yelp_xsl_path, 'xslt')
        Site._makedirs(self.tools_path)

        jsxsl = os.path.join(self.tools_path, 'pintail-js.xsl')
        fd = open(jsxsl, 'w')
        fd.writelines([
            '<xsl:stylesheet',
            ' xmlns:xsl="http://www.w3.org/1999/XSL/Transform"',
            ' xmlns:exsl="http://exslt.org/common"',
            ' xmlns:cache="http://projectmallard.org/cache/1.0/"',
            ' xmlns:mal="http://projectmallard.org/1.0/"',
            ' extension-element-prefixes="exsl"',
            ' version="1.0">\n'
            '<xsl:import href="', xslpath, '/mallard/html/mal2xhtml.xsl"/>\n'
            ])
        fd.write('<xsl:import href="%s"/>\n' % 'pintail-html.xsl')
        for xsl in self.get_custom_xsl():
            fd.write('<xsl:include href="%s"/>\n' % xsl)
        fd.writelines([
            '<xsl:output method="text"/>\n',
            '<xsl:template match="/">\n',
            ' <xsl:call-template name="html.js.content"/>\n',
            '</xsl:template>\n',
            '</xsl:stylesheet>\n'
            ])
        fd.close()

        self.log('JS', '/yelp.js')
        subprocess.call(['xsltproc',
                         '-o', os.path.join(self.target_path, 'yelp.js'),
                         jsxsl, self.get_cache_path()])

        if os.path.exists(os.path.join(jspath, 'highlight.pack.js')):
            self.log('JS', '/highlight.pack.js')
            shutil.copyfile(os.path.join(jspath, 'highlight.pack.js'),
                            os.path.join(self.target_path, 'highlight.pack.js'))

        if os.path.exists(os.path.join(jspath, 'jquery.syntax.js')):
            for js in ['jquery.syntax.js', 'jquery.syntax.core.js',
                       'jquery.syntax.layout.yelp.js']:
                self.log('JS', '/' + js)
                shutil.copyfile(os.path.join(jspath, js),
                                os.path.join(self.target_path, js))

            jsxsl = os.path.join(self.tools_path, 'pintail-js-brushes.xsl')
            fd = open(jsxsl, 'w')
            fd.writelines([
                '<xsl:stylesheet',
                ' xmlns:xsl="http://www.w3.org/1999/XSL/Transform"',
                ' xmlns:mal="http://projectmallard.org/1.0/"',
                ' xmlns:cache="http://projectmallard.org/cache/1.0/"',
                ' xmlns:exsl="http://exslt.org/common"',
                ' xmlns:html="http://www.w3.org/1999/xhtml"',
                ' extension-element-prefixes="exsl"',
                ' version="1.0">\n',
                '<xsl:import href="', xslpath, '/mallard/html/mal2xhtml.xsl"/>\n'
            ])
            for xsl in self.get_custom_xsl():
                fd.write('<xsl:include href="%s"/>\n' % xsl)
            fd.writelines([
                '<xsl:output method="text"/>\n',
                '<xsl:template match="/">\n',
                '<xsl:for-each select="/cache:cache/mal:page">\n',
                '<xsl:for-each select="document(@cache:href)//mal:code[@mime]">\n',
                '  <xsl:variable name="out">\n',
                '   <xsl:call-template name="mal2html.pre"/>\n',
                '  </xsl:variable>\n',
                '  <xsl:variable name="class">\n',
                '   <xsl:value-of select="exsl:node-set($out)/*/html:pre[last()]/@class"/>\n',
                '  </xsl:variable>\n',
                '  <xsl:if test="starts-with($class, ',
                "'contents syntax brush-'", ')">\n',
                '   <xsl:text>jquery.syntax.brush.</xsl:text>\n',
                '   <xsl:value-of select="substring-after($class, ',
                "'contents syntax brush-'", ')"/>\n',
                '   <xsl:text>.js&#x000A;</xsl:text>\n',
                '  </xsl:if>\n',
                '</xsl:for-each>\n',
                '</xsl:for-each>\n',
                '</xsl:template>\n',
                '</xsl:stylesheet>'
            ])
            fd.close()

            brushes = subprocess.check_output(['xsltproc',
                                               jsxsl, self.get_cache_path()],
                                              universal_newlines=True)
            for brush in brushes.split():
                self.log('JS', '/' + brush)
                shutil.copyfile(os.path.join(jspath, brush),
                                os.path.join(self.target_path, brush))


    def build_files(self):
        """
        Copy all extra files for this site.
        """
        self.scan_site()
        self.root.build_files()


    def build_feeds(self):
        """
        Build all Atom feeds for this site.
        """
        self.scan_site()
        self.root.build_feeds()


    def build_search(self):
        """
        Build all search data for the site.

        If there is a search provider, this method calls `index_site` on it.
        Otherwise, this method does nothing.
        """
        if self.config._index:
            self.scan_site()
            if self.search_provider is not None:
                self.search_provider.index_site()


    def get_ignore_directory(self, path):
        """
        Get whether or not to ignore a directory path when scanning a site.

        The `path` argument is a path as used by `Directory`.
        If it should be ignored, this method returns `True`.
        Currently, we ignore Pintail's built directory and git's hidden directory.
        We should be smarter in the future, and perhaps allow a config option.
        """
        if path == '/__pintail__/':
            return True
        # FIXME: use an ignore key in config
        if path == '/.git/':
            return True
        return False


    def log(self, tag, data):
        """
        Write something to the log.

        Pintail uses a tag to indicate what kind of thing is happening,
        followed by a data string to show what that thing is happening to.
        """
        if data.startswith(self.pindir + '/'):
            data = data[len(os.path.dirname(self.pindir))+1:]
        self.logger.info('%(tag)-6s %(data)s' % {'tag': tag, 'data': data})


    @classmethod
    def _makedirs(cls, path):
        # Python's os.makedirs complains if directory modes don't
        # match just so. I don't care if they match, as long as I
        # can write.
        if os.path.exists(path):
            return
        Site._makedirs(os.path.dirname(path))
        if not os.path.exists(path):
            os.mkdir(path)


class Config:
    """
    The configuration for a site.

    This class wraps Python's `ConfigParser` with various utility methods
    to ensure consistent access across Pintail.
    """

    def __init__(self, site, filename):
        self._site = site
        self._config = configparser.ConfigParser()
        self._config.read(filename)
        self._local = False
        self._update = True
        self._index = True


    def get(self, key, path=None):
        """
        Get the value for a key, possibly in a path.

        If `path` is omitted, it's assumed to be `pintail`, which is the group
        in the config file where site-level options are defined. If the path is
        `pintail` and `--local` has been passed to the `pintail` command, this
        method will also look in the `local` config group for overrides.
        """
        if path is None:
            path = 'pintail'
        if self._local and path == 'pintail':
            ret = self._config.get('local', key, fallback=None)
            if ret is not None:
                return ret
        return self._config.get(path, key, fallback=None)


    def get_site_root(self, path=None):
        """
        Get the root path for the site.

        For normal builds, this is either `"/"` or the value of the `site_root` config option.
        For local builds, this method creates a relative path from the `path` argument.
        """
        if self._local and path is not None:
            if path == '/':
                return './'
            ret = ''
            for i in range(path.count('/') - 1):
                ret = '../' + ret
            return ret
        else:
            return self.get('site_root') or '/'


    def set_local(self):
        """
        Set whether we are doing a local build.

        Local builds modify paths and certain other things to create files
        suitable for previewing locally.
        """
        self._config.set('pintail', 'site_root',
                         self._site.target_path + '/')
        self._local = True


    def set_update(self, update):
        """
        Set whether or not git repositories should be updated.

        Pintail will always clone repositories it does not have yet.
        Normally, it will update repositories it has already cloned.
        With updates turned off, it will not update cloned repositories.
        """
        self._update = update


    def set_index(self, index):
        """
        Set whether or not to index pages with the search provider.
        """
        self._index = index
