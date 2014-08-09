##  Photini - a simple photo metadata editor.
##  http://github.com/jim-easterbrook/Photini
##  Copyright (C) 2012-14  Jim Easterbrook  jim@jim-easterbrook.me.uk
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

from datetime import datetime
import fractions
import locale
import logging
import os
import sys

from PyQt4 import QtCore

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
    if sys.version_info[0] >= 3:
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
    if sys.version_info[0] >= 3:
        result = result.decode('utf_8')
    return result

class NullValue(object):
    def empty(self):
        return True

    def as_str(self):
        return u''

class BaseValue(object):
    def __init__(self, tag=None):
        self.tag = tag
        self.value = None

    def empty(self):
        return self.value is None

    def as_str(self):
        return str(self.value)

    def merge(self, other):
        return self

    def set_value(self, value):
        self.value = value

    def iptc_pred(self, max_bytes):
        return self.as_str()

class IntValue(BaseValue):
    # value is a single integer
    def to_exif(self, md, tag):
        if self.value is None:
            md.clear_tag(tag)
            return
        md.set_tag_string(tag, self.as_str())

    def from_exif(self, md):
        if self.tag not in md.get_exif_tags():
            return
        self.value = int(md.get_tag_string(self.tag))

    def from_xmp(self, md):
        if self.tag not in md.get_xmp_tags():
            return
        self.value = int(md.get_tag_multiple(self.tag)[0])

class LatLongValue(BaseValue):
    # value is a latitude + longitude pair, stored as floating point numbers
    def as_str(self):
        if self.value:
            return '%.6f, %.6f' % self.value
        return u''

    def to_exif(self, md, tag):
        lat_tag = tag
        long_tag = lat_tag.replace('Latitude', 'Longitude')
        if self.value is None:
            md.clear_tag(lat_tag)
            md.clear_tag(lat_tag + 'Ref')
            md.clear_tag(long_tag)
            md.clear_tag(long_tag + 'Ref')
            return
        for this_tag, value, sign_char in zip(
                            (lat_tag, long_tag), self.value, ('NS', 'EW')):
            if value >= 0.0:
                ref_string = sign_char[0]
            else:
                ref_string = sign_char[1]
                value = -value
            degrees = int(value)
            value = (value - degrees) * 60.0
            minutes = int(value)
            seconds = (value - minutes) * 60.0
            seconds = fractions.Fraction(seconds).limit_denominator(1000000)
            value_string = '%d/1 %d/1 %d/%d' % (
                degrees, minutes, seconds.numerator, seconds.denominator)
            md.set_tag_string(this_tag, value_string)
            md.set_tag_string(this_tag + 'Ref', ref_string)

    def from_exif(self, md):
        lat_tag = self.tag
        long_tag = lat_tag.replace('Latitude', 'Longitude')
        result = []
        for tag in (lat_tag, long_tag):
            ref_tag = tag + 'Ref'
            if not (tag in md.get_exif_tags() and ref_tag in md.get_exif_tags()):
                return
            value_string = md.get_tag_string(tag)
            ref_string = md.get_tag_string(ref_tag)
            parts = map(fractions.Fraction, value_string.split())
            value = float(parts[0])
            if len(parts) > 1:
                value += float(parts[1]) / 60.0
            if len(parts) > 2:
                value += float(parts[2]) / 3600.0
            if ref_string in ('S', 'W'):
                value = -value
            result.append(value)
        self.value = (result[0], result[1])

    def from_xmp(self, md):
        lat_tag = self.tag
        long_tag = lat_tag.replace('Latitude', 'Longitude')
        result = []
        for tag in (lat_tag, long_tag):
            if not tag in md.get_xmp_tags():
                return
            value_string = md.get_tag_multiple(tag)[0]
            degrees, residue = value_string.split(',')
            minutes = residue[:-1]
            ref_string = residue[-1]
            value = float(degrees) + (float(minutes) / 60.0)
            if ref_string in ('S', 'W'):
                value = -value
            result.append(value)
        self.value = (result[0], result[1])

