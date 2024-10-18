#  Photini - a simple photo metadata editor.
#  http://github.com/jim-easterbrook/Photini
#  Copyright (C) 2024  Jim Easterbrook  jim@jim-easterbrook.me.uk
#
#  This file is part of Photini.
#
#  Photini is free software: you can redistribute it and/or modify it
#  under the terms of the GNU General Public License as published by the
#  Free Software Foundation, either version 3 of the License, or (at
#  your option) any later version.
#
#  Photini is distributed in the hope that it will be useful, but
#  WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
#  General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with Photini.  If not, see <http://www.gnu.org/licenses/>.

import os
import shutil
import subprocess
import tempfile


def post_install(exec_path, icon_path, remove, generic_name, comment):
    local_root = os.path.expanduser('~/.local/share')
    icon_name = 'photini.png'
    icon_theme = os.path.basename(icon_path)
    if remove:
        if os.geteuid() != 0:
            # not running as root
            paths = [local_root]
        else:
            paths = ['/usr/share', '/usr/local/share']
        OK = False
        for dir_name in paths:
            # delete icons
            path = os.path.join(dir_name, 'icons', icon_theme)
            for root, dirs, files in os.walk(path, topdown=False):
                if icon_name in files:
                    path = os.path.join(root, icon_name)
                    print('Deleting', path)
                    os.unlink(path)
            # delete desktop file
            path = os.path.join(dir_name, 'applications', 'photini.desktop')
            if os.path.exists(path):
                print('Deleting', path)
                os.unlink(path)
                OK = True
        if OK:
            return 0
        print('No "desktop" file found.')
        return 1
    # copy icons
    if os.geteuid() == 0:
        dest_root = '/usr/share'
    else:
        dest_root = local_root
    dest_root = os.path.join(dest_root, 'icons', icon_theme)
    for root, dirs, files in os.walk(icon_path):
        for name in files:
            src = os.path.join(root, name)
            dst = root.replace(icon_path, dest_root)
            os.makedirs(dst, exist_ok=True)
            dst = os.path.join(dst, name)
            print('Writing', dst)
            shutil.copy(src, dst)
    # create desktop file
    with tempfile.TemporaryDirectory() as temp_dir:
        path = os.path.join(temp_dir, 'photini.desktop')
        print('Creating', path)
        with open(path, 'w') as file:
            file.write('''[Desktop Entry]
Type=Application
Name=Photini
Terminal=false
Categories=Graphics;Photography;
MimeType=image/jpeg;image/jpeg2000;image/tiff;image/png;image/gif;image/x-dcraw;application/rdf+xml;
''')
            file.write('Exec={} %F\n'.format(exec_path))
            file.write('Icon={}\n'.format(os.path.splitext(icon_name)[0]))
            file.write('GenericName={}\n'.format(generic_name))
            file.write('Comment={}\n'.format(comment))
        print('Installing', path)
        cmd = ['desktop-file-install', '--rebuild-mime-info-cache']
        if os.geteuid() != 0:
            # not running as root
            local_apps = os.path.join(local_root, 'applications')
            print(' to', local_apps)
            cmd.append('--dir={}'.format(local_apps))
        cmd.append(path)
        return subprocess.call(cmd)
    return 0
