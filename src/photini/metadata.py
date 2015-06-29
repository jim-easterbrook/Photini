##  Photini - a simple photo metadata editor.
##  http://github.com/jim-easterbrook/Photini
##  Copyright (C) 2012-15  Jim Easterbrook  jim@jim-easterbrook.me.uk
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

from __future__ import unicode_literals

from datetime import datetime
from fractions import Fraction
import locale
import logging
import math
import os

from PyQt4 import QtCore
import six

try:
    from .metadata_gexiv2 import MetadataHandler
except ImportError as e:
    try:
        from .metadata_pyexiv2 import MetadataHandler
    except ImportError:
        # raise exception on the one we really wanted
        raise e
from . import __version__

_encodings = None
def _decode_string(value):
    global _encodings
    if six.PY3:
        return value
    if not _encodings:
        _encodings = ['utf_8', 'latin_1']
        char_set = locale.getdefaultlocale()[1]
        if char_set:
            _encodings.append(char_set)
    for encoding in _encodings:
        try:
            return value.decode(encoding)
        except UnicodeDecodeError:
            continue
    return value.decode('utf_8')

def _encode_string(value, max_bytes=None):
    result = value.encode('utf_8')
    if max_bytes:
        result = result[:max_bytes]
    if six.PY3:
        result = result.decode('utf_8')
    return result

class LatLon(object):
    # simple class to store latitude and longitude
    def __init__(self, lat, lon):
        self.lat = round(lat, 6)
        self.lon = round(lon, 6)

    def __eq__(self, other):
        return isinstance(other, LatLon) and self.members() == other.members()

    def __ne__(self, other):
        return not isinstance(other, LatLon) or self.members() != other.members()

    def __str__(self):
        return '{:.6f}, {:.6f}'.format(self.lat, self.lon)

    def members(self):
        return (self.lat, self.lon)

    @classmethod
    def from_string(cls, value):
        return cls(*map(float, value.split(',')))

    @staticmethod
    def from_exif_part(value, ref):
        parts = list(map(Fraction, value.split()))
        result = float(parts[0])
        if len(parts) > 1:
            result += float(parts[1]) / 60.0
        if len(parts) > 2:
            result += float(parts[2]) / 3600.0
        if ref in ('S', 'W'):
            result = -result
        return result

    def to_exif(self):
        result = []
        for value, sign_char in zip((self.lat, self.lon), ('NS', 'EW')):
            if value >= 0.0:
                ref = sign_char[0]
            else:
                ref = sign_char[1]
                value = -value
            degrees = int(value)
            value = (value - degrees) * 60.0
            minutes = int(value)
            seconds = (value - minutes) * 60.0
            seconds = Fraction(seconds).limit_denominator(1000000)
            result.append('{:d}/1 {:d}/1 {:d}/{:d}'.format(
                degrees, minutes, seconds.numerator, seconds.denominator))
            result.append(ref)
        return result

    @staticmethod
    def from_xmp_part(value):
        degrees, residue = value.split(',')
        minutes = residue[:-1]
        ref = residue[-1]
        value = float(degrees) + (float(minutes) / 60.0)
        if ref in ('S', 'W'):
            value = -value
        return value

class LensSpec(object):
    # simple class to store lens "specificaton"
    def __init__(self, min_fl, max_fl, min_fl_fn, max_fl_fn):
        self.min_fl = Fraction(min_fl).limit_denominator(1000000)
        self.max_fl = Fraction(max_fl).limit_denominator(1000000)
        self.min_fl_fn = Fraction(min_fl_fn).limit_denominator(1000000)
        self.max_fl_fn = Fraction(max_fl_fn).limit_denominator(1000000)

    def __eq__(self, other):
        return isinstance(other, LensSpec) and self.members() == other.members()

    def __ne__(self, other):
        return not isinstance(other, LensSpec) or self.members() != other.members()

    def __str__(self):
        return '{:g}, {:g}, {:g}, {:g}'.format(
            float(self.min_fl), float(self.max_fl),
            float(self.min_fl_fn), float(self.max_fl_fn))

    def members(self):
        return (self.min_fl, self.max_fl, self.min_fl_fn, self.max_fl_fn)

    @classmethod
    def from_string(cls, value):
        return cls(*value.split(','))

