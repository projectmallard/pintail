# pintail - Build static sites from collections of Mallard documents
# Copyright (c) 2016-2020 Shaun McCance <shaunm@gnome.org>
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

import pintail.site

class TranslationProvider(pintail.site.Extendable):
    """
    An extension point to provide translations for the site.
    """
    def __init__(self, site):
        self.site = site
        self._langs = None


    def get_source_lang(self):
        """
        Get the language code for the original source language of the site.

        By default, this uses the `source_lang` config option, or `en` if that isn't present.
        Different translation providers could have a different behavior.
        """
        return self.site.config.get('source_lang') or 'en'


    def get_site_langs(self):
        """
        Get all languages used throughout the site.

        This returns all languages used in any directory in the site.
        Translation providers probably do not need to override this method.
        """
        if self._langs is not None:
            return self._langs
        self._langs = []
        for directory in self.site.root.iter_directories():
            for lang in self.get_directory_langs(directory):
                if lang not in self._langs:
                    self._langs.append(lang)
        return self._langs


    def get_directory_langs(self, directory):
        """
        Get all languages available for a single directory.

        Translation providers should override this method.
        """
        return []


    def translate_page(self, page, lang):
        """
        Translate a page into a language and return whether it was translated.

        Translation providers should override this method.
        """
        return False


    def translate_media(self, source, mediafile, lang):
        """
        Translate a media file into a language and return whether it was translated.

        Translation providers should override this method.
        """
        return False
