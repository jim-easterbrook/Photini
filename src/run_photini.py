##  Photini - a simple photo metadata editor.
##  http://github.com/jim-easterbrook/Photini
##  Copyright (C) 2019-23  Jim Easterbrook  jim@jim-easterbrook.me.uk
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

""" This script can be used during development to run Photini without
installing it. For this to work it needs to be in the 'src' directory,
with 'photini' as a subdirectory.

"""

import os
import sys

src_dir = os.path.dirname(__file__)
version_file = os.path.join(src_dir, 'photini', '_version.py')
if not os.path.exists(version_file):
    try:
        from setuptools_scm import _get_version
        from setuptools_scm.config import Configuration
        _get_version(Configuration.from_file(
            os.path.join(os.path.dirname(src_dir), 'pyproject.toml')))
    except ImportError:
        with open(version_file, 'w') as f:
            f.write('''# file generated by run_photini.py
# don't track in version control
version = '0.0.0+unknown'
''')

from photini.editor import main

if __name__ == "__main__":
    sys.exit(main())
