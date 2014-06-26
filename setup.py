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
import os
from setuptools import setup
import subprocess

# read current version info without importing package
with open('src/photini/version.py') as f:
    exec(f.read())

cmdclass = {}
command_options = {}

# regenerate version file, if required
regenerate = False
try:
    p = subprocess.Popen(['git', 'rev-parse', '--short', 'HEAD'],
                         stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    new_commit = p.communicate()[0].strip().decode('ASCII')
    regenerate = (not p.returncode) and new_commit != commit
except OSError:
    pass
if regenerate:
    commit = new_commit
    release = str(int(release) + 1)
    version = date.today().strftime('%y.%m') + '.dev%s' % release
    with open('src/photini/version.py', 'w') as vf:
        vf.write("from __future__ import unicode_literals\n\n")
        vf.write("version = '%s'\n" % version)
        vf.write("release = '%s'\n" % release)
        vf.write("commit = '%s'\n" % commit)

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

# set options for building distributions
command_options['sdist'] = {
    'formats'        : ('setup.py', 'gztar zip'),
    'force_manifest' : ('setup.py', '1'),
    }

with open('README.rst') as ldf:
    long_description = ldf.read()
url = 'https://github.com/jim-easterbrook/Photini'

setup(name = 'Photini',
      version = version,
      author = 'Jim Easterbrook',
      author_email = 'jim@jim-easterbrook.me.uk',
      url = url,
      download_url = url + '/archive/Photini-' + version + '.tar.gz',
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
