=======
Testing
=======

Testing locally is done by ``tox``.

You can install ``tox`` and its helpers from the requirements-file
``requirements/testing.txt``::

    pip install -r requirements/testing.txt

Just runnning ``tox`` will run the tests for the production version of EasyDMP,
and generate an HTML coverage report. Access the report via
``htmlcov/index.html``.
