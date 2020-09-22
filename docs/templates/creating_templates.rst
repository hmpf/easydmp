==============================
Creating and editing templates
==============================

There is a very rough and ready method available to create linear plans in
EasyDMP.

Getting access to create linear templates
=========================================

A superuser must grant you the role ``Template Designer``. After
that, you get access to the *template admin* from the link ``Admin`` up
top.

How to create templates
=======================

Start by clicking 'Add' next to **Templates**. On the next page, add at least
a ``title`` and a ``description``. The ``abbreviation`` is used only inside the
template admin in order to make some links shorter and easier to read at
a glance so you could skip that.

Then create the sections you need, and order them with the ``position``-field.

Next, and most time-consuming step: Add the questions! They also have
a ``position``-field.

You might want to write the questions down on Post-Its (one per question) and
move them around 'til they have the order you want before you add them in the
admin, since reordering is a bit clunky.

For a linear section, all questions are ``on_trunk``, so no need to change
that. An ``optional`` question need not be answered. The
``optional_canned_text`` will be shown in the generated text if the question
isn't given an answer. An optional question cannot start a branch, since in
order to know which branch to take, the question must be answered.

Testing a template
------------------

Create a new plan (path: ``/plan/``) and answer the questtions from beginning
to end.

Since a plan depends on the structure of a template, if you change a template,
the plan may very well break and error out.

For instance, the following template changes may break plans:

* changing the type of a question, if that question is answered in the plan.
* changing the ``choice`` of a CannedAnswer, if that choice is used as an
  answer to a question in a plan.

If flow or ``position`` is changed, some questions may become unreachable, and
clicking ``Prev``/``Next`` might not lead where expected.

A superadmin have access to the raw dump of the plans and can delete some
answers directly (be careful, though!), but a template designer should
currently delete their test-plans when changing an existing question or
whenever the test-plan errors out.

Better handling of such errors is on the todo-list, ideas welcome.

Give specific people access to the template
===========================================

Once the template is created you can click on **OBJECT PERMISSIONS** in the top
right corner. You'll need the email address the other person uses in
EasyDMP. Paste that into the "User identification" field and click ``Manage user``.

Allow a plan maker to test the template
---------------------------------------

Select ``Can use template`` in the left box and click on the little arrow to
the right, then click "Save", below.

Add another designer to the template
------------------------------------

Select everything in the left box before clicking the little arrow to the
right, and then "Save", below.

Give everyone access to the template
====================================

The moment you set a date in the ``published``-field on the ``Template``
itself, the template is publically accessible. Do not do this before the
template is completely finished!

**Do not alter the template after ``published`` is set!** If you need to make
a new version of a template that is in use, select it in the list of templates
in the admin (box on the left), select "Create new version" and click the
button that says "Go". This will create a new version. Versions after the first
one will have their version number visible everywhere.
