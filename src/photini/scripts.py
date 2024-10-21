##  Photini - a simple photo metadata editor.
##  http://github.com/jim-easterbrook/Photini
##  Copyright (C) 2020-24  Jim Easterbrook  jim@jim-easterbrook.me.uk
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

import argparse
import importlib.util
import logging
import os
import platform
import site
import subprocess
import sys

from photini.configstore import BaseConfigStore
try:
    from photini.pyqt import QtCore
except ImportError:
    QtCore = None


def configure(argv=None):
    # get config
    config = BaseConfigStore('editor')
    install_extras = []
    ## Qt library choice is complicated
    print('Which Qt package would you like to use?')
    packages = ['PyQt5', 'PySide2']
    if platform.system() != 'Windows' or platform.release() not in ('7', '8'):
        # Qt6 is not available for Windows < 10
        packages += ['PyQt6', 'PySide6']
    # get installed Qt packages
    installed = []
    choices = {}
    default = None
    n = 0
    for package in packages:
        if importlib.util.find_spec(package):
            status = 'installed'
            # check for QtWebEngine
            if importlib.util.find_spec(package + '.QtWebEngineWidgets'):
                installed.append(package)
            else:
                status += ', WebEngine not installed'
        else:
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
               ('pixelfed', 'photini.pixelfed',
                'upload pictures to Pixelfed or Mastodon'),
               ('spelling', None, 'check spelling of metadata'),
               ('gpxpy', None, 'import GPS track data')]
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
    parser = argparse.ArgumentParser(
        description='Install Photini start/application menu entry')
    parser.add_argument(
        '-l', '--language', metavar='xx', help='localise command description')
    parser.add_argument(
        '-r', '--remove', action='store_true', help='uninstall menu entry')
    options = parser.parse_args()
    pkg_data = os.path.join(os.path.dirname(__file__), 'data')
    # localise descriptive metadata if possible
    generic_name = 'Photini photo metadata editor'
    comment = ('An easy to use digital photograph metadata (Exif,'
               ' IPTC, XMP) editing application.')
    if options.language and QtCore:
        qm_file = os.path.join(
            pkg_data, 'lang', 'photini.{}.qm'.format(options.language))
        translator = QtCore.QTranslator()
        if translator.load(qm_file):
            generic_name = translator.translate(
                'MenuBar', generic_name) or generic_name
            comment = translator.translate(
                'MenuBar', comment) or comment
        else:
            print('translator load failed:', options.language)
    # run OS specific command(s)
    exec_path = os.path.abspath(
        os.path.join(os.path.dirname(sys.argv[0]), 'photini'))
    if sys.platform == 'win32':
        exec_path += '.exe'
        icon_path = os.path.join(pkg_data, 'icons', 'photini_win.ico')
        import photini.windows
        return photini.windows.post_install(
            exec_path, icon_path, options.remove, generic_name)
    if sys.platform.startswith('linux'):
        icon_path = os.path.join(pkg_data, 'icons', 'linux')
        import photini.linux
        return photini.linux.post_install(
            exec_path, icon_path, options.remove, generic_name, comment)
    if sys.platform == 'darwin':
        icon_path = os.path.join(pkg_data, 'icons', 'photini.icns')
        import photini.macos
        return photini.macos.post_install(
            exec_path, icon_path, options.remove, generic_name, comment)
    return 0
