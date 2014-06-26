Installation
============

Photini is not as simple to install as I would like, mainly because of the libraries required to access photographs' metadata.
The installation process is different for Windows, Linux and MacOS, and there are variations with different versions of those operating systems.
If you run into problems, please let me know (email jim@jim-easterbrook.me.uk) and once we've worked out what needs to be done I'll be able to improve these instructions.

Essential dependencies
----------------------

These are all required for Photini to be usable.

Python
^^^^^^

Photini should work with all versions of `Python <https://www.python.org/>`_ from 2.6 onwards, but the Picasa uploader requires a library that has not yet been ported to Python 3.
Linux users should use their package manager to install Python.
Windows and MacOS users can download an installer from https://www.python.org/downloads/.

PyQt
^^^^

The `PyQt <http://www.riverbankcomputing.co.uk/software/pyqt/>`_ application framework provides the graphical user interface elements used by Photini.
Version 4 is required.
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

gexiv2 (Linux & MacOS)
^^^^^^^^^^^^^^^^^^^^^^

The latest Python bindings to `Exiv2 <http://www.exiv2.org/>`_ use the "introspection bindings" to `gexiv2 <https://wiki.gnome.org/Projects/gexiv2>`_, which is a GObject wrapper around Exiv2.
Linux users should use their package manager to install these bindings, but note that the package name is not obvious.
The core gexiv2 wrapper is probably called ``libgexiv2`` or similar, but on my OpenSUSE system the introspection bindings are called ``typelib-1_0-GExiv2-0_4`` whereas on Ubuntu systems they are called ``gir1.2-gexiv2-0.4``.

There is a choice of library to provide Python bindings to gexiv2.
`PyGObject <https://wiki.gnome.org/Projects/PyGObject>`_ has been used in Photini development, but `pgi <https://pypi.python.org/pypi/pgi/>`_ is a pure Python alternative that should be compatible.
Linux users can use their package manager to install ``python-gobject`` or pip can be used to install pgi::

   sudo pip install pgi

pyexiv2 (Windows)
^^^^^^^^^^^^^^^^^

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

   sudo pip install Photini --allow-unverified Photini

Note the ``--allow-unverified Photini`` option.
This is required as pip downloads Photini from `GitHub <https://github.com/jim-easterbrook/Photini>`_ instead of `PyPI <https://pypi.python.org/pypi/Photini/>`_.

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

On many computers you can add Photini to the desktop "start menu" or similar.
For example, right-clicking on the KDE start menu allows one to "edit applications" and then add Photini to the "Graphics/Photography" section.
