.. This is part of the Photini documentation.
   Copyright (C)  2012-21  Jim Easterbrook.
   See the file DOC_LICENSE.txt for copying conditions.

Installation
============

Installing Photini is not always a simple process.
On some Linux distributions you might be able to use your package manager to install everything.
On other platforms you need to install several dependencies before installing Photini.

Windows
-------

Installing Photini on Windows is done in two stages.
First install Python_ (if you don't already have Windows Python installed) and then use pip_ to install Photini and its dependencies.

Python
^^^^^^

Python_ is absolutely essential to run Photini.
It is already installed on many computers, but on Windows you will almost certainly need to install it yourself.
Go to https://www.python.org/downloads/ and choose a suitable Windows installer.
I suggest you use the 64-bit stable release with the highest version number that will run on your version of Windows.

When you run the Python installer make sure you select the "add Python to PATH" option.
If you customise your installation then make sure you still select "pip".
If you would like other users to be able to run Photini then you need to install Python for all users.

.. highlight:: none

After installing Python, start a shell (e.g. ``cmd.exe``) and try running ``pip``::

    C:\Users\Jim>pip list
    Package    Version
    ---------- -------
    pip        21.1.1
    setuptools 56.0.0
    WARNING: You are using pip version 21.1.1; however, version 21.2.4 is available.

    You should consider upgrading via the 'c:\users\jim\appdata\local\programs\python\python38\python.exe -m pip install --upgrade pip' command.

As suggested, you should upgrade pip now.
(If you installed Python for all users you will need to run the shell as administrator.)
Note that ``pip`` must be run as ``python -m pip`` when upgrading itself::

    C:\Users\Jim>python -m pip install -U pip
    Requirement already satisfied: pip in c:\users\jim\appdata\local\programs\python\python38\lib\site-packages (21.1.1)
    Collecting pip
      Downloading pip-21.2.4-py3-none-any.whl (1.6 MB)
         |████████████████████████████████| 1.6 MB 652 kB/s
    Installing collected packages: pip
      Attempting uninstall: pip
        Found existing installation: pip 21.1.1
        Uninstalling pip-21.1.1:
          Successfully uninstalled pip-21.1.1
    Successfully installed pip-21.2.4

Photini
^^^^^^^

Now that Python is installed you can install Photini and the dependencies as listed in :ref:`essential-dependencies`.
You can start by installing PySide2_::

    C:\Users\Jim>pip install pyside2
    Collecting pyside2
      Downloading PySide2-5.15.2-5.15.2-cp35.cp36.cp37.cp38.cp39-none-win_amd64.whl (136.3 MB)
         |████████████████████████████████| 136.3 MB 12 kB/s
    Collecting shiboken2==5.15.2
      Downloading shiboken2-5.15.2-5.15.2-cp35.cp36.cp37.cp38.cp39-none-win_amd64.whl (2.3 MB)
         |████████████████████████████████| 2.3 MB 595 kB/s
    Installing collected packages: shiboken2, pyside2
    Successfully installed pyside2-5.15.2 shiboken2-5.15.2

Note that this installed two packages, pyside2 and shiboken2.
This is because ``pip`` knows what packages other packages depend on installs them if required.

The rest of the dependencies are installed similarly::

    C:\Users\Jim>pip install python-exiv2 photini

Now you should be able to run photini::

    C:\Users\Jim>python -m photini.editor
    ffmpeg not found
    No module named 'enchant'
    No module named 'gi'
    No module named 'gpxpy'
    QWindowsEGLStaticContext::create: Could not initialize EGL display: error 0x3001

    QWindowsEGLStaticContext::create: When using ANGLE, check if d3dcompiler_4x.dll is available
    No module named 'requests_oauthlib'
    No module named 'requests_oauthlib'

Note the list of ``No module named...`` statements.
These are optional dependencies that add functionality to Photini, for example ``enchant`` is used for spell checking.
See :ref:`installation-optional` for a full list.

Photini can be started more directly from a command shell::

    C:\Users\Jim>photini

However, most Windows users would probably prefer to use the start menu or a desktop icon.
These can be installed with the ``photini-post-install`` command::

    C:\Users\Jim>photini-post-install

This will require administrator privileges if you are not already running your command shell as administrator.

Linux
-----

Photini is available from the package manager on some Linux distributions, but beware of versions that are very out of date.
In general I recommend installing the dependencies with the package manager, to avoid breaking other software installed on your computer by installing an incompatible version.

See :ref:`essential-dependencies` and :ref:`installation-optional` for a full list of dependencies.
Where there is a choice of package you should usually choose the one that's available from your package manager.

If a package is not available from the system's package manager (or is not already in use by other software) then you can use ``pip`` to install it from PyPI_.
You may need to use ``pip3`` rather than ``pip`` to install Python3 packages.

Different operating systems have different names for the same packages.
If you run into problems, please let me know (email jim@jim-easterbrook.me.uk) and once we've worked out what needs to be done I'll be able to improve these instructions.

Latest release
^^^^^^^^^^^^^^

The easiest way to install the latest release of Photini is with the pip_ command::

    $ sudo pip3 install photini

This will install Photini and any Python packages it requires, for all users.
If you prefer a single-user installation, which doesn't require root permission, you can use the ``--user`` option::

    $ pip3 install photini --user

You can also use pip to install the optional dependencies when you install Photini::

    $ sudo pip3 install photini[flickr,google,importer]

.. _installation-photini:

Development version
^^^^^^^^^^^^^^^^^^^

If you prefer to use the development version you can use git to clone the `GitHub repository <https://github.com/jim-easterbrook/Photini>`_ or download it as a zip or tar.gz file and then unpack it.
Then set your working directory to the Photini top level directory before continuing.

You can run Photini without installing it, using the ``run_photini.py`` script::

    $ python3 src/run_photini.py

This can be useful during development as the script should also work within an IDE.

The development version can be built and installed using pip::

    $ sudo pip3 install .

or::

    $ pip3 install . --user

You will need to install the optional dependencies separately.

If you'd like to test or use one of Photini's translation files you will need to update and compile the translations before installing or running Photini::

    $ python3 utils/extract_program.py
    $ python3 setup.py lrelease

This requires the Qt "linguist" software to be installed.
See :ref:`localisation-program-testing` for more information about using translations.

Installing menu entries
-----------------------

.. versionadded:: 2020.12.0

In previous versions of Photini installing with pip_ created start menu (Windows) or application menu (Linux) entries to run Photini.
Recent versions of pip have made this a lot more difficult, so now the menu entries need to be created after installation.
Run a command window, as described in the troubleshooting_ section, then run Photini's post installation command::

    $ sudo photini-post-install

or ::

    C:\>photini-post-install

If you only want menu entries for a single user, run the command with the ``--user`` (or ``-u``) option::

    $ photini-post-install --user

The menu entries can be removed with the ``--remove`` (or ``-r``) option::

    $ sudo photini-post-install --remove

You need to do this **before** uninstalling Photini, as the post installation command gets deleted when Photini is uninstalled.

.. _essential-dependencies:

Essential dependencies
----------------------

These are all required for Photini to be usable.

=============================  =================  ============================  =================
Package                        Minimum version    Typical Linux package name    PyPI package name
=============================  =================  ============================  =================
Python_                        3.6                python3
PyQt_ [1]                      5.0.0              python3-qt5 or python3-pyqt5  PyQt5
PySide2_ [1]                   5.11.0             python3-pyside2               PySide2
QtWebEngine_ or QtWebKit_ [2]                     python3-pyqt5.qtwebkit        PyQtWebEngine
`python-exiv2`_ [3]            0.3.1                                            python-exiv2
appdirs                        1.3                python3-appdirs               appdirs
requests_                      2.4                python3-requests              requests
=============================  =================  ============================  =================

[1] PyQt_ and PySide2_ are both Python interfaces to the Qt GUI framework.
Photini version 2020.12.0 and later can use either PyQt or PySide2, so you can install whichever one you prefer.
If both are installed you can choose which one Photini uses by editing its :ref:`configuration file <configuration-pyqt>`.

[2] Photini needs the Python version of either QtWebEngine_ or QtWebKit_.
One of these may already be included in your PyQt_ or PySide2_ installation.
QtWebEngine is preferred, but is not available on all operating systems.
If you have both you can choose which one Photini uses by editing its :ref:`configuration file <configuration-pyqt>`.

[3] `python-exiv2`_ is a new interface to the Exiv2_ library.
If you cannot install it on your computer then you need to install these packages:

=============================  =================  ============================  =================
Package                        Minimum version    Typical Linux package name    PyPI package name
=============================  =================  ============================  =================
gexiv2_ [4]                    0.10.3             libgexiv2-2
gexiv2 introspection data                         typelib-1_0-GExiv2-0_10 or
                                                  gir1.2-gexiv2-0.10
PyGObject_ [5]                                    python3-gobject or
                                                  python3-gi
pgi_ [5]                       0.0.8                                            pgi
=============================  =================  ============================  =================

[4] This is a more circuitous way to access photograph metadata from Python.
Exiv2_ is the core "C" library.
gexiv2_ is a GObject wrapper around the Exiv2 library.
It has extra "introspection bindings" that allow it to be used by other languages.
PyGObject_ or pgi_ provide a Python interface to the introspection bindings of the GObject wrapper around the Exiv2 library.

[5] pgi_ is a pure Python alternative to PyGObject_ that may be more reliable on some systems, despite its author's warnings about its experimental status.
If pgi doesn't work on your system you can go back to using PyGObject by uninstalling pgi::

    $ sudo pip3 uninstall pgi

.. _installation-optional:

Optional dependencies
---------------------

Some of Photini's features are optional - if you don't install these libraries Photini will work but the relevant feature will not be available.
As before, you should use your system's package manager to install these if possible, otherwise use pip_.
The system package manager names will probably have ``python-`` or ``python3-`` prefixes.

============================  =================
Feature                       Dependencies
============================  =================
Spell check                   pyenchant_ 1.6+ or Gspell_ (e.g. ``typelib-1_0-Gspell-1_0``, ``gir1.2-gspell-1``)
Flickr upload                 `requests-oauthlib`_ 1.0+, `requests-toolbelt`_ 0.9+, keyring_ 7.0+
Google Photos upload          `requests-oauthlib`_ 1.0+, keyring_ 7.0+
Thumbnail creation[1]         FFmpeg_, Pillow_ 2.0+
Import photos from camera[2]  `python3-gphoto2`_ 0.10+
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
On Windows you need to run a command shell, for example ``cmd.exe``.
On Linux you can run any terminal or console program.

Start the Photini program as follows.
If it fails to run you should get some diagnostic information::

    C:\>python -m photini.editor

or ::

    $ python3 -m photini.editor

If you need more help, please email jim@jim-easterbrook.me.uk.
It would probably be helpful to copy any diagnostic messages into your email.
I would also find it useful to know what version of Photini and some of its dependencies you are running.
You can find out with the ``--version`` option::

    $ python3 -m photini.editor --version

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

    $ sudo pip3 install sphinx
    $ python3 utils/build_docs.py

Open ``doc/html/index.html`` with a web browser to read the local documentation.

.. _Exiv2:             http://exiv2.org/
.. _FFmpeg:            https://ffmpeg.org/
.. _gexiv2:            https://wiki.gnome.org/Projects/gexiv2
.. _GitHub releases:   https://github.com/jim-easterbrook/Photini/releases
.. _Windows installers: https://github.com/jim-easterbrook/Photini/releases/tag/2020.4.0-win
.. _gpxpy:             https://pypi.org/project/gpxpy/
.. _Gspell:            https://gitlab.gnome.org/GNOME/gspell
.. _keyring:           https://keyring.readthedocs.io/
.. _MSYS2:             http://www.msys2.org/
.. _NumPy:             http://www.numpy.org/
.. _OpenCV:            http://opencv.org/
.. _pacman:            https://wiki.archlinux.org/index.php/Pacman
.. _pgi:               https://pgi.readthedocs.io/
.. _Pillow:            http://pillow.readthedocs.io/
.. _pip:               https://pip.pypa.io/en/latest/
.. _PyEnchant:         https://pypi.org/project/pyenchant/
.. _PyGObject:         https://pygobject.readthedocs.io/
.. _Python:            https://www.python.org/
.. _python-exiv2:      https://pypi.org/project/python-exiv2/
.. _python3-gphoto2:   https://pypi.org/project/gphoto2/
.. _PyPI:              https://pypi.org/
.. _PyQt:              http://www.riverbankcomputing.co.uk/software/pyqt/
.. _PySide2:           https://doc.qt.io/qtforpython/
.. _QtWebEngine:       https://wiki.qt.io/QtWebEngine
.. _QtWebKit:          https://wiki.qt.io/Qt_WebKit
.. _requests:          http://python-requests.org/
.. _requests-oauthlib: https://requests-oauthlib.readthedocs.io/
.. _requests-toolbelt: https://toolbelt.readthedocs.io/
.. _WinPython:         http://winpython.github.io/
