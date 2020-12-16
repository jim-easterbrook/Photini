.. This is part of the Photini documentation.
   Copyright (C)  2015-20  Jim Easterbrook.
   See the file DOC_LICENSE.txt for copying conditions.

"Localisation"
==============

Photini can be made easier to use for people who don't speak English.
There are two parts to this -- the text used within the program and the documentation.
I rely on users to do the translation as I can not write any other language with any fluency.
You can use an online service called Transifex_ or a suitable text editor installed on your computer.

Online translation
------------------

Transifex_ is an online translation service that provides free support for open source projects such as Photini.
It provides an online editor, making it easy for individuals to contribute as much or as little effort as they wish.
Follow the link to Transifex_ and click on "help translate Photini".
From there you can create a free account and sign in.

If your language is not included in the Photini project languages list you can ask for it to be added by clicking on "request language".
Each language is represented by a code, e.g. ``nl`` or ``en_CA``.
The longer codes are usually regional or national variations of a common language.
You should choose the common language if it's not already available in Photini, moving on to the variations once the common language is done.
Once your language is added you can ask to join the language team and then start translating.

The main advantages of online translation are that you don't need to install any software on your computer (apart from a web browser) and that several people can work on the same language.
One disadvantage is that Transifex_ doesn't display the context in which a piece of text is used, which may make it more difficult to translate.

Offline translation
-------------------

Translating Photini on your own computer will probably require extra software to be installed, but may be easier as you can see the program source where translations are used.

Start by installing the development version of Photini by cloning the GitHub repository (see :ref:`installation-photini`).
You will also need to install the Transifex client program, Babel_ and ``pylupdate5``.
If possible, install these with your operating system software manager.
``pylupdate5`` should be in a package such as ``python3-qt5-devel`` or ``pyqt-tools`` or similar, depending on your Linux distribution.
Otherwise, you can use pip::

   sudo pip install transifex-client Babel

Start by getting the most recent translation into your chosen language from Transifex_, if there is one.
For example, if you are going to translate Photini into Dutch::

   tx pull -l nl -f

(The ``-f`` option forces a download, even if your local file is newer than the translation on Transifex.)

