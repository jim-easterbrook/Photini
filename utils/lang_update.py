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


def html_escape(match):
    text = match.group(0)
    text = text.replace('\xa0', '&#xa0;')
    text = text.replace('"', '&quot;')
    text = text.replace("'", '&apos;')
    return text


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
    # remove extra plurals expected by Transifex
    numerus_count = {
        'cs': {'qt': 3, 'tx': 4},
        'es': {'qt': 2, 'tx': 3},
        'fr': {'qt': 2, 'tx': 3},
        'it': {'qt': 2, 'tx': 3},
        'pl': {'qt': 3, 'tx': 4},
        }
    for path in outputs:
        if 'templates' in path or not os.path.exists(path):
            continue
        language = os.path.basename(os.path.dirname(path))
        if language not in numerus_count:
            continue
        tree = ET.parse(path)
        xml = tree.getroot()
        for context in xml.iter('context'):
            for message in context.iter('message'):
                if message.get('numerus'):
                    translation = message.find('translation')
                    numerusforms = translation.findall('numerusform')
                    extra = len(numerusforms) - numerus_count[language]['qt']
                    if extra > 0:
                        for i in range(extra):
                            translation.remove(numerusforms.pop())
        tree.write(path, encoding='utf-8',
                   xml_declaration=True, short_empty_elements=False)
    # run pylupdate
    cmd = ['pyside6-lupdate']
    if args.purge:
        cmd.append('-no-obsolete')
    if args.strip:
        cmd += ['-locations', 'none']
    cmd += inputs
    cmd.append('-ts')
    cmd += outputs
    result = subprocess.call(cmd)
    if result:
        return result
    # process pylupdate output
    if args.transifex:
        unused = ET.Element('numerusform')
        unused.text = 'Unused'
    for path in outputs:
        if not os.path.exists(path):
            continue
        if 'templates' in path:
            language = None
        else:
            language = os.path.basename(os.path.dirname(path))
        # process as XML
        tree = ET.parse(path)
        xml = tree.getroot()
        xml.set('sourcelanguage', 'en_GB')
        if language:
            xml.set('language', language)
        # add extra plurals expected by Transifex
        if args.transifex and  language in numerus_count:
            for context in xml.iter('context'):
                for message in context.iter('message'):
                    if message.get('numerus'):
                        translation = message.find('translation')
                        numerusforms = len(translation.findall('numerusform'))
                        missing = numerus_count[language]['tx'] - numerusforms
                        if missing > 0:
                            for i in range(missing):
                                translation.append(unused)
        tree.write(path, encoding='utf-8',
                   xml_declaration=True, short_empty_elements=False)
        # process as text
        with open(path, 'r') as f:
            text = f.read()
        text = re.sub('>.+?<', html_escape, text, flags=re.DOTALL)
        text = text.replace(
            "<?xml version='1.0' encoding='utf-8'?>",
            '<?xml version="1.0" encoding="utf-8"?>\n<!DOCTYPE TS>')
        text += '\n'
        with open(path, 'w') as f:
            f.write(text)
    return 0


def extract_doc_strings(root):
    # create / update .pot files with Sphinx
    src_dir = os.path.join(root, 'src', 'doc')
    dst_dir = os.path.join(root, 'src', 'lang', 'templates', 'gettext')
    doctree_dir = os.path.join(root, 'doctrees', 'gettext')
    app = Sphinx(src_dir, src_dir, dst_dir, doctree_dir, 'gettext')
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
    outputs = []
    for locale in locales:
        for in_file in inputs:
            domain = os.path.splitext(os.path.basename(in_file))[0]
            out_file = os.path.join(
                dst_dir, locale, 'LC_MESSAGES', domain + '.po')
            if os.path.exists(out_file):
                cmd = ['pybabel', 'update']
            else:
                cmd = ['pybabel', 'init']
            cmd += ['--input-file', in_file, '--output-file', out_file,
                    '--locale', locale, '--width', '79']
            result = subprocess.call(cmd)
            if result:
                return result
            outputs.append(out_file)
    if args.strip:
        test = re.compile('^#: ')
        for path in inputs + outputs:
            with open(path, 'r') as f:
                old_text = f.readlines()
            with open(path, 'w') as f:
                for line in old_text:
                    if not test.match(line):
                        f.write(line)
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
    parser.add_argument('-t', '--transifex', action='store_true',
                        help='make output Transifex compatible')
    args = parser.parse_args()
    root = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
    if args.docs:
        return extract_doc_strings(root)
    return extract_program_strings(root)


if __name__ == "__main__":
    sys.exit(main())
