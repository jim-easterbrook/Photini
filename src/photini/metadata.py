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

from gi.repository import GObject, GExiv2
import six

from .pyqt import QtCore
from . import __version__

# pydoc gi.repository.GExiv2.Metadata is useful to see methods available

GExiv2.log_set_level(GExiv2.LogLevel.MUTE)

class MetadataValue(object):
    # base for classes that store a metadata value, e.g. a string, int
    # or latitude & longitude pair
    def __init__(self, value):
        assert(value is not None)
        self.value = value

    def __nonzero__(self):
        return bool(self.value)

    def __eq__(self, other):
        return isinstance(other, MetadataValue) and self.value == other.value

    def __ne__(self, other):
        return not isinstance(other, MetadataValue) or self.value != other.value

    def contains(self, other):
        return (not other) or (other.value == self.value)

    def merge(self, other, family=None):
        return False


class Ignore(MetadataValue):
    pass


class LatLon(MetadataValue):
    # simple class to store latitude and longitude
    def __init__(self, value):
        if isinstance(value, six.string_types):
            value = value.split(',')
        lat, lon = value
        super(LatLon, self).__init__({
            'lat' : round(float(lat), 6),
            'lon' : round(float(lon), 6),
            })

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

    @classmethod
    def from_exif(cls, lat_string, lat_ref, lon_string, lon_ref):
        return cls((cls.from_exif_part(lat_string, lat_ref),
                    cls.from_exif_part(lon_string, lon_ref)))

    def to_exif(self):
        result = []
        for value, sign_char in zip((self.value['lat'], self.value['lon']),
                                    ('NS', 'EW')):
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

    @classmethod
    def from_xmp(cls, lat_string, lon_string):
        return cls((cls.from_xmp_part(lat_string),
                    cls.from_xmp_part(lon_string)))

    def __str__(self):
        return '{:.6f}, {:.6f}'.format(self.value['lat'], self.value['lon'])


class LensSpec(MetadataValue):
    # simple class to store lens "specificaton"
    def __init__(self, value, sep=None):
        if isinstance(value, six.string_types):
            value = value.split(sep)
        min_fl, max_fl, min_fl_fn, max_fl_fn = value
        super(LensSpec, self).__init__({
            'min_fl'    : Fraction(min_fl).limit_denominator(1000000),
            'max_fl'    : Fraction(max_fl).limit_denominator(1000000),
            'min_fl_fn' : Fraction(min_fl_fn).limit_denominator(1000000),
            'max_fl_fn' : Fraction(max_fl_fn).limit_denominator(1000000),
            })

    def __str__(self):
        return '{:g}, {:g}, {:g}, {:g}'.format(
            float(self.value['min_fl']),    float(self.value['max_fl']),
            float(self.value['min_fl_fn']), float(self.value['max_fl_fn']))

    def to_exif(self):
        return ' '.join(
            ['{:d}/{:d}'.format(x.numerator, x.denominator) for x in (
                self.value['min_fl'], self.value['max_fl'],
                self.value['min_fl_fn'], self.value['max_fl_fn'])])


