#!/usr/bin/env python

from distutils.core import setup
import os
import platform
import sys

sys.path.insert(0, os.path.abspath('code'))
from photini import version

if platform.system() == 'Windows':
    script = 'code/scripts/photini.bat'
else:
    script = 'code/scripts/photini'

setup(name = 'Photini',
      version = '%s_%s' % (version.version, version.release),
      author = 'Jim Easterbrook',
      author_email = 'jim@jim-easterbrook.me.uk',
      url = 'https://github.com/jim-easterbrook/Photini',
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
      packages = ['photini'],
      package_dir = {'': 'code'},
      package_data = {
          'photini' : [
              'code/data/googlemap.js', 'code/data/about.html',
              'code/data/LICENSE.txt'
              ],
          },
      scripts = [script],
      )
