Introduction
============

Photini is an easy to use digital photograph metadata editor.
"Metadata" is said to mean "data about data".
In the context of digital photographs this means information that isn't essential in order to display the image, but tells you something about it.
For example a title and description of the scene or the date & time and the GPS coördinates of the camera's position when the picture was taken.

Getting Photini
---------------

You can download the latest version of Photini from `Github <https://github.com/jim-easterbrook/Photini>`_.
If you have git installed on your computer, and are familiar with its use, then the best way to download it will be to clone the repository.
This will make it easier to update your copy when new features are added or bugs are fixed.

If you prefer to download a single archive file, go to the `Python Package Index (PyPI) <http://pypi.python.org/pypi/Photini>`_ and download the zip or tar.gz file.
Save the file on your computer, then extract all the files in it in the usual way.

The next task is to install the various dependencies.

Dependencies (Linux)
^^^^^^^^^^^^^^^^^^^^

Many Linux installations will already have `Python <http://python.org/>`_ installed, but if not you should be able to get it easily from the standard repository.
This should also be the case for `PyQt <http://www.riverbankcomputing.co.uk/software/pyqt/intro>`_.
`GExiv2 <http://redmine.yorba.org/projects/gexiv2/wiki>`_ may be in the repository.
If not, you should be able to build and install it yourself.
See the `"Building and installing" <http://redmine.yorba.org/projects/gexiv2/wiki>`_ instructions for details.
Only if you can't install GExiv2 should you use `pyexiv2 <http://tilloy.net/dev/pyexiv2/overview.html>`_.
It has some bugs which prevent Photini from saving location data correctly.
pyexiv2 may be in the repository.
If not, you should be able to download it from the `pyexiv2 download page <http://tilloy.net/dev/pyexiv2/download.html>`_.
As a last resort, you may need to compile and install it yourself, following `these instructions <http://tilloy.net/dev/pyexiv2/developers.html#building-and-installing>`_.

If you would like to use Photini to upload photos to Flickr, you will also need to install `python-flickrapi <http://stuvel.eu/flickrapi#installation>`_.
This is available from some Linux distributions' repositories, or via ``easy_install``.
See the python-flickrapi website for details.

Dependencies (Windows)
^^^^^^^^^^^^^^^^^^^^^^

Windows users will probably need to install `Python <http://python.org/>`_ and `PyQt <http://www.riverbankcomputing.co.uk/software/pyqt/intro>`_ themselves.
Installers are available from the `Python download page <http://www.python.org/download/>`_ and the `PyQt4 download page <http://www.riverbankcomputing.co.uk/software/pyqt/download>`_.
Make sure you get Python version 2.7 and the corresponding PyQt installer.
Windows installers for `pyexiv2 <http://tilloy.net/dev/pyexiv2/overview.html>`_ are available from the `pyexiv2 download page <http://tilloy.net/dev/pyexiv2/download.html>`_.
Again, make sure you get the installer for Python 2.7 and the latest version of pyexiv2.

If you would like to use Photini to upload photos to Flickr, you will also need to install `python-flickrapi <http://stuvel.eu/flickrapi#installation>`_.
This appears to be a pure Python package, so ``easy_install`` is probably the best way to install it on Windows.
See the python-flickrapi website for details.

Installing Photini
------------------

Having installed all the dependencies it's a good idea to test Photini.
Open a terminal command window and navigate to the directory you downloaded it to, then navigate to the ``code`` subdirectory.
You should then be able to run the Photini editor with one of the following commands.

Linux::

  python photini/editor.py

Windows::

  c:\python27\python.exe photini\editor.py

This should launch the GUI and you should then be able to switch to the "map" tab and load a Google map.

Whilst it is perfectly possible to use Photini from its download directory, it is more convenient to install it in your Python's "site-packages" and "scripts" directories.
This is fully automated by the setup.py script.

Linux::

  python setup.py build
  sudo python setup.py install

Windows::

  c:\python27\python.exe setup.py build
  c:\python27\python.exe setup.py install

After doing this the Photini editor can be launched from any command window with a simple ``photini`` command.
Windows users can also put a link to ``c:\python27\scripts\photini.bat`` on their desktop.