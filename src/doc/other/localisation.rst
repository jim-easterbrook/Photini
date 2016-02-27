.. This is part of the Photini documentation.
   Copyright (C)  2015-16  Jim Easterbrook.
   See the file DOC_LICENSE.txt for copying conditions.

"Localisation"
==============

Photini can be made easier to use for people who don't speak English.
There are two parts to this -- the text used within the program and the documentation.
I rely on users to do the translation as I can not write any other language with any fluency.

If your computer is configured to use a language other than English, and Photini has already been translated into that language, then Photini should use the translation automatically.
For example, this is what it looks like if your computer is configured to use Spanish.

.. image:: ../images/screenshot_37.png

If you'd like to help by translating Photini into another language, or by improving an existing translation, this is what you need to do.

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

Transifex is quite easy to use, but there are a few things to be aware of when working on the Photini project.
On the Transifex site there are several "resources" for Photini.
The one called ``photini`` contains the text strings used by the Photini program.
The others, beginning with ``doc``, contain the Photini documentation.

``photini`` resource
^^^^^^^^^^^^^^^^^^^^

Things to be aware of:

Words with special meanings
  Some of Photini's GUI elements such as ``Title / Object Name`` are named after the metadata items in the Exif, XMP or IPTC specifications.
  If information about these standards is available in your language it may help with translating these words.

Formatting strings
   In Python curly braces are used to include other data in a string.
   For example, ``Copyright ©{0:d} {1}. All rights reserved.`` includes the year and copyright holder's name when the program is run.
   You should take care not to change what's inside the braces, but you can reorder them if it's appropriate for your language.

HTML markup
   Strings such as ``<h3>Upload to Flickr has not finished.</h3>`` include HTML markup which must be copied to your translated string.
   The Transifex web page includes a "copy source string" button that can help with this.

Keyboard shortcuts
   Some strings include a single ampersand character ``&`` immediately before a letter that is used as a keyboard shortcut.
   You should choose a suitable letter in your translation and place the ampersand appropriately.

``doc.xxx`` resources
^^^^^^^^^^^^^^^^^^^^^

The Photini documentation is written in `reStructuredText <http://docutils.sourceforge.net/rst.html>`_.
This is a markup language that looks very like plain text, but uses certain characters to give extra meaning to some parts.
You need to take extra care when the string to be translated includes such markup.

Double backquotes ``````
   These usually mark words that are used in the Photini GUI.
   You may wish to include the English equivalent in brackets after your translation to help users read the documentation as the screen grabs are all from the English version.

Special characters, e.g. ``(|hazard|)``
   These refer to Unicode symbols and should not be translated.

Short cross references, e.g. ``:doc:`tags```
   These should not be translated.

Long cross references, e.g. ``:ref:`installation <installation-flickr>```
   The text within the ``<>`` characters should not be translated, but it may be appropriate to translate the preceding link caption.

External links, e.g. ```Flickr <http://www.flickr.com/>`_``
   The url within the ``<>`` characters should not be translated, but it may be appropriate to translate the preceding link text.

Testing your translations
-------------------------

To test your translated strings you will need to have a local copy of the Photini source files to build and install.
See :ref:`installation <installation-photini>` for more detail.
You will also need to install the Transifex client program::

   sudo pip install transifex-client

The Transifex client is used to download your translated strings.
For example, if you've been working on a Dutch translation with the language code ``nl``::

   tx pull -l nl

This will download several files.
``src/lang/photini.nl.ts`` is the Dutch translation of the Photini program strings.
``src/lang/doc/nl/LC_MESSAGES/xxx.po`` are the Dutch translations of the Photini documentation.
(Replace ``nl`` with the language code you are translating for.)


Testing the ``photini`` resource
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The ``src/lang/photini.nl.ts`` file needs to be "compiled" (converted from ``.ts`` format to ``.qm`` format) before it can be used by the Photini program.
This requires the ``lrelease`` program, which is part of the ``libqt4-linguist`` package on some Linux systems.
The ``lrelease`` command can be used directly to compile a single language file::

   lrelease src/lang/photini.nl.ts -qm src/photini/data/lang/photini.nl.qm

Or you can easily compile all the language files with setup.py::

   python setup.py build_messages

Now you can install Photini with your new translation(s)::

   python setup.py build
   sudo python setup.py install

Photini should use your new language if your computer's ``LANG`` environment variable is set appropriately.
You can force this when running Photini from the command line::

   LANG=nl photini

Photini should now be using your translations.
If all is well, please email jim@jim-easterbrook.me.uk with the good news that another language can be added to the next Photini release.

Testing the ``doc.xxx`` resources
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

If you install `Sphinx <http://sphinx-doc.org/index.html>`_ (See :ref:`installation <installation-documentation>`) you can build a local copy of the documentation using your translation.
For example, to build Dutch documentation::

   LANG=nl python setup.py build_sphinx

Open ``doc/html/index.html`` with a web browser to read the translated documentation.