class StringValue(BaseValue):
    # value is a single unicode string
    def __init__(self, tag=None):
        BaseValue.__init__(self, tag)
        self.value = u''

    def empty(self):
        return len(self.value) == 0

    def sanitise(self):
        self.value = self.value.strip()

    def iptc_pred(self, max_bytes):
        return _decode_string(_encode_string(self.value, max_bytes))

    def as_str(self):
        return self.value

    def merge(self, other):
        if isinstance(other, ListValue):
            return other.merge(self)
        result = StringValue()
        result.value = self.value
        if other.value not in result.value:
            result.value = '%s // %s' % (result.value, other.value)
        return result

    def set_value(self, value):
        self.value = value
        self.sanitise()

    def to_exif(self, md, tag):
        if not self.value:
            md.clear_tag(tag)
            return
        md.set_tag_string(tag, _encode_string(self.value))

    def from_exif(self, md):
        if self.tag not in md.get_exif_tags():
            return
        self.value = _decode_string(md.get_tag_string(self.tag))
        self.sanitise()

    def to_iptc(self, md, tag):
        if not self.value:
            md.clear_tag(tag)
            return
        md.set_tag_multiple(tag, [_encode_string(self.value)])

    def from_iptc(self, md):
        if self.tag not in md.get_iptc_tags():
            return
        self.value = md.get_tag_multiple(self.tag)
        self.value = _decode_string(self.value[0])
        self.sanitise()

    def to_xmp(self, md, tag):
        if not self.value:
            md.clear_tag(tag)
            return
        md.set_tag_multiple(tag, [self.value])

    def from_xmp(self, md):
        if self.tag not in md.get_xmp_tags():
            return
        self.value = md.get_tag_multiple(self.tag)[0]
        if sys.version_info[0] < 3 and not isinstance(self.value, unicode):
            self.value = self.value.decode('utf_8')
        self.sanitise()

class ListValue(BaseValue):
    # value is an array of unicode strings
    def __init__(self, tag=None):
        BaseValue.__init__(self, tag)
        self.value = []

    def empty(self):
        return len(self.value) == 0

    def sanitise(self):
        new_value = []
        for item in self.value:
            item = item.strip()
            if item:
                new_value.append(item)
        self.value = new_value

    def iptc_pred(self, max_bytes):
        pred_value = map(
            lambda x: _decode_string(_encode_string(x, max_bytes)),
            self.value)
        return u'; '.join(pred_value)

    def as_str(self):
        return u'; '.join(self.value)

    def merge(self, other):
        result = ListValue()
        result.value = list(self.value)
        if isinstance(other, StringValue):
            items = [other.value]
        else:
            items = list(other.value)
        for item in items:
            if item not in result.value:
                result.value.append(item)
        return result

    def set_value(self, value):
        if value:
            self.value = value.split(';')
            self.sanitise()
        else:
            self.value = []

    def to_exif(self, md, tag):
        if not self.value:
            md.clear_tag(tag)
            return
        md.set_tag_string(tag, _encode_string(self.as_str()))

    def to_iptc(self, md, tag):
        if not self.value:
            md.clear_tag(tag)
            return
        md.set_tag_multiple(tag, map(_encode_string, self.value))

    def from_iptc(self, md):
        if self.tag not in md.get_exif_tags():
            return
        self.value = map(_decode_string, md.get_tag_multiple(self.tag))
        self.sanitise()

    def to_xmp(self, md, tag):
        if not self.value:
            md.clear_tag(tag)
            return
        md.set_tag_multiple(tag, self.value)

    def from_xmp(self, md):
        if self.tag not in md.get_xmp_tags():
            return
        self.value = md.get_tag_multiple(self.tag)
        if sys.version_info[0] < 3 and self.value and not isinstance(self.value[0], unicode):
            self.value = map(lambda x: x.decode('utf_8'), self.value)
        self.sanitise()

