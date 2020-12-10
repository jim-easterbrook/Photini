#  Photini - a simple photo metadata editor.
#  http://github.com/jim-easterbrook/Photini
#  Copyright (C) 2012-20  Jim Easterbrook  jim@jim-easterbrook.me.uk
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
from distutils import log
from distutils.cmd import Command
from distutils.command.upload import upload
from distutils.errors import DistutilsExecError, DistutilsOptionError
import os
import re
from setuptools import setup

# read current version info without importing package
with open('src/photini/__init__.py') as f:
    exec(f.read())

cmdclass = {}
command_options = {}


# modify upload class to add appropriate tag
# requires GitPython - 'sudo pip install gitpython'
class upload_and_tag(upload):
    def run(self):
        import git
        result = upload.run(self)
        message = 'Photini-' + __version__ + '\n\n'
        with open('CHANGELOG.txt') as cl:
            while not cl.readline().startswith('Changes'):
                pass
            while True:
                line = cl.readline().strip()
                if not line:
                    break
                message += line + '\n'
        repo = git.Repo()
        tag = repo.create_tag(__version__, message=message)
        remote = repo.remotes.origin
        remote.push(tags=True)
        return result

cmdclass['upload'] = upload_and_tag


# set options for building distributions
command_options['sdist'] = {
    'formats'        : ('setup.py', 'gztar'),
    'force_manifest' : ('setup.py', '1'),
    }


# add command to 'compile' translated messages
class LRelease(Command):
    description = 'compile translated strings (.ts) to binary .qm files'
    user_options = [
        ('output-dir=', 'o', 'location of output .qm files'),
        ('input-dir=', 'i', 'location of input .ts files'),
    ]

    def initialize_options(self):
        self.output_dir = None
        self.input_dir = None

    def finalize_options(self):
        if not self.output_dir:
            raise DistutilsOptionError('no output directory specified')
        if not self.input_dir:
            raise DistutilsOptionError('no input directory specified')

    def run(self):
        self.mkpath(self.output_dir)
        for name in os.listdir(self.input_dir):
            base, ext = os.path.splitext(name)
            if ext != '.ts' or '.' not in base:
                continue
            args = [os.path.join(self.input_dir, name),
                    '-qm', os.path.join(self.output_dir, base + '.qm')]
            try:
                self.spawn(['lrelease-qt5'] + args)
            except DistutilsExecError:
                self.spawn(['lrelease'] + args)

cmdclass['lrelease'] = LRelease
command_options['lrelease'] = {
    'output_dir' : ('setup.py', 'src/photini/data/lang'),
    'input_dir'  : ('setup.py', 'src/lang'),
    }

# tweak Babel's translation commands
try:
    from babel.messages import frontend as babel
except ImportError:
    babel = None
if babel:
    class InitCatalog(babel.init_catalog):
        def finalize_options(self):
            if self.input_file:
                self.domain = os.path.splitext(
                    os.path.basename(self.input_file))[0]
            babel.init_catalog.finalize_options(self)
            if os.path.exists(self.output_file):
                raise DistutilsOptionError(
                    'output file exists, use "update_catalog" to update it')

    class UpdateCatalog(babel.update_catalog):
        def finalize_options(self):
            if self.input_file:
                self.domain = os.path.splitext(
                    os.path.basename(self.input_file))[0]
            babel.update_catalog.finalize_options(self)

    cmdclass['init_catalog'] = InitCatalog
    cmdclass['update_catalog'] = UpdateCatalog
    command_options['init_catalog'] = {
        'output_dir' : ('setup.py', 'src/lang/doc'),
        }
    command_options['update_catalog'] = {
        'output_dir' : ('setup.py', 'src/lang/doc'),
        }

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
          'Programming Language :: Python :: 2',
          'Programming Language :: Python :: 2.7',
          'Programming Language :: Python :: 3',
          'Topic :: Multimedia :: Graphics',
          ],
      packages = ['photini'],
      package_dir = {'' : 'src'},
      package_data = {'photini' : package_data},
      cmdclass = cmdclass,
      command_options = command_options,
      entry_points = {
          'console_scripts' : [
              'photini-post-install = photini.scripts:post_install',
              ],
          'gui_scripts' : [
              'photini = photini.editor:main',
              ],
          },
      install_requires = ['appdirs >= 1.3', 'requests >= 2.4.0', 'six >= 1.5'],
      extras_require = {
          'flickr'   : ['flickrapi >= 2.0', 'keyring >= 7.0'],
          'google'   : ['requests-oauthlib >= 1.0', 'keyring >= 7.0'],
          'importer' : ['gphoto2 >= 0.10'],
          'spelling' : [],
          },
      zip_safe = False,
      )
