##  Photini - a simple photo metadata editor.
##  http://github.com/jim-easterbrook/Photini
##  Copyright (C) 2022  Jim Easterbrook  jim@jim-easterbrook.me.uk
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

from photini.exiv2 import exiv2_version_info, MetadataHandler
from photini.pyqt import QtCore, QtGui

logger = logging.getLogger(__name__)

# photini.metadata imports these classes
__all__ = (
    'MD_Altitude', 'MD_Aperture', 'MD_CameraModel', 'MD_ContactInformation',
    'MD_DateTime', 'MD_Int', 'MD_LangAlt', 'MD_LatLon', 'MD_LensModel',
    'MD_Location', 'MD_MultiLocation', 'MD_MultiString', 'MD_Orientation',
    'MD_Rating', 'MD_Rational', 'MD_Rights', 'MD_Software', 'MD_String',
    'MD_Thumbnail', 'MD_Timezone', 'safe_fraction')


def safe_fraction(value):
    # Avoid ZeroDivisionError when '0/0' used for zero values in Exif
    try:
        if isinstance(value, (list, tuple)):
            value = Fraction(*value)
        else:
            value = Fraction(value)
    except ZeroDivisionError:
        return Fraction(0.0)
    # round off excessively large denominators
    return value.limit_denominator(1000000)


class MD_Value(object):
    # mixin for "metadata objects" - Python types with additional functionality
    _quiet = False

    def __bool__(self):
        # reinterpret to mean "has a value", even if the value is zero
        return True

    @classmethod
    def from_ffmpeg(cls, file_value, tag):
        if not file_value:
            return None
        return cls(file_value)

    @classmethod
    def from_exiv2(cls, file_value, tag):
        if not file_value:
            return None
        return cls(file_value)

    def to_exif(self):
        return str(self)

    def to_iptc(self):
        return self.to_exif()

    def to_xmp(self):
        return self.to_exif()

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
    def __new__(cls, value):
        value = isinstance(value, str) and value.strip()
        if not value:
            return None
        return super(MD_UnmergableString, cls).__new__(cls, value)

    @classmethod
    def from_exiv2(cls, file_value, tag):
        if not file_value:
            return None
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
        if not file_value:
            return None
        if tag.startswith('Iptc'):
            if not all(file_value):
                return None
            file_value = ' v'.join(file_value)
        return cls(file_value)

    def to_iptc(self):
        return self.split(' v')


class MD_Dict(MD_Value, dict):
    def __init__(self, value):
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

    @classmethod
    def from_exiv2(cls, file_value, tag):
        if not any(file_value):
            return None
        return cls(file_value)

    def to_exif(self):
        return [self[x] for x in self._keys]

    def __str__(self):
        result = []
        for key in self._keys:
            if self[key]:
                result.append('{}: {}'.format(key, self[key]))
        return '\n'.join(result)


class MD_Coordinate(MD_Dict):
    # stores latitude or longitude as three fractions and a sign boolean
    _keys = ('pstv', 'deg', 'min', 'sec')

    @staticmethod
    def convert(value):
        for key in value:
            if key == 'pstv':
                continue
            if not isinstance(value[key], Fraction):
                value[key] = safe_fraction(value[key] or 0)
        # make degrees and minutes integer (not mandated by Exif, but typical)
        for hi, lo in (('deg', 'min'), ('min', 'sec')):
            fraction = value[hi] % 1
            if fraction:
                value[lo] += fraction * 60
                value[hi] -= fraction
        # make sure minutes and seconds are in range
        for lo, hi in (('sec', 'min'), ('min', 'deg')):
            overflow = value[lo] // 60
            if overflow:
                value[hi] += overflow
                value[lo] -= overflow * 60
        return value

    @classmethod
    def from_exif(cls, file_value):
        value, ref = file_value
        if isinstance(value, str):
            value = value.split()
        pstv = ref in ('N', 'E')
        return cls((pstv, *value))

    def to_exif(self):
        return ('{:d}/{:d} {:d}/{:d} {:d}/{:d}'.format(
            self['deg'].numerator, self['deg'].denominator,
            self['min'].numerator, self['min'].denominator,
            self['sec'].numerator, self['sec'].denominator), self['pstv'])

    @classmethod
    def from_xmp(cls, value):
        ref = value[-1]
        if ref in ('N', 'E'):
            pstv = True
            value = value[:-1]
        elif ref in ('S', 'W'):
            pstv = False
            value = value[:-1]
        else:
            logger.info('no direction in XMP GPSCoordinate: %s', value)
            pstv = True
        if value[0] in ('+', '-'):
            logger.info('incorrect use of signed XMP GPSCoordinate: %s', value)
            value = value[1:]
            if value[0] == '-':
                pstv = not pstv
        return cls((pstv, *value.split(',')))

    def to_xmp(self):
        numbers = self['deg'], self['min'], self['sec']
        if all([x.denominator == 1 for x in numbers]):
            return ('{:d},{:d},{:d}'.format(*[x.numerator for x in numbers]),
                    not self['pstv'])
        degrees = int(self['deg'])
        minutes = float(((self['deg'] - degrees) * 60) + self['min']
                        + (self['sec'] / 60))
        return ('{:d},{:f}'.format(degrees, minutes), self['pstv'])

    def __float__(self):
        result = float(self['deg'] + (self['min'] / 60) + (self['sec'] / 3600))
        if not self['pstv']:
            result = -result
        return result


