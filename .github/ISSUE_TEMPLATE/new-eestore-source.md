---
name: New EEStore source
about: Document what's needed for developing a new eestore source
title: ''
labels: eestorecache
assignees: ''

---

# Who wants this source?

# Relevant endpoints

Fill in below:

List all entries:
Specific entry:
Paging: yes/no/unknown

# Format/API-type

XML, JSON or something completely different? REST, SOAP, Graph-ql or something else?

# Authentication

Describe whether an account/auth is necessary to use the endpoint, and what type of auth it is: token, jwt, basic auth, saml...

# Links to relevant API documentation

# Field-mapping

Type(s): which type(s) does the source sort under?

Fields that eestore needs:

* remote_pid, official pid for the record. Optional.
* remote_id, id used to look up the record (ought to be the same as remote_pid but isn't necessarily so). Optional.
* name, often called `title` or name in remotes. Required
* uri, the best link available, if any is available. Optional.
* last_fetched, date when the record was last updated. Optional.
