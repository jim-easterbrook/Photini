#  Photini - a simple photo metadata editor.
#  http://github.com/jim-easterbrook/Photini
#  Copyright (C) 2012-24  Jim Easterbrook  jim@jim-easterbrook.me.uk
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
import xml.etree.ElementTree as ET

from distutils.command.build import build
from distutils.errors import DistutilsOptionError
from setuptools import Command, setup
from setuptools import __version__ as setuptools_version


def strip_plurals(self, src_file, dst_file, plural_count):
    # copy source to remove extra plurals not used by Qt
    tree = ET.parse(src_file)
    xml = tree.getroot()
    for context in xml.iter('context'):
        for message in context.iter('message'):
            if message.get('numerus'):
                translation = message.find('translation')
                numerusforms = translation.findall('numerusform')
                extra = len(numerusforms) - plural_count
                for i in range(extra):
                    translation.remove(numerusforms.pop())
    tree.write(dst_file, encoding='utf-8',
               xml_declaration=True, short_empty_elements=False)

def run_lrelease(self, src_file, dst_file):
    # run one of the possible versions of 'lrelease'
    for tool in list(self.tools):
        try:
            self.spawn([tool, '-silent', src_file, '-qm', dst_file])
            return
        except Exception as ex:
            self.tools.remove(tool)


# add command to 'compile' translated messages
class BuildLang(Command):
    description = 'compile translated strings (.ts) to binary .qm files'
    user_options = [
        ('input-dir=', 'i', 'location of input .ts files'),
        ('build-lib=', 'd', 'directory to build to'),
        ('force', 'f', "forcibly build everything (ignore file timestamps)"),
        ]

    def initialize_options(self):
        self.input_dir = None
        self.build_lib = None
        self.build_temp = None
        self.force = None

    def finalize_options(self):
        self.set_undefined_options('build',
                                   ('build_lib', 'build_lib'),
                                   ('build_temp', 'build_temp'),
                                   ('force', 'force'),
                                   )
        if not self.input_dir:
            raise DistutilsOptionError('no input directory specified')
        self.build_temp = os.path.join(self.build_temp, 'lang')
        self.output_dir = os.path.join(
            self.build_lib, 'photini', 'data', 'lang')

    def run(self):
        self.announce('running build_lang')
        self.tools = ['lrelease', 'lrelease6', 'pyside6-lrelease',
                      'lrelease-qt5']
        self.mkpath(self.output_dir)
        self.mkpath(self.build_temp)
        numerus_count = {'cs': 3, 'es': 2, 'fr': 2, 'it': 2, 'pl': 3}
        for lang in os.listdir(self.input_dir):
            src_file = os.path.join(self.input_dir, lang, 'photini.ts')
            if not os.path.exists(src_file):
                continue
            dst_file = os.path.join(
                self.output_dir, 'photini.' + lang + '.qm')
            if lang in numerus_count:
                tmp_file = os.path.join(
                    self.build_temp, 'photini.' + lang + '.ts')
                self.make_file(src_file, tmp_file, strip_plurals,
                               (self, src_file, tmp_file, numerus_count[lang]))
                self.make_file(tmp_file, dst_file, run_lrelease,
                               (self, tmp_file, dst_file))
            else:
                self.make_file(src_file, dst_file, run_lrelease,
                               (self, src_file, dst_file))
            if not self.tools:
                self.warn('unable to compile translation files')
                break


class CustomBuild(build):
    sub_commands = [('build_lang', None), *build.sub_commands]


setup_kwds = {
    'cmdclass': {'build': CustomBuild, 'build_lang': BuildLang},
    'command_options': {
        'build_lang': {
            'input_dir'  : ('setup.py', 'src/lang'),
            },
        },
    }


if tuple(map(int, setuptools_version.split('.')[:2])) < (61, 0):
    # get metadata from pyproject.toml
    import toml
    metadata = toml.load('pyproject.toml')

    with open(metadata['project']['readme']) as ldf:
        long_description = ldf.read()

    package_data = []
    for root, dirs, files in os.walk('src/photini/data/'):
        package_data += [
            os.path.join(root.replace('src/photini/', ''), x) for x in files]

    setup_kwds.update(
        name = metadata['project']['name'],
        author = metadata['project']['authors'][0]['name'],
        author_email = metadata['project']['authors'][0]['email'],
        url = metadata['project']['urls']['Homepage'],
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

setup(**setup_kwds)