# type of each tag's data
_data_type = {
    'Exif.Canon.LensModel'               : 'ignore',
    'Exif.CanonCs.Lens'                  : 'ignore',
    'Exif.CanonCs.LensType'              : 'ignore',
    'Exif.CanonCs.MaxAperture'           : 'ignore',
    'Exif.CanonCs.MinAperture'           : 'ignore',
    'Exif.CanonCs.ShortFocal'            : 'ignore',
    'Exif.GPSInfo.GPSLatitude'           : 'latlon',
    'Exif.Image.ApertureValue'           : 'APEX_aperture',
    'Exif.Image.Artist'                  : 'multi_string',
    'Exif.Image.Copyright'               : 'string',
    'Exif.Image.DateTime'                : 'datetime',
    'Exif.Image.DateTimeOriginal'        : 'datetime',
    'Exif.Image.FNumber'                 : 'rational',
    'Exif.Image.FocalLength'             : 'rational',
    'Exif.Image.ImageDescription'        : 'string',
    'Exif.Image.Orientation'             : 'int',
    'Exif.Image.ProcessingSoftware'      : 'string',
    'Exif.Photo.ApertureValue'           : 'APEX_aperture',
    'Exif.Photo.DateTimeDigitized'       : 'datetime',
    'Exif.Photo.DateTimeOriginal'        : 'datetime',
    'Exif.Photo.FNumber'                 : 'rational',
    'Exif.Photo.FocalLength'             : 'rational',
    'Exif.Photo.FocalLengthIn35mmFilm'   : 'ignore',
    'Exif.Photo.LensMake'                : 'string',
    'Exif.Photo.LensModel'               : 'string',
    'Exif.Photo.LensSerialNumber'        : 'string',
    'Exif.Photo.LensSpecification'       : 'lensspec',
    'Iptc.Application2.Byline'           : 'multi_string',
    'Iptc.Application2.Caption'          : 'string',
    'Iptc.Application2.Copyright'        : 'string',
    'Iptc.Application2.DateCreated'      : 'datetime',
    'Iptc.Application2.DigitizationDate' : 'datetime',
    'Iptc.Application2.Headline'         : 'string',
    'Iptc.Application2.Keywords'         : 'multi_string',
    'Iptc.Application2.ObjectName'       : 'string',
    'Xmp.dc.creator'                     : 'multi_string',
    'Xmp.dc.description'                 : 'string',
    'Xmp.dc.rights'                      : 'string',
    'Xmp.dc.subject'                     : 'multi_string',
    'Xmp.dc.title'                       : 'string',
    'Xmp.photoshop.DateCreated'          : 'datetime',
    'Xmp.exif.ApertureValue'             : 'APEX_aperture',
    'Xmp.exif.DateTimeDigitized'         : 'datetime',
    'Xmp.exif.DateTimeOriginal'          : 'datetime',
    'Xmp.exif.FNumber'                   : 'rational',
    'Xmp.exif.FocalLength'               : 'rational',
    'Xmp.exif.FocalLengthIn35mmFilm'     : 'ignore',
    'Xmp.exif.GPSLatitude'               : 'latlon',
    'Xmp.tiff.Artist'                    : 'multi_string',
    'Xmp.tiff.Copyright'                 : 'string',
    'Xmp.tiff.DateTime'                  : 'datetime',
    'Xmp.tiff.ImageDescription'          : 'string',
    'Xmp.tiff.Orientation'               : 'int',
    'Xmp.xmp.CreateDate'                 : 'datetime',
    'Xmp.xmp.ModifyDate'                 : 'datetime',
    }
# maximum length of Iptc data
_max_bytes = {
    'Iptc.Application2.Byline'           :   32,
    'Iptc.Application2.Caption'          : 2000,
    'Iptc.Application2.Copyright'        :  128,
    'Iptc.Application2.Headline'         :  256,
    'Iptc.Application2.Keywords'         :   64,
    'Iptc.Application2.ObjectName'       :   64,
    }

