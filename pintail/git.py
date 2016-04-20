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

import pintail

class GitDirectory(pintail.Directory):
    def __init__(self, site, path, *, parent=None):
        self.site = site
        self.path = path
        self.parent = parent
        self.repo = self.site.config.get('git_repository', self.path)
        self.branch = self.site.config.get('git_branch', self.path) or 'master'
        self.repodir = (self.repo.replace('/', '!') + '@@' +
                        self.branch.replace('/', '!'))
        self.absrepodir = os.path.join(self.site.pindir, 'git', self.repodir)
        if os.path.exists(self.absrepodir):
            if self.site.config._update and self.site.config.get('git_update', self.path) != 'false':
                self.site.log('UPDATE', self.repo + '@' + self.branch)
                p = subprocess.Popen(['git', 'pull', '-q', '-r',
                                      'origin', self.branch],
                                     cwd=self.absrepodir)
                p.communicate()
        else:
            self.site.log('CLONE', self.repo + '@' + self.branch)
            pintail.Site._makedirs(os.path.join(self.site.pindir, 'git'))
            p = subprocess.Popen(['git', 'clone', '-q',
                                  '-b', self.branch, '--single-branch',
                                  self.repo, self.repodir],
                                 cwd=os.path.join(self.site.pindir, 'git'))
            p.communicate()

        pintail.Directory.__init__(self, site, path)

    @classmethod
    def is_special_path(cls, site, path):
        repo = site.config.get('git_repository', path)
        if repo is not None:
            return True

    @property
    def source_path(self):
        return os.path.join(self.absrepodir,
                            self.site.config.get('git_directory', self.path) or '')

