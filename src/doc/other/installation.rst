.. This is part of the Photini documentation.
   Copyright (C)  2012-23  Jim Easterbrook.
   See the file DOC_LICENSE.txt for copying conditions.

.. |nbsp| unicode:: 0xA0
    :trim:

.. highlight:: none

Installation
============

Installation of Photini is done in two parts - first install Python, then use Python to install and run Photini.

Installing Python
-----------------

Python_ is absolutely essential to run Photini.
It is already installed on many computers, but on Windows you will probably need to install it yourself.

.. tabs::
    .. group-tab:: Linux/MacOS

        Python should already be installed, but make sure you have Python |nbsp| 3.
        Open a terminal window and run the ``python3`` command::

            jim@mint:~$ python3 -V
            Python 3.8.10

        Note that the command is ``python3``.
        On many machines the ``python`` command still runs Python |nbsp| 2.
        If you do not have Python |nbsp| 3 installed then use your operating system's package manager to install it.

        You should also check what version of pip_ is installed::

            jim@mint:~$ pip3 --version
            pip 20.0.2 from /usr/lib/python3/dist-packages/pip (python 3.8)

        Most Linux systems suppress pip's normal version check, but I recommend upgrading pip anyway::

            jim@mint:~$ python3 -m pip install -U pip
            Collecting pip
              Downloading pip-23.1.2-py3-none-any.whl (2.1 MB)
                 |████████████████████████████████| 2.1 MB 755 kB/s 
            Installing collected packages: pip
              WARNING: The scripts pip, pip3, pip3.10 and pip3.8 are installed in '/home/jim/.local/bin' which is not on PATH.
              Consider adding this directory to PATH or, if you prefer to suppress this warning, use --no-warn-script-location.
            Successfully installed pip-23.1.2

        Note that pip has installed the new version in ``/home/jim/.local`` as normal users can't write to ``/usr``.
        (Don't be tempted to get round this by using ``sudo`` to run pip.
        ``/usr`` should only be written by the operating system's package manager.)
        You may need to log out and then log in again to update your PATH settings.
        (On some Linux distributions you can simply run ``source ~/.profile`` instead of logging out & in.)

        Running ``pip --version`` again shows the new version::

            jim@mint:~$ pip --version
            pip 23.1.2 from /home/jim/.local/lib/python3.8/site-packages/pip (python 3.8)


    .. group-tab:: Windows

        I suggest reading `Using Python on Windows`_ before you begin.
        Go to https://www.python.org/downloads/windows/ and choose a suitable Python |nbsp| 3 installer.
        Use the 64-bit stable release with the highest version number that will run on your version of Windows.
        Beware of using very new releases though, as some of Photini's dependencies may not have been updated to work with the latest Python.

        .. image:: ../images/screenshot_090.png

        The first main installer screen should have an option to customise the installation.
        I recommend choosing this and selecting the following options.

        .. image:: ../images/screenshot_091.png

        * Documentation: If you are installing Python only to run Photini then you don't really need the Python documentation.
        * pip: You definitely need this!
        * tcl/tk and IDLE: not needed unless you want to edit Python files.
        * Python test suite: not needed.
        * py launcher: I recommend installing the launcher for all users.

        .. image:: ../images/screenshot_092.png

        * Install for all users: this is essential if you'd like to share one installation of Photini between two or more users. I also recommend it for single users as it helps keep your Python installation separate from your Photini installation.
        * Associate files with Python: recommended.
        * Create shortcuts for installed applications: optional.
        * Add Python to environment variables: I don't recommend this. The py launcher (previous screen) is a cleaner way to run Python than adding things to your PATH environment variable.
        * Precompile standard library: recommended.
        * Download debugging symbols: not needed.
        * Download debug binaries: not needed.

        After installing Python, start a command window such as ``cmd.exe``.
        Now try running the ``py`` launcher::

            C:\Users\Jim>py --list
            Installed Pythons found by py Launcher for Windows
             -3.8-64 *

        This shows that Python 3.8 is installed and available.

        Now try running pip_.
        Note the use of ``py`` to run pip, instead of requiring the Python scripts directory to be on your PATH::

            C:\Users\Jim>py -m pip show pip
            Name: pip
            Version: 21.1.1
            Summary: The PyPA recommended tool for installing Python packages.
            Home-page: https://pip.pypa.io/
            Author: The pip developers
            Author-email: distutils-sig@python.org
            License: MIT
            Location: c:\program files\python38\lib\site-packages
            Requires:
            Required-by:

        This shows that ``pip`` is installed in ``c:\program files\python38\lib\site-packages``, which is only writeable with administrator privileges.

        If you install packages with ``pip`` as a normal user (i.e. without administrator privileges) it will put them under your "roaming" application data directory, e.g. ``c:\users\jim\appdata\roaming\python\python38\site-packages``.
        I think this is a curious choice of location and strongly recommend using a "virtual environment" to install Photini and its dependencies in your choice of location.
        
        The following instructions assume a virtual environment is in use and activated.
        If you don't use a virtual environment then replace ``python`` with ``py`` and ``pip`` with ``py -m pip``.

Installing Photini
------------------

Before installing Photini you need to decide if you are installing it for a single user or for multiple users.
Multi-user installations use a Python `virtual environment`_ to create a self contained installation that can easily be shared.
Using a virtual environment has other advantages, such as easy uninstallation, so I recommend using it for a single user installation.

Linux & MacOS users have another decision to make - whether to install Photini's dependencies with pip_ or with the operating system's package manager.
For a good introduction to the advantages and disadvantages of each I suggest reading `Managing Python packages the right way`_.
All of Photini's dependencies can be installed with pip_, but I recommend installing PySide6 / PySide2 / PyQt6 / PyQt5 (whichever is available) with the package manager to ensure you install all of its system libraries and plugins, and so that you get the same GUI style as other Qt based applications.

Virtual environment
^^^^^^^^^^^^^^^^^^^

If you are using a virtual environment you should set it up now.
You can create a virtual environment in any writeable directory.
I use the name ``photini`` and create it in my home directory:

.. tabs::
    .. group-tab:: Linux/MacOS

        ::

            jim@mint:~$ python3 -m venv photini --system-site-packages
            jim@mint:~$ source photini/bin/activate
            (photini) jim@mint:~$ python3 -m pip install -U pip
            Collecting pip
              Using cached pip-23.1.2-py3-none-any.whl (2.1 MB)
            Installing collected packages: pip
              Attempting uninstall: pip
                Found existing installation: pip 20.0.2
                Uninstalling pip-20.0.2:
                  Successfully uninstalled pip-20.0.2
            Successfully installed pip-23.1.2

        The option ``--system-site-packages`` makes packages installed with the system package manager (e.g. PySide6 / PySide2 / PyQt6 / PyQt5) available within the virtual environment.
        Note that pip may need to be updated again from within the virtual environment.

    .. group-tab:: Windows

        ::

            C:\Users\Jim>py -m venv photini

            C:\Users\Jim>photini\Scripts\activate.bat

            (photini) C:\Users\Jim>python -m pip install -U pip
            Requirement already satisfied: pip in c:\users\jim\photini\lib\site-packages (21.1.1)
            Collecting pip
              Downloading pip-23.3.1-py3-none-any.whl (2.1 MB)
                 |████████████████████████████████| 2.1 MB 327 kB/s
            Installing collected packages: pip
              Attempting uninstall: pip
                Found existing installation: pip 21.1.1
                Uninstalling pip-21.1.1:
                  Successfully uninstalled pip-21.1.1
            Successfully installed pip-23.3.1

        Note that after activating the virtual environment the ``py`` command is not needed.
        Python, pip, and other Python based commands are run directly.
        After creating the virtual environment you should update ``pip`` as shown above.
        This ensures that the latest version will be used to install Photini.

You should stay in this virtual environment while installing and testing Photini.

Qt package
^^^^^^^^^^

Photini uses the Qt_ Framework for its graphical user interface.
There are two current versions of Qt (Qt5 and Qt6) and each has two Python interfaces (PyQt and PySide).
Hence there are four Python Qt packages - PyQt5, PyQt6, PySide2, and PySide6.
Photini works with any one of these, but there isn't one of them that works on all platforms.
For example, Qt6 does not work on Windows versions earlier than Windows |nbsp| 10.

After installing Photini the ``photini-configure`` command can be used to choose a Qt package.
This allows you to try each until you find one that works satisfactorily on your computer.

Initial installation
^^^^^^^^^^^^^^^^^^^^

Firstly install Photini with pip_:

.. tabs::
    .. code-tab:: none Linux/MacOS

        (photini) jim@mint:~$ pip3 install photini
        Collecting photini
          Downloading Photini-2023.7.0-py3-none-any.whl (381 kB)
             ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 381.9/381.9 kB 561.1 kB/s eta 0:00:00
        Collecting appdirs>=1.3 (from photini)
          Downloading appdirs-1.4.4-py2.py3-none-any.whl (9.6 kB)
        Collecting cachetools>=3.0 (from photini)
          Downloading cachetools-5.3.1-py3-none-any.whl (9.3 kB)
        Requirement already satisfied: chardet>=3.0 in /usr/lib/python3/dist-packages (from photini) (3.0.4)
        Collecting exiv2>=0.14 (from photini)
          Downloading exiv2-0.14.1-cp38-cp38-manylinux_2_17_x86_64.manylinux2014_x86_64.whl (7.8 MB)
             ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 7.8/7.8 MB 703.9 kB/s eta 0:00:00
        Requirement already satisfied: requests>=2.4 in /usr/lib/python3/dist-packages (from photini) (2.22.0)
        Installing collected packages: exiv2, appdirs, cachetools, photini
        Successfully installed appdirs-1.4.4 cachetools-5.3.1 exiv2-0.14.1 photini-2023.7.0
    .. code-tab:: none Windows

        (photini) C:\Users\Jim>pip install photini
        Collecting photini
          Downloading Photini-2023.10.0-py3-none-any.whl.metadata (10 kB)
        Collecting appdirs>=1.3 (from photini)
          Downloading appdirs-1.4.4-py2.py3-none-any.whl (9.6 kB)
        Collecting cachetools>=3.0 (from photini)
          Downloading cachetools-5.3.2-py3-none-any.whl.metadata (5.2 kB)
        Collecting chardet>=3.0 (from photini)
          Downloading chardet-5.2.0-py3-none-any.whl.metadata (3.4 kB)
        Collecting exiv2>=0.14 (from photini)
          Downloading exiv2-0.14.1-cp38-cp38-win_amd64.whl.metadata (7.6 kB)
        Collecting requests>=2.4 (from photini)
          Downloading requests-2.31.0-py3-none-any.whl.metadata (4.6 kB)
        Collecting charset-normalizer<4,>=2 (from requests>=2.4->photini)
          Downloading charset_normalizer-3.3.1-cp38-cp38-win_amd64.whl.metadata (33 kB)
        Collecting idna<4,>=2.5 (from requests>=2.4->photini)
          Downloading idna-3.4-py3-none-any.whl (61 kB)
             -------------------------------------- 61.5/61.5 kB 205.2 kB/s eta 0:00:00
        Collecting urllib3<3,>=1.21.1 (from requests>=2.4->photini)
          Downloading urllib3-2.0.7-py3-none-any.whl.metadata (6.6 kB)
        Collecting certifi>=2017.4.17 (from requests>=2.4->photini)
          Downloading certifi-2023.7.22-py3-none-any.whl.metadata (2.2 kB)
        Downloading Photini-2023.10.0-py3-none-any.whl (382 kB)
           -------------------------------------- 382.4/382.4 kB 540.9 kB/s eta 0:00:00
        Downloading cachetools-5.3.2-py3-none-any.whl (9.3 kB)
        Downloading chardet-5.2.0-py3-none-any.whl (199 kB)
           -------------------------------------- 199.4/199.4 kB 483.7 kB/s eta 0:00:00
        Downloading exiv2-0.14.1-cp38-cp38-win_amd64.whl (1.8 MB)
           ---------------------------------------- 1.8/1.8 MB 884.3 kB/s eta 0:00:00
        Downloading requests-2.31.0-py3-none-any.whl (62 kB)
           ---------------------------------------- 62.6/62.6 kB 239.0 kB/s eta 0:00:00
        Downloading certifi-2023.7.22-py3-none-any.whl (158 kB)
           -------------------------------------- 158.3/158.3 kB 430.5 kB/s eta 0:00:00
        Downloading charset_normalizer-3.3.1-cp38-cp38-win_amd64.whl (97 kB)
           ---------------------------------------- 98.0/98.0 kB 373.4 kB/s eta 0:00:00
        Downloading urllib3-2.0.7-py3-none-any.whl (124 kB)
           -------------------------------------- 124.2/124.2 kB 430.1 kB/s eta 0:00:00
        Installing collected packages: exiv2, appdirs, urllib3, idna, charset-normalizer, chardet, certifi, cachetools, requests, photini
        Successfully installed appdirs-1.4.4 cachetools-5.3.2 certifi-2023.7.22 chardet-5.2.0 charset-normalizer-3.3.1 exiv2-0.14.1 idna-3.4 photini-2023.10.0 requests-2.31.0 urllib3-2.0.7

Photini's optional dependencies can be included in the installation by listing them as "extras" in the pip command.
For example, if you want to be able to upload to Flickr and Ipernity:

.. tabs::
    .. code-tab:: none Linux/MacOS

        (photini) jim@mint:~$ pip3 install "photini[flickr,ipernity]"
    .. code-tab:: none Windows

        (photini) C:\Users\Jim>pip install photini[flickr,ipernity]

Note that the extras' names are not case-sensitive.

.. versionadded:: 2023.7.0
    You can install all of Photini's optional dependencies by adding an ``all`` extra.
    You can also install any of the Qt packages as extras:

.. tabs::
    .. code-tab:: none Linux/MacOS

        (photini) jim@mint:~$ pip3 install "photini[all,pyqt5,pyside6]"
    .. code-tab:: none Windows

        (photini) C:\Users\Jim>pip install photini[all,pyqt5,pyside6]

Now run the ``photini-configure`` command to choose which Qt package to use.
(The Windows example is running Windows |nbsp| 7, so PyQt6 and PySide6 are not available):

.. tabs::
    .. code-tab:: none Linux/MacOS

        (photini) jim@mint:~$ photini-configure
        Which Qt package would you like to use?
          0 PyQt5 [installed]
          1 PySide2 [installed]
          2 PyQt6 [not installed]
          3 PySide6 [not installed]
        Choose 0/1/2/3: 0
        Would you like to upload pictures to Flickr? (y/n): 
        Would you like to upload pictures to Google Photos? (y/n): 
        Would you like to upload pictures to Ipernity? (y/n): 
        Would you like to upload pictures to Pixelfed or Mastodon? (y/n): 
        Would you like to check spelling of metadata? (y/n) [y]: n
        Would you like to import GPS track data? (y/n) [y]: n
        Would you like to make higher quality thumbnails? (y/n) [y]: n
        Would you like to import pictures from a camera? (y/n): 
    .. code-tab:: none Windows

        (photini) C:\Users\Jim>photini-configure
        Which Qt package would you like to use?
          0 PyQt5 [not installed]
          1 PySide2 [not installed]
        Choose 0/1 [0]: 0
        Would you like to upload pictures to Flickr? (y/n) [y]: n
        Would you like to upload pictures to Google Photos? (y/n) [y]: n
        Would you like to upload pictures to Ipernity? (y/n) [y]: n
        Would you like to upload pictures to Pixelfed or Mastodon? (y/n) [y]: n
        Would you like to check spelling of metadata? (y/n) [y]: n
        Would you like to import GPS track data? (y/n) [y]: n
        Would you like to make higher quality thumbnails? (y/n) [y]: n
        c:\users\jim\photini\scripts\python.exe -m pip install photini[PyQt5]
        Requirement already satisfied: photini[PyQt5] in c:\users\jim\photini\lib\site-packages (2023.10.0)
        Requirement already satisfied: appdirs>=1.3 in c:\users\jim\photini\lib\site-packages (from photini[PyQt5]) (1.4.4)
        Requirement already satisfied: cachetools>=3.0 in c:\users\jim\photini\lib\site-packages (from photini[PyQt5]) (5.3.2)
        Requirement already satisfied: chardet>=3.0 in c:\users\jim\photini\lib\site-packages (from photini[PyQt5]) (5.2.0)
        Requirement already satisfied: exiv2>=0.14 in c:\users\jim\photini\lib\site-packages (from photini[PyQt5]) (0.14.1)
        Requirement already satisfied: requests>=2.4 in c:\users\jim\photini\lib\site-packages (from photini[PyQt5]) (2.31.0)
        Collecting PyQt5>=5.9 (from photini[PyQt5])
          Downloading PyQt5-5.15.10-cp37-abi3-win_amd64.whl.metadata (2.2 kB)
        Collecting PyQtWebEngine>=5.12 (from photini[PyQt5])
          Downloading PyQtWebEngine-5.15.6-cp37-abi3-win_amd64.whl (182 kB)
             ------------------------------------ 182.7/182.7 kB 424.7 kB/s eta 0:00:00
        Collecting PyQt5-sip<13,>=12.13 (from PyQt5>=5.9->photini[PyQt5])
          Downloading PyQt5_sip-12.13.0-cp38-cp38-win_amd64.whl.metadata (524 bytes)
        Collecting PyQt5-Qt5>=5.15.2 (from PyQt5>=5.9->photini[PyQt5])
          Downloading PyQt5_Qt5-5.15.2-py3-none-win_amd64.whl (50.1 MB)
             -------------------------------------- 50.1/50.1 MB 952.1 kB/s eta 0:00:00
        Collecting PyQtWebEngine-Qt5>=5.15.0 (from PyQtWebEngine>=5.12->photini[PyQt5])
          Downloading PyQtWebEngine_Qt5-5.15.2-py3-none-win_amd64.whl (60.0 MB)
             -------------------------------------- 60.0/60.0 MB 970.9 kB/s eta 0:00:00
        Requirement already satisfied: charset-normalizer<4,>=2 in c:\users\jim\photini\lib\site-packages (from requests>=2.4->photini[PyQt5]) (3.3.1)
        Requirement already satisfied: idna<4,>=2.5 in c:\users\jim\photini\lib\site-packages (from requests>=2.4->photini[PyQt5]) (3.4)
        Requirement already satisfied: urllib3<3,>=1.21.1 in c:\users\jim\photini\lib\site-packages (from requests>=2.4->photini[PyQt5]) (2.0.7)
        Requirement already satisfied: certifi>=2017.4.17 in c:\users\jim\photini\lib\site-packages (from requests>=2.4->photini[PyQt5]) (2023.7.22)
        Downloading PyQt5-5.15.10-cp37-abi3-win_amd64.whl (6.8 MB)
           ---------------------------------------- 6.8/6.8 MB 1.0 MB/s eta 0:00:00
        Downloading PyQt5_sip-12.13.0-cp38-cp38-win_amd64.whl (78 kB)
           ---------------------------------------- 78.3/78.3 kB 217.3 kB/s eta 0:00:00
        Installing collected packages: PyQtWebEngine-Qt5, PyQt5-Qt5, PyQt5-sip, PyQt5, PyQtWebEngine
        Successfully installed PyQt5-5.15.10 PyQt5-Qt5-5.15.2 PyQt5-sip-12.13.0 PyQtWebEngine-5.15.6 PyQtWebEngine-Qt5-5.15.2

The command asks a series of questions, then runs pip_ to install any extra dependencies that are needed, then updates your Photini configuration file.

Test the installation
^^^^^^^^^^^^^^^^^^^^^

Now you should be able to run photini:

.. tabs::
    .. code-tab:: none Linux/MacOS

        (photini) jim@mint:~$ python3 -m photini
        No module named 'enchant'
        No module named 'gpxpy'
        No module named 'requests_oauthlib'
        No module named 'requests_toolbelt'
        No module named 'requests_oauthlib'
        No module named 'requests_oauthlib'
    .. code-tab:: none Windows

        (photini) C:\Users\Jim>python -m photini
        ffmpeg or ffprobe not found
        No module named 'enchant'
        No module named 'gpxpy'
        No module named 'requests_oauthlib'
        No module named 'requests_toolbelt'
        No module named 'requests_oauthlib'
        No module named 'requests_oauthlib'

Photini should run successfully, but it lists some optional dependencies that are not installed.
These provide additional features, for example the Flickr uploader, that not all users will need to install.

Missing system packages
"""""""""""""""""""""""

On some Linux systems (e.g. Ubuntu, Debian, Mint) Photini may still not run if you've installed a Qt package with pip_ instead of the system's package manager.
In this case it may be worth doing a web search for the error messages you get.
For example, failing to load a Qt plugin (on Debian) can be cured by installing just one system package (``libxcb-xinerama0``) but the error message doesn't tell you that!

Optional dependencies
^^^^^^^^^^^^^^^^^^^^^

Most of the dependencies required for Photini's optional features can also be installed with ``photini-configure``.
Default answers are given in square brackets:

.. tabs::
    .. code-tab:: none Linux/MacOS

        (photini) jim@mint:~$ photini-configure 
        Which Qt package would you like to use?
          0 PyQt5 [installed]
          1 PySide2 [installed]
          2 PyQt6 [not installed]
          3 PySide6 [not installed]
        Choose 0/1/2/3 [0]: 
        Would you like to upload pictures to Flickr? (y/n) [y]: 
        Would you like to upload pictures to Google Photos? (y/n) [y]: 
        Would you like to upload pictures to Ipernity? (y/n) [y]: 
        Would you like to upload pictures to Pixelfed or Mastodon? (y/n) [y]: 
        Would you like to check spelling of metadata? (y/n) [y]: 
        Would you like to import GPS track data? (y/n) [y]: 
        Would you like to make higher quality thumbnails? (y/n) [y]: 
        Would you like to import pictures from a camera? (y/n) [y]: 
        /home/jim/photini/bin/python3 -m pip install photini[flickr,google,ipernity,pixelfed,spelling,gpxpy,Pillow,importer]
        Requirement already satisfied: photini[Pillow,flickr,google,gpxpy,importer,ipernity,pixelfed,spelling] in ./photini/lib/python3.8/site-packages (2023.7.0)
        Requirement already satisfied: appdirs>=1.3 in ./photini/lib/python3.8/site-packages (from photini[Pillow,flickr,google,gpxpy,importer,ipernity,pixelfed,spelling]) (1.4.4)
        Requirement already satisfied: cachetools>=3.0 in ./photini/lib/python3.8/site-packages (from photini[Pillow,flickr,google,gpxpy,importer,ipernity,pixelfed,spelling]) (5.3.1)
        Requirement already satisfied: chardet>=3.0 in /usr/lib/python3/dist-packages (from photini[Pillow,flickr,google,gpxpy,importer,ipernity,pixelfed,spelling]) (3.0.4)
        Requirement already satisfied: exiv2>=0.14 in ./photini/lib/python3.8/site-packages (from photini[Pillow,flickr,google,gpxpy,importer,ipernity,pixelfed,spelling]) (0.14.1)
        Requirement already satisfied: requests>=2.4 in /usr/lib/python3/dist-packages (from photini[Pillow,flickr,google,gpxpy,importer,ipernity,pixelfed,spelling]) (2.22.0)
        Collecting gphoto2>=1.8 (from photini[Pillow,flickr,google,gpxpy,importer,ipernity,pixelfed,spelling])
          Downloading gphoto2-2.3.4-cp38-cp38-manylinux_2_12_x86_64.manylinux2010_x86_64.whl (5.9 MB)
             ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 5.9/5.9 MB 699.7 kB/s eta 0:00:00
        Requirement already satisfied: Pillow>=2.0 in /usr/lib/python3/dist-packages (from photini[Pillow,flickr,google,gpxpy,importer,ipernity,pixelfed,spelling]) (7.0.0)
        Collecting pyenchant>=2.0 (from photini[Pillow,flickr,google,gpxpy,importer,ipernity,pixelfed,spelling])
          Downloading pyenchant-3.2.2-py3-none-any.whl (55 kB)
             ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 55.7/55.7 kB 262.1 kB/s eta 0:00:00
        Collecting gpxpy>=1.3.5 (from photini[Pillow,flickr,google,gpxpy,importer,ipernity,pixelfed,spelling])
          Downloading gpxpy-1.5.0.tar.gz (111 kB)
             ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 111.6/111.6 kB 411.6 kB/s eta 0:00:00
          Preparing metadata (setup.py) ... done
        Requirement already satisfied: keyring>=7.0 in /usr/lib/python3/dist-packages (from photini[Pillow,flickr,google,gpxpy,importer,ipernity,pixelfed,spelling]) (18.0.1)
        Collecting requests-toolbelt>=0.9 (from photini[Pillow,flickr,google,gpxpy,importer,ipernity,pixelfed,spelling])
          Downloading requests_toolbelt-1.0.0-py2.py3-none-any.whl (54 kB)
             ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 54.5/54.5 kB 237.6 kB/s eta 0:00:00
        Collecting requests-oauthlib>=1.0 (from photini[Pillow,flickr,google,gpxpy,importer,ipernity,pixelfed,spelling])
          Downloading requests_oauthlib-1.3.1-py2.py3-none-any.whl (23 kB)
        Requirement already satisfied: secretstorage in /usr/lib/python3/dist-packages (from keyring>=7.0->photini[Pillow,flickr,google,gpxpy,importer,ipernity,pixelfed,spelling]) (2.3.1)
        Requirement already satisfied: oauthlib>=3.0.0 in /usr/lib/python3/dist-packages (from requests-oauthlib>=1.0->photini[Pillow,flickr,google,gpxpy,importer,ipernity,pixelfed,spelling]) (3.1.0)
        Building wheels for collected packages: gpxpy
          Building wheel for gpxpy (setup.py) ... done
          Created wheel for gpxpy: filename=gpxpy-1.5.0-py3-none-any.whl size=42878 sha256=77a7531cbed8cd315f03427adccc74c15fbae41a01fc4e160a4c6c959fc372ff
          Stored in directory: /home/jim/.cache/pip/wheels/93/15/ce/1cd2782b440b8a517b89c3fa112f79f7015bd6e51b552e1b1a
        Successfully built gpxpy
        Installing collected packages: gphoto2, requests-toolbelt, requests-oauthlib, pyenchant, gpxpy
        Successfully installed gphoto2-2.3.4 gpxpy-1.5.0 pyenchant-3.2.2 requests-oauthlib-1.3.1 requests-toolbelt-1.0.0
    .. code-tab:: none Windows

        (photini) C:\Users\Jim>photini-configure
        Which Qt package would you like to use?
          0 PyQt5 [installed]
          1 PySide2 [not installed]
        Choose 0/1 [0]:
        Would you like to upload pictures to Flickr? (y/n) [y]:
        Would you like to upload pictures to Google Photos? (y/n) [y]:
        Would you like to upload pictures to Ipernity? (y/n) [y]:
        Would you like to upload pictures to Pixelfed or Mastodon? (y/n) [y]:
        Would you like to check spelling of metadata? (y/n) [y]:
        Would you like to import GPS track data? (y/n) [y]:
        Would you like to make higher quality thumbnails? (y/n) [y]:
        c:\users\jim\photini\scripts\python.exe -m pip install photini[flickr,google,ipernity,pixelfed,spelling,gpxpy,Pillow]
        Requirement already satisfied: photini[Pillow,flickr,google,gpxpy,ipernity,pixelfed,spelling] in c:\users\jim\photini\lib\site-packages (2023.10.0)
        Requirement already satisfied: appdirs>=1.3 in c:\users\jim\photini\lib\site-packages (from photini[Pillow,flickr,google,gpxpy,ipernity,pixelfed,spelling]) (1.4.4)
        Requirement already satisfied: cachetools>=3.0 in c:\users\jim\photini\lib\site-packages (from photini[Pillow,flickr,google,gpxpy,ipernity,pixelfed,spelling]) (5.3.2)
        Requirement already satisfied: chardet>=3.0 in c:\users\jim\photini\lib\site-packages (from photini[Pillow,flickr,google,gpxpy,ipernity,pixelfed,spelling]) (5.2.0)
        Requirement already satisfied: exiv2>=0.14 in c:\users\jim\photini\lib\site-packages (from photini[Pillow,flickr,google,gpxpy,ipernity,pixelfed,spelling]) (0.14.1)
        Requirement already satisfied: requests>=2.4 in c:\users\jim\photini\lib\site-packages (from photini[Pillow,flickr,google,gpxpy,ipernity,pixelfed,spelling]) (2.31.0)
        Collecting gpxpy>=1.3.5 (from photini[Pillow,flickr,google,gpxpy,ipernity,pixelfed,spelling])
          Downloading gpxpy-1.6.0-py3-none-any.whl.metadata (5.9 kB)
        Collecting pyenchant>=2.0 (from photini[Pillow,flickr,google,gpxpy,ipernity,pixelfed,spelling])
          Downloading pyenchant-3.2.2-py3-none-win_amd64.whl (11.9 MB)
             -------------------------------------- 11.9/11.9 MB 973.5 kB/s eta 0:00:00
        Collecting Pillow>=2.0 (from photini[Pillow,flickr,google,gpxpy,ipernity,pixelfed,spelling])
          Downloading Pillow-10.1.0-cp38-cp38-win_amd64.whl.metadata (9.6 kB)
        Requirement already satisfied: charset-normalizer<4,>=2 in c:\users\jim\photini\lib\site-packages (from requests>=2.4->photini[Pillow,flickr,google,gpxpy,ipernity,pixelfed,spelling]) (3.3.1)
        Requirement already satisfied: idna<4,>=2.5 in c:\users\jim\photini\lib\site-packages (from requests>=2.4->photini[Pillow,flickr,google,gpxpy,ipernity,pixelfed,spelling]) (3.4)
        Requirement already satisfied: urllib3<3,>=1.21.1 in c:\users\jim\photini\lib\site-packages (from requests>=2.4->photini[Pillow,flickr,google,gpxpy,ipernity,pixelfed,spelling]) (2.0.7)
        Requirement already satisfied: certifi>=2017.4.17 in c:\users\jim\photini\lib\site-packages (from requests>=2.4->photini[Pillow,flickr,google,gpxpy,ipernity,pixelfed,spelling]) (2023.7.22)
        Collecting requests-oauthlib>=1.0 (from photini[Pillow,flickr,google,gpxpy,ipernity,pixelfed,spelling])
          Downloading requests_oauthlib-1.3.1-py2.py3-none-any.whl (23 kB)
        Collecting keyring>=7.0 (from photini[Pillow,flickr,google,gpxpy,ipernity,pixelfed,spelling])
          Downloading keyring-24.2.0-py3-none-any.whl.metadata (20 kB)
        Collecting requests-toolbelt>=0.9 (from photini[Pillow,flickr,google,gpxpy,ipernity,pixelfed,spelling])
          Downloading requests_toolbelt-1.0.0-py2.py3-none-any.whl (54 kB)
             -------------------------------------- 54.5/54.5 kB 202.9 kB/s eta 0:00:00
        Collecting jaraco.classes (from keyring>=7.0->photini[Pillow,flickr,google,gpxpy,ipernity,pixelfed,spelling])
          Downloading jaraco.classes-3.3.0-py3-none-any.whl.metadata (2.9 kB)
        Collecting importlib-metadata>=4.11.4 (from keyring>=7.0->photini[Pillow,flickr,google,gpxpy,ipernity,pixelfed,spelling])
          Downloading importlib_metadata-6.8.0-py3-none-any.whl.metadata (5.1 kB)
        Collecting importlib-resources (from keyring>=7.0->photini[Pillow,flickr,google,gpxpy,ipernity,pixelfed,spelling])
          Downloading importlib_resources-6.1.0-py3-none-any.whl.metadata (4.1 kB)
        Collecting pywin32-ctypes>=0.2.0 (from keyring>=7.0->photini[Pillow,flickr,google,gpxpy,ipernity,pixelfed,spelling])
          Downloading pywin32_ctypes-0.2.2-py3-none-any.whl.metadata (3.8 kB)
        Collecting oauthlib>=3.0.0 (from requests-oauthlib>=1.0->photini[Pillow,flickr,google,gpxpy,ipernity,pixelfed,spelling])
          Downloading oauthlib-3.2.2-py3-none-any.whl (151 kB)
             ------------------------------------ 151.7/151.7 kB 274.1 kB/s eta 0:00:00
        Collecting zipp>=0.5 (from importlib-metadata>=4.11.4->keyring>=7.0->photini[Pillow,flickr,google,gpxpy,ipernity,pixelfed,spelling])
          Downloading zipp-3.17.0-py3-none-any.whl.metadata (3.7 kB)
        Collecting more-itertools (from jaraco.classes->keyring>=7.0->photini[Pillow,flickr,google,gpxpy,ipernity,pixelfed,spelling])
          Downloading more_itertools-10.1.0-py3-none-any.whl.metadata (33 kB)
        Downloading gpxpy-1.6.0-py3-none-any.whl (42 kB)
           ---------------------------------------- 42.6/42.6 kB 138.5 kB/s eta 0:00:00
        Downloading Pillow-10.1.0-cp38-cp38-win_amd64.whl (2.6 MB)
           ---------------------------------------- 2.6/2.6 MB 950.1 kB/s eta 0:00:00
        Downloading keyring-24.2.0-py3-none-any.whl (37 kB)
        Downloading importlib_metadata-6.8.0-py3-none-any.whl (22 kB)
        Downloading pywin32_ctypes-0.2.2-py3-none-any.whl (30 kB)
        Downloading importlib_resources-6.1.0-py3-none-any.whl (33 kB)
        Downloading jaraco.classes-3.3.0-py3-none-any.whl (5.9 kB)
        Downloading zipp-3.17.0-py3-none-any.whl (7.4 kB)
        Downloading more_itertools-10.1.0-py3-none-any.whl (55 kB)
           ---------------------------------------- 55.8/55.8 kB 194.8 kB/s eta 0:00:00
        Installing collected packages: zipp, pywin32-ctypes, pyenchant, Pillow, oauthlib, more-itertools, gpxpy, requests-toolbelt, requests-oauthlib, jaraco.classes, importlib-resources, importlib-metadata, keyring
        Successfully installed Pillow-10.1.0 gpxpy-1.6.0 importlib-metadata-6.8.0 importlib-resources-6.1.0 jaraco.classes-3.3.0 keyring-24.2.0 more-itertools-10.1.0 oauthlib-3.2.2 pyenchant-3.2.2 pywin32-ctypes-0.2.2 requests-oauthlib-1.3.1 requests-toolbelt-1.0.0 zipp-3.17.0

Photini's spelling checker may require some other files to be installed.
See the `pyenchant documentation`_ for platform specific instructions.

One optional dependency that cannot be installed with pip_ or ``photini-configure`` is FFmpeg_.
This is used to read metadata from video files.
Linux & MacOS users can install it with the system package manager, but installing it on Windows is non-trivial.

Start menu / application menu
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Although you can run Photini from a command shell, most users would probably prefer to use the start / application menu or a desktop icon.
These can be installed with the ``photini-post-install`` command:

.. tabs::
    .. code-tab:: none Linux/MacOS

        (photini) jim@mint:~$ photini-post-install
        desktop-file-install \
          --dir=/home/jim/.local/share/applications \
          --set-key=Exec \
          --set-value=/home/jim/photini/bin/photini %F \
          --set-key=Icon \
          --set-value=/home/jim/photini/lib/python3.8/site-packages/photini/data/icons/photini_48.png \
          --set-key=GenericName[ca] \
          --set-value=Photini editor de metadades de foto \
          --set-key=Comment[ca] \
          --set-value=Un editor de metadades de foto digital fàcil d'usar. \
          --set-key=GenericName[cs] \
          --set-value=Editor fotografických popisných údajů Photini \
          --set-key=Comment[cs] \
          --set-value=Snadno se používající editor popisů digitálních fotografií. \
          --set-key=GenericName[de] \
          --set-value=Photini-Fotometadateneditor \
          --set-key=Comment[de] \
          --set-value=Ein einfach zu bedienender Metadaten-Editor für digitale Bilder. \
          --set-key=GenericName[es] \
          --set-value=Photini editor de metadatos fotográficos \
          --set-key=Comment[es] \
          --set-value=Un editor de metadatos fotográficos fácil de usar. \
          --set-key=GenericName[fr] \
          --set-value=Éditeur de métadonnées de photos Photini \
          --set-key=Comment[fr] \
          --set-value=Une application d'édition des métadonnées des photographies numériques (Exif, IPTC, XMP) facile à utiliser. \
          --set-key=GenericName[it] \
          --set-value=Editor di metadati fotografici di Photini \
          --set-key=Comment[it] \
          --set-value=Un'applicazione di modifica dei metadati delle fotografie digitali (Exif, IPTC, XMP) facile da usare. \
          --set-key=GenericName[pl] \
          --set-value=Photini edytor metadanych zdjęcia \
          --set-key=Comment[pl] \
          --set-value=Łatwy w użyciu edytor metadanych fotografii cyfrowej. \
          /home/jim/photini/lib/python3.8/site-packages/photini/data/linux/photini.desktop
    .. code-tab:: none Windows

        (photini) C:\Users\Jim>photini-post-install
        Creating C:\Users\Jim\AppData\Roaming\Microsoft\Windows\Start Menu\Photini
        Creating C:\Users\Jim\Desktop\Photini.lnk
        Creating C:\Users\Jim\AppData\Roaming\Microsoft\Windows\Start Menu\Photini\Photini.lnk
        Creating C:\Users\Jim\AppData\Roaming\Microsoft\Windows\Start Menu\Photini\Photini documentation.url

Additional users
^^^^^^^^^^^^^^^^

If you have installed Photini in a virtual environment then other users should be able to run the ``photini`` command using its full path.
(On Windows you will need to share the virtual environment top level directory first.)

.. tabs::
    .. code-tab:: none Linux/MacOS

        sarah@mint:~$ /home/jim/photini/bin/photini
    .. code-tab:: none Windows

        C:\Users\Sarah>..\Jim\photini\Scripts\photini.exe

This is not a very convenient way to run Photini, so most users will want to add it to their start / application menu:

.. tabs::
    .. code-tab:: none Linux/MacOS

        sarah@mint:~$ /home/jim/photini/bin/photini-post-install
        sarah@mint:~$ /home/jim/photini/bin/photini-post-install 
        desktop-file-install \
          --dir=/home/sarah/.local/share/applications \
          --set-key=Exec \
          --set-value=/home/jim/photini/bin/photini %F \
          --set-key=Icon \
          --set-value=/home/jim/photini/lib/python3.8/site-packages/photini/data/icons/photini_48.png \
          --set-key=GenericName[ca] \
          --set-value=Photini editor de metadades de foto \
          --set-key=Comment[ca] \
          --set-value=Un editor de metadades de foto digital fàcil d'usar. \
          --set-key=GenericName[cs] \
          --set-value=Editor fotografických popisných údajů Photini \
          --set-key=Comment[cs] \
          --set-value=Snadno se používající editor popisů digitálních fotografií. \
          --set-key=GenericName[de] \
          --set-value=Photini-Fotometadateneditor \
          --set-key=Comment[de] \
          --set-value=Ein einfach zu bedienender Metadaten-Editor für digitale Bilder. \
          --set-key=GenericName[es] \
          --set-value=Photini editor de metadatos fotográficos \
          --set-key=Comment[es] \
          --set-value=Un editor de metadatos fotográficos fácil de usar. \
          --set-key=GenericName[fr] \
          --set-value=Éditeur de métadonnées de photos Photini \
          --set-key=Comment[fr] \
          --set-value=Une application d'édition des métadonnées des photographies numériques (Exif, IPTC, XMP) facile à utiliser. \
          --set-key=GenericName[it] \
          --set-value=Editor di metadati fotografici di Photini \
          --set-key=Comment[it] \
          --set-value=Un'applicazione di modifica dei metadati delle fotografie digitali (Exif, IPTC, XMP) facile da usare. \
          --set-key=GenericName[pl] \
          --set-value=Photini edytor metadanych zdjęcia \
          --set-key=Comment[pl] \
          --set-value=Łatwy w użyciu edytor metadanych fotografii cyfrowej. \
          /home/jim/photini/lib/python3.8/site-packages/photini/data/linux/photini.desktop
    .. code-tab:: none Windows

        C:\Users\Sarah>..\Jim\photini\Scripts\photini-post-install.exe
        Creating C:\Users\Sarah\AppData\Roaming\Microsoft\Windows\Start Menu\Photini
        Creating C:\Users\Sarah\Desktop\Photini.lnk
        Creating C:\Users\Sarah\AppData\Roaming\Microsoft\Windows\Start Menu\Photini\Photini.lnk
        Creating C:\Users\Sarah\AppData\Roaming\Microsoft\Windows\Start Menu\Photini\Photini documentation.url

To install Photini menu shortcuts for all users you can run the post install command as root (Linux) or in a command window run as administrator (Windows).
It is important to use the full path to the post install command:

.. tabs::
    .. code-tab:: none Linux/MacOS

        jim@mint:~$ sudo /home/jim/photini/bin/photini-post-install
        [sudo] password for jim:        
        desktop-file-install \
          --set-key=Exec \
          --set-value=/home/jim/photini/bin/photini %F \
          --set-key=Icon \
          --set-value=/home/jim/photini/lib/python3.8/site-packages/photini/data/icons/photini_48.png \
          --set-key=GenericName[ca] \
          --set-value=Photini editor de metadades de foto \
          --set-key=Comment[ca] \
          --set-value=Un editor de metadades de foto digital fàcil d'usar. \
          --set-key=GenericName[cs] \
          --set-value=Editor fotografických popisných údajů Photini \
          --set-key=Comment[cs] \
          --set-value=Snadno se používající editor popisů digitálních fotografií. \
          --set-key=GenericName[de] \
          --set-value=Photini-Fotometadateneditor \
          --set-key=Comment[de] \
          --set-value=Ein einfach zu bedienender Metadaten-Editor für digitale Bilder. \
          --set-key=GenericName[es] \
          --set-value=Photini editor de metadatos fotográficos \
          --set-key=Comment[es] \
          --set-value=Un editor de metadatos fotográficos fácil de usar. \
          --set-key=GenericName[fr] \
          --set-value=Éditeur de métadonnées de photos Photini \
          --set-key=Comment[fr] \
          --set-value=Une application d'édition des métadonnées des photographies numériques (Exif, IPTC, XMP) facile à utiliser. \
          --set-key=GenericName[it] \
          --set-value=Editor di metadati fotografici di Photini \
          --set-key=Comment[it] \
          --set-value=Un'applicazione di modifica dei metadati delle fotografie digitali (Exif, IPTC, XMP) facile da usare. \
          --set-key=GenericName[pl] \
          --set-value=Photini edytor metadanych zdjęcia \
          --set-key=Comment[pl] \
          --set-value=Łatwy w użyciu edytor metadanych fotografii cyfrowej. \
          /home/jim/photini/lib/python3.8/site-packages/photini/data/linux/photini.desktop
    .. code-tab:: none Windows

        C:\Windows\system32>c:\Users\Jim\photini\Scripts\photini-post-install.exe
        Creating C:\ProgramData\Microsoft\Windows\Start Menu\Photini
        Creating C:\Users\Public\Desktop\Photini.lnk
        Creating C:\ProgramData\Microsoft\Windows\Start Menu\Photini\Photini.lnk
        Creating C:\ProgramData\Microsoft\Windows\Start Menu\Photini\Photini documentation.url

Uninstalling Photini
^^^^^^^^^^^^^^^^^^^^

Before removing Photini you should use the ``photini-post-install`` command to remove it from the start / application menu:

.. tabs::
    .. code-tab:: none Linux/MacOS

        (photini) jim@mint:~$ photini-post-install --remove
        Deleting /home/jim/.local/share/applications/photini.desktop
    .. code-tab:: none Windows

        (photini) C:\Users\Jim>photini-post-install --remove
        Deleting C:\Users\Jim\Desktop\Photini.lnk
        Deleting C:\Users\Jim\AppData\Roaming\Microsoft\Windows\Start Menu\Photini\Photini.lnk
        Deleting C:\Users\Jim\AppData\Roaming\Microsoft\Windows\Start Menu\Photini\Photini documentation.url
        Deleting C:\Users\Jim\AppData\Roaming\Microsoft\Windows\Start Menu\Photini

If you used a virtual environment you can simply delete the top level directory created when setting up the virtual environment.
Otherwise you can use pip to uninstall Photini and as many of its dependencies as you want to remove:

.. tabs::
    .. code-tab:: none Linux/MacOS

        jim@mint:~$ pip3 uninstall photini exiv2
        Found existing installation: Photini 2023.7.0
        Uninstalling Photini-2023.7.0:
          Would remove:
            /home/jim/.local/bin/photini
            /home/jim/.local/bin/photini-configure
            /home/jim/.local/bin/photini-post-install
            /home/jim/.local/lib/python3.8/site-packages/Photini-2023.7.0.dist-info/*
            /home/jim/.local/lib/python3.8/site-packages/photini/*
        Proceed (Y/n)? y
          Successfully uninstalled Photini-2023.7.0
        Found existing installation: exiv2 0.14.1
        Uninstalling exiv2-0.14.1:
          Would remove:
            /home/jim/.local/lib/python3.8/site-packages/exiv2-0.14.1.dist-info/*
            /home/jim/.local/lib/python3.8/site-packages/exiv2/*
        Proceed (Y/n)? y
          Successfully uninstalled exiv2-0.14.1
    .. code-tab:: none Windows

        (photini) C:\Users\Jim>pip uninstall photini exiv2
        Found existing installation: Photini 2023.10.0
        Uninstalling Photini-2023.10.0:
          Would remove:
            c:\users\jim\photini\lib\site-packages\photini-2023.10.0.dist-info\*
            c:\users\jim\photini\lib\site-packages\photini\*
            c:\users\jim\photini\scripts\photini-configure.exe
            c:\users\jim\photini\scripts\photini-post-install.exe
            c:\users\jim\photini\scripts\photini.exe
        Proceed (Y/n)? y
          Successfully uninstalled Photini-2023.10.0
        Found existing installation: exiv2 0.14.1
        Uninstalling exiv2-0.14.1:
          Would remove:
            c:\users\jim\photini\lib\site-packages\exiv2-0.14.1.dist-info\*
            c:\users\jim\photini\lib\site-packages\exiv2\*
        Proceed (Y/n)? y
          Successfully uninstalled exiv2-0.14.1

Updating Photini
----------------

When a new release of Photini is issued you can easily update your installation with pip_.
If you installed Photini in a virtual environment then you need to activate the virtual environment before upgrading:

.. tabs::
    .. code-tab:: none Linux/MacOS

        (photini) jim@mint:~$ pip3 install -U photini
    .. code-tab:: none Windows

        (photini) C:\Users\Jim>pip install -U photini

The ``-U`` option tells pip to update Photini to the latest available version.

If you upgrade Python you shouldn't need to reinstall Photini or its dependencies if only the patch level changes (e.g. 3.8.9 to 3.8.10).
After a more significant Python upgrade (e.g. 3.7.x to 3.8.y) you will need to do a fresh installation of Photini and its dependencies.

Dependency details
------------------

These lists of dependencies may be useful to Linux or MacOS users who prefer to use their system package manager to install them instead of pip_.
Note that in some cases you have a choice of packages, as discussed in the notes below each table.

Different operating systems have different names for the same packages.
If you run into problems, please let me know (email jim@jim-easterbrook.me.uk) and once we've worked out what needs to be done I'll be able to improve these instructions.

.. _essential-dependencies:

Essential dependencies
^^^^^^^^^^^^^^^^^^^^^^

These are all required for Photini to be usable.

=============================  =================  ================================  =================
Package                        Minimum version    Typical Linux package name        PyPI package name
=============================  =================  ================================  =================
Python_                        3.6                ``python3``
PyQt_ [1]                      5.11               ``python3-qt5``
                                                  or ``python3-pyqt5``
                                                  or ``python310-PyQt6``
PySide2_ [1]                   5.11.0             ``python3-pyside2``               PySide2
PySide6_ [1]                   6.2.0              ``python3-pyside6``               PySide6
QtWebEngine_ [2]                                  ``python3-pyside2.qtwebengine``   PyQtWebEngine
                                                  or ``python310-PyQt6-WebEngine``
`python-exiv2`_                0.14.0                                               exiv2
appdirs                        1.3                ``python3-appdirs``               appdirs
requests_                      2.4                ``python3-requests``              requests
=============================  =================  ================================  =================

[1] PyQt_, PySide2_, and PySide6_ are Python interfaces to the Qt GUI framework.
Photini can use any of them (although PyQt is preferred), so you can install whichever one you prefer that is available for your operating system.
(Note that PyQt6 and PySide6 are not compatible with Windows versions earlier than Windows 10.)
If more than one of them is installed you can choose which one Photini uses by editing its :ref:`configuration file <configuration-pyqt>` or by running ``photini-configure``.

[2] Photini needs the Python interface to QtWebEngine_.
This is included in PySide6_ and some PyQt_ or PySide2_ installations, otherwise you need to install a separate package.
The ``photini-configure`` command will tell you if it's missing.

.. _installation-optional:

Optional dependencies
^^^^^^^^^^^^^^^^^^^^^

Some of Photini's features are optional - if you don't install these packages Photini will work but the relevant feature will not be available.
Linux package manager names will probably have ``python-`` or ``python3-`` prefixes.

============================  =================
Feature                       Dependencies
============================  =================
Spell check[1]                pyenchant_ 2.0+
Flickr upload                 `requests-oauthlib`_ 1.0+, `requests-toolbelt`_ 0.9+, keyring_ 7.0+
Ipernity upload               `requests-toolbelt`_ 0.9+, keyring_ 7.0+
Pixelfed upload               `requests-oauthlib`_ 1.0+, `requests-toolbelt`_ 0.9+, keyring_ 7.0+
Google Photos upload          `requests-oauthlib`_ 1.0+, keyring_ 7.0+
Thumbnail creation[2]         FFmpeg_, Pillow_ 2.0+
Import photos from camera[3]  `python3-gphoto2`_ 1.8+
Import GPS logger file        gpxpy_ 1.3.5+
============================  =================

[1] Pyenchant requires a C library and dictionaries to be installed.
See the `pyenchant documentation`_ for detailed instructions.

[2] Photini can create thumbnail images using PyQt, but better quality ones can be made by installing Pillow.
FFmpeg is needed to generate thumbnails for video files, but it can also make them for some still image formats.

[3]Photini can import pictures from any directory on your computer (e.g. a memory card) but on Linux and MacOS systems it can also import directly from a camera if python-gphoto2 is installed.

Special installations
---------------------

There are some circumstances where installing Photini from the Python Package Index (PyPI_) with pip_ is not suitable.
If you need easy access to the source files, for example to work on translating the user interface into another language, then you should install the development version.

.. _installation-photini:

Development version
^^^^^^^^^^^^^^^^^^^

To install the development version you can use git to clone the `GitHub repository <https://github.com/jim-easterbrook/Photini>`_ or download it as a .zip or .tar.gz file and then unpack it.
Then set your working directory to the Photini top level directory before continuing.

You can run Photini without installing it, using the ``run_photini.py`` script::

    $ python3 src/run_photini.py

This can be useful during development as the script should also work within an IDE.

The development version can be built and installed using pip::

    $ pip3 install . --user

If you'd like to test or use one of Photini's translation files you will need to update the translations before installing or running Photini::

    $ python3 utils/lang_update.py
    $ pip3 install . --user

This requires the Qt "linguist" software to be installed.
See :ref:`localisation-program-testing` for more information about using translations.

.. _installation-troubleshooting:

Troubleshooting
---------------

If you ever have problems running Photini the first thing to do is to run it in a command window.
If you installed Photini in a `virtual environment`_ then activate that environment, for example:

.. tabs::
    .. code-tab:: none Linux/MacOS

        jim@brains:~$ source /home/jim/photini/bin/activate
        (photini) jim@brains:~$
    .. code-tab:: none Windows

        C:\Users\Jim>c:\Users\Jim\photini\Scripts\activate.bat

        (photini) C:\Users\Jim>

Start the Photini program as follows.
If it fails to run you should get some diagnostic information:

.. tabs::
    .. code-tab:: none Linux/MacOS

        jim@brains:~$ python3 -m photini -v
    .. code-tab:: none Windows

        (photini) C:\Users\Jim>python -m photini -v

Note the use of the ``-v`` option to increase the verbosity of Photini's message logging.
This option can be repeated for even more verbosity.

To find out what version of Photini and some of its dependencies you are using, run it with the ``--version`` option:

.. tabs::
    .. code-tab:: none Linux/MacOS

        (photini) jim@mint:~$ python3 -m photini --version
        qt5ct: using qt5ct plugin
        Photini 2023.7.0, build release
          Python 3.8.10 (default, May 26 2023, 14:05:08)
        [GCC 9.4.0]
          python-exiv2 0.14.1, exiv2 0.27.7
          PyQt 5.14.1, Qt 5.12.8, locale en-GB
          PyEnchant 3.2.2
          ffmpeg version 4.2.7-0ubuntu0.1 Copyright (c) 2000-2022 the FFmpeg developers
          available styles: cleanlooks, gtk2, cde, motif, plastique, qt5ct-style, Windows, Fusion
          using style: qt5ct-style
    .. code-tab:: none Windows

        (photini) C:\Users\Jim>python -m photini --version
        ffmpeg or ffprobe not found
        Photini 2023.10.0, build release
          Python 3.8.10 (tags/v3.8.10:3d8993a, May  3 2021, 11:48:03) [MSC v.1928 64 bit (AMD64)]
          python-exiv2 0.14.1, exiv2 0.27.7
          PyQt 5.15.10, Qt 5.15.2, locale en-GB
          PyEnchant 3.2.2
          available styles: windowsvista, Windows, Fusion
          using style: windowsvista

This information is useful if you need to email me (jim@jim-easterbrook.me.uk) with any problems you have running Photini.

Mailing list
------------

For more general discussion of Photini (e.g. release announcements, questions about using it, problems with installing, etc.) there is an email list or forum hosted on Google Groups.
You can view previous messages and ask to join the group at https://groups.google.com/forum/#!forum/photini.

.. _installation-documentation:

Photini documentation
---------------------

If you would like to have a local copy of the Photini documentation, and have downloaded or cloned the source files, you can install Sphinx_ and associated packages and then "compile" the documentation::

    $ pip3 install -r src/doc/requirements.txt
    $ python3 utils/build_docs.py

Open ``doc/html/index.html`` with a web browser to read the local documentation.

.. _Exiv2:             http://exiv2.org/
.. _FFmpeg:            https://ffmpeg.org/
.. _GitHub releases:   https://github.com/jim-easterbrook/Photini/releases
.. _gpxpy:             https://pypi.org/project/gpxpy/
.. _keyring:           https://keyring.readthedocs.io/
.. _Managing Python packages the right way:
        https://opensource.com/article/19/4/managing-python-packages
.. _MSYS2:             http://www.msys2.org/
.. _pgi:               https://pgi.readthedocs.io/
.. _Pillow:            http://pillow.readthedocs.io/
.. _pip:               https://pip.pypa.io/en/latest/
.. _PyEnchant:         https://pypi.org/project/pyenchant/
.. _pyenchant documentation:
        https://pyenchant.github.io/pyenchant/install.html
.. _Python:            https://www.python.org/
.. _python-exiv2:      https://pypi.org/project/python-exiv2/
.. _python3-gphoto2:   https://pypi.org/project/gphoto2/
.. _PyPI:              https://pypi.org/
.. _PyQt:              http://www.riverbankcomputing.co.uk/software/pyqt/
.. _PySide2:           https://pypi.org/project/PySide2/
.. _PySide6:           https://pypi.org/project/PySide6/
.. _Qt:                https://wiki.qt.io/About_Qt
.. _QtWebEngine:       https://wiki.qt.io/QtWebEngine
.. _requests:          http://python-requests.org/
.. _requests-oauthlib: https://requests-oauthlib.readthedocs.io/
.. _requests-toolbelt: https://toolbelt.readthedocs.io/
.. _Sphinx:            https://www.sphinx-doc.org/
.. _Using Python on Windows:
        https://docs.python.org/3/using/windows.html
.. _virtual environment:
        https://docs.python.org/3/tutorial/venv.html
.. _WinPython:         http://winpython.github.io/
