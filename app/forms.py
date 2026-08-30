from django import forms
from django.contrib.auth.models import User 
from .models import * 




## ====================================================================
## ====================================================================
class LoginForm(forms.Form):
    username = forms.CharField(max_length = 30, widget= forms.TextInput(attrs={'class': 'form-control'}))
    password = forms.CharField(max_length=200 , widget = forms.PasswordInput(attrs={'class': 'form-control'}))


#
# ===========================================================================================
# enregistrement de taux d'echange 
class TauxChangeForm(forms.ModelForm):
    class Meta:
        model = TauxChange
        fields = ['taux_usd_cdf', 'est_actif']
        widgets = {
            'taux_usd_cdf': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'placeholder': 'Ex: 2500.00',
            }),
            'est_actif': forms.CheckboxInput(attrs={
                'class': 'form-check-input',
            }),
        }
        labels = {
            'taux_usd_cdf': 'Taux USD vers CDF',
            'est_actif': 'Taux actif',
        }

    def clean_taux_usd_cdf(self):
        taux = self.cleaned_data.get('taux_usd_cdf')
        if taux is not None and taux <= 0:
            raise forms.ValidationError('Le taux doit être supérieur à zéro.')
        return taux