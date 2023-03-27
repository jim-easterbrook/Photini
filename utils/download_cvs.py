#  Photini - a simple photo metadata editor.
#  http://github.com/jim-easterbrook/Photini
#  Copyright (C) 2023  Jim Easterbrook  jim@jim-easterbrook.me.uk
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
from pprint import pprint
import sys

import requests


def main(argv=None):
    root = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
    dest_file = os.path.join(root, 'src', 'photini', 'cv.py')
    with open(dest_file, 'w') as py:
        py.write('''# http://github.com/jim-easterbrook/Photini
# IPTC "controlled vocabulary" data downloaded from http://cv.iptc.org/newscodes

''')
        for (url, data_name) in (
                ('https://cv.iptc.org/newscodes/imageregiontype/',
                 'image_region_types'),
                ('https://cv.iptc.org/newscodes/imageregionrole/',
                 'image_region_roles')):
            with requests.Session() as session:
                params = {
                    'format': 'json',
                    'lang': 'x-all',
                    }
                rsp = session.get(url, params=params)
                rsp.raise_for_status()
                rsp = rsp.json()
                py.write('''# ©{copyrightHolder}
# Date: {dateReleased}
# Licence: {licenceLink}
# {uri}
'''.format(**rsp))
                uris = []
                data = {}
                for concept in rsp['conceptSet']:
                    uri = concept['uri']
                    if uri not in uris:
                        uris.append(uri)
                        data[uri] = {'name': {}, 'definition': {}, 'note': {}}
                    data[uri]['name'].update(concept['prefLabel'])
                    data[uri]['definition'].update(concept['definition'])
                    if 'note' in concept:
                        data[uri]['note'].update(concept['note'])
                    data[uri]['uri'] = concept['uri']
                py.write(data_name)
                py.write(' = \\\n')
                pprint(tuple(data[x] for x in uris), stream=py)
                py.write('\n')
    return 0


if __name__ == "__main__":
    sys.exit(main())
