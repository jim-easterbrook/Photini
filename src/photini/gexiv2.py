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

import codecs
from collections import namedtuple
from contextlib import contextmanager
import locale
import logging
import os
import random
import shutil
import string
import sys

from photini.gi import gi, using_pgi

gi.require_version('GExiv2', '0.10')
from gi.repository import GExiv2, GLib, GObject

logger = logging.getLogger(__name__)

# pydoc gi.repository.GExiv2.Metadata is useful to see methods available

_gexiv2_version = namedtuple(
    'gexiv2_version', ('major', 'minor', 'micro'))._make((
        GExiv2.MAJOR_VERSION, GExiv2.MINOR_VERSION, GExiv2.MICRO_VERSION))

# can't read libexiv2 version
exiv2_version_info = (0, 0, 0)
exiv2_version = '{}.{}.{}'.format(*_gexiv2_version)
if exiv2_version < '0.10.3':
    raise ImportError(
        'gexiv2 version {} is less than 0.10.3'.format(exiv2_version))

exiv2_version = 'GExiv2 {}, {} {}, GObject {}, GLib {}.{}.{}'.format(
    exiv2_version, ('PyGObject', 'pgi')[using_pgi], gi.__version__,
    GObject._version,
    GLib.MAJOR_VERSION, GLib.MINOR_VERSION, GLib.MICRO_VERSION)

XMP_WRAPPER = '''<?xpacket begin="" id="W5M0MpCehiHzreSzNTczkc9d"?>
<x:xmpmeta xmlns:x="adobe:ns:meta/" x:xmptk="XMP Core 4.4.0-Exiv2">
  <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
    <rdf:Description rdf:about=""
      {}/>
  </rdf:RDF>
</x:xmpmeta>
<?xpacket end="w"?>'''


@contextmanager
def temp_rename(path):
    # Rename path to an ascii-safe file, further up the directory path
    # if necessary, then restore to the original name and directory on
    # completion. Only needed for workaround for bug in GExiv2 on
    # Windows
    dir_name, file_name = os.path.split(path)
    while dir_name.encode('ascii', 'replace').decode('ascii') != dir_name:
        dir_name = os.path.dirname(dir_name)
    while True:
        tmp_path = os.path.join(dir_name, file_name)
        if (tmp_path.encode('ascii', 'replace').decode('ascii') == tmp_path
                and not os.path.exists(tmp_path)):
            break
        file_name = ''.join(
            random.choices(string.ascii_lowercase, k=8)) + '.tmp'
    try:
        logger.warning('Renaming %s to %s', path, tmp_path)
        shutil.move(path, tmp_path)
        yield tmp_path
    finally:
        logger.warning('Renaming %s to %s', tmp_path, path)
        shutil.move(tmp_path, path)


