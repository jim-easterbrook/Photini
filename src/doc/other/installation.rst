.. This is part of the Photini documentation.
   Copyright (C)  2012-20  Jim Easterbrook.
   See the file DOC_LICENSE.txt for copying conditions.

Installation
============

There are several ways to install Photini.
On Windows you can use an all-in-one installer or you can use MSYS2_.
On some Linux distributions you might be able to use your package manager to install everything.
On other platforms you need to install several dependencies before installing Photini.

All-in-one installer (Windows)
------------------------------

The Windows installers create a stand-alone MSYS2_ installation with all the dependencies needed to run Photini.
This is a minimal MSYS2 and Python system, and should not conflict with any other Python version installed on your computer, or any other MSYS2 installation.

Previous installers (from before May 2019) used a "portable Python" system based on WinPython_.
If you have a Photini installation from one of these installers you should remove it using the "Programs and Features" control panel item, and ensure the installation folder (e.g. ``C:\Program Files (x86)\Photini`` has been removed, before using the new installer.

You can download the Windows installers from the GitHub `Windows installers`_ page.
These install the latest version of Photini, even if the installer is older.
There are installers for 32 bit and 64 bit Windows, and they should work on any version since Windows XP.

When you run the installer you will probably get a security warning because the installer is not signed by a recognised authority.
This is unavoidable unless I purchase a certificate with which to sign the installer.
As I don't make any money from Photini this is unlikely to happen!

The installer should finish by running the Photini program.
If this works then you have successfully installed Photini and can ignore the rest of these instructions.
If not, see the troubleshooting_ section below.

Upgrading all-in-one installation
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Before upgrading Photini you should check the `Windows installers`_ page to see if a new Windows installer has been released since you last downloaded it.
If there is a new installer available then you should use it to create a fresh installation, after using the "Programs and Features" control panel item to uninstall the old version of Photini.

To upgrade an existing installation you need to run an MSYS2_ "command shell".
Open the folder where Photini is installed (probably ``C:\Program Files (x86)\Photini``) and run the ``mingw64.exe`` program in the ``msys2`` folder (use ``mingw32.exe`` if you have a 32-bit installation).
This program needs to be run as administrator.
Then follow the instructions in :ref:`upgrading MSYS2 installation <upgrading-msys2>` below.

MSYS2 (Windows)
---------------

An alternative to the Windows standalone installer is to use a full installation of MSYS2_.
This is not that difficult to do, but will need almost 3 GBytes of disc space, and half an hour of your time.
Installing Photini this way ensures its dependencies are up to date and should be easier to update in future.

The following instructions assume you are using 64-bit Windows.
If you are on a 32-bit machine you'll need to install the 32-bit (``i686`` instead of ``x86_64``) versions of everything.
Note that the 32-bit version of MSYS2_ is no longer supported.

First install MSYS2_ and update the packages as described on the MSYS2 homepage.
You do not need to install it as ``C:\msys64``, but you probably should avoid using spaces in the directory name.
You should also avoid installing in ``C:\Program Files`` or ``C:\Program Files (x86)`` so you don't have to use administrator privileges to make any changes.
Run the ``C:\msys64\mingw64.exe`` shell and use pacman_ to install Photini's dependencies::

   pacman -S $MINGW_PACKAGE_PREFIX-{gexiv2,python-gobject,python-pyqt5,python-pip,python-pillow}

This will take some time as over 300 MByte will be downloaded.
(The Qt package itself is 175 MByte!)
When it's finished you can free up some disc space with the ``pacman -Scc`` command.

Use pip_ to install Photini::

   python -m pip install photini

Then run Photini::

   python -m photini.editor

.. _upgrading-msys2:

Upgrading MSYS2 installation
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Run the ``mingw64.exe`` shell and update pacman_, then use it to update all installed packages::

   pacman -Syu
   pacman -Su

Use pip_ to update Photini::

   python -m pip install -U photini

Note that pip_ may warn that you are using an old version of pip and instruct you to update it with pip.
DO NOT DO THIS!
The MSYS2_ installation of pip has been patched to work with Windows paths and should only be upgraded using pacman_.

.. versionadded:: 2020.12.0
   After installing or upgrading Photini you should (re)install the start menu shortcuts, as described in the `installing menu entries`_ section.

If you use the Flickr uploader this can also be installed or updated with pip_::

   python -m pip install -U flickrapi keyring

Installing the spell checker components uses pacman_::

   pacman -S $MINGW_PACKAGE_PREFIX-gspell

You'll also need to install one or more dictionaries.
To get a list of available dictionaries::

   pacman -Ss dictionar

Note the use of ``dictionar`` as a search term - it matches ``dictionary`` or ``dictionaries``.
This search will show 32-bit and 64-bit versions of the dictionary packages.
Make sure you choose the correct one, prefaced by ``mingw32`` or ``mingw64``.
For example, to install the 64-bit French dictionaries::

   pacman -S mingw-w64-x86_64-aspell-fr

The MSYS2 repositories only provide dictionaries for a few languages, but it is possible to install from other sources.
See the :ref:`configuration page <configuration-spell>` for more information.

The FFmpeg_ package is needed to read metadata from video files::

   pacman -S $MINGW_PACKAGE_PREFIX-ffmpeg

When you've finished you can close the command shell with the ``exit`` command.

Package manager (some Linux distributions)
------------------------------------------

Ubuntu and derived systems
^^^^^^^^^^^^^^^^^^^^^^^^^^

You might discover PPAs (personal package archives) that include Photini.
Unfortunately the ones that I know of are very out of date and should not be used.

OpenSUSE
^^^^^^^^

Photini is part of the official release of Leap and Tumbleweed versions and can be installed with YaST.

Piecemeal installation
----------------------

This is the most time consuming way to install Photini.
Different operating systems have different names for the same packages.
If you run into problems, please let me know (email jim@jim-easterbrook.me.uk) and once we've worked out what needs to be done I'll be able to improve these instructions.

Essential dependencies
----------------------

These are all required for Photini to be usable.
In general you should use your operating system's package manager to install these, to avoid breaking other software installed on your computer by installing an incompatible version.
If a package is not available from the system's package manager (or is not already in use by other software) then you can use pip_ to install it from PyPI_.
You may need to use ``pip3`` rather than ``pip`` to install Python3 packages.

=============================  =================  ============================  =================
Package                        Minimum version    Typical Linux package name    PyPI package name
=============================  =================  ============================  =================
Python_                        3.6                python3
PyQt_ [1]                      5.0.0              python3-qt5 or python3-pyqt5  PyQt5
PySide2_ [1]                   5.11.0             python3-pyside2               PySide2
QtWebEngine_ or QtWebKit_ [2]                     python3-pyqt5.qtwebkit
gexiv2_ [3]                    0.10               libgexiv2-2
gexiv2 introspection data                         typelib-1_0-GExiv2-0_10 or
                                                  gir1.2-gexiv2-0.10
PyGObject_ [4]                                    python3-gobject or
                                                  python3-gi
pgi_ [4]                       0.0.8                                            pgi
appdirs                        1.3                python3-appdirs               appdirs
requests_                      2.4                python3-requests              requests
six                            1.5                python3-six                   six
=============================  =================  ============================  =================

[1] PyQt_ and PySide2_ are both Python interfaces to the Qt GUI framework.
Photini version 2020.12.0 and later can use either PyQt or PySide2, so you can install whichever one you prefer.
If both are installed you can choose which one Photini uses by editing its :ref:`configuration file <configuration-pyqt>`.

[2] Photini needs the Python version of either QtWebEngine_ or QtWebKit_.
One of these may already be included in your PyQt_ or PySide2_ installation.
QtWebEngine is preferred, but is not available on all operating systems.
If you have both you can choose which one Photini uses by editing its :ref:`configuration file <configuration-pyqt>`.

[3] Several libraries are needed to access photograph metadata from Python.
Exiv2_ is the core "C" library.
gexiv2_ is a GObject wrapper around the Exiv2 library.
It has extra "introspection bindings" that allow it to be used by other languages.
PyGObject_ or pgi_ provide a Python interface to the introspection bindings of the GObject wrapper around the Exiv2 library.
Got that?

[4] pgi_ is a pure Python alternative to PyGObject_ that may be more reliable on some systems, despite its author's warnings about its experimental status.
If pgi doesn't work on your system you can go back to using PyGObject by uninstalling pgi::

   sudo pip uninstall pgi

.. _installation-photini:

Installing Photini
------------------

The easiest way to install the latest release of Photini is with the pip_ command::

   sudo pip install photini

This will install Photini and any Python packages it requires, for all users.
If you prefer a single-user installation, which doesn't require root permission, you can use the ``--user`` option::

   pip install photini --user

You can also use pip to install the optional dependencies when you install Photini::

   sudo pip install photini[flickr,google,importer]

If you prefer to use the development version you can use git to clone the `GitHub repository <https://github.com/jim-easterbrook/Photini>`_ or download it as a zip or tar.gz file and then unpack it.
Then set your working directory to the Photini top level directory before continuing.

You can run Photini without installing it, using the ``run_photini.py`` script::

   python src/run_photini.py

This can be useful during development as the script should also work within an IDE.

The development version can be built and installed using pip::

   sudo python -m pip install .

or::

   python -m pip install . --user

You will need to install the optional dependencies separately.

If you'd like to test or use one of Photini's translation files you will need to update and compile the translations before installing or running Photini::

   python utils/extract_program.py
   python setup.py lrelease

This requires the Qt "linguist" software to be installed.
See :ref:`localisation-program-testing` for more information about using translations.

Installing menu entries
-----------------------

.. versionadded:: 2020.12.0

In previous versions of Photini installing with pip_ created start menu (Windows) or application menu (Linux) entries to run Photini.
Recent versions of pip have made this a lot more difficult, so now the menu entries need to be created after installation.
Run a command window, as described in the troubleshooting_ section, then run Photini's post installation command::

   sudo photini-post-install

(Windows users should omit the ``sudo``.)
If you only want menu entries for a single user, run the command with the ``--user`` (or ``-u``) option::

   photini-post-install --user

The menu entries can be removed with the ``--remove`` (or ``-r``) option::

   sudo photini-post-install --remove

You need to do this **before** uninstalling Photini, as the post installation command gets deleted when Photini is uninstalled.

.. _installation-optional:

Optional dependencies
---------------------

Some of Photini's features are optional - if you don't install these libraries Photini will work but the relevant feature will not be available.
As before, you should use your system's package manager to install these if possible, otherwise use pip_.
The system package manager names will probably have ``python-`` or ``python3-`` prefixes.

============================  =================
Feature                       Dependencies
============================  =================
Spell check                   Gspell_ (e.g. ``typelib-1_0-Gspell-1_0``, ``gir1.2-gspell-1``) or pyenchant_ 1.6+
Flickr upload                 flickrapi_ 2.0+, keyring_ 7.0+
Google Photos upload          `requests-oauthlib`_ 1.0+, keyring_ 7.0+
Thumbnail creation[1]         FFmpeg_, Pillow_ 2.0+
Import photos from camera[2]  `python-gphoto2`_ 0.10+
Import GPS logger file        gpxpy_ 1.3.5+
============================  =================

[1] Photini can create thumbnail images using PyQt, but better quality ones can be made by installing Pillow.
FFmpeg is needed to generate thumbnails for video files, but it can also make them for some still image formats.

[2]Photini can import pictures from any directory on your computer (e.g. a memory card) but on Linux and MacOS systems it can also import directly from a camera if python-gphoto2 is installed.
Installation of python-gphoto2 will require the "development headers" versions of Python and libgphoto2.
You should be able to install these with your system package manager.

Running Photini
---------------

If the installation has been successful you should be able to run Photini from the "Start" menu (Windows) or application launcher (Linux).

.. _installation-troubleshooting:

Troubleshooting
^^^^^^^^^^^^^^^

If Photini fails to run for some reason you may be able to find out why by trying to run it in a command window.
On Windows you need to open the folder where Photini is installed (probably ``C:\Program Files (x86)\Photini``) and run the ``mingw64.exe`` program in the ``msys2`` folder.
This program needs to be run as administrator.
(Use ``mingw32.exe`` if you have a 32-bit installation.)
On Linux you can run any terminal or console program.

Start the Photini program as follows.
If it fails to run you should get some diagnostic information::

   python3 -m photini.editor

If you need more help, please email jim@jim-easterbrook.me.uk.
It would probably be helpful to copy any diagnostic messages into your email.
I would also find it useful to know what version of Photini and some of its dependencies you are running.
You can find out with the ``--version`` option::

   python3 -m photini.editor --version

Some versions of PyQt may fail to work properly with Photini, even causing a crash at startup.
If this happens you may be able to circumvent the problem by editing the :ref:`Photini configuration file <configuration-pyqt>` before running Photini.

Mailing list
------------

For more general discussion of Photini (e.g. release announcements, questions about using it, problems with installing, etc.) there is an email list or forum hosted on Google Groups.
You can view previous messages and ask to join the group at https://groups.google.com/forum/#!forum/photini.

.. _installation-documentation:

Photini documentation
---------------------

If you would like to have a local copy of the Photini documentation, and have downloaded or cloned the source files, you can install `Sphinx <http://sphinx-doc.org/index.html>`_ and then "compile" the documentation::

   sudo pip install sphinx
   python utils/build_docs.py

Open ``doc/html/index.html`` with a web browser to read the local documentation.

.. _Exiv2:             http://exiv2.org/
.. _FFmpeg:            https://ffmpeg.org/
.. _flickrapi:         https://stuvel.eu/flickrapi/
.. _gexiv2:            https://wiki.gnome.org/Projects/gexiv2
.. _GitHub releases:   https://github.com/jim-easterbrook/Photini/releases
.. _Windows installers: https://github.com/jim-easterbrook/Photini/releases/tag/2020.4.0-win
.. _gpxpy:             https://pypi.org/project/gpxpy/
.. _Gspell:            https://wiki.gnome.org/Projects/gspell
.. _keyring:           https://keyring.readthedocs.io/
.. _MSYS2:             http://www.msys2.org/
.. _NumPy:             http://www.numpy.org/
.. _OpenCV:            http://opencv.org/
.. _pacman:            https://wiki.archlinux.org/index.php/Pacman
.. _pgi:               https://pgi.readthedocs.io/
.. _Pillow:            http://pillow.readthedocs.io/
.. _pip:               https://pip.pypa.io/en/latest/
.. _PyEnchant:         http://pythonhosted.org/pyenchant/
.. _PyGObject:         https://pygobject.readthedocs.io/
.. _Python:            https://www.python.org/
.. _python-gphoto2:    https://pypi.python.org/pypi/gphoto2/
.. _PyPI:              https://pypi.python.org/pypi
.. _PyQt:              http://www.riverbankcomputing.co.uk/software/pyqt/
.. _PySide2:           https://doc.qt.io/qtforpython/
.. _QtWebEngine:       https://wiki.qt.io/QtWebEngine
.. _QtWebKit:          https://wiki.qt.io/Qt_WebKit
.. _requests:          http://python-requests.org/
.. _requests-oauthlib: https://requests-oauthlib.readthedocs.io/
.. _requests-toolbelt: https://toolbelt.readthedocs.io/
.. _WinPython:         http://winpython.github.io/
