#  Photini - a simple photo metadata editor.
#  http://github.com/jim-easterbrook/Photini
#  Copyright (C) 2012-19  Jim Easterbrook  jim@jim-easterbrook.me.uk
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
from distutils.cmd import Command
from distutils.command.upload import upload
from distutils.errors import DistutilsExecError, DistutilsOptionError
import os
import re
from setuptools import setup
import sys

# read current version info without importing package
with open('src/photini/__init__.py') as f:
    exec(f.read())

cmdclass = {}
command_options = {}

# get GitHub repo information
# requires GitPython - 'sudo pip install gitpython'
try:
    import git
except ImportError:
    git = None
if git:
    try:
        repo = git.Repo()
        if repo.is_dirty():
            dev_no = int(build.split()[0])
            commit = build.split()[1][1:-1]
            # increment dev_no when there's been a commit
            last_commit = str(repo.head.commit)[:7]
            if last_commit != commit:
                dev_no += 1
                commit = last_commit
            # get latest release tag
            latest = 0
            for tag in repo.tags:
                if tag.commit.committed_date > latest:
                    tag_name = str(tag)
                    if re.match('\d{4}\.\d{1,2}\.\d$', tag_name):
                        latest = tag.commit.committed_date
                        last_release = tag_name
            # set current version number (calendar based)
            major, minor, micro = map(int, last_release.split('.'))
            today = date.today()
            if today.year == major and today.month == minor:
                micro += 1
            else:
                micro = 0
            __version__ = '{:4d}.{:d}.{:d}'.format(
                today.year, today.month, micro)
            # update __init__.py if anything's changed
            new_text = """from __future__ import unicode_literals

__version__ = '%s'
build = '%d (%s)'
""" % (__version__, dev_no, commit)
            with open('src/photini/__init__.py', 'r') as vf:
                old_text = vf.read()
            if new_text != old_text:
                with open('src/photini/__init__.py', 'w') as vf:
                    vf.write(new_text)
    except (git.exc.InvalidGitRepositoryError, git.exc.GitCommandNotFound):
        pass

# if sphinx is installed, add commands to build documentation and to
# extract strings for translation
try:
    from sphinx.setup_command import BuildDoc
except ImportError:
    BuildDoc = None
if BuildDoc:
    class BuildSphinx(BuildDoc):
        description = 'build Photini documentation'

    class GetText(BuildDoc):
        description = 'prepare Photini documentation for translation'

    cmdclass['build_sphinx'] = BuildSphinx
    command_options['build_sphinx'] = {
        'all_files'  : ('setup.py', '1'),
        'source_dir' : ('setup.py', 'src/doc'),
        'build_dir'  : ('setup.py', 'doc'),
        'builder'    : ('setup.py', 'html'),
        }
    cmdclass['xgettext'] = GetText
    command_options['xgettext'] = {
        'all_files'  : ('setup.py', '1'),
        'source_dir' : ('setup.py', 'src/doc'),
        'build_dir'  : ('setup.py', 'src/lang/doc/pot'),
        'builder'    : ('setup.py', 'gettext'),
        }

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

# add command to extract strings for translation
# NB the "babel" package provides an extract_messages command, but it is
# an alternative to xgettext, generating .pot files. This uses Qt's
# pylupdate5 (or pylupdate4) command to generate .ts files
class LUpdate(Command):
    description = 'extract localizable strings from Photini program code'
    user_options = [
        ('locale=', 'l',
         'locale for a new localized catalog'),
        ('output-dir=', 'o',
         'directory for the output file'),
        ('project-file=', 'p',
         'name of the project file (generated)'),
        ('input-dir=', 'i',
         'directory that should be scanned for Python files'),
    ]

    def initialize_options(self):
        self.locale = None
        self.output_dir = None
        self.input_dir = None
        self.project_file = None

    def finalize_options(self):
        if not self.output_dir:
            raise DistutilsOptionError('no output directory specified')
        if not self.project_file:
            raise DistutilsOptionError('no project file specified')
        if not self.input_dir:
            raise DistutilsOptionError('no input directory specified')

    def run(self):
        inputs = []
        for name in os.listdir(self.input_dir):
            base, ext = os.path.splitext(name)
            if ext == '.py':
                inputs.append(os.path.join(self.input_dir, name))
        inputs.sort()
        self.mkpath(self.output_dir)
        outputs = []
        for name in os.listdir(self.output_dir):
            if name.startswith('photini.'):
                outputs.append(os.path.join(self.output_dir, name))
        if self.locale:
            output_file = os.path.join(
                self.output_dir, 'photini.' + self.locale + '.ts')
            if output_file not in outputs:
                outputs.append(output_file)
        outputs.sort()
        # workaround for UTF-8 bug in pylupdate
        for output_file in outputs:
            if os.path.exists(output_file):
                bak_file = output_file + '.bak'
                os.rename(output_file, bak_file)
                with open(bak_file, 'r') as src:
                    with open(output_file, 'w') as dst:
                        for line in src.readlines():
                            dst.write(line.replace(
                                '<message>', '<message encoding="UTF-8">'))
                os.unlink(bak_file)
        with open(self.project_file, 'w') as proj:
            proj.write('''SOURCES = {}
TRANSLATIONS = {}
CODECFORTR = UTF-8
CODECFORSRC = UTF-8
'''.format(' '.join(inputs), ' '.join(outputs)))
        args = ['-verbose', '-noobsolete', self.project_file]
        try:
            self.spawn(['pylupdate5'] + args)
        except DistutilsExecError:
            self.spawn(['pylupdate4'] + args)

cmdclass['lupdate'] = LUpdate
command_options['lupdate'] = {
    'output_dir'  : ('setup.py', 'src/lang'),
    'project_file': ('setup.py', 'photini.pro'),
    'input_dir'   : ('setup.py', 'src/photini'),
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

data_files = []
if sys.platform.startswith('linux'):
    # install application menu shortcut
    data_files.append(('share/icons/hicolor/48x48/apps',
                       ['src/photini/data/icons/48/photini.png']))
    data_files.append(('share/applications', ['src/linux/photini.desktop']))
    command_options['install'] = {
        'single_version_externally_managed' : ('setup.py', '1'),
        'record'                            : ('setup.py', 'install.txt'),
        }

with open('README.rst') as ldf:
    long_description = ldf.read()
url = 'https://github.com/jim-easterbrook/Photini'

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
          'Programming Language :: Python :: 2.6',
          'Programming Language :: Python :: 2.7',
          'Programming Language :: Python :: 3',
          'Topic :: Multimedia :: Graphics',
          ],
      packages = ['photini'],
      package_dir = {'' : 'src'},
      package_data = {
          'photini' : ['data/*.txt', 'data/*.png', 'data/icons/*/photini.png',
                       'data/*map/script.js', 'data/openstreetmap/*.js',
                       'data/lang/*.qm'],
          },
      data_files = data_files,
      cmdclass = cmdclass,
      command_options = command_options,
      entry_points = {
          'gui_scripts' : [
              'photini = photini.editor:main',
              ],
          },
      install_requires = ['appdirs >= 1.3', 'requests >= 2.4.0', 'six >= 1.5'],
      extras_require = {
          'facebook' : [],
          'flickr'   : ['flickrapi >= 2.0', 'keyring >= 7.0'],
          'google'   : ['requests-oauthlib >= 1.0', 'keyring >= 7.0'],
          'importer' : ['gphoto2 >= 0.10'],
          'spelling' : [],
          },
      zip_safe = False,
      )
