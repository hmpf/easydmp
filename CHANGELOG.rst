=========
CHANGELOG
=========

This project adheres to `Semantic Versioning <https://semver.org/spec/v2.0.0.html>`_)
as of v0.10. Prior to v0.10, annotated tags per feature, annotated tags plus
date per feature, or commit hashes were used.

Planned
-------

* Repeated sections
* Better support for exporting to RDA DMP Common Standard

Unreleased
----------

1.9.3
-----

Another bugfix release

Bugfixes:

* Optional section questions are now not reorderable but stays at position 0
* In the continuing saga of "validate branching sections correctly"...

  * Paths passed around are now always tuples of ints
  * The if-monster in ``AnswerSet.validate_data()`` is replaced by the light
    early-return structure of ``Section.validate_data()``

* Get rid of a 404: When going from a linear section to a branching section,
  the answerset is now passed in

1.9.2
-----

Teeny tiny bugfix release

Bugfixes:

* Cloning was broken for plans due to a bug in Answer.clone()
* Clicking on anything in the progress bar no longer leads to a 404

Paperwork:

* Synchronize the User table schema with upstream

1.9.1
-----

Obligatory big release "oops"

1.9.0
-----

This release has very little that has visibly changed for the end users but
there are some enormous incompatible changes in the database. DO NOT FORGET TO
MIGRATE and take a backup before you do.

The migrations are numerous and heavy. They have been optimized for speed, but
they might take a while.

This release is the biggest, scariest, step in supporting repeatable sections,
that means that a section can be answered more than once.

Incompatible changes:

* Stop storing answers on Plan.data/Plan.previous_data, store them on the
  AnswerSet instead. The fields still exist but will be dropped in a future
  release.

Big new features:

* Move answers to AnswerSets, with all the needed reshuffling of validation
  logic, storage logic and traversal logic that implies.

Small new features:

* Allow setting a section as "repeatable" in the admin. This is for testing and
  does not effect anything yet.
* Hide the "Edit all"-link where it is pointless

Bugfixes:

* Validation for branching sections works better
* AnswerSets are now cloned correctly

Paperwork:

* Switch to Django's non-postgres specific JSONField-implementation
* Drop support for Django 2.2

1.8.1
-----

Admin bugfix/QoL improvements release

- Fix bug that prevented the creation of new sections
- Made section cloning information read only
- Made questions auto-increment position on first save, just like sections and
  canned answers

1.8.0
-----

See UPGRADING.rst.

Incompatible changes:

* JWT: Due to supporting the new Django LTS (3.2) it was necessary to upgrade
  the jwt library used by the API. However, the existing JWT library did not
  support the new LTS, so it was necessary to switch to a newer, still
  developed fork. This fork has a slightly different API and has its own way of
  doing masquerading. The existing, non-documented masquerading endpoint
  ``authorize`` has been dropped.

Big new features:

* Much easier to reorder sections, questions, canned answers in a template,
  both in admin and manually. It is now no longer possible to set position
  directly. A valid position is generated for you on first save.
* Sections now nest properly. Nesting (via the ``section_depth`` and
  ``super_section`` attributes) was once upon a time added in order to organize
  the branching H2020 template. Reordering them via admin was very clunky, and
  the uniqueness constraint that ensured each section had a unique position per
  *template* was removed to make it easier. The admin UI for reordering has now
  been improved enough that the constraint can be reintroduced.

Bugfixes:

* Prevent server error on unauthorized access to pdf

Paperwork:

* Improve how the validity checkmark is done. Now it is CSS-styleable.
* Log a "cannot ever happen" bug that nevertheless has happened
* Official support for Django 3.2 LTS. This will be the last minor version to
  support Django 2.2.

1.7.0
-----

Small new features:

* Template Designers can import templates
* Templates can now be locked (made read only) in addition to published (made
  public).
* Allow HTML in Question.comment, Question.help_text, Section.comment,
  Section.introductory_text

Bugfixes:

* Trying to access a link to a plan containing a non-existing plan id or
  question id will now always end up with a "404 Not Found" instead of
  sometimes a "500 Server Error".
