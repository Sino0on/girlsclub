from django import forms

from .models import Order


class OrderForm(forms.ModelForm):
    quantity = forms.IntegerField(
        label="Количество билетов",
        min_value=1,
        max_value=10,
        initial=1,
        widget=forms.NumberInput(attrs={"inputmode": "numeric"}),
    )
    rules_agreed = forms.BooleanField(
        label="Я ознакомлен(а) с правилами мероприятия",
        required=True,
        error_messages={"required": "Нужно подтвердить, что вы ознакомлены с правилами."},
        widget=forms.CheckboxInput(attrs={"class": "agree__input"}),
    )

    class Meta:
        model = Order
        fields = ["full_name", "email", "phone", "quantity", "rules_agreed"]
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


class ReceiptUploadForm(forms.ModelForm):
    receipt = forms.FileField(
        label="Скриншот или файл чека",
        required=True,
        error_messages={"required": "Прикрепите скриншот или файл с чеком об оплате."},
    )

    class Meta:
        model = Order
        fields = ["receipt"]
