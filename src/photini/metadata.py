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
from datetime import datetime
from fractions import Fraction
import locale
import logging
import math
import os
import re
import sys

import six

from photini import __version__
from photini.gi import gexiv2_version, GLib, GObject, GExiv2, using_pgi
from photini.pyqt import QtCore, QtGui

logger = logging.getLogger(__name__)

# pydoc gi.repository.GExiv2.Metadata is useful to see methods available

XMP_WRAPPER = '''<?xpacket begin="" id="W5M0MpCehiHzreSzNTczkc9d"?>
<x:xmpmeta xmlns:x="adobe:ns:meta/" x:xmptk="XMP Core 4.4.0-Exiv2">
  <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
    <rdf:Description rdf:about=""
      {}/>
  </rdf:RDF>
</x:xmpmeta>
<?xpacket end="w"?>'''

# Recent versions of Exiv2 have these namespaces defined, but older
# versions may not recognise them. The xapGImg URL is invalid, but
# Photini doesn't write xapGImg so it doesn't matter.
for prefix, name in (
        ('exifEX',  'http://cipa.jp/exif/1.0/'),
        ('video',   'http://www.video/'),
        ('xapGImg', 'http://ns.adobe.com/xxx/'),
        ('xmpGImg', 'http://ns.adobe.com/xap/1.0/g/img/')):
    GExiv2.Metadata.register_xmp_namespace(name, prefix)

# Gexiv2 won't register the 'Iptc4xmpExt' namespace as its abbreviated
# version 'iptcExt' is already defined. This kludge registers it by
# reading some data with the full namespace
data = XMP_WRAPPER.format(
    'xmlns:Iptc4xmpExt="http://iptc.org/std/Iptc4xmpExt/2008-02-29/"')
if six.PY2:
    data = data.decode('utf-8')
# open the data to register the namespace
GExiv2.Metadata().open_buf(data.encode('utf-8'))
del data


def safe_fraction(value):
    # Avoid ZeroDivisionError when '0/0' used for zero values in Exif
    if isinstance(value, six.string_types):
        numerator, sep, denominator = value.partition('/')
        if denominator and int(denominator) == 0:
            return Fraction(0.0)
    return Fraction(value).limit_denominator(1000000)

def decode_UCS2(value):
    value = bytearray(map(int, value.split()))
    return value.decode('utf_16', errors='ignore').strip('\x00')

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
        if self != other:
            self.log_ignored(info, tag, other)
        return self

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
        super(MD_Dict, self).__init__(dict.fromkeys(self._keys))
        # update with any supplied values
        self.update(value)

    def __getattr__(self, name):
        if name in self:
            return self[name]
        raise AttributeError(
            "{} has no attribute {}".format(self.__class__, name))

    def __setattr__(self, name, value):
        if name in self:
            self[name] = value
            return
        super(MD_Dict, self).__setattr__(name, value)

    def __bool__(self):
        return any([x is not None for x in self.values()])

    def merge(self, info, tag, other):
        if other == self:
            return self
        ignored = False
        result = MD_Dict(self)
        for key in result:
            if not other[key]:
                continue
            if not result[key]:
                result[key] = other[key]
            elif other[key] != result[key]:
                ignored = True
        if ignored:
            self.log_ignored(info, tag, other)
        else:
            self.log_merged(info, tag, other)
        return result


class LatLon(MD_Dict):
    # simple class to store latitude and longitude
    _keys = ('lat', 'lon')

    def __init__(self, value):
        super(LatLon, self).__init__(value)
        self.lat = round(float(self.lat), 6)
        self.lon = round(float(self.lon), 6)

    @classmethod
    def read(cls, handler, tag):
        file_value = handler.get_string(tag)
        if tag == 'Xmp.video.GPSCoordinates':
            if file_value:
                match = re.match(r'([-+]\d+\.\d+)([-+]\d+\.\d+)', file_value)
                if match:
                    return cls(match.group(1, 2))
            return None
        if not all(file_value):
            return None
        if handler.is_exif_tag(tag[0]):
            return cls((cls.from_exif_part(file_value[0], file_value[1]),
                        cls.from_exif_part(file_value[2], file_value[3])))
        else:
            return cls((cls.from_xmp_part(file_value[0]),
                        cls.from_xmp_part(file_value[1])))

    def write(self, handler, tag):
        if handler.is_exif_tag(tag[0]):
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

    def merge(self, info, tag, other):
        if max(abs(other.lat - self.lat), abs(other.lon - self.lon)) > 0.0000015:
            self.log_ignored(info, tag, other)
        return self


class Location(MD_Dict):
    # stores IPTC defined location heirarchy
    _keys = ('sublocation', 'city', 'province_state',
             'country_name', 'country_code', 'world_region')

    def __init__(self, value):
        super(Location, self).__init__(value)
        for key in self:
            if self[key] and not self[key].strip():
                self[key] = None
        if self.country_code:
            self.country_code = self.country_code.upper()

    @classmethod
    def read(cls, handler, tag):
        file_value = handler.get_string(tag)
        if not any(file_value):
            return None
        return cls(file_value)

    def write(self, handler, tag):
        handler.set_string(tag, [self[x] for x in self._keys])

    @classmethod
    def from_address(cls, address, key_map):
        result = cls({})
        for key in result:
            result[key] = []
        for key in key_map:
            for foreign_key in key_map[key]:
                if foreign_key not in address:
                    continue
                if key in result and address[foreign_key] not in result[key]:
                    result[key].append(address[foreign_key])
                del(address[foreign_key])
        # only use one country code
        result.country_code = result.country_code[:1]
        # put unknown foreign keys in sublocation
        for foreign_key in address:
            if address[foreign_key] in ' '.join(result['sublocation']):
                continue
            result['sublocation'] = [
                '{}: {}'.format(foreign_key, address[foreign_key])
                ] + result['sublocation']
        for key in result:
            result[key] = ', '.join(result[key]) or None
        return result

    def __str__(self):
        result = []
        for key in self._keys:
            if self[key]:
                result.append('{}: {}'.format(key, self[key]))
        return '\n'.join(result)

    def merge(self, info, tag, other):
        merged = False
        result = Location(self)
        for key in result:
            if not other[key]:
                continue
            if not result[key]:
                result[key] = other[key]
                merged = True
            elif other[key] not in result[key]:
                result[key] += ' // ' + other[key]
                merged = True
        if merged:
            self.log_merged(info, tag, other)
            return result
        return self


