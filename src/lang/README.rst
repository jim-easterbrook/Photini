Notes
=====

Transifex and Weblate both pull content from the ``main`` branch.
Transifex creates pull requests when a component is 100% translated, Weblate pushes to the ``weblate`` branch when anything is updated.

Reminders for what to do when translations are updated.

When program source changes::

   git checkout main                    # switch to main branch
   python3 utils/lang_update.py -s -t   # update translations from source
   git push                             # push updated translations to GitHub
   tx push -s                           # push updated translations to Transifex

When documentation source changes::

   git checkout main                    # switch to main branch
   python3 utils/lang_update.py -d -s   # update translations from source
   git push                             # push updated translations to GitHub
   tx push -s                           # push updated translations to Transifex

When new content on Weblate gets pushed to GitHub, use GitHub's web page to create a pull request from the branch to main.
Then download updated translations::

   git checkout main                    # switch to main branch
   git pull                             # fetch new content
   python3 utils/lang_update.py -s -t   # reformat translations if needed
   git push                             # push updated translations to GitHub
   tx push -t                           # push updated translations to Transifex

When there is new content on Transifex in language xx::

   git checkout main                        # switch to main branch
   tx pull -l xx -f                         # fetch new content from Transifex
   python3 utils/lang_update.py -s -t -l xx # reformat translations if needed
   python3 utils/lang_update.py -d -s -l xx # reformat translations if needed
   git push                                 # push updated translations to GitHub

Edit translation locally::

   git checkout main                        # switch to main branch
   git pull                                 # fetch new content
   python3 utils/lang_update.py -l xx       # update from source, with line numbers
   pyside6-linguist src/lang/xx/photini.ts  # edit translation of language xx
   python3 utils/lang_update.py -s -t -l xx # remove line numbers
   git push                                 # push updated translation to GitHub
   tx push -t -l xx                         # push updated translations to Transifex

Before a new release of Photini::

   git checkout main                    # switch to main branch
   git pull                             # fetch new content
   python3 utils/lang_update.py         # update from source
   python3 utils/build_lang.py          # "compile" language files

Plurals
-------

Qt Linguist and Transifex have different ideas about how many plural forms some languages have.
For example, Transifex expects French to have three plurals ``1``, ``many``, and ``other``, but Qt Linguist expects two ``singular`` and ``plural``.
The ``lang_update.py`` adds empty plural forms to satisfy Transifex (the ``-t`` option) and removes them before running Qt tools.
