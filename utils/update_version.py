#  Photini - a simple photo metadata editor.
#  http://github.com/jim-easterbrook/Photini
#  Copyright (C) 2020  Jim Easterbrook  jim@jim-easterbrook.me.uk
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

# requires GitPython - 'sudo pip install gitpython'
import git

INIT_FILE = 'src/photini/__init__.py'

# read current version info without importing package
with open(INIT_FILE) as f:
    init_text = f.read()
exec(init_text)


def main(argv=None):
    # get GitHub repo information
    repo = git.Repo()
    if not repo.is_dirty():
        return
    dev_no = int(build.split()[0])
    commit = build.split()[1][1:-1]
    # increment dev_no when there's been a commit
    last_commit = str(repo.head.commit)[:7]
    if last_commit != commit:
        dev_no += 1
        commit = last_commit
    # get latest release tag
    latest = 0
    for tag in repo.tags:
        if tag.commit.committed_date > latest:
            tag_name = str(tag)
            if re.match(r'\d{4}\.\d{1,2}\.\d$', tag_name):
                latest = tag.commit.committed_date
                last_release = tag_name
    # set current version number (calendar based)
    major, minor, micro = map(int, last_release.split('.'))
    today = date.today()
    if today.year == major and today.month == minor:
        micro += 1
    else:
        micro = 0
    # update __init__.py if anything's changed
    new_text = """from __future__ import unicode_literals

__version__ = '{:4d}.{:d}.{:d}'
build = '{:d} ({:s})'
""".format(today.year, today.month, micro, dev_no, commit)
    if new_text != init_text:
        with open(INIT_FILE, 'w') as vf:
            vf.write(new_text)


if __name__ == "__main__":
    sys.exit(main())
