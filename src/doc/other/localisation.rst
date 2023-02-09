.. This is part of the Photini documentation.
   Copyright (C)  2015-23  Jim Easterbrook.
   See the file DOC_LICENSE.txt for copying conditions.

"Localisation"
==============

Photini can be made easier to use for people who don't speak English.
There are two parts to this -- the text used within the program and the documentation.
I rely on users to do the translation as I can not write any other language with any fluency.
You can use an online service (Weblate_ or Transifex_) or a suitable text editor installed on your computer.

Translating the program text
----------------------------

If your computer is configured to use a language other than English, and Photini has already been translated into that language, then Photini should use the translation automatically.
For example, this is what it might look like if your computer is configured to use Spanish.

.. image:: ../images/screenshot_37.png

If you'd like to help by translating Photini into another language, or by improving an existing translation, this is what you need to do.

.. figure:: https://hosted.weblate.org/widgets/photini/-/gui/multi-auto.svg
    :alt: Translation status
    :target: https://hosted.weblate.org/engage/photini/
    :width: 70 %
    :align: center

    Translation progress so far

Online translation
^^^^^^^^^^^^^^^^^^

The main advantages of online translation are that you don't need to install any software on your computer (apart from a web browser) and that several people can work on the same language.
Each person can contribute as much or as little effort as they wish.

Please read the :ref:`notes <localisation-program-notes>` below for things to be aware of when translating the program strings.

Weblate
"""""""

Weblate_ is an online translation service that provides free support for open source projects such as Photini.
Its main advantage over Transifex is that most strings have a screenshot associated with them to show the context where the string is used.
Follow the link to Weblate_ and click on "Register".
From there you can create a free account and sign in.
I recommend using one of the authentication services (e.g. GitHub or Google) so you don't have to invent yet another user name and password.

Back at the Photini project page, click on the "GUI" component, then click on a language to work on, or "Start new translation" if your language is not listed.
Clicking on "Browse" shows a list of strings and their translations.
You can then click on a string to edit its translation.

When you've finished working on a translation there's no need to do anything further.
Weblate automatically pushes the translation to GitHub, where I can merge it into the main repository branch.
You might like to :ref:`test your translation <localisation-program-testing>` though.

