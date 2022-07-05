=========
Templates
=========

A template is a collection of questions, and questions are organized into
sections. When filling in plan a form is generated from the section and
questions according to the template of that plan.

The structure of a template
===========================

A ``Template`` consists of at least one ``Section``. If there is only a single
section, it does not need a ``title``. If there are multiple sections, each
should have a title unique to that template.

A ``Section`` can be empty. That means it doesn't have any ``Question`` s and
is just used as an organizational tool. Sections that do have at least one
``Question`` is of two types: ``branching`` or ``linear``. The default is
a linear section. If a branching section is needed it needs to be set
explicitly on that section.

All questions are by default ``on_trunk``. That means that they will all be
shown to the plan maker. In a branching plan, questions hidden by a branch are
NOT on_trunk, they can be skipped over completely, never seen by the plan
maker.

Templates included with the source
==================================

There are currently two templates included with the source:

* One template that exemplifies every single question type that comes with
  a vanilla installation of EasyDMP, in
  ``src/easydmp/dmpt/data/question-type-demonstration.template.json``.
* One template for importing plans in RDA DCS format, in
  ``src/easydmp/rdadcs/data/rdadcs-v1.1.template.json``.

In order to have full RDA DCS support, the latter *must* be imported. See the
howtos for how.
