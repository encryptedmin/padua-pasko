from django import forms

from .models import Event


class EventSettingsForm(forms.ModelForm):
    class Meta:
        model = Event
        fields = ("title", "year", "budget_text", "party_date")
        widgets = {"party_date": forms.DateInput(attrs={"type": "date"})}
