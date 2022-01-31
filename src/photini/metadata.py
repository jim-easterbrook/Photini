##  Photini - a simple photo metadata editor.
##  http://github.com/jim-easterbrook/Photini
##  Copyright (C) 2012-21  Jim Easterbrook  jim@jim-easterbrook.me.uk
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

import codecs
from datetime import datetime, timedelta
from fractions import Fraction
import imghdr
import logging
import math
import mimetypes
import os
import re

from photini import __version__
from photini.pyqt import QtCore, QtGui
from photini.ffmpeg import FFmpeg
from photini.filemetadata import ImageMetadata, SidecarMetadata

logger = logging.getLogger(__name__)


class FFMPEGMetadata(object):
    _tag_list = {
        'altitude':       ('com.apple.quicktime.location.ISO6709',
                           'location'),
        'camera_model':   ('model',
                           'Model',
                           'com.apple.quicktime.model'),
        'copyright':      ('com.apple.quicktime.copyright',
                           'copyright',
                           'Copyright'),
        'creator':        ('com.apple.quicktime.author',
                           'artist'),
        'date_digitised': ('DateTimeDigitized',),
        'date_modified':  ('DateTime',),
        'date_taken':     ('com.apple.quicktime.creationdate',
                           'date',
                           'creation_time',
                           'DateTimeOriginal'),
        'description':    ('comment',),
        'latlong':        ('com.apple.quicktime.location.ISO6709',
                           'location'),
        'orientation':    ('rotate',),
        'rating':         ('com.apple.quicktime.rating.user',),
        'title':          ('title',),
        }

    def __init__(self, path):
        self._path = path
        self.md = {}
        raw = FFmpeg.ffprobe(path)
        if 'format' in raw and 'tags' in raw['format']:
            self.md.update(self.read_tags('format', raw['format']['tags']))
        if 'streams' in raw:
            for stream in raw['streams']:
                if 'tags' in stream:
                    self.md.update(self.read_tags(
                        'stream[{}]'.format(stream['index']), stream['tags']))

    def read_tags(self, label, tags):
        result = {}
        for key, value in tags.items():
            result['ffmpeg/{}/{}'.format(label, key)] = value
        return result

    @classmethod
    def open_old(cls, path):
        try:
            return cls(path)
        except RuntimeError as ex:
            logger.error(str(ex))
        except Exception as ex:
            logger.exception(ex)
        return None

    def read(self, name, type_):
        if name not in self._tag_list:
            return []
        result = []
        for part_tag in self._tag_list[name]:
            for tag in self.md:
                if tag.split('/')[2] != part_tag:
                    continue
                try:
                    value = type_.from_ffmpeg(self.md[tag], tag)
                except ValueError as ex:
                    logger.error('{}({}), {}: {}'.format(
                        os.path.basename(self._path), name, tag, str(ex)))
                    continue
                except Exception as ex:
                    logger.exception(ex)
                    continue
                if value:
                    result.append((tag, value))
        return result


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

    @staticmethod
    def merge_item(this, other):
        if other == this:
            return this, False, False
        return this, False, True

    @staticmethod
    def log_merged(info, tag, value):
        logger.info('%s: merged %s', info, tag)

    def log_replaced(self, info, tag, value):
        if self._quiet:
            logger.info(
                '%s: "%s" replaced by %s "%s"', info, str(self), tag, str(value))
        else:
            logger.warning(
                '%s: "%s" replaced by %s "%s"', info, str(self), tag, str(value))

    @classmethod
    def log_ignored(cls, info, tag, value):
        if cls._quiet:
            logger.info('%s: ignored %s "%s"', info, tag, str(value))
        else:
            logger.warning('%s: ignored %s "%s"', info, tag, str(value))


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


class MD_Dict_Mergeable(MD_Dict):
    @staticmethod
    def convert(value):
        for key in value:
            if value[key] is None:
                continue
            if not isinstance(value[key], str):
                value[key] = str(value[key])
            value[key] = value[key].strip() or None
        return value

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
                result[key], merged, ignored = self.merge_item(
                                                        result[key], other[key])
            if ignored:
                self.log_ignored(info, tag, {key: other[key]})
            elif merged:
                self.log_merged(info, tag, {key: other[key]})
        return self.__class__(result)


