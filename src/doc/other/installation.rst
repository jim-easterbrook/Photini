.. This is part of the Photini documentation.
   Copyright (C)  2012-18  Jim Easterbrook.
   See the file DOC_LICENSE.txt for copying conditions.

Installation
============

There are three ways to install Photini.
On Windows you can use an all-in-one installer.
On some Linux distributions you might be able to use your package manager to install everything, or you may be able to use the package manager to install Photini's dependencies and pip_ to install Photini.
On other platforms you need to install several dependencies before installing Photini.

All-in-one installer (Windows)
------------------------------

The Windows installer creates a standalone Python installation with all the dependencies needed to run Photini.
The standalone Python interpreter is only used to run Photini, and should not conflict with any other Python version installed on your computer.

You can download the latest Windows installer from the `GitHub releases`_ page.
Look for the most recent release with a ``.exe`` file listed in its downloads, e.g. ``photini-win32-2018.02.exe``.
This is a Windows installer for the latest version of Photini, even if it's listed under an older release.
The installer is suitable for 32 bit and 64 bit Windows, and should work on any version since Windows XP.

When you run the installer you will probably get a security warning because the installer is not signed by a recognised authority.
This is unavoidable unless I purchase a certificate with which to sign the installer.
As I don't make any money from Photini this is unlikely to happen!

The installer should finish by running the Photini program.
If this works then you have successfully installed Photini and can ignore the rest of these instructions.
If not, see the troubleshooting_ section below.

Upgrading all-in-one installation
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Before upgrading Photini you should check the `GitHub releases`_ page to see if a new Windows installer has been released since you last downloaded it.
If it hasn't, then you can use the "upgrade Photini" command in the start menu.
This needs to be run as administrator.
Click on the "Start" icon, then select "All Programs", then "Photini", then right-click on "upgrade Photini" and choose "Run as administrator" from the context menu.

If there is a new installer available then you should download it and use it to create a fresh installation, after using the "Programs and Features" control panel item to uninstall the old version of Photini.

Package manager (some Linux distributions)
------------------------------------------

.. note:: These Linux packages are maintained by other people and may not install the latest version of Photini.
   You may also need to install further dependencies, as described below.

Ubuntu and derived systems
^^^^^^^^^^^^^^^^^^^^^^^^^^

