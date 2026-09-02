from django.db import models
from django.contrib.auth.models import  User 
from django.conf import settings
from django.utils import timezone
from django.core.exceptions import ValidationError
from decimal import Decimal

# Create your models here.



#
# creation de la class pharmacie pour chaque user puisse affiche les nom des sa pharmacie
class Pharmacie(models.Model):
    nom_pharmacie = models.CharField(max_length= 30)
    user_pharmacie = models.ForeignKey(User , on_delete= models.SET_NULL , null = True , blank= True) 
    dateCreation = models.DateField(auto_now_add= True)


    def __str__(self):
        return self.nom_pharmacie

#
#
# creation de la type de role 
class TypeRole(models.Model):
    nom_typeRole = models.CharField(max_length= 40)

    def __str__(self):
        return self.nom_typeRole

#
#
# creation de role dans le systeme 
class Role(models.Model):
    role = models.ForeignKey(TypeRole , on_delete= models.SET_NULL, null= True , blank= True, verbose_name= 'roleType')
    userRole = models.ForeignKey(User , on_delete= models.SET_NULL, verbose_name= 'userRole', null= True)
    pharmacie = models.ForeignKey(Pharmacie , on_delete= models.SET_NULL, verbose_name= 'pharmacieRole', null= True ) 
    statut = models.CharField(max_length=10, default='active') 

    
    def __str__(self):
        return self.statut

#
#
# taux d'echange pour chaque pharmacie
class TauxChange(models.Model):
    pharmacie = models.OneToOneField(
        Pharmacie, 
        on_delete=models.CASCADE, 
        related_name='taux_change',
        verbose_name='Pharmacie'
    )
    taux_usd_cdf = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        verbose_name='Taux USD vers CDF',
        help_text='Ex: 1 USD = 2500 CDF'
    )
    date_mise_a_jour = models.DateTimeField(auto_now=True)
    utilisateur = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True,
        verbose_name='Utilisateur ayant défini le taux'
    )
    est_actif = models.BooleanField(default=True, verbose_name='Taux actif')
    
    class Meta:
        verbose_name = 'Taux de change'
        verbose_name_plural = 'Taux de change'
        ordering = ['-date_mise_a_jour']
        constraints = [
            models.UniqueConstraint(
                fields=['pharmacie', 'est_actif'],
                condition=models.Q(est_actif=True),
                name='unique_taux_actif_par_pharmacie'
            )
        ]
    
    def __str__(self):
        return f"{self.pharmacie.nom_pharmacie} - 1 USD = {self.taux_usd_cdf} CDF"
    

#
# medicament 

class Medicament(models.Model):

    class Devise(models.TextChoices):
        CDF = 'CDF', 'Franc Congolais'
        USD = 'USD', 'Dollar Américain'

    class FormePharmaceutique(models.TextChoices):
        COMPRIME = 'COMPRIME', 'Comprimé'
        GELULE = 'GELULE', 'Gélule'
        SIROP = 'SIROP', 'Sirop'
        INJECTABLE = 'INJECTABLE', 'Injectable'
        POMMADE = 'POMMADE', 'Pommade'
        SUPPOSITOIRE = 'SUPPOSITOIRE', 'Suppositoire'
        POUDRE = 'POUDRE', 'Poudre'
        AUTRE = 'AUTRE', 'Autre'

    class CategorieMedicament(models.TextChoices):
        ANTIBIOTIQUE = 'ANTIBIOTIQUE', 'Antibiotique'
        ANTALGIQUE = 'ANTALGIQUE', 'Antalgique/Douleur'
        ANTIPALUDEEN = 'ANTIPALUDEEN', 'Antipaludéen'
        ANTIINFLAMMATOIRE = 'ANTIINFLAMMATOIRE', 'Anti-inflammatoire'
        ANTIFONGIQUE = 'ANTIFONGIQUE', 'Antifongique'
        VITAMINE = 'VITAMINE', 'Vitamine/Complément'
        ANTIHYPERTENSEUR = 'ANTIHYPERTENSEUR', 'Antihypertenseur'
        AUTRE = 'AUTRE', 'Autre'

    # Relations
    pharmacie = models.ForeignKey(
        'Pharmacie',
        on_delete=models.CASCADE,
        related_name='medicaments'
    )
    utilisateur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='medicaments_enregistres'
    )

    # Identification
    nom = models.CharField(max_length=255)
    forme = models.CharField(
        max_length=20,
        choices=FormePharmaceutique.choices,
        default=FormePharmaceutique.COMPRIME
    )
    categorie = models.CharField(
        max_length=30,
        choices=CategorieMedicament.choices,
        default=CategorieMedicament.AUTRE
    )
    dosage = models.CharField(
        max_length=50,
        blank=True, null=True,
        help_text="Ex: 500mg, 250mg/5ml"
    )
    fabricant = models.CharField(max_length=255, blank=True, null=True)
    description = models.TextField(blank=True, null=True)

    # Devise et gestion des cartons
    devise = models.CharField(
        max_length=3,
        choices=Devise.choices,
        default=Devise.CDF,
        help_text="Devise dans laquelle les prix ci-dessous sont exprimés"
    )
    quantite_par_carton = models.PositiveIntegerField(
        help_text="Nombre de pièces contenues dans un carton"
    )
    prix_achat_carton = models.DecimalField(
        max_digits=12, decimal_places=2,
        help_text="Prix d'achat d'un carton entier"
    )
    prix_vente_piece = models.DecimalField(
        max_digits=12, decimal_places=2,
        help_text="Prix de vente d'une seule pièce"
    )

    # Métadonnées
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('pharmacie', 'nom', 'dosage')
        ordering = ['nom']
        verbose_name = "Médicament"
        verbose_name_plural = "Médicaments"

    def __str__(self):
        return f"{self.nom} {self.dosage or ''} - {self.get_forme_display()} ({self.pharmacie.nom_pharmacie})"

    @property
    def prix_achat_piece(self):
        if self.quantite_par_carton:
            return self.prix_achat_carton / self.quantite_par_carton
        return 0