* Also clone import metadata when cloning a template

Paperwork:

* Support running on Django 3.1 and prepare for running on Django 3.2

1.6.0
-----

Small new features:

* Template Designers can now make new versions of their templates as well as
  making private copies of them.
* Published templates are readonly in the admin for *everyone*
* The batch plan export CLI script is updated due to end user feedback: instead
  of exporting every single plan it can be limited to plans of a specific
  template, as well as only validated plans.
* Change how setup of a new site is done, + devfixtures

  There's now a separate management command for loading a fresh database with
  standardized data, ``setup``.

Bugfixes:

* Regression: It was not possible to add/change Section.label or Question.label
  in the admin. Thx, frafra!
* Importing templates using the EEStore didn't work due to overzealous
  validation

Paperwork:

* Hopefully the final needed database change for supporting repeatable sections
* The plan export script now uses ``argparse``, for more detailed help.
* A new management command ``resetmigrationhistory`` to empty the
  ``django_migrations``-table so that ``--fake --fake-initial`` can be run,
  that does not involve manually typing in SQL commands. Only run when all
  migrations are up to date.

Do remember to run ``migrate``.

1.5.0
-----

Big new features:

* Export of templates, via CLI, admin, API
* Import of templates, via CLI, admin

Small new features:

* CLI script to batch export plans to PDF

Paperwork:

* New way to update/freeze dependencies
* Final step of JSONField-conversion: Remove traces of squashed migrations
* New management command to ease development of support for RDA DMP CS

1.4.2
-----
PDF support in plan export.

1.4.1
-----

Step two of the JSONField-conversion that started in the previous
version was done now. The final will happen no later than 1.5.0.

The migration plan.0006_link_answer_to_answerset does not like
some databases. It can time out if that happens, blocking the
other migrations. If this holds for you, see UPGRADING.rst

1.4.0
-----

New features:

* Add API authentication by token
* Export Plan to PDF

Bugfixes:

* Fix bug due to url arg now being int, not str

On the way to better export to RDA DMP CS:

* Rename SectionValidity to AnswerSet and QuestionValidity to Answer, in
  preparation for repeated sections.

Prepping for upgrade of Django:

* Mark tests that need JSONField support
* Change NullBooleanField to BooleanField(null=True)
* Use contrib.postgres JSONField instead of 3rd party field
* Replace url() with path()

Cleanup:

* Remove the model PlanComment (never in use)

Developer QoL:

* Read logging config from separate file
* Add file to control codecov
* Greatly improve the sphinx docs

1.3.3
-----

* Tons of fixes to the test and test-system
* Make plan data searchable in DRF (will run a migration)
* Prepare API for v2
* Use `drf-spectacular` for OpenAPI support

1.3.2
-----

* Fix typo during refactor
* Fix bug caused by mypy

1.3.1
-----

* Fix various bugs in optional sectons
* Add some type hints to tricky bits. This will help with making setions
  repeatable but does *not* mean that we will aim for everything typed.

  Common setup is added to "setup.cfg". Override with "mypi.ini" and
  ".mypi.ini", which are in .gitignore.
* Add support for toggleable pagination, turn on with query param `page_size`
* Remove last vestiges of old flow-app
* Refactor Plan, especially validation. This is the first step in adding
  repeatable sections.
* Move the remains of easydmp.utils to easydmp.lib
* Update devfixtures.json for v1.3.0
* Remove final traces of cached section graphs

1.3.0
-----

New: Add support for optional sections

1.2.9
-----

* Run tests on github for a shiny, shiny badge
* Allow running flake8 from tox
* Fix thinko in plan list api

1.2.8
-----

* Rename Question.obligatory to Question.on_trunk

1.2.7
-----

* Plan list in API will not filter on published field

1.2.6
-----

* Plan serializer was missing the validation-fields
* Make it easier to override just the password for a database, in settings
* Bugfix

1.2.5
-----

* Layout improvements

1.2.4
-----

