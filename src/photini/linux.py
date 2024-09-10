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
import subprocess
import tempfile


def post_install(exec_path, icon_path, remove, generic_name, comment):
    local_dir = os.path.expanduser('~/.local/share/applications')
    if remove:
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
            file.write('Icon={}\n'.format(icon_path))
            file.write('GenericName={}\n'.format(generic_name))
            file.write('Comment={}\n'.format(comment))
        print('Installing', path)
        cmd = ['desktop-file-install']
        if os.geteuid() != 0:
            # not running as root
            print(' to', local_dir)
            cmd.append('--dir={}'.format(local_dir))
        cmd.append(path)
        return subprocess.call(cmd)
    return 0
