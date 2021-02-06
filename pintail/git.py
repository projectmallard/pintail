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

import os
import subprocess

import pintail.site


class GitSource(pintail.site.Source, pintail.site.XslProvider):
    """
    A source directory from a remote git repository.

    If a directory or other source in the config file uses the `git_repository` option,
    this source will be used to fetch pages from another git repository.
    This source recognizes the following config options:

    * `git_repository` - The git repository URL, suitable to pass to `git clone`.
    * `git_branch` - The remote git branch to check out.
    * `git_directory` - The directory in the git repository where pages can be found.
    * `git_update` - Whether to update the git clone on each run, `true` or `false`.
    """

    def __init__(self, directory, name):
        self.repo = directory.site.config.get('git_repository', name)
        self.branch = directory.site.config.get('git_branch', name) or 'master'
        self.repodir = (self.repo.replace('/', '!') + '@@' +
                        self.branch.replace('/', '!'))
        self.absrepodir = os.path.join(directory.site.pindir, 'git', self.repodir)

        super().__init__(directory, name)

        if os.path.exists(self.absrepodir):
            if self.site._update and self.site.config.get('git_update', name) != 'false':
                self.site.log('UPDATE', self.repo + '@' + self.branch)
                p = subprocess.Popen(['git', 'pull', '-q', '-r',
                                      'origin', self.branch],
                                     cwd=self.absrepodir,
                                     env={'GIT_TERMINAL_PROMPT': '0'})
                try:
                    p.communicate()
                except:
                    self.site.warn('Failed to update git repository')
        else:
            self.site.log('CLONE', self.repo + '@' + self.branch)
            pintail.site.Site._makedirs(os.path.join(self.site.pindir, 'git'))
            p = subprocess.Popen(['git', 'clone', '-q', '--depth', '1',
                                  '-b', self.branch, '--single-branch',
                                  self.repo, self.repodir],
                                 cwd=os.path.join(self.site.pindir, 'git'),
                                 env={'GIT_TERMINAL_PROMPT': '0'})
            try:
                p.communicate()
            except:
                self.site.fail('Failed to clone git repository')


    def get_source_path(self):
        """
        The absolute path to the source directory for this source.
        """
        return os.path.join(self.absrepodir,
                            self.site.config.get('git_directory', self.name) or '')


    @classmethod
    def create_sources(cls, directory, name):
        """
        Return a list of source objects for a remote git source.

        If a directory or other source in the config file uses `git_repository`,
        this function will return a list with a single git source.
        """
        repo = directory.site.config.get('git_repository', name)
        if repo is not None:
            return [cls(directory, name)]
        return []


    @classmethod
    def get_xsl_params(cls, output, obj, lang=None):
        """
        Get a list of XSLT params about the git location.
        """
        if not (output == 'html' and isinstance(obj, pintail.site.Page)):
            return []
        if isinstance(obj.directory, cls):
            d = obj.directory
            return [('pintail.git.repository', d.repo),
                    ('pintail.git.branch', d.branch),
                    ('pintail.git.directory',
                     d.site.config.get('git_directory', d.path) or '')]
        return []
