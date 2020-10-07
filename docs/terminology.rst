===========
Terminology
===========

Some terms, alphabetized.

.. glossary::

   branching section
       A section where which questions are available to be answered depends on
       what questions have already been answered.

   editor
       A person that controls a plan. May invite others to edit, or to view the
       plan.

   invitation
       When an editor wants to allow others to edit or view their plans, they can
       make an invitation. The invitation is done by sending an email with
       a magical link. On visiting that link and clicking on the button there,
       access to the plan is granted.

   linear section
       A section without any branches (except for a magical one if the section is
       also optional.)

       Every question is on_trunk.

   on_branch question
       A question that *may* never bee seen or contemplated by an editor, because
       it may be hidden in a different branch.

   on_trunk question
       A question that *must* be contemplated for a plan to be validi, unless it
       is in an optional section. It may be optional.

       The first question (and any optional section question) of a section is
       always on_trunk.

   optional question
       A question that need not be answered.

       If it is not answered it will still count towards that plan being valid.

   optional section
       A section that is designed to be optional and need not be answered.

       It has a magical toggle question, that if answered with "No" will skip that
       section.

       If it is not answered it will still count towards that plan being valid.

   optional section question
       An optional section's magical toggle question. It has two possible
       answers, "Yes", and "No". Answering "No" will skip the section.

       It is the first question of a sections's questions and have a magical
       position of "0". It will be automatically created when a section is
       designated as "optional".

   plan
       A named collection of question-answer pairs according to some template, and
       some metadata.

       A plan is valid if its answers as checked against its template are valid.

   question
       A question that may be answered in a plan. A question has a type. Can be
       optional. Can have multiple answers of the same type. Questions are ordered.

   required question
       The opposite of an optional question, this is the default. These nust
       always be answered if not hidden by a branch.

       Marked with a red dot after the question text itself.

   section
       A named collection of a subset of a template's questions. Can be nested.
       Can be optional. Can be branching or linear. Need not have any questions
       itself but just serve as structural support. Sections are ordered.

       A section is valid if their questions' answers are valid.

   required section
       The opposite of an optional section. A section that must be seen and whose
       questions must be answered. This is the default.

   skipped section
       An optional section that has been skipped by a plan having answered it with
       "No".

       Skipped sections are automatically valid.

   template
       A named collection of questions that a plan seeks to answer. Consists of
       one or more sections.

      Templates are valid if the answers to the questions in their sections are
      valid.

   template designer
       A person that may dersign a template for editors to use.

   toggle question
       See "optional section question".

   viewer
       A person that has read-only access to the plan.
