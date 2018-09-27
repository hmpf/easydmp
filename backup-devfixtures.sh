#!/bin/bash

python manage.py dumpdata --natural-foreign --natural-primary --exclude=auth.Permission --format=json --indent=2 easydmp_auth auth dmpt eestore
