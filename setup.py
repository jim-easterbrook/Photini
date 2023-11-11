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

from setuptools import setup
from setuptools import __version__ as setuptools_version

if tuple(map(int, setuptools_version.split('.')[:2])) >= (61, 0):
    # use metadata from pyproject.toml directly
    setup()
else:
    import os

    # get metadata from pyproject.toml
    import toml
    metadata = toml.load('pyproject.toml')

    with open(metadata['project']['readme']) as ldf:
        long_description = ldf.read()

    package_data = []
    for root, dirs, files in os.walk('src/photini/data/'):
        package_data += [
            os.path.join(root.replace('src/photini/', ''), x) for x in files]

    setup(name = metadata['project']['name'],
          author = metadata['project']['authors'][0]['name'],
          author_email = metadata['project']['authors'][0]['email'],
          url = metadata['project']['urls']['homepage'],
          description = metadata['project']['description'],
          long_description = long_description,
          classifiers = metadata['project']['classifiers'],
          license = metadata['project']['license']['text'],
          packages = ['photini'],
          package_dir = {'' : 'src'},
          package_data = {'photini' : package_data},
          entry_points = {
              'console_scripts' : [
                  '{} = {}'.format(k, v)
                  for k, v in metadata['project']['scripts'].items()],
              'gui_scripts' : [
                  '{} = {}'.format(k, v)
                  for k, v in metadata['project']['gui-scripts'].items()],
              },
          install_requires = metadata['project']['dependencies'],
          extras_require = metadata['project']['optional-dependencies'],
          zip_safe = metadata['tool']['setuptools']['zip-safe'],
          )
