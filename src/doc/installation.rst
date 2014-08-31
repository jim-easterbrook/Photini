Installation
============

There are two ways to install Photini.
The simpler is to use an all-in-one installer, currently only available for Windows.
On other platforms you need to install several dependencies before installing Photini.

All-in-one installer (Windows)
------------------------------

The Windows installer creates a standalone Python installation with all the dependencies needed to run Photini.
The standalone Python interpreter is only used to run Photini, so does not conflict with any other Python version installed on your computer.

You can download the latest Windows installer from the `GitHub releases <https://github.com/jim-easterbrook/Photini/releases>`_ page.
Don't worry if there are newer releases of Photini itself - the installer will download and install the latest release of Photini when it is run.
The installer is suitable for 32 bit and 64 bit Windows, and should work on any version since Windows XP.

The installer should finish by running the Photini program.
If this works then you have successfully installed Photini and can ignore the rest of these instructions.

Upgrading all-in-one installation
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Future versions of the Windows installer will add an "upgrade Photini" command to the start menu.
In the meantime you can upgrade Photini as follows (Windows 7 - other versions will vary):

   #. Right-click on the Photini start menu entry and then click on "properties". Note the path in the "start in" box.
   #. Find ``cmd.exe`` in the start menu, then right-click on it and click on "run as administrator". Allow it to make changes on your computer.
   #. Use ``cd`` to navigate to the "start in" path shown in the Photini shortcut properties, then to its ``Scripts`` folder. For example::

         Microsoft Windows [Version 6.1.7601]
         Copyright (c) 2009 Microsoft Corporation.  All rights reserved.

         C:\Windows\system32>cd "c:\Program Files (x86)\Photini\python-2.7.6"

         c:\Program Files (x86)\Photini\python-2.7.6>cd Scripts

         c:\Program Files (x86)\Photini\python-2.7.6\Scripts>

   #. Use ``pip`` to upgrade Photini::

         c:\Program Files (x86)\Photini\python-2.7.6\Scripts>pip install -U photini

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

Photini should work with all versions of `Python <https://www.python.org/>`_ from 2.6 onwards, but the Picasa uploader requires a library that has not yet been ported to Python 3.

Python may already be installed on your computer.
To find out, open a terminal window (Windows users run ``cmd.exe``) and try running python by typing this command::

   python -V

If Python is installed this should show you the version number.

Linux users should use their system's package manager to install Python.
Windows and MacOS users can download an installer from https://www.python.org/downloads/.
As some libraries have not yet been ported to Python 3 you should probably install version 2.7.
Windows users should install the 32 bit version of Python, even on a 64 bit machine.
This is because some of the required libraries are not available in 64 bit builds.

PyQt
^^^^

The `PyQt <http://www.riverbankcomputing.co.uk/software/pyqt/>`_ application framework provides the graphical user interface elements used by Photini.
Version 4 is required.

You can check if PyQt4 is already installed with this command::

   python -c "import PyQt4"

If PyQt4 is installed this will run without generating any error message.

Linux users should use their package manager to install ``python-qt4``.
Windows users can download a binary installer from http://www.riverbankcomputing.co.uk/software/pyqt/download (make sure you choose the installer for your version of Python).

appdirs
^^^^^^^

`appdirs <https://pypi.python.org/pypi/appdirs/>`_ is a small Python module that makes cross-platform programming easier.
The best way to install it is with `pip <https://pip.pypa.io/en/latest/>`_.
Linux users should use their package manager to install ``python-pip``.
Windows and MacOS users can use the installer from https://pip.pypa.io/en/latest/installing.html#install-pip.
All users should then `upgrade pip <https://pip.pypa.io/en/latest/installing.html#upgrade-pip>`_.

Once pip is installed, installing appdirs is easy::

   sudo pip install appdirs

Note that ``sudo`` is not required on Windows, or if you have root privileges.
In this case you just run ``pip install appdirs``.

gexiv2 (preferred)
^^^^^^^^^^^^^^^^^^

The latest Python bindings to `Exiv2 <http://www.exiv2.org/>`_ use the "introspection bindings" to `gexiv2 <https://wiki.gnome.org/Projects/gexiv2>`_, which is a GObject wrapper around Exiv2.

Linux users should use their package manager to install these bindings, but note that the package name is not obvious.
The core gexiv2 wrapper is probably called ``libgexiv2`` or similar, but on my OpenSUSE system the introspection bindings are called ``typelib-1_0-GExiv2-0_4`` whereas on Ubuntu systems they are called ``gir1.2-gexiv2-0.4``.

Windows users should download and run the latest "pygi-aio" (PyGI all-in-one) installer from http://sourceforge.net/projects/pygobjectwin32/files/.
You should install the "Base packages" and "GExiv2" libraries, but nothing else is needed.

Linux users have a choice of library to provide Python bindings to gexiv2.
`PyGObject <https://wiki.gnome.org/Projects/PyGObject>`_ has been used in Photini development, but `pgi <https://pypi.python.org/pypi/pgi/>`_ is a pure Python alternative that should be compatible.
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

Note that there is a bug in v1.4 of flickrapi that stops the upload progress bar working correctly (see `Photini issue #6 <https://github.com/jim-easterbrook/Photini/issues/6>`_).
Flickrapi v1.4 is also not compatible with Python 3.

If you are using Python 3 then you need to install version 2, which is still under development.
You can download the source from https://bitbucket.org/sybren/flickrapi and then use setup.py to build and install::

   python setup.py build
   sudo python setup.py install

.. _installation-picasa:

gdata-python-client
^^^^^^^^^^^^^^^^^^^

The Google Picasa uploader requires `gdata-python-client <https://pypi.python.org/pypi/gdata/>`_.
This is also installed with pip::

   sudo pip install gdata

Note that gdata-python-client is not compatible with Python 3.

.. _installation-importer:

python-gphoto2
^^^^^^^^^^^^^^

Photini can import pictures from many types of digital camera using `libgphoto2 <http://www.gphoto.org/proj/libgphoto2/>`_.
This is often already installed on Linux systems, but you still need its `python-gphoto2 <https://pypi.python.org/pypi/gphoto2/>`_ Python bindings.
See the `python-gphoto2 documentation <https://pypi.python.org/pypi/gphoto2/#dependencies>`_ for details of how to install it.

Installing Photini
------------------

The easiest way to install the latest release of Photini is with the pip command::

   sudo pip install Photini

If you prefer to install the development version you can use git to clone the `GitHub repository <https://github.com/jim-easterbrook/Photini>`_ or download it as a zip file and then unpack it.
Either way, you then need to build and install Photini::

   python setup.py build
   sudo python setup.py install

Note that if you are using Python 3 this process uses the `2to3 <https://docs.python.org/2/library/2to3.html>`_ tool to translate the source files.

Running Photini
---------------

If the installation has been successful you should be able to run Photini from the command line::

   photini

This should launch the Photini graphical application.
If it fails, you may get more helpful error messages by running the Photini editor module directly::

   python -m photini.editor

On many computers you can add Photini to the desktop "start menu" or similar.
For example, right-clicking on the KDE start menu allows one to "edit applications" and then add Photini to the "Graphics/Photography" section.

Photini documentation
---------------------

If you would like to have a local copy of the Photini documentation, and have downloaded or cloned the source files, you can use setup.py to "compile" the documentation::

   python setup.py build_sphinx

Open ``doc/html/index.html`` with a web browser to read the local documentation.
