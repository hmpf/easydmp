=========
CHANGELOG
=========

This project adheres to `Semantic Versioning
<https://semver.org/spec/v2.0.0.html>`_) as of v0.10. Prior to
v0.10, named tags per feature, named tag plus date per feature or
commit hashes were used.

Unreleased
----------

* Logging of events.
* Comments for plans.

Next
----

* Set a question-type specific css class on every question widget
* Prevent Makefile from exiting with an error
* Added CONTRIBUTORS.txt and CONTRIBUTING.rst
* Remove the TemplateAccess model, which was replaced by django-guardian ages
  ago.
* Truncate long section titles in section progress bar

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
