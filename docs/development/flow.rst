====
Flow
====

For linear (non-branching) sections, flow, the order of questions, is solely
controlled by the ``position``-field in Sections and Questions.

For optional and branching sections, the ``ExplicitBranch`` model comes into
play.

Visualizing flow
================

With ``graphviz``, the example templates, and the dependencies in
``requirements/dev.txt`` installed, it is possible to generate a flow chart for
a section.

Start up a python shell with::

    python manage.py shell

Inside the shell, try::

    from easydmp.dmpt.models import Template, Section
    t = Template_objects.get(id=1)
    s = t.sections.all()[0]
    s.view_dotsource('pdf')

A section with no questions will look like two double circles.

A linear section will have a start-node in a double-circle, an arrow going to
the first question, another from the first question to the second, all the way
to the last, which will have an arrow to an end-node in a double-circle. All
the arrows will be marked by ``->``, because thet marks movement through the
``position``-field.

In a branching section, multiple arrows can both eneter and leave a question,
and the markers on the arrows will be one of:

``->``
    for movement through position.

``=>``
    for movement through position from a question that has a node, usually the
    last node in a branch.

a string
    for an edge with a condition. This is only for question with
    CannedAnswers.

empty
    for an edge without a condition, ususally due to an edge without
    a CannedAnswer.

Too many of the last type is usually a sign that the graph is too complex.

There should be no loops.