* Wherever answers can be entered, show the section introductory text by default
* Stop making irrelevant answers in Plan.data from leading to a validation error
* Fix bug in validation when clicking "Check" in the UI

1.2.3
-----

* Improve the widget for storage forecast

1.2.2
-----

* Fix bug in section graph rendering in the api, affecting the admin

1.2.1
-----

* Fix a bug when navigating through a template with both branching and linear
  sections.
* Stop caching section graphs on disc, generate them realtime instead

1.2.0
-----

* Adds a new question type for storage forecast


1.1.3
-----

* Improve the generated html
* Update devfixtures to not mention the old flow


1.1.2
-----

* Improves on earlier bugfix.

1.1.1
-----

* Fixes a bug where the application crashes when navigating forward to next page.

1.1.0
-----

* Add a way to show questions in the generated text, not just the answers and
  notes. Toggled by a field on the template.
* Make the template API up to date with newer template fields
* Add the url to the generated html to the plan API

1.0.2
-----

* Bugfix of 1.0.1

1.0.1
-----

* First step of removing the old branching system: remove code, delete tables.

1.0.0
-----

First version using the new branching system

See UPGRADING.rst!

0.25.0
------

Last version using the old branching system

* Remove upgrade-commands needed for the last important upgrade, going from
  0.20.1 to 0.21. (Probably should have been removed in 0.22.)
* Search for users in eventlog (admin)
* Fix for a bug in Question formsets

0.24.1
------

* Improve plan API: add search, improve filtering
* Improve looks for formsets
* Improve looks for sinle section templates

0.24.0
------

* Two new question types: date and multirdacostonetext, developed during the
  May 2020 virtual RDA hackathon
* Sundry fixes and dependency updates

0.23.2
------

* Fix bug with missing methid on BooleanQuestion after refactor
* Use Python 3.8 due to cached_property

0.23.1
------

Maintenance release

* Fix bug due to incompatibility with Django 2.1 that affected invitations
* Upstream auth.User has changed so alter our own copy likewise
* New CLI-command for seeing rough plan question usage statitstics: which plans
  have answered which questions
* Various code cleanup, e.g. fixing code broken and/or missing after rebase
* Switch to running on Django 2.2 and prep for running on 3.x

0.23.0
------

* Add support for exporting to RDA DMP Common Standard. This necessitated
  adding one more piece of personal data: the full name of persons involved
  with a plan. For this reason the privacy policy has been updated as well,
  and it has been moved from the database to code for easier versioning.

0.22.3
------

* Fix the docker-compose setup to work on a newer OS with newer postgres image
* Improve miscellanea about optional questions. Validation, show in admin, show
  in gv graphs.
* Switch to run on Django 2.2

0.22.2
------

* Amend the previous patch so that superusers can choose whether to see all
  plans in existance in the personal plan list or not.

0.22.1
------

* Allow superusers access to all plans in end user web ui
* Fix a problem when working on templates with subsections

0.22.0
------

* Fix an annoyance with the layout/whitespace between the page header and page
  contents.
* Show a plan's title and version in the page title, for bookmarks etc.
* Bugfixes galore: When cloning (saving a plan under a new name, or unlocking)
  section validities and editors were created twice, which ran into
  a unique-constraint. This also hid a typo in the event logging, and an error
  with incrementing the version number when unlocking.
* Make it so that Plan.modified only updates on explicit alterations by
  a human, not when batch-processing fixes.
* Improve the API for dmpt models: show template and newer fields on Question,
  allow search and filtering on Template, Section, Question and CannedAnswer.
* Upgrade lots of dependencies and allow testing on newer Djangos

0.21.5
------

* Bugfix: Unpinned dependency was incompatible with Django 1.11

0.21.4
------

* Show some statistics on the public front page

0.21.3
------

* Stop a long title from leaking into the next row of plans in the plan list

0.21.2
------

* Push out some stable code to lock it in ahead of the big, scary branching
  change. Small releases are a good thing. Nothing in this release should
  change anything visible to the end users.

0.21.1
------