# ==============================================================================
# ==============================================================================
# Gestion d'approvisionnement des medicaments 
class Stock(models.Model):
    # ---------------------------------------------------------
    # Relations
    # ---------------------------------------------------------
    medicament = models.ForeignKey(
        'Medicament',
        on_delete=models.CASCADE,
        related_name='stocks'
    )

    pharmacie = models.ForeignKey(
        'Pharmacie',
        on_delete=models.CASCADE,
        related_name='stocks'
    )

    utilisateur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='stocks_enregistres'
    )

    # ---------------------------------------------------------
    # Identification du lot
    # ---------------------------------------------------------
    numero_lot = models.CharField(
        max_length=100,
        help_text=(
            "Le numéro de lot doit être unique dans cette pharmacie."
        )
    )

    date_peremption = models.DateField()

    date_achat = models.DateField(
        auto_now_add=True
    )

    # ---------------------------------------------------------
    # Quantités
    # ---------------------------------------------------------
    nombre_cartons = models.PositiveIntegerField(
        help_text="Nombre de cartons achetés lors de cette livraison"
    )

    quantite_piece = models.PositiveIntegerField(
        editable=False,
        help_text=(
            "Calculé automatiquement : nombre_cartons × "
            "quantite_par_carton du médicament"
        )
    )

    quantite_restante = models.PositiveIntegerField(
        editable=False,
        help_text=(
            "Stock encore disponible pour ce lot "
            "(diminue à chaque vente)"
        )
    )

    # ---------------------------------------------------------
    # Prix archivés au moment de l'approvisionnement
    # ---------------------------------------------------------
    devise = models.CharField(
        max_length=3,
        choices=[
            ('CDF', 'Franc Congolais'),
            ('USD', 'Dollar Américain'),
        ],
        default='CDF'
    )

    prix_achat_carton = models.DecimalField(
        max_digits=12,
        decimal_places=2
    )

    prix_vente_piece = models.DecimalField(
        max_digits=12,
        decimal_places=2
    )

    # ---------------------------------------------------------
    # Configuration modèle
    # ---------------------------------------------------------
    class Meta:
        ordering = ['date_peremption']
        verbose_name = "Stock"
        verbose_name_plural = "Stocks"

        constraints = [
            models.UniqueConstraint(
                fields=[
                    'pharmacie',
                    'numero_lot',
                ],
                name='unique_numero_lot_par_pharmacie',
                violation_error_message=(
                    "Ce numéro de lot existe déjà dans cette pharmacie."
                )
            )
        ]

    # ---------------------------------------------------------
    # Affichage
    # ---------------------------------------------------------
    def __str__(self):
        return (
            f"{self.medicament.nom} - "
            f"Lot {self.numero_lot} "
            f"({self.quantite_restante} pièces) - "
            f"{self.pharmacie.nom_pharmacie}"
        )

    # ---------------------------------------------------------
    # Validation métier
    # ---------------------------------------------------------
    def clean(self):
        super().clean()

        # Le médicament sélectionné doit appartenir à la pharmacie
        # affectée au stock.
        if self.medicament_id and self.pharmacie_id:
            if self.medicament.pharmacie_id != self.pharmacie_id:
                raise ValidationError(
                    "Ce médicament n'appartient pas à cette pharmacie."
                )

        # Vérifie le lot avant la sauvegarde pour fournir une erreur
        # lisible dans les formulaires Django.
        if self.pharmacie_id and self.numero_lot:
            lot_existe = Stock.objects.filter(
                pharmacie_id=self.pharmacie_id,
                numero_lot__iexact=self.numero_lot.strip()
            )

            # Important pour une future page de modification :
            # le lot en cours ne doit pas être comparé avec lui-même.
            if self.pk:
                lot_existe = lot_existe.exclude(pk=self.pk)

            if lot_existe.exists():
                raise ValidationError({
                    'numero_lot': (
                        "Ce numéro de lot existe déjà dans cette pharmacie."
                    )
                })

        # Vérification additionnelle : la péremption doit être future.
        if (
            self.date_peremption and
            self.date_peremption <= timezone.localdate()
        ):
            raise ValidationError({
                'date_peremption': (
                    "La date de péremption doit être postérieure à aujourd'hui."
                )
            })

    # ---------------------------------------------------------
    # Enregistrement, calculs automatiques et traçabilité
    # ---------------------------------------------------------
    def save(self, *args, **kwargs):
        is_new = not self.pk

        if is_new:
            # La pharmacie du stock est toujours celle du médicament.
            # Même si une valeur différente est envoyée depuis un formulaire,
            # le modèle impose la pharmacie correcte.
            self.pharmacie = self.medicament.pharmacie

            # Prix et devise archivés lors de l'approvisionnement.
            self.devise = self.medicament.devise
            self.prix_achat_carton = self.medicament.prix_achat_carton
            self.prix_vente_piece = self.medicament.prix_vente_piece

            # Quantité totale reçue pour ce lot.
            self.quantite_piece = (
                self.nombre_cartons *
                self.medicament.quantite_par_carton
            )

            # À la création, tout le lot est disponible.
            self.quantite_restante = self.quantite_piece

        super().save(*args, **kwargs)

        # Trace automatiquement l'entrée en stock dans MouvementStock,
        # uniquement à la création (pas lors d'une modification future).
        if is_new:
            MouvementStock.objects.create(
                stock=self,
                medicament=self.medicament,
                pharmacie=self.pharmacie,
                utilisateur=self.utilisateur,
                type_mouvement=MouvementStock.TypeMouvement.ENTREE,
                quantite=self.quantite_piece,
                quantite_avant=0,
                quantite_apres=self.quantite_restante,
                motif=f"Approvisionnement lot {self.numero_lot}"
            )

    # ---------------------------------------------------------
    # Propriétés de calcul
    # ---------------------------------------------------------
    @property
    def valeur_totale_achat(self):
        return self.nombre_cartons * self.prix_achat_carton

    @property
    def valeur_totale_vente_potentielle(self):
        return self.quantite_restante * self.prix_vente_piece

    @property
    def est_perime(self):
        return self.date_peremption < timezone.localdate()

    @property
    def prix_achat_piece(self):
        if self.medicament.quantite_par_carton:
            return (
                self.prix_achat_carton /
                self.medicament.quantite_par_carton
            )

        return Decimal('0.00')

    @property
    def quantite_sortie(self):
        """
        Nombre total de pièces sorties ou vendues depuis la création du lot.
        """
        return self.quantite_piece - self.quantite_restante

    @property
    def pourcentage_restant(self):
        """
        Pourcentage de stock restant dans ce lot.
        """
        if self.quantite_piece > 0:
            return (
                Decimal(self.quantite_restante) * Decimal('100')
            ) / Decimal(self.quantite_piece)

        return Decimal('0.00')

