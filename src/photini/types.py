##  Photini - a simple photo metadata editor.
##  http://github.com/jim-easterbrook/Photini
##  Copyright (C) 2022-24  Jim Easterbrook  jim@jim-easterbrook.me.uk
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

import codecs
from datetime import datetime, timedelta
from fractions import Fraction
import logging
import math
import pprint
import re

from photini.cv import (image_region_roles, image_region_roles_idx,
                        image_region_types, image_region_types_idx)
from photini.exiv2 import MetadataHandler
from photini.pyqt import *
from photini.pyqt import qt_version_info, using_pyside

logger = logging.getLogger(__name__)

# photini.metadata imports these classes
__all__ = (
    'MD_Aperture', 'MD_CameraModel', 'MD_ContactInformation', 'MD_DateTime',
    'MD_Dimensions', 'MD_GPSinfo', 'MD_HierarchicalTags', 'MD_ImageRegion',
    'MD_Int', 'MD_Keywords', 'MD_LangAlt', 'MD_LensModel', 'MD_MultiLocation',
    'MD_MultiString', 'MD_Orientation', 'MD_Rating', 'MD_Rational', 'MD_Rights',
    'MD_SingleLocation', 'MD_Software', 'MD_String', 'MD_Thumbnail',
    'MD_Timezone', 'MD_VideoDuration', 'safe_fraction')


def safe_fraction(value, limit=True):
    # Avoid ZeroDivisionError when '0/0' used for zero values in Exif
    try:
        if isinstance(value, (list, tuple)):
            value = Fraction(*value)
        else:
            value = Fraction(value)
    except ZeroDivisionError:
        return Fraction(0.0)
    if limit:
        # round off excessively large denominators
        value = value.limit_denominator(1000000)
    return value


class MD_Value(object):
    # mixin for "metadata objects" - Python types with additional functionality
    _quiet = False

    @classmethod
    def from_ffmpeg(cls, file_value, tag):
        return cls(file_value)

    @classmethod
    def from_exiv2(cls, file_value, tag):
        return cls(file_value)

    def to_exiv2(self, tag):
        return {'Exif': self.to_exif,
                'Iptc': self.to_iptc,
                'Xmp': self.to_xmp}[tag.split('.')[0]]()

    def to_exif(self):
        return str(self)

    def to_iptc(self):
        return str(self)

    def to_xmp(self):
        return str(self)

    def compact_form(self):
        return self

    def merge(self, info, tag, other):
        result, merged, ignored = self.merge_item(self, other)
        if ignored:
            self.log_ignored(info, tag, other)
        elif merged:
            self.log_merged(info, tag, other)
            return self.__class__(result)
        return self

    def merge_item(self, this, other):
        if self.contains(this, other):
            return this, False, False
        if self.contains(other, this):
            return other, True, False
        return self.concat(this, other)

    def contains(self, this, other):
        return other == this

    def concat(self, this, other):
        return this, False, True

    @staticmethod
    def log_merged(info, tag, value):
        logger.info('%s: merged %s', info, tag)

    def log_replaced(self, info, tag, value):
        logger.log(
            (logging.WARNING, logging.INFO)[self._quiet],
            '%s: "%s" replaced by %s "%s"', info, str(self), tag, str(value))

    @classmethod
    def log_ignored(cls, info, tag, value):
        logger.log(
            (logging.WARNING, logging.INFO)[cls._quiet],
            '%s: ignored %s "%s"', info, tag, str(value))


class MD_UnmergableString(MD_Value, str):
    def __new__(cls, value=None):
        if value is None:
            value = ''
        elif isinstance(value, str):
            value = value.strip()
        return super(MD_UnmergableString, cls).__new__(cls, value)

    @classmethod
    def from_exiv2(cls, file_value, tag):
        if isinstance(file_value, list):
            file_value = ' // '.join(file_value)
        return cls(file_value)

    def contains(self, this, other):
        return other in this


class MD_String(MD_UnmergableString):
    def concat(self, this, other):
        return this + ' // ' + other, True, False


class MD_Software(MD_String):
    @classmethod
    def from_exiv2(cls, file_value, tag):
        if tag.startswith('Iptc'):
            file_value = ' v'.join(x for x in file_value if x)
        return cls(file_value)

    def to_iptc(self):
        return self.split(' v')


class MD_Dict(MD_Value, dict):
    def __init__(self, value=None):
        value = value or {}
        # can initialise from a string containing comma separated values
        if isinstance(value, str):
            value = value.split(',')
        # or a list of values
        if isinstance(value, (tuple, list)):
            value = zip(self._keys, value)
        # initialise all keys to None
        result = dict.fromkeys(self._keys)
        # update with any supplied values
        if value:
            result.update(value)
        # let sub-classes do any data manipulation
        result = self.convert(result)
        super(MD_Dict, self).__init__(result)

    @staticmethod
    def convert(value):
        for key in value:
            if isinstance(value[key], str):
                value[key] = value[key].strip() or None
        return value

    def __setattr__(self, name, value):
        raise TypeError(
            "{} does not support item assignment".format(self.__class__))

    def __setitem__(self, key, value):
        raise TypeError(
            "{} does not support item assignment".format(self.__class__))

    def __bool__(self):
        return any([x is not None for x in self.values()])

    def to_exif(self):
        return [self[x] for x in self._keys]

    def __str__(self):
        return '\n'.join('{}: {}'.format(k, v) for (k, v) in self.items() if v)


