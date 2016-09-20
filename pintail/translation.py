# pintail - Build static sites from collections of Mallard documents
# Copyright (c) 2016 Shaun McCance <shaunm@gnome.org>
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
    def __init__(self, site):
        self.site = site
        self._langs = None

    def get_site_langs(self):
        if self._langs is not None:
            return self._langs
        self._langs = []
        for directory in self.site.root.iter_directories():
            for lang in self.get_directory_langs(directory):
                if lang not in self._langs:
                    self._langs.append(lang)
        return self._langs

    def get_directory_langs(self, directory):
        return []

    def translate_page(self, page, lang):
        return False

    def translate_media(self, directory, mediafile, lang):
        return False
