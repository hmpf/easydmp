=========
CHANGELOG
=========

This project adheres to `Semantic Versioning
<https://semver.org/spec/v2.0.0.html>`_) as of v0.10. Prior to v0.10,
named tags per feature, named tag plus date per feature or commit
hashes were used.

Unreleased
----------

* Optional/non-required questions. These are, if obligatory, always seen but
  need not be answered.
* Multiple questions on a single page, for sections without branches.
* Logging of events.
* Comments for plans.
* Usage of JWT for access to non-public parts of the API.
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

* Easy and not so easy speed optimizations. It used to take up
  to 10 seconds to go to the next question. Now it takes less than
  1 second.
* Quality if life changes to allow for easier on-boarding of new developers.

2018, first half
----------------

* Work on another branching template for H2020.
* New look and many UI-improvements for end users.
* Most templates made private.

2017-09-08
----------

* The big rename. Officially forked off from sigma-dmp, and the code was
  cleaned up and moved to a publically visible git repository.
* Large deployment changes. All deployment-specific code was moved to
  a separate repository to facilitate multiple deployment options.

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
