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
    if argv:
        sys.argv = argv
    parser = OptionParser(
        usage='Usage: %prog [options] [file_name, ...]',
        description='Install Photini start/application menu entry')
    parser.add_option(
        '-u', '--user', action='store_true', help='install for single user')
    parser.add_option(
        '-r', '--remove', action='store_true', help='uninstall menu entry')
    options, args = parser.parse_args()
    exec_path = os.path.join(os.path.dirname(sys.argv[0]), 'photini')
    icon_path = pkg_resources.resource_filename('photini', 'data/icons')
    if sys.platform == 'win32':
        exec_path += '.exe'
        icon_path = os.path.join(icon_path, 'photini_win.ico')
        cmd = ['cscript', '/nologo',
               pkg_resources.resource_filename(
                   'photini', 'data/windows/install_shortcuts.vbs'),
               exec_path, icon_path, sys.prefix]
        if options.user:
            cmd.append('/user')
        if options.remove:
            cmd.append('/remove')
            print('Removing menu shortcuts')
        else:
            print('Creating menu shortcuts')
        return subprocess.call(cmd)
    elif sys.platform.startswith('linux'):
        local_dir = os.path.expanduser('~/.local/share/applications')
        if options.remove:
            if options.user:
                paths = [local_dir]
            else:
                paths = ['/usr/share/applications/',
                         '/usr/local/share/applications/']
            for dir_name in paths:
                path = os.path.join(dir_name, 'photini.desktop')
                if os.path.exists(path):
                    print('Deleting', path)
                    os.unlink(path)
                    return 0
            print('No "desktop" file found.')
            return 1
        icon_path = os.path.join(icon_path, 'photini_48.png')
        cmd = ['desktop-file-install']
        if options.user:
            cmd.append('--dir={}'.format(local_dir))
        cmd += ['--set-key=Exec', '--set-value={} %F'.format(exec_path)]
        cmd += ['--set-key=Icon', '--set-value={}'.format(icon_path)]
        cmd.append(pkg_resources.resource_filename(
            'photini', 'data/linux/photini.desktop'))
        print(' '.join(cmd))
        return subprocess.call(cmd)
    return 0
