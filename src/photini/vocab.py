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
    def data_for_name(cls, name):
        return cls.vocab[name]['data']


class IPTCRoleCV(IPTCBaseCV):
    vocab = image_region_roles


class IPTCTypeCV(IPTCBaseCV):
    vocab = image_region_types


class MWGTypeCV(IPTCBaseCV):
    vocab = {
        'Face': {
            'data': {'Iptc4xmpExt:Name': {'en-GB': 'Face'},
                     'xmp:Identifier': ('Face',)},
            'file_data': {'mwg-rs:Type': 'Face'},
            'definition': {'en-GB': "Region area for people's faces."},
            'note': None},
        'Pet': {
            'data': {'Iptc4xmpExt:Name': {'en-GB': 'Pet'},
                     'xmp:Identifier': ('Pet',)},
            'file_data': {'mwg-rs:Type': 'Pet'},
            'definition': {'en-GB': "Region area for pets."},
            'note': None},
        'FocusEvaluatedUsed': {
            'data': {'Iptc4xmpExt:Name': {'en-GB': 'Focus (EvaluatedUsed)'},
                     'xmp:Identifier': ('FocusEvaluatedUsed',)},
            'file_data': {'mwg-rs:Type': 'Focus',
                          'mwg-rs:FocusUsage': 'EvaluatedUsed'},
            'definition': {'en-GB': "Region area for camera auto-focus regions."
                           "<br/>EvaluatedUsed specifies that the focus point"
                           " was considered during focusing and was used in the"
                           " final image."},
            'note': None},
        'FocusEvaluatedNotUsed': {
            'data': {'Iptc4xmpExt:Name': {'en-GB': 'Focus (EvaluatedNotUsed)'},
                     'xmp:Identifier': ('FocusEvaluatedNotUsed',)},
            'file_data': {'mwg-rs:Type': 'Focus',
                          'mwg-rs:FocusUsage': 'EvaluatedNotUsed'},
            'definition': {'en-GB': "Region area for camera auto-focus regions."
                           "<br/>EvaluatedNotUsed specifies that the focus"
                           " point was considered during focusing but not"
                           " utilised in the final image."},
            'note': None},
        'FocusNotEvaluatedNotUsed': {
            'data': {
                'Iptc4xmpExt:Name': {'en-GB': 'Focus (NotEvaluatedNotUsed)'},
                'xmp:Identifier': ('FocusNotEvaluatedNotUsed',)},
            'file_data': {'mwg-rs:Type': 'Focus',
                          'mwg-rs:FocusUsage': 'NotEvaluatedNotUsed'},
            'definition': {'en-GB': "Region area for camera auto-focus regions."
                           "<br/>NotEvaluatedNotUsed specifies that a focus"
                           " point was not evaluated and not used, e.g. a fixed"
                           " focus point on the camera which was not used in"
                           " any fashion."},
            'note': None},
        'BarCode': {
            'data': {'Iptc4xmpExt:Name': {'en-GB': 'BarCode'},
                     'xmp:Identifier': ('BarCode',)},
            'file_data': {'mwg-rs:Type': 'BarCode'},
            'definition': {'en-GB': "One dimensional linear or two dimensional"
                           " matrix optical code."},
            'note': None},
        }

    @classmethod
    def clean_file_data(cls, ctype_data):
        # remove any MWG ctype from a list of ctypes
        result = list(ctype_data)
        for item in cls.vocab.values():
            if item['data'] in result:
                result.remove(item['data'])
                break
        return result

    @classmethod
    def to_file_data(cls, ctype_data):
        for item in cls.vocab.values():
            if item['data'] in ctype_data:
                return item['file_data']
        return {}

    @classmethod
    def from_file_data(cls, data):
        if 'mwg-rs:Type' not in data:
            return {}
        label = data['mwg-rs:Type']
        if 'mwg-rs:FocusUsage' in data:
            label += data['mwg-rs:FocusUsage']
        if label in cls.vocab:
            return cls.vocab[label]['data']
        name = data['mwg-rs:Type']
        if 'mwg-rs:FocusUsage' in data:
            name = '{} ({})'.format(name, data['mwg-rs:FocusUsage'])
        return {'Iptc4xmpExt:Name': {'en-GB': name},
                'xmp:Identifier': (label,)}
