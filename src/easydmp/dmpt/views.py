from django.shortcuts import render


def test(request):
    template_name = 'easydmp/dmpt/test.html'
    return render(request, template_name)
