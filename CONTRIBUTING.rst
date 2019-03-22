=======================
Contributing to EasyDMP
=======================

If you want to contribute to the code of EasyDMP, you have come to the right
place.

See the README for the technical details on how to set up an environment to
play in, this document is about how to get your changes into the master-branch.

Reporting bugs
==============

First of all, is your bug really a security issue? If you can

* access something that's not yours, or something you shouldn't have access to
* disable something for other people

Then you have a security issue, not a bug. Send those in an email to
support@easydmp.sigma2.no.

Otherwise, you might have a bug.

Bugs in production
------------------

A prodction website will have have an email address for you to use to report
problems.

If you get a 500 error when using a production website, you need to send an
email to that address.

In the email, you need to

* tell us your username (an email address) so we can look through the logs
* paste in the url where the bug happened
* tell us what you tried to do
* tell us what you expected to happen

If it was not a 500-error, you might want to also attach a screenshot.

Bugs in development
-------------------

If you're finding bugs while developing, make an issue here.

At a minimum, you need to enclose the url (without domain), for instance
``/plan/``. The goal of your bug report is to make it possible for the rest of
us to trigger the same bug in our own environments, so double check that the
data in your database makes sense since we won't have your copy of the
database.

Making feature requests
=======================

Feature requests should be made in the issue-system here.

There are three types of feature request:

1. improvements to the production websites
2. improvements to the production api
3. anything else

With the first two, you need to enclose the url(s) involved. If it's a looks
issue, also enclose screenshots. A shot of before and after is great!

Contributing code
=================

Fork the code, make a new branch. Add the name that git puts in your git
commits to the end of the CONTRIBUTORS.txt file together with the email address
you used to commit with. You can get all the email addresses you have used by
running::

    git shortlog -sne

Make a pull request. If you want early feedback on some idea you're having
that's far from ready, prefix the pull request with "WIP:" and the branch name
with "wip-". If you think it is ready to merge, push a new branch that doesn't
start with "wip-".

Branches are cheap!

Getting your code accepted
--------------------------

* Strive for PEP8.
* 4 space indents are not negotiable.
* Code should be 7bit ASCII or UTF8.
* We recommend running flake8 to check your code, pylint is too noisy. As for
  line lengths, try to stay below 100 characters.
* Rebase on master early, rebase on master often.
* Whitespace-only changes happens in a separate commit.
* Update the changelog
* Make sensible commit-messages
* Break long lines like so::

    sensiblevariablename = longfunctionormethodname(
        parameter1=bla,
        parameter2=bla2,
        extra_long_parameter_deluxe=something,
    )

* If you need to break a dot-do-dot long line, do it like so::

    qs = (ModelName.objects
        .filter(something_or_other=blah)
        .exclude(status=something)
        .order_by('some_field'))

Branch names should be in 7 bit ascii, not be too long, and not contain names.

Feel free to use `Black <https://black.readthedocs.io/en/stable/>`_ to reformat
your own, fresh code. Target: py37. The only disagreements we have with black
is string quoting (we use ``"`` for text that will be read by humans and ``'``
for everything else, like string dictionary keys; how to write hexadecimal
numbers, where we prefer all lowercase; and we don't do whitespace around slice
``:``, since we fail to see why we should change a more than 20 year old
ingrained habit.

The changelog
.............

Add your change under the heading "Next", which goes after "Unreleased" and
before the latest verson. If it's a bugfix, just call it that, and be brief. If
it's a feature, describe it a little more. If there already is a heading
"Next", append your message to the bottom of that section so that early changes
goes before later changes.

It's fine to make a new commit with just the changelog changes. The message
should then be just "Update changelog".

On a new release, the text in the changelog may be adjusted quite a bit.

The commit message
..................

The following holds for the first line of the commit message:

* It is a summary and thus needs be short: strive for a maximum of 50 bytes.
* It should *not* end in a period.
* No names of persons should be included.
* No emoji should be used.
* No need to waste space on "the" and "a" if the summary makes sense without
  it.
* Do not start a summary with "Do not..", as that breaks the next rule. Use
  a proper verb instead, like "avoid", "stop" or "prevent".
* It should be a continuation of the following sentence: "(If this commit is
  accepted,) this commit will.."
  Examples:

    * "Ensure only valid plans can be published"
    * "Show all templates for superuser"

* Exception to the previous rule: Add "Migrate: " at the start if it is
  necessary to run ``python manage.py migrate`` to update the database.
  The rest of the line still needs to work with the "This will.."-template.

  ::

      "Migrate: Add a an index for performance reasons"

Additional context may follow the commit-summary, for instance referencing
a specific issue number or a pull request. No emoji, no names of
persons, no lines longer than 79 bytes.

For some existing examples, use ``git log``.

This is what you do instead of force-pushing
--------------------------------------------

First close the existing pull request, with the comment "Force-pushing new
version". Make a new branch with the branch name of the previous branch plus
a dash and a numbered suffix. If you had "myfinebranch", the new one should be
called "myfinebranch-2". If you need to "force-push again", the new branch will
be "myfinebranch-3" etc.

In the message to the pull request, reference the earlier pull requests. (Copy
in the link to the previous pull-request.)

If you pushed something you shouldn't, like a password, first change the
password everywhere it is used, then if necessary ask (in an issue) for a nuke
of that branch.

Community
=========

This is currently the only place to publicly discuss and work on the code.
