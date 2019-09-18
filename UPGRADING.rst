UPGRADING
=========

Normally, upgrading is just a matter of getting the new code and running
``python manage.py migrate``. Any exceptions will be listed here.

0.20.0 -> 0.20.1
----------------

There was an error in 0.20.0. It is possible to go directly from a correctly
migrated 0.19.9 to 0.20.1. When on 0.20.1 run::

    python manage.py migrate --fake

to correctly update the migrations-table.

0.19.9 -> 0.20.0
----------------

If you go directly from anything before 0.19.9 to anything after 0.19.9, your
upgrade will fail. First upgrade to 0.19.9 and run its migrations, which will
just manipulate the migrations log, then upgrade to 0.20.0, which deletes the
files of the no longer needed migrations.