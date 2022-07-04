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
    if args.weblate:
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
    # ensure messages are marked as UTF-8
    for path in outputs:
        if not os.path.exists(path):
            continue
        tree = ET.parse(path)
        xml = tree.getroot()
        for context in xml.iter('context'):
            for message in context.iter('message'):
                message.set('encoding', 'UTF-8')
        tree.write(path, encoding='UTF-8',
                   xml_declaration=True, short_empty_elements=True)
    # run pylupdate
    cmd = ['pylupdate5', '-verbose']
    cmd += inputs
    cmd.append('-ts')
    cmd += outputs
    result = subprocess.call(cmd)
    if result:
        return result
    # process pylupdate output
    numerus_count = {
        'cs': 4,
        'es': 3,
        'fr': 3,
        'it': 3,
        'pl': 4,
        }
    unused = ET.Element('numerusform')
    unused.text = 'Unused'
    for path in outputs:
        if not os.path.exists(path):
            continue
        # process as XML
        tree = ET.parse(path)
        xml = tree.getroot()
        language = xml.get('language')
        for context in xml.iter('context'):
            for message in context.iter('message'):
                if args.strip:
                    location = message.find('location')
                    if location is not None:
                        message.remove(message.find('location'))
                # add extra plurals expected by Transifex
                if language in numerus_count and message.get('numerus'):
                    translation = message.find('translation')
                    numerusforms = translation.findall('numerusform')
                    missing = numerus_count[language] - len(numerusforms)
                    if missing > 0:
                        for i in range(missing):
                            translation.append(unused)
        tree.write(path, encoding='utf-8',
                   xml_declaration=True, short_empty_elements=True)
        # process as text
        with open(path, 'r') as f:
            text = f.read()
        text = re.sub('>.+?<', html_escape, text, flags=re.DOTALL)
        if args.weblate:
            text = text.replace(
                "<?xml version='1.0' encoding='utf-8'?>",
                '<?xml version="1.0" encoding="utf-8"?>\n<!DOCTYPE TS>')
            text = text.replace(
                '<TS language="{}" sourcelanguage="en_GB" version="2.0">'.format(language),
                '<TS version="2.1" language="{}" sourcelanguage="en_GB">'.format(language))
            text += '\n'
        if args.transifex:
            text = text.replace(
                "<?xml version='1.0' encoding='utf-8'?>\n",
                '<?xml version="1.0" ?><!DOCTYPE TS>')
            text = text.replace(
                '<TS language="{}" sourcelanguage="en_GB" version="2.0">'.format(language),
                '<TS version="2.0" language="{}" sourcelanguage="en_GB">'.format(language))
            text = text.replace(
                '<translation type="unfinished" />',
                '<translation type="unfinished"/>')
            text = re.sub(
                '\s+<numerusform', '<numerusform', text, flags=re.DOTALL)
            text = re.sub(
                '\s+</translation', '</translation', text, flags=re.DOTALL)
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
    parser.add_argument('-s', '--strip', action='store_true',
                        help='remove line numbers')
    parser.add_argument('-t', '--transifex', action='store_true',
                        help='attempt to match Transifex syntax')
    parser.add_argument('-w', '--weblate', action='store_true',
                        help='attempt to match Weblate syntax')
    args = parser.parse_args()
    if args.transifex or args.weblate:
        args.strip = True
    root = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
    if args.docs:
        return extract_doc_strings(root)
    return extract_program_strings(root)


if __name__ == "__main__":
    sys.exit(main())
