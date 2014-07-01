#!/usr/bin/env python
#  Photini - a simple photo metadata editor.
#  http://github.com/jim-easterbrook/Photini
#  Copyright (C) 2012-14  Jim Easterbrook  jim@jim-easterbrook.me.uk
#
#  This program is free software: you can redistribute it and/or
#  modify it under the terms of the GNU General Public License as
#  published by the Free Software Foundation, either version 3 of the
#  License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
#  General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program.  If not, see
#  <http://www.gnu.org/licenses/>.

from datetime import date
from distutils.command.upload import upload
import os
from setuptools import setup

# read current version info without importing package
with open('src/photini/__init__.py') as f:
    exec(f.read())

cmdclass = {}
command_options = {}

# get GitHub repo information
# requires GitPython - 'sudo pip install gitpython --pre'
last_commit = _commit
last_release = None
try:
    import git
    try:
        repo = git.Repo()
        latest = 0
        for tag in repo.tags:
            if tag.commit.committed_date > latest:
                latest = tag.commit.committed_date
                last_release = str(tag)
        last_commit = str(repo.head.commit)[:7]
    except git.exc.InvalidGitRepositoryError:
        pass
except ImportError:
    pass

# regenerate version file, if required
if last_commit != _commit:
    _dev_no = str(int(_dev_no) + 1)
    _commit = last_commit
if last_release:
    major, minor, patch = last_release.split('.')
    today = date.today()
    if today.strftime('%m') == minor:
        patch = int(patch) + 1
    else:
        patch = 0
    next_release = today.strftime('%y.%m') + '.%d' % patch
    next_version = next_release + '.dev%s' % _dev_no
else:
    next_release = '.'.join(__version__.split('.')[:3])
    next_version = next_release
if next_version != __version__:
    with open('src/photini/__init__.py', 'w') as vf:
        vf.write("from __future__ import unicode_literals\n\n")
        vf.write("__version__ = '%s'\n" % next_version)
        vf.write("_dev_no = '%s'\n" % _dev_no)
        vf.write("_commit = '%s'\n" % _commit)

# if sphinx is installed, add command to build documentation
try:
    from sphinx.setup_command import BuildDoc
    cmdclass['build_sphinx'] = BuildDoc
    command_options['build_sphinx'] = {
        'all_files'  : ('setup.py', '1'),
        'source_dir' : ('setup.py', 'src/doc'),
        'build_dir'  : ('setup.py', 'doc'),
        'builder'    : ('setup.py', 'html'),
        }
except ImportError:
    pass

# set options for uploading documentation to PyPI
command_options['upload_docs'] = {
    'upload_dir' : ('setup.py', 'doc/html'),
    }

# modify upload class to add appropriate tag
# requires GitPython - 'sudo pip install gitpython --pre'
class upload_and_tag(upload):
    def run(self):
        import git
        message = ''
        with open('CHANGELOG.txt') as cl:
            while not cl.readline().startswith('Changes'):
                pass
            while True:
                line = cl.readline().strip()
                if not line:
                    break
                message += line + '\n'
        repo = git.Repo()
        tag = repo.create_tag('Photini-%s' % next_release, message=message)
        remote = repo.remotes.origin
        remote.push(tags=True)
        return upload.run(self)
cmdclass['upload'] = upload_and_tag

# set options for building distributions
command_options['sdist'] = {
    'formats'        : ('setup.py', 'gztar zip'),
    'force_manifest' : ('setup.py', '1'),
    }

with open('README.rst') as ldf:
    long_description = ldf.read()
url = 'https://github.com/jim-easterbrook/Photini'

setup(name = 'Photini',
      version = next_release,
      author = 'Jim Easterbrook',
      author_email = 'jim@jim-easterbrook.me.uk',
      url = url,
      download_url = url + '/archive/Photini-' + next_release + '.tar.gz',
      description = 'Simple photo metadata editor',
      long_description = long_description,
      classifiers = [
          'Development Status :: 4 - Beta',
          'Intended Audience :: End Users/Desktop',
          'License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)',
          'Operating System :: OS Independent',
          'Programming Language :: Python :: 2',
          'Programming Language :: Python :: 2.6',
          'Programming Language :: Python :: 2.7',
          'Programming Language :: Python :: 3',
          'Topic :: Multimedia :: Graphics',
          ],
      license = 'GNU GPL',
      platforms = ['POSIX', 'MacOS', 'Windows'],
      packages = ['photini'],
      package_dir = {'' : 'src'},
      package_data = {
          'photini' : [
              'data/*.html', 'data/*.txt', 'data/*.js',   'data/*.png'],
          },
      cmdclass = cmdclass,
      command_options = command_options,
      entry_points = {
          'gui_scripts' : [
              'photini = photini.editor:main',
              ],
          },
      install_requires = ['appdirs >= 1.3'],
      extras_require = {
          'flickr'  : ['flickrapi >= 1.4'],
          'importer': ['gphoto2'],
          'picasa'  : ['gdata >= 2.0.16']
          },
      use_2to3 = True,
      )
