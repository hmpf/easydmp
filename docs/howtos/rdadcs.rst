Export a plan to RDA DCS
========================

This is most easily done via the the API. The endpoint is
``/api/v2/plans/{id}/export/rda/``, where ``{id}`` is the numeric identifier of
the plan.

Set up RDA DCS support
======================

To set up RDA DCS support you need access to the source code.

The file ``src/easydmp/rdadcs/data/rdadcs-v1.tsv`` contains all the RDA DCS
keys mapped to EasyDMP question types.

Load it into the database with the management-command
``load_rdadcs_keys_and_types``::

    python manage.py load_rdadcs_keys_and_types src/easydmp/rdadcs/data/rdadcs-v1.tsv

Check in the admin under RDADCS > RDADCS keys that they were loaded correctly.


Mark up a template with RDA DCS keys
====================================

This depends on RDA DCS support to have been set up first.

This is easiest done via admin and CLI simultaneously. Split your screen so
that you have the open admin on one side and a console/terminal on the other
side.

Either use the file ``src/easydmp/rdadcs/data/rdadcs-v1.tsv`` directly, or get
it by dumping it via the command ``dump_rdadcs_keys_and_types``::

    python manage.py dump_rdadcs_keys_and_types > rdadcs-v1.tsv

This is a tab-separated file.

Copy it twice, into ``question_links.tsv`` and ``section_links.tsv``.

Mark up the structure
---------------------

The structure of the template is set up via the ``section_links.tsv``. So, for
instance if you have a section in your template that corresponds to RDA DCS
"dataset", you find the key '.dmp.dataset[]' in the left column and add or
replace the right column with the integer section id of your section.

Get the section id via the admin, see "EASYDMP Template > Sections", filter on
your template. Do this for all relevant sections in your template, then delete
all lines in ``section_links.tsv`` that does not end with an integer.

Load the section structure with::

    python manage.py load_rdadcs_section_links section_links.tsv

Since a key can only be connected once, you can remove the keys that remains in
``section_links.tsv`` from ``question_links.tsv``.

Then do ``question_links.tsv``.

Mark up the lookups
-------------------

In the admin, switch to the "EASYDMP TEMPLATES > Questions"-page, filter on
template, then go section by section (via filtering). Find the relevant key in
``question_links.tsv``, check that the right-hand value is the same type as the
question, and replace the right-hand value with the id of the question.

When done, again remove all ines that do not end with an integer, and load the
lookups by::

    python manage.py load_rdadcs_question_links question_links.tsv

Test your markup by exporting a plan based on it via the API (endpoint
``/api/v2/plans/{id}/export/rda/``, where ``{id}`` is the numeric identifier of
the plan.)

The result may not be valid. The RDA DCS JSON Schema is available in
``src/easydmp/rdadcs/data/maDMP-schema-1.1.json`` so that you can validate.

There are two main reasons why your export is not valid: the structure of your
template is too different from RDA DCS, or a required value in RDA DCS is not
required in you template. You might want to play with the links (via the admin)
until you get an export you are satisfied with.

When you are happy, export your template so that you have a backup.
