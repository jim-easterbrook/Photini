#  Photini - a simple photo metadata editor.
#  http://github.com/jim-easterbrook/Photini
#  Copyright (C) 2020-22  Jim Easterbrook  jim@jim-easterbrook.me.uk
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
            if re.match(r'\d{4}\.\d{1,2}\.\d', tag_name):
                latest = tag.commit.committed_date
                last_release = tag_name
    # set current version number
    last_release = [int(x) for x in last_release.split('.')]
    major, minor, micro = last_release[:3]
    version = [int(x) for x in __version__.split('.')]
    if len(version) == 3:
        # update normal version number based on date
        today = date.today()
        if today.year == major and today.month == minor:
            micro += 1
        else:
            micro = 0
        version = '{:4d}.{:d}.{:d}'.format(today.year, today.month, micro)
    else:
        # update bug fix version number
        if len(last_release) == 3:
            bug_fix = 1
        else:
            bug_fix = last_release[3] + 1
        version = '{:4d}.{:d}.{:d}.{:d}'.format(major, minor, micro, bug_fix)
    # update __init__.py if anything's changed
    new_text = """\"\"\"Full documentation is at https://photini.readthedocs.io/\"\"\"

__version__ = '{:s}'
build = '{:d} ({:s})'
""".format(version, dev_no, commit)
    if new_text != init_text:
        with open(INIT_FILE, 'w') as vf:
            vf.write(new_text)


if __name__ == "__main__":
    sys.exit(main())
