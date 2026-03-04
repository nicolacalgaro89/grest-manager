# grestmanager/forms.py
from django import forms
from .models import Person

class PersonForm(forms.ModelForm):
    class Meta:
        model = Person
        fields = ['name', 'surname', 'birth_date', 'tax_code']
        widgets = {
            'birth_date': forms.DateInput(attrs={'type': 'date'}),
        }