Dariusz Duma (https://launchpad.net/~dhor) has added Photini to his PPA (personal package archive).
See the instructions at http://linuxg.net/how-to-install-photini-15-01-1-on-ubuntu-14-10-ubuntu-14-04-and-derivative-systems/.

Pascal Mons (https://launchpad.net/~anton+) also has a PPA with many photo applications, including Photini.
See https://launchpad.net/~anton+/+archive/ubuntu/photo-video-apps/.

OpenSUSE 42.2 or newer
^^^^^^^^^^^^^^^^^^^^^^

Photini is available from the Packman community repository.
It can be installed by clicking on this link: http://packman.links2linux.org/install/Photini

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

==============  =================  ============================  =================
Package         Minimum version    Typical Linux package name    PyPI package name
==============  =================  ============================  =================
Python_         2.6 (3 preferred)  python3
PyQt_           4 (5 preferred)    python3-qt5 or python3-pyqt5  PyQt5
                                   (qt5-webkit may also be
                                   needed)
gexiv2_ [1]     0.10               typelib-1_0-GExiv2-0_10 or
                                   gir1.2-gexiv2-0.10
PyGObject_ [2]                     python3-gobject or
                                   python3-gi
pgi_ [2]        0.0.8                                            pgi
appdirs         1.3                python3-appdirs               appdirs
requests_       2.4                python3-requests              requests
six             1.5                python3-six                   six
==============  =================  ============================  =================

[1] Several libraries are needed to access photograph metadata from Python.
Exiv2_ is the core "C" library.
gexiv2_ is a GObject wrapper around the Exiv2 library.
It has extra "introspection bindings" that allow it to be used by other languages.
PyGObject_ or pgi_ provide a Python interface to the introspection bindings of the GObject wrapper around the Exiv2 library.
Got that?

[2] pgi_ is a pure Python alternative to PyGObject that I have found to be more reliable, despite its author's warnings about its experimental status.
If pgi doesn't work on your system you can go back to using PyGObject by uninstalling pgi::

   sudo pip uninstall pgi

.. _installation-photini:

Installing Photini
------------------

The easiest way to install the latest release of Photini is with the pip_ command::

   sudo pip install photini

This will install Photini and any Python packages it requires.
You can also use pip to install the optional dependencies when you install Photini::

   sudo pip install photini[flickr,google,importer,spelling]

If you prefer to install the development version you can use git to clone the `GitHub repository <https://github.com/jim-easterbrook/Photini>`_ or download it as a zip file and then unpack it.
Either way, you then need to build and install Photini::

   python setup.py build
   sudo python setup.py install

You will also need to install the remaining Python packages.

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
Google Photos upload          keyring_ 7.0+, `requests-oauthlib`_ 0.4+
Thumbnail creation[1]         NumPy_ 1.8+, OpenCV_ 3.0+, Pillow_ 2.0+
Import photos from camera[2]  `python-gphoto2`_ 0.10+
============================  =================

[1] Photini can create thumbnail images using PyQt, but better quality ones can be made by installing Pillow.
The NumPy and OpenCV packages are only required to generate thumbnails from video files.
You may still find that Photini can't read image data from video files.
Running it from the command line (see troubleshooting_) may show why.
(The OpenCV library writes messages to the console rather than raise a Python exception.)

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
On Windows you need to open the folder where Photini is installed (probably ``C:\Program Files (x86)\Photini``) and run the ``WinPython Command Prompt.exe`` program.
On Linux you can run any terminal or console program.

Start the Photini program as follows.
If it fails to run you should get some diagnostic information::

   python -m photini.editor

If you need more help, please email jim@jim-easterbrook.me.uk.
It would probably be helpful to copy any diagnostic messages into your email.
I would also find it useful to know what version of Photini and some of its dependencies you are running.
You can find out with the ``--version`` option::

   python -m photini.editor --version

Some versions of PyQt may fail to work properly with Photini, even causing a crash at startup.
If this happens you may be able to circumvent the problem by editing the :ref:`Photini configuration file <configuration-pyqt>` before running Photini.

Mailing list
------------

For more general discussion of Photini (e.g. release announcements, questions about using it, problems with installing, etc.) there is an email list or forum hosted on Google Groups.
You can view previous messages and ask to join the group at https://groups.google.com/forum/#!forum/photini.

.. _installation-documentation:

Photini documentation
---------------------

If you would like to have a local copy of the Photini documentation, and have downloaded or cloned the source files, you can install `Sphinx <http://sphinx-doc.org/index.html>`_ and use setup.py to "compile" the documentation::

   sudo pip install sphinx
   python -B setup.py build_sphinx

Open ``doc/html/index.html`` with a web browser to read the local documentation.

.. _Exiv2:             http://exiv2.org/
.. _flickrapi:         https://stuvel.eu/flickrapi/
.. _gexiv2:            https://wiki.gnome.org/Projects/gexiv2
.. _GitHub releases:   https://github.com/jim-easterbrook/Photini/releases
.. _Gspell:            https://wiki.gnome.org/Projects/gspell
.. _keyring:           https://keyring.readthedocs.io/
.. _NumPy:             http://www.numpy.org/
.. _OpenCV:            http://opencv.org/
.. _pgi:               https://pgi.readthedocs.io/
.. _Pillow:            http://pillow.readthedocs.io/
.. _pip:               https://pip.pypa.io/en/latest/
.. _PyEnchant:         http://pythonhosted.org/pyenchant/
.. _PyGObject:         https://pygobject.readthedocs.io/
.. _Python:            https://www.python.org/
.. _python-gphoto2:    https://pypi.python.org/pypi/gphoto2/
.. _PyPI:              https://pypi.python.org/pypi
.. _PyQt:              http://www.riverbankcomputing.co.uk/software/pyqt/
.. _requests:          https://github.com/kennethreitz/requests/
.. _requests-oauthlib: https://requests-oauthlib.readthedocs.io/
.. _requests-toolbelt: https://toolbelt.readthedocs.io/