# ===================================================================================
# ===================================================================================
class MouvementStock(models.Model):

    class TypeMouvement(models.TextChoices):
        ENTREE = 'ENTREE', 'Entrée (approvisionnement)'
        VENTE = 'VENTE', 'Sortie (vente)'
        AJUSTEMENT = 'AJUSTEMENT', 'Ajustement manuel'
        PEREMPTION = 'PEREMPTION', 'Retrait pour péremption'
        PERTE = 'PERTE', 'Perte / casse'

    # Relations
    stock = models.ForeignKey(
        'Stock',
        on_delete=models.CASCADE,
        related_name='mouvements',
        help_text="Lot concerné par ce mouvement"
    )
    medicament = models.ForeignKey(
        'Medicament',
        on_delete=models.CASCADE,
        related_name='mouvements'
    )
    pharmacie = models.ForeignKey(
        'Pharmacie',
        on_delete=models.CASCADE,
        related_name='mouvements'
    )
    utilisateur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='mouvements_enregistres'
    )

    # Détails du mouvement
    type_mouvement = models.CharField(
        max_length=20,
        choices=TypeMouvement.choices
    )
    quantite = models.PositiveIntegerField(
        help_text="Quantité de pièces concernées par ce mouvement"
    )
    quantite_avant = models.PositiveIntegerField(
        editable=False,
        help_text="quantite_restante du lot avant ce mouvement"
    )
    quantite_apres = models.PositiveIntegerField(
        editable=False,
        help_text="quantite_restante du lot après ce mouvement"
    )
    motif = models.CharField(
        max_length=255,
        blank=True, null=True,
        help_text="Ex: numéro de vente, raison de l'ajustement..."
    )

    date_mouvement = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date_mouvement']
        verbose_name = "Mouvement de stock"
        verbose_name_plural = "Mouvements de stock"

    def __str__(self):
        return (
            f"{self.get_type_mouvement_display()} - "
            f"{self.medicament.nom} ({self.quantite} pièces) - "
            f"{self.date_mouvement.strftime('%d/%m/%Y %H:%M')}"
        )