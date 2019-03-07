#!/bin/bash -xe

export SECRET_KEY=$SECRET_KEY

python3 manage.py collectstatic --noinput
python3 manage.py migrate --noinput
python3 manage.py cache_graphs -F -A
gunicorn --log-level debug --access-logfile - easydmp.site.wsgi -b 0.0.0.0:8000
