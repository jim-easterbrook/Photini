##  Photini - a simple photo metadata editor.
##  http://github.com/jim-easterbrook/Photini
##  Copyright (C) 2012-19  Jim Easterbrook  jim@jim-easterbrook.me.uk
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

import six

from photini import __version__
from photini.gi import using_pgi
from photini.pyqt import QtCore, QtGui
from photini.exiv2 import ImageMetadata, SidecarMetadata, VideoHeaderMetadata
from photini.ffmpeg import FFmpeg

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
                    value = type_.read(self, tag)
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

    def get_string(self, tag):
        if tag in self.md:
            return self.md[tag]
        return None

    @staticmethod
    def get_tag_type(tag):
        return 'FFMpeg'


def safe_fraction(value):
    # Avoid ZeroDivisionError when '0/0' used for zero values in Exif
    if isinstance(value, six.string_types):
        numerator, sep, denominator = value.partition('/')
        if denominator and int(denominator) == 0:
            return Fraction(0.0)
    return Fraction(value).limit_denominator(1000000)


class MD_Value(object):
    # mixin for "metadata objects" - Python types with additional functionality
    def __bool__(self):
        # reinterpret to mean "has a value", even if the value is zero
        return True

    # Python 3 uses __bool__, Python 2 uses __nonzero__
    __nonzero__ = __bool__

    @classmethod
    def read(cls, handler, tag):
        file_value = handler.get_string(tag)
        if not file_value:
            return None
        return cls(file_value)

    def write(self, handler, tag):
        handler.set_string(tag, six.text_type(self))

    def merge(self, info, tag, other):
        result, merged, ignored = self.merge_item(self, other)
        if ignored:
            self.log_ignored(info, tag, other)
        elif merged:
            self.log_merged(info, tag, other)
            return self.__class__(result)
        return self

    def merge_item(self, this, other):
        if other == this:
            return this, False, False
        return this, False, True

    def log_merged(self, info, tag, value):
        logger.info('%s: merged %s', info, tag)

    def log_replaced(self, info, tag, value):
        logger.warning(
            '%s: "%s" replaced by %s "%s"', info, str(self), tag, str(value))

    def log_ignored(self, info, tag, value):
        logger.warning('%s: ignored %s "%s"', info, tag, str(value))


class MD_Dict(MD_Value, dict):
    def __init__(self, value):
        # can initialise from a string containing comma separated values
        if isinstance(value, six.string_types):
            value = value.split(',')
        # or a list of values
        if isinstance(value, (tuple, list)):
            value = zip(self._keys, value)
        # initialise all keys to None
        result = dict.fromkeys(self._keys)
        # update with any supplied values
        result.update(value)
        # let sub-classes do any data manipulation
        result = self.convert(result)
        super(MD_Dict, self).__init__(result)

    @staticmethod
    def convert(value):
        return value

    def __getattr__(self, name):
        if name in self:
            return self[name]
        raise AttributeError(
            "{} has no attribute {}".format(self.__class__, name))

    def __setattr__(self, name, value):
        raise TypeError(
            "{} does not support item assignment".format(self.__class__))

    def __setitem__(self, key, value):
        raise TypeError(
            "{} does not support item assignment".format(self.__class__))

    def __bool__(self):
        return any([x is not None for x in self.values()])

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
                self.log_ignored(info + '[' + key + ']', tag, other)
            elif merged:
                self.log_merged(info + '[' + key + ']', tag, other)
        return self.__class__(result)


