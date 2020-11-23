===========================
Authenticating with the API
===========================

To use the non-public API endpoints it is necessary to either be
logged in (by reusing the session cookie) or utilize a token.

There are two kinds of tokens available: Bearer tokens and JSON
Web Tokens (JWT).

The former is meant for one-off CLI-work by people, while the
latter is better suited for automation and software agents.

Authenticating with bearer token
================================

There is no verification or refreshing of bearer tokens. They work
until they are deleted.

Get the token
-------------

Superusers
..........

Get/create a token via the admin or the management-command
``drf_create_token``.

Regular users
.............

Ask a superuser for a token, for instance via asking support for
your specific instance.

Use the token
-------------

Add the header ``Authorization: Bearer YOUR_TOKEN`` to all
requests, where YOUR_TOKEN is the token you got from the previous
step.

Authenticating with JWT
=======================

For JWT you need a non-SSO password, because you fetch the token
by logging in.

Get a password
--------------

Superusers
..........

If you are a superuser or can easily become superuser (for instance by
running your own instance), you can set this password via the admin.

Regular users
.............

There is no automated way to set a password for regular users, as who’s
authorized to get the extra access to the API hasn’t been specified yet.

Currently, ask support for your specific instance to set a password for
you if you need the access.

(One possible way would be applying for API access in the user profile,
which then would have to be accepted by an administrator.)

Getting the token
-----------------

When you have a password, get the token at
``/api/v1/jwt/authenticate/``. This token is what you will need to
store in your client.

Logging in
----------

After having the token, log in at ``/api/v1/jwt/authenticate/``.
Afterwards you should have access to the private API.

Verifying the token
-------------------

POST the token into ``api/v1/jwt/verify/``.

Refresh the token
-----------------

POST the token into ``/api/v1/jwt/refresh/``.
