.. This is part of the Photini documentation.
   Copyright (C)  2012-15  Jim Easterbrook.
   See the file DOC_LICENSE.txt for copying condidions.

Installation
============

There are three ways to install Photini.
On Windows you can use an all-in-one installer.
On some Linux distributions you might be able to use your package manager.
On other platforms you need to install several dependencies before installing Photini.

All-in-one installer (Windows)
------------------------------

The Windows installer creates a standalone Python installation with all the dependencies needed to run Photini.
The standalone Python interpreter is only used to run Photini, and should not conflict with any other Python version installed on your computer.

You can download the latest Windows installer from the `GitHub releases <https://github.com/jim-easterbrook/Photini/releases>`_ page.
Don't worry if there are newer releases of Photini itself - the installer will download and install the latest release of Photini when it is run.
The installer is suitable for 32 bit and 64 bit Windows, and should work on any version since Windows XP.

The installer should finish by running the Photini program.
If this works then you have successfully installed Photini and can ignore the rest of these instructions.

Upgrading all-in-one installation
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The Windows installer adds an "upgrade Photini" command to the start menu.
This needs to be run as administrator.
Click on the "Start" icon, then select "All Programs", then "Photini", then right-click on "upgrade Photini" and choose "Run as administrator" from the context menu.

Alternatively, you can use the "Programs and Features" control panel item to uninstall Photini before running the installer again to install the latest version.

Verifying the Windows installer
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The Windows installer is digitally signed using a "self-signed Certificate Authority".
If you add my certificate to your computer you will get fewer security warnings when you install Photini.
You can download the certificate file ``jim_easterbrook_CA.cer`` from the `GitHub releases <https://github.com/jim-easterbrook/Photini/releases>`_ page and install it by running ``cmd.exe`` and issuing the following command::

   certutil -user -addstore Root jim_easterbrook_CA.cer

If you want to check the validity of the certificate file, you can do so using GnuPG.
The file ``jim_easterbrook_CA.cer.asc`` contains a digital signature that can be checked with my public keys ``959AF9B6`` or ``4748AD59``.

If the above means nothing to you, don't worry about it.
The security warnings when you install Photini can safely be ignored.

Package manager (some Linux distributions)
------------------------------------------

.. note:: These Linux packages are maintained by other people and may not install the latest version of Photini.
   You may also need to install missing dependencies, as described below.

Ubuntu and derived systems
^^^^^^^^^^^^^^^^^^^^^^^^^^

