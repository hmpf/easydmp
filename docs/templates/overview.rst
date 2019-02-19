========
Overview
========

A ``Template`` consists of at least one ``Section``. If there is only a single
section, it does not need a ``title``. If there are multiple sections, each
should have a title unique to that template.

A ``Section`` can be empty. That means it doesn't have any ``Question`` s and
is just used as an organizational tool. Sections that do have at least one
``Question`` is of two types: ``branching`` or ``linear``. The default is
a linear section. If a branching section is needed it needs to be set
explicitly on that section.

All questions are by default ``obligatory``. That means that they will all be
shown to the plan maker. In a branching plan, questions hidden by a branch are
NOT obligatory, they can be skipped over completely, never seen by the plan
maker.
