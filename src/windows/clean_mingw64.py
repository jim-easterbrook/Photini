import os
import sys

TARGET = 'C:/photini64'


def main():
    # remove unwanted directories
    for path in (
            '/clang32',
            '/mingw32',
            '/mingw64/lib/cmake',
            '/mingw64/lib/include',
            '/mingw64/lib/pkgconfig',
            '/mingw64/lib/python3.7/test',
            '/mingw64/share/doc',
            '/mingw64/share/gtk-doc',
            '/mingw64/share/man',
            '/mingw64/share/qt5/doc',
            '/mingw64/share/qt5/examples',
            '/mingw64/share/qt5/plugins/designer',
            '/mingw64/share/qt5/plugins/geoservices',
            '/mingw64/share/qt5/plugins/qmltooling',
            '/mingw64/share/qt5/qml',
            '/usr/share/doc',
            '/usr/share/man',
            ):
        root_dir = TARGET + path
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
                    path = os.path.join(root, name)
                    print('Delete', path)
                    os.unlink(path)
            for name in dirs:
                test_name = name.lower()
                for word in (
                        'copying', 'copyright', 'licence', 'license'):
                    if word in test_name:
                        break
                else:
                    path = os.path.join(root, name)
                    if not os.listdir(path):
                        print('Delete', path)
                        os.rmdir(path)
        if not os.listdir(root_dir):
            print('Delete', root_dir)
            os.rmdir(root_dir)
    # remove Qt5 debug files
    for path in ('/mingw64/bin/',
                 '/mingw64/lib/',
                 '/mingw64/share/qt5/plugins/'):
        root_dir = TARGET + path
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
            '/mingw64/lib/terminfo',
            '/mingw64/share/terminfo',
            '/usr/lib/terminfo',
            '/usr/share/terminfo'):
        root_dir = TARGET + path
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
            '/mingw32.exe',
            '/mingw32.ini',
            '/mingw64/bin/qdoc.exe',
            '/mingw64/bin/Qt53D*',
            '/mingw64/bin/Qt5Designer*',
            '/mingw64/lib/Qt53D*',
            '/mingw64/lib/Qt5Designer*',
            '/mingw64/lib/libQt53D*',
            '/mingw64/lib/libQt5Designer*',
            '/var/lib/pacman/sync/mingw32.db',
            '/var/lib/pacman/sync/mingw32.db.sig',
            ):
        target_path = TARGET + path
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
