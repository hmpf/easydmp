from django import template


register = template.Library()


@register.filter
def may_edit_plan(user, plan):
    return plan.may_edit(user)


@register.filter
def may_view_plan(user, plan):
    return plan.may_view(user)
