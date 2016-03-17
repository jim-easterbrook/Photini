#
# spec file for package python3-photini-meta
#
#  Photini - a simple photo metadata editor.
#  http://github.com/jim-easterbrook/Photini
#  Copyright (C) 2016  Jim Easterbrook  jim@jim-easterbrook.me.uk
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

Name:           python3-photini-meta
Version:	1
Release:	0
License:	GPLv3
Summary:	Photini metadata editor dependencies

BuildArch:	noarch

Requires:	python3-devel
Requires:	python3-qt5
Requires:	typelib(GExiv2)
Requires:	python3-gobject
Requires:	libgphoto2-devel
Requires:	dbus-1-python3
Requires:	python3-pip

%description
Meta package to install Photini's dependencies, Python 3 version.

%prep

%build

%clean

%install

%post

%postun

%files