class MD_DateTime(MD_Dict):
    # store date and time with "precision" to store how much is valid
    # tz_offset is stored in minutes
    _keys = ('datetime', 'precision', 'tz_offset')

    @classmethod
    def convert(cls, value):
        value['precision'] = value['precision'] or 7
        if value['datetime']:
            value['datetime'] = cls.truncate_datetime(
                value['datetime'], value['precision'])
        if value['precision'] <= 3:
            value['tz_offset'] = None
        return value

    _replace = (('microsecond', 0), ('second', 0),
                ('minute',      0), ('hour',   0),
                ('day',         1), ('month',  1))

    @classmethod
    def truncate_datetime(cls, date_time, precision):
        return date_time.replace(**dict(cls._replace[:7 - precision]))

    _tz_re = re.compile(r'(.*?[T ].*?)([+-])(\d{1,2}):?(\d{1,2})$')
    _subsec_re = re.compile(r'(.*?)\.(\d+)$')
    _time_re = re.compile(r'(.*?)[T ](\d{1,2}):?(\d{1,2})?:?(\d{1,2})?$')
    _date_re = re.compile(r'(\d{1,4})[:-]?(\d{1,2})?[:-]?(\d{1,2})?$')

    @classmethod
    def from_ISO_8601(cls, datetime_string, sub_sec_string=None):
        """Sufficiently general ISO 8601 parser.

        See https://en.wikipedia.org/wiki/ISO_8601

        """
        if not datetime_string:
            return cls([])
        unparsed = datetime_string.strip()
        precision = 7
        # extract time zone
        match = cls._tz_re.match(unparsed)
        if match:
            unparsed, sign, hours, minutes = match.groups()
            tz_offset = (int(hours) * 60) + int(minutes)
            if sign == '-':
                tz_offset = -tz_offset
        elif unparsed[-1] == 'Z':
            tz_offset = 0
            unparsed = unparsed[:-1]
        else:
            tz_offset = None
        # extract sub seconds
        if not sub_sec_string:
            match = cls._subsec_re.match(unparsed)
            if match:
                unparsed, sub_sec_string = match.groups()
        if sub_sec_string:
            sub_sec_string = sub_sec_string.strip()
            microsecond = int((sub_sec_string + '000000')[:6])
        else:
            microsecond = 0
            precision = 6
        # extract time
        match = cls._time_re.match(unparsed)
        if match:
            groups = match.groups('0')
            unparsed = groups[0]
            hour, minute, second = [int(x) for x in groups[1:]]
            if match.lastindex < 4:
                precision = 2 + match.lastindex
        else:
            hour, minute, second = 0, 0, 0
            precision = 3
        # extract date
        match = cls._date_re.match(unparsed)
        if match:
            year, month, day = [int(x) for x in match.groups('1')]
            if match.lastindex < 3:
                precision = match.lastindex
            if day == 0:
                day = 1
                precision = 2
            if month == 0:
                month = 1
                precision = 1
        else:
            raise ValueError(
                'Cannot parse datetime "{}"'.format(datetime_string))
        return cls((
            datetime(year, month, day, hour, minute, second, microsecond),
            precision, tz_offset))

    _fmt_elements = ('%Y', '-%m', '-%d', 'T%H', ':%M', ':%S', '.%f')

    def to_ISO_8601(self, precision=None, time_zone=True):
        if precision is None:
            precision = self['precision']
        fmt = ''.join(self._fmt_elements[:precision])
        datetime_string = self['datetime'].strftime(fmt)
        if precision > 6 and datetime_string[-3:] == '000':
            # truncate subsecond to 3 digits
            datetime_string = datetime_string[:-3]
        if precision > 3 and time_zone and self['tz_offset'] is not None:
            # add time zone
            minutes = self['tz_offset']
            if minutes >= 0:
                datetime_string += '+'
            else:
                datetime_string += '-'
                minutes = -minutes
            datetime_string += '{:02d}:{:02d}'.format(
                minutes // 60, minutes % 60)
        return datetime_string

    @classmethod
    def from_ffmpeg(cls, file_value, tag):
        return cls.from_ISO_8601(file_value)

    # many quicktime movies use Apple's 1904 timestamp zero point
    _qt_offset = (datetime(1970, 1, 1) - datetime(1904, 1, 1)).total_seconds()

    @classmethod
    def from_exiv2(cls, file_value, tag):
        if tag.startswith('Exif'):
            return cls.from_exif(file_value)
        if tag.startswith('Iptc'):
            return cls.from_iptc(file_value)
        if tag.startswith('Xmp.video'):
            try:
                time_stamp = int(file_value)
            except Exception:
                # not an integer timestamp
                return cls([])
            if not time_stamp:
                return cls([])
            # assume date should be in range 1970 to 2034
            if time_stamp > cls._qt_offset:
                time_stamp -= cls._qt_offset
            return cls((datetime.utcfromtimestamp(time_stamp), 6, None))
        return cls.from_ISO_8601(file_value)

    # From the Exif spec: "The format is "YYYY:MM:DD HH:MM:SS" with time
    # shown in 24-hour format, and the date and time separated by one
    # blank character [20.H]. When the date and time are unknown, all
    # the character spaces except colons (":") may be filled with blank
    # characters.

    # Although the standard says "all", I've seen examples where some of
    # the values are spaces, e.g. "2004:01:     :  :  ". I assume this
    # represents a reduced precision. In Photini we write a full
    # resolution datetime and get the precision from the Xmp value.
    @classmethod
    def from_exif(cls, file_value):
        datetime_string, sub_sec_string = file_value
        if not datetime_string:
            return cls([])
        # check for blank values
        while datetime_string[-2:] == '  ':
            datetime_string = datetime_string[:-3]
        # do conversion
        return cls.from_ISO_8601(datetime_string, sub_sec_string=sub_sec_string)

    def to_exif(self):
        datetime_string = self.to_ISO_8601(
            precision=max(self['precision'], 6), time_zone=False)
        date_string = datetime_string[:10].replace('-', ':')
        time_string = datetime_string[11:19]
        sub_sec_string = datetime_string[20:]
        return date_string + ' ' + time_string, sub_sec_string

    # The exiv2 library parses correctly formatted IPTC date & time and
    # gives us integer values for each element. If the date or time is
    # malformed we get a string instead, and ignore it.

    # The date (and time?) can have missing values represented by 00
    # according to
    # https://www.iptc.org/std/photometadata/specification/IPTC-PhotoMetadata#date-created
    @classmethod
    def from_iptc(cls, file_value):
        date_value, time_value = file_value
        if not date_value:
            return cls([])
        if isinstance(date_value, str):
            # Exiv2 couldn't read malformed date, let our parser have a go
            if isinstance(time_value, str):
                date_value += 'T' + time_value
            return cls.from_ISO_8601(date_value)
        if date_value['year'] == 0:
            return cls([])
        precision = 3
        if isinstance(time_value, dict):
            tz_offset = (time_value['tzHour'] * 60) + time_value['tzMinute']
            del time_value['tzHour'], time_value['tzMinute']
            # all-zero time is assumed to be no time info
            if any(time_value.values()):
                precision = 6
        else:
            # missing or malformed time
            time_value = {}
            tz_offset = None
        if date_value['day'] == 0:
            date_value['day'] = 1
            precision = 2
        if date_value['month'] == 0:
            date_value['month'] = 1
            precision = 1
        return cls((datetime(**date_value, **time_value), precision, tz_offset))

    def to_iptc(self):
        precision = self['precision']
        datetime = self['datetime']
        year, month, day = datetime.year, datetime.month, datetime.day
        if precision < 2:
            month = 0
        if precision < 3:
            day = 0
        date_value = year, month, day
        if precision < 4:
            time_value = None
        else:
            tz_offset = self['tz_offset']
            if tz_offset is None:
                tz_hr, tz_min = 0, 0
            elif tz_offset < 0:
                tz_offset = -tz_offset
                tz_hr, tz_min = -(tz_offset // 60), -(tz_offset % 60)
            else:
                tz_hr, tz_min = tz_offset // 60, tz_offset % 60
            time_value = (
                datetime.hour, datetime.minute, datetime.second, tz_hr, tz_min)
        return date_value, time_value

    # XMP uses extended ISO 8601, but the time cannot be hours only. See
    # p75 of
    # https://partners.adobe.com/public/developer/en/xmp/sdk/XMPspecification.pdf
    # According to p71, when converting Exif values with no time zone,
    # local time zone should be assumed. However, the MWG guidelines say
    # this must not be assumed to be the time zone where the photo is
    # processed. It also says the XMP standard has been revised to make
    # time zone information optional.
    def to_xmp(self):
        precision = self['precision']
        if precision == 4:
            precision = 5
        return self.to_ISO_8601(precision=precision)

    def __bool__(self):
        return bool(self['datetime'])

    def __str__(self):
        return self.to_ISO_8601()

    def to_utc(self):
        if self['tz_offset']:
            return self['datetime'] - timedelta(minutes=self['tz_offset'])
        return self['datetime']

    def merge(self, info, tag, other):
        if other == self or not other:
            return self
        if other['datetime'] != self['datetime']:
            verbose = (other['datetime'] != self.truncate_datetime(
                self['datetime'], other['precision']))
            # datetime values differ, choose self or other
            if (self['tz_offset'] in (None, 0)) != (other['tz_offset'] in (None, 0)):
                if self['tz_offset'] in (None, 0):
                    # other has "better" time zone info so choose it
                    if verbose:
                        self.log_replaced(info, tag, other)
                    return other
                # self has better time zone info
                if verbose:
                    self.log_ignored(info, tag, other)
                return self
            if other['precision'] > self['precision']:
                # other has higher precision so choose it
                if verbose:
                    self.log_replaced(info, tag, other)
                return other
            if verbose:
                self.log_ignored(info, tag, other)
            return self
        # datetime values agree, merge other info
        result = dict(self)
        if tag.startswith('Xmp'):
            # other is Xmp, so has trusted timezone and precision
            result['precision'] = other['precision']
            result['tz_offset'] = other['tz_offset']
        else:
            # use higher precision
            if other['precision'] > self['precision']:
                result['precision'] = other['precision']
            # only trust non-zero timezone (IPTC defaults to zero)
            if (self['tz_offset'] in (None, 0)
                    and other['tz_offset'] not in (None, 0)):
                result['tz_offset'] = other['tz_offset']
        return MD_DateTime(result)


class MD_LensSpec(MD_Dict):
    # simple class to store lens "specification"
    _keys = ('min_fl', 'max_fl', 'min_fl_fn', 'max_fl_fn')
    _quiet = True

    @staticmethod
    def convert(value):
        for key in value:
            value[key] = safe_fraction(value[key] or 0)
        return value

    @classmethod
    def from_exiv2(cls, file_value, tag):
        if not file_value:
            return cls([])
        if isinstance(file_value, str):
            file_value = file_value.split()
        if 'CanonCs' in tag:
            long_focal, short_focal, focal_units = [int(x) for x in file_value]
            if focal_units == 0:
                return cls([])
            file_value = [(short_focal, focal_units), (long_focal, focal_units)]
        return cls(file_value)

    def to_xmp(self):
        return ' '.join(['{}/{}'.format(x.numerator, x.denominator)
                         for x in self.to_exif()])

    def __str__(self):
        return ','.join(['{:g}'.format(float(self[x])) for x in self._keys])


class MD_Thumbnail(MD_Dict):
    _keys = ('w', 'h', 'fmt', 'data', 'image')
    _quiet = True

    @staticmethod
    def image_from_data(data):
        # PySide insists on bytes, can't use buffer interface
        if using_pyside and not isinstance(data, bytes):
            data = bytes(data)
        buf = QtCore.QBuffer()
        buf.setData(data)
        reader = QtGui.QImageReader(buf)
        fmt = reader.format().data().decode().upper()
        reader.setAutoTransform(False)
        image = reader.read()
        if image.isNull():
            raise RuntimeError(reader.errorString())
        image.buf = buf
        return fmt, image

    @staticmethod
    def data_from_image(image, max_size=60000):
        buf = QtCore.QBuffer()
        buf.open(buf.OpenModeFlag.WriteOnly)
        quality = 95
        while quality > 10:
            image.save(buf, 'JPEG', quality)
            data = buf.data().data()
            if len(data) < max_size:
                return data
            quality -= 5
        return None

    @classmethod
    def convert(cls, value):
        value['fmt'] = value['fmt'] or 'JPEG'
        if value['data'] and not value['image']:
            value['fmt'], value['image'] = cls.image_from_data(value['data'])
        if not value['image']:
            return {}
        value['w'] = value['image'].width()
        value['h'] = value['image'].height()
        if value['data'] and len(value['data']) >= 60000:
            # don't keep unusably large amount of data
            value['data'] = None
        return value

    def to_exif(self):
        fmt, data = self['fmt'], self['data']
        if not data:
            fmt = 'JPEG'
            data = self.data_from_image(self['image'])
        if not data:
            return None, None, None, None
        fmt = (None, 6)[fmt == 'JPEG']
        return self['w'], self['h'], fmt, data

    def to_xmp(self):
        fmt, data = self['fmt'], self['data']
        if fmt != 'JPEG':
            data = None
        if not data:
            fmt = 'JPEG'
            data = self.data_from_image(self['image'], max_size=2**32)
        data = codecs.encode(memoryview(data), 'base64_codec').decode('ascii')
        return [{
            'xmpGImg:width': str(self['w']),
            'xmpGImg:height': str(self['h']),
            'xmpGImg:format': fmt,
            'xmpGImg:image': data,
            }]

    def __str__(self):
        result = '{fmt} thumbnail, {w}x{h}'.format(**self)
        if self['data']:
            result += ', {} bytes'.format(len(self['data']))
        return result


class MD_Collection(MD_Dict):
    # class for a group of independent items, each of which is an MD_Value
    _type = {}
    _default_type = MD_String

    @classmethod
    def get_type(cls, key):
        if key in cls._type:
            return cls._type[key]
        return cls._default_type

    @classmethod
    def convert(cls, value):
        for key in value:
            if not value[key]:
                continue
            value[key] = cls.get_type(key)(value[key])
        return value

    @classmethod
    def from_exiv2(cls, file_value, tag):
        if not (file_value and any(file_value)):
            return cls([])
        value = dict(zip(cls._keys, file_value))
        for key in value:
            value[key] = cls.get_type(key).from_exiv2(value[key], tag)
        return cls(value)

    def to_exif(self):
        return [(self[x] or None) and self[x].to_exif() for x in self._keys]

    def to_iptc(self):
        return [(self[x] or None) and self[x].to_iptc() for x in self._keys]

    def to_xmp(self):
        return [(self[x] or None) and self[x].to_xmp() for x in self._keys]

    def merge(self, info, tag, other):
        if other == self:
            return self
        result = dict(self)
        for key in other:
            if other[key] is None:
                continue
            if key in result and result[key] is not None:
                result[key], merged, ignored = result[key].merge_item(
                                                        result[key], other[key])
            else:
                result[key] = other[key]
                merged, ignored = True, False
            if ignored:
                self.log_ignored(info, tag, {key: str(other[key])})
            elif merged:
                self.log_merged(info, tag, {key: str(other[key])})
        return self.__class__(result)


class MD_Structure(MD_Value, dict):
    extendable = False

    def __init__(self, value=None):
        value = value or {}
        # deep copy initial values
        value = dict((k, self.get_type(k, v)(v)) for (k, v) in value.items())
        # set missing values to empty
        for k in self.item_type:
            if k not in value:
                value[k] = self.item_type[k]()
        super(MD_Structure, self).__init__(value)

    @classmethod
    def get_type(cls, key, value):
        if cls.extendable and key not in cls.item_type:
            logger.warning('Inferring type for %s', key)
            if isinstance(value, (list, tuple)):
                cls.item_type[key] = MD_MultiString
            elif isinstance(value, dict):
                cls.item_type[key] = MD_LangAlt
            else:
                cls.item_type[key] = MD_String
        return cls.item_type[key]

    @classmethod
    def from_exiv2(cls, file_value, tag):
        file_value = file_value or {}
        if isinstance(file_value, (list, tuple)):
            # "legacy" list of string values
            file_value = dict(zip(cls.legacy_keys, file_value))
        new_value = {}
        for key, value in file_value.items():
            # some files have incorrect use of 'iptcExt' in structures
            key = key.replace('iptcExt', 'Iptc4xmpExt')
            new_value[key] = cls.get_type(key, value).from_exiv2(value, tag)
        return cls(new_value)

    def merge(self, info, tag, other):
        if other == self:
            return self
        result = dict(self)
        for key in other:
            if not other[key]:
                continue
            if key in result and result[key]:
                result[key] = result[key].merge(
                    info, '{}[{}]'.format(tag, key), other[key])
            else:
                result[key] = other[key]
                self.log_merged(info, '{}[{}]'.format(tag, key), other[key])
        return self.__class__(result)

    def to_exif(self):
        if not self:
            return None
        return [self[k] and self[k].to_exif() for k in self.legacy_keys]

    def to_iptc(self):
        if not self:
            return None
        return [self[k] and self[k].to_iptc() for k in self.legacy_keys]

    def to_xmp(self):
        if not self:
            return None
        return dict((k, v.to_xmp()) for (k, v) in self.items() if v)

    def compact_form(self):
        return dict((k.split(':')[-1], v.compact_form())
                    for (k, v) in self.items() if v)

    def __str__(self):
        return pprint.pformat(self.compact_form(), compact=True)

    def __bool__(self):
        return any(self.values())


class Unused(object):
    def __new__(cls, value=None):
        return None

    @classmethod
    def from_exiv2(cls, file_value, tag):
        logger.warning('%s: to be deleted when data is saved: %s',
                       tag, file_value)
        return None


class MD_ContactInformation(MD_Structure):
    item_type = {
        'plus:LicensorID': Unused,
        'plus:LicensorName': Unused,
        'plus:LicensorStreetAddress': MD_String,
        'plus:LicensorExtendedAddress': MD_String,
        'plus:LicensorCity': MD_String,
        'plus:LicensorRegion': MD_String,
        'plus:LicensorPostalCode': MD_String,
        'plus:LicensorCountry': MD_String,
        'plus:LicensorTelephoneType1': Unused,
        'plus:LicensorTelephone1': MD_String,
        'plus:LicensorTelephoneType2': Unused,
        'plus:LicensorTelephone2': Unused,
        'plus:LicensorEmail': MD_String,
        'plus:LicensorURL': MD_String,
        }

    _ci_map = {
        'Iptc4xmpCore:CiAdrExtadr': 'plus:LicensorStreetAddress',
        'Iptc4xmpCore:CiAdrCity':   'plus:LicensorCity',
        'Iptc4xmpCore:CiAdrCtry':   'plus:LicensorCountry',
        'Iptc4xmpCore:CiEmailWork': 'plus:LicensorEmail',
        'Iptc4xmpCore:CiTelWork':   'plus:LicensorTelephone1',
        'Iptc4xmpCore:CiAdrPcode':  'plus:LicensorPostalCode',
        'Iptc4xmpCore:CiAdrRegion': 'plus:LicensorRegion',
        'Iptc4xmpCore:CiUrlWork':   'plus:LicensorURL',
        }

    @classmethod
    def from_exiv2(cls, file_value, tag):
        if tag == 'Xmp.iptc.CreatorContactInfo':
            file_value = file_value or {}
            file_value = dict((cls._ci_map[k], v)
                              for (k, v) in file_value.items())
            if 'plus:LicensorStreetAddress' in file_value:
                line1, sep, line2 = file_value[
                    'plus:LicensorStreetAddress'].partition('\n')
                if line2:
                    file_value['plus:LicensorExtendedAddress'] = line1
                    file_value['plus:LicensorStreetAddress'] = line2
        elif file_value:
            for value in file_value[1:]:
                logger.warning(
                    '%s: to be deleted when data is saved: %s', tag, value)
            # Xmp.plus.Licensor is an XMP bag with up to 3 entries, use the 1st
            file_value = file_value[0]
        return super(MD_ContactInformation, cls).from_exiv2(file_value, tag)

    def to_xmp(self):
        return [super(MD_ContactInformation, self).to_xmp()]


class MD_StructArray(MD_Value, tuple):
    # class for arrays of XMP structures such as locations or image regions
    def __new__(cls, value=None):
        value = value or []
        temp = []
        for item in value:
            if not isinstance(item, cls.item_type):
                item = cls.item_type(item)
            temp.append(item)
        while temp and not temp[-1]:
            temp = temp[:-1]
        return super(MD_StructArray, cls).__new__(cls, temp)

    @classmethod
    def from_exiv2(cls, file_value, tag):
        if not file_value:
            return cls()
        # Exif and IPTC only store one item, XMP stores any number
        if tag.startswith('Xmp'):
            file_value = [cls.item_type.from_exiv2(x, tag) for x in file_value]
        else:
            file_value = [cls.item_type.from_exiv2(file_value, tag)]
        return cls(file_value)

    def to_exif(self):
        return self and self[0].to_exif()

    def to_iptc(self):
        return self and self[0].to_iptc()

    def to_xmp(self):
        return [x.to_xmp() for x in self]

    def merge(self, info, tag, other):
        result = self
        for item in other:
            if not isinstance(item, self.item_type):
                item = self.item_type(item)
            idx = result.index(item)
            result = list(result)
            if idx < len(result):
                result[idx] = result[idx].merge(info, tag, item)
            else:
                self.log_merged(info, tag, item)
                result.append(item)
            result = self.__class__(result)
        return result

    def compact_form(self):
        return [v.compact_form() for v in self if v]

    def __str__(self):
        return '\n\n'.join(str(x) for x in self)


class MD_LangAlt(MD_Value, dict):
    # XMP LangAlt values are a sequence of RFC3066 language tag keys and
    # text values. The sequence can have a single default value, but if
    # it has more than one value, the default should be repeated with a
    # language tag. See
    # https://developer.adobe.com/xmp/docs/XMPNamespaces/XMPDataTypes/#language-alternative

    DEFAULT = 'x-default'

    def __init__(self, value=None, default_lang=None, strip=True):
        if isinstance(value, str):
            value = {self.DEFAULT: value}
        elif isinstance(value, MD_LangAlt):
            default_lang = default_lang or value.default_lang
        value = value or {}
        if strip:
            value = dict((k, v.strip()) for (k, v) in value.items())
        value = dict((k, v) for (k, v) in value.items() if v)
        if default_lang:
            self.default_lang = default_lang
            if self.DEFAULT in value and self.default_lang not in value:
                value[self.default_lang] = value[self.DEFAULT]
        else:
            self.default_lang = self.identify_default(value)
        if self.default_lang != self.DEFAULT and self.DEFAULT in value:
            del value[self.DEFAULT]
        super(MD_LangAlt, self).__init__(value)

    @classmethod
    def identify_default(cls, value):
        keys = list(value.keys())
        if len(keys) == 0:
            return QtCore.QLocale.system().bcp47Name() or cls.DEFAULT
        if len(keys) == 1:
            return keys[0]
        if cls.DEFAULT not in keys:
            # arbitrarily choose first language
            return keys[0]
        # look for language with same text as 'x-default' value
        text = value[cls.DEFAULT]
        for k, v in value.items():
            if k != cls.DEFAULT and v == text:
                return k
        return cls.DEFAULT

    def find_key(self, key):
        # languages are case insensitive
        key = key.lower()
        for k in self:
            if k.lower() == key:
                return k
        return None

    def __contains__(self, key):
        key = key and self.find_key(key)
        return super(MD_LangAlt, self).__contains__(key)

    def __getitem__(self, key):
        key = self.find_key(key)
        if not key:
            return ''
        return super(MD_LangAlt, self).__getitem__(key)

    def __setitem__(self, key, value):
        raise NotImplemented()

    def __bool__(self):
        return any(self.values())

    def __eq__(self, other):
        if isinstance(other, MD_LangAlt):
            return not self.__ne__(other)
        return super(MD_LangAlt, self).__eq__(other)

    def __ne__(self, other):
        if isinstance(other, MD_LangAlt):
            if self.default_lang != other.default_lang:
                return True
        return super(MD_LangAlt, self).__ne__(other)

    def __str__(self):
        result = []
        for key in self.languages():
            if key != self.DEFAULT:
                result.append('-- {} --'.format(key))
            result.append(self[key])
        return '\n'.join(result)

    def best_match(self, lang=None):
        if len(self) < 2:
            return self[self.default_lang]
        lang = lang or QtCore.QLocale.system().bcp47Name()
        if not lang:
            return self[self.default_lang]
        lang = lang.lower()
        langs = [lang]
        if '-' in lang:
            langs.append(lang.split('-')[0])
        for lang in langs:
            for k in self:
                if k.lower() == lang:
                    return self[k]
            for k in self:
                if k.lower().startswith(lang):
                    return self[k]
        return self[self.default_lang]

    def languages(self):
        keys = list(self.keys())
        if len(keys) < 1:
            return [self.default_lang]
        if len(keys) < 2:
            return keys
        if self.default_lang in keys:
            keys.remove(self.default_lang)
            keys.sort(key=lambda x: x.lower())
            keys.insert(0, self.default_lang)
        else:
            keys.sort(key=lambda x: x.lower())
        return keys

    def to_exif(self):
        # Xmp spec says to store only the default language in Exif
        if not self:
            return None
        return self[self.default_lang]

    def to_iptc(self):
        return self.to_exif()

    def to_xmp(self):
        if not self:
            return None
        if len(self) < 2:
            return dict(self)
        result = dict((k, v) for (k, v) in self.items() if v)
        if len(result) > 1:
            result[self.DEFAULT] = result[self.default_lang]
        return result

    def merge(self, info, tag, other):
        if self == other:
            return self
        if not isinstance(other, MD_LangAlt):
            other = MD_LangAlt(other)
        default_lang = self.default_lang
        if default_lang == self.DEFAULT:
            default_lang = other.default_lang
        result = dict(self)
        for key, value in other.items():
            if key == self.DEFAULT:
                # try to find matching value
                for k, v in result.items():
                    if k != self.DEFAULT and v == value:
                        key = k
                        break
            else:
                # try to find matching language
                key = self.find_key(key) or key
            if key not in result:
                result[key] = value
            elif value in result[key]:
                continue
            elif result[key] in value:
                result[key] = value
            else:
                result[key] += ' // ' + value
            self.log_merged(info + '[' + key + ']', tag, value)
        return self.__class__(result, default_lang=default_lang)


class MD_Rights(MD_Collection):
    # stores IPTC rights information
    _keys = ('UsageTerms', 'WebStatement')
    _default_type = MD_UnmergableString
    _type = {'UsageTerms': MD_LangAlt}


class MD_CameraModel(MD_Collection):
    _keys = ('make', 'model', 'serial_no')
    _default_type = MD_UnmergableString
    _quiet = True

    def convert(self, value):
        if value['model'] == 'unknown':
            value['model'] = None
        return super(MD_CameraModel, self).convert(value)

    def __str__(self):
        return str(dict([(x, y) for x, y in self.items() if y]))

    def get_name(self, inc_serial=True):
        result = []
        # start with 'model'
        if self['model']:
            result.append(self['model'])
        # only add 'make' if it's not part of model
        if self['make']:
            if not (result
                    and self['make'].split()[0].lower() in result[0].lower()):
                result = [self['make']] + result
        # add serial no if a unique answer is needed
        if inc_serial and self['serial_no']:
            result.append('(S/N: ' + self['serial_no'] + ')')
        return ' '.join(result)


class MD_LensModel(MD_Collection):
    _keys = ('make', 'model', 'serial_no', 'spec')
    _default_type = MD_UnmergableString
    _type = {'spec': MD_LensSpec}
    _quiet = True

    def convert(self, value):
        if value['model'] in ('n/a', '(0)', '65535'):
            value['model'] = None
        if value['serial_no'] == '0000000000':
            value['serial_no'] = None
        return super(MD_LensModel, self).convert(value)

    def get_name(self, inc_serial=True):
        result = []
        # start with 'model'
        if self['model']:
            result.append(self['model'])
        # only add 'make' if it's not part of model
        if self['make']:
            if not (result
                    and self['make'].split()[0].lower() in result[0].lower()):
                result = [self['make']] + result
        if inc_serial and self['serial_no']:
            result.append('(S/N: ' + self['serial_no'] + ')')
        if self['spec'] and not result:
            # generic name based on spec
            fl = [float(self['spec']['min_fl']), float(self['spec']['max_fl'])]
            fl = '–'.join(['{:g}'.format(x) for x in fl if x])
            fn = [float(self['spec']['min_fl_fn']),
                  float(self['spec']['max_fl_fn'])]
            fn = '–'.join(['{:g}'.format(x) for x in fn if x])
            if fl:
                model = fl + ' mm'
                if fn:
                    model += ' ƒ/' + fn
                result.append(model)
        return ' '.join(result)


class MD_MultiString(MD_Value, tuple):
    def __new__(cls, value=None):
        value = value or []
        if isinstance(value, str):
            value = value.split(';')
        value = filter(bool, [x.strip() for x in value])
        return super(MD_MultiString, cls).__new__(cls, value)

    def to_exif(self):
        return ';'.join(self)

    def to_iptc(self):
        return tuple(self)

    def to_xmp(self):
        return tuple(self)

    def __str__(self):
        return '; '.join(self)

    def merge(self, info, tag, other):
        merged = False
        result = list(self)
        for item in other:
            if tag.split('.')[0] == 'Iptc':
                # IPTC-IIM data can be truncated version of existing value
                if item not in [MetadataHandler.truncate_iptc(tag, x)
                                for x in result]:
                    result.append(item)
                    merged = True
            elif item not in result:
                result.append(item)
                merged = True
        if merged:
            self.log_merged(info, tag, other)
            return MD_MultiString(result)
        return self


class MD_HierarchicalTags(MD_Value, tuple):
    def __new__(cls, value=None):
        value = value or []
        value = [x.strip() for x in value]
        value = [x.replace('/', '|') for x in value if x]
        value.sort(key=str.casefold)
        return super(MD_HierarchicalTags, cls).__new__(cls, value)

    def to_exiv2(self, tag):
        value = list(self)
        if tag == 'Xmp.digiKam.TagsList':
            value = [x.replace('|', '/') for x in value]
        return value

    def __str__(self):
        return pprint.pformat(self, compact=True)


class MD_Keywords(MD_MultiString):
    _machine_tag = re.compile(r'^(.+):(.+)=(.+)$')

    def human_tags(self):
        return [x for x in self if not self._machine_tag.match(x)]

    def machine_tags(self):
        # yield keyword, (ns, predicate, value) for each machine tag
        for keyword in self:
            match = self._machine_tag.match(keyword)
            if match:
                yield keyword, match.groups()


class MD_Int(MD_Value, int):
    def __new__(cls, value=None):
        if value is None:
            return None
        return super(MD_Int, cls).__new__(cls, value)

    def to_exif(self):
        return self

    def __bool__(self):
        # reinterpret to mean "has a value", even if the value is zero
        return True


class MD_Orientation(MD_Int):
    @classmethod
    def from_ffmpeg(cls, file_value, tag):
        mapping = {'0': 1, '90': 6, '180': 3, '-90': 8}
        if file_value not in mapping:
            raise ValueError('unrecognised orientation {}'.format(file_value))
        return cls(mapping[file_value])

    def get_transform(self, inverted=False):
        bits = self - 1
        if not bits:
            return None
        # need to rotate and or reflect image
        # translation is set so a unit rectangle maps to a unit rectangle
        transform = QtGui.QTransform()
        if bits & 0b001:
            # reflect left-right
            transform = transform.scale(-1.0, 1.0)
        if bits & 0b010:
            # rotate 180°
            transform = transform.rotate(180.0)
        if bits & 0b100:
            # rotate 90° then reflect left-right
            transform = transform.rotate(-90.0)
            transform = transform.scale(-1.0, 1.0)
        if transform.m11() + transform.m12() < 0:
            transform = transform.translate(-1, 0)
        if transform.m21() + transform.m22() < 0:
            transform = transform.translate(0, -1)
        if inverted:
            transform = transform.inverted()[0]
        return transform


class MD_Timezone(MD_Int):
    _quiet = True

    @classmethod
    def from_exiv2(cls, file_value, tag):
        if file_value is None:
            return None
        if tag == 'Exif.Image.TimeZoneOffset':
            # convert hours to minutes
            file_value = file_value * 60
        return cls(file_value)


class MD_Float(MD_Value, float):
    def __new__(cls, value=None):
        if value is None:
            return None
        return super(MD_Float, cls).__new__(cls, value)

    def __bool__(self):
        # reinterpret to mean "has a value", even if the value is zero
        return True


class MD_Rating(MD_Float):
    @classmethod
    def from_exiv2(cls, file_value, tag):
        if not file_value:
            return None
        if tag in ('Exif.Image.RatingPercent', 'Xmp.MicrosoftPhoto.Rating'):
            value = 1.0 + (float(file_value) / 25.0)
        else:
            value = min(max(float(file_value), -1.0), 5.0)
        return cls(value)

    def to_exif(self):
        return str(int(self + 1.5) - 1)


class MD_Rational(MD_Value, Fraction):
    def __new__(cls, value=None):
        if value is None:
            return None
        return super(MD_Rational, cls).__new__(cls, safe_fraction(value))

    def to_exif(self):
        return self

    def to_xmp(self):
        return '{}/{}'.format(self.numerator, self.denominator)

    def compact_form(self):
        return float(self)

    def __bool__(self):
        # reinterpret to mean "has a value", even if the value is zero
        return True

    def __str__(self):
        return str(float(self))


class MD_Altitude(MD_Rational):
    @classmethod
    def from_exiv2(cls, file_value, tag):
        if not all(file_value):
            return None
        altitude, ref = file_value
        altitude = safe_fraction(altitude)
        if ref in (b'\x01', '1'):
            altitude = -altitude
        return cls(altitude)

    def to_exif(self):
        altitude = self
        if altitude < 0:
            altitude = -altitude
            ref = b'\x01'
        else:
            ref = b'\x00'
        return altitude, ref

    def to_xmp(self):
        altitude = self
        if altitude < 0:
            altitude = -altitude
            ref = '1'
        else:
            ref = '0'
        return '{}/{}'.format(altitude.numerator, altitude.denominator), ref

    def contains(self, this, other):
        return abs(float(other) - float(this)) < 0.001


class MD_Coordinate(MD_Rational):
    @classmethod
    def from_exiv2(cls, file_value, tag):
        if tag.startswith('Exif'):
            return cls.from_exif(file_value)
        return cls.from_xmp(file_value)

    @classmethod
    def from_exif(cls, value):
        if not all(value):
            return None
        value, ref = value
        value = [safe_fraction(x, limit=False) for x in value]
        degrees, minutes, seconds = value
        degrees += (minutes / 60) + (seconds / 3600)
        if ref in ('S', 'W'):
            degrees = -degrees
        return cls(degrees)

    @classmethod
    def from_xmp(cls, value):
        if not value:
            return None
        ref = value[-1]
        if ref in ('N', 'E', 'S', 'W'):
            negative = ref in ('S', 'W')
            value = value[:-1]
        else:
            logger.warning('no direction in XMP GPSCoordinate: %s', value)
            negative = False
        if value[0] in ('+', '-'):
            logger.warning(
                'incorrect use of signed XMP GPSCoordinate: %s', value)
            if value[0] == '-':
                negative = not negative
            value = value[1:]
        value = [safe_fraction(x, limit=False) for x in value.split(',')]
        degrees, minutes = value[:2]
        degrees += (minutes / 60)
        if len(value) > 2:
            seconds = value[2]
            degrees += (seconds / 3600)
        if negative:
            degrees = -degrees
        return cls(degrees)

    def to_exif_part(self):
        degrees = self
        pstv = degrees >= 0
        if not pstv:
            degrees = -degrees
        # make degrees and minutes integer (not mandated by Exif, but typical)
        i = int(degrees)
        minutes = (degrees - i) * 60
        degrees = Fraction(i)
        i = int(minutes)
        seconds = (minutes - i) * 60
        minutes = Fraction(i)
        seconds = seconds.limit_denominator(1000000)
        return (degrees, minutes, seconds), pstv

    def to_xmp_part(self):
        numbers, pstv = self.to_exif_part()
        if all([x.denominator == 1 for x in numbers]):
            return ('{:d},{:d},{:d}'.format(*[x.numerator for x in numbers]),
                    pstv)
        degrees, minutes, seconds = numbers
        degrees = int(degrees)
        minutes = float(minutes + (seconds / 60))
        return '{:d},{:.8f}'.format(degrees, minutes), pstv

    def contains(self, this, other):
        if other is None:
            return False
        return abs(float(other) - float(this)) < 0.0000005

    def compact_form(self):
        return float(self)

    def __float__(self):
        return round(super(MD_Coordinate, self).__float__(), 6)

    def __str__(self):
        return '{:.6f}'.format(float(self))

    def __eq__(self, other):
        return self.contains(self, other)

    def __ne__(self, other):
        return not self.contains(self, other)


class MD_Latitude(MD_Coordinate):
    def to_exif(self):
        numbers, pstv = self.to_exif_part()
        return numbers, ('S', 'N')[pstv]

    def to_xmp(self):
        string, pstv = self.to_xmp_part()
        return string + ('S', 'N')[pstv]


class MD_Longitude(MD_Coordinate):
    def to_exif(self):
        numbers, pstv = self.to_exif_part()
        return numbers, ('W', 'E')[pstv]

    def to_xmp(self):
        string, pstv = self.to_xmp_part()
        return string + ('W', 'E')[pstv]


class GPSVersionId(MD_Value, bytes):
    def __new__(cls, value=None):
        value = value or b'\x02\x00\x00\x00'
        return super(GPSVersionId, cls).__new__(cls, value)

    @classmethod
    def from_exiv2(cls, file_value, tag):
        if file_value and tag.startswith('Xmp'):
            file_value = [int(x) for x in file_value.split('.')]
        return cls(file_value)

    def to_exif(self):
        return self

    def to_xmp(self):
        return '.'.join(str(x) for x in self)

    def compact_form(self):
        return self.to_xmp()


class MD_GPSinfo(MD_Structure):
    item_type = {
        'version_id': GPSVersionId,
        'method': MD_UnmergableString,
        'exif:GPSAltitude': MD_Altitude,
        'exif:GPSLatitude': MD_Latitude,
        'exif:GPSLongitude': MD_Longitude,
        }
    legacy_keys = (
        'version_id', 'method',
        'exif:GPSAltitude', 'exif:GPSLatitude', 'exif:GPSLongitude')

    @classmethod
    def from_ffmpeg(cls, file_value, tag):
        if file_value:
            match = re.match(
                r'([-+]\d+\.\d+)([-+]\d+\.\d+)([-+]\d+\.\d+)?/', file_value)
            if match:
                return cls(dict(zip(('exif:GPSLatitude', 'exif:GPSLongitude',
                                     'exif:GPSAltitude'), match.groups())))
        return cls()

    @classmethod
    def from_exiv2(cls, file_value, tag):
        if tag.startswith('Xmp.video'):
            return cls.from_ffmpeg(file_value, tag)
        version_id = file_value[0]
        method = file_value[1]
        alt = file_value[2:4]
        if tag.startswith('Exif'):
            lat = file_value[4:6]
            lon = file_value[6:8]
        else:
            lat = file_value[4]
            lon = file_value[5]
        file_value = version_id, method, alt, lat, lon
        return super(MD_GPSinfo, cls).from_exiv2(file_value, tag)

    def to_exif(self):
        if not self:
            return None
        result = []
        for k in self.legacy_keys:
            if k in ('exif:GPSAltitude', 'exif:GPSLatitude',
                     'exif:GPSLongitude'):
                if self[k]:
                    result += self[k].to_exif()
                else:
                    result += [None, None]
            else:
                result.append(self[k] and self[k].to_exif())
        return result

    def to_xmp(self):
        if not self:
            return None
        result = []
        for k in self.legacy_keys:
            if k == 'exif:GPSAltitude':
                if self[k]:
                    result += self[k].to_xmp()
                else:
                    result += [None, None]
            else:
                result.append(self[k] and self[k].to_xmp())
        return result

    def __bool__(self):
        return any(self[k] for k in ('exif:GPSLatitude', 'exif:GPSLongitude',
                                     'exif:GPSAltitude'))

    def __eq__(self, other):
        return not self.__ne__(other)

    def __ne__(self, other):
        if not isinstance(other, MD_GPSinfo):
            other = MD_GPSinfo(other)
        return any(self[k] != other[k] for k in (
            'exif:GPSLatitude', 'exif:GPSLongitude', 'exif:GPSAltitude'))


class MD_Aperture(MD_Rational):
    # store FNumber and APEX aperture as fractions
    # only FNumber is presented to the user, either is computed if missing
    @classmethod
    def from_exiv2(cls, file_value, tag):
        if not any(file_value):
            return None
        f_number, apex = file_value
        if apex:
            apex = safe_fraction(apex)
        if not f_number:
            f_number = 2.0 ** (apex / 2.0)
        self = cls(f_number)
        if apex:
            self.apex = apex
        return self

    def to_exif(self):
        file_value = [self]
        if float(self) != 0:
            apex = getattr(self, 'apex', safe_fraction(math.log(self, 2) * 2.0))
            file_value.append(apex)
        return file_value

    def to_xmp(self):
        return ['{}/{}'.format(x.numerator, x.denominator)
                for x in self.to_exif()]

    def contains(self, this, other):
        return float(min(other, this)) > (float(max(other, this)) * 0.95)


class MD_VideoDuration(MD_Rational):
    @classmethod
    def from_ffmpeg(cls, file_value, tag):
        if tag == 'ffmpeg/streams[0]/duration':
            return cls(file_value)
        elif tag == 'ffmpeg/streams[0]/duration_ts':
            duration_ts, time_base = file_value
            if duration_ts and time_base:
                return cls(duration_ts * Fraction(time_base))
        elif tag == 'ffmpeg/streams[0]/frames':
            frames, frame_rate = file_value
            if frames and frame_rate:
                return cls((int(frames) / Fraction(frame_rate)))
        return None

    @classmethod
    def from_exiv2(cls, file_value, tag):
        if file_value:
            return cls((int(file_value), 1000))
        return None

    def contains(self, this, other):
        # some values are a bit approximate
        lo = float(min(other, this))
        hi = float(max(other, this))
        return hi - lo < max(hi * 0.0001, 0.2)


class MD_Dimensions(MD_Collection):
    _keys = ('width', 'height')
    _default_type = MD_Int

    def scaled_to(self, target_size):
        w = float(self['width'])
        h = float(self['height'])
        if w > h:
            return target_size, int((float(target_size) * h / w) + 0.5)
        return int((float(target_size) * w / h) + 0.5), target_size


class CountryCode(MD_UnmergableString):
    def __new__(cls, value=None):
        if value is None:
            value = ''
        elif isinstance(value, str):
            value = value.strip().upper()
        return super(CountryCode, cls).__new__(cls, value)


class MD_Location(MD_Structure):
    # stores IPTC defined location hierarchy
    item_type = {
        'Iptc4xmpExt:City': MD_String,
        'Iptc4xmpExt:CountryCode': CountryCode,
        'Iptc4xmpExt:CountryName': MD_String,
        'exif:GPSAltitude': MD_Rational,
        'exif:GPSLatitude': MD_Latitude,
        'exif:GPSLongitude': MD_Longitude,
        'Iptc4xmpExt:LocationId': MD_MultiString,
        'Iptc4xmpExt:LocationName': MD_LangAlt,
        'Iptc4xmpExt:ProvinceState': MD_String,
        'Iptc4xmpExt:Sublocation': MD_String,
        'Iptc4xmpExt:WorldRegion': MD_String,
        }
    legacy_keys = (
        'Iptc4xmpExt:Sublocation', 'Iptc4xmpExt:City',
        'Iptc4xmpExt:ProvinceState', 'Iptc4xmpExt:CountryName',
        'Iptc4xmpExt:CountryCode',
        )

    def to_xmp(self):
        if not self:
            # need a place holder for empty values
            return {'Iptc4xmpExt:City': ' '}
        return super(MD_Location, self).to_xmp()

    @classmethod
    def from_address(cls, gps, address, key_map):
        result = {}
        for key in cls.item_type:
            result[key] = []
        for key in key_map:
            for foreign_key in key_map[key]:
                if foreign_key not in address or not address[foreign_key]:
                    continue
                if key in result and address[foreign_key] not in result[key]:
                    result[key].append(address[foreign_key])
                del(address[foreign_key])
        # only use one country code
        result['Iptc4xmpExt:CountryCode'] = result[
            'Iptc4xmpExt:CountryCode'][:1]
        # put unknown foreign keys in Sublocation
        for foreign_key in address:
            if address[foreign_key] in ' '.join(
                    result['Iptc4xmpExt:Sublocation']):
                continue
            result['Iptc4xmpExt:Sublocation'] = [
                '{}: {}'.format(foreign_key, address[foreign_key])
                ] + result['Iptc4xmpExt:Sublocation']
        for key in result:
            result[key] = ', '.join(result[key]) or None
        result['exif:GPSLatitude'] = gps['lat']
        result['exif:GPSLongitude'] = gps['lng']
        return cls(result)


class MD_MultiLocation(MD_StructArray):
    item_type = MD_Location

    def index(self, other):
        for n, value in enumerate(self):
            if value == other:
                return n
        return len(self)


class MD_SingleLocation(MD_MultiLocation):
    def index(self, other):
        return 0


class ConceptIndentifier(MD_MultiString):
    def compact_form(self):
        fm = QtWidgets.QWidget().fontMetrics()
        width = fm.boundingRect('x' * 30).width()
        return [fm.elidedText(v, Qt.TextElideMode.ElideLeft, width)
                for v in self if v]


class EntityConcept(MD_Structure):
    item_type = {
        'Iptc4xmpExt:Name': MD_LangAlt,
        'xmp:Identifier': ConceptIndentifier,
        }


class EntityConceptArray(MD_StructArray):
    item_type = EntityConcept


class RegionBoundaryNumber(MD_Float):
    def set_decimals(self, decimals):
        self.decimals = decimals

    def compact_form(self):
        return round(self, self.decimals)

    def __eq__(self, other):
        return round(other, self.decimals) == round(self, self.decimals)

    def __str__(self):
        return '{:g}'.format(round(self, self.decimals))


class RegionBoundaryPoint(MD_Structure):
    item_type = {
        'Iptc4xmpExt:rbX': RegionBoundaryNumber,
        'Iptc4xmpExt:rbY': RegionBoundaryNumber,
        }

    def set_decimals(self, decimals):
        for v in self.values():
            v.set_decimals(decimals)


class RegionBoundaryPointArray(MD_StructArray):
    item_type = RegionBoundaryPoint

    def set_decimals(self, decimals):
        for v in self:
            v.set_decimals(decimals)


class RegionBoundary(MD_Structure):
    item_type = {
        'Iptc4xmpExt:rbShape': MD_String,
        'Iptc4xmpExt:rbUnit': MD_String,
        'Iptc4xmpExt:rbX': RegionBoundaryNumber,
        'Iptc4xmpExt:rbY': RegionBoundaryNumber,
        'Iptc4xmpExt:rbW': RegionBoundaryNumber,
        'Iptc4xmpExt:rbH': RegionBoundaryNumber,
        'Iptc4xmpExt:rbRx': RegionBoundaryNumber,
        'Iptc4xmpExt:rbVertices': RegionBoundaryPointArray,
        }

    def __init__(self, value=None):
        value = value or {}
        super(RegionBoundary, self).__init__(value)
        if self['Iptc4xmpExt:rbUnit'] == 'pixel':
            decimals = 0
        else:
            decimals = 4
        for v in self.values():
            if isinstance(v, (RegionBoundaryNumber, RegionBoundaryPointArray)):
                v.set_decimals(decimals)

    def compact_form(self):
        result = super(RegionBoundary, self).compact_form()
        if result['rbShape'] == 'circle':
            return {'rbShape':
                    'circle({rbX:g}, {rbY:g}, {rbRx:g})'.format(**result),
                    'rbUnit': result['rbUnit']}
        if result['rbShape'] == 'rectangle':
            return {'rbShape':
                    'rectangle({rbX:g}, {rbY:g}, {rbW:g}, {rbH:g})'.format(**result),
                    'rbUnit': result['rbUnit']}
        return result

    def to_Qt(self, image):
        # convert the boundary to a Qt polygon defining the shape in
        # relative units
        if self['Iptc4xmpExt:rbShape'] == 'rectangle':
            # polygon is two opposite corners of rectangle
            rect = QtCore.QRectF(
                self['Iptc4xmpExt:rbX'], self['Iptc4xmpExt:rbY'],
                self['Iptc4xmpExt:rbW'], self['Iptc4xmpExt:rbH'])
            polygon = QtGui.QPolygonF([rect.topLeft(), rect.bottomRight()])
        elif self['Iptc4xmpExt:rbShape'] == 'circle':
            # polygon is centre and a point on the circumference
            centre = QtCore.QPointF(
                self['Iptc4xmpExt:rbX'], self['Iptc4xmpExt:rbY'])
            edge = centre + QtCore.QPointF(self['Iptc4xmpExt:rbRx'], 0.0)
            polygon = QtGui.QPolygonF([centre, edge])
        else:
            # polygon is a list of vertices
            polygon = QtGui.QPolygonF([
                QtCore.QPointF(v['Iptc4xmpExt:rbX'], v['Iptc4xmpExt:rbY'])
                for v in self['Iptc4xmpExt:rbVertices']])
        if self['Iptc4xmpExt:rbUnit'] == 'relative':
            return polygon
        image_dims = image.metadata.dimensions
        transform = QtGui.QTransform().scale(1.0 / float(image_dims['width']),
                                             1.0 / float(image_dims['height']))
        return transform.map(polygon)

    def from_Qt(self, polygon, image):
        # convert a Qt polygon defining the shape in relative units to a
        # boundary in pixel or relative units
        boundary = dict(self)
        if boundary['Iptc4xmpExt:rbUnit'] == 'pixel':
            image_dims = image.metadata.dimensions
            transform = QtGui.QTransform().scale(float(image_dims['width']),
                                                 float(image_dims['height']))
            polygon = transform.map(polygon)
        if boundary['Iptc4xmpExt:rbShape'] == 'rectangle':
            # polygon is two opposite corners of rectangle
            rect = QtCore.QRectF(polygon.at(0), polygon.at(1))
            boundary['Iptc4xmpExt:rbX'] = rect.x()
            boundary['Iptc4xmpExt:rbY'] = rect.y()
            boundary['Iptc4xmpExt:rbW'] = rect.width()
            boundary['Iptc4xmpExt:rbH'] = rect.height()
        elif boundary['Iptc4xmpExt:rbShape'] == 'circle':
            # polygon is centre and a point on the circumference
            centre = polygon.at(0)
            radius = (polygon.at(1) - centre).manhattanLength()
            boundary['Iptc4xmpExt:rbX'] = centre.x()
            boundary['Iptc4xmpExt:rbY'] = centre.y()
            boundary['Iptc4xmpExt:rbRx'] = radius
        else:
            # polygon is a list of vertices
            boundary['Iptc4xmpExt:rbVertices'] = [
                {'Iptc4xmpExt:rbX': p.x(), 'Iptc4xmpExt:rbY': p.y()}
                for p in (polygon.at(n) for n in range(polygon.count()))]
        return RegionBoundary(boundary)


class ImageRegionItem(MD_Structure):
    extendable = True
    item_type = {
        'Iptc4xmpExt:RegionBoundary': RegionBoundary,
        'Iptc4xmpExt:rId': MD_String,
        'Iptc4xmpExt:Name': MD_LangAlt,
        'Iptc4xmpExt:rCtype': EntityConceptArray,
        'Iptc4xmpExt:rRole': EntityConceptArray,
        'Iptc4xmpExt:PersonInImage': MD_MultiString,
        'Iptc4xmpExt:OrganisationInImageName': MD_MultiString,
        'photoshop:CaptionWriter': MD_String,
        'dc:description': MD_LangAlt,
        }

    @classmethod
    def from_exiv2(cls, file_value, tag):
        if not file_value:
            return None
        if tag.startswith('Xmp'):
            return cls(file_value)
        # Convert Exif.Photo.SubjectArea to an image region. See
        # https://www.iptc.org/std/photometadata/documentation/userguide/#_mapping_exif_subjectarea_iptc_image_region
        if len(file_value) == 2:
            region = {'Iptc4xmpExt:rbShape': 'polygon',
                      'Iptc4xmpExt:rbVertices': [{
                          'Iptc4xmpExt:rbX': file_value[0],
                          'Iptc4xmpExt:rbY': file_value[1]}]}
        elif len(file_value) == 3:
            region = {'Iptc4xmpExt:rbShape': 'circle',
                      'Iptc4xmpExt:rbX': file_value[0],
                      'Iptc4xmpExt:rbY': file_value[1],
                      'Iptc4xmpExt:rbRx': file_value[2] // 2}
        elif len(file_value) == 4:
            region = {'Iptc4xmpExt:rbShape': 'rectangle',
                      'Iptc4xmpExt:rbX': file_value[0] - (file_value[2] // 2),
                      'Iptc4xmpExt:rbY': file_value[1] - (file_value[3] // 2),
                      'Iptc4xmpExt:rbW': file_value[2],
                      'Iptc4xmpExt:rbH': file_value[3]}
        else:
            return None
        region['Iptc4xmpExt:rbUnit'] = 'pixel'
        return cls({
            'Iptc4xmpExt:RegionBoundary': region,
            'Iptc4xmpExt:rRole': [image_region_roles[
                image_region_roles_idx['imgregrole:mainSubjectArea']]['data']],
            })

    def has_uid(self, key, uid):
        if key not in self:
            return False
        for item in self[key]:
            if 'xmp:Identifier' in item and uid in item['xmp:Identifier']:
                return True
        return False

    def has_type(self, qcode):
        data = image_region_types[image_region_types_idx[qcode]]['data']
        return self.has_uid('Iptc4xmpExt:rCtype', data['xmp:Identifier'][0])

    def has_role(self, qcode):
        data = image_region_roles[image_region_roles_idx[qcode]]['data']
        return self.has_uid('Iptc4xmpExt:rRole', data['xmp:Identifier'][0])

    def to_Qt(self, image):
        return self['Iptc4xmpExt:RegionBoundary'].to_Qt(image)

    def from_Qt(self, polygon, image):
        return self['Iptc4xmpExt:RegionBoundary'].from_Qt(polygon, image)

    def convert_unit(self, unit, image):
        boundary = self['Iptc4xmpExt:RegionBoundary']
        if boundary['Iptc4xmpExt:rbUnit'] == unit:
            return self
        polygon = boundary.to_Qt(image)
        boundary['Iptc4xmpExt:rbUnit'] = unit
        boundary = boundary.from_Qt(polygon, image)
        result = ImageRegionItem(self)
        result['Iptc4xmpExt:RegionBoundary'] = boundary
        return result


class MD_ImageRegion(MD_StructArray):
    item_type = ImageRegionItem

    def new_region(self, region, idx=None):
        if idx is None:
            idx = len(self)
        result = list(self)
        if region:
            if idx < len(self):
                result[idx] = region
            else:
                result.append(region)
        elif idx < len(self):
            result.pop(idx)
        result = MD_ImageRegion(result)
        return result

    def index(self, other):
        if other.has_role('imgregrole:mainSubjectArea'):
            # only one main subject area region allowed
            for n, value in enumerate(self):
                if value.has_role('imgregrole:mainSubjectArea'):
                    return True
            return len(self)
        for n, value in enumerate(self):
            for key in ('Iptc4xmpExt:RegionBoundary', 'Iptc4xmpExt:rId'):
                if value[key] and value[key] == other[key]:
                    return n
        return len(self)

    @staticmethod
    def boundary_from_note(note, dims, image):
        if not ('x' in note and 'y' in note and
                'w' in note and 'h' in note):
            return None
        transform = (image.metadata.orientation and
                     image.metadata.orientation.get_transform(inverted=True))
        w, h = dims
        if transform and transform.isRotating():
            w, h = h, w
        scale = QtGui.QTransform().scale(1.0 / float(w), 1.0 / float(h))
        rect = QtCore.QRectF(float(note['x']), float(note['y']),
                             float(note['w']), float(note['h']))
        rect = scale.mapRect(rect)
        if transform:
            rect = transform.mapRect(rect)
        boundary = {'Iptc4xmpExt:rbShape': 'rectangle',
                    'Iptc4xmpExt:rbUnit': 'relative'}
        (boundary['Iptc4xmpExt:rbX'],
         boundary['Iptc4xmpExt:rbY'],
         boundary['Iptc4xmpExt:rbW'],
         boundary['Iptc4xmpExt:rbH']) = rect.getRect()
        return boundary

    def from_notes(self, notes, image, target_size):
        # convert current regions to note boundaries for comparison
        boundaries = {}
        for region, note in self.to_note_boundary(image, target_size):
            key = ','.join(note[k] for k in ('x', 'y', 'w', 'h'))
            boundaries[key] = region['Iptc4xmpExt:RegionBoundary']
        dims = image.metadata.dimensions.scaled_to(target_size)
        result = []
        for note in notes:
            # use existing boundary if it matches (to cope with low
            # resolution of Flickr / Ipernity)
            key = ','.join(note[k] for k in ('x', 'y', 'w', 'h'))
            if key in boundaries:
                boundary = dict(boundaries[key])
            else:
                boundary = self.boundary_from_note(note, dims, image)
            if not boundary:
                continue
            region = {
                'Iptc4xmpExt:RegionBoundary': boundary,
                'Iptc4xmpExt:rRole': [image_region_roles[
                    image_region_roles_idx['imgregrole:subjectArea']]['data']],
                }
            if note['is_person']:
                region['Iptc4xmpExt:PersonInImage'] = [note['content']]
                region['Iptc4xmpExt:rCtype'] = [image_region_types[
                    image_region_types_idx['imgregtype:human']]['data']]
            else:
                region['dc:description'] = {'x-default': note['content']}
            if note['authorrealname']:
                region['photoshop:CaptionWriter'] = note['authorrealname']
            result.append(region)
        return result

    def to_note_boundary(self, image, target_size):
        w, h = image.metadata.dimensions.scaled_to(target_size)
        transform = (image.metadata.orientation
                     and image.metadata.orientation.get_transform())
        if transform and transform.isRotating():
            w, h = h, w
        scale = QtGui.QTransform().scale(w, h)
        for region in self:
            boundary = region['Iptc4xmpExt:RegionBoundary']
            if boundary['Iptc4xmpExt:rbShape'] != 'rectangle':
                continue
            points = region.to_Qt(image)
            rect = QtCore.QRectF(points.at(0), points.at(1))
            if transform:
                rect = transform.mapRect(rect).normalized()
            rect = scale.mapRect(rect)
            note = dict(zip(('x', 'y', 'w', 'h'),
                            [str(int(v + 0.5)) for v in rect.getRect()]))
            yield region, note

    def to_notes(self, image, target_size):
        result = []
        for region, note in self.to_note_boundary(image, target_size):
            note['content'] = ''
            note['is_person'] = False
            if region.has_type('imgregtype:human'):
                if 'Iptc4xmpExt:PersonInImage' in region:
                    note['content'] = ', '.join(
                        region['Iptc4xmpExt:PersonInImage'])
                note['is_person'] = True
            elif not any(region.has_role(x) for x in (
                    'imgregrole:subjectArea',
                    'imgregrole:mainSubjectArea',
                    'imgregrole:areaOfInterest')):
                continue
            if 'dc:description' in region and not note['content']:
                note['content'] = MD_LangAlt(
                    region['dc:description']).best_match()
            if 'Iptc4xmpExt:Name' in region and not note['content']:
                note['content'] = MD_LangAlt(
                    region['Iptc4xmpExt:Name']).best_match()
            if not note['content']:
                continue
            result.append(note)
        return result

    def get_focus(self, image):
        image_dims = image.metadata.dimensions
        portrait_format = image_dims['height'] > image_dims['width']
        transform = (image.metadata.orientation
                     and image.metadata.orientation.get_transform())
        if transform and transform.isRotating():
            portrait_format = not portrait_format
        if portrait_format:
            roles = ('imgregrole:landscapeCropping',
                     'imgregrole:squareCropping',
                     'imgregrole:recomCropping',
                     'imgregrole:cropping',
                     'imgregrole:portraitCropping')
        else:
            roles = ('imgregrole:squareCropping',
                     'imgregrole:portraitCropping',
                     'imgregrole:landscapeCropping',
                     'imgregrole:recomCropping',
                     'imgregrole:cropping')
        for role in roles:
            for region in self:
                if not region.has_role(role):
                    continue
                points = region.to_Qt(image)
                boundary = region['Iptc4xmpExt:RegionBoundary']
                if boundary['Iptc4xmpExt:rbShape'] == 'rectangle':
                    centre = (points.at(0) + points.at(1)) / 2.0
                elif boundary['Iptc4xmpExt:rbShape'] == 'circle':
                    centre = points.at(0)
                else:
                    centre = points.boundingRect().center()
                if transform:
                    centre = transform.map(centre)
                return (centre.x() * 2.0) - 1.0, 1.0 - (centre.y() * 2.0)
        return None