Now update (or initialise if they don't exist) the translation files with the current program strings::

   python utils/lang_update.py -l nl

Now you can open a translation file in your chosen editor, for example::

   linguist-qt5 src/lang/nl/photini.ts
   linguist-qt5 src/lang/nl/LC_MESSAGES/manual.po

You can use any text editor for your translations, but a special purpose translation editor is preferable.
The `Qt Linguist`_ program is ideal, but any editor that understands the ``.ts`` file format used for the program strings or the ``.po`` file format used for the documentation should be acceptable.

Translating the program text
----------------------------

If your computer is configured to use a language other than English, and Photini has already been translated into that language, then Photini should use the translation automatically.
For example, this is what it might look like if your computer is configured to use Spanish.

.. image:: ../images/screenshot_37.png

If you'd like to help by translating Photini into another language, or by improving an existing translation, this is what you need to do.

Online translation
^^^^^^^^^^^^^^^^^^

On the Transifex site there are several "resources" for Photini.
The one called ``photini`` contains the text strings used by the Photini program.
(The others, beginning with ``doc``, contain the Photini documentation.)
Click on the ``photini`` resource, then the language you want to work on, then click on the ``translate`` button.
This displays a translation editing page where you can click on a text string to be translated and then type in your translation.
See the :ref:`notes <localisation-program-notes>` below for things to be aware of when translating the program strings.

Offline translation
^^^^^^^^^^^^^^^^^^^

The program strings are stored in files with names like ``src/lang/nl/photini.ts``, where ``nl`` is the code for the Dutch language.
You can open the translation file in any editor, but a translation tool is best.
For example::

   linguist-qt5 src/lang/nl/photini.ts

See the :ref:`notes <localisation-program-notes>` below for things to be aware of when translating the program strings.

If you have a Transifex account then you should upload your translation as it progresses.
This will ensure that your work isn't accidentally duplicated by other translators::

   tx push -t -l nl

.. _localisation-program-notes:

Things to be aware of
^^^^^^^^^^^^^^^^^^^^^

Words with special meanings
  Some of Photini's GUI elements such as ``Title / Object Name`` are named after the metadata items in the Exif, XMP or IPTC specifications.
  If information about these standards is available in your language it may help with translating these words.

Formatting strings
   In Python curly braces are used to include other data in a string.
   For example, ``Copyright ©{year} {name}. All rights reserved.`` includes the year and copyright holder's name when the program is run.
   You should take care not to change what's inside the braces, but you can reorder them if it's appropriate for your language.

Carriage returns
   Some of Photini's buttons split their labels over two or more lines to stop the button being too wide.
   You should split your translation in similar size pieces so it has the same number of lines.

HTML markup
   Strings such as ``<h3>Upload to Flickr has not finished.</h3>`` include HTML markup which must be copied to your translated string.
   The Transifex web page includes a "copy source string" button that can help with this.
   Some strings such as ``<multiple values>`` are not HTML.
   The angle brackets ``<>`` are used to indicate data with a special meaning.
   These strings should usually be translated.

Keyboard shortcuts
   Some strings include a single ampersand character ``&`` immediately before a letter that is used as a keyboard shortcut.
   You should choose a suitable letter in your translation and place the ampersand appropriately.

Plural forms
   Translations can accommodate the many ways that languages handle plurals.
   For example in English we write "0 files, 1 file, 2 files".
   Transifex_ has small buttons to select the quantity the translation applies to.
   Other translation editors should also handle plural forms.

Note that Transifex may attempt to render some of this markup rather than show the raw strings.
It may help if you use the settings button (a cogwheel shape) on the translation page to "enable raw editor mode".

When you've finished your translation, or done a significant chunk of it, please email me (jim@jim-easterbrook.me.uk) to let me know.
(If you're not using Transifex then send me your translation file directly.)
If you install the development version of Photini (see :ref:`installation-photini`) you could also :ref:`test your translation <localisation-program-testing>` first.

.. _localisation-program-testing:

Testing your translation
^^^^^^^^^^^^^^^^^^^^^^^^

If you've been working online then the Transifex client is used to download your translated strings.
For example, if you've been working on a Dutch translation with the language code ``nl``::

   tx pull -l nl -f

The translation file (e.g. ``src/lang/nl/photini.ts``) needs to be "compiled" (converted from ``.ts`` format to ``.qm`` format) before it can be used by the Photini program.
This requires the ``lrelease-qt5`` program, which is part of the ``libqt5-linguist`` package on some Linux systems.

You can easily update and compile all the language files::

   python utils/lang_update.py
   python utils/build_lang.py

Now you can install Photini with your new translation(s)::

   sudo python -m pip install .

Photini should use your new language if your computer's ``LANG`` environment variable is set appropriately.
You can force this when running Photini from the command line::

   LANG=nl photini

Photini should now be using your translations.

Translating the documentation
-----------------------------

Translating Photini's documentation is a lot more work than translating the program itself.
The `"Read the Docs" <https://readthedocs.org/>`_ web site can host multiple languages, and I would welcome the chance to add documentation of Photini in other languages.

Online translation
^^^^^^^^^^^^^^^^^^

On the Transifex site Photini's documentation is in the resources that have names beginning with ``doc``.
See the :ref:`notes <localisation-documentation-notes>` below for things to be aware of when translating the documentation.

Offline translation
^^^^^^^^^^^^^^^^^^^

The documentation translation uses ``.po`` files as specified by the `GNU gettext <https://www.gnu.org/software/gettext/>`_ project.
You can open the translation file in any editor, but a translation tool is best.
For example::

   linguist-qt5 src/lang/nl/LC_MESSAGES/manual.po

See the :ref:`notes <localisation-documentation-notes>` below for things to be aware of when translating the documentation.

If you have a Transifex account then you should upload your translation as it progresses.
This will ensure that your work isn't accidentally duplicated by other translators::

   tx push -t -l nl

.. _localisation-documentation-notes:

Things to be aware of
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

Long cross references, e.g. ``:ref:`installation <installation-optional>```
   The text within the ``<>`` characters should not be translated, but it may be appropriate to translate the preceding link text.

External links, e.g. ```Flickr <http://www.flickr.com/>`_``
   The url within the ``<>`` characters should not be translated, but it may be appropriate to translate the preceding link text.

When you've finished your translation, or done a significant chunk of it, please email me (jim@jim-easterbrook.me.uk) to let me know.
(If you're not using Transifex then send me your translation file directly.)

.. _localisation-documentation-testing:

Testing your translation
^^^^^^^^^^^^^^^^^^^^^^^^

The Transifex client is used to download your translated strings.
For example, if you've been working online on a Dutch translation with the language code ``nl``::

   tx pull -l nl -f

If you install Sphinx_ (See :ref:`installation <installation-documentation>`) you can build a local copy of the documentation using your translation.
For example, to build Dutch documentation::

   LANG=nl python utils/build_docs.py

Open ``doc/html/index.html`` with a web browser to read the translated documentation.

.. _Babel:       http://babel.pocoo.org/
.. _Qt Linguist: https://doc.qt.io/qt-5/linguist-translators.html
.. _Sphinx:      https://www.sphinx-doc.org/
.. _Transifex:   https://www.transifex.com/projects/p/photini/
