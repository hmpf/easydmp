# set tw: 72

=================
Release checklist
=================

#. Ensure that the commit message of any commit that changes the
   database starts with "Migrate:". Rebase if necessary.
#. If there is any commit that migrates anything in the ``dmpt``-app,
   migrate the change to a database which has the example templates
   loaded, export the templates and include them in a commit.
#. Rebase branches that are to be included on master, and merge them
   with ``--no-ff``. Strive to avoid octopus merges.
#. Ensure we're on the master branch.
#. Update the version number in ``src/easydmp/__init__.py`` and
   ``CHANGELOG.rst``. Everywhere else needing the version number should
   try fetching it ``from src/easydmp/__init__.py``.
#. Write something sensible in ``CHANGELOG.rst``. The summary for the
   changelog can be copied and adjusted from ::

        $ git log --format="* %B" <previous version tag>..HEAD

   Full details can be had via ``git log``, so strive for readability and
   highlights in the changelog.
#. Commit the changelog and ``src/easydmp/__init__.py``.
   The commit message should be "Bump version to {version}".
#. Tag that commit with "v{version}" and add a brief summary of the
   changes as the tag message. (Thus making an annotated tag.)
#. Push the code and tag to the official repo
