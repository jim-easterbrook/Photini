#  Photini - a simple photo metadata editor.
#  http://github.com/jim-easterbrook/Photini
#  Copyright (C) 2012-23  Jim Easterbrook  jim@jim-easterbrook.me.uk
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
install_requires = ['appdirs', 'cachetools', 'chardet', 'exiv2', 'requests']
extras_require = {
    'basic'    : ['PySide2'],
    'flickr'   : ['requests-oauthlib', 'requests-toolbelt', 'keyring'],
    'google'   : ['requests-oauthlib', 'keyring'],
    'importer' : ['gphoto2; platform_system != "Windows"'],
    'ipernity' : ['requests-toolbelt', 'keyring'],
    'spelling' : ['pyenchant'],
    # the following are intended for use by the photini-configure script
    'PySide2'  : ['PySide2'],
    'PySide6'  : ['PySide6'],
    'gpxpy'    : ['gpxpy'],
    'Pillow'   : ['Pillow'],
    }
extras_require['extras'] = list(
    set(extras_require['flickr']) | set(extras_require['google']) |
    set(extras_require['importer']) | set(extras_require['ipernity']) |
    set(extras_require['spelling']) | set(['gpxpy', 'Pillow']))
extras_require['win7'] = list(
    set(extras_require['basic']) | set(extras_require['extras']))
extras_require['win10'] = extras_require['win7']

# add version numbers
min_version = {
    'appdirs': '1.3', 'cachetools': '3.0', 'chardet': '3.0', 'exiv2': '0.13.2',
    'gphoto2': '1.8.0', 'gpxpy': '1.3.5', 'keyring': '7.0', 'Pillow': '2.0.0',
    'pyenchant': '2.0', 'PyQt5': '5.9', 'PySide2': '5.11.0', 'PySide6': '6.2.0',
    'requests': '2.4.0', 'requests-oauthlib': '1.0', 'requests-toolbelt': '0.9',
    }

def add_version(package):
    package, sep, marker = package.partition(';')
    return '{} >= {}'.format(package, min_version[package]) + sep + marker

for option in extras_require:
    extras_require[option] = [add_version(x) for x in extras_require[option]]
install_requires = [add_version(x) for x in install_requires]

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
      license = 'GPLv3+',
      packages = ['photini'],
      package_dir = {'' : 'src'},
      package_data = {'photini' : package_data},
      entry_points = {
          'console_scripts' : [
              'photini-configure = photini.scripts:configure',
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
