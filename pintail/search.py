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
# Free Software Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA
# 02111-1307, USA.

import pintail

class SearchProvider(pintail.Extendable):
    def __init__(self, site):
        self.site = site

    def index_site(self):
        for subdir in self.site.root.iter_directories():
            self.index_directory(subdir)

    def index_directory(self, directory):
        if not self.site.get_dir_filter(directory):
            return
        for page in directory.pages:
            self.index_page(page)

    def index_page(self, page):
        pass
