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
try:
    from setuptools import setup
    using_setuptools = True
except ImportError:
    from distutils.core import setup
    using_setuptools = False
import os
import platform
import subprocess
import sys

import photini.version

cmdclass = {}
command_options = {}

# if using Python 3, translate during build
try:
    from distutils.command.build_py import build_py_2to3 as build_py
    cmdclass['build_py'] = build_py
except ImportError:
    pass

# regenerate version file, if required
regenerate = False
try:
    p = subprocess.Popen(['git', 'rev-parse', '--short', 'HEAD'],
                         stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    commit = p.communicate()[0].strip().decode('ASCII')
    regenerate = (not p.returncode) and commit != photini.version.commit
except OSError:
    pass
if regenerate:
    release = str(int(photini.version.release) + 1)
    version = date.today().strftime('%y.%m') + '.dev%s' % release
    vf = open('photini/version.py', 'w')
    vf.write("version = '%s'\n" % version)
    vf.write("release = '%s'\n" % release)
    vf.write("commit = '%s'\n" % commit)
    vf.close()
else:
    version = photini.version.version

# if sphinx is installed, add command to build documentation
try:
    from sphinx.setup_command import BuildDoc
    cmdclass['build_sphinx'] = BuildDoc
    command_options['build_sphinx'] = {
        'all_files'  : ('setup.py', '1'),
        'source_dir' : ('setup.py', 'doc_src'),
        'build_dir'  : ('setup.py', 'doc'),
        'builder'    : ('setup.py', 'html'),
        }
except ImportError:
    pass

# set options for uploading documentation to PyPI
if using_setuptools:
    command_options['upload_docs'] = {
        'upload_dir' : ('setup.py', 'doc/html'),
        }

# add package requirements (setuptools only)
setuptools_options = {}
if using_setuptools:
    setuptools_options['install_requires'] = ['appdirs >= 1.3']
    setuptools_options['extras_require'] = {
        'flickr': ['flickrapi >= 1.4'],
        'picasa': ['gdata >= 2.0.16']
        }

# set options for building distributions
command_options['sdist'] = {
    'formats'        : ('setup.py', 'gztar zip'),
    'force_manifest' : ('setup.py', '1'),
    }

if platform.system() == 'Windows':
    scripts = ['scripts/photini.bat']
else:
    scripts = ['scripts/photini']
scripts.append('scripts/photini-importer.py')

setup(name = 'Photini',
      version = version,
      author = 'Jim Easterbrook',
      author_email = 'jim@jim-easterbrook.me.uk',
      url = 'https://github.com/jim-easterbrook/Photini/',
      download_url = 'https://pypi.python.org/pypi/Photini/%s' % version,
      description = 'Simple photo metadata editor',
      long_description = """
Photini is a GUI program to create and edit metadata for digital
photographs. It can set textual information such as title, description
and copyright as well as geolocation information by browsing a map or
setting coordinates directly. It reads metadata in EXIF, IPTC or XMP
format and writes it to all three, to maximise compatibility with
other software.
""",
      classifiers = [
          'Development Status :: 4 - Beta',
          'Intended Audience :: End Users/Desktop',
          'License :: OSI Approved :: GNU General Public License v3 (GPLv3)',
          'Operating System :: OS Independent',
          'Programming Language :: Python :: 2 :: Only',
          ],
      license = 'GNU GPL',
      platforms = ['POSIX', 'MacOS', 'Windows'],
      packages = ['photini'],
      package_data = {
          'photini' : [
              'data/*.html', 'data/*.txt', 'data/*.js',   'data/*.png'],
          },
      scripts = scripts,
      cmdclass = cmdclass,
      command_options = command_options,
      **setuptools_options
      )