class DateTime(MetadataValue):
    # store date and time with "precision" to store how much is valid
    # tz_offset is stored in minutes
    def __init__(self, datetime, precision, tz_offset=None):
        super(DateTime, self).__init__({
            'datetime'  : datetime,
            'precision' : precision,
            'tz_offset' : tz_offset,
            })

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
            precision = self.value['precision']
        if basic:
            fmt = ''.join(self.basic_fmt[:precision])
        else:
            fmt = ''.join(self.extended_fmt[:precision])
        datetime_string = self.value['datetime'].strftime(fmt)
        if precision > 3 and time_zone and self.value['tz_offset'] is not None:
            return datetime_string + self.tz_string(basic=basic)
        return datetime_string

    def tz_string(self, basic=False):
        if self.value['tz_offset'] is None:
            return ''
        minutes = self.value['tz_offset']
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

    # Exif datetime replaces missing values with zeros, keeping the
    # colon separators and the overall string length.
    @classmethod
    def from_exif(cls, datetime_string, sub_sec_string):
        # separate date & time and remove separators
        date_string = datetime_string[:10].replace(':', '')
        time_string = datetime_string[11:].replace(':', '')
        # remove missing values
        while len(date_string) > 4 and date_string[-2:] == '00':
            date_string = date_string[:-2]
        if date_string == '0000':
            date_string = ''
        # ignore time if date is not full precision
        if len(date_string) < 8:
            time_string = ''
        elif sub_sec_string:
            time_string += '.' + sub_sec_string
        elif time_string == '000000':
            # probably a missing time
            time_string = ''
        return cls.from_ISO_8601(date_string, time_string)

    def to_exif(self):
        datetime_string, sep, sub_sec_string = self.to_ISO_8601(
            time_zone=False).partition('.')
        if sub_sec_string == '':
            sub_sec_string = None
        datetime_string = datetime_string.replace('-', ':').replace('T', ' ')
        # add zeros for any missing values
        #                   YYYY mm dd HH MM SS
        datetime_string += '0000:00:00 00:00:00'[len(datetime_string):]
        return datetime_string, sub_sec_string

    # IPTC date & time should have no separators and be 8 and 11 chars
    # respectively (time includes time zone offset). I suspect the exiv2
    # library is adding separators, but am not sure.

    # The date (and time?) can have missing values represented by 00
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
        if time_string[:6] == '000000':
            # probably a missing time
            time_string = ''
        return cls.from_ISO_8601(date_string, time_string)

    def to_iptc(self):
        if self.value['precision'] <= 3:
            date_string = self.to_ISO_8601()
            #               YYYY mm dd
            date_string += '0000-00-00'[len(date_string):]
            return date_string, None
        datetime_string = self.to_ISO_8601(precision=6)
        return datetime_string[:10], datetime_string[11:]

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
        precision = self.value['precision']
        if precision == 4:
            precision = 5
        return self.to_ISO_8601(precision=precision)

    def __str__(self):
        return self.to_ISO_8601()

    def contains(self, other):
        if (not other) or (other.value == self.value):
            return True
        if other.value['datetime'] != self.value['datetime']:
            return False
        if other.value['precision'] < self.value['precision']:
            return False
        return bool(other.value['tz_offset']) == bool(self.value['tz_offset'])

    def merge(self, other, family=None):
        result = False
        # some formats default to a higher precision
        if self.value['precision'] > other.value['precision']:
            self.value['precision'] = other.value['precision']
            result = True
        # don't trust IPTC time zone
        if self.value['tz_offset'] is None and family != 'Iptc':
            self.value['tz_offset'] = other.value['tz_offset']
            result = True
        return result


@six.python_2_unicode_compatible
class MultiString(MetadataValue):
    def __init__(self, value):
        if isinstance(value, six.string_types):
            value = value.split(';')
        value = list(filter(bool, [x.strip() for x in value]))
        super(MultiString, self).__init__(value)

    def __str__(self):
        return '; '.join(self.value)

    def contains(self, other):
        return (not other) or (not bool(
            [x for x in other.value if x not in self.value]))

    def merge(self, other, family=None):
        self.value += other.value
        return True


@six.python_2_unicode_compatible
class String(MetadataValue):
    def __init__(self, value):
        if isinstance(value, list):
            value = value[0]
        super(String, self).__init__(six.text_type(value).strip())

    def __str__(self):
        return self.value

    def contains(self, other):
        return (not other) or (other.value in self.value)

    def merge(self, other, family=None):
        self.value += ' // ' + other.value
        return True


class Software(String):
    def to_iptc(self):
        return self.value.split(' v')