def read_exif(md, tag):
    if _data_type[tag] == 'ignore':
        return None
    if _data_type[tag] == 'latlon':
        lat_tag = tag
        lon_tag = lat_tag.replace('Latitude', 'Longitude')
        parts = []
        for sub_tag in (lat_tag, lat_tag + 'Ref', lon_tag, lon_tag + 'Ref'):
            if sub_tag not in md.get_exif_tags():
                return None
            parts.append(md.get_tag_string(sub_tag))
        return LatLon(LatLon.from_exif_part(parts[0], parts[1]),
                      LatLon.from_exif_part(parts[2], parts[3]))
    if tag not in md.get_exif_tags():
        return None
    value_string = md.get_tag_string(tag)
    if _data_type[tag] == 'int':
        return value_string
    elif _data_type[tag] == 'APEX_aperture':
        return math.sqrt(2.0 ** Fraction(value_string))
    elif _data_type[tag] == 'rational':
        return value_string
    elif _data_type[tag] == 'string':
        return _decode_string(value_string)
    elif _data_type[tag] == 'multi_string':
        return _decode_string(value_string).split(';')
    elif _data_type[tag] == 'datetime':
        return datetime.strptime(value_string, '%Y:%m:%d %H:%M:%S')
    elif _data_type[tag] == 'lensspec':
        return LensSpec(*value_string.split())
    else:
        raise RuntimeError('Cannot read tag ' + tag)
    return result

def read_iptc(md, tag):
    if _data_type[tag] == 'datetime':
        date_tag = tag
        time_tag = date_tag.replace('Date', 'Time')
        if date_tag in md.get_iptc_tags():
            date_string = md.get_tag_multiple(date_tag)[0]
            has_date = True
        else:
            date_string = '0001-01-01'
            has_date = False
        if time_tag in md.get_iptc_tags():
            time_string = md.get_tag_multiple(time_tag)[0][:8]
            has_time = True
        else:
            time_string = '00:00:00'
            has_time = False
        if has_date or has_time:
            return datetime.strptime(
                date_string + time_string, '%Y-%m-%d%H:%M:%S')
        return None
    if tag not in md.get_iptc_tags():
        return None
    if _data_type[tag] == 'string':
        return '; '.join(map(_decode_string, md.get_tag_multiple(tag)))
    elif _data_type[tag] == 'multi_string':
        return list(map(_decode_string, md.get_tag_multiple(tag)))
    else:
        raise RuntimeError('Cannot read tag ' + tag)
    return result

def read_xmp(md, tag):
    if _data_type[tag] == 'ignore':
        return None
    if _data_type[tag] == 'latlon':
        lat_tag = tag
        lon_tag = lat_tag.replace('Latitude', 'Longitude')
        parts = []
        for sub_tag in (lat_tag, lon_tag):
            if sub_tag not in md.get_xmp_tags():
                return None
            parts.append(md.get_tag_multiple(sub_tag)[0])
        return LatLon(LatLon.from_xmp_part(parts[0]),
                      LatLon.from_xmp_part(parts[1]))
    if tag not in md.get_xmp_tags():
        return None
    value_strings = md.get_tag_multiple(tag)
    if not value_strings:
        return None
    if _data_type[tag] == 'int':
        return value_strings[0]
    elif _data_type[tag] == 'APEX_aperture':
        return math.sqrt(2.0 ** Fraction(value_strings[0]))
    elif _data_type[tag] == 'rational':
        return value_strings[0]
    elif _data_type[tag] == 'string':
        if not isinstance(value_strings[0], six.text_type):
            value_strings = [x.decode('utf_8') for x in value_strings]
        return '; '.join(value_strings)
    elif _data_type[tag] == 'multi_string':
        if not isinstance(value_strings[0], six.text_type):
            value_strings = [x.decode('utf_8') for x in value_strings]
        return list(value_strings)
    elif _data_type[tag] == 'datetime':
        string_value = value_strings[0]
        # remove any time zone info
        if string_value.count(':') >= 2:
            string_value = string_value[:19]
        else:
            string_value = string_value[:16]
        # extend short strings to include all info
        string_value += '0001-01-01T00:00:00'[len(string_value):]
        # convert to datetime
        return datetime.strptime(string_value, '%Y-%m-%dT%H:%M:%S')
    else:
        raise RuntimeError('Cannot read tag ' + tag)
    return result

