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

Gluing it all together
======================

The string-name, like `date`, of a Question-class, is registered in the list
`INPUT_TYPES` in `easydmp.dmpt.models`. This is used to build the choice-list
for the `input_type` field on the mother class.

In the same file is `INPUT_TYPE_MAP`, where the string-name is the key, and the
subclassed Question-model is the value. This is used to look up the class for
a specific string-name.

In `easydmp.dmpt.forms` is the third map and last place where a string-name
must be registered: INPUT_TYPE_TO_FORMS. The string-name is the key, and the
form-class or formset-class is the value.

The map is used in `make_forms()` in the same file to look up a form class
given an instance of a question.

Things that should be better
============================

It would be better if the three `INPUT_TYPE` constants were built up with
a plugin-system instead of being kept up to date by hand. Each question-type
could then have all its various components in the same module, and it would be
more obvious how to write a new type. This would also allow optional 3rd party
question modules.

Whenever a new string-name is added to `INPUT_TYPES`, Django generates a new
migration that doers not change anything in the database. It might be better if
`INPUT_TYPES` were a lookup table, testing needed.
