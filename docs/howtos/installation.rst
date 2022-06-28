======================
Installation and setup
======================

This project has been designed to be installable via ``setup.py``.

Layout:

::

    manage.py
    requirements/
    |-- django.txt
    \-- base.txt
    requirements.txt
    tests/
    src/
    |-- flow
    \-- easydmp/
        \-- site/
            |-- __init__.py
            |-- settings/
            |   |-- base.py
            |   \-- dev.py
            |-- urls.py
            \-- wsgi.py


Prerequisites
=============

- python >= 3.8
- pip
- graphviz
- virtualenv/wrapper (optional)

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


For virtualenv
..............

::


    $ virtualenv -p /usr/bin/python3 --no-site-packages easydmp-env
    $ cd easydmp-env
    $ source bin/activate


Clone the code
--------------

Obtain the url to your git repository::

    bash
    git clone <URL_TO_GIT_RESPOSITORY> easydmp


Install requirements
--------------------

::

    $ cd easydmp
    $ pip install -r requirements.txt


Setup and sync database
-----------------------

::

    $ python manage.py migrate


Running in development
======================

If you need to change any settings from the default, put a file
``devsettings.py`` with the changes somewhere on the python path, and set the
environment-variable ``DJANGO_SETTINGS_MODULE`` to the dotted path of the
devsettings-file.

When using virtualenv(wrapper)
------------------------------


::

    $ python manage.py runserver


Open browser to ``http://127.0.0.1:8000``


Deploying to production
=======================

Use a settings-file tailored for the production environment. If there are more
than one webserver working together as a cluster, they should all have the same
production settings. Assure that the following holds:

* ``DEBUG`` must be ``False``
* Generate a new ``SECRET_KEY`` (a string of 50 random printable ASCII
  characters is the norm)

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
version is 3.8, the follwing path must be somehow added to the python path::

    /path/to/virtualenv/lib/python3.8/site-pacakges/

If using Apache, do not use ``mod_python``, use ``mod_wsgi`` in daemon mode.