def write_exif(md, tag, value):
    if _data_type[tag] == 'latlon':
        lat_tag = tag
        lon_tag = lat_tag.replace('Latitude', 'Longitude')
        tag_list = (lat_tag, lat_tag + 'Ref', lon_tag, lon_tag + 'Ref')
        if value is None:
            for sub_tag in tag_list:
                md.clear_tag(sub_tag)
            return
        for sub_value, sub_tag in zip(value.to_exif(), tag_list):
            md.set_tag_string(sub_tag, sub_value)
        return
    if value is None:
        md.clear_tag(tag)
    elif _data_type[tag] == 'int':
        md.set_tag_string(tag, '{:d}'.format(value))
    elif _data_type[tag] == 'rational':
        md.set_tag_string(
            tag, '{:d}/{:d}'.format(value.numerator, value.denominator))
    elif _data_type[tag] == 'lensspec':
        md.set_tag_string(tag, ' '.join(['{:d}/{:d}'.format(
            x.numerator, x.denominator) for x in value.members()]))
    elif _data_type[tag] == 'string':
        md.set_tag_string(tag, _encode_string(value))
    elif _data_type[tag] == 'multi_string':
        md.set_tag_string(tag, _encode_string(';'.join(value)))
    elif _data_type[tag] == 'datetime':
        md.set_tag_string(tag, value.strftime('%Y:%m:%d %H:%M:%S'))
    else:
        raise RuntimeError('Cannot write tag ' + tag)

def write_iptc(md, tag, value):
    if _data_type[tag] == 'datetime':
        date_tag = tag
        time_tag = date_tag.replace('Date', 'Time')
        if value is None:
            md.clear_tag(date_tag)
            md.clear_tag(time_tag)
            return
        md.set_tag_multiple(date_tag, [value.strftime('%Y-%m-%d')])
        md.set_tag_multiple(time_tag, [value.strftime('%H:%M:%S')])
    if value is None:
        md.clear_tag(tag)
    elif _data_type[tag] == 'string':
        md.set_tag_multiple(tag, [_encode_string(value, _max_bytes[tag])])
    elif _data_type[tag] == 'multi_string':
        md.set_tag_multiple(
            tag, [_encode_string(x, _max_bytes[tag]) for x in value])
    else:
        raise RuntimeError('Cannot write tag ' + tag)

def write_xmp(md, tag, value):
    if value is None:
        if _data_type[tag] == 'latlon':
            lat_tag = tag
            lon_tag = lat_tag.replace('Latitude', 'Longitude')
            for sub_tag in (lat_tag, lon_tag):
                md.clear_tag(sub_tag)
        else:
            md.clear_tag(tag)
    elif _data_type[tag] == 'string':
        md.set_tag_multiple(tag, [value])
    elif _data_type[tag] == 'multi_string':
        md.set_tag_multiple(tag, value)
    elif _data_type[tag] == 'datetime':
        md.set_tag_multiple(tag, [value.strftime('%Y-%m-%dT%H:%M:%S')])
    else:
        raise RuntimeError('Cannot write tag ' + tag)

def sanitise(name, value):
    # convert value if required and clean it up
    if value in (None, '', []):
        return None
    if name in ('aperture', 'focal_length'):
        # single Fraction
        if not isinstance(value, Fraction):
            value = Fraction(value).limit_denominator(1000000)
        return value
    if name in ('copyright', 'description', 'lens_make', 'lens_model',
                'lens_serial', 'software', 'title'):
        # single string
        value = value.strip()
        if value:
            return value
        return None
    if name in ('date_digitised', 'date_modified', 'date_taken'):
        # single datetime
        return value
    if name in ('creator', 'keywords'):
        # list of strings
        if isinstance(value, six.string_types):
            value = value.split(';')
        value = list(filter(bool, [x.strip() for x in value]))
        if value:
            return value
        return None
    if name in ('latlong',):
        if isinstance(value, six.string_types):
            value = LatLon.from_string(value)
        elif isinstance(value, (list, tuple)):
            value = LatLon(*value)
        return value
    if name in ('lens_spec',):
        if isinstance(value, six.string_types):
            value = LensSpec.from_string(value)
        elif isinstance(value, (list, tuple)):
            value = LensSpec(*value)
        return value
    if name in ('orientation',):
        # single integer
        if not isinstance(value, int):
            value = int(value)
        return value
    return value

