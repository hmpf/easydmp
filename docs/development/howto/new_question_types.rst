=========================
Howto: New Question types
=========================

Question subtypes: form-based and formset-based
===============================================

Questions roughly come in two types: Those that can be shown with a form, and
those that need a formset. The former is much easier and quicker to make than
the latter.

A formset is needed for multiple, number non-predetermined, rows of the same
thing, where at least one thing is typed in. For instance an url (validated
free text) and its title text (free text); or a cost with a sum (written
number), a currency (drop down) and a description (free text).

If each row just asks for a small set of single, predetermined things there is
already a ChoiceQuestion (max one) or a MultipleChoiceOneTextQuestion and the
CannedAnswer model. If there more than ten predetermined things consider using
one of the EEStore question types.

--------------
Formset extras
--------------

A formset factory has the extra parameters `min_num`, `max_num`, `validate_min`
and `validate_max`. If the field `Question.optional` is True, validate_min will
be automatically forced to False.

The parameter `can_order` has no effect as of yet since it needs support in the
html-template and is not used. While `can_delete` is used, deletion needs an
overhaul, it breaks easily.

A way to make the formset widget
--------------------------------

If you make a standard form for all the fields and instanciate it, eg. with
``print(form)``, you'll have all the field definitions to put into the html.
Then reuse the field definitions in a subclass of MultiValueField.

How to make the different types
===============================

A simple Question like `date` consists of a proxy model inheriting from
Question with an `input_type`, and a form for the same `input_type`. If it's
a single field like in `date` that's it, but for a complex field like
`daterange` you also need a widget.

A formset like `cost` also has a proxy model inheriting from Question, but in
addition to the form it also has a formset. Do note the base class:
AbstractNodeFormSet has a lot of extras to make the formset behave like
a question form. It is also always necessary to make a widget for combining all
the fields in the form.

The field ``input_type`` on Question is a ``QuestionType``-model, pointing to
a table of registered types. This model has two fields. In addition to the
id, which is the same as the string-name, there is a boolean field ``allow_notes``
that by default is True. This controls the default value for ``has_notes`` on
a question. If `has_notes` isn't explicitly set to anything on saving the
question, it will be set to whatever the ``QuestionType``'s ``allow_notes`` is.

Gluing it all together
======================

The string-name, like `date`, of a Question-class is automatically registered
as a key in the dict `INPUT_TYPES` on `easydmp.dmpt.models.Question`. The keys
are used to build the choice-list for the `input_type` field on the mother
class.

The values of `INPUT_TYPES` are InputType objects. These have the attribute
`model`, which is the Question-model subclass. This may be used to look up the
class for a specific string-name. They also have the attribute `form`, which is
used to look up the form-class or formset-class for that input type. Forms
inheriting from AbstractNodeForm does this automatically, but formsets must do
it explicitly. `INPUT_TYPES` is used in `make_forms()` in the same file to look
up a form class given an instance of a question.

Finally, run "makemigrations". To the resulting migration, add a data-migration
that adds a row to the QuestionType-table:

.. code-block::

    from functools import partial
    ..

    from easydmp.dmpt.utils import register_question_type

    register_mytype_type = partial(register_question_type, 'mytype', True)


    class Migration(migrations.Migration):
        ..
        operations = [
            ..
            migrations.RunPython(register_mytype_type, migrations.RunPython.noop),
        ]


The last argument to ``partial()`` must be either True (allow notes by default)
or False (do not allow notes by default).

Things that should be better
============================

It would be better if formsets also could auto-register in `INPUT_TYPES`, but
frankly, it would be better to avoid formsets altogether.

Whenever a new input type is created, the TYPE-attribute on the form and model
must match.
