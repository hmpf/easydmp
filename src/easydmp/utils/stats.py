from datetime import timedelta

from django.utils.timezone import now as tznow

from easydmp.auth.models import User
from easydmp.plan.models import Plan


__all__ = [
    'stats',
]


def _get_user_email_domains(user_qs):
    emails = user_qs.filter(email__contains='@').values_list('email', flat=True)
    domains = set([email.rsplit('@', 1)[1] for email in emails])
    return domains


def stats():
    """
    Collect some statistics about plans and users
    """
    all_users = User.objects.all()
    all_plans = Plan.objects.all()

    now = tznow()
    last_30days = now - timedelta(days=30)
    last_30days_users = User.objects.filter(date_joined__gte=last_30days)
    last_30days_plans = User.objects.filter(date_joined__gte=last_30days)

    return {
        'users': {
            'all': all_users.count(),
            'last_30days': last_30days_users.count(),
        },
        'plans': {
            'all': all_plans.count(),
            'last_30days': last_30days_plans.count(),
        },
        'domains': {
            'all': len(_get_user_email_domains(all_users)),
            'last_30days': len(_get_user_email_domains(last_30days_users)),
        },
    }
