===================================
Importing plans and their templates
===================================

Plans and templates in the export-format, as exported from the API, can be
imported into EasyDMP. This makes it possible to move a plan or template from
one EasyDMP to another, or to a restore from backup.

Templates from file
===================

The endpoint is at ``/api/v2/templates/import/``.

You can get an import by curl:

.. code-block:: console

    curl -X POST "https://DOMAIN/api/v2/templates/ID/import/" \
    -H "Content-Type: application/json" -H "Authorization: Bearer TOKEN" \
    -d @import.json

or by httpie:

.. code-block:: console

    https POST DOMAIN/api/v2/templates/ID/import/ \
    "Authorization:Bearer TOKEN" < import.json

Templates from URL
==================

If a template export is reachable on a publicly available URL it can be fetched
directly.

The endpoint is at ``/api/v2/templates/import/url/``.

You can get an import by curl:

.. code-block:: console

    curl -X POST "https://DOMAIN/api/v2/templates/ID/import/" \
    -H "Content-Type: application/json" -H "Authorization: Bearer TOKEN" \
    -d '{"url": "URL_TO_TEMPLATE"}'

or by httpie:

.. code-block:: console

    https POST DOMAIN/api/v2/templates/ID/import/ \
    "Authorization:Bearer TOKEN" url=URL_TO_TEMPLATE

Plans from file
===============

The endpoint is at ``/api/v2/plans/import/``.

You can get an import by curl:

.. code-block:: console

    curl -X POST "https://DOMAIN/api/v2/plans/import/" \
    -H "Content-Type: application/json" -H "Authorization: Bearer TOKEN" \
    -d @import.json

or by httpie:

.. code-block:: console

    https POST DOMAIN/api/v2/plans/import/ \
    "Authorization:Bearer TOKEN" < import.json

Plans from URL
==============

If a plan export is reachable on a publicly available URL it can be fetched
directly.

The endpoint is at ``/api/v2/plans/import/url/``.

You can get an import by curl:

.. code-block:: console

    curl -X POST "https://DOMAIN/api/v2/plans/import/" \
    -H "Content-Type: application/json" -H "Authorization: Bearer TOKEN" \
    -d '{"url": "URL_TO_PLAN"}'

or by httpie:

.. code-block:: console

    https POST DOMAIN/api/v2/plans/import/ \
    "Authorization:Bearer TOKEN" url=URL_TO_PLAN
