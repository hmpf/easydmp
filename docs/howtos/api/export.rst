===================================
Exporting plans and their templates
===================================

While it is possible to dump all info about a (public) template or plan by
crawling the API, there are dedicated export endpoints to get everything needed
in a single operation. Using the endpoints also allows exporting non-public
plans and templates that you have view-access to, by autenticating first.

Such exports can be imported into another instance of EasyDMP, or, since it is
a json dump, converted into a different DMP-system's plans or templates,
provided there exists a converter. The export-format is also suitable as
a backup.

Templates
=========

The endpoint is at ``/api/v2/templates/ID/export/``.

You can get an export by curl:

.. code-block:: console

    curl "https://DOMAIN/api/v2/templates/ID/export/" \
    -H "Accept: application/json" \
    -H "Authorization: Bearer TOKEN" > template-ID.json

or by httpie:

.. code-block:: console

    https DOMAIN/api/v2/templates/ID/export/ \
    "Authorization:Bearer TOKEN" > template-ID.json

Plans
=====

The endpoint is ``/api/v2/plans/ID/export/?format=json``, note the formatting
flag.

You can get an export by curl:

.. code-block:: console

    curl "https://DOMAIN/api/v2/plans/ID/export/?format=json" \
    -H "Accept: application/json" \
    -H "Authorization: Bearer TOKEN" > plan-ID.json

or by httpie:

.. code-block:: console

    https DOMAIN/api/v2/plans/ID/export/ format==json \
    "Authorization:Bearer TOKEN" > plan-ID.json

Other supported formats are "html" and "pdf".

An exported plan contains an export of its template.
