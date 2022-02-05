#  Photini - a simple photo metadata editor.
#  http://github.com/jim-easterbrook/Photini
#  Copyright (C) 2012-22  Jim Easterbrook  jim@jim-easterbrook.me.uk
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

import os
from setuptools import setup


# list dependency packages
install_requires = ['appdirs', 'requests']
extras_require = {
    'flickr'   : ['requests-oauthlib', 'requests-toolbelt', 'keyring'],
    'google'   : ['requests-oauthlib', 'keyring'],
    'importer' : ['gphoto2'],
    'ipernity' : ['requests-toolbelt', 'keyring'],
    'spelling' : ['pyenchant'],
    'win7'     : ['PySide2', 'python-exiv2', 'pyenchant', 'gpxpy',
                  'requests-oauthlib', 'requests-toolbelt', 'keyring'],
    'win10'    : ['PySide6', 'python-exiv2', 'pyenchant', 'gpxpy',
                  'requests-oauthlib', 'requests-toolbelt', 'keyring'],
    }

# add version numbers
min_version = {
    'appdirs': '1.3', 'gphoto2': '0.10', 'gpxpy': '1.3.5', 'keyring': '7.0',
    'pyenchant': '2.0',
    'PyQt5': '5.0.0', 'PySide2': '5.11.0', 'PySide6': '6.2.0',
    'python-exiv2': '0.8.1',
    'requests': '2.4.0', 'requests-oauthlib': '1.0', 'requests-toolbelt': '0.9',
    }
for option in extras_require:
    extras_require[option] = ['{} >= {}'.format(x, min_version[x])
                              for x in extras_require[option]]
install_requires = ['{} >= {}'.format(x, min_version[x])
                    for x in install_requires]

# read current version info without importing package
with open('src/photini/__init__.py') as f:
    exec(f.read())

with open('README.rst') as ldf:
    long_description = ldf.read()
url = 'https://github.com/jim-easterbrook/Photini'

package_data = []
for root, dirs, files in os.walk('src/photini/data/'):
    package_data += [
        os.path.join(root.replace('src/photini/', ''), x) for x in files]

setup(name = 'Photini',
      version = __version__,
      author = 'Jim Easterbrook',
      author_email = 'jim@jim-easterbrook.me.uk',
      url = url,
      download_url = url + '/archive/' + __version__ + '.tar.gz',
      description = 'Simple photo metadata editor',
      long_description = long_description,
      classifiers = [
          'Development Status :: 5 - Production/Stable',
          'Environment :: Win32 (MS Windows)',
          'Environment :: X11 Applications :: Qt',
          'Intended Audience :: End Users/Desktop',
          'License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)',
          'Operating System :: OS Independent',
          'Programming Language :: Python :: 3',
          'Topic :: Multimedia :: Graphics',
          ],
      packages = ['photini'],
      package_dir = {'' : 'src'},
      package_data = {'photini' : package_data},
      entry_points = {
          'console_scripts' : [
              'photini-post-install = photini.scripts:post_install',
              ],
          'gui_scripts' : [
              'photini = photini.editor:main',
              ],
          },
      install_requires = install_requires,
      extras_require = extras_require,
      zip_safe = False,
      )
