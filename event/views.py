from django.shortcuts import render

from .models import FAQItem, Partner, ProgramItem


def home(request):
    return render(
        request,
        "event/home.html",
        {
            "faqs": FAQItem.objects.filter(is_active=True),
            "program": ProgramItem.objects.filter(is_active=True),
            "partners": Partner.objects.filter(is_active=True),
        },
    )
