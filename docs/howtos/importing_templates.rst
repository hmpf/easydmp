===================
Importing templates
===================

A template can be imported via the CLI, admin or API.

Via CLI
=======

Run the command::

    python manage.py import_complete_template EXPORT

where EXPORT is the path to the EasyDMP template export, a json file.

Via admin
=========

A superuser can import a template by going to "DMPT > Templates". Just to left
of the "ADD TEMPLATE"-button there's an "IMPORT"-button.

Via API
=======

There are two endpoints to import templates:

* `/api/v2/templates/import/`, where you POST a JSON-file in the correct format
* `/api/v2/templates/import/url/`, where you POST a JSON-file of the following format::

    {"url": URL}

  The URL is an url to a publicly available export of an existing template.
