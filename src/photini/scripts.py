##  Photini - a simple photo metadata editor.
##  http://github.com/jim-easterbrook/Photini
##  Copyright (C) 2020  Jim Easterbrook  jim@jim-easterbrook.me.uk
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

import logging
from optparse import OptionParser
import os
import subprocess
import sys

import pkg_resources


logger = logging.getLogger(__name__)


def post_install(argv=None):
    if not sys.platform.startswith('linux'):
        return 0
    if argv:
        sys.argv = argv
    parser = OptionParser(
        usage='Usage: %prog [options] [file_name, ...]',
        description='Install Photini application menu entry')
    local_dir = os.path.expanduser('~/.local/share/applications')
    parser.add_option(
        '-u', '--user', action='store_true',
        help='install in user directory {}'.format(local_dir))
    options, args = parser.parse_args()
    cmd = ['desktop-file-install']
    if options.user:
        cmd.append('--dir={}'.format(local_dir))
    cmd += ['--set-key=Exec', '--set-value={} %F'.format(
        os.path.join(os.path.dirname(sys.argv[0]), 'photini'))]
    cmd += ['--set-key=Icon', '--set-value={}'.format(
        pkg_resources.resource_filename(
            'photini', 'data/icons/48/photini.png'))]
    cmd.append(pkg_resources.resource_filename(
        'photini', 'data/linux/photini.desktop'))
    print(' '.join(cmd))
    return subprocess.call(cmd)


def pre_uninstall(argv=None):
    if not sys.platform.startswith('linux'):
        return 0
    if argv:
        sys.argv = argv
    parser = OptionParser(
        usage='Usage: %prog [options] [file_name, ...]',
        description='Remove Photini application menu entry')
    local_dir = os.path.expanduser('~/.local/share/applications')
    parser.add_option(
        '-u', '--user', action='store_true',
        help='remove from user directory {}'.format(local_dir))
    options, args = parser.parse_args()
    if options.user:
        paths = [local_dir]
    else:
        paths = ['/usr/share/applications/', '/usr/local/share/applications/']
    for dir_name in paths:
        path = os.path.join(dir_name, 'photini.desktop')
        if os.path.exists(path):
            print('Deleting', path)
            os.unlink(path)
            return 0
    print('No "desktop" file found.')
    return 1
