==============================
Logging in to the API with JWT
==============================

Getting the token
=================

You need to have a separate password to use the non-public bits of the
API.

Getting the password
--------------------

Superusers
..........

If you are a superuser or can easily become superuser (for instance by
running your own instance), you can set this password via the admin.

Regular users
.............

There is no automated way to set a password for regular users, as who’s
authorized to get the extra access to the API hasn’t been specified yet.
One possible way would be applying for API access in the user profile,
which then would have to be accepted by an administrator.

Currently, ask support for your specific instance to set a password for
you if you need the access.

.. _getting-the-token-1:

Getting the token
-----------------

When you have a password, get the token at
``/api/v1/jwt/authenticate/``. The token is what you will need to store
in your client.

Logging in
==========

After having the token, log in at ``/api/v1/jwt/authenticate/``.
Afterwards you should have access to the private API.

Verifying the token
===================

POST your token into ``api/v1/jwt/verify/``.

Refresh your token
==================

POST your token into ``/api/v1/jwt/refresh/``.
