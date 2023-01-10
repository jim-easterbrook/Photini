##  Photini - a simple photo metadata editor.
##  http://github.com/jim-easterbrook/Photini
##  Copyright (C) 2020-23  Jim Easterbrook  jim@jim-easterbrook.me.uk
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

import importlib
import logging
from optparse import OptionParser
import os
import site
import subprocess
import sys

import pkg_resources

from photini.configstore import BaseConfigStore


logger = logging.getLogger(__name__)


def configure(argv=None):
    # get config
    config = BaseConfigStore('editor')
    install_extras = []
    ## Qt library choice is complicated
    print('Which Qt package would you like to use?')
    packages = ['PyQt5', 'PyQt6', 'PySide2', 'PySide6']
    # get installed Qt packages
    installed = []
    choices = {}
    default = None
    n = 0
    for package in packages:
        # run separate python interpreter for each to avoid interactions
        cmd = [sys.executable, '-c', '"import {}.QtCore"'.format(package)]
        if subprocess.run(' '.join(cmd), shell=True,
                          stderr=subprocess.DEVNULL).returncode == 0:
            installed.append(package)
            status = 'installed'
            # check for QtWebEngine
            cmd = [sys.executable,
                   '-c', '"import {}.QtWebEngineWidgets"'.format(package)]
            if subprocess.run(' '.join(cmd), shell=True,
                              stderr=subprocess.DEVNULL).returncode != 0:
                status += ', WebEngine not installed'
        else:
            if 'PyQt' in package:
                # can't install PyQt5 or PyQt6 with pip
                continue
            status = 'not installed'
        if package == config.get('pyqt', 'qt_lib'):
            default = str(n)
        choices[str(n)] = package
        print('  {} {} [{}]'.format(n, package, status))
        n += 1
    # get user choice
    while True:
        msg = 'Choose {}'.format('/'.join(choices))
        if default:
            msg += ' [{}]'.format(default)
        choice = input(msg + ': ') or default
        if choice in choices:
            break
    choice = choices[choice]
    # set config
    config.set('pyqt', 'qt_lib', choice)
    # add to installation list
    if choice not in installed:
        install_extras.append(choice)
    ## Other options are simpler
    options = [('flickr', 'photini.flickr', 'upload pictures to Flickr'),
               ('google', 'photini.googlephotos',
                'upload pictures to Google Photos'),
               ('ipernity', 'photini.ipernity', 'upload pictures to Ipernity'),
               ('spelling', None, 'check spelling of metadata'),
               ('gpxpy', None, 'import GPS track data'),
               ('Pillow', None, 'make higher quality thumbnails')]
    if sys.platform != 'win32':
        options.append(
            ('importer', 'photini.importer', 'import pictures from a camera'))
    for name, module, description in options:
        msg = 'Would you like to {}? (y/n)'.format(description)
        if module:
            default = config.get('tabs', module)
        else:
            default = True
        if default is not None:
            default = ('n', 'y')[default]
            msg += ' [{}]'.format(default)
        choice = input(msg + ': ') or default
        if choice not in ('y', 'Y'):
            continue
        install_extras.append(name)
        if module:
            config.set('tabs', module, True)
    config.save()
    # install packages
    if not install_extras:
        return 0
    cmd = [sys.executable, '-m', 'pip', 'install']
    if not os.access(site.getsitepackages()[0], os.W_OK):
        cmd.append('--user')
    cmd.append('photini[{}]'.format(','.join(install_extras)))
    print(' '.join(cmd))
    subprocess.check_call(cmd)
    return 0


def post_install(argv=None):
    if argv:
        sys.argv = argv
    parser = OptionParser(
        usage='Usage: %prog [options] [file_name, ...]',
        description='Install Photini start/application menu entry')
    parser.add_option(
        '-r', '--remove', action='store_true', help='uninstall menu entry')
    options, args = parser.parse_args()
    exec_path = os.path.abspath(
        os.path.join(os.path.dirname(sys.argv[0]), 'photini'))
    icon_path = pkg_resources.resource_filename('photini', 'data/icons')
    if sys.platform == 'win32':
        exec_path += '.exe'
        icon_path = os.path.join(icon_path, 'photini_win.ico')
        cmd = ['cscript', '/nologo',
               pkg_resources.resource_filename(
                   'photini', 'data/windows/install_shortcuts.vbs'),
               exec_path, icon_path, sys.prefix]
        if options.remove:
            cmd.append('/remove')
        return subprocess.call(cmd)
    elif sys.platform.startswith('linux'):
        local_dir = os.path.expanduser('~/.local/share/applications')
        if options.remove:
            if os.geteuid() != 0:
                # not running as root
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
        if os.geteuid() != 0:
            # not running as root
            cmd.append('--dir={}'.format(local_dir))
        cmd += ['--set-key=Exec', '--set-value={} %F'.format(exec_path)]
        cmd += ['--set-key=Icon', '--set-value={}'.format(icon_path)]
        cmd.append(pkg_resources.resource_filename(
            'photini', 'data/linux/photini.desktop'))
        print(' \\\n  '.join(cmd))
        return subprocess.call(cmd)
    return 0