class LatLon(MD_Dict):
    # simple class to store latitude and longitude
    _keys = ('lat', 'lon')

    @staticmethod
    def convert(value):
        for key in value:
            value[key] = round(float(value[key]), 6)
        return value

    @classmethod
    def read(cls, handler, tag):
        file_value = handler.get_string(tag)
        if (isinstance(handler, FFMPEGMetadata)
                or tag == 'Xmp.video.GPSCoordinates'):
            if file_value:
                match = re.match(r'([-+]\d+\.\d+)([-+]\d+\.\d+)', file_value)
                if match:
                    return cls(match.group(1, 2))
            return None
        if not all(file_value):
            return None
        if handler.is_exif_tag(tag):
            return cls((cls.from_exif_part(file_value[0], file_value[1]),
                        cls.from_exif_part(file_value[2], file_value[3])))
        else:
            return cls((cls.from_xmp_part(file_value[0]),
                        cls.from_xmp_part(file_value[1])))

    def write(self, handler, tag):
        if handler.is_exif_tag(tag):
            lat_string, negative = self.to_exif_part(self.lat)
            lat_ref = 'NS'[negative]
            lon_string, negative = self.to_exif_part(self.lon)
            lon_ref = 'EW'[negative]
            handler.set_string(tag, (lat_string, lat_ref, lon_string, lon_ref))
        else:
            lat_string, negative = self.to_xmp_part(self.lat)
            lat_string += 'NS'[negative]
            lon_string, negative = self.to_xmp_part(self.lon)
            lon_string += 'EW'[negative]
            handler.set_string(tag, (lat_string, lon_string))

    @staticmethod
    def from_exif_part(value, ref):
        parts = [float(Fraction(x)) for x in value.split()] + [0.0, 0.0]
        result = parts[0] + (parts[1] / 60.0) + (parts[2] / 3600.0)
        if ref in ('S', 'W'):
            result = -result
        return result

    @staticmethod
    def to_exif_part(value):
        negative = value < 0.0
        if negative:
            value = -value
        degrees = int(value)
        value = (value - degrees) * 60.0
        minutes = int(value)
        seconds = (value - minutes) * 60.0
        seconds = safe_fraction(seconds)
        return '{:d}/1 {:d}/1 {:d}/{:d}'.format(
            degrees, minutes, seconds.numerator, seconds.denominator), negative

    @staticmethod
    def from_xmp_part(value):
        ref = value[-1]
        if ref in ('N', 'S', 'E', 'W'):
            value = value[:-1]
        if ',' in value:
            degrees, minutes = value.split(',')
            value = float(degrees) + (float(minutes) / 60.0)
        else:
            value = float(value)
        if ref in ('S', 'W'):
            value = -value
        return value

    @staticmethod
    def to_xmp_part(value):
        negative = value < 0.0
        if negative:
            value = -value
        degrees = int(value)
        minutes = (value - degrees) * 60.0
        return '{:d},{:.6f}'.format(degrees, minutes), negative

    def __str__(self):
        return '{:.6f}, {:.6f}'.format(self.lat, self.lon)

    def merge_item(self, this, other):
        if abs(other - this) < 0.0000015:
            return this, False, False
        return this, False, True


class Location(MD_Dict):
    # stores IPTC defined location heirarchy
    _keys = ('sublocation', 'city', 'province_state',
             'country_name', 'country_code', 'world_region')

    @staticmethod
    def convert(value):
        for key in value:
            if value[key] and not value[key].strip():
                value[key] = None
        if value['country_code']:
            value['country_code'] = value['country_code'].upper()
        return value

    @classmethod
    def read(cls, handler, tag, idx=1):
        file_value = handler.get_string(tag, idx=idx)
        if not any(file_value):
            return None
        return cls(file_value)

    def write(self, handler, tag, idx=1):
        handler.set_string(tag, [self[x] for x in self._keys], idx=idx)

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
        result['country_code'] = result['country_code'][:1]
        # put unknown foreign keys in sublocation
        for foreign_key in address:
            if address[foreign_key] in ' '.join(result['sublocation']):
                continue
            result['sublocation'] = [
                '{}: {}'.format(foreign_key, address[foreign_key])
                ] + result['sublocation']
        for key in result:
            result[key] = ', '.join(result[key]) or None
        return cls(result)

    def __str__(self):
        result = []
        for key in self._keys:
            if self[key]:
                result.append('{}: {}'.format(key, self[key]))
        return '\n'.join(result)

    def merge_item(self, this, other):
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
    def read(cls, handler, tag):
        count = 0
        for t in handler.get_xmp_tags():
            if t.startswith(tag):
                match = re.search('\[(\d+)\]', t)
                if match:
                    count = max(count, int(match.group(1)))
        value = []
        for n in range(count):
            value.append(Location.read(handler, tag, idx=n + 1))
        return cls(value)

    def write(self, handler, tag):
        # ignore empty values at end of list
        count = len(self)
        while count > 0 and not self[count - 1]:
            count -= 1
        # delete file values beyond end of list
        file_count = count
        while Location.read(handler, tag, idx=file_count + 1) is not None:
            file_count += 1
        while file_count > count:
            handler.clear_value(tag, idx=file_count)
            file_count -= 1
        # save list values
        for n in range(count):
            if self[n]:
                self[n].write(handler, tag, idx=n + 1)
            else:
                handler.clear_value(tag, idx=n + 1, place_holder=True)

    def __str__(self):
        result = ''
        for n, location in enumerate(self):
            result += 'subject {}\n'.format(n + 1)
            if location:
                result += six.text_type(location) + '\n'
        return result