class Metadata(QtCore.QObject):
    # mapping of preferred tags to Photini data fields
    _primary_tags = {
        'aperture'       : {'Exif' : 'Exif.Photo.FNumber'},
        'copyright'      : {'Exif' : 'Exif.Image.Copyright',
                            'Xmp'  : 'Xmp.dc.rights',
                            'Iptc' : 'Iptc.Application2.Copyright'},
        'creator'        : {'Exif' : 'Exif.Image.Artist',
                            'Xmp'  : 'Xmp.dc.creator',
                            'Iptc' : 'Iptc.Application2.Byline'},
        'date_digitised' : {'Exif' : 'Exif.Photo.DateTimeDigitized',
                            'Xmp'  : 'Xmp.xmp.CreateDate',
                            'Iptc' : 'Iptc.Application2.DigitizationDate'},
        'date_modified'  : {'Exif' : 'Exif.Image.DateTime',
                            'Xmp'  : 'Xmp.xmp.ModifyDate'},
        'date_taken'     : {'Exif' : 'Exif.Photo.DateTimeOriginal',
                            'Xmp'  : 'Xmp.photoshop.DateCreated',
                            'Iptc' : 'Iptc.Application2.DateCreated'},
        'description'    : {'Exif' : 'Exif.Image.ImageDescription',
                            'Xmp'  : 'Xmp.dc.description',
                            'Iptc' : 'Iptc.Application2.Caption'},
        'focal_length'   : {'Exif' : 'Exif.Photo.FocalLength'},
        'keywords'       : {'Xmp'  : 'Xmp.dc.subject',
                            'Iptc' : 'Iptc.Application2.Keywords'},
        'latlong'        : {'Exif' : 'Exif.GPSInfo.GPSLatitude'},
        'lens_make'      : {'Exif' : 'Exif.Photo.LensMake'},
        'lens_model'     : {'Exif' : 'Exif.Photo.LensModel'},
        'lens_serial'    : {'Exif' : 'Exif.Photo.LensSerialNumber'},
        'lens_spec'      : {'Exif' : 'Exif.Photo.LensSpecification'},
        'orientation'    : {'Exif' : 'Exif.Image.Orientation'},
        'software'       : {'Exif' : 'Exif.Image.ProcessingSoftware'},
        'title'          : {'Xmp'  : 'Xmp.dc.title',
                            'Iptc' : 'Iptc.Application2.ObjectName'},
        }
    # mapping of duplicate tags to Photini data fields
    # data in these is merged in when data is read
    # they get deleted when data is written
    _secondary_tags = {
        'aperture'       : {'Exif' : ('Exif.Image.FNumber',
                                      'Exif.Image.ApertureValue',
                                      'Exif.Photo.ApertureValue',),
                            'Xmp'  : ('Xmp.exif.FNumber',
                                      'Xmp.exif.ApertureValue')},
        'copyright'      : {'Xmp'  : ('Xmp.tiff.Copyright',)},
        'creator'        : {'Xmp'  : ('Xmp.tiff.Artist',)},
        'date_digitised' : {'Xmp'  : ('Xmp.exif.DateTimeDigitized',)},
        'date_modified'  : {'Xmp'  : ('Xmp.tiff.DateTime',)},
        'date_taken'     : {'Exif' : ('Exif.Image.DateTimeOriginal',),
                            'Xmp'  : ('Xmp.exif.DateTimeOriginal',)},
        'description'    : {'Xmp'  : ('Xmp.tiff.ImageDescription',)},
        'focal_length'   : {'Exif' : ('Exif.Image.FocalLength',
                                      'Exif.Photo.FocalLengthIn35mmFilm',),
                            'Xmp'  : ('Xmp.exif.FocalLength',
                                      'Xmp.exif.FocalLengthIn35mmFilm',)},
        'keywords'       : {},
        'latlong'        : {'Xmp'  : ('Xmp.exif.GPSLatitude',)},
        'lens_make'      : {},
        'lens_model'     : {'Exif' : ('Exif.Canon.LensModel',
                                      'Exif.CanonCs.LensType',)},
        'lens_serial'    : {},
        'lens_spec'      : {'Exif' : ('Exif.CanonCs.Lens',
                                      'Exif.CanonCs.MaxAperture',
                                      'Exif.CanonCs.MinAperture',
                                      'Exif.CanonCs.ShortFocal')},
        'orientation'    : {'Xmp'  : ('Xmp.tiff.Orientation',)},
        'software'       : {},
        'title'          : {'Iptc' : ('Iptc.Application2.Headline',)},
        }
    def __init__(self, path, parent=None):
        QtCore.QObject.__init__(self, parent)
        self.logger = logging.getLogger(self.__class__.__name__)
        # create metadata handlers for image file and/or sidecar
        self._path = path
        self._sc_path = self._find_side_car(path)
        if self._sc_path:
            self._sc = MetadataHandler(self._sc_path)
        else:
            self._sc = None
        try:
            self._if = MetadataHandler(path)
        except Exception:
            self._if = None
            if not self._sc:
                self.create_side_car()
        self._unsaved = False
        self._value_cache = {}

    def _find_side_car(self, path):
        for base in (os.path.splitext(path)[0], path):
            for ext in ('.xmp', '.XMP'):
                result = base + ext
                if os.path.exists(result):
                    return result
        return None

    def create_side_car(self):
        self._sc_path = self._path + '.xmp'
        with open(self._sc_path, 'w') as of:
            of.write('<x:xmpmeta x:xmptk="XMP Core 4.4.0-Exiv2" ')
            of.write('xmlns:x="adobe:ns:meta/">\n')
            of.write('</x:xmpmeta>')
        self._sc = MetadataHandler(self._sc_path)
        if self._if:
            self._sc.copy(self._if, comment=False)

    def save(self, if_mode, sc_mode):
        if not self._unsaved:
            return
        self.set_item('software', 'Photini editor v{0}'.format(__version__))
        if self._if and sc_mode == 'delete' and self._sc:
            self._if.copy(self._sc, comment=False)
        OK = False
        if self._if and if_mode:
            OK = self._if.save()
        if sc_mode == 'delete' and self._sc and OK:
            os.unlink(self._sc_path)
            self._sc = None
        if sc_mode == 'auto' and not self._sc and not OK:
            self.create_side_car()
        if sc_mode == 'always' and not self._sc:
            self.create_side_car()
        if self._sc:
            OK = self._sc.save()
        self._set_unsaved(not OK)

    # tag lists: merge tags from sidecar and image file
    def get_exif_tags(self):
        result = []
        if self._if:
            result = self._if.get_exif_tags()
        if self._sc:
            for tag in self._sc.get_exif_tags():
                if tag not in result:
                    result.append(tag)
        return result

    def get_iptc_tags(self):
        result = []
        if self._if:
            result = self._if.get_iptc_tags()
        if self._sc:
            for tag in self._sc.get_iptc_tags():
                if tag not in result:
                    result.append(tag)
        return result

    def get_xmp_tags(self):
        result = []
        if self._if:
            result = self._if.get_xmp_tags()
        if self._sc:
            for tag in self._sc.get_xmp_tags():
                if tag not in result:
                    result.append(tag)
        return result

    # getters: use sidecar if tag is present, otherwise use image file
    def get_tag_string(self, tag):
        if self._sc and tag in self._sc.get_tags():
            return self._sc.get_tag_string(tag)
        if self._if:
            return self._if.get_tag_string(tag)
        return None

    def get_tag_multiple(self, tag):
        if self._sc and tag in self._sc.get_tags():
            return self._sc.get_tag_multiple(tag)
        if self._if:
            return self._if.get_tag_multiple(tag)
        return None

    # setters: set in both sidecar and image file
    def set_tag_string(self, tag, value):
        if self._sc:
            self._sc.set_tag_string(tag, value)
        if self._if:
            self._if.set_tag_string(tag, value)

    def set_tag_multiple(self, tag, value):
        if self._sc:
            self._sc.set_tag_multiple(tag, value)
        if self._if:
            self._if.set_tag_multiple(tag, value)

    def clear_tag(self, tag):
        if self._sc:
            self._sc.clear_tag(tag)
        if self._if:
            self._if.clear_tag(tag)

    def get_tags(self):
        return self.get_exif_tags() + self.get_iptc_tags() + self.get_xmp_tags()

    def _get_value(self, name, family, tag):
        if tag not in _data_type:
            raise RuntimeError('Cannot read tag ' + tag)
        if family == 'Exif':
            value = read_exif(self, tag)
        elif family == 'Iptc':
            value = read_iptc(self, tag)
        else:
            value = read_xmp(self, tag)
        return sanitise(name, value)

    def __getattr__(self, name):
        if name not in self._primary_tags:
            return super(Metadata, self).__getattr__(name)
        if name in self._value_cache:
            return self._value_cache[name]
        # get values from all 3 families, using first tag in list that has data
        value = {'Exif': None, 'Iptc': None, 'Xmp': None}
        for family in self._primary_tags[name]:
            try:
                value[family] = self._get_value(
                    name, family, self._primary_tags[name][family])
            except Exception as ex:
                self.logger.exception(ex)
        # merge conflicting data from secondary tags
        for family in self._secondary_tags[name]:
            for tag in self._secondary_tags[name][family]:
                try:
                    new_value = self._get_value(name, family, tag)
                except Exception as ex:
                    self.logger.exception(ex)
                    continue
                if new_value is None:
                    continue
                elif value[family] is None:
                    value[family] = new_value
                elif new_value == value[family]:
                    continue
                elif isinstance(value[family], six.string_types):
                    if new_value not in value[family]:
                        self.logger.warning('merging %s into %s', tag, name)
                        value[family] += ' // ' + new_value
                elif isinstance(value[family], list):
                    if new_value not in value[family]:
                        self.logger.warning('merging %s into %s', tag, name)
                        value[family] += new_value
                else:
                    self.logger.warning(
                        'ignoring conflicting data %s from tag %s',
                        str(new_value), tag)
        # choose preferred family
        if value['Exif'] is not None:
            preference = 'Exif'
        elif value['Xmp'] is not None:
            preference = 'Xmp'
        else:
            preference = 'Iptc'
        # merge in non-matching data so user can review it
        result = value[preference]
        for family in ('Exif', 'Xmp', 'Iptc'):
            if value[family] in (result, None):
                continue
            if isinstance(result, six.string_types):
                if value[family] not in result:
                    self.logger.warning('merging %s data into %s', family, name)
                    result += ' // ' + value[family]
            elif isinstance(result, list):
                if value[family] not in result:
                    self.logger.warning('merging %s data into %s', family, name)
                    result += value[family]
            else:
                self.logger.warning(
                    'ignoring conflicting %s data %s from %s',
                    name, str(value[family]), family)
        self._value_cache[name] = result
        return result

    def set_item(self, name, value):
        value = sanitise(name, value)
        if getattr(self, name) == value:
            return
        self._value_cache[name] = value
        # write data to primary tags (iptc only if it already exists)
        for family in self._primary_tags[name]:
            tag = self._primary_tags[name][family]
            if tag not in _data_type:
                raise RuntimeError('Cannot write tag ' + tag)
            if family == 'Exif':
                write_exif(self, tag, value)
            elif family == 'Xmp':
                write_xmp(self, tag, value)
            elif tag in self.get_iptc_tags():
                write_iptc(self, tag, value)
        # delete secondary tags
        for family in self._secondary_tags[name]:
            for tag in self._secondary_tags[name][family]:
                if tag not in _data_type:
                    raise RuntimeError('Cannot clear tag ' + tag)
                if family == 'Exif':
                    write_exif(self, tag, None)
                elif family == 'Xmp':
                    write_xmp(self, tag, None)
                else:
                    write_iptc(self, tag, None)
        self._set_unsaved(True)

    def del_item(self, name):
        self.set_item(name, None)

    new_status = QtCore.pyqtSignal(bool)
    def _set_unsaved(self, status):
        self._unsaved = status
        self.new_status.emit(self._unsaved)

    def changed(self):
        return self._unsaved