* Bugfix in the old branching system, prevent invalid ``Edge``'s from breaking
  the flow calculator.

0.21.0
------

* Change BooleanQuestion to store "Yes"/"No" instead of True/False

See UPGRADING.rst!

0.20.1
------

* Fix to 0.20.0

See UPGRADING.rst!

0.20.0
------

* Do second and last step of database migration cleanup

See UPGRADING.rst!

0.19.9
------

* Do first step of database migration cleanup

See UPGRADING.rst!

0.19.8
------

* Various bugfixes
* Squash migrations ahead of branching changeover

0.19.7
------

* Update outdated devfixtures

0.19.6
------

* Fix error in new template-chooser if attempting to access deleted template
* Improve the dmpt admin:

  * Filter questions on EEStore mounts
  * Add method to copy a template
* Pull in newer versions of some dependencies for security reasons
* Improve cloning for templates: store a reference to the original version

0.19.5
------

* Add explicit LICENSE.txt
* Freeze version of django-select2, the newest doesn't work on Django 1.11
* Improve testing, by adding fixture-generators among other things
* Adjust UI of template chooser a little
* Prevent showing template version twice in the generated text

0.19.4
------

* Improve and document testing
* Bugfix in SectionDetailView, affected H2020-plans

0.19.3
------

* Fix bug with exports not rendering properly. Has been here since 0.19.0.

0.19.2
------

* Show the version of templates, if there are multiple versions
* Use ISO 8601-ish formatting for dates and times throughout
* Fix bug with logging in some cases of saving a plan

0.19.1
------

* Fix bug in validating optional questions

0.19.0
------

* Set a question-type specific css class on every question widget
* Prevent Makefile from exiting with an error
* Added CONTRIBUTORS.txt and CONTRIBUTING.rst
* Remove the TemplateAccess model, which was replaced by django-guardian ages
  ago.
* Truncate long section titles in section progress bar
* Major change: Replace "Publish" plan with "Lock" plan. A locked plan is not
  accessible to the public, and can be unlocked to create a new version.
* Remove "Create new plan" from header in UI
* New feature: Add rudimentary support for setting CORS headers for API-access
* Add "Help"-link to help-page in header
* Replace the privacy policy with a locally hosted one
* Add more metadata for templates
* Choose template before creating a plan, not during
* Logging of some events

0.18.0
------

* New question type: ShortFreetext. A single line of text suitable for titles
  and names
* Fix for validations of plans not being saved when clicking "Check" in the UI

0.17.1
------

* Fixed broken listing of plans in API for authenticated users
* Show username in header
* Find users by date_joined in admin

0.17.0
------

* New feature: cache generated section graphs and make them available from the
  admin and from an API endpoint.

0.16.1
------

* Removed duplicate in requirements (confuses pip)

0.16.0
------

* Add docs about template design
* New feature: optional questions, need not be answered if shown
* Fixed some infelicities on the section update page
* Reverted an admin feature that can't work in production as is (review graph)

0.15.0
------

* Add link to user guide in footer
* Add docs on flow visualization
* Various css fixes and typo fixes
* Various cleanups, code style
* New feature: view flow for a section from the admin
* New feature: Make a new version of a template from the admin


0.14.6
------

* Document and update devfixtures.json
* Fix bug that made next/page buttons on linear sections (multiple
  questions per page) behave differently from branching sections
  (single question per page).
* Use python 3.7 and nonbinary psycopg2 in the Docker image
* Sundry bugfixes
* Add some template metadata

  * Differ between generic and domain specific templates
  * Store a description for each template

0.14.5
------

* Switch to a newer JSONField implementation
* Save validities in bulk, avoid multiple expensive UPSERTs
* Fix Heisenbug that made saving questions work differently on
  different instances:

  * Use Python 3.7 due to ordered dicts
  * Ensure all question keys stored in plans are strings, since
    json converts ints to strings and, dependsing on
    implementation, may allow duplicate keys.

  Different JSON libraries treat duplicate keys differently.
  Python's json picks the last key if there are duplicates, and
  with python 3.7, the last key is always the newest key.

