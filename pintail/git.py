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

import pintail.site

class GitDirectory(pintail.site.Directory):
    def __init__(self, site, path, *, parent=None):
        self.repo = site.config.get('git_repository', path)
        self.branch = site.config.get('git_branch', path) or 'master'
        self.repodir = (self.repo.replace('/', '!') + '@@' +
                        self.branch.replace('/', '!'))
        self.absrepodir = os.path.join(site.pindir, 'git', self.repodir)

        if os.path.exists(self.absrepodir):
            if site.config._update and site.config.get('git_update', path) != 'false':
                site.log('UPDATE', self.repo + '@' + self.branch)
                p = subprocess.Popen(['git', 'pull', '-q', '-r',
                                      'origin', self.branch],
                                     cwd=self.absrepodir)
                p.communicate()
        else:
            site.log('CLONE', self.repo + '@' + self.branch)
            pintail.site.Site._makedirs(os.path.join(site.pindir, 'git'))
            p = subprocess.Popen(['git', 'clone', '-q',
                                  '-b', self.branch, '--single-branch',
                                  self.repo, self.repodir],
                                 cwd=os.path.join(site.pindir, 'git'))
            p.communicate()

        super().__init__(site, path, parent=parent)

    @property
    def source_path(self):
        return os.path.join(self.absrepodir,
                            self.site.config.get('git_directory', self.path) or '')

    @classmethod
    def is_special_path(cls, site, path):
        repo = site.config.get('git_repository', path)
        if repo is not None:
            return True

    def get_special_path_info(self):
        return {
            'source_repository': self.repo,
            'source_branch': self.branch,
            'source_directory': self.site.config.get('git_directory', self.path) or ''
        }
