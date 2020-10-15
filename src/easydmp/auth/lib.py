from django.contrib.auth import login

from easydmp.eventlog.utils import log_event


def su_login(request, user):
    original_user = request.user
    switch_to_user = user
    exit_users_pk = request.session.get("exit_users_pk", default=[])
    if exit_users_pk:
        template = '{timestamp} {actor} impersonated {target}'
        verb = 'impersonate'
    else:
        template = '{timestamp} {actor} stopped impersonating {target}'
        verb = 'stop impersonating'
    log_event(request.user, 'impersonate', target=user, template='')
    login(request, user)
