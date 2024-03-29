======================
Easydmp Django Project
======================

.. image:: https://github.com/hmpf/easydmp/workflows/Test%20django%20package/badge.svg

.. image:: https://readthedocs.org/projects/easydmp/badge/?version=latest
  :target: https://easydmp.readthedocs.io/en/latest/?badge=latest
  :alt: Documentation Status

.. image:: https://codecov.io/gh/hmpf/easydmp/branch/master/graph/badge.svg?token=7X5GP4NXHH
   :target: https://codecov.io/gh/hmpf/easydmp


This project has been designed to be installable via ``setup.py``.

Layout:

::

    manage.py
    requirements/
    |-- django.txt
    |-- base.txt
    \-- ..
    requirements.txt
    tests/
    src/
    \-- easydmp/
       |-- site/
       |   |-- __init__.py
       |   |-- settings/
       |   |   |-- base.py
       |   |   |-- dev.py
       |   |   \-- production.py-example
       |   |-- urls.py
       |   \-- wsgi.py
       |
       \-- [apps] ..


Prerequisites
=============

- python >= 3.8
- pip
- graphviz (if you want to be able to graph the flow of templates)
- virtualenv/wrapper (optional)
- some sql database supported by Django

As for the database, it can run on sqlite. It's better to run it on PostgreSQL.
It does not depend on any postgres features newer than version 9.3.

Installation
============

Creating the environment
------------------------

Create a virtual python environment for the project.
If you're not using virtualenv or virtualenvwrapper you may skip this step.

For virtualenvwrapper
.....................


::

    $ mkvirtualenv -p /usr/bin/python3 --no-site-packages easydmp-env

Activate with::

    $ workon easydmp-env


For virtualenv
..............

Create a virtual env in the current directory called ``easydmp-env``::

    $ virtualenv -p /usr/bin/python3 easydmp-env

Activate with::

    $ source easydmp-env/bin/activate

We do not recommend having the actual code inside the virtual env.


Clone the code
--------------

Obtain the url to your the repository::

    $ git clone <URL_TO_GIT_RESPOSITORY> easydmp


Install requirements
--------------------

::

    $ cd easydmp
    $ pip install -r requirements-frozen.txt

This will get you the latest officially supported Django version and EasyDMP's
other dependencies. For other versions, see the other ``requirements-*.txt``
files.

Setup and sync database
-----------------------

::

    $ python manage.py migrate

Unit tests with a particular database (example)
-----------------------------------------------

::

    $ TEST_DATABASE_URL=postgresql://easydmp:easydmp@localhost:5432/easydmp tox

Running in development
======================

If you need to change any settings from the default, put a file
``devsettings.py`` with the changes somewhere on the python path, and set the
environment-variable ``DJANGO_SETTINGS_MODULE`` to the dotted path of the
devsettings-file.

Using docker-compose
--------------------

The docker-compose file runs its own database. After the first `docker-compose
build` and `docker-compose up`, fill the database with the default development
fixture like so:

1. Enter the django container: ``docker exec -ti django_server bash``
2. Bootstrap some users, tnmplates, and the EEStore cache: ``python manage.py setup --development``

When using virtualenv(wrapper)
------------------------------


::

    $ python manage.py runserver

This will use the settings file ``easydmp.site.settings.dev`` unless
``DJANGO_SETTINGS_MODULE`` has been set.

Bootstrap some users, tnmplates, and the EEStore cache: ``python manage.py setup --development``

Open browser to ``http://127.0.0.1:8000``

What happens during setup
-------------------------

With no flags, the ``setup``-command currently just creates the Template
Designer group.

With the ``--eestore`` flag an outdated copy of cached data from the EEStore is
loaded.

The ``--development`` flag does the same as the ``--eestore`` but in addition
creates the development users and loads some starter templates.

Whenever you make a change that necessitates a migration of anything in the
``dmpt``-app, check that the template export and import works correctly and
make new exports of the templates, to be included in the PR.

Development users
.................

Three users are created. The password to all of them is ``niezynarecxaqd``.
Obviously, these users should not be used in production.

ordinaryuser
    This is the default user, and is what is created automatically on login via
    OAuth. May create and edit plans, invite other user to view and edit plans,
    share and unshare plans.
templatedesigner
    This is an ``ordinaryuser`` with additional access to a special version of
    the admin that allows creating linear templates. An ``ordinaryuser`` can be
    converted to a ``templatedesigner`` by a ``superuser``.
superuser
    Has access to everything, and may use the admin.

Additional superusers can be created from the command line::

    python manage.py createsuperuser

Standard groups
...............

A single group is created, ``Template Designer``. Putting a user in this group
will make that user into a ``templatedesigner``.

Example templates
-----------------

At least two templates are created: One with multiple linear sections, and one
with only a single linear section.

Deploying to production
=======================

Use a settings-file tailored for the production environment. If there are more
than one webserver working together as a cluster, they should all have the same
production settings. Assure that the following holds:

* ``DEBUG`` must be ``False``
* Generate a new ``SECRET_KEY`` (a string of 50 random printable ASCII
  characters is the norm)
* We recommend setting the environment variable ``MEDIA_ROOT`` to a path that
  is servable by the web server and has a handful megabytes of free diskspace.

Deploying to PaaSes
-------------------

We recommend making a deployment-specific project that fetches the code (for
instance with ``curl``/``wget``, ``pip install`` or ``git clone``) and adds all
the necessary deployment-specific code, including any overrides for settings,
templates, static files etc.

::

    .
    |-- deploymentmethod
    |   |-- settings.py
    |   |-- wsgi.py
    |   |-- templates/
    |   |-- static/
    |   |-- requirements.txt
    |   .. deployment method specific files
    |
    .. deployment method specific files


Deploying to hardware
---------------------

Get the code to where it needs to be, with a script utilizing ``rsync``,
``git clone``, ``fabric`` or whatever. We recommend keeping the dependencies in
a ``virtualenv``, which means that the web server will need to know about the
path to the virtualenv.

If the virtualenv is installed at ``/path/to/virtualenv`` and the python
version is 3.5, the follwing path must be somehow added to the python path::

    /path/to/virtualenv/lib/python3.5/site-pacakges/

If using Apache, do not use ``mod_python``, use ``mod_wsgi`` in daemon mode.

----

This work is co-funded by the EOSC-hub project (Horizon 2020) under Grant
number 777536.