class MD_LatLon(MD_Dict):
    # simple class to store latitude and longitude
    _keys = ('lat', 'lon')

    @staticmethod
    def convert(value):
        for key in value:
            if isinstance(value[key], MD_Coordinate):
                continue
            if not isinstance(value[key], float):
                value[key] = float(value[key])
            pstv = True
            if value[key] < 0.0:
                value[key] = -value[key]
                pstv = False
            value[key] = MD_Coordinate((pstv, value[key]))
        return value

    @classmethod
    def from_ffmpeg(cls, file_value, tag):
        if file_value:
            match = re.match(r'([-+]\d+\.\d+)([-+]\d+\.\d+)', file_value)
            if match:
                return cls(match.group(1, 2))
        return None

    @classmethod
    def from_exiv2(cls, file_value, tag):
        if not all(file_value):
            return None
        if tag.startswith('Exif'):
            lat = MD_Coordinate.from_exif(file_value[:2])
            lon = MD_Coordinate.from_exif(file_value[2:])
        else:
            lat = MD_Coordinate.from_xmp(file_value[0])
            lon = MD_Coordinate.from_xmp(file_value[1])
        return cls((lat, lon))

    def to_exif(self):
        lat_string, pstv = self['lat'].to_exif()
        lat_ref = 'SN'[pstv]
        lon_string, pstv = self['lon'].to_exif()
        lon_ref = 'WE'[pstv]
        return (lat_string, lat_ref, lon_string, lon_ref)

    def to_xmp(self):
        lat_string, pstv = self['lat'].to_xmp()
        lat_string += 'SN'[pstv]
        lon_string, pstv = self['lon'].to_xmp()
        lon_string += 'WE'[pstv]
        return (lat_string, lon_string)

    def __str__(self):
        return '{:.6f}, {:.6f}'.format(float(self['lat']), float(self['lon']))

    def contains(self, this, other):
        return (abs(float(other['lat']) - float(this['lat'])) < 0.000001
                and abs(float(other['lon']) - float(this['lon'])) < 0.000001)


