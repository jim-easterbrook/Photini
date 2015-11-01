# -*- coding: utf-8 -*-
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

import six

from .metadata_gexiv2 import MetadataHandler
from .pyqt import QtCore
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

class DateTime(object):
    # store date and time with "precision" to store how much is valid
    # tz_offset is stored in minutes
    def __init__(self, datetime, precision, tz_offset=None):
        self.datetime = datetime
        self.precision = precision
        self.tz_offset = tz_offset

    def __eq__(self, other):
        return isinstance(other, DateTime) and self.members() == other.members()

    def __ne__(self, other):
        return not isinstance(other, DateTime) or self.members() != other.members()

    def __str__(self):
        return self.to_ISO_8601()

    def members(self):
        return self.datetime, self.precision, self.tz_offset

    @classmethod
    def from_ISO_8601(cls, date_string, time_string):
        """Sufficiently general ISO 8601 parser.

        Inputs must be in "basic" format, i.e. no '-' or ':' separators.
        See https://en.wikipedia.org/wiki/ISO_8601

        """
        # separate time and timezone
        tz_offset = None
        if time_string:
            if time_string[-1] == 'Z':
                # time zone designator of Z
                time_string = time_string[:-1]
                zone_string = '0000'
                zone_sign = '+'
            else:
                time_string, zone_sign, zone_string = time_string.partition('+')
                if not zone_string:
                    time_string, zone_sign, zone_string = time_string.partition('-')
            # compute tz_offset
            if zone_string:
                zone_string += '  00'[len(zone_string):]
                tz_offset = (int(zone_string[:2]) * 60) + int(zone_string[2:])
                if zone_sign == '-':
                    tz_offset = -tz_offset
        datetime_string = date_string + time_string
        precision = min((len(datetime_string) - 2) // 2, 6)
        if precision <= 0:
            return None
        if precision == 6 and datetime_string.count('.') > 0:
            precision = 7
        fmt = ''.join(cls.basic_fmt[:precision])
        return cls(datetime.strptime(datetime_string, fmt), precision, tz_offset)

    basic_fmt    = ('%Y',  '%m',  '%d',  '%H',  '%M',  '%S', '.%f')
    extended_fmt = ('%Y', '-%m', '-%d', 'T%H', ':%M', ':%S', '.%f')

    def to_ISO_8601(self, basic=False, precision=None, time_zone=True):
        if precision is None:
            precision = self.precision
        if basic:
            fmt = ''.join(self.basic_fmt[:precision])
        else:
            fmt = ''.join(self.extended_fmt[:precision])
        datetime_string = self.datetime.strftime(fmt)
        if precision > 3 and time_zone and self.tz_offset is not None:
            return datetime_string + self.tz_string(basic=basic)
        return datetime_string

    def tz_string(self, basic=False):
        if self.tz_offset is None:
            return ''
        minutes = self.tz_offset
        if minutes >= 0:
            sign_string = '+'
        else:
            sign_string = '-'
            minutes = -minutes
        if basic:
            fmt = '{}{:02d}{:02d}'
        else:
            fmt = '{}{:02d}:{:02d}'
        return fmt.format(sign_string, minutes // 60, minutes % 60)

    # Exif datetime replaces missing values with spaces, keeping the
    # colon separators and the overall string length. See
    # http://www.awaresystems.be/imaging/tiff/tifftags/privateifd/exif/datetimeoriginal.html
    @classmethod
    def from_exif(cls, datetime_string, sub_sec_string):
        # separate date & time and remove separators
        date_string = datetime_string[:10].replace(':', '')
        time_string = datetime_string[11:].replace(':', '')
        # truncate if any missing values
        space_pos = date_string.find(' ')
        if space_pos >= 0:
            date_string = date_string[:space_pos]
            time_string = ''
        else:
            space_pos = time_string.find(' ')
            if space_pos >= 0:
                time_string = time_string[:space_pos]
            elif sub_sec_string:
                time_string += '.' + sub_sec_string
        return cls.from_ISO_8601(date_string, time_string)

    def to_exif(self):
        datetime_string, sep, sub_sec_string = self.to_ISO_8601(
            time_zone=False).partition('.')
        if sub_sec_string == '':
            sub_sec_string = None
        datetime_string = datetime_string.replace('-', ':').replace('T', ' ')
        # add spaces for any missing values
        #                   YYYY mm dd HH MM SS
        datetime_string += '    :  :     :  :  '[len(datetime_string):]
        return datetime_string, sub_sec_string

    # IPTC date & time should have no separators and be 8 and 11 chars
    # respectively (time includes time zone offset). I suspect the exiv2
    # library is adding separators on read and time zone on write, but
    # am not sure.

    # The date (but not time) can have missing values represented by 00
    # according to
    # https://de.wikipedia.org/wiki/IPTC-IIM-Standard#IPTC-Felder
    @classmethod
    def from_iptc(cls, date_string, time_string):
        # remove separators (that shouldn't be there)
        date_string = date_string.replace('-', '')
        # remove missing values
        while len(date_string) > 4 and date_string[-2:] == '00':
            date_string = date_string[:-2]
        if date_string == '0000':
            date_string = ''
        # ignore time if date is not full precision
        if len(date_string) >= 8 and time_string:
            # remove separators (that shouldn't be there)
            time_string = time_string.replace(':', '')
        else:
            time_string = ''
        return cls.from_ISO_8601(date_string, time_string)

    def to_iptc(self):
        if self.precision <= 3:
            date_string = self.to_ISO_8601(basic=True)
            #               YYYYmmdd
            date_string += '00000000'[len(date_string):]
            return date_string, None
        datetime_string = self.to_ISO_8601(basic=True, precision=6)
        return datetime_string[:8], datetime_string[8:]

    # XMP uses extended ISO 8601, but the time cannot be hours only. See
    # p75 of
    # https://partners.adobe.com/public/developer/en/xmp/sdk/XMPspecification.pdf
    # According to p71, when converting Exif values with no time zone,
    # local time zone should be assumed. However, the MWG guidelines say
    # this must not be assumed to be the time zone where the photo is
    # processed. It also says the XMP standard has been revised to make
    # time zone information optional.
    @classmethod
    def from_xmp(cls, datetime_string):
        date_string, sep, time_string = datetime_string.partition('T')
        return cls.from_ISO_8601(
            date_string.replace('-', ''), time_string.replace(':', ''))

    def to_xmp(self):
        precision = self.precision
        if precision == 4:
            precision = 5
        return self.to_ISO_8601(precision=precision)

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
    'Exif.Image.Model'                   : 'string',
    'Exif.Image.Orientation'             : 'int',
    'Exif.Image.ProcessingSoftware'      : 'string',
    'Exif.Image.UniqueCameraModel'       : 'string',
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
    'Iptc.Application2.Program'          : 'string',
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
    'Iptc.Application2.Program'          :   32,
    'Iptc.Application2.ProgramVersion'   :   10,
    }

def sanitise(name, value):
    # convert value if required and clean it up
    if value in (None, '', []):
        return None
    if name in ('aperture', 'focal_length'):
        # single Fraction
        if not isinstance(value, Fraction):
            value = Fraction(value).limit_denominator(1000000)
        return value
    if name in ('camera_model', 'copyright', 'description',
                'lens_make', 'lens_model', 'lens_serial', 'software', 'title'):
        # single string
        value = value.strip()
        if value:
            return value
        return None
    if name in ('date_digitised', 'date_modified', 'date_taken'):
        if isinstance(value, (list, tuple)):
            value = DateTime(*value)
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
        'camera_model'   : {'Exif' : 'Exif.Image.Model'},
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
        'software'       : {'Exif' : 'Exif.Image.ProcessingSoftware',
                            'Iptc' : 'Iptc.Application2.Program'},
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
        'camera_model'   : {'Exif' : ('Exif.Image.UniqueCameraModel',)},
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
    def __init__(self, path, image_data, parent=None):
        super(Metadata, self).__init__(parent)
        self.logger = logging.getLogger(self.__class__.__name__)
        # create metadata handlers for image file and/or sidecar
        self._path = path
        self._sc_path = self._find_side_car(path)
        if self._sc_path:
            self._sc = MetadataHandler(self._sc_path)
        else:
            self._sc = None
        try:
            self._if = MetadataHandler(path, image_data)
        except Exception:
            self._if = None
            if not self._sc:
                self.create_side_car()
        self._unsaved = False

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

    def save(self, if_mode, sc_mode, force_iptc):
        if not self._unsaved:
            return
        self.software = 'Photini editor v' + __version__
        save_iptc = force_iptc or self.get_iptc_tags()
        for name in self._primary_tags:
            value = getattr(self, name)
            # write data to primary tags
            for family in self._primary_tags[name]:
                tag = self._primary_tags[name][family]
                if tag not in _data_type:
                    raise RuntimeError('Cannot write tag ' + tag)
                if family == 'Exif':
                    self._write_exif(tag, value)
                elif family == 'Xmp':
                    self._write_xmp(tag, value)
                elif save_iptc:
                    self._write_iptc(tag, value)
            # delete secondary tags
            for family in self._secondary_tags[name]:
                for tag in self._secondary_tags[name][family]:
                    if tag not in _data_type:
                        raise RuntimeError('Cannot clear tag ' + tag)
                    if family == 'Exif':
                        self._write_exif(tag, None)
                    elif family == 'Xmp':
                        self._write_xmp(tag, None)
                    else:
                        self._write_iptc(tag, None)
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

    def _read_exif(self, tag):
        if _data_type[tag] == 'ignore':
            return None
        if _data_type[tag] == 'latlon':
            lat_tag = tag
            lon_tag = lat_tag.replace('Latitude', 'Longitude')
            parts = []
            for sub_tag in (lat_tag, lat_tag + 'Ref', lon_tag, lon_tag + 'Ref'):
                if sub_tag not in self.get_exif_tags():
                    return None
                parts.append(self.get_tag_string(sub_tag))
            return LatLon(LatLon.from_exif_part(parts[0], parts[1]),
                          LatLon.from_exif_part(parts[2], parts[3]))
        if tag not in self.get_exif_tags():
            return None
        value_string = self.get_tag_string(tag)
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
            # Exif.Photo.SubSecXXX can be used with
            # Exif.Photo.DateTimeXXX or Exif.Image.DataTimeXXX
            sub_sec_tag = tag.replace('DateTime', 'SubSecTime')
            sub_sec_tag = sub_sec_tag.replace('Image', 'Photo')
            if sub_sec_tag in self.get_exif_tags():
                sub_sec_string = self.get_tag_string(sub_sec_tag)
            else:
                sub_sec_string = None
            return DateTime.from_exif(value_string, sub_sec_string)
        elif _data_type[tag] == 'lensspec':
            return LensSpec(*value_string.split())
        raise RuntimeError('Cannot read tag ' + tag)

    def _read_iptc(self, tag):
        if _data_type[tag] == 'datetime':
            date_tag = tag
            time_tag = date_tag.replace('Date', 'Time')
            if date_tag in self.get_iptc_tags():
                date_string = self.get_tag_multiple(date_tag)[0]
            else:
                date_string = None
            if time_tag in self.get_iptc_tags():
                time_string = self.get_tag_multiple(time_tag)[0]
            else:
                time_string = None
            if date_string:
                return DateTime.from_iptc(date_string, time_string)
            return None
        if tag not in self.get_iptc_tags():
            return None
        if tag == 'Iptc.Application2.Program':
            result = _decode_string(self.get_tag_multiple(tag)[0])
            version_tag = tag + 'Version'
            if version_tag in self.get_iptc_tags():
                result += (' v' +
                           _decode_string(self.get_tag_multiple(version_tag)[0]))
            return result
        elif _data_type[tag] == 'string':
            return '; '.join(map(_decode_string, self.get_tag_multiple(tag)))
        elif _data_type[tag] == 'multi_string':
            return list(map(_decode_string, self.get_tag_multiple(tag)))
        raise RuntimeError('Cannot read tag ' + tag)

    def _read_xmp(self, tag):
        if _data_type[tag] == 'ignore':
            return None
        if _data_type[tag] == 'latlon':
            lat_tag = tag
            lon_tag = lat_tag.replace('Latitude', 'Longitude')
            parts = []
            for sub_tag in (lat_tag, lon_tag):
                if sub_tag not in self.get_xmp_tags():
                    return None
                parts.append(self.get_tag_multiple(sub_tag)[0])
            return LatLon(LatLon.from_xmp_part(parts[0]),
                          LatLon.from_xmp_part(parts[1]))
        if tag not in self.get_xmp_tags():
            return None
        value_strings = self.get_tag_multiple(tag)
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
            return DateTime.from_xmp(value_strings[0])
        raise RuntimeError('Cannot read tag ' + tag)

    def _get_value(self, name, family, tag):
        if tag not in _data_type:
            raise RuntimeError('Cannot read tag ' + tag)
        if family == 'Exif':
            value = self._read_exif(tag)
        elif family == 'Iptc':
            value = self._read_iptc(tag)
        else:
            value = self._read_xmp(tag)
        return sanitise(name, value)

    def __getattr__(self, name):
        if name not in self._primary_tags:
            return super(Metadata, self).__getattr__(name)
        # get values from all 3 families
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
                        self.logger.warning(
                            '%s: merging %s into %s',
                            os.path.basename(self._path), tag, name)
                        value[family] += ' // ' + new_value
                elif isinstance(value[family], list):
                    if new_value not in value[family]:
                        self.logger.warning(
                            '%s: merging %s into %s',
                            os.path.basename(self._path), tag, name)
                        value[family] += new_value
                elif (isinstance(value[family], DateTime) and
                      new_value.precision > value[family].precision):
                    self.logger.warning(
                        '%s: using %s value "%s", ignoring %s value "%s"',
                        os.path.basename(self._path),
                        tag, str(new_value),
                        self._primary_tags[name][family], str(value[family]))
                    value[family] = new_value
                else:
                    self.logger.warning(
                        '%s: using %s value "%s", ignoring %s value "%s"',
                        os.path.basename(self._path),
                        self._primary_tags[name][family], str(value[family]),
                        tag, str(new_value))
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
            other = value[family]
            if other in (result, None):
                continue
            if isinstance(result, six.string_types):
                if other not in result:
                    self.logger.warning(
                        '%s: merging %s data into %s:%s',
                        os.path.basename(self._path), family, preference, name)
                    result += ' // ' + other
            elif isinstance(result, list):
                if other not in result:
                    self.logger.warning(
                        '%s: merging %s data into %s:%s',
                        os.path.basename(self._path), family, preference, name)
                    result += other
            elif (isinstance(other, DateTime) and
                  other.datetime == result.datetime):
                if result.tz_offset is None and family != 'Iptc':
                    result.tz_offset = other.tz_offset
            else:
                self.logger.warning(
                    '%s: %s: using %s value "%s", ignoring %s value "%s"',
                    os.path.basename(self._path),
                    name, preference, str(result), family, str(other))
        # add value to object attributes so __getattr__ doesn't get
        # called again
        super(Metadata, self).__setattr__(name, result)
        return result

    def _write_exif(self, tag, value):
        if _data_type[tag] == 'latlon':
            lat_tag = tag
            lon_tag = lat_tag.replace('Latitude', 'Longitude')
            tag_list = (lat_tag, lat_tag + 'Ref', lon_tag, lon_tag + 'Ref')
            if value is None:
                for sub_tag in tag_list:
                    self.clear_tag(sub_tag)
                return
            for sub_value, sub_tag in zip(value.to_exif(), tag_list):
                self.set_tag_string(sub_tag, sub_value)
            return
        if _data_type[tag] == 'datetime':
            # don't clear sub_sec value when writing secondary tags
            if tag == 'Exif.Image.DateTime':
                sub_sec_tag = 'Exif.Photo.SubSecTime'
            elif tag.startswith('Exif.Photo'):
                sub_sec_tag = tag.replace('DateTime', 'SubSecTime')
            else:
                sub_sec_tag = None
            if value is None:
                self.clear_tag(tag)
                if sub_sec_tag:
                    self.clear_tag(sub_sec_tag)
                return
            datetime_string, sub_sec_string = value.to_exif()
            self.set_tag_string(tag, datetime_string)
            if sub_sec_tag is None:
                pass
            elif sub_sec_string is None:
                self.clear_tag(sub_sec_tag)
            else:
                self.set_tag_string(sub_sec_tag, sub_sec_string)
            return
        if value is None:
            self.clear_tag(tag)
        elif _data_type[tag] == 'int':
            self.set_tag_string(tag, '{:d}'.format(value))
        elif _data_type[tag] == 'rational':
            self.set_tag_string(
                tag, '{:d}/{:d}'.format(value.numerator, value.denominator))
        elif _data_type[tag] == 'lensspec':
            self.set_tag_string(tag, ' '.join(['{:d}/{:d}'.format(
                x.numerator, x.denominator) for x in value.members()]))
        elif _data_type[tag] == 'string':
            self.set_tag_string(tag, _encode_string(value))
        elif _data_type[tag] == 'multi_string':
            self.set_tag_string(tag, _encode_string(';'.join(value)))
        else:
            raise RuntimeError('Cannot write tag ' + tag)

    def _write_iptc(self, tag, value):
        if _data_type[tag] == 'datetime':
            date_tag = tag
            time_tag = date_tag.replace('Date', 'Time')
            if value is None:
                self.clear_tag(date_tag)
                self.clear_tag(time_tag)
                return
            date_string, time_string = value.to_iptc()
            self.set_tag_multiple(date_tag, [date_string])
            if time_string:
                self.set_tag_multiple(time_tag, [time_string])
            else:
                self.clear_tag(time_tag)
            return
        if value is None:
            self.clear_tag(tag)
        elif tag == 'Iptc.Application2.Program':
            program, version = value.split(' v')
            self.set_tag_multiple(tag, [_encode_string(program, _max_bytes[tag])])
            tag += 'Version'
            self.set_tag_multiple(tag, [_encode_string(version, _max_bytes[tag])])
        elif _data_type[tag] == 'string':
            self.set_tag_multiple(tag, [_encode_string(value, _max_bytes[tag])])
        elif _data_type[tag] == 'multi_string':
            self.set_tag_multiple(
                tag, [_encode_string(x, _max_bytes[tag]) for x in value])
        else:
            raise RuntimeError('Cannot write tag ' + tag)

    def _write_xmp(self, tag, value):
        if value is None:
            if _data_type[tag] == 'latlon':
                lat_tag = tag
                lon_tag = lat_tag.replace('Latitude', 'Longitude')
                for sub_tag in (lat_tag, lon_tag):
                    self.clear_tag(sub_tag)
            else:
                self.clear_tag(tag)
        elif _data_type[tag] == 'string':
            self.set_tag_multiple(tag, [value])
        elif _data_type[tag] == 'multi_string':
            self.set_tag_multiple(tag, value)
        elif _data_type[tag] == 'datetime':
            self.set_tag_multiple(tag, [value.to_xmp()])
        else:
            raise RuntimeError('Cannot write tag ' + tag)

    def __setattr__(self, name, value):
        if name not in self._primary_tags:
            return super(Metadata, self).__setattr__(name, value)
        value = sanitise(name, value)
        if getattr(self, name) == value:
            return
        super(Metadata, self).__setattr__(name, value)
        self._set_unsaved(True)

    new_status = QtCore.pyqtSignal(bool)
    def _set_unsaved(self, status):
        self._unsaved = status
        self.new_status.emit(self._unsaved)

    def changed(self):
        return self._unsaved
