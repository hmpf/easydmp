===================
Exporting templates
===================

A template can be exported via the CLI, admin or API.

Via CLI
=======

Run the command::

    python manage.py export_complete_template ID > FILENAME

where ID is the numeric id of the template and FILENAME is what name to give
the exported file.

Via admin
=========

A superuser can export a template by going to "DMPT > Templates". There is
a column "Export" that redirects to the correct JSON file.

Via API
=======

There is an endpoint to export templates:

* `/api/v2/templates/{id}/export/`, where "id" is the numeric id of a template
