========
Overview
========

EasyDMP's main design goal is to be easy to use for researchers
writing a data management plan, based on a template.

The data planner answers a series of questions by choosing among
a limited set of possible answers, and has space for notes for
each answer. The template designer adapting an existing set of
questions therefore needs to rewrite the questions to facilitate
this, and needs to design the canned responses carefully.

The answers the planners make to the question are stored as
a *flow*, a serialized traversal of a directed acyclic graph
(DAG). By running the flow through a finite state machine (FSM)
the answers are mapped to canned responses, building up to a text
that appears to be hand written. This is then suitable for being
attached, in paper form if need be, to a project proposal.

Each question is connected to its own FSM. Each FSM is part of
a section, and each section is part of a template. The sections
can be reordered and the FSMs can be reordered within each
section.

A template, a section and a specific FSM can all be copied to be
reused in a different template, section or FSM. Templates are
versioned, and the system handles multiple templates
simultaneously. A specific plan is made from a specific versioned
template, and each plan is also versioned.

.. _figure_birds_eye_overview:
.. figure:: images/easydmp-overview.*

   Figure 1: Bird's eye view