Dariusz Duma (https://launchpad.net/~dhor) has added Photini to his PPA (personal package archive).
See the instructions at http://linuxg.net/how-to-install-photini-15-01-1-on-ubuntu-14-10-ubuntu-14-04-and-derivative-systems/.

OpenSUSE and Fedora
^^^^^^^^^^^^^^^^^^^

Togan Muftuoglu (https://build.opensuse.org/user/show/toganm) has created a python-photini package.
See https://build.opensuse.org/package/show/home:toganm:photography/python-photini for more information.

Piecemeal installation
----------------------

Photini is not as simple to install as I would like, mainly because of the libraries required to access photographs' metadata.
The installation process is different for Windows, Linux and MacOS, and there are variations with different versions of those operating systems.
If you run into problems, please let me know (email jim@jim-easterbrook.me.uk) and once we've worked out what needs to be done I'll be able to improve these instructions.

Essential dependencies
----------------------

These are all required for Photini to be usable.

Python
^^^^^^

Photini should work with all versions of `Python <https://www.python.org/>`_ from 2.6 onwards.

Python may already be installed on your computer.
To find out, open a terminal window (Windows users run ``cmd.exe``) and try running python by typing this command::

   python -V

If Python is installed this should show you the version number.

Linux users should use their system's package manager to install Python.
Windows and MacOS users can download an installer from https://www.python.org/downloads/.
Windows users should install the 32 bit version of Python, even on a 64 bit machine.
This is because some of the required libraries are not available in 64 bit builds.

PyQt
^^^^

The `PyQt <http://www.riverbankcomputing.co.uk/software/pyqt/>`_ application framework provides the graphical user interface elements used by Photini.
Version 4 or 5 is required.

You can check if PyQt is already installed with one of these commands::

   python -c "import PyQt5"

or ::

   python -c "import PyQt4"

If PyQt is installed then one of these will run without generating any error message.

Linux users should use their package manager to install ``python-qt4`` or ``python-qt5``.
Windows users can download a binary installer from http://www.riverbankcomputing.co.uk/software/pyqt/download (make sure you choose the installer for your version of Python).

six
^^^

`six <https://pypi.python.org/pypi/six/>`_ is a small module that makes it easier to write Python code that works with versions 2 & 3.
The best way to install it is with `pip <https://pip.pypa.io/en/latest/>`_.
Linux users should use their package manager to install ``python-pip``.
Windows and MacOS users can use the installer from https://pip.pypa.io/en/latest/installing.html#install-pip.
All users should then `upgrade pip <https://pip.pypa.io/en/latest/installing.html#upgrade-pip>`_.

Once pip is installed, installing six is easy::

   sudo pip install six

Note that ``sudo`` is not required on Windows, or if you have root privileges.
In this case you just run ``pip install six``.

appdirs
^^^^^^^

`appdirs <https://pypi.python.org/pypi/appdirs/>`_ is a small Python module that makes cross-platform programming easier.
It is also easily installed with pip::

   sudo pip install appdirs

gexiv2 (preferred)
^^^^^^^^^^^^^^^^^^

The latest Python bindings to `Exiv2 <http://www.exiv2.org/>`_ use the "introspection bindings" to `gexiv2 <https://wiki.gnome.org/Projects/gexiv2>`_, which is a GObject wrapper around Exiv2.

Linux users should use their package manager to install these bindings, but note that the package name is not obvious.
The core gexiv2 wrapper is probably called ``libgexiv2`` or similar, but on my OpenSUSE system the introspection bindings are called ``typelib-1_0-GExiv2-0_4`` whereas on Ubuntu systems they are called ``gir1.2-gexiv2-0.4``.

Windows users should download and run the latest "pygi-aio" (PyGI all-in-one) installer from http://sourceforge.net/projects/pygobjectwin32/files/.
You should install the "Base packages" and "GExiv2" libraries, but nothing else is needed.

Linux users have a choice of library to provide Python bindings to gexiv2.
`PyGObject <https://wiki.gnome.org/Projects/PyGObject>`_ can be used, but `pgi <https://pypi.python.org/pypi/pgi/>`_ may be more reliable.
Linux users can use their package manager to install ``python-gobject`` or pip can be used to install pgi::

   sudo pip install pgi

pyexiv2 (if gexiv2 cannot be installed)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

`pyexiv2 <http://tilloy.net/dev/pyexiv2/>`_ is an older Python binding to Exiv2.
If you are unable to install gexiv2 then it can be used instead.
Windows users can download a binary installer from http://tilloy.net/dev/pyexiv2/download.html (once again, make sure you choose the installer for your version of Python).
Linux users can use their package manager to install ``python-pyexiv2``.

Optional dependencies
---------------------

Some of Photini's features are optional - if you don't install these libraries Photini will work but the relevant feature will not be available.

.. _installation-flickr:

python-flickrapi
^^^^^^^^^^^^^^^^

Photini's Flickr uploader requires `python-flickrapi <https://pypi.python.org/pypi/flickrapi/>`_.
This is easily installed with pip::

   sudo pip install flickrapi

.. _installation-picasa:

requests and requests-oauthlib
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The Google Picasa uploader requires `requests <https://github.com/kennethreitz/requests>`_ and `requests-oauthlib <https://github.com/requests/requests-oauthlib>`_.
These are also installed with pip::

   sudo pip install requests requests-oauthlib

python-keyring
^^^^^^^^^^^^^^

The Flickr and Picasa uploaders both use `python-keyring <https://pypi.python.org/pypi/keyring/>`_ to store your authorisation credentials.
This is easily installed with pip::

   sudo pip install keyring

.. _installation-importer:

python-gphoto2
^^^^^^^^^^^^^^

Photini can import pictures from many types of digital camera using `libgphoto2 <http://www.gphoto.org/proj/libgphoto2/>`_.
This is often already installed on Linux systems, but you still need its `python-gphoto2 <https://pypi.python.org/pypi/gphoto2/>`_ Python bindings, version 0.10 or greater::

   sudo pip install gphoto2

Installation of python-gphoto2 will require the "development headers" versions of Python and libgphoto2.
You should be able to install these with your system package manager.

.. _installation-photini:

Installing Photini
------------------

The easiest way to install the latest release of Photini is with the pip command::

   sudo pip install photini

You can also use pip to install the optional dependencies when you install Photini::

   sudo pip install photini[flickr,picasa,importer]

If you prefer to install the development version you can use git to clone the `GitHub repository <https://github.com/jim-easterbrook/Photini>`_ or download it as a zip file and then unpack it.
Either way, you then need to build and install Photini::

   python setup.py build
   sudo python setup.py install

Running Photini
---------------

If the installation has been successful you should be able to run Photini from the "Start" menu (Windows) or application launcher (Linux).
If that fails, you may get more helpful error messages by opening a command window and running the Photini editor module directly::

   python -m photini.editor

.. _installation-documentation:

Photini documentation
---------------------

If you would like to have a local copy of the Photini documentation, and have downloaded or cloned the source files, you can install `Sphinx <http://sphinx-doc.org/index.html>`_ and use setup.py to "compile" the documentation::

   sudo pip install sphinx
   python setup.py build_sphinx

Open ``doc/html/index.html`` with a web browser to read the local documentation.
