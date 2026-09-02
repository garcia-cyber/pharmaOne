from django import forms
from django.contrib.auth.models import User 
from .models import * 
from django.utils import timezone



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

# ========================================================================
# ========================================================================
class MedicamentForm(forms.ModelForm):
    class Meta:
        model = Medicament
        fields = [
            'nom',
            'forme',
            'categorie',
            'dosage',
            'fabricant',
            'description',
            'devise',
            'quantite_par_carton',
            'prix_achat_carton',
            'prix_vente_piece',
        ]
        # pharmacie et utilisateur sont exclus du formulaire :
        # ils seront assignés automatiquement dans la vue (request.user)

        widgets = {
            'nom': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ex: Amoxicilline'
            }),
            'forme': forms.Select(attrs={
                'class': 'form-select'
            }),
            'categorie': forms.Select(attrs={
                'class': 'form-select'
            }),
            'dosage': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ex: 500mg'
            }),
            'fabricant': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ex: Laboratoire XYZ'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Description ou notes complémentaires (facultatif)'
            }),
            'devise': forms.Select(attrs={
                'class': 'form-select'
            }),
            'quantite_par_carton': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ex: 5',
                'min': 1
            }),
            'prix_achat_carton': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ex: 2000',
                'step': '0.01',
                'min': 0
            }),
            'prix_vente_piece': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ex: 1000',
                'step': '0.01',
                'min': 0
            }),
        }

    def clean_quantite_par_carton(self):
        quantite = self.cleaned_data.get('quantite_par_carton')
        if quantite is not None and quantite <= 0:
            raise forms.ValidationError("La quantité par carton doit être supérieure à 0.")
        return quantite

    def clean_prix_achat_carton(self):
        prix = self.cleaned_data.get('prix_achat_carton')
        if prix is not None and prix <= 0:
            raise forms.ValidationError("Le prix d'achat doit être supérieur à 0.")
        return prix

    def clean_prix_vente_piece(self):
        prix = self.cleaned_data.get('prix_vente_piece')
        if prix is not None and prix <= 0:
            raise forms.ValidationError("Le prix de vente doit être supérieur à 0.")
        return prix

    def clean(self):
        cleaned_data = super().clean()
        prix_achat_carton = cleaned_data.get('prix_achat_carton')
        quantite_par_carton = cleaned_data.get('quantite_par_carton')
        prix_vente_piece = cleaned_data.get('prix_vente_piece')
        devise = cleaned_data.get('devise')

        if prix_achat_carton and quantite_par_carton and prix_vente_piece:
            prix_achat_piece = prix_achat_carton / quantite_par_carton
            if prix_vente_piece <= prix_achat_piece:
                raise forms.ValidationError(
                    f"Attention : le prix de vente ({prix_vente_piece} {devise}) est inférieur ou égal "
                    f"au prix d'achat par pièce ({prix_achat_piece:.2f} {devise}). Vérifiez vos montants."
                )
        return cleaned_data


