import os
import sys


def main():
    for params in ({'TARGET': 'C:/photini32',
                    '+'     : '32',
                    '-'     : '64'},
                   {'TARGET': 'C:/photini64',
                    '+'     : '64',
                    '-'     : '32'}
                   ):
        # remove unwanted directories
        for path in (
                '/clang{-}',
                '/mingw{-}',
                '/mingw{+}/lib/cmake',
                '/mingw{+}/lib/include',
                '/mingw{+}/lib/pkgconfig',
                '/mingw{+}/lib/python2.7',
                '/mingw{+}/lib/python3.7/test',
                '/mingw{+}/share/doc',
                '/mingw{+}/share/gtk-doc',
                '/mingw{+}/share/man',
                '/mingw{+}/share/qt5/doc',
                '/mingw{+}/share/qt5/examples',
                '/mingw{+}/share/qt5/plugins/designer',
                '/mingw{+}/share/qt5/plugins/geoservices',
                '/mingw{+}/share/qt5/plugins/qmltooling',
                '/mingw{+}/share/qt5/qml',
                '/usr/share/doc',
                '/usr/share/man',
                ):
            root_dir = params['TARGET'] + path.format(**params)
            if not os.path.isdir(root_dir):
                continue
            for root, dirs, files in os.walk(root_dir, topdown=False):
                for name in files:
                    test_name = name.lower()
                    for word in (
                            'copying', 'copyright', 'licence', 'license'):
                        if word in test_name:
                            break
                    else:
                        full_path = os.path.join(root, name)
                        print('Delete', full_path)
                        os.unlink(full_path)
                for name in dirs:
                    test_name = name.lower()
                    for word in (
                            'copying', 'copyright', 'licence', 'license'):
                        if word in test_name:
                            break
                    else:
                        full_path = os.path.join(root, name)
                        if not os.listdir(full_path):
                            print('Delete', full_path)
                            os.rmdir(full_path)
            if not os.listdir(root_dir):
                print('Delete', root_dir)
                os.rmdir(root_dir)
        # remove Qt5 debug files
        for path in ('/mingw{+}/bin/',
                     '/mingw{+}/lib/',
                     '/mingw{+}/share/qt5/plugins/'):
            root_dir = params['TARGET'] + path.format(**params)
            for root, dirs, files in os.walk(root_dir):
                for name in files:
                    if 'd.' in name and ('Qt5' in name or 'qt5' in root):
                        normal_name = name.replace('d.', '.')
                        if normal_name in files:
                            debug_path = os.path.join(root, name)
                            print('Delete', debug_path)
                            os.unlink(debug_path)
        # remove unwanted terminfo
        for path in (
                '/mingw{+}/lib/terminfo',
                '/mingw{+}/share/terminfo',
                '/usr/lib/terminfo',
                '/usr/share/terminfo'):
            root_dir = params['TARGET'] + path.format(**params)
            for root, dirs, files in os.walk(root_dir):
                for name in files:
                    if 'linux' in name.lower() or 'xterm' in name.lower():
                        continue
                    debug_path = os.path.join(root, name)
                    print('Delete', debug_path)
                    os.unlink(debug_path)
        # remove unwanted files
        for path in (
                '/maintenancetool.exe',
                '/maintenancetool.ini',
                '/maintenancetool.dat',
                '/mingw{-}.exe',
                '/mingw{-}.ini',
                '/mingw{+}/bin/qdoc.exe',
                '/mingw{+}/bin/Qt53D*',
                '/mingw{+}/bin/Qt5Designer*',
                '/mingw{+}/lib/Qt53D*',
                '/mingw{+}/lib/Qt5Designer*',
                '/mingw{+}/lib/libQt53D*',
                '/mingw{+}/lib/libQt5Designer*',
                '/var/lib/pacman/sync/mingw{-}.db',
                '/var/lib/pacman/sync/mingw{-}.db.sig',
                ):
            target_path = params['TARGET'] + path.format(**params)
            if target_path[-1] == '*':
                dir_name, base_name = os.path.split(target_path)
                base_name = base_name[:-1]
                for file_name in os.listdir(dir_name):
                    if file_name.startswith(base_name):
                        target_file = os.path.join(dir_name, file_name)
                        print('Delete', target_file)
                        os.unlink(target_file)
            else:
                if os.path.exists(target_path):
                    print('Delete', target_path)
                    os.unlink(target_path)
    return 0


if __name__ == '__main__':
    sys.exit(main())
