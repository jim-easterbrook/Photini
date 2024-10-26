Notes
=====

Weblate pulls content from the ``main`` branchand pushes to the ``weblate`` branch when anything is updated.

Transifex's GitHub integration isn't great, so do it manually with 'tx push' and 'tx pull'.

Reminders for what to do when translations are updated.

When program source changes::

   git checkout main                     # switch to main branch
   python3.11 utils/lang_update.py       # update translations from source
   linguist-qt5 src/lang/en/photini.ts   # copy any new English strings
   python3.11 utils/lang_update.py -s    # update translations from source
   git push                              # push updated translations to GitHub
   python3.11 utils/lang_update.py -s -t # update translations from source
   tx push -s                            # push updated translations to Transifex

When documentation source changes::

   git checkout main                    # switch to main branch
   python3 utils/lang_update.py -d -s   # update translations from source
   git push                             # push updated translations to GitHub
   tx push -s                           # push updated translations to Transifex

When new content on Weblate gets pushed to GitHub, use GitHub's web page to create a pull request from the branch to main.
Then download updated translations::

   git checkout main                     # switch to main branch
   git pull                              # fetch new content
   python3.11 utils/lang_update.py -s    # reformat translations if needed
   git push                              # push updated translations to GitHub
   python3.11 utils/lang_update.py -s -t # update translations from source
   tx push -t                            # push updated translations to Transifex

When there is new content on Transifex in language xx::

   git checkout main                        # switch to main branch
   tx pull -l xx -f                         # fetch new content from Transifex
   python3.11 utils/lang_update.py -s -l xx # reformat translations if needed
   python3 utils/lang_update.py -d -s -l xx # reformat translations if needed
   git push                                 # push updated translations to GitHub

Edit translation locally::

   git checkout main                        # switch to main branch
   git pull                                 # fetch new content
   python3 utils/lang_update.py -l xx       # update from source, with line numbers and suitable for Qt Linguist
   pyside6-linguist src/lang/xx/photini.ts  # edit translation of language xx
   python3.11 utils/lang_update.py -s -l xx # remove line numbers
   git push                                 # push updated translation to GitHub
   tx push -t -l xx                         # push updated translations to Transifex

Before a new release of Photini::

   git checkout main                    # switch to main branch
   git pull                             # fetch new content
   python3.11 utils/lang_update.py -s   # update from source

Plurals
-------

Qt Linguist and Transifex have different ideas about how many plural forms some languages have.
For example, Transifex expects French to have three plurals ``1``, ``many``, and ``other``, but Qt Linguist expects two ``singular`` and ``plural``.
The -t option to lang_update.py inserts extra plurals to make the file suitable for Transifex.
