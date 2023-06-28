#  Photini - a simple photo metadata editor.
#  http://github.com/jim-easterbrook/Photini
#  Copyright (C) 2020-23  Jim Easterbrook  jim@jim-easterbrook.me.uk
#
#  This program is free software: you can redistribute it and/or
#  modify it under the terms of the GNU General Public License as
#  published by the Free Software Foundation, either version 3 of the
#  License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
#  General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program.  If not, see
#  <http://www.gnu.org/licenses/>.

from datetime import date
import re
import sys

import git      # GitPython package


def main(argv=None):
    # get GitHub repo information
    repo = git.Repo()
    # get latest release tag
    latest = 0
    for tag in repo.tags:
        if tag.commit.committed_date > latest:
            tag_name = str(tag)
            if re.match(r'\d{4}\.\d{1,2}\.\d', tag_name):
                latest = tag.commit.committed_date
                last_release = tag_name
    # set current version number
    last_release = tuple(int(x) for x in last_release.split('.'))
    major, minor, micro = last_release[:3]
    today = date.today()
    if today.year == major and today.month == minor:
        micro += 1
    else:
        micro = 0
    version = '{:4d}.{:d}.{:d}'.format(today.year, today.month, micro)
    # tag local git repos
    message = 'Photini-' + version + '\n\n'
    with open('CHANGELOG.txt') as cl:
        while True:
            line = cl.readline().strip()
            if line.startswith('Changes'):
                break
        cl_version = re.search(r'(\d{4}\.\d{1,2}\.\d)', line)
        if not (cl_version and cl_version.group(1) == version):
            print('Changelog line "{}" version wrong or missing'.format(line))
            return 1
        while True:
            line = cl.readline().strip()
            if not line:
                break
            message += line + '\n'
    tag = repo.create_tag(version, message=message)
    return 0


if __name__ == "__main__":
    sys.exit(main())