Transifex
"""""""""

Transifex_ is another online translation service with free support for open source projects.
Follow the link to Transifex_ and click on "Help Translate "Photini"".
From there you can create a free account and sign in.
I recommend using one of the authentication services (e.g. GitHub or Google) so you don't have to invent yet another user name and password.

Back at the Transifex Photini page click on "Languages" to show all the languages currently being translated to.
If your language is not included in the list you can ask for it to be added by clicking on "request language".
Each language is represented by a code, e.g. nl or en_CA.
The longer codes are usually regional or national variations of a common language.
You should choose the common language if it’s not already available in Photini, moving on to the variations once the common language is done.
Once your language is added you can ask to join the language team and then start translating.

Click on your language, then click on "src..en/photini.ts (master)" to work on the Photini GUI strings.

When you've finished working on a translation there's no need to do anything further.
Transifex automatically pushes the translation to GitHub, where I can merge it into the main repository branch.
You might like to :ref:`test your translation <localisation-program-testing>` though.

Offline translation
^^^^^^^^^^^^^^^^^^^

Translating Photini on your own computer will probably require extra software to be installed, but may be easier as you can see the program source where translations are used.

Start by downloading the development version of Photini by cloning the GitHub repository (see :ref:`installation-photini`).
You will also need to install ``pyside6-lupdate``.
This is part of the ``PySide6`` package installable with ``pip``.

The program strings are stored in files with names like ``src/lang/nl/photini.ts``, where ``nl`` is the code for the Dutch language.
First you should update (or initialise if they don't exist) the translation files with the current program strings::

   $ python3 utils/lang_update.py -l nl

Now you can open a translation file in your chosen editor, for example::

   $ pyside6-linguist src/lang/nl/photini.ts

You can use any text editor for your translations, but a special purpose translation editor is preferable.
The `Qt Linguist`_ program is ideal, but any editor that understands the ``.ts`` file format used for the program strings should be acceptable.

Please read the :ref:`notes <localisation-program-notes>` below for things to be aware of when translating the program strings.
When you've finished your translation, or done a significant chunk of it, please email it to me (jim@jim-easterbrook.me.uk).
You might like to :ref:`test your translation <localisation-program-testing>` first.

.. _localisation-program-notes:

Things to be aware of
^^^^^^^^^^^^^^^^^^^^^

String length
  Many of the strings to be translated have to fit into buttons on the GUI, so your translation should not be much longer than the English original.
  If the English text is using abbreviations then the translation probably needs to as well.

Words with special meanings
  Some of Photini's GUI elements such as ``Title / Object Name`` are named after the metadata items in the Exif, XMP or IPTC specifications.
  If information about these standards is available in your language it may help with translating these words.

Formatting strings
   In Python curly braces are used to include other data in a string.
   For example, ``File "{file_name}" has {size} bytes and exceeds {service}'s limit of {max_size} bytes.`` includes the file name & size and a size limit set by a service such as Flickr.
   You should take care not to change what's inside the braces, but you can reorder them if it's appropriate for your language.

Carriage returns
   Some of Photini's buttons split their labels over two or more lines to stop the button being too wide.
   You should split your translation in similar size pieces so it has the same number of lines.

HTML markup
   Strings such as ``<h3>Upload to Flickr has not finished.</h3>`` include HTML markup which must be copied to your translated string.
   Some strings such as ``<multiple values>`` are not HTML.
   The angle brackets ``<>`` are used to indicate data with a special meaning.
   These strings should usually be translated.

Keyboard shortcuts
   Some strings include a single ampersand character ``&`` immediately before a letter that is used as a keyboard shortcut.
   You should choose a suitable letter in your translation and place the ampersand appropriately.

Plural forms
   Translations can accommodate the many ways that languages handle plurals.
   For example in English we write "0 files, 1 file, 2 files".
   Weblate_ has a separate translation for each plural form.
   Other translation editors should also handle plural forms.

.. _localisation-program-testing:

Testing your translation
^^^^^^^^^^^^^^^^^^^^^^^^

You need a copy of the Photini source files to test your translation with.
You can download or clone this from GitHub (see :ref:`installation-photini`).

If you've been working online then you can download your translation with Weblate's "Files" menu.
It will have the wrong default name so, for example, make sure you save ``photini-gui-fr.ts`` as ``src/lang/fr/photini.ts``.

The translation file needs to be "compiled" (converted from ``.ts`` format to ``.qm`` format) before it can be used by the Photini program.
This requires the ``pyside6-lrelease`` program, which is part of the ``PySide6`` package on PyPI.

You can easily update and compile all the language files::

   $ python3 utils/lang_update.py
   $ python3 utils/build_lang.py

Now you can install Photini with your new translation(s)::

   $ pip3 install --user .

Photini should use your new language if your computer's ``LANG`` environment variable is set appropriately.
You can force this when running Photini from the command line::

   $ LANG=nl python3 -m photini

Photini should now be using your translations.

Translating the documentation
-----------------------------

Translating Photini's documentation is a lot more work than translating the program itself.
The `"Read the Docs" <https://readthedocs.org/>`_ web site can host multiple languages, and I would welcome the chance to add documentation of Photini in other languages.
However, translating the program strings is a much higher priority.

Online translation
^^^^^^^^^^^^^^^^^^

This uses Transifex_ as described above.
The documentation strings are in resources with names like "src..gettext/manual.pot (master)".

See the :ref:`notes <localisation-documentation-notes>` below for things to be aware of when translating the documentation.

Offline translation
^^^^^^^^^^^^^^^^^^^

The documentation translation uses ``.po`` files as specified by the `GNU gettext <https://www.gnu.org/software/gettext/>`_ project.
You can open the translation file in any editor, but a translation tool is best.
For example::

   $ python3 utils/lang_update.py -l nl -d
   $ pyside6-linguist src/lang/nl/LC_MESSAGES/manual.po

See the :ref:`notes <localisation-documentation-notes>` below for things to be aware of when translating the documentation.

.. _localisation-documentation-notes:

Things to be aware of
^^^^^^^^^^^^^^^^^^^^^

The Photini documentation is written in `reStructuredText <http://docutils.sourceforge.net/rst.html>`_.
This is a markup language that looks very like plain text, but uses certain characters to give extra meaning to some parts.
You need to take extra care when the string to be translated includes such markup.
The markup often needs to be preceded or followed by a space or other punctuation.
Take care to copy spaces and punctuation from the English source.

Double backquotes ``````
   These often mark words that are used in the Photini GUI.
   You may wish to include the English equivalent in brackets after your translation to help users read the documentation as the screen grabs are all from the English version.
   For example, the English ````Orientation```` could appear in a German translation as ````Ausrichtung (Orientation)````.

Special characters, e.g. ``(|hazard|)``
   These refer to Unicode symbols and should not be translated.

Short cross references, e.g. ``:doc:`tags```
   These should not be translated.

Long cross references, e.g. ``:ref:`installation <installation-optional>```
   The text within the ``<>`` characters should not be translated, but it may be appropriate to translate the preceding link text.

Short external links, e.g. ```Google Photos`_``
   If you need to translate the text you can transform the short link into a long one.
   For example, the English ```Google Photos`_`` could appear in a Korean translation as ```Google 포토 <Google Photos_>`_``.
   Note the underscores ``_`` and backquotes ````` - they are vital!

Long external links, e.g. ```Flickr <http://www.flickr.com/>`_``
   The url within the ``<>`` characters should not be translated, but it may be appropriate to translate the preceding link text.

.. _localisation-documentation-testing:

Testing your translation
^^^^^^^^^^^^^^^^^^^^^^^^

If you install Sphinx_ (See :ref:`installation <installation-documentation>`) you can build a local copy of the documentation using your translation.
For example, to build Dutch documentation::

   $ LANG=nl python3 utils/build_docs.py

Open ``doc/html/index.html`` with a web browser to read the translated documentation.

.. _Babel:       http://babel.pocoo.org/
.. _Qt Linguist: https://doc.qt.io/qt-6/linguist-translators.html
.. _Sphinx:      https://www.sphinx-doc.org/
.. _Transifex:   https://www.transifex.com/jim-easterbrook/photini/
.. _Weblate:     https://hosted.weblate.org/projects/photini/
