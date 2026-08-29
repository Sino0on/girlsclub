from django.shortcuts import render

from .models import FAQItem


def home(request):
    faqs = FAQItem.objects.filter(is_active=True)
    return render(request, "event/home.html", {"faqs": faqs})
