Notes
=====

The ``localisation`` branch is used for all translation activity.
Weblate and Transifex both pull content from GitHub and push updated content there.

Reminders for what to do when translations are updated.

When program or documentation source changes::

   git checkout localisation            # switch to localisation branch
   git merge master                     # merge in new source content
   python3 utils/lang_update.py -s      # update templates from source
   git push                             # push updated source to GitHub

When new content on Transifex or Weblate eventually gets pushed to GitHub, use GitHub's web page to create a pull request from localisation branch to master.
Then download updated translations::

   git checkout master                  # switch to master branch
   git pull                             # fetch new content

Edit translation locally::

   git checkout localisation            # switch to localisation branch
   git pull                             # fetch new content
   python3 utils/lang_update.py         # update from source
   linguist-qt5 src/lang/xx/photini.ts  # edit translation of language xx
   git push                             # push updated translation to GitHub

Before a new release of Photini::

   git checkout master                  # switch to master branch
   git pull                             # fetch new content
   python3 utils/lang_update.py         # update from source
   python3 utils/build_lang.py          # "compile" language files
