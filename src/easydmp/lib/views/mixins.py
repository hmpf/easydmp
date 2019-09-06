from django.views.generic.edit import FormMixin

from ..forms import DeleteForm


class DeleteFormMixin(FormMixin):
    # FormMixin needed in order to use a proper form in the
    # confirmation step. A DeleteView just needs a POST.
    form_class = DeleteForm