class MetadataHandler(GExiv2.Metadata):
    @classmethod
    def initialise(cls, config_store, verbosity):
        if not GExiv2.initialize():
            raise RuntimeError('Failed to initialise GExiv2')
        GExiv2.log_set_level(max(
            GExiv2.LogLevel.DEBUG, min(GExiv2.LogLevel.ERROR, 4 - verbosity)))
        GExiv2.log_use_glib_logging()
        # Recent versions of Exiv2 have these namespaces defined, but
        # older versions may not recognise them. The xapGImg URL is
        # invalid, but Photini doesn't write xapGImg so it doesn't
        # matter.
        for prefix, name in (
                ('exifEX',    'http://cipa.jp/exif/1.0/'),
                ('xapGImg',   'http://ns.adobe.com/xxx/'),
                ('xmpGImg',   'http://ns.adobe.com/xap/1.0/g/img/'),
                ('xmpRights', 'http://ns.adobe.com/xap/1.0/rights/')):
            GExiv2.Metadata.register_xmp_namespace(name, prefix)
        # Gexiv2 won't register the 'Iptc4xmpExt' namespace as its
        # abbreviated version 'iptcExt' is already defined. This kludge
        # registers it by reading some data with the full namespace
        data = XMP_WRAPPER.format(
            'xmlns:Iptc4xmpExt="http://iptc.org/std/Iptc4xmpExt/2008-02-29/"')
        # open the data to register the namespace
        GExiv2.Metadata().open_buf(data.encode('utf-8'))
        # make list of possible character encodings
        cls.encodings = ['utf-8', 'iso8859-1', 'ascii']
        char_set = locale.getdefaultlocale()[1]
        if char_set:
            try:
                name = codecs.lookup(char_set).name
                if name not in cls.encodings:
                    cls.encodings.append(name)
            except LookupError:
                pass

    def __init__(self, path, buf=None, utf_safe=False):
        super(MetadataHandler, self).__init__()
        self._path = path
        # workaround for bug in GExiv2 on Windows
        # https://gitlab.gnome.org/GNOME/gexiv2/-/issues/59
        self._gexiv_unsafe = False
        if sys.platform == 'win32' and _gexiv2_version <= (0, 12, 1):
            try:
                self._path.encode('ascii')
            except UnicodeEncodeError:
                self._gexiv_unsafe = True
        if self._gexiv_unsafe and not buf:
            with open(self._path, 'rb') as f:
                buf = f.read()
        if buf:
            # read metadata from buffer
            self.open_buf(buf)
        else:
            # read metadata from file
            self.open_path(self._path)
        self.read_only = not any((self.get_supports_exif(),
                                  self.get_supports_iptc(),
                                  self.get_supports_xmp()))
        self.mime_type = self.get_mime_type()
        self.xmp_only = self.mime_type in (
            'application/rdf+xml', 'application/postscript')
        # Don't use Exiv2's converted values when accessing Xmp files
        if self.xmp_only:
            self.clear_exif()
            self.clear_iptc()
        # transcode any non utf-8 strings (Xmp is always utf-8)
        if not utf_safe:
            if self.has_exif() and not self.xmp_only:
                self.transcode_exif()
            if self.has_iptc() and not self.xmp_only:
                self.transcode_iptc()

    def __bool__(self):
        return True

    def transcode_exif(self):
        for tag in self.get_exif_tags():
            if self.get_tag_type(tag) != 'Ascii':
                continue
            family, group, name = tag.split('.', 2)
            if name == '0xea1c':
                continue
            if group[:5] in (
                    'Canon', 'Casio', 'Fujif', 'Minol', 'Nikon', 'Olymp',
                    'Panas', 'Penta', 'Samsu', 'Sigma', 'Sony1'):
                continue
            raw_value = self.get_raw_value(tag)
            if not raw_value:
                logger.error('%s: failed to read tag %s',
                             os.path.basename(self._path), tag)
                continue
            for encoding in self.encodings:
                try:
                    new_value = raw_value.decode(encoding)
                except UnicodeDecodeError:
                    continue
                if encoding != 'utf-8':
                    logger.info('%s: transcoded %s from %s',
                                os.path.basename(self._path), tag, encoding)
                    self.set_tag_string(tag, new_value)
                break

    def transcode_iptc(self):
        encodings = self.encodings
        iptc_charset = self.get_iptc_encoding()
        if iptc_charset in ('utf-8', 'ascii'):
            # no need to translate anything
            return
        if iptc_charset:
            encodings = [iptc_charset]
        # transcode every string tag except Iptc.Envelope.CharacterSet
        tags = ['Iptc.Envelope.CharacterSet']
        multiple = []
        for tag in self.get_iptc_tags():
            if tag in tags:
                multiple.append(tag)
            elif self.get_tag_type(tag) == 'String':
                tags.append(tag)
        for tag in tags[1:]:
            if tag in multiple:
                # PyGObject segfaults if strings are not utf-8
                if using_pgi:
                    try:
                        value = self.get_tag_multiple(tag)
                        continue
                    except UnicodeDecodeError:
                        pass
                logger.warning('%s: ignoring multiple %s values',
                               os.path.basename(self._path), tag)
                logger.warning(
                    'Try running Photini with the --utf_safe option.')
            try:
                value = self.get_tag_string(tag)
                self.set_tag_string(tag, value)
                continue
            except UnicodeDecodeError:
                pass
            raw_value = self.get_raw_value(tag)
            if not raw_value:
                logger.error('%s: failed to read tag %s',
                             os.path.basename(self._path), tag)
                continue
            for encoding in encodings:
                try:
                    new_value = raw_value.decode(encoding)
                except UnicodeDecodeError:
                    continue
                if encoding != 'utf-8':
                    logger.info('%s: transcoded %s from %s',
                                os.path.basename(self._path), tag, encoding)
                    self.set_tag_string(tag, new_value)
                break

    def get_xmp_tags(self):
        return [x.replace('.iptcExt.', '.Iptc4xmpExt.') for x in
                super(MetadataHandler, self).get_xmp_tags()]

    @classmethod
    def open_old(cls, *arg, **kw):
        try:
            return cls(*arg, **kw)
        except GLib.GError:
            # expected if unrecognised file format
            return None
        except Exception as ex:
            logger.exception(ex)
            return None

    def get_exif_thumbnail(self):
        data = super(MetadataHandler, self).get_exif_thumbnail()
        if using_pgi and isinstance(data, tuple):
            # get_exif_thumbnail returns (OK, data) tuple
            data = data[data[0]]
        if data:
            return data
        return None

    _charset_map = {
        'ascii'  : 'ascii',
        'unicode': 'utf-16-be',
        'jis'    : 'euc_jp',
        }

    def get_exif_comment(self, tag):
        result = self.get_raw_value(tag)
        if not result:
            return None
        # first 8 bytes should be the encoding charset
        try:
            charset = result[:8].decode(
                'ascii', 'replace').strip('\x00').lower()
            if charset in self._charset_map:
                result = result[8:].decode(self._charset_map[charset])
            elif charset != '':
                result = result.decode('ascii', 'replace')
            else:
                # blank charset, so try known encodings
                for encoding in self.encodings:
                    try:
                        result = result[8:].decode(encoding)
                        break
                    except UnicodeDecodeError:
                        pass
                else:
                    raise UnicodeDecodeError
            if result:
                result = result.strip('\x00')
            if not result:
                return None
            return result
        except UnicodeDecodeError:
            logger.error('%s: %s: %d bytes binary data will be deleted'
                         ' when metadata is saved',
                         os.path.basename(self._path), tag, len(result))
            raise

    def get_exif_value(self, tag):
        if not self.has_tag(tag):
            return None
        if tag in ('Exif.Canon.ModelID', 'Exif.CanonCs.LensType',
                   'Exif.Image.XPTitle', 'Exif.Image.XPComment',
                   'Exif.Image.XPAuthor', 'Exif.Image.XPKeywords',
                   'Exif.Image.XPSubject',
                   'Exif.NikonLd1.LensIDNumber', 'Exif.NikonLd2.LensIDNumber',
                   'Exif.NikonLd3.LensIDNumber', 'Exif.Pentax.ModelID'):
            return self.get_tag_interpreted_string(tag)
        if tag == 'Exif.Photo.UserComment':
            return self.get_exif_comment(tag)
        return self.get_tag_string(tag)

    def get_iptc_value(self, tag):
        if not self.has_tag(tag):
            return None
        if tag in ('Iptc.Application2.Byline', 'Iptc.Application2.BylineTitle',
                   'Iptc.Application2.Contact', 'Iptc.Application2.Keywords'):
            # Iptc standard allows tag to repeat
            return self.get_tag_multiple(tag)
        return self.get_tag_string(tag)

    def get_xmp_value(self, tag):
        tag = tag.replace('.Iptc4xmpExt.', '.iptcExt.')
        if not self.has_tag(tag):
            return None
        if self.get_tag_type(tag) == 'LangAlt':
            return self.get_tag_multiple(tag)[0]
        if self.get_tag_type(tag) in ('XmpBag', 'XmpSeq'):
            return self.get_tag_multiple(tag)
        return self.get_tag_string(tag)

    def get_raw_value(self, tag):
        if not self.has_tag(tag):
            return None
        try:
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

    def get_preview_thumbnail(self):
        props = self.get_preview_properties()
        if not props:
            return None
        # get largest acceptable image
        idx = len(props)
        while idx > 0:
            idx -= 1
            if max(props[idx].get_width(), props[idx].get_height()) <= 640:
                break
        image = self.get_preview_image(props[idx])
        return image.get_data()

    def get_preview_imagedims(self):
        props = self.get_preview_properties()
        if not props:
            return 0, 0
        return props[-1].get_width(), props[-1].get_height()

    def set_exif_value(self, tag, value):
        if not value:
            self.clear_tag(tag)
        else:
            self.set_tag_string(tag, value)

    def set_iptc_value(self, tag, value):
        if not value:
            self.clear_tag(tag)
        elif isinstance(value, str):
            self.set_tag_string(tag, value)
        else:
            self.set_tag_multiple(tag, value)

    def set_xmp_value(self, tag, value):
        tag = tag.replace('.Iptc4xmpExt.', '.iptcExt.')
        if not value:
            self.clear_tag(tag)
            return
        if '[' in tag:
            # create XMP array
            container = tag.split('[')[0]
            for t in super(MetadataHandler, self).get_xmp_tags():
                if t.startswith(container):
                    # container already exists
                    break
            else:
                type_ = self.get_tag_type(container)
                if type_ == 'XmpBag':
                    type_ = GExiv2.StructureType.BAG
                elif type_ == 'XmpSeq':
                    type_ = GExiv2.StructureType.SEQ
                else:
                    type_ = GExiv2.StructureType.ALT
                self.set_xmp_tag_struct(container, type_)
        if isinstance(value, str):
            self.set_tag_string(tag, value)
        else:
            self.set_tag_multiple(tag, value)

    def save(self):
        try:
            if self._gexiv_unsafe:
                with temp_rename(self._path) as tmp_file:
                    self.save_file(tmp_file)
            else:
                self.save_file(self._path)
        except GLib.GError as ex:
            logger.error(str(ex))
            return False
        except Exception as ex:
            logger.exception(ex)
            return False
        return True

    def clear_maker_note(self):
        self.clear_tag('Exif.Image.Make')
        self.save_file(self._path)
        self.open_path(self._path)
        self.clear_tag('Exif.Photo.MakerNote')
        self.save_file(self._path)

    @staticmethod
    def create_sc(path, image_md):
        if image_md and _gexiv2_version >= (0, 10, 6):
            image_md.save_external(path)
        else:
            with open(path, 'w') as of:
                of.write(XMP_WRAPPER.format(
                    'xmlns:xmp="http://ns.adobe.com/xap/1.0/"'))
            if image_md:
                # let exiv2 copy as much metadata as it can into sidecar
                image_md.save_file(path)

    def merge_sc(self, other):
        # merge sidecar data into image file data, ignoring thumbnails
        raw_sc = GExiv2.Metadata()
        raw_sc.open_path(other._path)
        # allow exiv2 to infer Exif tags from XMP
        for tag in raw_sc.get_exif_tags():
            if tag.startswith('Exif.Thumbnail'):
                continue
            # ignore inferred datetime values the exiv2 gets wrong
            # (I think it's adding the local timezone offset)
            if tag in ('Exif.Image.DateTime', 'Exif.Photo.DateTimeOriginal',
                       'Exif.Photo.DateTimeDigitized'):
                self.clear_tag(tag)
            else:
                value = raw_sc.get_tag_string(tag)
                if value:
                    self.set_tag_string(tag, value)
        # copy all XMP tags except inferred Exif tags
        for tag in raw_sc.get_xmp_tags():
            if tag.startswith('Xmp.xmp.Thumbnails'):
                continue
            ns = tag.split('.')[1]
            if ns in ('exif', 'exifEX', 'tiff', 'aux'):
                # exiv2 will already have supplied the equivalent Exif tag
                pass
            elif self.get_tag_type(tag) == 'XmpText':
                value = raw_sc.get_tag_string(tag)
                if value:
                    self.set_tag_string(tag, value)
            else:
                value = raw_sc.get_tag_multiple(tag)
                if value:
                    self.set_tag_multiple(tag, value)