# ================================================================
# ================================================================
class StockForm(forms.ModelForm):
    class Meta:
        model = Stock

        fields = [
            'medicament',
            'numero_lot',
            'date_peremption',
            'nombre_cartons',
        ]

        widgets = {
            'medicament': forms.Select(attrs={
                'class': 'form-select',
            }),

            'numero_lot': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ex : LOT-2026-001',
            }),

            'date_peremption': forms.DateInput(
                format='%Y-%m-%d',
                attrs={
                    'class': 'form-control',
                    'type': 'date',
                }
            ),

            'nombre_cartons': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 1,
                'placeholder': 'Ex : 10',
            }),
        }

        labels = {
            'medicament': 'Médicament',
            'numero_lot': 'Numéro de lot',
            'date_peremption': 'Date de péremption',
            'nombre_cartons': 'Nombre de cartons',
        }

    def __init__(self, *args, **kwargs):
        # IMPORTANT :
        # On retire "user" de kwargs AVANT super().
        # Sinon BaseModelForm reçoit un argument qu'il ne reconnaît pas.
        self.user = kwargs.pop('user', None)

        super().__init__(*args, **kwargs)

        self.pharmacie = None

        # Récupère la pharmacie dont le user connecté est propriétaire.
        if self.user and self.user.is_authenticated:
            self.pharmacie = (
                Pharmacie.objects
                .filter(user_pharmacie=self.user)
                .first()
            )

        # L'utilisateur ne voit que les médicaments de sa pharmacie.
        if self.pharmacie:
            self.fields['medicament'].queryset = (
                self.pharmacie.medicaments
                .all()
                .order_by('nom', 'dosage')
            )
        else:
            # Aucune pharmacie = aucune possibilité de sélectionner un médicament.
            self.fields['medicament'].queryset = (
                self.fields['medicament'].queryset.none()
            )

    def clean(self):
        cleaned_data = super().clean()

        medicament = cleaned_data.get('medicament')
        date_peremption = cleaned_data.get('date_peremption')
        nombre_cartons = cleaned_data.get('nombre_cartons')

        if not self.user or not self.user.is_authenticated:
            raise ValidationError(
                "Vous devez être connecté pour enregistrer un stock."
            )

        if not self.pharmacie:
            raise ValidationError(
                "Vous devez d'abord créer votre pharmacie."
            )

        # Sécurité : le médicament doit appartenir à la pharmacie du user.
        if medicament and medicament.pharmacie_id != self.pharmacie.id:
            self.add_error(
                'medicament',
                "Ce médicament n'appartient pas à votre pharmacie."
            )

        # Évite l'enregistrement d'un lot déjà expiré.
        if date_peremption and date_peremption <= timezone.localdate():
            self.add_error(
                'date_peremption',
                "La date de péremption doit être postérieure à aujourd'hui."
            )

        # Cette validation est normalement déjà couverte par PositiveIntegerField,
        # mais elle donne un message plus clair.
        if nombre_cartons is not None and nombre_cartons <= 0:
            self.add_error(
                'nombre_cartons',
                "Le nombre de cartons doit être supérieur à zéro."
            )

        return cleaned_data

    def save(self, commit=True):
        stock = super().save(commit=False)

        # Données non modifiables depuis le formulaire HTML.
        stock.pharmacie = self.pharmacie
        stock.utilisateur = self.user

        if commit:
            stock.save()

        return stock

# ====================================================================
# ====================================================================
# MODIFICATION DU STOCK 
class StockModificationForm(forms.ModelForm):
    class Meta:
        model = Stock

        fields = [
            "numero_lot",
            "date_peremption",
            "prix_vente_piece",
        ]

        widgets = {
            "numero_lot": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Ex : LOT-2026-001",
            }),

            "date_peremption": forms.DateInput(
                format="%Y-%m-%d",
                attrs={
                    "class": "form-control",
                    "type": "date",
                }
            ),

            "prix_vente_piece": forms.NumberInput(attrs={
                "class": "form-control",
                "min": "0",
                "step": "0.01",
                "placeholder": "Prix de vente par pièce",
            }),
        }

        labels = {
            "numero_lot": "Numéro de lot",
            "date_peremption": "Date de péremption",
            "prix_vente_piece": "Prix de vente par pièce",
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)

        super().__init__(*args, **kwargs)

    def clean_numero_lot(self):
        numero_lot = self.cleaned_data["numero_lot"].strip()

        # Numéro de lot unique dans la pharmacie actuelle.
        lot_existe = Stock.objects.filter(
            pharmacie=self.instance.pharmacie,
            numero_lot__iexact=numero_lot
        ).exclude(pk=self.instance.pk)

        if lot_existe.exists():
            raise ValidationError(
                "Ce numéro de lot existe déjà dans votre pharmacie."
            )

        return numero_lot

    def clean_date_peremption(self):
        date_peremption = self.cleaned_data["date_peremption"]

        if date_peremption <= timezone.localdate():
            raise ValidationError(
                "La date de péremption doit être postérieure à aujourd'hui."
            )

        return date_peremption

    def clean_prix_vente_piece(self):
        prix_vente_piece = self.cleaned_data["prix_vente_piece"]

        if prix_vente_piece < 0:
            raise ValidationError(
                "Le prix de vente ne peut pas être négatif."
            )

        return prix_vente_piece