class MD_DateTime(MD_Dict):
    # store date and time with "precision" to store how much is valid
    # tz_offset is stored in minutes
    _keys = ('datetime', 'precision', 'tz_offset')

    @classmethod
    def convert(cls, value):
        value['precision'] = value['precision'] or 7
        if not value['datetime']:
            # use a well known 'zero'
            value['datetime'] = datetime(1970, 1, 1)
        else:
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

    _fmt_elements = ('%Y', '-%m', '-%d', 'T%H', ':%M', ':%S', '.%f')

    @classmethod
    def from_ISO_8601(cls, datetime_string):
        """Sufficiently general ISO 8601 parser.

        Input must be in "extended" format, i.e. with separators.
        See https://en.wikipedia.org/wiki/ISO_8601

        """
        if not datetime_string:
            return None
        # extract time zone
        tz_idx = datetime_string.find('+', 13)
        if tz_idx < 0:
            tz_idx = datetime_string.find('-', 13)
        if tz_idx >= 0:
            tz_string = datetime_string[tz_idx:]
            datetime_string = datetime_string[:tz_idx]
            tz_offset = int(tz_string[1:3]) * 60
            if len(tz_string) >= 5:
                tz_offset += int(tz_string[-2:])
            if tz_string[0] == '-':
                tz_offset = -tz_offset
        elif datetime_string[-1] == 'Z':
            tz_offset = 0
            datetime_string = datetime_string[:-1]
        else:
            tz_offset = None
        # compute precision from string length
        precision = min((len(datetime_string) - 1) // 3, 7)
        if precision <= 0:
            return None
        # set format to use same separators
        fmt = list(cls._fmt_elements[:precision])
        for n, idx in (1, 4), (2, 7), (3, 10):
            if n >= precision:
                break
            if fmt[n][0] != datetime_string[idx]:
                fmt[n] = datetime_string[idx] + fmt[n][1:]
        fmt = ''.join(fmt)
        return cls((
            datetime.strptime(datetime_string, fmt), precision, tz_offset))

    def to_ISO_8601(self, precision=None, time_zone=True):
        if precision is None:
            precision = self['precision']
        fmt = ''.join(self._fmt_elements[:precision])
        datetime_string = self['datetime'].strftime(fmt)
        if precision > 6:
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

    @classmethod
    def from_exiv2(cls, file_value, tag):
        if tag.startswith('Exif'):
            return cls.from_exif(file_value)
        if tag.startswith('Iptc'):
            return cls.from_iptc(file_value)
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
            return None
        # check for blank values
        while datetime_string[-2:] == '  ':
            datetime_string = datetime_string[:-3]
        # append sub seconds
        if len(datetime_string) == 19 and len(file_value) > 1:
            if sub_sec_string:
                sub_sec_string = sub_sec_string.strip()
            if sub_sec_string:
                datetime_string += '.' + sub_sec_string
        # do conversion
        return cls.from_ISO_8601(datetime_string)

    def to_exif(self):
        datetime_string = self.to_ISO_8601(
            precision=max(self['precision'], 6), time_zone=False)
        date_string = datetime_string[:10].replace('-', ':')
        time_string = datetime_string[11:19]
        sub_sec_string = datetime_string[20:]
        return date_string + ' ' + time_string, sub_sec_string

    # IPTC date & time should have no separators and be 8 and 11 chars
    # respectively (time includes time zone offset). The exiv2 library
    # adds separators if the data is correctly formatted, otherwise it
    # gives us the raw string.

    # The date (and time?) can have missing values represented by 00
    # according to
    # https://www.iptc.org/std/photometadata/specification/IPTC-PhotoMetadata#date-created
    @classmethod
    def from_iptc(cls, file_value):
        date_string, time_string = file_value
        if not date_string:
            return None
        # try and cope with any format - no separators, duplicate
        # separators, whatever
        parts = []
        expected = 4
        while date_string:
            while date_string and not date_string[0].isdecimal():
                date_string = date_string[1:]
            part = ''
            while expected and date_string and date_string[0].isdecimal():
                part += date_string[0]
                date_string = date_string[1:]
                expected -= 1
            parts.append(int(part))
            expected = 2
        # remove missing values
        while parts[-1] == 0:
            parts = parts[:-1]
            if not parts:
                return None
        date_string = '-'.join(['{:04d}'.format(parts[0])]
                               + ['{:02d}'.format(x) for x in parts[1:]])
        # ignore time if date is not full precision
        if len(date_string) < 10:
            time_string = None
        if time_string:
            datetime_string = date_string + 'T' + time_string
        else:
            datetime_string = date_string
        return cls.from_ISO_8601(datetime_string)

    def to_iptc(self):
        precision = self['precision']
        if precision <= 3:
            if exiv2_version_info == (0, 27, 5):
                # libexiv2 v0.27.5 won't accept zero months or days
                precision = 3
            date_string = self.to_ISO_8601(precision=precision)
            #               YYYY mm dd
            date_string += '0000-00-00'[len(date_string):]
            time_string = None
        else:
            datetime_string = self.to_ISO_8601(precision=6)
            date_string = datetime_string[:10]
            time_string = datetime_string[11:]
        return date_string, time_string

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

    def __str__(self):
        return self.to_ISO_8601()

    def to_utc(self):
        if self['tz_offset']:
            return self['datetime'] - timedelta(minutes=self['tz_offset'])
        return self['datetime']

    def merge(self, info, tag, other):
        if other == self:
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
        if self['precision'] < 7 and other['precision'] < self['precision']:
            # some formats default to a higher precision than wanted
            result['precision'] = other['precision']
        # don't trust IPTC time zone and Exif doesn't have time zone
        if (other['tz_offset'] not in (None, self['tz_offset']) and
                tag.startswith('Xmp')):
            result['tz_offset'] = other['tz_offset']
        return MD_DateTime(result)


class MD_LensSpec(MD_Dict):
    # simple class to store lens "specificaton"
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
            return None
        if isinstance(file_value, str):
            file_value = file_value.split()
        if 'CanonCs' in tag:
            long_focal, short_focal, focal_units = [int(x) for x in file_value]
            if focal_units == 0:
                return None
            file_value = [(short_focal, focal_units), (long_focal, focal_units)]
        return cls(file_value)

    def to_exif(self):
        return ' '.join(
            ['{:d}/{:d}'.format(self[x].numerator,
                                self[x].denominator) for x in self._keys])

    def __bool__(self):
        return any([bool(x) for x in self.values()])

    def __str__(self):
        return ','.join(['{:g}'.format(float(self[x])) for x in self._keys])


class MD_Thumbnail(MD_Dict):
    _keys = ('w', 'h', 'fmt', 'data', 'image')
    _quiet = True

    @staticmethod
    def image_from_data(data):
        buf = QtCore.QBuffer()
        buf.setData(data)
        reader = QtGui.QImageReader(buf)
        fmt = reader.format().data().decode().upper()
        reader.setAutoTransform(False)
        image = reader.read()
        if image.isNull():
            raise RuntimeError(reader.errorString())
        return fmt, image

    @staticmethod
    def data_from_image(image, max_size=60000):
        buf = QtCore.QBuffer()
        buf.open(buf.WriteOnly)
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
        return str(self['w']), str(self['h']), fmt, data

    def to_xmp(self):
        fmt, data = self['fmt'], self['data']
        if fmt != 'JPEG':
            data = None
        if not data:
            fmt = 'JPEG'
            data = self.data_from_image(self['image'], max_size=2**32)
        data = codecs.encode(data, 'base64_codec').decode('ascii')
        return str(self['w']), str(self['h']), fmt, data

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
    def convert(cls, value):
        for key in value:
            if key in cls._type:
                value[key] = cls._type[key](value[key])
            else:
                value[key] = cls._default_type(value[key])
        return value

    @classmethod
    def from_exiv2(cls, file_value, tag):
        if not (file_value and any(file_value)):
            return None
        value = dict(zip(cls._keys, file_value))
        for key in value:
            if key in cls._type:
                value[key] = cls._type[key].from_exiv2(value[key], tag)
            else:
                value[key] = cls._default_type.from_exiv2(value[key], tag)
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
        for key in result:
            if other[key] is None:
                continue
            if result[key] is None:
                result[key] = other[key]
                merged, ignored = True, False
            else:
                result[key], merged, ignored = result[key].merge_item(
                                                        result[key], other[key])
            if ignored:
                self.log_ignored(info, tag, {key: str(other[key])})
            elif merged:
                self.log_merged(info, tag, {key: str(other[key])})
        return self.__class__(result)


class MD_ContactInformation(MD_Collection):
    # stores IPTC contact information
    _keys = ('CiAdrExtadr', 'CiAdrCity', 'CiAdrCtry', 'CiEmailWork',
             'CiTelWork', 'CiAdrPcode', 'CiAdrRegion', 'CiUrlWork')


class MD_Location(MD_Collection):
    # stores IPTC defined location heirarchy
    _keys = ('SubLocation', 'City', 'ProvinceState',
             'CountryName', 'CountryCode', 'WorldRegion')
    _type = {'CountryCode': MD_UnmergableString}

    def convert(self, value):
        if value['CountryCode']:
            value['CountryCode'] = value['CountryCode'].upper()
        return super(MD_Location, self).convert(value)

    @classmethod
    def from_address(cls, address, key_map):
        result = {}
        for key in cls._keys:
            result[key] = []
        for key in key_map:
            for foreign_key in key_map[key]:
                if foreign_key not in address or not address[foreign_key]:
                    continue
                if key in result and address[foreign_key] not in result[key]:
                    result[key].append(address[foreign_key])
                del(address[foreign_key])
        # only use one country code
        result['CountryCode'] = result['CountryCode'][:1]
        # put unknown foreign keys in SubLocation
        for foreign_key in address:
            if address[foreign_key] in ' '.join(result['SubLocation']):
                continue
            result['SubLocation'] = [
                '{}: {}'.format(foreign_key, address[foreign_key])
                ] + result['SubLocation']
        for key in result:
            result[key] = ', '.join(result[key]) or None
        return cls(result)


class MD_MultiLocation(tuple):
    def __new__(cls, value):
        temp = []
        for item in value:
            if not item:
                item = None
            elif not isinstance(item, MD_Location):
                item = MD_Location(item)
            temp.append(item)
        while temp and not temp[-1]:
            temp = temp[:-1]
        return super(MD_MultiLocation, cls).__new__(cls, temp)

    @classmethod
    def from_exiv2(cls, file_value, tag):
        if not file_value:
            return None
        return cls(file_value)

    def to_xmp(self):
        result = []
        for location in self:
            if location:
                result.append(location.to_xmp())
            else:
                result.append([])
        return result

    def __str__(self):
        result = ''
        for n, location in enumerate(self):
            result += 'subject {}\n'.format(n + 1)
            if location:
                result += str(location) + '\n'
        return result


class LangAltDict(dict):
    # Modified dict that keeps track of a default language.
    def __init__(self, value={}):
        if isinstance(value, str):
            value = {'x-default': value}
        super(LangAltDict, self).__init__(value or {})
        self._default_lang = ''
        if isinstance(value, LangAltDict):
            self._default_lang = value._default_lang
        # Check for duplicate of 'x-default' value
        dflt_key = self.find_key('x-default')
        if dflt_key:
            dflt_value = super(LangAltDict, self).__getitem__(dflt_key)
            if dflt_value:
                super(LangAltDict, self).__delitem__(dflt_key)
                for key, value in self.items():
                    if value == dflt_value:
                        self._default_lang = key
                        break
                else:
                    super(LangAltDict, self).__setitem__(
                        'x-default', dflt_value)
        elif len(self) == 1:
            # only one item, and it's not 'x-default'
            self._default_lang = list(self.keys())[0]
        # Make sure we're not empty
        if len(self) == 0:
            super(LangAltDict, self).__setitem__('x-default', '')
        # set default_lang
        if self._default_lang:
            return
        # Exiv2 doesn't preserve the order of items, so we can't assume
        # the first item is the default language. Use the locale
        # instead.
        lang = QtCore.QLocale.system().bcp47Name()
        if not lang:
            return
        for lang in (lang, lang.split('-')[0]):
            self._default_lang = self.find_key(lang)
            if self._default_lang:
                return

    def find_key(self, key):
        # languages are case insensitive
        key = key or ''
        key = key.lower()
        for k in self:
            if k.lower() == key:
                return k
        return ''

    def __contains__(self, key):
        return bool(self.find_key(key))

    def __getitem__(self, key):
        old_key = self.find_key(key)
        if old_key:
            return super(LangAltDict, self).__getitem__(old_key)
        return super(LangAltDict, self).__getitem__(key)

    def __setitem__(self, key, value):
        old_key = self.find_key(key)
        if old_key and old_key != key:
            # new key does not have same case as old one
            if self._default_lang == old_key:
                self._default_lang = key
            super(LangAltDict, self).__delitem__(old_key)
        super(LangAltDict, self).__setitem__(key, value)

    def __delitem__(self, key):
        if self._default_lang == key:
            self._default_lang = ''
        super(LangAltDict, self).__delitem__(key)

    def __bool__(self):
        return any(self.values())

    def __eq__(self, other):
        return not self.__ne__(other)

    def __ne__(self, other):
        if isinstance(other, LangAltDict):
            if self._default_lang != other._default_lang:
                return True
        return super(LangAltDict, self).__ne__(other)

    def __str__(self):
        result = []
        for key in self.langs():
            if key != 'x-default':
                result.append('-- {} --'.format(key))
            result.append(self[key])
        return '\n'.join(result)

    def _sort_key(self, key):
        key = key.lower()
        if key == 'x-default':
            return ' '
        if key == self._default_lang.lower():
            return '!'
        return key

    def langs(self):
        result = list(self.keys())
        result.sort(key=self._sort_key)
        return result

    def default_text(self):
        if not self:
            return ''
        return self[self.langs()[0]]

    def set_default_lang(self, lang):
        new_value = ''
        key = self.find_key(lang)
        if key:
            new_value = super(LangAltDict, self).__getitem__(key)
            super(LangAltDict, self).__delitem__(key)
        old_value = ''
        key = self.find_key('x-default')
        if key:
            old_value = super(LangAltDict, self).__getitem__(key)
            super(LangAltDict, self).__delitem__(key)
        if new_value in old_value:
            new_value = old_value
        elif old_value not in new_value:
            new_value += ' // ' + old_value
        self._default_lang = lang
        super(LangAltDict, self).__setitem__(lang, new_value)


class MD_LangAlt(LangAltDict, MD_Value):
    # MD_LangAlt values are a sequence of RFC3066 language tag keys and
    # text values. The sequence can have a single default value, but if
    # it has more than one value, the default should be repeated with a
    # language tag. See
    # https://developer.adobe.com/xmp/docs/XMPNamespaces/XMPDataTypes/#language-alternative

    def to_exif(self):
        # Xmp spec says to store only the default language in Exif
        return self.default_text()

    def to_xmp(self):
        if not self:
            return None
        default_lang = self.langs()[0]
        result = {'x-default': self[default_lang],
                  default_lang: self[default_lang]}
        # don't save empty values
        for k, v in self.items():
            if v:
                result[k] = v
        return result

    def merge(self, info, tag, other):
        other = LangAltDict(other)
        if other == self:
            return self
        result = LangAltDict(self)
        for key, value in other.items():
            if key == 'x-default':
                # try to find matching value
                for k, v in result.items():
                    if value in v or v in value:
                        key = k
                        break
            else:
                # try to find matching language
                key = result.find_key(key) or key
            if key not in result:
                result[key] = value
            elif value in result[key]:
                continue
            elif result[key] in value:
                result[key] = value
            else:
                result[key] += ' // ' + value
            self.log_merged(info + '[' + key + ']', tag, value)
        return self.__class__(result)


class MD_Rights(MD_Collection):
    # stores IPTC rights information
    _keys = ('UsageTerms', 'WebStatement', 'LicensorURL')
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
    def __new__(cls, value):
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


class MD_Int(MD_Value, int):
    pass


class MD_Orientation(MD_Int):
    @classmethod
    def from_ffmpeg(cls, file_value, tag):
        mapping = {'0': 1, '90': 6, '180': 3, '-90': 8}
        if file_value not in mapping:
            raise ValueError('unrecognised orientation {}'.format(file_value))
        return cls(mapping[file_value])


class MD_Timezone(MD_Int):
    _quiet = True

    @classmethod
    def from_exiv2(cls, file_value, tag):
        if file_value in (None, ''):
            return None
        if tag == 'Exif.Image.TimeZoneOffset':
            # convert hours to minutes
            file_value = int(file_value) * 60
        return cls(file_value)


class MD_Rating(MD_Value, float):
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

    def to_xmp(self):
        return str(self)


class MD_Rational(MD_Value, Fraction):
    def __new__(cls, value):
        return super(MD_Rational, cls).__new__(cls, safe_fraction(value))

    def to_exif(self):
        return '{:d}/{:d}'.format(self.numerator, self.denominator)

    def __str__(self):
        return str(float(self))


class MD_Altitude(MD_Rational):
    @classmethod
    def from_ffmpeg(cls, file_value, tag):
        if file_value:
            match = re.match(
                r'([-+]\d+\.\d+)([-+]\d+\.\d+)([-+]\d+\.\d+)', file_value)
            if match:
                return cls(match.group(3))
        return None

    @classmethod
    def from_exiv2(cls, file_value, tag):
        if not all(file_value):
            return None
        altitude, ref = file_value
        altitude = safe_fraction(altitude)
        if ref == '1':
            altitude = -altitude
        return cls(altitude)

    def to_exif(self):
        numerator, denominator = self.numerator, self.denominator
        if numerator < 0:
            numerator = -numerator
            ref = '1'
        else:
            ref = '0'
        return ('{:d}/{:d}'.format(numerator, denominator), ref)


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
        file_value = ['{:d}/{:d}'.format(self.numerator, self.denominator)]
        if float(self) != 0:
            apex = getattr(self, 'apex', safe_fraction(math.log(self, 2) * 2.0))
            file_value.append(
                '{:d}/{:d}'.format(apex.numerator, apex.denominator))
        return file_value

    def contains(self, this, other):
        return float(min(other, this)) > (float(max(other, this)) * 0.95)
