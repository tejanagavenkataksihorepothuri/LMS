from django import forms
from .models import Holiday
from django.core.exceptions import ValidationError
from django.utils import timezone

class HolidayForm(forms.ModelForm):
    date = forms.DateField(
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )
    name = forms.CharField(
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter holiday name'
        })
    )
    description = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'placeholder': 'Enter holiday description (optional)',
            'rows': 3
        })
    )

    class Meta:
        model = Holiday
        fields = ['name', 'date', 'description']

    def clean_date(self):
        date = self.cleaned_data.get('date')
        if date:
            if date < timezone.now().date():
                raise ValidationError("Holiday date cannot be in the past")
            if Holiday.objects.filter(date=date).exists():
                raise ValidationError("A holiday already exists on this date")
        return date