class Coordinate(MD_Dict):
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


class LatLon(MD_Dict):
    # simple class to store latitude and longitude
    _keys = ('lat', 'lon')

    @staticmethod
    def convert(value):
        for key in value:
            if isinstance(value[key], Coordinate):
                continue
            if not isinstance(value[key], float):
                value[key] = float(value[key])
            pstv = True
            if value[key] < 0.0:
                value[key] = -value[key]
                pstv = False
            value[key] = Coordinate((pstv, value[key]))
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
            lat = Coordinate.from_exif(file_value[:2])
            lon = Coordinate.from_exif(file_value[2:])
        else:
            lat = Coordinate.from_xmp(file_value[0])
            lon = Coordinate.from_xmp(file_value[1])
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

    @staticmethod
    def merge_item(this, other):
        if (abs(float(other['lat']) - float(this['lat'])) < 0.000001
                and abs(float(other['lon']) - float(this['lon'])) < 0.000001):
            return this, False, False
        return this, False, True


class ContactInformation(MD_Dict_Mergeable):
    # stores IPTC contact information
    _keys = ('CiAdrExtadr', 'CiAdrCity', 'CiAdrCtry', 'CiEmailWork',
             'CiTelWork', 'CiAdrPcode', 'CiAdrRegion', 'CiUrlWork')

    def __str__(self):
        result = []
        for key in self._keys:
            if self[key]:
                result.append('{}: {}'.format(key, self[key]))
        return '\n'.join(result)

    @staticmethod
    def merge_item(this, other):
        if other in this:
            return this, False, False
        return this + ' // ' + other, True, False


class Location(MD_Dict_Mergeable):
    # stores IPTC defined location heirarchy
    _keys = ('SubLocation', 'City', 'ProvinceState',
             'CountryName', 'CountryCode', 'WorldRegion')

    def convert(self, value):
        value = super(Location, self).convert(value)
        if value['CountryCode']:
            value['CountryCode'] = value['CountryCode'].upper()
        return value

    @classmethod
    def from_address(cls, address, key_map):
        result = {}
        for key in cls._keys:
            result[key] = []
        for key in key_map:
            for foreign_key in key_map[key]:
                if foreign_key not in address:
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

    def __str__(self):
        result = []
        for key in self._keys:
            if self[key]:
                result.append('{}: {}'.format(key, self[key]))
        return '\n'.join(result)

    @staticmethod
    def merge_item(this, other):
        if other in this:
            return this, False, False
        return this + ' // ' + other, True, False


class MultiLocation(tuple):
    def __new__(cls, value):
        temp = []
        for item in value:
            if not item:
                item = None
            elif not isinstance(item, Location):
                item = Location(item)
            temp.append(item)
        while temp and not temp[-1]:
            temp = temp[:-1]
        return super(MultiLocation, cls).__new__(cls, temp)

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


class CameraModel(MD_Dict_Mergeable):
    _keys = ('make', 'model', 'serial_no')
    _quiet = True

    def convert(self, value):
        value = super(CameraModel, self).convert(value)
        if value['model'] == 'unknown':
            value['model'] = None
        return value

    def __str__(self):
        return str(dict([(x, y) for x, y in self.items() if y]))

    def get_name(self, inc_serial=True):
        # start with 'model'
        result = self['model'] or ''
        # only add 'make' if it's really needed
        if (self['make']
                and self['make'].split()[0].lower() not in result.lower()):
            if result:
                result = ' ' + result
            result = self['make'] + result
        # add serial no if a unique answer is needed
        if inc_serial and self['serial_no']:
            if result:
                result += ' '
            result += '(S/N: ' + self['serial_no'] + ')'
        return result