class Int(MetadataValue):
    def __init__(self, value):
        super(Int, self).__init__(int(value))

    def __nonzero__(self):
        return self.value is not None

    def __str__(self):
        return '{:d}'.format(self.value)


class Rational(MetadataValue):
    def __init__(self, value):
        super(Rational, self).__init__(Fraction(value))

    def __nonzero__(self):
        return self.value is not None

    def __str__(self):
        return '{:g}'.format(float(self.value))


class APEXAperture(Rational):
    def __init__(self, value):
        super(APEXAperture, self).__init__(math.sqrt(2.0 ** Fraction(value)))


# type of each tag's data
_data_type = {
    'aperture'                           : Rational,
    'camera_model'                       : String,
    'copyright'                          : String,
    'creator'                            : MultiString,
    'date_digitised'                     : DateTime,
    'date_modified'                      : DateTime,
    'date_taken'                         : DateTime,
    'description'                        : String,
    'focal_length'                       : Rational,
    'keywords'                           : MultiString,
    'latlong'                            : LatLon,
    'lens_make'                          : String,
    'lens_model'                         : String,
    'lens_serial'                        : String,
    'lens_spec'                          : LensSpec,
    'orientation'                        : Int,
    'software'                           : Software,
    'title'                              : String,

    'Exif.Canon.LensModel'               : Ignore,
    'Exif.CanonCs.Lens'                  : Ignore,
    'Exif.CanonCs.LensType'              : Ignore,
    'Exif.CanonCs.MaxAperture'           : Ignore,
    'Exif.CanonCs.MinAperture'           : Ignore,
    'Exif.CanonCs.ShortFocal'            : Ignore,
    'Exif.GPSInfo.GPSLatitude'           : LatLon,
    'Exif.Image.ApertureValue'           : APEXAperture,
    'Exif.Image.Artist'                  : MultiString,
    'Exif.Image.Copyright'               : String,
    'Exif.Image.DateTime'                : DateTime,
    'Exif.Image.DateTimeOriginal'        : DateTime,
    'Exif.Image.FNumber'                 : Rational,
    'Exif.Image.FocalLength'             : Rational,
    'Exif.Image.ImageDescription'        : String,
    'Exif.Image.Model'                   : String,
    'Exif.Image.Orientation'             : Int,
    'Exif.Image.ProcessingSoftware'      : Software,
    'Exif.Image.UniqueCameraModel'       : String,
    'Exif.Photo.ApertureValue'           : APEXAperture,
    'Exif.Photo.DateTimeDigitized'       : DateTime,
    'Exif.Photo.DateTimeOriginal'        : DateTime,
    'Exif.Photo.FNumber'                 : Rational,
    'Exif.Photo.FocalLength'             : Rational,
    'Exif.Photo.FocalLengthIn35mmFilm'   : Ignore,
    'Exif.Photo.LensMake'                : String,
    'Exif.Photo.LensModel'               : String,
    'Exif.Photo.LensSerialNumber'        : String,
    'Exif.Photo.LensSpecification'       : LensSpec,
    'Iptc.Application2.Byline'           : MultiString,
    'Iptc.Application2.Caption'          : String,
    'Iptc.Application2.Copyright'        : String,
    'Iptc.Application2.DateCreated'      : DateTime,
    'Iptc.Application2.DigitizationDate' : DateTime,
    'Iptc.Application2.Headline'         : String,
    'Iptc.Application2.Keywords'         : MultiString,
    'Iptc.Application2.ObjectName'       : String,
    'Iptc.Application2.Program'          : Software,
    'Xmp.dc.creator'                     : MultiString,
    'Xmp.dc.description'                 : String,
    'Xmp.dc.rights'                      : String,
    'Xmp.dc.subject'                     : MultiString,
    'Xmp.dc.title'                       : String,
    'Xmp.photoshop.DateCreated'          : DateTime,
    'Xmp.exif.ApertureValue'             : APEXAperture,
    'Xmp.exif.DateTimeDigitized'         : DateTime,
    'Xmp.exif.DateTimeOriginal'          : DateTime,
    'Xmp.exif.FNumber'                   : Rational,
    'Xmp.exif.FocalLength'               : Rational,
    'Xmp.exif.FocalLengthIn35mmFilm'     : Ignore,
    'Xmp.exif.GPSLatitude'               : LatLon,
    'Xmp.tiff.Artist'                    : MultiString,
    'Xmp.tiff.Copyright'                 : String,
    'Xmp.tiff.DateTime'                  : DateTime,
    'Xmp.tiff.ImageDescription'          : String,
    'Xmp.tiff.Orientation'               : Int,
    'Xmp.xmp.CreateDate'                 : DateTime,
    'Xmp.xmp.ModifyDate'                 : DateTime,
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

_encodings = None

class MetadataHandler(GExiv2.Metadata):
    def __init__(self, path, image_data=None):
        super(MetadataHandler, self).__init__()
        self._logger = logging.getLogger(self.__class__.__name__)
        self._path = path
        if image_data:
            self.open_buf(image_data)
        else:
            self.open_path(self._path)

    def _decode_string(self, value):
        global _encodings
        if not value:
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

    def _encode_string(self, tag, value):
        result = value.encode('utf_8')
        if tag in _max_bytes:
            result = result[:_max_bytes[tag]]
        if six.PY3:
            result = result.decode('utf_8')
        return result


    def get_value(self, tag):
        # get value as our preferred data type
        exiv_type = MetadataHandler.get_tag_type(tag)
        if exiv_type in ('Ascii', 'XmpText'):
            result = self.get_tag_string_unicode(tag)
        elif exiv_type in ('Date', 'Rational', 'Short'):
            result = self.get_tag_string(tag)
        elif exiv_type in ('LangAlt', 'String', 'XmpBag', 'XmpSeq'):
            result = self.get_tag_multiple_unicode(tag)
        else:
            raise RuntimeError('Unknown tag type ' + exiv_type)
        if not result:
            return None
        if _data_type[tag] == DateTime:
            if MetadataHandler.is_exif_tag(tag):
                # Exif.Photo.SubSecXXX can be used with
                # Exif.Photo.DateTimeXXX or Exif.Image.DataTimeXXX
                sub_sec_tag = tag.replace('DateTime', 'SubSecTime')
                sub_sec_tag = sub_sec_tag.replace('Image', 'Photo')
                sub_sec_string = self.get_tag_string(sub_sec_tag)
                return DateTime.from_exif(result, sub_sec_string)
            if MetadataHandler.is_iptc_tag(tag):
                time_tag = tag.replace('Date', 'Time')
                time_string = self.get_tag_string(time_tag)
                return DateTime.from_iptc(result, time_string)
            return DateTime.from_xmp(result)
        if _data_type[tag] == LatLon:
            lon_tag = tag.replace('Latitude', 'Longitude')
            if MetadataHandler.is_exif_tag(tag):
                parts = [result]
                for sub_tag in (tag + 'Ref', lon_tag, lon_tag + 'Ref'):
                    if not self.has_tag(sub_tag):
                        return None
                    parts.append(self.get_tag_string(sub_tag))
                return LatLon.from_exif(*parts)
            if not self.has_tag(lon_tag):
                return None
            return LatLon.from_xmp(result, self.get_tag_string(lon_tag))
        if _data_type[tag] == Software and MetadataHandler.is_iptc_tag(tag):
            result = result[0]
            version_tag = tag + 'Version'
            if self.has_tag(version_tag):
                result += ' v' + self.get_tag_string(version_tag)
        return _data_type[tag](result)

    def set_value(self, tag, value):
        exiv_type = MetadataHandler.get_tag_type(tag)
        # do multi-tag items
        if _data_type[tag] == LatLon and MetadataHandler.is_exif_tag(tag):
            lon_tag = tag.replace('Latitude', 'Longitude')
            tag_list = (tag, tag + 'Ref', lon_tag, lon_tag + 'Ref')
            if not value:
                for sub_tag in tag_list:
                    self.clear_tag(sub_tag)
            else:
                for sub_value, sub_tag in zip(value.to_exif(), tag_list):
                    self.set_tag_string(sub_tag, sub_value)
            return
        if _data_type[tag] == DateTime and MetadataHandler.is_exif_tag(tag):
            # don't clear sub_sec value when writing secondary tags
            if tag == 'Exif.Image.DateTime':
                sub_sec_tag = 'Exif.Photo.SubSecTime'
            elif tag.startswith('Exif.Photo'):
                sub_sec_tag = tag.replace('DateTime', 'SubSecTime')
            else:
                sub_sec_tag = None
            if not value:
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
        if _data_type[tag] == DateTime and MetadataHandler.is_iptc_tag(tag):
            time_tag = tag.replace('Date', 'Time')
            if not value:
                self.clear_tag(tag)
                self.clear_tag(time_tag)
                return
            date_string, time_string = value.to_iptc()
            self.set_tag_string(tag, date_string)
            if time_string:
                self.set_tag_string(time_tag, time_string)
            else:
                self.clear_tag(time_tag)
            return
        if _data_type[tag] == Software and MetadataHandler.is_iptc_tag(tag):
            program, version = value.to_iptc()
            self.set_tag_string_unicode(tag, program)
            self.set_tag_string_unicode(tag + 'Version', version)
            return
        # do single tag items
        if not value:
            self.clear_tag(tag)
        elif _data_type[tag] == DateTime:
            self.set_tag_string(tag, value.to_xmp())
        elif _data_type[tag] == MultiString:
            if exiv_type in ('Ascii', 'XmpText'):
                self.set_tag_string_unicode(tag, ';'.join(value.value))
            else:
                self.set_tag_multiple_unicode(tag, value.value)
        elif _data_type[tag] == Rational and MetadataHandler.is_exif_tag(tag):
            self.set_tag_string(tag, '{:d}/{:d}'.format(
                value.value.numerator, value.value.denominator))
        elif _data_type[tag] == Int and MetadataHandler.is_exif_tag(tag):
            self.set_tag_string(tag, '{:d}'.format(value.value))
        elif _data_type[tag] == LensSpec and MetadataHandler.is_exif_tag(tag):
            self.set_tag_string(tag, value.to_exif())
        elif isinstance(value, String):
            self.set_tag_string_unicode(tag, six.text_type(value))
        else:
            raise RuntimeError('Cannot write tag ' + tag)

    def get_tag_string_unicode(self, tag):
        try:
            result = self.get_tag_string(tag)
            if six.PY2:
                result = self._decode_string(result)
        except UnicodeDecodeError as ex:
            self._logger.error(str(ex))
            return ''
        return result

    def set_tag_string_unicode(self, tag, value):
        self.set_tag_string(tag, self._encode_string(tag, value))

    def get_tag_multiple_unicode(self, tag):
        try:
            result = self.get_tag_multiple(tag)
            if six.PY2:
                result = map(self._decode_string, result)
        except UnicodeDecodeError as ex:
            self._logger.error(str(ex))
            return []
        return result

    def set_tag_multiple_unicode(self, tag, value):
        self.set_tag_multiple(tag, [self._encode_string(tag, x) for x in value])

    def save(self):
        try:
            self.save_file(self._path)
        except GObject.GError as ex:
            self._logger.exception(ex)
            return False
        return True

    def copy(self, other, exif=True, iptc=True, xmp=True, comment=True):
        # copy from other to self
        if exif:
            for tag in other.get_exif_tags():
                self.set_tag_string(
                    tag, other.get_tag_string(tag))
        if iptc:
            for tag in other.get_iptc_tags():
                self.set_tag_multiple(
                    tag, other.get_tag_multiple(tag))
        if xmp:
            for tag in other.get_xmp_tags():
                self.set_tag_multiple(
                    tag, other.get_tag_multiple(tag))
        if comment:
            value = other.get_comment()
            if value:
                self.set_comment(value)


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
        save_iptc = force_iptc or self.has_iptc()
        for name in self._primary_tags:
            value = getattr(self, name)
            # write data to primary tags
            for family in self._primary_tags[name]:
                tag = self._primary_tags[name][family]
                self.set_value(tag, value)
            # delete secondary tags
            for family in self._secondary_tags[name]:
                for tag in self._secondary_tags[name][family]:
                    self.set_value(tag, None)
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

    # getters: use sidecar if tag is present, otherwise use image file
    def get_value(self, tag):
        assert(tag in _data_type)
        if _data_type[tag] == Ignore:
            return None
        result = None
        if self._sc:
            result = self._sc.get_value(tag)
        if self._if and not result:
            result = self._if.get_value(tag)
        return result

    def has_iptc(self):
        if self._sc and self._sc.has_iptc():
            return True
        if self._if and self._if.has_iptc():
            return True
        return False

    # setters: set in both sidecar and image file
    def set_value(self, tag, value):
        assert(tag in _data_type)
        if self._sc:
            self._sc.set_value(tag, value)
        if self._if:
            self._if.set_value(tag, value)

    def __getattr__(self, name):
        if name not in self._primary_tags:
            return super(Metadata, self).__getattr__(name)
        # get values from all 3 families
        value = {'Exif': None, 'Iptc': None, 'Xmp': None}
        used_tag = {'Exif': None, 'Iptc': None, 'Xmp': None}
        for family in self._primary_tags[name]:
            tag = self._primary_tags[name][family]
            try:
                value[family] = self.get_value(tag)
                used_tag[family] = tag
            except Exception as ex:
                self.logger.exception(ex)
        # merge conflicting data from secondary tags
        for family in self._secondary_tags[name]:
            for tag in self._secondary_tags[name][family]:
                try:
                    new_value = self.get_value(tag)
                except Exception as ex:
                    self.logger.exception(ex)
                    continue
                if new_value is None:
                    continue
                elif value[family] is None:
                    value[family] = new_value
                    used_tag[family] = tag
                elif value[family].contains(new_value):
                    continue
                elif value[family].merge(new_value):
                    self.logger.warning(
                        '%s: merged %s into %s',
                        os.path.basename(self._path), tag, used_tag[family])
                else:
                    self.logger.warning(
                        '%s: using %s value "%s", ignoring %s value "%s"',
                        os.path.basename(self._path), used_tag[family],
                        str(value[family]), tag, str(new_value))
        # choose preferred family
        if value['Exif'] is not None:
            preference = 'Exif'
        elif value['Xmp'] is not None:
            preference = 'Xmp'
        else:
            preference = 'Iptc'
        # merge in non-matching data so user can review it
        result = value[preference]
        if result is not None:
            for family in ('Exif', 'Xmp', 'Iptc'):
                other = value[family]
                if result.contains(other):
                    continue
                elif result.merge(other, family):
                    self.logger.warning(
                        '%s: merged %s data into %s',
                        os.path.basename(self._path),
                        used_tag[family], used_tag[preference])
                else:
                    self.logger.warning(
                        '%s: using %s value "%s", ignoring %s value "%s"',
                        os.path.basename(self._path), used_tag[preference],
                        str(result), used_tag[family], str(other))
        # add value to object attributes so __getattr__ doesn't get
        # called again
        super(Metadata, self).__setattr__(name, result)
        return result

    def __setattr__(self, name, value):
        if name not in self._primary_tags:
            return super(Metadata, self).__setattr__(name, value)
        if value in (None, '', [], {}):
            value = None
        elif not isinstance(value, _data_type[name]):
            value = _data_type[name](value)
            if not value:
                value = None
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
