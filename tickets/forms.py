from django import forms

from .models import Order


class OrderForm(forms.ModelForm):
    rules_agreed = forms.BooleanField(
        label="Я ознакомлен(а) с правилами мероприятия",
        required=True,
        error_messages={"required": "Нужно подтвердить, что вы ознакомлены с правилами."},
        widget=forms.CheckboxInput(attrs={"class": "agree__input"}),
    )

    class Meta:
        model = Order
        fields = ["full_name", "email", "phone", "rules_agreed"]
        labels = {
            "full_name": "ФИО",
            "email": "Email",
            "phone": "Телефон",
        }
        widgets = {
            "full_name": forms.TextInput(attrs={"placeholder": "Иванова Айгуль"}),
            "email": forms.EmailInput(attrs={"placeholder": "you@example.com"}),
            "phone": forms.TextInput(attrs={"placeholder": "+996 700 000 000"}),
        }
