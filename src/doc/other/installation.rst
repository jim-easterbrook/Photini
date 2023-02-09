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
    .. tab:: Linux/MacOS

        Python should already be installed, but make sure you have Python |nbsp| 3.
        Open a terminal window and run the ``python3`` command::

            jim@mint:~$ python3 -V
            Python 3.8.10

        Note that the command is ``python3``.
        On many machines the ``python`` command still runs Python |nbsp| 2.
        If you do not have Python |nbsp| 3 installed then use your operating system's package manager to install it.

        You should also check what version of pip_ is installed::

            jim@mint:~$ pip --version
            pip 20.0.2 from /usr/lib/python3/dist-packages/pip (python 3.8)

        Most Linux systems suppress pip's normal version check, but I recommend upgrading pip anyway::

            jim@mint:~$ python3 -m pip install -U pip
            Collecting pip
              Downloading pip-22.0.3-py3-none-any.whl (2.1 MB)
                 |████████████████████████████████| 2.1 MB 185 kB/s 
            Installing collected packages: pip
            Successfully installed pip-22.0.3
            Installing collected packages: pip
              WARNING: The scripts pip, pip3 and pip3.8 are installed in '/home/jim/.local/bin' which is not on PATH.
              Consider adding this directory to PATH or, if you prefer to suppress this warning, use --no-warn-script-location.
            Successfully installed pip-22.0.3

        Note that pip has installed the new version in ``/home/jim/.local`` as normal users can't write to ``/usr``.
        (Don't be tempted to get round this by using ``sudo`` to run pip.
        ``/usr`` should only be written by the operating system's package manager.)
        You may need to log out and then log in again to update your PATH settings.

        Running ``pip --version`` again shows the new version::

            jim@mint:~$ pip --version
            pip 22.0.3 from /home/jim/.local/lib/python3.8/site-packages/pip (python 3.8)

    .. tab:: Windows

        I suggest reading `Using Python on Windows`_ before you begin.
        Go to https://www.python.org/downloads/windows/ and choose a suitable Python |nbsp| 3 installer.
        Use the 64-bit stable release with the highest version number that will run on your version of Windows.
        Beware of using very new releases though, as some dependencies may not have been updated to work with the latest Python.

        When you run the Python installer make sure you select the "add Python to PATH" option.
        If you customise your installation then make sure you still select "pip".
        If you would like other users to be able to run Photini then you need to install Python for all users (in the "Advanced Options" part of customised installation).

        After installing Python, start a command window such as ``cmd.exe``.
        Now try running pip_::

            C:\Users\Jim>pip list
            Package    Version
            ---------- -------
            pip        21.1.1
            setuptools 56.0.0
            WARNING: You are using pip version 21.1.1; however, version 22.0.4 is available.

            You should consider upgrading via the 'c:\users\jim\appdata\local\programs\python\python38\python.exe -m pip install --upgrade pip' command.

        As suggested, you should upgrade pip now.
        (If you installed Python for all users you will need to run the shell as administrator.)
        Note that ``pip`` must be run as ``python -m pip`` when upgrading itself::

            C:\Users\Jim>python -m pip install -U pip
            Requirement already satisfied: pip in c:\users\jim\appdata\local\programs\python\python38\lib\site-packages (21.1.1)
            Collecting pip
              Downloading pip-22.0.4-py3-none-any.whl (2.1 MB)
                 |████████████████████████████████| 2.1 MB 113 kB/s
            Installing collected packages: pip
              Attempting uninstall: pip
                Found existing installation: pip 21.1.1
                Uninstalling pip-21.1.1:
                  Successfully uninstalled pip-21.1.1
            Successfully installed pip-22.0.4

Installing Photini
------------------

Before installing Photini you need to decide if you are installing it for a single user or for multiple users.
Multi-user installations use a Python `virtual environment`_ to create a self contained installation that can easily be shared.
Using a virtual environment has other advantages, such as easy uninstallation, so you could also use it for a single user installation.

Linux & MacOS users have another decision to make - whether to install Photini's dependencies with pip_ or with the operating system's package manager.
For a good introduction to the advantages and disadvantages of each I suggest reading `Managing Python packages the right way`_.
All of Photini's dependencies can be installed with pip_, but I recommend installing PySide6 / PySide2 / PyQt6 / PyQt5 (whichever is available) with the package manager to ensure you install all of its system libraries and plugins, and so that you get the same GUI style as other Qt based applications.

Virtual environment
^^^^^^^^^^^^^^^^^^^

If you are using a virtual environment you should set it up now.
I use the name ``photini`` and create it in my home directory:

.. tabs::
    .. code-tab:: none Linux/MacOS

        jim@mint:~$ python3 -m venv photini --system-site-packages
        jim@mint:~$ source photini/bin/activate
        (photini) jim@mint:~$ python3 -m pip install -U pip
    .. code-tab:: none Windows

        C:\Users\Jim>python -m venv photini
        C:\Users\Jim>photini\Scripts\activate.bat
        (photini) C:\Users\Jim>python -m pip install -U pip

Note that pip may need to be updated again from within the virtual environment.
The Linux/MacOS option ``--system-site-packages`` makes packages installed with the system package manager (e.g. PySide6 / PySide2 / PyQt6 / PyQt5) available within the virtual environment.
You should stay in this virtual environment while installing and testing Photini.

Initial installation
^^^^^^^^^^^^^^^^^^^^

.. versionadded:: 2022.9.0
    The ``photini-configure`` post installation script can be used to install most dependencies and configure Photini to use them.

Firstly install Photini with pip_:

.. tabs::
    .. code-tab:: none Linux/MacOS

        (photini) jim@mint:~$ pip3 install photini
        Collecting photini
          Downloading Photini-2022.9.0-py3-none-any.whl (324 kB)
             ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 324.9/324.9 kB 443.5 kB/s eta 0:00:00
        Collecting exiv2>=0.11.0
          Downloading exiv2-0.11.3-cp38-cp38-manylinux_2_17_x86_64.manylinux2014_x86_64.whl (8.0 MB)
             ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 8.0/8.0 MB 903.7 kB/s eta 0:00:00
        Collecting cachetools>=3.0
          Downloading cachetools-5.2.0-py3-none-any.whl (9.3 kB)
        Requirement already satisfied: requests>=2.4.0 in /usr/lib/python3/dist-packages (from photini) (2.22.0)
        Collecting appdirs>=1.3
          Downloading appdirs-1.4.4-py2.py3-none-any.whl (9.6 kB)
        Installing collected packages: exiv2, appdirs, cachetools, photini
        Successfully installed appdirs-1.4.4 cachetools-5.2.0 exiv2-0.11.3 photini-2022.9.0
    .. code-tab:: none Windows

        C:\Users\Jim>pip install photini
        Collecting photini
          Downloading Photini-2022.9.0-py3-none-any.whl (324 kB)
             ------------------------------------ 324.9/324.9 kB 718.5 kB/s eta 0:00:00
        Collecting cachetools>=3.0
          Downloading cachetools-5.2.0-py3-none-any.whl (9.3 kB)
        Collecting exiv2>=0.11.0
          Downloading exiv2-0.11.3-cp38-cp38-win_amd64.whl (1.7 MB)
             ---------------------------------------- 1.7/1.7 MB 826.9 kB/s eta 0:00:00
        Collecting appdirs>=1.3
          Downloading appdirs-1.4.4-py2.py3-none-any.whl (9.6 kB)
        Collecting requests>=2.4.0
          Downloading requests-2.28.1-py3-none-any.whl (62 kB)
             -------------------------------------- 62.8/62.8 kB 420.8 kB/s eta 0:00:00
        Collecting idna<4,>=2.5
          Downloading idna-3.4-py3-none-any.whl (61 kB)
             -------------------------------------- 61.5/61.5 kB 205.2 kB/s eta 0:00:00
        Collecting charset-normalizer<3,>=2
          Downloading charset_normalizer-2.1.1-py3-none-any.whl (39 kB)
        Collecting certifi>=2017.4.17
          Downloading certifi-2022.9.24-py3-none-any.whl (161 kB)
             ------------------------------------ 161.1/161.1 kB 482.0 kB/s eta 0:00:00
        Collecting urllib3<1.27,>=1.21.1
          Downloading urllib3-1.26.12-py2.py3-none-any.whl (140 kB)
             ------------------------------------ 140.4/140.4 kB 461.5 kB/s eta 0:00:00
        Installing collected packages: exiv2, appdirs, urllib3, idna, charset-normalizer, certifi, cachetools, requests, photini
        Successfully installed appdirs-1.4.4 cachetools-5.2.0 certifi-2022.9.24 charset-normalizer-2.1.1 exiv2-0.11.3 idna-3.4 photini-2022.9.0 requests-2.28.1 urllib3-1.26.12

Now run the ``photini-configure`` command to choose which Qt package to use:

.. tabs::
    .. code-tab:: none Linux/MacOS

        (photini) jim@mint:~$ photini-configure 
        Which Qt package would you like to use?
          0 PyQt5 [installed]
          1 PySide2 [installed]
          2 PySide6 [not installed]
        Choose 0/1/2: 1
        Would you like to upload pictures to Flickr? (y/n): 
        Would you like to upload pictures to Google Photos? (y/n): 
        Would you like to upload pictures to Ipernity? (y/n): 
        Would you like to check spelling of metadata? (y/n): 
        Would you like to import GPS track data? (y/n): 
        Would you like to make higher quality thumbnails? (y/n): 
        Would you like to import pictures from a camera? (y/n): 
    .. code-tab:: none Windows

        C:\Users\Jim>photini-configure
        Which Qt package would you like to use?
          0 PySide2 [not installed]
          1 PySide6 [not installed]
        Choose 0/1: 0
        Would you like to upload pictures to Flickr? (y/n):
        Would you like to upload pictures to Google Photos? (y/n):
        Would you like to upload pictures to Ipernity? (y/n):
        Would you like to check spelling of metadata? (y/n):
        Would you like to import GPS track data? (y/n):
        Would you like to make higher quality thumbnails? (y/n):
        c:\users\jim\appdata\local\programs\python\python38\python.exe -m pip install photini[PySide2]
        Requirement already satisfied: photini[PySide2] in c:\users\jim\appdata\local\programs\python\python38\lib\site-packages (2022.9.0)
        Requirement already satisfied: exiv2>=0.11.0 in c:\users\jim\appdata\local\programs\python\python38\lib\site-packages (from photini[PySide2]) (0.11.3)
        Requirement already satisfied: appdirs>=1.3 in c:\users\jim\appdata\local\programs\python\python38\lib\site-packages (from photini[PySide2]) (1.4.4)
        Requirement already satisfied: cachetools>=3.0 in c:\users\jim\appdata\local\programs\python\python38\lib\site-packages (from photini[PySide2]) (5.2.0)
        Requirement already satisfied: requests>=2.4.0 in c:\users\jim\appdata\local\programs\python\python38\lib\site-packages (from photini[PySide2]) (2.28.1)
        Collecting PySide2>=5.11.0
          Downloading PySide2-5.15.2.1-5.15.2-cp35.cp36.cp37.cp38.cp39.cp310-none-win_amd64.whl (137.4 MB)
             ------------------------------------ 137.4/137.4 MB 763.3 kB/s eta 0:00:00
        Collecting shiboken2==5.15.2.1
          Downloading shiboken2-5.15.2.1-5.15.2-cp35.cp36.cp37.cp38.cp39.cp310-none-win_amd64.whl (2.3 MB)
             ---------------------------------------- 2.3/2.3 MB 826.2 kB/s eta 0:00:00
        Requirement already satisfied: idna<4,>=2.5 in c:\users\jim\appdata\local\programs\python\python38\lib\site-packages (from requests>=2.4.0->photini[PySide2]) (3.4)
        Requirement already satisfied: urllib3<1.27,>=1.21.1 in c:\users\jim\appdata\local\programs\python\python38\lib\site-packages (from requests>=2.4.0->photini[PySide2]) (1.26.12)
        Requirement already satisfied: charset-normalizer<3,>=2 in c:\users\jim\appdata\local\programs\python\python38\lib\site-packages (from requests>=2.4.0->photini[PySide2]) (2.1.1)
        Requirement already satisfied: certifi>=2017.4.17 in c:\users\jim\appdata\local\programs\python\python38\lib\site-packages (from requests>=2.4.0->photini[PySide2]) (2022.9.24)
        Installing collected packages: shiboken2, PySide2
        Successfully installed PySide2-5.15.2.1 shiboken2-5.15.2.1

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
    .. code-tab:: none Windows

        C:\Users\Jim>python -m photini
        ffmpeg or ffprobe not found
        No module named 'enchant'
        No module named 'gpxpy'
        No module named 'requests_oauthlib'
        No module named 'requests_toolbelt'
        No module named 'requests_oauthlib'

Photini should run successfully, but it lists some optional dependencies that are not installed.
These provide additional features, for example the Flickr uploader, that not all users will need to install.

Missing system packages
"""""""""""""""""""""""

On some Linux systems (e.g. Ubuntu, Debian, Mint) Photini may still not run if you've installed PySide2 or PySide6 with pip_ instead of the system's package manager.
In this case it may be worth doing a web search for the error messages you get.
For example, failing to load a Qt plugin (on Debian) can be cured by installing just one system package (``libxcb-xinerama0``) but the error message doesn't tell you that!

Optional dependencies
^^^^^^^^^^^^^^^^^^^^^

Most of the dependencies required for Photini's optional features can also be installed with ``photini-configure``:

.. tabs::
    .. code-tab:: none Linux/MacOS

        (photini) jim@mint:~$ photini-configure 
        Which Qt package would you like to use?
          0 PyQt5 [installed]
          1 PySide2 [installed]
          2 PySide6 [not installed]
        Choose 0/1/2: 1
        Would you like to upload pictures to Flickr? (y/n): y
        Would you like to upload pictures to Google Photos? (y/n): y
        Would you like to upload pictures to Ipernity? (y/n): y
        Would you like to check spelling of metadata? (y/n): y
        Would you like to import GPS track data? (y/n): y
        Would you like to make higher quality thumbnails? (y/n): y
        Would you like to import pictures from a camera? (y/n): y
        /home/jim/photini/bin/python3 -m pip install photini[flickr,google,ipernity,spelling,gpxpy,Pillow,importer]
        Requirement already satisfied: photini[Pillow,flickr,google,gpxpy,importer,ipernity,spelling] in ./photini/lib/python3.8/site-packages (2022.9.0)
        Requirement already satisfied: appdirs>=1.3 in ./photini/lib/python3.8/site-packages (from photini[Pillow,flickr,google,gpxpy,importer,ipernity,spelling]) (1.4.4)
        Requirement already satisfied: cachetools>=3.0 in ./photini/lib/python3.8/site-packages (from photini[Pillow,flickr,google,gpxpy,importer,ipernity,spelling]) (5.2.0)
        Requirement already satisfied: requests>=2.4.0 in /usr/lib/python3/dist-packages (from photini[Pillow,flickr,google,gpxpy,importer,ipernity,spelling]) (2.22.0)
        Requirement already satisfied: exiv2>=0.11.0 in ./photini/lib/python3.8/site-packages (from photini[Pillow,flickr,google,gpxpy,importer,ipernity,spelling]) (0.11.3)
        Collecting requests-toolbelt>=0.9
          Downloading requests_toolbelt-0.9.1-py2.py3-none-any.whl (54 kB)
             ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 54.3/54.3 kB 241.5 kB/s eta 0:00:00
        Requirement already satisfied: keyring>=7.0 in /usr/lib/python3/dist-packages (from photini[Pillow,flickr,google,gpxpy,importer,ipernity,spelling]) (18.0.1)
        Collecting requests-oauthlib>=1.0
          Downloading requests_oauthlib-1.3.1-py2.py3-none-any.whl (23 kB)
        Requirement already satisfied: Pillow>=2.0.0 in /usr/lib/python3/dist-packages (from photini[Pillow,flickr,google,gpxpy,importer,ipernity,spelling]) (7.0.0)
        Collecting pyenchant>=2.0
          Downloading pyenchant-3.2.2-py3-none-any.whl (55 kB)
             ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 55.7/55.7 kB 269.7 kB/s eta 0:00:00
        Collecting gphoto2>=1.8.0
          Downloading gphoto2-2.3.4-cp38-cp38-manylinux_2_12_x86_64.manylinux2010_x86_64.whl (5.9 MB)
             ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 5.9/5.9 MB 900.6 kB/s eta 0:00:00
        Collecting gpxpy>=1.3.5
          Downloading gpxpy-1.5.0.tar.gz (111 kB)
             ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 111.6/111.6 kB 313.3 kB/s eta 0:00:00
          Preparing metadata (setup.py) ... done
        Requirement already satisfied: secretstorage in /usr/lib/python3/dist-packages (from keyring>=7.0->photini[Pillow,flickr,google,gpxpy,importer,ipernity,spelling]) (2.3.1)
        Requirement already satisfied: oauthlib>=3.0.0 in /usr/lib/python3/dist-packages (from requests-oauthlib>=1.0->photini[Pillow,flickr,google,gpxpy,importer,ipernity,spelling]) (3.1.0)
        Building wheels for collected packages: gpxpy
          Building wheel for gpxpy (setup.py) ... done
          Created wheel for gpxpy: filename=gpxpy-1.5.0-py3-none-any.whl size=42878 sha256=fe9e48d88437fb635227a114ddd4c021e99979514e83cbba7cb3cd620bc7f8f8
          Stored in directory: /home/jim/.cache/pip/wheels/93/15/ce/1cd2782b440b8a517b89c3fa112f79f7015bd6e51b552e1b1a
        Successfully built gpxpy
        Installing collected packages: gphoto2, requests-toolbelt, requests-oauthlib, pyenchant, gpxpy
        Successfully installed gphoto2-2.3.4 gpxpy-1.5.0 pyenchant-3.2.2 requests-oauthlib-1.3.1 requests-toolbelt-0.9.1
    .. code-tab:: none Windows

        C:\Users\Jim>photini-configure
        Which Qt package would you like to use?
          0 PySide2 [installed]
          1 PySide6 [not installed]
        Choose 0/1: 0
        Would you like to upload pictures to Flickr? (y/n): y
        Would you like to upload pictures to Google Photos? (y/n): y
        Would you like to upload pictures to Ipernity? (y/n): y
        Would you like to check spelling of metadata? (y/n): y
        Would you like to import GPS track data? (y/n): y
        Would you like to make higher quality thumbnails? (y/n): y
        c:\users\jim\appdata\local\programs\python\python38\python.exe -m pip install photini[flickr,google,ipernity,spelling,gpxpy,Pillow]
        Requirement already satisfied: photini[Pillow,flickr,google,gpxpy,ipernity,spelling] in c:\users\jim\appdata\local\programs\python\python38\lib\site-packages (2022.9.0)
        Requirement already satisfied: appdirs>=1.3 in c:\users\jim\appdata\local\programs\python\python38\lib\site-packages (from photini[Pillow,flickr,google,gpxpy,ipernity,spelling]) (1.4.4)
        Requirement already satisfied: exiv2>=0.11.0 in c:\users\jim\appdata\local\programs\python\python38\lib\site-packages (from photini[Pillow,flickr,google,gpxpy,ipernity,spelling]) (0.11.3)
        Requirement already satisfied: cachetools>=3.0 in c:\users\jim\appdata\local\programs\python\python38\lib\site-packages (from photini[Pillow,flickr,google,gpxpy,ipernity,spelling]) (5.2.0)
        Requirement already satisfied: requests>=2.4.0 in c:\users\jim\appdata\local\programs\python\python38\lib\site-packages (from photini[Pillow,flickr,google,gpxpy,ipernity,spelling]) (2.28.1)
        Collecting requests-oauthlib>=1.0
          Downloading requests_oauthlib-1.3.1-py2.py3-none-any.whl (23 kB)
        Collecting requests-toolbelt>=0.9
          Downloading requests_toolbelt-0.9.1-py2.py3-none-any.whl (54 kB)
             -------------------------------------- 54.3/54.3 kB 352.6 kB/s eta 0:00:00
        Collecting keyring>=7.0
          Downloading keyring-23.9.3-py3-none-any.whl (35 kB)
        Collecting gpxpy>=1.3.5
          Downloading gpxpy-1.5.0.tar.gz (111 kB)
             ------------------------------------ 111.6/111.6 kB 542.0 kB/s eta 0:00:00
          Preparing metadata (setup.py) ... done
        Collecting pyenchant>=2.0
          Downloading pyenchant-3.2.2-py3-none-win_amd64.whl (11.9 MB)
             -------------------------------------- 11.9/11.9 MB 893.7 kB/s eta 0:00:00
        Collecting Pillow>=2.0.0
          Downloading Pillow-9.2.0-cp38-cp38-win_amd64.whl (3.3 MB)
             ---------------------------------------- 3.3/3.3 MB 889.4 kB/s eta 0:00:00
        Collecting pywin32-ctypes!=0.1.0,!=0.1.1
          Downloading pywin32_ctypes-0.2.0-py2.py3-none-any.whl (28 kB)
        Collecting jaraco.classes
          Downloading jaraco.classes-3.2.3-py3-none-any.whl (6.0 kB)
        Collecting importlib-metadata>=3.6
          Downloading importlib_metadata-4.12.0-py3-none-any.whl (21 kB)
        Requirement already satisfied: charset-normalizer<3,>=2 in c:\users\jim\appdata\local\programs\python\python38\lib\site-packages (from requests>=2.4.0->photini[Pillow,flickr,google,gpxpy,ipernity,spelling]) (2.1.1)
        Requirement already satisfied: certifi>=2017.4.17 in c:\users\jim\appdata\local\programs\python\python38\lib\site-packages (from requests>=2.4.0->photini[Pillow,flickr,google,gpxpy,ipernity,spelling]) (2022.9.24)
        Requirement already satisfied: idna<4,>=2.5 in c:\users\jim\appdata\local\programs\python\python38\lib\site-packages (from requests>=2.4.0->photini[Pillow,flickr,google,gpxpy,ipernity,spelling]) (3.4)
        Requirement already satisfied: urllib3<1.27,>=1.21.1 in c:\users\jim\appdata\local\programs\python\python38\lib\site-packages (from requests>=2.4.0->photini[Pillow,flickr,google,gpxpy,ipernity,spelling]) (1.26.12)
        Collecting oauthlib>=3.0.0
          Downloading oauthlib-3.2.1-py3-none-any.whl (151 kB)
             ------------------------------------ 151.7/151.7 kB 604.4 kB/s eta 0:00:00
        Collecting zipp>=0.5
          Downloading zipp-3.8.1-py3-none-any.whl (5.6 kB)
        Collecting more-itertools
          Downloading more_itertools-8.14.0-py3-none-any.whl (52 kB)
             -------------------------------------- 52.2/52.2 kB 116.5 kB/s eta 0:00:00
        Using legacy 'setup.py install' for gpxpy, since package 'wheel' is not installed.
        Installing collected packages: pywin32-ctypes, zipp, pyenchant, Pillow, oauthlib, more-itertools, gpxpy, requests-toolbelt, requests-oauthlib, jaraco.classes, importlib-metadata, keyring
          Running setup.py install for gpxpy ... done
        Successfully installed Pillow-9.2.0 gpxpy-1.5.0 importlib-metadata-4.12.0 jaraco.classes-3.2.3 keyring-23.9.3 more-itertools-8.14.0 oauthlib-3.2.1 pyenchant-3.2.2 pywin32-ctypes-0.2.0 requests-oauthlib-1.3.1 requests-toolbelt-0.9.1 zipp-3.8.1

Photini's spelling checker may require some other files to be installed.
See the `pyenchant documentation`_ for platform specific instructions.

One optional dependency that cannot be installed with pip_ or ``photini-configure`` is FFmpeg_.
This is used to read metadata from video files.
Linux & MacOS users can install it with the system package manager, but installing it on Windows is non-trivial.

Start menu / application menu
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Although you can run Photini from a command shell, most users would probably prefer to use the start/application menu or a desktop icon.
These can be installed with the ``photini-post-install`` command:

.. tabs::
    .. code-tab:: none Linux/MacOS

        jim@mint:~$ photini-post-install
        desktop-file-install \
          --dir=/home/jim/.local/share/applications \
          --set-key=Exec \
          --set-value=/home/jim/photini/bin/photini %F \
          --set-key=Icon \
          --set-value=/home/jim/photini/lib/python3.8/site-packages/photini/data/icons/photini_48.png \
          /home/jim/photini/lib/python3.8/site-packages/photini/data/linux/photini.desktop
    .. code-tab:: none Windows

        C:\Users\Jim>photini-post-install
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

This is not a very convenient way to run Photini, so most users will want to add it to their start/application menu:

.. tabs::
    .. code-tab:: none Linux/MacOS

        sarah@mint:~$ /home/jim/photini/bin/photini-post-install
        desktop-file-install \
          --dir=/home/sarah/.local/share/applications \
          --set-key=Exec \
          --set-value=/home/jim/photini/bin/photini %F \
          --set-key=Icon \
          --set-value=/home/jim/photini/lib/python3.8/site-packages/photini/data/icons/photini_48.png \
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
          /home/jim/photini/lib/python3.8/site-packages/photini/data/linux/photini.desktop
    .. code-tab:: none Windows

        C:\Windows\system32>c:\Users\Jim\photini\Scripts\photini-post-install.exe
        Creating C:\ProgramData\Microsoft\Windows\Start Menu\Photini
        Creating C:\Users\Public\Desktop\Photini.lnk
        Creating C:\ProgramData\Microsoft\Windows\Start Menu\Photini\Photini.lnk
        Creating C:\ProgramData\Microsoft\Windows\Start Menu\Photini\Photini documentation.url

Uninstalling Photini
^^^^^^^^^^^^^^^^^^^^

Before removing Photini you should use the ``photini-post-install`` command to remove it from the start/application menu:

.. tabs::
    .. code-tab:: none Linux/MacOS

        jim@mint:~$ photini-post-install --remove
        Deleting /home/jim/.local/share/applications/photini.desktop
    .. code-tab:: none Windows

        C:\Users\Jim>photini-post-install --remove
        Deleting C:\Users\Jim\Desktop\Photini.lnk
        Deleting C:\Users\Jim\AppData\Roaming\Microsoft\Windows\Start Menu\Photini\Photini.lnk
        Deleting C:\Users\Jim\AppData\Roaming\Microsoft\Windows\Start Menu\Photini\Photini documentation.url
        Deleting C:\Users\Jim\AppData\Roaming\Microsoft\Windows\Start Menu\Photini

If you used a virtual environment you can simply delete the top level directory created when setting up the virtual environment.
Otherwise you can use pip to uninstall Photini and as many of its dependencies as you want to remove:

.. tabs::
    .. code-tab:: none Linux/MacOS

        jim@mint:~$ pip3 uninstall photini pyside2
        Found existing installation: Photini 2022.2.0
        Uninstalling Photini-2022.2.0:
          Would remove:
            /home/jim/photini/bin/photini
            /home/jim/photini/bin/photini-post-install
            /home/jim/photini/lib/python3.8/site-packages/Photini-2022.2.0.dist-info/*
            /home/jim/photini/lib/python3.8/site-packages/photini/*
        Proceed (Y/n)? y
          Successfully uninstalled Photini-2022.2.0
        Found existing installation: PySide2 5.15.2.1
        Uninstalling PySide2-5.15.2.1:
          Would remove:
            /home/jim/photini/bin/pyside2-designer
            /home/jim/photini/bin/pyside2-lupdate
            /home/jim/photini/bin/pyside2-rcc
            /home/jim/photini/bin/pyside2-uic
            /home/jim/photini/lib/python3.8/site-packages/PySide2-5.15.2.1.dist-info/*
            /home/jim/photini/lib/python3.8/site-packages/PySide2/*
        Proceed (Y/n)? y
          Successfully uninstalled PySide2-5.15.2.1
    .. code-tab:: none Windows

        C:\Users\Jim>pip uninstall photini pyside2
        Found existing installation: Photini 2022.2.0
        Uninstalling Photini-2022.2.0:
          Would remove:
            c:\users\jim\photini\lib\site-packages\photini-2022.2.0.dist-info\*
            c:\users\jim\photini\lib\site-packages\photini\*
            c:\users\jim\photini\scripts\photini-post-install.exe
            c:\users\jim\photini\scripts\photini.exe
        Proceed (y/n)? y
          Successfully uninstalled Photini-2022.2.0
        Found existing installation: PySide2 5.15.2.1
        Uninstalling PySide2-5.15.2.1:
          Would remove:
            c:\users\jim\photini\lib\site-packages\pyside2-5.15.2.1.dist-info\*
            c:\users\jim\photini\lib\site-packages\pyside2\*
            c:\users\jim\photini\scripts\pyside2-designer.exe
            c:\users\jim\photini\scripts\pyside2-lupdate.exe
            c:\users\jim\photini\scripts\pyside2-rcc.exe
            c:\users\jim\photini\scripts\pyside2-uic.exe
        Proceed (y/n)? y
          Successfully uninstalled PySide2-5.15.2.1

Updating Photini
----------------

When a new release of Photini is issued you can easily update your installation with pip_:

.. tabs::
    .. code-tab:: none Linux/MacOS

        jim@mint:~$ pip3 install -U photini
    .. code-tab:: none Windows

        C:\Users\Jim>pip install -U photini

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
PyQt_ [1]                      5.9                ``python3-qt5``
                                                  or ``python3-pyqt5``
                                                  or ``python310-PyQt6``
PySide2_ [1]                   5.11.0             ``python3-pyside2``               PySide2
PySide6_ [1]                   6.2.0              ``python3-pyside6``               PySide6
QtWebEngine_ [2]                                  ``python3-pyside2.qtwebengine``   PyQtWebEngine
                                                  or ``python310-PyQt6-WebEngine``
`python-exiv2`_                0.13.2                                               exiv2
appdirs                        1.3                ``python3-appdirs``               appdirs
requests_                      2.4                ``python3-requests``              requests
=============================  =================  ================================  =================

[1] PyQt_, PySide2_, and PySide6_ are Python interfaces to the Qt GUI framework.
Photini can use any of them (although PySide2 is preferred), so you can install whichever one you prefer that is available for your operating system.
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

    $ pip3 install .

If you'd like to test or use one of Photini's translation files you will need to update and compile the translations before installing or running Photini::

    $ python3 utils/lang_update.py
    $ python3 utils/build_lang.py
    $ pip3 install .

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

        C:\Users\Jim>python -m photini -v

Note the use of the ``-v`` option to increase the verbosity of Photini's message logging.
This option can be repeated for even more verbosity.

To find out what version of Photini and some of its dependencies you are using, run it with the ``--version`` option:

.. tabs::
    .. code-tab:: none Linux/MacOS

        jim@mint:~$ python -m photini --version
        Photini 2022.3.2, build 2084 (3194bd4)
          Python 3.8.10 (default, Nov 26 2021, 20:14:08) [GCC 9.3.0]
          python-exiv2 0.11.0, exiv2 0.27.5
          PySide2 5.15.2.1, Qt 5.15.2, using QtWebEngine
          PyEnchant 3.2.2
          ffmpeg version 4.2.4-1ubuntu0.1 Copyright (c) 2000-2020 the FFmpeg developers
          available styles: Windows, Fusion
          using style: fusion
    .. code-tab:: none Windows

        C:\Users\Jim>python -m photini --version
        ffmpeg or ffprobe not found
        Photini 2022.2.0, build 1995 (11743ef)
          Python 3.8.10 (tags/v3.8.10:3d8993a, May  3 2021, 11:48:03) [MSC v.1928 64 bit (AMD64)]
          python-exiv2 0.9.0, exiv2 0.27.5
          PySide2 5.15.2.1, Qt 5.15.2, using QtWebEngine
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