class DateTimeValue(BaseValue):
    # value is a Python datetime object
    def as_str(self):
        if self.value:
            return self.value.isoformat()
        return u''

    def to_exif(self, md, tag):
        if not self.value:
            md.clear_tag(tag)
            return
        string_value = self.value.strftime('%Y:%m:%d %H:%M:%S')
        md.set_tag_string(tag, string_value)

    def from_exif(self, md):
        if self.tag not in md.get_exif_tags():
            return
        string_value = md.get_tag_string(self.tag)
        self.value = datetime.strptime(string_value, '%Y:%m:%d %H:%M:%S')

    def to_iptc(self, md, tag):
        date_tag = tag
        time_tag = date_tag.replace('Date', 'Time')
        if not self.value:
            md.clear_tag(date_tag)
            md.clear_tag(time_tag)
            return
        date_string = self.value.strftime('%Y-%m-%d')
        time_string = self.value.strftime('%H:%M:%S')
        md.set_tag_multiple(date_tag, [date_string])
        md.set_tag_multiple(time_tag, [time_string])

    def from_iptc(self, md):
        date_tag = self.tag
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
            self.value = datetime.strptime(
                date_string + time_string, '%Y-%m-%d%H:%M:%S')

    def to_xmp(self, md, tag):
        if not self.value:
            md.clear_tag(tag)
            return
        string_value = self.value.strftime('%Y-%m-%dT%H:%M:%S')
        md.set_tag_multiple(tag, [string_value])

    def from_xmp(self, md):
        if self.tag not in md.get_xmp_tags():
            return
        string_value = md.get_tag_multiple(self.tag)[0]
        # remove any time zone info
        if string_value.count(':') >= 2:
            string_value = string_value[:19]
        else:
            string_value = string_value[:16]
        # extend short strings to include all info
        string_value += '0001-01-01T00:00:00'[len(string_value):]
        # convert to datetime
        self.value = datetime.strptime(string_value, '%Y-%m-%dT%H:%M:%S')

# class to use for each tag's data
_data_object = {
    'Exif.GPSInfo.GPSLatitude'           : LatLongValue,
    'Exif.Image.Artist'                  : StringValue,
    'Exif.Image.Copyright'               : StringValue,
    'Exif.Image.DateTime'                : DateTimeValue,
    'Exif.Image.DateTimeOriginal'        : DateTimeValue,
    'Exif.Image.ImageDescription'        : StringValue,
    'Exif.Image.Orientation'             : IntValue,
    'Exif.Image.ProcessingSoftware'      : StringValue,
    'Exif.Photo.DateTimeDigitized'       : DateTimeValue,
    'Exif.Photo.DateTimeOriginal'        : DateTimeValue,
    'Iptc.Application2.Byline'           : ListValue,
    'Iptc.Application2.Caption'          : StringValue,
    'Iptc.Application2.Copyright'        : StringValue,
    'Iptc.Application2.DateCreated'      : DateTimeValue,
    'Iptc.Application2.DigitizationDate' : DateTimeValue,
    'Iptc.Application2.Headline'         : StringValue,
    'Iptc.Application2.Keywords'         : ListValue,
    'Iptc.Application2.ObjectName'       : StringValue,
    'Xmp.dc.creator'                     : ListValue,
    'Xmp.dc.description'                 : StringValue,
    'Xmp.dc.rights'                      : StringValue,
    'Xmp.dc.subject'                     : ListValue,
    'Xmp.dc.title'                       : StringValue,
    'Xmp.photoshop.DateCreated'          : DateTimeValue,
    'Xmp.exif.DateTimeDigitized'         : DateTimeValue,
    'Xmp.exif.DateTimeOriginal'          : DateTimeValue,
    'Xmp.exif.GPSLatitude'               : LatLongValue,
    'Xmp.tiff.Artist'                    : StringValue,
    'Xmp.tiff.Copyright'                 : StringValue,
    'Xmp.tiff.DateTime'                  : DateTimeValue,
    'Xmp.tiff.ImageDescription'          : StringValue,
    'Xmp.tiff.Orientation'               : IntValue,
    'Xmp.xmp.CreateDate'                 : DateTimeValue,
    'Xmp.xmp.ModifyDate'                 : DateTimeValue,
    }
