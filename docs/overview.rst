========
Overview
========

EasyDMP's main design goal is to be easy to use for researchers
writing a data management plan, based on a template.

The researcher answers a series of questions by choosing among
a limited set of possible answers, and has space for notes for
each answer. An HTML file suitable for importing into document
processing tools is generated from the answers, as well as
a JSON-dump, for export to other types of tools.

Questions have a type, depending on the expected type of answer.
For instance, Yes vs. No, a date range, one or more choices of
a short set of hand-written predefined choices, one or more
choices from an auto-generated large set of choices, one or more
urls. Each question also has a position, in order to be able to
show them in the correct order. Some question types can lead to
branching, for instance if a dataset not sensitive, questions
regarding how to safe guard the data can be skipped.

Whenever it makes sense, an answer is translated to a "canned
answer", for instance a "Yes" to "Does this dataset contain
sensitive data" can be converted to "This dataset does contain
sensitive data." For other question types, the answer can be put
inside a framing text. A question "When will the data be
collected?", which is answered with the date range 2017-2020, can
be converted to "The data will be collected between 2017 and
2020".

Every template has one or more designers. It is the designers'
task to write the canned answers and framing texts so that the
text in the generated HTML makes sense. It is the responsibilty of
the researchers making plans to assure that any text written in
free text fields, like "Notes", makes sense together with the
canned answers.