0.14.4
------

* Support Python 3.7
* Remove some unused code
* Improve UX in template admin, add search
* Always pull in debug toolbar
* Log question saving to ease debugging
* Make plan save lighter and speedier
* Improve UI for multi question pages

0.14.3
------

* Better solution to the solution in 0.14.2
* Upgrade many dependencies
* Record what dependencies work together

0.14.2
------

* Lock down more versions of (sub-)dependencies

0.14.1
------

* Bugfix, failing filter-lookup in admin

0.14.0
------

* New feature: allow selected users to create templates. If a user
  is in the group "Template Designer", and is_staff is True, that
  user gains access to a stripped down Django admin to create and
  edit their own templates. They can use their own unfinished
  templates for making plans as well.
* Remove the separate CannedAnswer entry from the admin

0.13.4
------

* Yet another bugfix to multiple questions on a single page
* Bugfix to template deletion
* Fix ordering of canned answers
* Fix Sigma2-logo (remote url was 404)

0.13.3
------

* Make a start on simplifying the CSS and the HTML structure
* Add a customized 500 error page

0.13.2
------

* Show current plan in header when known

0.13.1
------

* Bugfixes to 0.13.0

0.13.0
------

* Multiple questions on a single page, for sections without branches.

0.12.3
------

* Bugfixes: relating to the viewer role after 0.12.1
* Bugfixes: relating to what pages should be public after 0.12.1
* Added a themed 400 Not Found page.

0.12.2
------

* Add links to EUDAT's T0S and Privacy Policy in the footer.

0.12.1
------

* Bugfix: Users were not redirected to the login page when
  accessing a plan anonymously but got a 500 server error instead.
* Bugfix: Not all the necessary authentication backends were in use.
* Other small fixes.

0.12
----

2018-10-18

* Backend-support for logging of events
* Usage of JWT for access to non-public parts of the API.
* Switch from homebrew auth system for templates to django-guardian.
  Eventually switch to use django-guardian wherever convenient.
* Start of changelog.

v0.11.1
-------

2018-09-26

* Support for docker-compose to ease development. This includes
  fixtures to fill the database with the relevant user types
  (superuser, ordinary user) and a sample template. This isn't
  end-user relevant or run-time bug prone so is relegated to
  a patch-version.


0.11
----

2018-09-21

* New feature: A very rudimentary system for giving people usage
  access to unpublished templates, for ease of cooperative
  development of new templates.

0.10
----

2018-09-14

* First version using semantic versioning
* New user role for plans: view only. This necessitated an
  overhaul of the invitation system

2018, early September
---------------------

* Easy and not so easy speed optimizations. It used to take up to
  10 seconds to go to the next question. Now it takes less than
  1 second.
* Quality if life changes to allow for easier on-boarding of new
  developers.

2018, first half
----------------

* Work on another branching template for H2020.
* New look and many UI-improvements for end users.
* Most templates made private.

2017-09-08
----------

* The big rename. Officially forked off from sigma-dmp, and the
  code was cleaned up and moved to a publically visible git
  repository.
* Large deployment changes. All deployment-specific code was moved
  to a separate repository to facilitate multiple deployment
  options.

2017, second half
-----------------

* Support for multiple templates, and better UI for making
  templates (superuser only).
* Work on making a branching template for H2020 and the additional
  form-support needed.
* Creation of the EEStore, which gathers publically accessible
  data from various repositories via APIs, normalizes that data
  and provides an API to access the result. Useful for creating
  drop-down lists.
* Support for using data from external APIs via the EEStore.
* Email-based system for inviting other users to edit a plan.
* Upgrade from python 2.7 to python 3.
* Upgrade to Django 1.11.
* Read-only API.

2016
----

* Proof of concept named "sigma-dmp" with a single, branching,
  hard coded template. Eventually the questions and flow was
  stored in a database so that it would not be necessary to make
  a new deployment for every change of wording in a question.
* Start of FSA-backed form-generator.
* Support branching on boolean questions.