# some data requires more than one tag
_associated_tags = {
    'Exif.GPSInfo.GPSLatitude'           : ('Exif.GPSInfo.GPSLatitudeRef',
                                            'Exif.GPSInfo.GPSLongitude',
                                            'Exif.GPSInfo.GPSLongitudeRef'),
    'Iptc.Application2.DateCreated'      : ('Iptc.Application2.TimeCreated',),
    'Iptc.Application2.DigitizationDate' : ('Iptc.Application2.DigitizationTime',),
    'Xmp.exif.GPSLatitude'               : ('Xmp.exif.GPSLongitude',),
    }
# maximum length of Iptc data
_max_bytes = {
    'Iptc.Application2.Byline'           :   32,
    'Iptc.Application2.Caption'          : 2000,
    'Iptc.Application2.Copyright'        :  128,
    'Iptc.Application2.DateCreated'      : None,
    'Iptc.Application2.DigitizationDate' : None,
    'Iptc.Application2.Headline'         :  256,
    'Iptc.Application2.Keywords'         :   64,
    'Iptc.Application2.ObjectName'       :   64,
    }

class Metadata(QtCore.QObject):
    # mapping of preferred tags to Photini data fields
    _primary_tags = {
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
        'keywords'       : {'Xmp'  : 'Xmp.dc.subject',
                            'Iptc' : 'Iptc.Application2.Keywords'},
        'latlong'        : {'Exif' : 'Exif.GPSInfo.GPSLatitude'},
        'orientation'    : {'Exif' : 'Exif.Image.Orientation'},
        'software'       : {'Exif' : 'Exif.Image.ProcessingSoftware'},
        'title'          : {'Xmp'  : 'Xmp.dc.title',
                            'Iptc' : 'Iptc.Application2.ObjectName'},
        }
    # mapping of duplicate tags to Photini data fields
    # data in these is merged in when data is read
    # they get deleted when data is written
    _secondary_tags = {
        'copyright'      : {'Xmp'  : ('Xmp.tiff.Copyright',)},
        'creator'        : {'Xmp'  : ('Xmp.tiff.Artist',)},
        'date_digitised' : {'Xmp'  : ('Xmp.exif.DateTimeDigitized',)},
        'date_modified'  : {'Xmp'  : ('Xmp.tiff.DateTime',)},
        'date_taken'     : {'Exif' : ('Exif.Image.DateTimeOriginal',),
                            'Xmp'  : ('Xmp.exif.DateTimeOriginal',)},
        'description'    : {'Xmp'  : ('Xmp.tiff.ImageDescription',)},
        'keywords'       : {},
        'latlong'        : {'Xmp'  : ('Xmp.exif.GPSLatitude',)},
        'orientation'    : {'Xmp'  : ('Xmp.tiff.Orientation',)},
        'software'       : {},
        'title'          : {'Iptc' : ('Iptc.Application2.Headline',)},
        }
    def __init__(self, path, parent=None):
        QtCore.QObject.__init__(self, parent)
        self.logger = logging.getLogger(self.__class__.__name__)
        # create metadata handlers for image file and sidecar (if present)
        self._path = path
        self._if = MetadataHandler(path)
        self._sc_path = self._find_side_car(path)
        if self._sc_path:
            self._sc = MetadataHandler(self._sc_path)
        else:
            self._sc = None
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
        self._sc.copy(self._if, comment=False)

    def save(self, if_mode, sc_mode):
        if not self._unsaved:
            return
        self.set_item('software', 'Photini editor v%s' % (__version__))
        if sc_mode == 'delete' and self._sc:
            self._if.copy(self._sc, comment=False)
        OK = False
        if if_mode:
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
        result = self._if.get_exif_tags()
        if self._sc:
            for tag in self._sc.get_exif_tags():
                if tag not in result:
                    result.append(tag)
        return result

    def get_iptc_tags(self):
        result = self._if.get_iptc_tags()
        if self._sc:
            for tag in self._sc.get_iptc_tags():
                if tag not in result:
                    result.append(tag)
        return result

    def get_xmp_tags(self):
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
        return self._if.get_tag_string(tag)

    def get_tag_multiple(self, tag):
        if self._sc and tag in self._sc.get_tags():
            return self._sc.get_tag_multiple(tag)
        return self._if.get_tag_multiple(tag)

    # setters: set in both sidecar and image file
    def set_tag_string(self, tag, value):
        if self._sc:
            self._sc.set_tag_string(tag, value)
        self._if.set_tag_string(tag, value)

    def set_tag_multiple(self, tag, value):
        if self._sc:
            self._sc.set_tag_multiple(tag, value)
        self._if.set_tag_multiple(tag, value)

    def clear_tag(self, tag):
        if self._sc:
            self._sc.clear_tag(tag)
        self._if.clear_tag(tag)

    def get_tags(self):
        return self.get_exif_tags() + self.get_iptc_tags() + self.get_xmp_tags()

    def _get_value(self, family, tag):
        result = _data_object[tag](tag)
        if family == 'Exif':
            result.from_exif(self)
        elif family == 'Iptc':
            result.from_iptc(self)
        else:
            result.from_xmp(self)
        return result

    def get_item(self, name):
        if name in self._value_cache:
            return self._value_cache[name]
        # get values from all 3 families, using first tag in list that has data
        value = {'Exif': NullValue(), 'Iptc': NullValue(), 'Xmp': NullValue()}
        for family in self._primary_tags[name]:
            try:
                value[family] = self._get_value(
                    family, self._primary_tags[name][family])
            except Exception, ex:
                self.logger.exception(ex)
        for family in self._secondary_tags[name]:
            for tag in self._secondary_tags[name][family]:
                try:
                    new_value = self._get_value(family, tag)
                except Exception, ex:
                    self.logger.exception(ex)
                    continue
                if new_value.empty():
                    continue
                elif value[family].empty():
                    value[family] = new_value
                elif new_value.as_str() not in value[family].as_str():
                    self.logger.warning('merging %s with %s',
                                        new_value.tag, value[family].tag)
                    value[family] = value[family].merge(new_value)
        # choose preferred family
        if not value['Exif'].empty():
            preference = 'Exif'
        elif not value['Xmp'].empty():
            preference = 'Xmp'
        else:
            preference = 'Iptc'
        # check for IPTC being modified by non-compliant software
        if preference != 'Iptc' and not value['Iptc'].empty():
            iptc_tag = value['Iptc'].tag
            pred_str = value[preference].iptc_pred(_max_bytes[iptc_tag])
            if pred_str != value['Iptc'].as_str():
                self.logger.warning(
                    '%s mismatch with %s', iptc_tag, value[preference].tag)
                preference = 'Iptc'
        # merge in non-matching data so user can review it
        result = value[preference]
        for family in ('Exif', 'Xmp'):
            if preference != family and not value[family].empty():
                if value[family].as_str() not in result.as_str():
                    self.logger.warning('merging %s with %s',
                                        value[family].tag, value[preference].tag)
                    result = result.merge(value[family])
        self._value_cache[name] = result
        return result

    def set_item(self, name, value):
        current_object = self.get_item(name)
        for family in ('Exif', 'Xmp', 'Iptc'):
            if family in self._primary_tags[name]:
                tag = self._primary_tags[name][family]
                new_object = _data_object[tag](tag)
                break
        new_object.set_value(value)
        if new_object.as_str() == current_object.as_str():
            return
        self._value_cache[name] = new_object
        # write data to primary tags (iptc only if it already exists)
        for family in self._primary_tags[name]:
            tag = self._primary_tags[name][family]
            if family == 'Exif':
                new_object.to_exif(self, tag)
            elif family == 'Xmp':
                new_object.to_xmp(self, tag)
            elif tag in self.get_iptc_tags():
                new_object.to_iptc(self, tag)
        # delete secondary tags
        for family in self._secondary_tags[name]:
            for tag in self._secondary_tags[name][family]:
                if tag in self.get_tags():
                    self.clear_tag(tag)
                if tag in _associated_tags:
                    for sup_tag in _associated_tags[tag]:
                        if sup_tag in self.get_tags():
                            self.clear_tag(sup_tag)
        self._set_unsaved(True)

    def del_item(self, name):
        self.set_item(name, None)

    new_status = QtCore.pyqtSignal(bool)
    def _set_unsaved(self, status):
        self._unsaved = status
        self.new_status.emit(self._unsaved)

    def changed(self):
        return self._unsaved
