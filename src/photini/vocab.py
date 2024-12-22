#  Photini - a simple photo metadata editor.
#  http://github.com/jim-easterbrook/Photini
# Copyright (C) 2024  Jim Easterbrook  jim@jim-easterbrook.me.uk
#
# This file is part of Photini.
#
# Photini is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the
# Free Software Foundation, either version 3 of the License, or (at your
# option) any later version.
#
# Photini is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
# FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License
# for more details.
#
# You should have received a copy of the GNU General Public License
# along with Photini.  If not, see <http://www.gnu.org/licenses/>.

# Stuff to handle "controlled vocabularies" from IPTC and others

from photini.cv import image_region_types, image_region_roles


class IPTCBaseCV(object):
    @classmethod
    def init_qcode_map(cls, prefix):
        prefix += ':'
        cls.qcode_map = {}
        for item in cls.vocab:
            qcode = item['qcode'].replace(prefix, '')
            cls.qcode_map[qcode] = item['data']

    @classmethod
    def data_for_qcode(cls, qcode):
        if qcode in cls.qcode_map:
            return cls.qcode_map[qcode]
        return {}


class IPTCRoleCV(IPTCBaseCV):
    vocab = image_region_roles


class IPTCTypeCV(IPTCBaseCV):
    vocab = image_region_types


IPTCRoleCV.init_qcode_map('imgregrole')
IPTCTypeCV.init_qcode_map('imgregtype')


class MWGTypeCV(object):
    vocab = (
        {'data': {'Iptc4xmpExt:Name': {'en-GB': 'Face'},
                  'xmp:Identifier': ('mwg-rs:Type Face',)},
         'definition': {'en-GB': "Region area for people's faces."},
         'name': {'en-GB': 'Face'},
         'note': None},
        {'data': {'Iptc4xmpExt:Name': {'en-GB': 'Pet'},
                  'xmp:Identifier': ('mwg-rs:Type Pet',)},
         'definition': {'en-GB': "Region area for pets."},
         'name': {'en-GB': 'Pet'},
         'note': None},
        {'data': {'Iptc4xmpExt:Name': {'en-GB': 'Focus/EvaluatedUsed'},
                  'xmp:Identifier': ('mwg-rs:Type Focus',
                                     'mwg-rs:FocusUsage EvaluatedUsed')},
         'definition': {'en-GB': "Region area for camera auto-focus regions."
                        "<br/>EvaluatedUsed specifies that the focus point was"
                        " considered during focusing and was used in the final"
                        " image."},
         'name': {'en-GB': 'Focus (EvaluatedUsed)'},
         'note': None},
        {'data': {'Iptc4xmpExt:Name': {'en-GB': 'Focus/EvaluatedNotUsed'},
                  'xmp:Identifier': ('mwg-rs:Type Focus',
                                     'mwg-rs:FocusUsage EvaluatedNotUsed')},
         'definition': {'en-GB': "Region area for camera auto-focus regions."
                        "<br/>EvaluatedNotUsed specifies that the focus point"
                        " was considered during focusing but not utilised in"
                        " the final image."},
         'name': {'en-GB': 'Focus (EvaluatedNotUsed)'},
         'note': None},
        {'data': {'Iptc4xmpExt:Name': {'en-GB': 'Focus/NotEvaluatedNotUsed'},
                  'xmp:Identifier': ('mwg-rs:Type Focus'
                                     'mwg-rs:FocusUsage NotEvaluatedNotUsed')},
         'definition': {'en-GB': "Region area for camera auto-focus regions."
                        "<br/>NotEvaluatedNotUsed specifies that a focus point"
                        " was not evaluated and not used, e.g. a fixed focus"
                        " point on the camera which was not used in any"
                        " fashion."},
         'name': {'en-GB': 'Focus (NotEvaluatedNotUsed)'},
         'note': None},
        {'data': {'Iptc4xmpExt:Name': {'en-GB': 'BarCode'},
                  'xmp:Identifier': ('mwg-rs:Type BarCode',)},
         'definition': {'en-GB': "One dimensional linear or two dimensional"
                        " matrix optical code."},
         'name': {'en-GB': 'BarCode'},
         'note': None},
        )

    @classmethod
    def clean_file_data(cls, ctype_data):
        # remove any MWG ctype from a list of ctypes
        result = list(ctype_data)
        for item in cls.vocab:
            if item['data'] in result:
                result.remove(item['data'])
                break
        return result

    @classmethod
    def to_file_data(cls, ctype_data):
        for item in cls.vocab:
            if item['data'] in ctype_data:
                return dict(x.split() for x in item['data']['xmp:Identifier'])
        return {}

    @staticmethod
    def from_file_data(data):
        if 'mwg-rs:Type' not in data:
            return {}
        name = data['mwg-rs:Type']
        identifier = ['mwg-rs:Type ' + name]
        if 'mwg-rs:FocusUsage' in data:
            focus_usage = data['mwg-rs:FocusUsage']
            name += '/' + focus_usage
            identifier.append('mwg-rs:FocusUsage ' + focus_usage)
        return {'Iptc4xmpExt:Name': name, 'xmp:Identifier': tuple(identifier)}
