#!/usr/bin/env python

from datetime import date
from distutils.core import setup
import os
import platform
import subprocess
import sys

sys.path.insert(0, os.path.abspath('code'))
import photini.version

command_options = {}

# regenerate version file, if required
try:
    p = subprocess.Popen(
        ['git', 'rev-parse', '--short', 'HEAD'], stdout=subprocess.PIPE)
    commit = p.communicate()[0].strip().decode('ASCII')
    if p.returncode:
        commit = photini.version.commit
except OSError:
    commit = photini.version.commit
if commit != photini.version.commit:
    photini.version.version = date.today().strftime('%y.%m')
    photini.version.release = str(int(photini.version.release) + 1)
    photini.version.commit = commit
    vf = open('code/photini/version.py', 'w')
    vf.write("version = '%s'\n" % photini.version.version)
    vf.write("release = '%s'\n" % photini.version.release)
    vf.write("commit = '%s'\n" % photini.version.commit)
    vf.close()

# set options for building distributions
command_options['sdist'] = {
    'formats'        : ('setup.py', 'gztar zip'),
    'force_manifest' : ('setup.py', '1'),
    }

if platform.system() == 'Windows':
    scripts = ['scripts/photini.bat']
else:
    scripts = ['scripts/photini']

version = '%s_r%s' % (photini.version.version, photini.version.release)

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
      packages = ['photini'],
      package_dir = {'': 'code'},
      package_data = {
          'photini' : [
              'code/data/googlemap.js', 'code/data/about.html',
              'code/data/LICENSE.txt'
              ],
          },
      scripts = scripts,
      command_options = command_options,
      )