class LensModel(MD_Dict_Mergeable):
    _keys = ('make', 'model', 'serial_no')
    _quiet = True

    def convert(self, value):
        value = super(LensModel, self).convert(value)
        if value['model'] in ('n/a', '(0)', '65535'):
            value['model'] = None
        if value['serial_no'] == '0000000000':
            value['serial_no'] = None
        return value

    def __str__(self):
        return str(dict([(x, y) for x, y in self.items() if y]))

    def get_name(self, inc_serial=True):
        result = self['make'] or ''
        if self['model']:
            if result in self['model']:
                result = ''
            if result:
                result += ' '
            result += self['model']
        if inc_serial and self['serial_no']:
            if result:
                result += ' '
            result += '(S/N: ' + self['serial_no'] + ')'
        return result


class LensSpec(MD_Dict):
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
        if tag == 'Exif.CanonCs.Lens':
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


class Thumbnail(MD_Dict):
    _keys = ('w', 'h', 'fmt', 'data', 'image')
    _quiet = True

    @staticmethod
    def convert(value):
        if value['data'] and not value['image']:
            buf = QtCore.QBuffer()
            buf.setData(value['data'])
            reader = QtGui.QImageReader(buf)
            reader.setAutoTransform(False)
            value['fmt'] = reader.format().data().decode().upper()
            value['image'] = reader.read()
            if value['image'].isNull():
                logger.error('thumbnail: %s', reader.errorString())
                value['image'] = None
        if value['image']:
            value['w'] = value['image'].width()
            value['h'] = value['image'].height()
            if value['data'] and len(value['data']) >= 60000:
                # don't keep unusably large amount of data
                value['data'] = None
        else:
            value['w'] = 0
            value['h'] = 0
            value['data'] = None
        return value

    @classmethod
    def from_video_header(cls, properties):
        w, h = 512, 512
        preview = None
        for props in properties:
            width = props.get_width()
            height = props.get_height()
            if abs(max(width, height) - 160) < abs(max(w, h) - 160):
                w, h = width, height
                preview = props
        if not preview:
            return None
        data = preview.get_data()
        return cls({'data': data})

    @classmethod
    def from_exiv2(cls, file_value, tag):
        w, h, fmt, data = file_value
        if not data:
            return None
        if tag.startswith('Xmp'):
            data = bytes(data, 'ascii')
            data = codecs.decode(data, 'base64_codec')
        return cls({'data': data})

    def to_exif(self):
        fmt, data = self['fmt'], self['data']
        if self['image'] and not data:
            buf = QtCore.QBuffer()
            buf.open(buf.WriteOnly)
            fmt = 'JPEG'
            quality = 95
            while quality > 10:
                self['image'].save(buf, fmt, quality)
                data = buf.data().data()
                if len(data) < 60000:
                    break
                data = None
                quality -= 5
        return (str(self['w']), str(self['h']), fmt, data)

    def to_xmp(self):
        fmt, data = self['fmt'], self['data']
        if fmt != 'JPEG':
            data = None
        if self['image'] and not data:
            buf = QtCore.QBuffer()
            buf.open(buf.WriteOnly)
            fmt = 'JPEG'
            self['image'].save(buf, self['fmt'], 95)
            data = buf.data().data()
        data = codecs.encode(data, 'base64_codec').decode('ascii')
        return (str(self['w']), str(self['h']), fmt, data)

    def __str__(self):
        result = '{fmt} thumbnail, {w}x{h}'.format(**self)
        if self['data']:
            result += ', {} bytes'.format(len(self['data']))
        return result


class DateTime(MD_Dict):
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
    # https://de.wikipedia.org/wiki/IPTC-IIM-Standard#IPTC-Felder
    @classmethod
    def from_iptc(cls, file_value):
        date_string, time_string = file_value
        if not date_string:
            return None
        # remove missing date values, allowing for GIMP not writing
        # leading zeros (some GIMP versions write '-' instead of zero!)
        parts = [int(x) for x in date_string.split('-') if x]
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
        if self['precision'] <= 3:
            date_string = self.to_ISO_8601()
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
                ImageMetadata.is_xmp_tag(tag)):
            result['tz_offset'] = other['tz_offset']
        return DateTime(result)