class MultiLocation(list):
    def __init__(self, value):
        temp = []
        for item in value:
            if not item:
                item  = None
            elif not isinstance(item, Location):
                item = Location(item)
            temp.append(item)
        while temp and not temp[-1]:
            temp = temp[:-1]
        super(MultiLocation, self).__init__(temp)

    @staticmethod
    def tag_n(tag, n):
        result = []
        for sub_tag in tag:
            result.append(sub_tag.replace('1', str(n)))
        return tuple(result)

    @classmethod
    def read(cls, handler, tag):
        value = []
        count = 1
        while True:
            file_value = Location.read(handler, cls.tag_n(tag, count))
            if file_value is None:
                break
            value.append(file_value)
            count += 1
        return cls(value)

    def write(self, handler, tag):
        # ignore empty values at end of list
        count = len(self)
        while count > 0 and not self[count - 1]:
            count -= 1
        # delete file values beyond end of list
        file_count = count
        while Location.read(
                handler, self.tag_n(tag, file_count + 1)) is not None:
            file_count += 1
        while file_count > count:
            handler.clear_value(self.tag_n(tag, file_count))
            file_count -= 1
        # save list values
        for n in range(count):
            tag_n = self.tag_n(tag, n + 1)
            if self[n]:
                self[n].write(handler, tag_n)
            else:
                handler.clear_value(tag_n)
                # save placeholder
                handler.set_string(tag_n[0], ' ')

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

    def __init__(self, value):
        super(LensSpec, self).__init__(value)
        self.min_fl = safe_fraction(self.min_fl)
        self.max_fl = safe_fraction(self.max_fl)
        self.min_fl_fn = safe_fraction(self.min_fl_fn)
        self.max_fl_fn = safe_fraction(self.max_fl_fn)

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
                data = bytes(data, 'ASCII')
            data = codecs.decode(data, 'base64_codec')
            w = int(w)
            h = int(h)
        else:
            data = handler.get_exif_thumbnail()
            if not data:
                return None
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
            if self.fmt != 'JPEG':
                pixmap = QtGui.QPixmap()
                pixmap.loadFromData(data)
                buf = QtCore.QBuffer()
                buf.open(QtCore.QIODevice.WriteOnly)
                pixmap.save(buf, 'JPEG')
                data = buf.data().data()
                self.w = pixmap.width()
                self.h = pixmap.height()
            if not self.w or not self.h:
                pixmap = QtGui.QPixmap()
                pixmap.loadFromData(data)
                self.w = pixmap.width()
                self.h = pixmap.height()
            data = codecs.encode(data, 'base64_codec')
            if not six.PY2:
                data = data.decode('ASCII')
            handler.set_string(tag, (data, 'JPEG', str(self.w), str(self.h)))
        elif handler.get_supports_exif():
            handler.set_exif_thumbnail_from_buffer(self.data)

    def __str__(self):
        return '{} thumbnail, {}x{}'.format(self.fmt, self.w, self.h)


