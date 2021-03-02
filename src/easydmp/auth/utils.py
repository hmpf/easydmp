from guardian.shortcuts import assign_perm

from easydmp.lib import get_model_name


__all__ = [
    'generate_default_permission_strings',
    'set_user_object_permissions',
]


def generate_default_permission_strings(model_name):
    perms = []
    for perm in ('add', 'change', 'delete', 'view'):
        perms.append('{}_{}'.format(perm, model_name))
    return perms


def set_user_object_permissions(user, obj, extra_perms=()):
    if user.has_superpowers:
        return
    default_permissions = generate_default_permission_strings(
        get_model_name(obj)
    )
    permissions = default_permissions + list(extra_perms)
    for perm in permissions:
        assign_perm(perm, user, obj)