class MultiString(MD_Value, tuple):
    def __new__(cls, value):
        if isinstance(value, str):
            value = value.split(';')
        value = filter(bool, [x.strip() for x in value])
        return super(MultiString, cls).__new__(cls, value)

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
            if item not in result:
                result.append(item)
                merged = True
        if merged:
            self.log_merged(info, tag, other)
            return MultiString(result)
        return self


class MD_String(MD_Value, str):
    def __new__(cls, value):
        value = value.strip()
        if not value:
            return None
        return super(MD_String, cls).__new__(cls, value)

    @classmethod
    def from_exiv2(cls, file_value, tag):
        if not file_value:
            return None
        if not isinstance(file_value, str):
            file_value = ' // '.join(file_value)
        return cls(file_value)

    @staticmethod
    def merge_item(this, other):
        if other in this:
            return this, False, False
        if this in other:
            return other, True, False
        return this + ' // ' + other, True, False


class Software(MD_String):
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


class MD_Int(MD_Value, int):
    pass


class Orientation(MD_Int):
    @classmethod
    def from_ffmpeg(cls, file_value, tag):
        mapping = {'0': 1, '90': 6, '180': 3, '-90': 8}
        if file_value not in mapping:
            raise ValueError('unrecognised orientation {}'.format(file_value))
        return cls(mapping[file_value])


class Timezone(MD_Int):
    @classmethod
    def from_exiv2(cls, file_value, tag):
        if file_value in (None, ''):
            return None
        if tag == 'Exif.Image.TimeZoneOffset':
            # convert hours to minutes
            file_value = int(file_value) * 60
        return cls(file_value)


class MD_Rational(MD_Value, Fraction):
    def __new__(cls, value):
        return super(MD_Rational, cls).__new__(cls, safe_fraction(value))

    def to_exif(self):
        return '{:d}/{:d}'.format(self.numerator, self.denominator)

    def __str__(self):
        return str(float(self))


class Altitude(MD_Rational):
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


class Aperture(MD_Rational):
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

    @staticmethod
    def merge_item(this, other):
        if float(min(other, this)) > (float(max(other, this)) * 0.95):
            return this, False, False
        return this, False, True


class Rating(MD_Value, float):
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


