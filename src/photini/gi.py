##  Photini - a simple photo metadata editor.
##  http://github.com/jim-easterbrook/Photini
##  Copyright (C) 2018-20  Jim Easterbrook  jim@jim-easterbrook.me.uk
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

from __future__ import absolute_import, unicode_literals

from collections import namedtuple
import ctypes
from functools import reduce
import logging
import os
import site
import sys

if sys.platform == 'win32':
    # add gnome DLLs to PATH before importing GObject stuff
    for name in site.getsitepackages():
        gnome_path = os.path.join(name, 'gnome')
        if os.path.isdir(gnome_path) and gnome_path not in os.environ['PATH']:
            os.environ['PATH'] = gnome_path + ';' + os.environ['PATH']
            break

# use pgi if it's available, otherwise use PyGObject
try:
    import pgi
    pgi.install_as_gi()
    using_pgi = True
except ImportError:
    using_pgi = False
import gi

# declare preferred versions
for lib, vsn in (('GExiv2', '0.10'), ('Gspell', '1')):
    try:
        gi.require_version(lib, vsn)
    except ValueError:
        pass

# import required libraries
from gi.repository import GExiv2, GLib, GObject

# import optional library
try:
    from gi.repository import Gspell
except ImportError:
    Gspell = None

_glib_logger = logging.getLogger('GLib')

# initialise GObject stuff
GLib.set_prgname('Photini')
if not GExiv2.initialize():
    raise RuntimeError('Failed to initialise GExiv2')
GExiv2.log_use_glib_logging()

if (GLib.MAJOR_VERSION, GLib.MINOR_VERSION) >= (2, 46):
    # the numeric values of GLib.LogLevelFlags suggest ERROR is more
    # severe than CRITICAL, Python's logging has them the other way
    # round
    _log_mapping = {
        GLib.LogLevelFlags.LEVEL_DEBUG   : logging.DEBUG,
        GLib.LogLevelFlags.LEVEL_INFO    : logging.INFO,
        GLib.LogLevelFlags.LEVEL_MESSAGE : logging.INFO,
        GLib.LogLevelFlags.LEVEL_WARNING : logging.WARNING,
        GLib.LogLevelFlags.LEVEL_CRITICAL: logging.ERROR,
        GLib.LogLevelFlags.LEVEL_ERROR   : logging.CRITICAL,
        }

    def _gi_log_callback(log_domain, log_level, message, data):
        _glib_logger.log(_log_mapping[log_level], message)

    GLib.log_set_handler(
        None, reduce(lambda x, y: x|y, _log_mapping), _gi_log_callback, None)

# create version string
gexiv2_version = namedtuple(
    'gexiv2_version', ('major', 'minor', 'micro'))._make((
        GExiv2.MAJOR_VERSION, GExiv2.MINOR_VERSION, GExiv2.MICRO_VERSION))

gi_version = '{} {}, GExiv2 {}.{}.{}, GObject {}'.format(
    ('PyGObject', 'pgi')[using_pgi], gi.__version__, gexiv2_version[0],
    gexiv2_version[1], gexiv2_version[2], GObject._version)
gi_version += ', GLib {}.{}.{}'.format(
    GLib.MAJOR_VERSION, GLib.MINOR_VERSION, GLib.MICRO_VERSION)
if Gspell:
    gi_version += ', Gspell {}'.format(Gspell._version)


def GSListPtr_to_list(value):
    if isinstance(value, list):
        return value
    if using_pgi and hasattr(value, 'length'):
        # convert pgi.clib.glib.GSListPtr to Python list
        result = []
        for i in range(value.length):
            c_str = ctypes.c_char_p(value.nth_data(i))
            result.append(c_str.value.decode('utf-8'))
        return result
    return []
