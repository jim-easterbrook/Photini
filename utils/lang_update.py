##  Photini - a simple photo metadata editor.
##  http://github.com/jim-easterbrook/Photini
##  Copyright (C) 2020-22  Jim Easterbrook  jim@jim-easterbrook.me.uk
##
##  This program is free software: you can redistribute it and/or
##  modify it under the terms of the GNU General Public License as
##  published by the Free Software Foundation, either version 3 of the
##  License, or (at your option) any later version.
##
##  This program is distributed in the hope that it will be useful,
##  but WITHOUT ANY WARRANTY; without even the implied warranty of
##  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
##  General Public License for more details.
##
##  You should have received a copy of the GNU General Public License
##  along with this program.  If not, see
##  <http://www.gnu.org/licenses/>.

from argparse import ArgumentParser
import os
import re
import subprocess
import sys
import xml.etree.ElementTree as ET

from sphinx.application import Sphinx


args = None


def extract_program_strings(root):
    src_dir = os.path.join(root, 'src', 'photini')
    dst_dir = os.path.join(root, 'src', 'lang')
    inputs = []
    for name in os.listdir(src_dir):
        base, ext = os.path.splitext(name)
        if ext == '.py':
            inputs.append(os.path.join(src_dir, name))
    inputs.sort()
    # choose language(s)
    outputs = [os.path.join(dst_dir, 'templates', 'qt', 'photini.ts')]
    if args.language:
        path = os.path.join(dst_dir, args.language)
        if not os.path.isdir(path):
            os.makedirs(path)
        outputs.append(os.path.join(path, 'photini.ts'))
    else:
        for name in os.listdir(dst_dir):
            path = os.path.join(dst_dir, name, 'photini.ts')
            if os.path.exists(path):
                outputs.append(path)
        outputs.sort()
    # change Transifex language
    for path in outputs:
        if not os.path.exists(path):
            continue
        tree = ET.parse(path)
        xml = tree.getroot()
        language = xml.get('language', default='')
        if '@' not in language:
            continue
        xml.set('language', language.split('@')[0])
        tree.write(path, encoding='utf-8',
                   xml_declaration=True, short_empty_elements=False)
    # run pylupdate
    for path in outputs:
        cmd = ['pyside6-lupdate', '-source-language', 'en_GB']
        if 'templates' not in path:
            language = os.path.basename(os.path.dirname(path))
            cmd += ['-target-language', language]
        if args.purge:
            cmd.append('-no-obsolete')
        if args.strip:
            cmd += ['-locations', 'none']
        cmd += inputs
        cmd += ['-ts', path]
        result = subprocess.call(cmd)
        if result:
            return result
    return 0


def extract_doc_strings(root):
    # create / update .pot files with Sphinx
    src_dir = os.path.join(root, 'src', 'doc')
    dst_dir = os.path.join(root, 'src', 'lang', 'templates', 'gettext')
    doctree_dir = os.path.join(root, 'doctrees', 'gettext')
    confoverrides = {'gettext_location': not args.strip}
    app = Sphinx(src_dir, src_dir, dst_dir, doctree_dir, 'gettext',
                 confoverrides=confoverrides, freshenv=True,
                 warningiserror=True)
    app.build()
    # create / update .po files with Babel
    src_dir = dst_dir
    dst_dir = os.path.join(root, 'src', 'lang')
    inputs = []
    for name in os.listdir(src_dir):
        base, ext = os.path.splitext(name)
        if ext == '.pot':
            inputs.append(os.path.join(src_dir, name))
    inputs.sort()
    if args.language:
        locales = [args.language]
    else:
        locales = []
        for name in os.listdir(dst_dir):
            if '.' not in name and name not in ('templates', 'en'):
                locales.append(name)
    locales.sort()
    for locale in locales:
        dst_dir = os.path.join(root, 'src', 'lang', locale, 'LC_MESSAGES')
        if not os.path.isdir(dst_dir):
            os.makedirs(dst_dir)
        for in_file in inputs:
            domain = os.path.splitext(os.path.basename(in_file))[0]
            out_file = os.path.join(dst_dir, domain + '.po')
            cmd = ['pybabel', 'update', '--input-file', in_file,
                   '--output-file', out_file, '--locale', locale,
                   '--width', '79', '--init-missing']
            result = subprocess.call(cmd)
            if result:
                return result
    return 0


def main(argv=None):
    global args

    if argv:
        sys.argv = argv
    parser = ArgumentParser(
        description='Extract strings for translation')
    parser.add_argument('-d', '--docs', action='store_true',
                        help='process documentation strings')
    parser.add_argument('-l', '--language',
                        help='language code, e.g. nl or cs_CZ')
    parser.add_argument('-p', '--purge', action='store_true',
                        help='remove obsolete strings')
    parser.add_argument('-s', '--strip', action='store_true',
                        help='remove line numbers')
    args = parser.parse_args()
    root = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
    if args.docs:
        return extract_doc_strings(root)
    return extract_program_strings(root)


if __name__ == "__main__":
    sys.exit(main())
