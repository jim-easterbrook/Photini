Notes
=====

Transifex and Weblate both pull content from the ``master`` branch.
Transifex creates pull requests when it has new content, Weblate pushes to the ``weblate`` branch.

Reminders for what to do when translations are updated.

When program or documentation source changes::

   git checkout master                  # switch to master branch
   python3 utils/lang_update.py -s      # update templates from source
   git push                             # push updated source to GitHub

When new content on Transifex or Weblate eventually gets pushed to GitHub, use GitHub's web page to create a pull request from the branch to master if necessary.
Then download updated translations::

   git checkout master                  # switch to master branch
   git pull                             # fetch new content

Edit translation locally::

   git checkout master                  # switch to master branch
   git pull                             # fetch new content
   python3 utils/lang_update.py         # update from source, with line numbers
   linguist-qt5 src/lang/xx/photini.ts  # edit translation of language xx
   python3 utils/lang_update.py -s      # remove line numbers
   git push                             # push updated translation to GitHub

Before a new release of Photini::

   git checkout master                  # switch to master branch
   git pull                             # fetch new content
   python3 utils/lang_update.py         # update from source
   python3 utils/build_lang.py          # "compile" language files

Plurals
-------

Qt Linguist and Transifex have different ideas about how many plural forms some languages have.
For example, Transifex expects French to have three plurals ``1``, ``many``, and ``other``, but Qt Linguist expects two ``singular`` and ``plural``.
The ``lang_update.py`` adds empty plural forms to satisfy Transifex.
These make Qt Linguist report a warning, but everything else seems to work OK.
