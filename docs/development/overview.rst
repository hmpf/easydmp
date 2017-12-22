# set tw: 72

====================
Developer's overview
====================

A bird's eye view
=================

.. _figure_birds_eye_overview:
.. figure:: ../images/overview.*

   Figure 1: Bird's eye view

Legend
------

Arrow with single arrow-head: read only, points towards reader Arrow
with two arrow-heads: read-write

The **DB** is a PostGreSQL database that stores all state: questions,
answers, templates, plans, FSAs and users.

The **Model** is an ORM that wraps the tables in the **DB** and holds
the business logic.

**Web** is the web-interface generated from the **Model** where template
designers create and edit templates and planners create and edit plans
based on a preexisting template.

**API** is currently very rudimentary and is only a read-only view of
most of the data in **Model**. Services who wishes to import data from
EasyDMP should look here.

**EEStore** is an external, separate, micro-service that wraps,
combines, simplifies and normalizes the data of several external
services, like Re3Data and Cristin. The  **Model** fetches data from the
**EEStore** in order to generate drop downs and multiselect lists.

**Auth** is an OAuth2-client. Several OAuth2 IdP's can be in use
simultaneously.


Workflow
========

.. _figure_model:
.. figure:: ../images/model.*

   Figure 2: Inside the model

Templates
---------

A template designer creates a plan template in the web interface.
A template consists of some metadata and one or more sections. Each
section consist of one or more questions, and each question has a type,
a position, and is optionally part of an Finite State Automaton (FSA).

The sections can be reordered within a template, and the questions can
be reordered within each section. The actual order of questions is also
affected by any FSAs that questions are connected to.

The currently supported types are:

* Boolean
* Positive integer
* Text field
* Daterange
* Choice (choose one of a short list of predefined choices)
* Multi choice (choose one or more of a short list of predefined choices)
* Single url + name/description
* Multiple pairs of urls with name/description
* External choice (choose one of a long list fetched from the EEStore)
* External multi choice (choose one or more of a long list fetched from
  the EEStore)

The "Boolean" and "Choice"-types can branch, that is: which question is
the next may depend on a specific answer. Such questions are part of an
FSA, and their answers gives the keys to lookup the correct edge between
two nodes. If there is no FSA, the next question is decided by position,
higher position is asked later.

Plans
-----

When planners create a plan, they answer each question in order, and the
question-id and actual answer is stored in the plan. Each question-type
then has logic to pretty-print the value of their answers, the so-called
"canned answer". The "canned answers" are used to generate a text that
is suitable for a paper-based application process, be it for funding or
etther resources.

In order to output the generated the text, the answers in the plan are
run through a *flow*, a serialized traversal of a directed acyclic graph
(DAG). By running the flow through an FSA the answers are mapped to
canned responses, building up to a text that appears to be hand written.
This is then suitable for being attached, in paper form if need be, to
a project proposal.

The questions are not all nodes in the same FSA, as that proved to make
template design quite unwieldy. Instead, only questions that lead to
a branch and the questions that take part in the branches are part of
the same FSA. Also, an FSA might only connect two questions that are in
the same section. The goal is to have a winding road with the occasional
shortcut, not a tree.

For simplicity's sake, each question has its own page with its own url,
so it is very easy to revisit a specific question.

.. todo::
    A template, a section and a specific FSA can all be copied to be
    reused in a different template, section or FSA. Templates are
    versioned, and the system handles multiple templates
    simultaneously. A specific plan is made from a specific versioned
    template, and each plan is also versioned.

