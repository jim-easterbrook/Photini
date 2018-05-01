##  Photini - a simple photo metadata editor.
##  http://github.com/jim-easterbrook/Photini
##  Copyright (C) 2018  Jim Easterbrook  jim@jim-easterbrook.me.uk
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

import ctypes
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

# create version string
gi_version = '{} {}, GExiv2 {}.{}.{}, GObject {}'.format(
    ('PyGI', 'pgi')[using_pgi], gi.__version__, GExiv2.MAJOR_VERSION,
    GExiv2.MINOR_VERSION, GExiv2.MICRO_VERSION, GObject._version)
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
            result.append(c_str.value.decode('utf_8'))
        return result
    return []
