# pintail - Build static sites from collections of Mallard documents
# Copyright (c) 2015 Shaun McCance <shaunm@gnome.org>
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

import os
import subprocess

import pintail.site

class GitDirectory(pintail.site.Directory, pintail.site.XslProvider):
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
                                  '-b', self.branch, '--depth=1',
                                  self.repo, self.repodir],
                                 cwd=os.path.join(site.pindir, 'git'))
            p.communicate()

        super().__init__(site, path, parent=parent)

    def get_source_path(self):
        return os.path.join(self.absrepodir,
                            self.site.config.get('git_directory', self.path) or '')

    @classmethod
    def is_special_path(cls, site, path):
        repo = site.config.get('git_repository', path)
        if repo is not None:
            return True

    @classmethod
    def get_xsl_params(cls, output, obj, lang=None):
        if not (output == 'html' and isinstance(obj, pintail.site.Page)):
            return []
        if isinstance(obj.directory, cls):
            d = obj.directory
            return [('pintail.git.repository', d.repo),
                    ('pintail.git.branch', d.branch),
                    ('pintail.git.directory',
                     d.site.config.get('git_directory', d.path) or '')]
        return []
