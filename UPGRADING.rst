=========
UPGRADING
=========

Normally, upgrading is just a matter of getting the new code and running
``python manage.py migrate``. Any exceptions will be listed here.

0.25.0 -> 1.0.0
===============

This switches to a redesigned branching system.

If you have no templates utilizing branches, all you need do is install the new
version.

How to check whether you have any templates utilizing branches:

The easiest method is to use the built in web admin.

1. Go to "Sections" under "Dmpt".
2. Filter on "By branching": "Yes".

If zero sections have branching, just install the new version. It's not even
necessary to run ``python manage.py migrate``.

If you **DO** have one or more sections utilizing branches...

Most important step: make a backup of the production database.

How to convert, maximum paranoia version
----------------------------------------

1. Make a copy of the production database. You need the branching templates and
   some plans built on those templates.
2. Point a test-instance with the new version towards the copy. You'll need
   command line-access to the instance.
3. Run ``python manage.py show_branching`` to get a list of sections to convert.
4. Run ``python manage.py shell``, in such a way that the shell may open
   programs on the computer you are on. (Inside docker might be tricky!)
5. In the python shell, run ``from easydmp.dmpt.models import Section``
6. In the same shell, run::

       Section.objects.get(id=NUM).view_dotsource('pdf', debug=True)

   (NUM is the integer id of the section, which you can get from
   ``show_branching`` in step 3 or via the admin.)

   This should pop up a program showing a pdf of the directed acyclic graph of
   that section, pre-conversion. You might want to store or print out this pdf,
   for later comparison.
7. From the command line in the interface, run ``python manage.py fill_explicitbranch -s NUM``
   to convert. NUM is the same integer as in the previous step.
8. Redo step 6. The new graph should have the same paths, but when there are
   multiple paths connecting the same two questions, some might have been
   simplified away.
9. Go to the website for the instance and "walk" a plan, backwards and
   forwards, forcing changes in what branch is taken in order to check that
   conversion worked with your old branch-design.
10. You might want to also get rid of the old branches with
    ``python manage.py unset_chosen_nodes -s NUM`` and then redo step 8 and 9.

If there are no surprises, you can run ``fill_explicitbranch`` for that section
on the production database. After every section is converted in the production
database, you can upgrade to the new version on the production instance.

Finally, run ``python manage.py unset_chosen_nodes -a`` on the production version.

If the branches are very simple it might be easier to first convert, then fix
any errors manually.

How to convert, recklessly
--------------------------

You have a recent backup of the database, right?

1. Install the new version in a new instance and point it towards the production database.
2. Run ``python manage.py fill_explicitbranch -a`` to convert everything at once.
3. Install the new version in the production instance.
4. Get rid of the old branches in prodction:
   ``python manage.py unset_chosen_nodes -a``.

How to fix branching errors
---------------------------

Add or change new entries in ExplicitBranch, for instance via a Question's page
in the admin, until it works. Copy the resulting ExplicitBranch-data to the
production database. When the section is done, nuke the old branches for that
section with ``unset_chosen_nodes -s NUM``, NUM being the section's id.

Reverting to the previous branching system
------------------------------------------

This is what you have the database backup for! Use version 0.25.0 with the
backup database.

0.20.1 -> 0.21.0
================

This rewrites True/False answers in plans to 'Yes/No'.

A plan created on 0.21.0 won't work on an EasyDMP older than 0.21.0. A plan
created before 0.21.0 won't work on 0.21.0 until the migration have been run.

Specific plans can be converted via the django admin command
"answers_bool_to_yesno", and back with "answers_yesno_to_bool".

0.20.0 -> 0.20.1
================

There was an error in 0.20.0. It is possible to go directly from a correctly
migrated 0.19.9 to 0.20.1. When on 0.20.1 run::

    python manage.py migrate --fake

to correctly update the migrations-table.

0.19.9 -> 0.20.0
================

If you go directly from anything before 0.19.9 to anything after 0.19.9, your
upgrade will fail. First upgrade to 0.19.9 and run its migrations, which will
just manipulate the migrations log, then upgrade to 0.20.0, which deletes the
files of the no longer needed migrations.
