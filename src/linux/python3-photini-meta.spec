#
# spec file for package python3-photini-meta
#

Name:           python3-photini-meta
Version:	1
Release:	0
License:	GPLv3
Summary:	Photini metadata editor dependencies

BuildArch:	noarch

Requires:	python3-devel
Requires:	python3-qt5
Requires:	typelib-1_0-GExiv2-0_4
Requires:	python3-gobject
Requires:	libgphoto2-devel
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