class DateTime(MD_Dict):
    # store date and time with "precision" to store how much is valid
    # tz_offset is stored in minutes
    _keys = ('datetime', 'precision', 'tz_offset')

    def __init__(self, value):
        super(DateTime, self).__init__(value)
        if not self.datetime:
            # use a well known 'zero'
            self.datetime = datetime(1970, 1, 1)
        else:
            self.datetime = self.truncate_datetime(self.precision)
        if self.precision <= 3:
            self.tz_offset = None

    _replace = (('microsecond', 0), ('second', 0),
                ('minute',      0), ('hour',   0),
                ('day',         1), ('month',  1))

    def truncate_datetime(self, precision):
        return self.datetime.replace(**dict(self._replace[:7 - precision]))

    _fmt_elements = ('%Y', '-%m', '-%d', 'T%H', ':%M', ':%S', '.%f')

    @classmethod
    def from_ISO_8601(cls, datetime_string):
        """Sufficiently general ISO 8601 parser.

        Input must be in "extended" format, i.e. with separators.
        See https://en.wikipedia.org/wiki/ISO_8601

        """
        # extract time zone
        if 'T' in datetime_string and datetime_string[-6] in ('+', '-'):
            tz_offset = int(datetime_string[-2:]) + (
                        int(datetime_string[-5:-3]) * 60)
            if datetime_string[-6] == '-':
                tz_offset = -tz_offset
            datetime_string = datetime_string[:-6]
        elif 'T' in datetime_string and datetime_string[-1] == 'Z':
            tz_offset = 0
            datetime_string = datetime_string[:-1]
        else:
            tz_offset = None
        precision = min((len(datetime_string) - 1) // 3, 7)
        if precision <= 0:
            return None
        fmt = ''.join(cls._fmt_elements[:precision])
        return cls(
            (datetime.strptime(datetime_string, fmt), precision, tz_offset))

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
        if handler.is_exif_tag(tag):
            return cls.from_exif(file_value)
        if handler.is_iptc_tag(tag):
            return cls.from_iptc(file_value)
        if tag.startswith('Xmp.video'):
            try:
                time_stamp = int(file_value)
            except ValueError:
                return None
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

    # Exif datetime is always full resolution and valid. Assume a time
    # of 00:00:00 is a None value though.
    @classmethod
    def from_exif(cls, file_value):
        datetime_string = file_value[0]
        if not datetime_string:
            return None
        date_string = datetime_string[:10].replace(':', '-')
        time_string = datetime_string[11:]
        # append sub seconds
        if len(file_value) > 1:
            sub_sec_string = file_value[1]
            if sub_sec_string:
                sub_sec_string = sub_sec_string.strip()
            if sub_sec_string:
                time_string += '.' + sub_sec_string
        # check for no time
        if time_string == '00:00:00':
            datetime_string = date_string
        else:
            datetime_string = date_string + 'T' + time_string
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
        return cls.from_ISO_8601(file_value)

    def to_xmp(self):
        precision = self.precision
        if precision == 4:
            precision = 5
        return self.to_ISO_8601(precision=precision)

    def __str__(self):
        return self.to_ISO_8601()

    def merge(self, info, tag, other):
        if other == self:
            return self
        merged = False
        result = DateTime(self)
        if other.datetime != result.datetime:
            # if datetime values differ, choose the one with more precision
            if other.precision > result.precision:
                self.log_replaced(info, tag, other)
                return other
            if other.datetime != result.truncate_datetime(other.precision):
                self.log_ignored(info, tag, other)
                return self
        else:
            # some formats default to a higher precision than wanted
            if result.precision < 7 and other.precision < result.precision:
                result.precision = other.precision
                merged = True
        # don't trust IPTC time zone and Exif doesn't have time zone
        if (other.tz_offset not in (None, result.tz_offset) and
                MetadataHandler.is_xmp_tag(tag)):
            result.tz_offset = other.tz_offset
            merged = True
        if merged:
            self.log_merged(info, tag, other)
            return result
        return self


class MultiString(MD_Value, list):
    def __init__(self, value):
        if isinstance(value, six.string_types):
            value = value.split(';')
        value = filter(bool, [x.strip() for x in value])
        super(MultiString, self).__init__(value)

    @classmethod
    def read(cls, handler, tag):
        if handler.get_tag_type(tag) in ('String', 'XmpBag', 'XmpSeq'):
            file_value = handler.get_multiple(tag)
        else:
            file_value = handler.get_string(tag)
        if not file_value:
            return None
        if handler.get_tag_type(tag) == 'Byte':
            file_value = decode_UCS2(file_value)
        return cls(file_value)

    def write(self, handler, tag):
        if handler.is_exif_tag(tag):
            handler.set_string(tag, ';'.join(self))
        elif handler.get_tag_type(tag) in ('String', 'XmpBag', 'XmpSeq'):
            handler.set_multiple(tag, self)
        else:
            handler.set_string(tag, self)

    def __str__(self):
        return '; '.join(self)

    def merge(self, info, tag, other):
        merged = False
        result = MultiString(self)
        for item in other:
            if item not in result:
                result.append(item)
                merged = True
        if merged:
            self.log_merged(info, tag, other)
            return result
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
        if file_value and handler.get_tag_type(tag) == 'Byte':
            file_value = decode_UCS2(file_value)
        if file_value:
            file_value = six.text_type(file_value).strip()
        if not file_value:
            return None
        return cls(file_value)

    def write(self, handler, tag):
        handler.set_string(tag, self)

    def merge(self, info, tag, other):
        if other in self:
            return self
        self.log_merged(info, tag, other)
        return MD_String(self + ' // ' + other)


class CharacterSet(MD_String):
    known_encodings = {
        'ascii'   : '\x1b(B',
        'latin_1' : '\x1b/A',
        'latin1'  : '\x1b.A',
        'utf_8'   : '\x1b%G',
        }

    @classmethod
    def read(cls, handler, tag):
        file_value = handler.get_string(tag)
        for charset, encoding in cls.known_encodings.items():
            if encoding == file_value:
                return cls(charset)
        if file_value:
            logger.warning('Unknown character encoding "%s"', repr(file_value))
        return None

    def write(self, handler, tag):
        handler.set_string(tag, self.known_encodings[self])


class Software(MD_String):
    @classmethod
    def read(cls, handler, tag):
        file_value = handler.get_string(tag)
        if isinstance(file_value, list):
            program, version = file_value
            if not program:
                return None
            if version:
                program += ' v' + version
            return cls(program)
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
    @classmethod
    def read(cls, handler, tag):
        file_value = handler.get_string(tag)
        if not file_value:
            return None
        return cls(safe_fraction(file_value))

    def write(self, handler, tag):
        handler.set_string(
            tag, '{:d}/{:d}'.format(self.numerator, self.denominator))

    def __str__(self):
        return six.text_type(float(self))


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
        f_number = safe_fraction(f_number)
        self = cls(f_number)
        if apex:
            self.apex = apex
        return self

    def write(self, handler, tag):
        apex = getattr(self, 'apex', safe_fraction(math.log(self, 2) * 2.0))
        handler.set_string(tag, (
            '{:d}/{:d}'.format(self.numerator, self.denominator),
            '{:d}/{:d}'.format(apex.numerator, apex.denominator)))

    def merge(self, info, tag, other):
        if (min(other, self) / max(other, self)) < 0.95:
            self.log_ignored(info, tag, other)
        return self


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


# maximum length of Iptc data
_max_bytes = {
    'Iptc.Application2.Byline'           :   32,
    'Iptc.Application2.Caption'          : 2000,
    'Iptc.Application2.City'             :   32,
    'Iptc.Application2.Copyright'        :  128,
    'Iptc.Application2.CountryCode'      :    3,
    'Iptc.Application2.CountryName'      :   64,
    'Iptc.Application2.Headline'         :  256,
    'Iptc.Application2.Keywords'         :   64,
    'Iptc.Application2.ObjectName'       :   64,
    'Iptc.Application2.Program'          :   32,
    'Iptc.Application2.ProgramVersion'   :   10,
    'Iptc.Application2.ProvinceState'    :   32,
    'Iptc.Application2.SubLocation'      :   32,
    'Iptc.Envelope.CharacterSet'         :   32,
    }

_repeatable = (
    'Iptc.Application2.Byline',
    'Iptc.Application2.BylineTitle',
    'Iptc.Application2.Contact',
    'Iptc.Application2.Keywords',
    'Iptc.Application2.LocationCode',
    'Iptc.Application2.LocationName',
    'Iptc.Application2.ObjectAttribute',
    'Iptc.Application2.ReferenceNumber',
    'Iptc.Application2.ReferenceService',
    'Iptc.Application2.Subject',
    'Iptc.Application2.SuppCategory',
    'Iptc.Application2.Writer',
    'Iptc.Envelope.Destination',
    'Iptc.Envelope.ProductId',
    )

if gexiv2_version >= (0, 10, 3):
    _xmp_struct_type = {
        'Xmp.iptcExt.LocationCreated': GExiv2.StructureType.BAG,
        'Xmp.iptcExt.LocationShown'  : GExiv2.StructureType.BAG,
        'Xmp.xmp.Thumbnails'         : GExiv2.StructureType.ALT,
        }

class MetadataHandler(GExiv2.Metadata):
    def __init__(self, path):
        super(MetadataHandler, self).__init__()
        self._path = path
        # read metadata from file
        self.open_path(self._path)
        self._xmp_only = self.get_mime_type() in (
            'application/rdf+xml', 'application/postscript')
        # make list of possible character encodings
        self._encodings = []
        for name in ('utf_8', 'latin_1'):
            self._encodings.append(codecs.lookup(name).name)
        char_set = locale.getdefaultlocale()[1]
        if char_set:
            try:
                name = codecs.lookup(char_set).name
                if name not in self._encodings:
                    self._encodings.append(name)
            except LookupError:
                pass
        # convert IPTC data to UTF-8
        if not self.has_iptc():
            return
        current_encoding = CharacterSet.read(self, 'Iptc.Envelope.CharacterSet')
        if current_encoding:
            if current_encoding == 'utf_8':
                return
            try:
                name = codecs.lookup(current_encoding).name
                if name not in self._encodings:
                    self._encodings.insert(0, name)
            except LookupError:
                pass
        for tag in self.get_iptc_tags():
            if self.get_tag_type(tag) == 'String':
                try:
                    if tag in _repeatable:
                        self.set_multiple(tag, self.get_multiple(tag))
                    else:
                        self.set_string(tag, self.get_string(tag))
                except Exception as ex:
                    logger.exception(ex)

    def _decode_string(self, value):
        if not value:
            return value
        for encoding in self._encodings:
            try:
                return value.decode(encoding)
            except UnicodeDecodeError:
                continue
        return value.decode('utf_8', 'replace')

    _parse_xmp_struct = re.compile('(.+?)(?:\[(\d+)\])?/')

    def clear_value(self, tag):
        if isinstance(tag, tuple):
            for sub_tag in tag:
                self.clear_value(sub_tag)
            return
        if not self.has_tag(tag):
            return
        self.clear_tag(tag)
        if self.is_xmp_tag(tag) and '/' in tag:
            # GExiv2 won't delete container, so leave a value in it
            match = self._parse_xmp_struct.match(tag)
            if match:
                bag = match.group(1)
                for t in self.get_xmp_tags():
                    if t.startswith(bag):
                        # container is not empty
                        break
                else:
                    self.set_tag_string(tag, ' ')

    def get_raw(self, tag):
        try:
            if gexiv2_version < (0, 10, 3):
                return None
            result = self.get_tag_raw(tag).get_data()
            if not result:
                return None
            if isinstance(result, list):
                # pgi returns a list of ints, or ctypes pointers in some versions
                if isinstance(result[0], int):
                    result = bytearray(result)
                else:
                    # some other type we can't handle
                    logger.info('Unknown data type %s in tag %s',
                                type(result[0]), tag)
                    return None
        except Exception as ex:
            logger.exception(ex)
            return None
        return result

    _charset_map = {
        'ascii'  : 'ascii',
        'unicode': 'utf_16',
        'jis'    : 'euc_jp',
        }

    def get_string(self, tag):
        if isinstance(tag, tuple):
            return [self.get_string(x) for x in tag]
        if not self.has_tag(tag):
            return None
        if self.get_tag_type(tag) == 'Comment':
            result = self.get_raw(tag)
            if not result:
                return None
            charset = result[:8].decode(
                'ascii', 'replace').strip('\x00').lower()
            if charset in self._charset_map:
                result = result[8:].decode(self._charset_map[charset])
            elif charset == '':
                result = self._decode_string(result[8:])
            else:
                result = result.decode('ascii', 'replace')
            return result.strip('\x00')
        try:
            result = self.get_tag_string(tag)
            if six.PY2:
                result = self._decode_string(result)
            return result
        except UnicodeDecodeError as ex:
            pass
        # attempt to read raw data instead
        result = self.get_raw(tag)
        if not result:
            return None
        return self._decode_string(result).strip('\x00')

    def get_multiple(self, tag):
        if isinstance(tag, tuple):
            return [self.get_multiple(x) for x in tag]
        if not self.has_tag(tag):
            return []
        if not six.PY2 and not using_pgi and self.is_iptc_tag(tag):
            # PyGObject segfaults if strings are not utf8
            return [self.get_string(tag)]
        try:
            result = self.get_tag_multiple(tag)
            if six.PY2:
                result = list(map(self._decode_string, result))
            return result
        except UnicodeDecodeError as ex:
            pass
        # attempt to read raw data instead, only gets the first value
        result = self.get_raw(tag)
        if not result:
            return []
        return [self._decode_string(result).strip('\x00')]

    def set_string(self, tag, value):
        if isinstance(tag, tuple):
            for sub_tag, sub_value in zip(tag, value):
                self.set_string(sub_tag, sub_value)
            return
        if not value:
            self.clear_value(tag)
            return
        if tag in _max_bytes:
            value = value.encode('utf_8')[:_max_bytes[tag]]
            if not six.PY2:
                value = value.decode('utf_8', errors='ignore')
        elif six.PY2:
            value = value.encode('utf_8')
        if self.is_xmp_tag(tag) and '/' in tag:
            # create XMP structure/container
            match = self._parse_xmp_struct.match(tag)
            if match:
                bag = match.group(1)
                for t in self.get_xmp_tags():
                    if t.startswith(bag):
                        # container already exists
                        break
                else:
                    if gexiv2_version >= (0, 10, 3):
                        self.set_xmp_tag_struct(bag, _xmp_struct_type[bag])
                    else:
                        super(MetadataHandler, self).set_tag_string(bag, '')
        self.set_tag_string(tag, value)

    def set_multiple(self, tag, value):
        if isinstance(tag, tuple):
            for sub_tag, sub_value in zip(tag, value):
                self.set_multiple(sub_tag, sub_value)
            return
        if not value:
            self.clear_value(tag)
            return
        if self.is_iptc_tag(tag) and tag in _max_bytes:
            value = [x.encode('utf_8')[:_max_bytes[tag]] for x in value]
            if not six.PY2:
                value = [x.decode('utf_8') for x in value]
        elif six.PY2:
            value = [x.encode('utf_8') for x in value]
        self.set_tag_multiple(tag, value)

    @staticmethod
    def is_exif_tag(tag):
        if isinstance(tag, tuple):
            tag = tag[0]
        return GExiv2.Metadata.is_exif_tag(tag)

    @staticmethod
    def is_iptc_tag(tag):
        if isinstance(tag, tuple):
            tag = tag[0]
        return GExiv2.Metadata.is_iptc_tag(tag)

    @staticmethod
    def is_xmp_tag(tag):
        if isinstance(tag, tuple):
            tag = tag[0]
        return GExiv2.Metadata.is_xmp_tag(tag)

    def get_supports_exif(self):
        if self._xmp_only:
            return False
        return super(MetadataHandler, self).get_supports_exif()

    def get_supports_iptc(self):
        if self._xmp_only:
            return False
        return super(MetadataHandler, self).get_supports_iptc()

    def has_iptc(self):
        if self._xmp_only:
            return False
        return super(MetadataHandler, self).has_iptc()

    def save(self, file_times):
        # don't try to save to unwritable formats
        if not (self.get_supports_xmp() or self.get_supports_exif()):
            return False
        try:
            self.save_file(self._path)
            if file_times:
                os.utime(self._path, file_times)
        except Exception as ex:
            logger.exception(ex)
            return False
        return True

    def merge_sc(self, other):
        # merge sidecar data into image file data, ignoring thumbnails
        # allow exiv2 to infer Exif tags from XMP
        for tag in other.get_exif_tags():
            if tag.startswith('Exif.Thumbnail'):
                continue
            # ignore inferred datetime values the exiv2 gets wrong
            # (I think it's adding the local timezone offset)
            if tag in ('Exif.Image.DateTime', 'Exif.Photo.DateTimeOriginal',
                       'Exif.Photo.DateTimeDigitized'):
                self.clear_tag(tag)
            else:
                self.set_string(tag, other.get_string(tag))
        # copy all XMP tags except inferred Exif tags
        for tag in other.get_xmp_tags():
            if tag.startswith('Xmp.xmp.Thumbnails'):
                continue
            ns = tag.split('.')[1]
            if ns in ('exif', 'exifEX', 'tiff', 'aux'):
                # exiv2 will already have supplied the equivalent Exif tag
                pass
            elif self.get_tag_type(tag) == 'XmpText':
                self.set_string(tag, other.get_string(tag))
            else:
                self.set_multiple(tag, other.get_multiple(tag))

    def get_all_tags(self):
        return self.get_exif_tags() + self.get_iptc_tags() + self.get_xmp_tags()

    def get_exif_thumbnail(self):
        thumb = super(MetadataHandler, self).get_exif_thumbnail()
        if using_pgi and isinstance(thumb, tuple):
            # get_exif_thumbnail returns (OK, data) tuple
            thumb = thumb[thumb[0]]
        if thumb:
            return bytearray(thumb)
        return None


class Metadata(QtCore.QObject):
    unsaved = QtCore.pyqtSignal(bool)

    # type of each Photini data field's data
    _data_type = {
        'aperture'       : Aperture,
        'camera_model'   : MD_String,
        'character_set'  : CharacterSet,
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
        'orientation'    : MD_Int,
        'rating'         : Rating,
        'resolution_x'   : MD_Rational,
        'resolution_y'   : MD_Rational,
        'resolution_unit': MD_Int,
        'software'       : Software,
        'thumbnail'      : Thumbnail,
        'timezone'       : Timezone,
        'title'          : MD_String,
        }
    # Mapping of tags to Photini data fields Each field has a list of
    # (mode, tag) pairs, where tag can be a tuple of tags. The mode is a
    # string containing the read mode (RA (always), or RN (never)) and
    # write mode (WA (always), WX (if Exif not supported), W0 (clear the
    # tag), or WN (never).
    _tag_list = {
        'aperture'       : (('RA.WA', ('Exif.Photo.FNumber',
                                       'Exif.Photo.ApertureValue')),
                            ('RA.W0', ('Exif.Image.FNumber',
                                       'Exif.Image.ApertureValue')),
                            ('RA.WX', ('Xmp.exif.FNumber',
                                       'Xmp.exif.ApertureValue'))),
        'camera_model'   : (('RA.WN', 'Exif.Image.Model'),
                            ('RA.WN', 'Exif.Image.UniqueCameraModel'),
                            ('RA.WN', 'Xmp.video.Model')),
        'character_set'  : (('RA.WA', 'Iptc.Envelope.CharacterSet'),),
        'copyright'      : (('RA.WA', 'Exif.Image.Copyright'),
                            ('RA.WA', 'Xmp.dc.rights'),
                            ('RA.W0', 'Xmp.tiff.Copyright'),
                            ('RA.WA', 'Iptc.Application2.Copyright')),
        'creator'        : (('RA.WA', 'Exif.Image.Artist'),
                            ('RA.W0', 'Exif.Image.XPAuthor'),
                            ('RA.WA', 'Xmp.dc.creator'),
                            ('RA.W0', 'Xmp.tiff.Artist'),
                            ('RA.WA', 'Iptc.Application2.Byline')),
        'date_digitised' : (('RA.WA', ('Exif.Photo.DateTimeDigitized',
                                       'Exif.Photo.SubSecTimeDigitized')),
                            ('RA.WA', 'Xmp.xmp.CreateDate'),
                            ('RA.W0', 'Xmp.exif.DateTimeDigitized'),
                            ('RA.WN', 'Xmp.video.DateUTC'),
                            ('RA.WA', ('Iptc.Application2.DigitizationDate',
                                       'Iptc.Application2.DigitizationTime'))),
        'date_modified'  : (('RA.WA', ('Exif.Image.DateTime',
                                       'Exif.Photo.SubSecTime')),
                            ('RA.WA', 'Xmp.xmp.ModifyDate'),
                            ('RA.WN', 'Xmp.video.ModificationDate'),
                            ('RA.W0', 'Xmp.tiff.DateTime')),
        'date_taken'     : (('RA.WA', ('Exif.Photo.DateTimeOriginal',
                                       'Exif.Photo.SubSecTimeOriginal')),
                            ('RA.W0', ('Exif.Image.DateTimeOriginal',)),
                            ('RA.WA', 'Xmp.photoshop.DateCreated'),
                            ('RA.W0', 'Xmp.exif.DateTimeOriginal'),
                            ('RA.WN', 'Xmp.video.DateUTC'),
                            ('RA.WA', ('Iptc.Application2.DateCreated',
                                       'Iptc.Application2.TimeCreated'))),
        'description'    : (('RA.WA', 'Exif.Image.ImageDescription'),
                            ('RA.W0', 'Exif.Image.XPComment'),
                            ('RA.W0', 'Exif.Image.XPSubject'),
                            ('RA.W0', 'Exif.Photo.UserComment'),
                            ('RA.WA', 'Xmp.dc.description'),
                            ('RA.W0', 'Xmp.tiff.ImageDescription'),
                            ('RA.WA', 'Iptc.Application2.Caption')),
        'dimension_x'    : (('RA.WN', 'Exif.Image.ImageWidth'),
                            ('RA.WN', 'Exif.Photo.PixelXDimension'),
                            ('RA.WN', 'Xmp.tiff.ImageWidth'),
                            ('RA.WN', 'Xmp.exif.PixelXDimension')),
        'dimension_y'    : (('RA.WN', 'Exif.Image.ImageLength'),
                            ('RA.WN', 'Exif.Photo.PixelYDimension'),
                            ('RA.WN', 'Xmp.tiff.ImageLength'),
                            ('RA.WN', 'Xmp.exif.PixelYDimension')),
        'focal_length'   : (('RA.WA', 'Exif.Photo.FocalLength'),
                            ('RA.W0', 'Exif.Image.FocalLength'),
                            ('RA.WX', 'Xmp.exif.FocalLength')),
        'focal_length_35': (('RA.WA', 'Exif.Photo.FocalLengthIn35mmFilm'),
                            ('RA.WX', 'Xmp.exif.FocalLengthIn35mmFilm')),
        'keywords'       : (('RA.WA', 'Xmp.dc.subject'),
                            ('RA.WA', 'Iptc.Application2.Keywords'),
                            ('RA.W0', 'Exif.Image.XPKeywords')),
        'latlong'        : (('RA.WA', ('Exif.GPSInfo.GPSLatitude',
                                       'Exif.GPSInfo.GPSLatitudeRef',
                                       'Exif.GPSInfo.GPSLongitude',
                                       'Exif.GPSInfo.GPSLongitudeRef')),
                            ('RA.WX', ('Xmp.exif.GPSLatitude',
                                       'Xmp.exif.GPSLongitude')),
                            ('RA.WN', 'Xmp.video.GPSCoordinates')),
        'lens_make'      : (('RA.WA', 'Exif.Photo.LensMake'),
                            ('RA.WX', 'Xmp.exifEX.LensMake')),
        'lens_model'     : (('RA.WA', 'Exif.Photo.LensModel'),
                            ('RA.WX', 'Xmp.exifEX.LensModel'),
                            ('RA.W0', 'Exif.Canon.LensModel'),
                            ('RA.W0', 'Exif.OlympusEq.LensModel'),
                            ('RA.W0', 'Xmp.aux.Lens'),
                            ('RN.W0', 'Exif.CanonCs.LensType')),
        'lens_serial'    : (('RA.WA', 'Exif.Photo.LensSerialNumber'),
                            ('RA.WX', 'Xmp.exifEX.LensSerialNumber'),
                            ('RA.W0', 'Exif.OlympusEq.LensSerialNumber'),
                            ('RA.W0', 'Xmp.aux.SerialNumber')),
        'lens_spec'      : (('RA.WA', 'Exif.Photo.LensSpecification'),
                            ('RA.WX', 'Xmp.exifEX.LensSpecification'),
                            ('RA.W0', 'Exif.Image.LensInfo'),
                            ('RA.W0', 'Exif.CanonCs.Lens'),
                            ('RA.W0', 'Exif.Nikon3.Lens'),
                            ('RN.W0', 'Exif.CanonCs.ShortFocal'),
                            ('RN.W0', 'Exif.CanonCs.MaxAperture'),
                            ('RN.W0', 'Exif.CanonCs.MinAperture')),
        'location_shown' : (
            ('RA.WA', ('Xmp.iptcExt.LocationShown[1]/Iptc4xmpExt:Sublocation',
                       'Xmp.iptcExt.LocationShown[1]/Iptc4xmpExt:City',
                       'Xmp.iptcExt.LocationShown[1]/Iptc4xmpExt:ProvinceState',
                       'Xmp.iptcExt.LocationShown[1]/Iptc4xmpExt:CountryName',
                       'Xmp.iptcExt.LocationShown[1]/Iptc4xmpExt:CountryCode',
                       'Xmp.iptcExt.LocationShown[1]/Iptc4xmpExt:WorldRegion',
                       'Xmp.iptcExt.LocationShown[1]/Iptc4xmpExt:LocationId')),),
        'location_taken' : (
            ('RA.WA', ('Xmp.iptcExt.LocationCreated[1]/Iptc4xmpExt:Sublocation',
                       'Xmp.iptcExt.LocationCreated[1]/Iptc4xmpExt:City',
                       'Xmp.iptcExt.LocationCreated[1]/Iptc4xmpExt:ProvinceState',
                       'Xmp.iptcExt.LocationCreated[1]/Iptc4xmpExt:CountryName',
                       'Xmp.iptcExt.LocationCreated[1]/Iptc4xmpExt:CountryCode',
                       'Xmp.iptcExt.LocationCreated[1]/Iptc4xmpExt:WorldRegion',
                       'Xmp.iptcExt.LocationCreated[1]/Iptc4xmpExt:LocationId')),
            ('RA.WA', ('Xmp.iptc.Location',
                       'Xmp.photoshop.City',
                       'Xmp.photoshop.State',
                       'Xmp.photoshop.Country',
                       'Xmp.iptc.CountryCode')),
            ('RA.WA', ('Iptc.Application2.SubLocation',
                       'Iptc.Application2.City',
                       'Iptc.Application2.ProvinceState',
                       'Iptc.Application2.CountryName',
                       'Iptc.Application2.CountryCode'))),
        'orientation'    : (('RA.WA', 'Exif.Image.Orientation'),
                            ('RA.WX', 'Xmp.tiff.Orientation')),
        'rating'         : (('RA.WA', 'Xmp.xmp.Rating'),
                            ('RA.W0', 'Exif.Image.Rating'),
                            ('RA.W0', 'Exif.Image.RatingPercent'),
                            ('RA.W0', 'Xmp.MicrosoftPhoto.Rating')),
        'resolution_x'   : (('RA.WN', 'Exif.Image.FocalPlaneXResolution'),
                            ('RA.WN', 'Exif.Photo.FocalPlaneXResolution'),
                            ('RA.WN', 'Xmp.exif.FocalPlaneXResolution')),
        'resolution_y'   : (('RA.WN', 'Exif.Image.FocalPlaneYResolution'),
                            ('RA.WN', 'Exif.Photo.FocalPlaneYResolution'),
                            ('RA.WN', 'Xmp.exif.FocalPlaneYResolution')),
        'resolution_unit': (('RA.WN', 'Exif.Image.FocalPlaneResolutionUnit'),
                            ('RA.WN', 'Exif.Photo.FocalPlaneResolutionUnit'),
                            ('RA.WN', 'Xmp.exif.FocalPlaneResolutionUnit')),
        'software'       : (('RA.WA', 'Exif.Image.ProcessingSoftware'),
                            ('RA.WA', ('Iptc.Application2.Program',
                                       'Iptc.Application2.ProgramVersion'))),
        # Both xmpGImg and xapGImg namespaces are specified in different
        # Adobe documents I've seen. xmpGImg appears to be more recent,
        # so we write that but read either.
        'thumbnail'      : (('RA.WA', 'Exif.Thumbnail.Compression'),
                            ('RA.WX', ('Xmp.xmp.Thumbnails[1]/xmpGImg:image',
                                       'Xmp.xmp.Thumbnails[1]/xmpGImg:format',
                                       'Xmp.xmp.Thumbnails[1]/xmpGImg:width',
                                       'Xmp.xmp.Thumbnails[1]/xmpGImg:height')),
                            ('RA.W0', ('Xmp.xmp.Thumbnails[1]/xapGImg:image',
                                       'Xmp.xmp.Thumbnails[1]/xapGImg:format',
                                       'Xmp.xmp.Thumbnails[1]/xapGImg:width',
                                       'Xmp.xmp.Thumbnails[1]/xapGImg:height'))),
        'timezone'       : (('RA.WN', 'Exif.Image.TimeZoneOffset'),
                            ('RA.WN', 'Exif.CanonTi.TimeZone'),
                            ('RA.WN', 'Exif.NikonWt.Timezone')),
        'title'          : (('RA.WA', 'Xmp.dc.title'),
                            ('RA.WA', 'Iptc.Application2.ObjectName'),
                            ('RA.W0', 'Exif.Image.XPTitle'),
                            ('RA.W0', 'Iptc.Application2.Headline')),
        }
    def __init__(self, path, *args, **kw):
        super(Metadata, self).__init__(*args, **kw)
        # create metadata handlers for image file and/or sidecar
        self._path = path
        self._sc_path = self._find_side_car(path)
        self._sc = None
        if self._sc_path:
            try:
                self._sc = MetadataHandler(self._sc_path)
            except Exception as ex:
                logger.exception(ex)
        self._if = None
        try:
            self._if = MetadataHandler(path)
        except GLib.Error:
            # expected if unrecognised file format
            pass
        except Exception as ex:
            logger.exception(ex)
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

    def _find_side_car(self, path):
        for base in (os.path.splitext(path)[0], path):
            for ext in ('.xmp', '.XMP'):
                result = base + ext
                if os.path.exists(result):
                    return result
        return None

    def create_side_car(self):
        self._sc_path = self._path + '.xmp'
        try:
            with open(self._sc_path, 'w') as of:
                of.write(XMP_WRAPPER.format(
                    'xmlns:xmp="http://ns.adobe.com/xap/1.0/"'))
            if self._if:
                # let exiv2 copy as much metadata as it can into sidecar
                self._if.save_file(self._sc_path)
            self._sc = MetadataHandler(self._sc_path)
            self._sc.set_string(
                'Xmp.xmp.CreatorTool', 'Photini editor v' + __version__)
        except Exception as ex:
            logger.exception(ex)
            self._sc = None

    def save(self, if_mode=True, sc_mode='auto',
             force_iptc=False, file_times=None):
        if not self.dirty:
            return
        if (sc_mode == 'always' or not self._if) and not self._sc:
            self.create_side_car()
        self.software = 'Photini editor v' + __version__
        self.character_set = 'utf_8'
        try:
            if self._if and sc_mode == 'delete' and self._sc:
                self._if.merge_sc(self._sc)
            if self._sc:
                # workaround for bug in exiv2 xmp timestamp altering
                for name in ('date_digitised', 'date_modified', 'date_taken'):
                    for mode, tag in self._tag_list[name]:
                        if mode in ('RA.WA', 'RA.W0'):
                            self._sc.clear_value(tag)
                self._sc.save(file_times)
            for handler in (self._sc, self._if):
                if not handler:
                    continue
                omit_exif = not handler.get_supports_exif()
                omit_iptc = not (handler.get_supports_iptc() and
                                 (force_iptc or handler.has_iptc()))
                for name in self._tag_list:
                    value = getattr(self, name)
                    for mode, tag in self._tag_list[name]:
                        if ((omit_exif and handler.is_exif_tag(tag)) or
                            (omit_iptc and handler.is_iptc_tag(tag))):
                            handler.clear_value(tag)
                            continue
                        write_mode = mode.split('.')[1]
                        if write_mode == 'WN':
                            continue
                        if ((not value) or (write_mode == 'W0') or
                            (write_mode == 'WX' and handler.get_supports_exif())):
                            handler.clear_value(tag)
                        else:
                            value.write(handler, tag)
            OK = False
            if self._if and if_mode:
                OK = self._if.save(file_times)
                if OK:
                    # check that data really was saved
                    saved_tags = MetadataHandler(self._path).get_all_tags()
                    for tag in self._if.get_all_tags():
                        if tag in ('Exif.Image.GPSTag',):
                            # some tags disappear with good reason
                            continue
                        if tag not in saved_tags:
                            logger.warning('tag not saved: %s', tag)
                            OK = False
                if not OK and not self._sc:
                    # can't write to image so create side car
                    self.save(if_mode=False, sc_mode='always',
                              force_iptc=force_iptc, file_times=file_times)
                    return
            if sc_mode == 'delete' and self._sc and OK:
                os.unlink(self._sc_path)
                self._sc = None
            if self._sc:
                OK = self._sc.save(file_times)
        except Exception as ex:
            logger.exception(ex)
            return
        if OK:
            self.dirty = False
            self.unsaved.emit(self.dirty)

    def get_mime_type(self):
        if self._if:
            return self._if.get_mime_type()
        return None

    def __getattr__(self, name):
        if name not in self._tag_list:
            raise AttributeError(
                "%s has no attribute %s" % (self.__class__, name))
        # read data values
        values = []
        for handler in self._sc, self._if:
            if not handler:
                continue
            omit_exif = not handler.get_supports_exif()
            omit_iptc = not handler.get_supports_iptc()
            for mode, tag in self._tag_list[name]:
                if mode.split('.')[0] == 'RN':
                    continue
                if ((omit_exif and handler.is_exif_tag(tag)) or
                    (omit_iptc and handler.is_iptc_tag(tag))):
                    continue
                try:
                    new_value = self._data_type[name].read(handler, tag)
                except Exception as ex:
                    logger.exception(ex)
                    continue
                if new_value:
                    values.append((tag, new_value))
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
        if (result and name.startswith('date_') and
                            result.tz_offset is None and self.timezone):
            result.tz_offset = self.timezone
            logger.info('%s: merged camera timezone offset', info)
        # add value to object attributes so __getattr__ doesn't get
        # called again
        super(Metadata, self).__setattr__(name, result)
        return result

    def __setattr__(self, name, value):
        if name not in self._tag_list:
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
