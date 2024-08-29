#  Photini - a simple photo metadata editor.
#  http://github.com/jim-easterbrook/Photini
#  Copyright (C) 2023  Jim Easterbrook  jim@jim-easterbrook.me.uk
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or (at
#  your option) any later version.
#
#  This program is distributed in the hope that it will be useful, but
#  WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
#  General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program.  If not, see <http://www.gnu.org/licenses/>.

import os
import subprocess
import tempfile
import xml.etree.ElementTree as ET

from setuptools import build_meta as _orig
from setuptools.build_meta import *


def build_lang(result_directory):
    tools = ['lrelease6', 'pyside6-lrelease', 'lrelease-qt5']
    src_dir = os.path.join('src', 'lang')
    dst_dir = os.path.join('src', 'photini', 'data', 'lang')
    if os.path.exists(dst_dir) and not os.path.exists(src_dir):
        # probably building wheel from sdist, no need to compile
        return
    print('running build_lang')
    os.makedirs(dst_dir, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=result_directory) as tmp_dir:
        for lang in os.listdir(src_dir):
            src_file = os.path.join(src_dir, lang, 'photini.ts')
            if not os.path.exists(src_file):
                continue
            # copy source to remove extra plurals not used by Qt
            numerus_count = {'cs': 3, 'es': 2, 'fr': 2, 'it': 2, 'pl': 3}
            if lang in numerus_count:
                tree = ET.parse(src_file)
                xml = tree.getroot()
                for context in xml.iter('context'):
                    for message in context.iter('message'):
                        if message.get('numerus'):
                            translation = message.find('translation')
                            numerusforms = translation.findall('numerusform')
                            extra = len(numerusforms) - numerus_count[lang]
                            for i in range(extra):
                                translation.remove(numerusforms.pop())
                src_file = os.path.join(tmp_dir, 'photini.' + lang + '.ts')
                tree.write(src_file, encoding='utf-8',
                           xml_declaration=True, short_empty_elements=False)
            dst_file = os.path.join(dst_dir, 'photini.' + lang + '.qm')
            if (os.path.exists(dst_file) and
                    os.stat(dst_file).st_mtime >= os.stat(src_file).st_mtime):
                continue
            print('compiling {} -> {}'.format(src_file, dst_file))
            for tool in list(tools):
                try:
                    subprocess.check_call([
                        tool, '-silent', src_file, '-qm', dst_file])
                    break
                except Exception:
                    if len(tools) == 1:
                        raise
                    tools.remove(tool)


def build_wheel(wheel_directory, config_settings=None, metadata_directory=None):
    build_lang(wheel_directory)
    return _orig.build_wheel(wheel_directory, config_settings=config_settings,
                             metadata_directory=metadata_directory)


def build_sdist(sdist_directory, config_settings=None):
    build_lang(sdist_directory)
    return _orig.build_sdist(sdist_directory, config_settings=config_settings)
