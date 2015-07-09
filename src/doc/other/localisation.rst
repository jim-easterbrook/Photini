.. This is part of the Photini documentation.
   Copyright (C)  2015  Jim Easterbrook.
   See the file DOC_LICENSE.txt for copying conditions.

"Localisation"
==============

Photini's user interface can be configured to use your local language instead of English.
I rely on users to do the translation as I can not write any other language with any fluency.
If there is already a translation into your language then Photini should use it automatically.
If not, this is what you need to do.

Join Transifex
--------------

The Photini project uses `Transifex <https://www.transifex.com/projects/p/photini/>`_ to host its translations.
This provides an online editor, making it easy for individuals to contribute as much or as little effort as they wish.
Follow the link to the Transifex Photini page and click on "help translate Photini".
From here you can create a free account and sign in.

If your language is not included in the Photini project languages list you can request it to be added by clicking on "request language".
Each language is represented by a code, e.g. ``nl`` or ``en_CA``.
The longer codes are usually regional or national variations of a common language.
You should choose the common language if it's not already available in Photini, moving on to the variations once the common language is done.
Once your language is added you can ask to join the language team and then start translating.

Translating Photini
-------------------

Transifex is quite easy to use.
However, there are a few things to be aware of when working on the Photini program's strings.

Words with special meanings
^^^^^^^^^^^^^^^^^^^^^^^^^^^

Some of Photini's GUI elements such as "Title / Object Name" are named after the metadata items in the Exif, Xmp or Iptc specifications.
If information about these standards is available in your language it may help with translating these words.

Formatting strings
^^^^^^^^^^^^^^^^^^

In Python curly braces are used to include other data in a string.
For example, "Copyright ©{0:d} {1}. All rights reserved." includes the year and copyright holder's name when the program is run.
You should take care not to change what's inside the braces, but you can reorder them if it's appropriate for your language.

HTML markup
^^^^^^^^^^^

Strings such as "<h3>Upload to Flickr has not finished.</h3>" include HTML markup which must be copied to your translated string.
The Transifex web page includes a "copy source string" button that can help with this.

Keyboard shortcuts
^^^^^^^^^^^^^^^^^^

Some strings include a single ampersand character '&' immediately before a letter that is used as a keyboard shortcut.
You should choose a suitable letter in your translation and place the ampersand appropriately.

Testing your translation
------------------------

To test your translated strings you will need to have a local copy of the Photini source files to build and install.
See :ref:`installation<installation-photini>` for more detail.
You will also need to install the Transifex client program::

   sudo pip install transifex-client

The client is used to download your translated strings.
For example, if you've been working on a Dutch translation with the language code ``nl``::

   tx pull -l nl

This will download a ``.ts`` file which needs to be "compiled" before it can be used by the Photini program.
This requires the ``lrelease`` program, which is part of the ``libqt4-linguist`` package on some Linux systems.
Compilation and installation is done with setup.py::

   python setup.py build_messages
   python setup.py build
   sudo python setup.py install

Photini should use your new language if your computer's ``LANG`` environment variable is set appropriately.
You can force this when running Photini from the command line::

   LANG=nl photini

Photini should now be using your translations.
If all is well, please email jim@jim-easterbrook.me.uk with the good news that another language can be added to the next Photini release.