class Metadata(object):
    # type of each Photini data field's data
    _data_type = {
        'altitude'       : Altitude,
        'aperture'       : Aperture,
        'camera_model'   : CameraModel,
        'contact_info'   : ContactInformation,
        'copyright'      : MD_String,
        'creator'        : MultiString,
        'creator_title'  : MultiString,
        'credit_line'    : MD_String,
        'date_digitised' : DateTime,
        'date_modified'  : DateTime,
        'date_taken'     : DateTime,
        'description'    : MD_String,
        'focal_length'   : MD_Rational,
        'focal_length_35': MD_Int,
        'instructions'   : MD_String,
        'keywords'       : MultiString,
        'latlong'        : LatLon,
        'lens_model'     : LensModel,
        'lens_spec'      : LensSpec,
        'location_shown' : MultiLocation,
        'location_taken' : Location,
        'orientation'    : Orientation,
        'rating'         : Rating,
        'software'       : Software,
        'thumbnail'      : Thumbnail,
        'timezone'       : Timezone,
        'title'          : MD_String,
        'usageterms'     : MD_String,
        }

    def __init__(self, path, notify=None, utf_safe=False):
        super(Metadata, self).__init__()
        # create metadata handlers for image file, video file, and sidecar
        self._path = path
        self._notify = notify
        self._utf_safe = utf_safe
        video_md = None
        self._sc = SidecarMetadata.open_old(self.find_sidecar())
        self._if = ImageMetadata.open_old(path, utf_safe=utf_safe)
        self.mime_type = self.get_mime_type()
        if self.mime_type.split('/')[0] == 'video':
            video_md = FFMPEGMetadata.open_old(path)
        self.dirty = False
        self.iptc_in_file = self._if and self._if.has_iptc()
        # get maker note info
        if self._if:
            self._maker_note = {
                'make': (self._if.has_tag('Exif.Photo.MakerNote') and
                         self._if.get_value('Exif.Image.Make')),
                'delete': False,
                }
        # read Photini metadata items
        for name in self._data_type:
            # read data values from first file that has any
            values = []
            for handler in self._sc, video_md, self._if:
                if not handler:
                    continue
                values = handler.read(name, self._data_type[name])
                if values:
                    break
            # choose result and merge in non-matching data so user can review it
            value = None
            if values:
                info = '{}({})'.format(os.path.basename(self._path), name)
                tag, value = values[0]
                logger.debug('%s: set from %s', info, tag)
            for tag2, value2 in values[1:]:
                value = value.merge(info, tag2, value2)
            super(Metadata, self).__setattr__(name, value)
        # merge in camera timezone if needed
        if not self.timezone:
            return
        for name in ('date_digitised', 'date_modified', 'date_taken'):
            value = getattr(self, name)
            if value['tz_offset'] is None:
                value = dict(value)
                value['tz_offset'] = self.timezone
                info = '{}({})'.format(os.path.basename(self._path), name)
                logger.info('%s: merged camera timezone offset', info)
                super(Metadata, self).__setattr__(
                    name, self._data_type[name](value))

    def find_sidecar(self):
        for base in (os.path.splitext(self._path)[0], self._path):
            for ext in ('.xmp', '.XMP', '.Xmp'):
                sc_path = base + ext
                if os.path.exists(sc_path):
                    return sc_path
        return None

    @staticmethod
    def abspath(path):
        # if file is an Xmp sidecar, return the corresponding image file
        path = os.path.abspath(path)
        base, ext = os.path.splitext(path)
        if ext.lower() != '.xmp':
            return path
        if os.path.isfile(base):
            return base
        for entry in os.scandir(os.path.dirname(path)):
            b, e = os.path.splitext(entry.path)
            if b == base and e != ext:
                path = entry.path
        return path

    # Exiv2 uses the Exif.Image.Make value to decode Exif.Photo.MakerNote
    # If we change Exif.Image.Make we should delete Exif.Photo.MakerNote
    def camera_change_ok(self, camera_model):
        if not self._maker_note['make']:
            return True
        if not camera_model:
            return False
        return self._maker_note['make'] == camera_model['make']

    def set_delete_makernote(self):
        self._maker_note['delete'] = True

    @classmethod
    def clone(cls, path, other):
        if other._if:
            # use exiv2 to clone image file metadata
            other._if.save_file(path)
        self = cls(path)
        if other._sc and self._if:
            # merge in sidecar data
            self._if.merge_sc(other._sc)
        # copy Photini metadata items
        for name in cls._data_type:
            value = getattr(other, name)
            setattr(self, name, value)
        return self

    def _handler_save(self, handler, *arg, **kw):
        # store Photini metadata items
        for name in self._data_type:
            value = getattr(self, name)
            handler.write(name, value)
        # save file
        return handler.save(*arg, **kw)

    def save(self, if_mode=True, sc_mode='auto',
             force_iptc=False, file_times=None):
        if not self.dirty:
            return
        self.software = 'Photini editor v' + __version__
        OK = False
        force_iptc = force_iptc or self.iptc_in_file
        try:
            # save to image file
            if if_mode and self._if:
                if self._maker_note['delete']:
                    if not self.camera_change_ok(self.camera_model):
                        self._if.clear_maker_note()
                    self._maker_note['delete'] = False
                OK = self._handler_save(
                    self._if, file_times=file_times, force_iptc=force_iptc)
                if OK:
                    self.iptc_in_file = force_iptc
            if not OK:
                # can't write to image file so must create side car
                sc_mode = 'always'
            # create side car
            if sc_mode == 'always' and not self._sc:
                self._sc = SidecarMetadata.open_new(self._path, self._if)
            # save or delete side car
            if self._sc:
                if sc_mode == 'delete':
                    self._if.merge_sc(self._sc)
                    self._sc = self._sc.delete()
                else:
                    # workaround for bug in exiv2 xmp timestamp altering
                    self._sc.clear_dates()
                    OK = self._handler_save(self._sc, file_times=file_times)
        except Exception as ex:
            logger.exception(ex)
            return
        if OK:
            self.dirty = False
            if self._notify:
                self._notify(self.dirty)

    def get_crop_factor(self):
        md = self._if or self._sc
        if not md:
            return None
        # get relevant metadata
        resolution = {}
        sensor_size = {}
        resolution_source = None, None
        for key in md.get_all_tags():
            family, group, tag = key.split('.', 2)
            if tag in ('FocalPlaneXResolution', 'FocalPlaneYResolution',
                       'FocalPlaneResolutionUnit'):
                resolution[key] = md.get_value(key)
                resolution_source = family, group
            if tag in ('PixelXDimension', 'PixelYDimension',
                       'ImageWidth', 'ImageLength'):
                sensor_size[key] = md.get_value(key)
        # convert resolution values
        if not resolution:
            return None
        family, group = resolution_source
        for tag in ('FocalPlaneXResolution', 'FocalPlaneYResolution',
                    'FocalPlaneResolutionUnit'):
            key = '.'.join((family, group, tag))
            if key not in resolution:
                return None
            resolution[tag] = resolution[key]
        resolution['x'] = safe_fraction(resolution['FocalPlaneXResolution'])
        resolution['y'] = safe_fraction(resolution['FocalPlaneYResolution'])
        resolution['unit'] = int(resolution['FocalPlaneResolutionUnit'])
        # find largest image dimensions
        sensor_size['x'], sensor_size['y'] = md.get_preview_imagedims()
        for x_key in sensor_size:
            if 'PixelXDimension' in x_key:
                y_key = x_key.replace('PixelXDimension', 'PixelYDimension')
            elif 'ImageWidth' in x_key:
                y_key = x_key.replace('ImageWidth', 'ImageLength')
            else:
                continue
            if y_key not in sensor_size:
                continue
            sensor_size['x'] = max(sensor_size['x'], int(sensor_size[x_key]))
            sensor_size['y'] = max(sensor_size['y'], int(sensor_size[y_key]))
        if not sensor_size['x'] or not sensor_size['y']:
            return None
        w = sensor_size['x'] / resolution['x']
        h = sensor_size['y'] / resolution['y']
        d = math.sqrt((h ** 2) + (w ** 2))
        if resolution['unit'] == 3:
            # unit is cm
            d *= 10.0
        elif resolution['unit'] in (None, 1, 2):
            # unit is (assumed to be) inches
            d *= 25.4
        else:
            logger.info('Unknown resolution unit %d', resolution['unit'])
            return None
        # 35 mm film diagonal is 43.27 mm
        crop_factor = 43.27 / d
        # round to 2 digits
        scale = 10 ** int(math.log10(crop_factor))
        crop_factor = round(crop_factor / scale, 1) * scale
        return crop_factor

    def get_mime_type(self):
        result = None
        if self._if:
            result = self._if.mime_type
        if not result:
            result = mimetypes.guess_type(self._path)[0]
        if not result:
            result = imghdr.what(self._path)
            if result:
                result = 'image/' + result
        # anything not recognised is assumed to be 'raw'
        if not result:
            result = 'image/raw'
        return result

    def __setattr__(self, name, value):
        if name not in self._data_type:
            return super(Metadata, self).__setattr__(name, value)
        if value in (None, '', [], {}):
            value = None
        elif not isinstance(value, self._data_type[name]):
            value = self._data_type[name](value) or None
        if getattr(self, name) == value:
            return
        super(Metadata, self).__setattr__(name, value)
        if not self.dirty:
            self.dirty = True
            if self._notify:
                self._notify(self.dirty)

    def changed(self):
        return self.dirty