class LensSpec(MD_Dict):
    # simple class to store lens "specificaton"
    _keys = ('min_fl', 'max_fl', 'min_fl_fn', 'max_fl_fn')

    @staticmethod
    def convert(value):
        for key in value:
            value[key] = safe_fraction(value[key])
        return value

    @classmethod
    def read(cls, handler, tag):
        file_value = handler.get_string(tag)
        if not file_value:
            return None
        file_value = file_value.split()
        if tag == 'Exif.CanonCs.Lens':
            long_focal, short_focal, focal_units = file_value
            if focal_units == '0':
                return None
            return cls(('{}/{}'.format(short_focal, focal_units),
                        '{}/{}'.format(long_focal, focal_units), 0, 0))
        return cls(file_value)

    def write(self, handler, tag):
        handler.set_string(tag, ' '.join(['{:d}/{:d}'.format(
            self[x].numerator, self[x].denominator) for x in self._keys]))

    def __str__(self):
        return ','.join(['{:g}'.format(float(self[x])) for x in self._keys])


class Thumbnail(MD_Dict):
    _keys = ('data', 'fmt', 'w', 'h')

    @classmethod
    def read(cls, handler, tag):
        if handler.is_xmp_tag(tag):
            data, fmt, w, h = handler.get_string(tag)
            if not all((data, fmt, w, h)):
                return None
            if not six.PY2:
                data = bytes(data, 'ascii')
            data = codecs.decode(data, 'base64_codec')
            w = int(w)
            h = int(h)
        elif handler.is_exif_tag(tag):
            data = handler.get_exif_thumbnail()
            if using_pgi and isinstance(data, tuple):
                # get_exif_thumbnail returns (OK, data) tuple
                data = data[data[0]]
            if not data:
                return None
            data = bytearray(data)
            fmt = handler.get_tag_string(tag)
            fmt = ('TIFF', 'JPEG')[fmt == '6']
            pixmap = QtGui.QPixmap()
            pixmap.loadFromData(data)
            w = pixmap.width()
            h = pixmap.height()
        return cls((data, fmt, w, h))

    def write(self, handler, tag):
        if handler.is_xmp_tag(tag):
            data = self.data
            w = self.w
            h = self.h
            if self.fmt != 'JPEG':
                pixmap = QtGui.QPixmap()
                pixmap.loadFromData(data)
                buf = QtCore.QBuffer()
                buf.open(QtCore.QIODevice.WriteOnly)
                pixmap.save(buf, 'JPEG')
                data = buf.data().data()
                w = pixmap.width()
                h = pixmap.height()
            if not w or not h:
                pixmap = QtGui.QPixmap()
                pixmap.loadFromData(data)
                w = pixmap.width()
                h = pixmap.height()
            data = codecs.encode(data, 'base64_codec')
            if not six.PY2:
                data = data.decode('ascii')
            handler.set_string(tag, (data, 'JPEG', str(w), str(h)))
        elif handler.is_exif_tag(tag):
            handler.set_exif_thumbnail_from_buffer(self.data)

    def __str__(self):
        return '{} thumbnail, {}x{}'.format(self.fmt, self.w, self.h)


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
            precision = self.precision
        fmt = ''.join(self._fmt_elements[:precision])
        datetime_string = self.datetime.strftime(fmt)
        if precision > 6:
            # truncate subsecond to 3 digits
            datetime_string = datetime_string[:-3]
        if precision > 3 and time_zone and self.tz_offset is not None:
            # add time zone
            minutes = self.tz_offset
            if minutes >= 0:
                datetime_string += '+'
            else:
                datetime_string += '-'
                minutes = -minutes
            datetime_string += '{:02d}:{:02d}'.format(
                minutes // 60, minutes % 60)
        return datetime_string

    # many quicktime movies use Apple's 1904 timestamp zero point
    qt_offset = (datetime(1970, 1, 1) - datetime(1904, 1, 1)).total_seconds()

    # Do something different with Xmp.video tags
    @classmethod
    def read(cls, handler, tag):
        file_value = handler.get_string(tag)
        if not file_value:
            return None
        if isinstance(handler, FFMPEGMetadata):
            return cls.from_ISO_8601(file_value)
        if handler.is_exif_tag(tag):
            return cls.from_exif(file_value)
        if handler.is_iptc_tag(tag):
            return cls.from_iptc(file_value)
        if tag.startswith('Xmp.video'):
            time_stamp = int(file_value)
            if time_stamp == 0:
                return None
            # assume date should be in range 1970 to 2034
            if time_stamp > cls.qt_offset:
                time_stamp -= cls.qt_offset
            return cls((datetime.utcfromtimestamp(time_stamp), 6, None))
        return cls.from_xmp(file_value)

    def write(self, handler, tag):
        if handler.is_exif_tag(tag):
            handler.set_string(tag, self.to_exif())
        elif handler.is_iptc_tag(tag):
            handler.set_string(tag, self.to_iptc())
        else:
            handler.set_string(tag, self.to_xmp())

    # From the Exif spec: "The format is "YYYY:MM:DD HH:MM:SS" with time
    # shown in 24-hour format, and the date and time separated by one
    # blank character [20.H]. When the date and time are unknown, all
    # the character spaces except colons (":") may be filled with blank
    # characters.

    # Although the standard says "all", I've seen examples where some of
    # the values are spaces, e.g. "2004:01:  :  :  ". I assume this
    # represents a reduced precision. In Photini we write a full
    # resolution datetime, but treat "00:00:00" as a None time value.
    @classmethod
    def from_exif(cls, file_value):
        datetime_string = file_value[0]
        if not datetime_string:
            return None
        # check for blank values
        while datetime_string[-2:] == '  ':
            datetime_string = datetime_string[:-3]
        # check for zero time
        if len(datetime_string) == 19 and datetime_string[-8:] == '00:00:00':
            datetime_string = datetime_string[:-9]
            if datetime_string == '0000:00:00':
                # all zeros, used by some programs to indicate missing value
                return None
        # append sub seconds
        if len(datetime_string) == 19 and len(file_value) > 1:
            sub_sec_string = file_value[1]
            if sub_sec_string:
                sub_sec_string = sub_sec_string.strip()
            if sub_sec_string:
                datetime_string += '.' + sub_sec_string
        # do conversion
        return cls.from_ISO_8601(datetime_string)

    def to_exif(self):
        datetime_string = self.to_ISO_8601(
            precision=max(self.precision, 6), time_zone=False)
        date_string = datetime_string[:10].replace('-', ':')
        time_string = datetime_string[11:19]
        sub_sec_string = datetime_string[20:]
        return date_string + ' ' + time_string, sub_sec_string

    # IPTC date & time should have no separators and be 8 and 11 chars
    # respectively (time includes time zone offset). I suspect the exiv2
    # library is adding separators, but am not sure.

    # The date (and time?) can have missing values represented by 00
    # according to
    # https://de.wikipedia.org/wiki/IPTC-IIM-Standard#IPTC-Felder
    @classmethod
    def from_iptc(cls, file_value):
        date_string, time_string = file_value
        if not date_string:
            return None
        # remove missing values
        while len(date_string) > 4 and date_string[-2:] == '00':
            date_string = date_string[:-3]
        if date_string == '0000':
            return None
        # ignore time if date is not full precision
        if len(date_string) < 10:
            time_string = None
        if time_string:
            datetime_string = date_string + 'T' + time_string
        else:
            datetime_string = date_string
        return cls.from_ISO_8601(datetime_string)

    def to_iptc(self):
        if self.precision <= 3:
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
    @classmethod
    def from_xmp(cls, file_value):
        self = cls.from_ISO_8601(file_value)
        if self and self.precision == 5 and self.datetime.minute == 0:
            return cls((self.datetime, 4, self.tz_offset))
        return self

    def to_xmp(self):
        precision = self.precision
        if precision == 4:
            precision = 5
        return self.to_ISO_8601(precision=precision)

    def __str__(self):
        return self.to_ISO_8601()

    def to_utc(self):
        if self.tz_offset:
            return self.datetime - timedelta(minutes=self.tz_offset)
        return self.datetime

    def merge(self, info, tag, other):
        if other == self:
            return self
        if other.datetime != self.datetime:
            # datetime values differ, choose self or other
            if (self.tz_offset in (None, 0)) != (other.tz_offset in (None, 0)):
                if self.tz_offset in (None, 0):
                    # other has "better" time zone info so choose it
                    self.log_replaced(info, tag, other)
                    return other
                # self has better time zone info
                self.log_ignored(info, tag, other)
                return self
            if other.precision > self.precision:
                # other has higher precision so choose it
                self.log_replaced(info, tag, other)
                return other
            if other.datetime != self.truncate_datetime(
                                            self.datetime, other.precision):
                self.log_ignored(info, tag, other)
            return self
        # datetime values agree, merge other info
        result = dict(self)
        if self.precision < 7 and other.precision < self.precision:
            # some formats default to a higher precision than wanted
            result['precision'] = other.precision
        # don't trust IPTC time zone and Exif doesn't have time zone
        if (other.tz_offset not in (None, self.tz_offset) and
                ImageMetadata.is_xmp_tag(tag)):
            result['tz_offset'] = other.tz_offset
        return DateTime(result)


class MultiString(MD_Value, tuple):
    def __new__(cls, value):
        if isinstance(value, six.string_types):
            value = value.split(';')
        value = filter(bool, [x.strip() for x in value])
        return super(MultiString, cls).__new__(cls, value)

    @classmethod
    def read(cls, handler, tag):
        if handler.get_tag_type(tag) in ('String', 'XmpBag', 'XmpSeq'):
            file_value = handler.get_multiple(tag)
        else:
            file_value = handler.get_string(tag)
        if not file_value:
            return None
        return cls(file_value)

    def write(self, handler, tag):
        if handler.get_tag_type(tag) in ('String', 'XmpBag', 'XmpSeq'):
            handler.set_multiple(tag, self)
        else:
            handler.set_string(tag, ';'.join(self))

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


class MD_String(MD_Value, six.text_type):
    @classmethod
    def read(cls, handler, tag):
        if handler.get_tag_type(tag) == 'LangAlt':
            file_value = handler.get_multiple(tag)
            if file_value:
                file_value = file_value[0]
        else:
            file_value = handler.get_string(tag)
        if file_value:
            file_value = six.text_type(file_value).strip()
        if not file_value:
            return None
        return cls(file_value)

    def write(self, handler, tag):
        handler.set_string(tag, self)

    def merge_item(self, this, other):
        if other in this:
            return this, False, False
        return this + ' // ' + other, True, False


class CameraModel(MD_String):
    @classmethod
    def read(cls, handler, tag):
        file_value = handler.get_string(tag)
        if not file_value:
            return None
        if file_value == 'unknown':
            return None
        if tag == 'Exif.Canon.ModelID':
            file_value = 'Canon_ID-{:08x}'.format(int(file_value))
        return cls(file_value)

    def merge_item(self, this, other):
        return this, False, False


class Software(MD_String):
    @classmethod
    def read(cls, handler, tag):
        file_value = handler.get_string(tag)
        if handler.is_iptc_tag(tag):
            file_value, version = file_value
            if file_value and version:
                file_value += ' v' + version
        if not file_value:
            return None
        return cls(file_value)

    def write(self, handler, tag):
        if handler.is_iptc_tag(tag):
            handler.set_string(tag, self.split(' v'))
        else:
            handler.set_string(tag, self)


class MD_Int(MD_Value, int):
    pass


class Orientation(MD_Int):
    @classmethod
    def read(cls, handler, tag):
        file_value = handler.get_string(tag)
        if file_value is None:
            return None
        if isinstance(handler, FFMPEGMetadata):
            file_value = int(file_value)
            if file_value == 0:
                file_value = 1
            elif file_value == 90:
                file_value = 6
            elif file_value == 180:
                file_value = 3
            elif file_value == -90:
                file_value = 8
            else:
                logger.error('unrecognised %s value %s', tag, file_value)
                file_value = None
        return cls(file_value)


class Timezone(MD_Int):
    @classmethod
    def read(cls, handler, tag):
        file_value = handler.get_string(tag)
        if not file_value:
            return None
        if tag == 'Exif.Image.TimeZoneOffset':
            # convert hours to minutes
            return cls(int(file_value) * 60)
        return cls(file_value)


class MD_Rational(MD_Value, Fraction):
    def __new__(cls, value):
        return super(MD_Rational, cls).__new__(cls, safe_fraction(value))

    @classmethod
    def read(cls, handler, tag):
        file_value = handler.get_string(tag)
        if not file_value:
            return None
        return cls(file_value)

    def write(self, handler, tag):
        handler.set_string(
            tag, '{:d}/{:d}'.format(self.numerator, self.denominator))

    def __str__(self):
        return six.text_type(float(self))


class Altitude(MD_Rational):
    @classmethod
    def read(cls, handler, tag):
        file_value = handler.get_string(tag)
        if isinstance(handler, FFMPEGMetadata):
            if file_value:
                match = re.match(
                    r'([-+]\d+\.\d+)([-+]\d+\.\d+)([-+]\d+\.\d+)', file_value)
                if match:
                    return cls(match.group(3))
            return None
        if not all(file_value):
            return None
        altitude, ref = file_value
        altitude = safe_fraction(altitude)
        if ref == '1':
            altitude = -altitude
        return cls(altitude)

    def write(self, handler, tag):
        numerator, denominator = self.numerator, self.denominator
        if numerator < 0:
            numerator = -numerator
            ref = '1'
        else:
            ref = '0'
        handler.set_string(
            tag, ('{:d}/{:d}'.format(numerator, denominator), ref))


class Aperture(MD_Rational):
    # store FNumber and APEX aperture as fractions
    # only FNumber is presented to the user, either is computed if missing
    @classmethod
    def read(cls, handler, tag):
        file_value = handler.get_string(tag)
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

    def write(self, handler, tag):
        file_value = ['{:d}/{:d}'.format(self.numerator, self.denominator)]
        if self != 0:
            apex = getattr(self, 'apex', safe_fraction(math.log(self, 2) * 2.0))
            file_value.append(
                '{:d}/{:d}'.format(apex.numerator, apex.denominator))
        handler.set_string(tag, file_value)

    def merge_item(self, this, other):
        if (min(other, this) / max(other, this)) > 0.95:
            return this, False, False
        return this, False, True


class Rating(MD_Value, float):
    @classmethod
    def read(cls, handler, tag):
        file_value = handler.get_string(tag)
        if file_value is None:
            return None
        if tag in ('Exif.Image.RatingPercent', 'Xmp.MicrosoftPhoto.Rating'):
            value = 1.0 + (float(file_value) / 25.0)
        else:
            value = min(max(float(file_value), -1.0), 5.0)
        return cls(value)

    def write(self, handler, tag):
        if handler.is_exif_tag(tag):
            handler.set_string(tag, six.text_type(int(self + 1.5) - 1))
        else:
            handler.set_string(tag, six.text_type(self))


class Metadata(QtCore.QObject):
    unsaved = QtCore.pyqtSignal(bool)

    # type of each Photini data field's data
    _data_type = {
        'altitude'       : Altitude,
        'aperture'       : Aperture,
        'camera_model'   : CameraModel,
        'copyright'      : MD_String,
        'creator'        : MultiString,
        'date_digitised' : DateTime,
        'date_modified'  : DateTime,
        'date_taken'     : DateTime,
        'description'    : MD_String,
        'dimension_x'    : MD_Int,
        'dimension_y'    : MD_Int,
        'focal_length'   : MD_Rational,
        'focal_length_35': MD_Int,
        'keywords'       : MultiString,
        'latlong'        : LatLon,
        'lens_make'      : MD_String,
        'lens_model'     : MD_String,
        'lens_serial'    : MD_String,
        'lens_spec'      : LensSpec,
        'location_shown' : MultiLocation,
        'location_taken' : Location,
        'orientation'    : Orientation,
        'rating'         : Rating,
        'resolution_x'   : MD_Rational,
        'resolution_y'   : MD_Rational,
        'resolution_unit': MD_Int,
        'software'       : Software,
        'thumbnail'      : Thumbnail,
        'timezone'       : Timezone,
        'title'          : MD_String,
        }

    def __init__(self, path, *args, **kw):
        super(Metadata, self).__init__(*args, **kw)
        # create metadata handlers for image file, video file, and sidecar
        self._path = path
        self._vf = None
        self._sc = SidecarMetadata.open_old(path)
        self._if = ImageMetadata.open_old(path)
        self.mime_type = self.get_mime_type()
        if self.mime_type.split('/')[0] == 'video':
            vhm = VideoHeaderMetadata.open_old(path)
            if vhm and self._if:
                vhm.merge_segment(self._if)
            self._if = vhm
            self._vf = FFMPEGMetadata.open_old(path)
        self.dirty = False

    @classmethod
    def clone(cls, path, other, *args, **kw):
        if other._if:
            # use exiv2 to clone image file metadata
            other._if.save_file(path)
        self = cls(path, *args, **kw)
        if other._sc and self._if:
            # merge in sidecar data
            self._if.merge_sc(other._sc)
        return self

    def save(self, if_mode=True, sc_mode='auto',
             force_iptc=False, file_times=None):
        if not self.dirty:
            return
        if (sc_mode == 'always' or not self._if) and not self._sc:
            self._sc = SidecarMetadata.open_new(self._path, self._if)
        self.software = 'Photini editor v' + __version__
        try:
            if self._if and sc_mode == 'delete' and self._sc:
                self._if.merge_sc(self._sc)
            if self._sc:
                # workaround for bug in exiv2 xmp timestamp altering
                self._sc.clear_dates()
            for handler in (self._sc, self._if):
                if not handler:
                    continue
                for name in self._data_type:
                    value = getattr(self, name)
                    handler.write(name, value)
            OK = False
            if self._if and if_mode:
                OK = self._if.save(file_times=file_times, force_iptc=force_iptc)
                if not OK and not self._sc:
                    # can't write to image so create side car
                    self.save(if_mode=False, sc_mode='always',
                              force_iptc=force_iptc, file_times=file_times)
                    return
            if sc_mode == 'delete' and self._sc and OK:
                self._sc = self._sc.delete()
            if self._sc:
                OK = self._sc.save(file_times=file_times)
        except Exception as ex:
            logger.exception(ex)
            return
        if OK:
            self.dirty = False
            self.unsaved.emit(self.dirty)

    def get_mime_type(self):
        result = None
        if self._if:
            result = self._if.get_mime_type()
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

    def __getattr__(self, name):
        if name not in self._data_type:
            raise AttributeError(
                "%s has no attribute %s" % (self.__class__, name))
        # read data values
        values = []
        for handler in self._sc, self._vf, self._if:
            if not handler:
                continue
            values = handler.read(name, self._data_type[name])
            if values:
                break
        # choose result and merge in non-matching data so user can review it
        result = None
        if values:
            info = '{}({})'.format(os.path.basename(self._path), name)
            tag, result = values.pop(0)
            logger.debug('%s: set from %s', info, tag)
        for tag, value in values:
            result = result.merge(info, tag, value)
        # merge in camera timezone if needed
        if (isinstance(result, DateTime) and
                            result.tz_offset is None and self.timezone):
            result = dict(result)
            result['tz_offset'] = self.timezone
            result = DateTime(result)
            logger.info('%s: merged camera timezone offset', info)
        # add value to object attributes so __getattr__ doesn't get
        # called again
        super(Metadata, self).__setattr__(name, result)
        return result

    def __setattr__(self, name, value):
        if name not in self._data_type:
            return super(Metadata, self).__setattr__(name, value)
        if value in (None, '', [], {}):
            value = None
        elif not isinstance(value, self._data_type[name]):
            value = self._data_type[name](value)
            if not value:
                value = None
        if getattr(self, name) == value:
            return
        super(Metadata, self).__setattr__(name, value)
        if not self.dirty:
            self.dirty = True
        self.unsaved.emit(self.dirty)

    def changed(self):
        return self.dirty
