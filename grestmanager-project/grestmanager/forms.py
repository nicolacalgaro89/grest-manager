# grestmanager/forms.py
from django import forms
from .models import Person, Subscription, Event

class PersonForm(forms.ModelForm):
    class Meta:
        model = Person
        fields = ['name', 'surname', 'birth_date', 'tax_code']
        widgets = {
            'birth_date': forms.DateInput(attrs={'type': 'date'}),
        }


# I 16 flag di partecipazione, raggruppati per settimana (riusati anche nei template)
PARTICIPATION_FIELDS = [
    f"week{week}_{segment}"
    for week in range(1, 5)
    for segment in ("morning", "lunch", "afternoon", "trip")
]


class SubscriptionForm(forms.ModelForm):
    class Meta:
        model = Subscription
        fields = ["to_event"] + PARTICIPATION_FIELDS

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Nel menù a tendina solo gli eventi attivi
        self.fields["to_event"].queryset = Event.objects.filter(active=True)
        self.fields["to_event"].widget.attrs["class"] = "form-select"
        # Stile Bootstrap per i checkbox di partecipazione
        for name in PARTICIPATION_FIELDS:
            self.fields[name].widget.attrs["class"] = "form-check-input"