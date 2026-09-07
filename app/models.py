from django.db import models
from django.conf import settings
from django.utils import timezone
from django.core.exceptions import ValidationError
from decimal import Decimal, ROUND_HALF_UP

# Create your models here.



#
# creation de la class pharmacie pour chaque user puisse affiche les nom des sa pharmacie
class Pharmacie(models.Model):
    nom_pharmacie = models.CharField(max_length=30)
    user_pharmacie = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="pharmacies",
    )
    dateCreation = models.DateField(auto_now_add=True)

    class Meta:
        ordering = ["nom_pharmacie"]
        indexes = [
            models.Index(fields=["user_pharmacie"]),
        ]

    def __str__(self):
        return self.nom_pharmacie

#
#
# creation de la type de role 
class TypeRole(models.Model):
    nom_typeRole = models.CharField(max_length=40, unique=True)

    def __str__(self):
        return self.nom_typeRole

#
#
# creation de role dans le systeme 
class Role(models.Model):
    role = models.ForeignKey(
        TypeRole,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="roleType",
    )
    userRole = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        verbose_name="userRole",
        null=True,
        blank=True,
        related_name="roles",
    )
    pharmacie = models.ForeignKey(
        Pharmacie,
        on_delete=models.SET_NULL,
        verbose_name="pharmacieRole",
        null=True,
        blank=True,
        related_name="roles",
    )
    statut = models.CharField(max_length=10, default="active")

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["userRole", "pharmacie", "role"],
                name="unique_role_user_pharmacie_type",
            ),
        ]

    def __str__(self):
        return f"{self.userRole} - {self.role} ({self.statut})"

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
        settings.AUTH_USER_MODEL,
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

    def clean(self):
        super().clean()
        if self.taux_usd_cdf is not None and self.taux_usd_cdf <= Decimal("0.00"):
            raise ValidationError({
                "taux_usd_cdf": "Le taux doit être supérieur à zéro."
            })

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)


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
        constraints = [
            models.UniqueConstraint(
                fields=("pharmacie", "nom", "dosage"),
                name="unique_medicament_pharmacie_nom_dosage",
            ),
            models.CheckConstraint(
                condition=models.Q(quantite_par_carton__gt=0),
                name="medicament_quantite_carton_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(prix_achat_carton__gt=0),
                name="medicament_prix_achat_positif",
            ),
            models.CheckConstraint(
                condition=models.Q(prix_vente_piece__gt=0),
                name="medicament_prix_vente_positif",
            ),
        ]
        ordering = ['nom']
        verbose_name = "Médicament"
        verbose_name_plural = "Médicaments"

    def __str__(self):
        return f"{self.nom} {self.dosage or ''} - {self.get_forme_display()} ({self.pharmacie.nom_pharmacie})"

    def clean(self):
        super().clean()
        if self.nom:
            self.nom = self.nom.strip()
        if self.dosage:
            self.dosage = self.dosage.strip() or None
        if (
            self.quantite_par_carton and
            self.prix_achat_carton is not None and
            self.prix_vente_piece is not None and
            self.prix_vente_piece <= (
                self.prix_achat_carton / self.quantite_par_carton
            )
        ):
            raise ValidationError({
                "prix_vente_piece": (
                    "Le prix de vente doit être supérieur au prix d'achat "
                    "par pièce."
                )
            })

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

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

        if self.numero_lot:
            self.numero_lot = self.numero_lot.strip()

        if self.nombre_cartons is not None and self.nombre_cartons <= 0:
            raise ValidationError({
                "nombre_cartons": "Le nombre de cartons doit être supérieur à zéro."
            })

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
            if not self.medicament_id:
                raise ValidationError(
                    {"medicament": "Un médicament est obligatoire pour le stock."}
                )

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

            # Les champs calculés doivent être cohérents avant l'insertion.
            self.full_clean()

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

    @property
    def jours_avant_peremption(self):
        """
        Nombre de jours restants avant péremption.
        Négatif si déjà périmé (ex: -5 = périmé depuis 5 jours).
        """
        delta = self.date_peremption - timezone.localdate()
        return delta.days

# ===================================================================================
# ===================================================================================
class MouvementStock(models.Model):

    class TypeMouvement(models.TextChoices):
        ENTREE = 'ENTREE', 'Entrée (approvisionnement)'
        VENTE = 'VENTE', 'Sortie (vente)'
        ANNULATION = 'ANNULATION', 'Annulation de vente'
        AJUSTEMENT = 'AJUSTEMENT', 'Ajustement manuel'
        PEREMPTION = 'PEREMPTION', 'Retrait pour péremption'
        PERTE = 'PERTE', 'Perte / casse'
        RETOUR_CLIENT = "RETOUR_CLIENT", "Retour client"

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
        constraints = [
            models.CheckConstraint(
                condition=models.Q(quantite__gt=0),
                name="mouvement_quantite_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(quantite_apres__gte=0),
                name="mouvement_quantite_apres_non_negative",
            ),
        ]

    def __str__(self):
        return (
            f"{self.get_type_mouvement_display()} - "
            f"{self.medicament.nom} ({self.quantite} pièces) - "
            f"{self.date_mouvement.strftime('%d/%m/%Y %H:%M')}"
        )

# ----------------------------------------------------------------------------------------------------
# partie vente et ligne vente 
class Vente(models.Model):

    class StatutVente(models.TextChoices):
        EN_ATTENTE = "EN_ATTENTE", "En attente de paiement"

        PARTIELLEMENT_PAYEE = (
            "PARTIELLEMENT_PAYEE",
            "Partiellement payée"
        )

        PAYEE = "PAYEE", "Payée intégralement"

        ANNULEE = "ANNULEE", "Annulée"

    # =========================================================
    # RELATIONS
    # =========================================================
    pharmacie = models.ForeignKey(
        "Pharmacie",
        on_delete=models.CASCADE,
        related_name="ventes"
    )

    utilisateur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="ventes_enregistrees"
    )

    # =========================================================
    # CLIENT
    # =========================================================
    client_nom = models.CharField(
        max_length=255,
        blank=True,
        null=True
    )

    client_telephone = models.CharField(
        max_length=30,
        blank=True,
        null=True
    )

    # =========================================================
    # DEVISE
    # =========================================================
    devise = models.CharField(
        max_length=3,
        choices=[
            ("CDF", "Franc Congolais"),
            ("USD", "Dollar Américain"),
        ],
        default="CDF"
    )

    # =========================================================
    # STATUT
    # =========================================================
    statut = models.CharField(
        max_length=25,
        choices=StatutVente.choices,
        default=StatutVente.EN_ATTENTE
    )

    date_vente = models.DateTimeField(
        auto_now_add=True
    )

    notes = models.CharField(
        max_length=255,
        blank=True,
        null=True
    )

    class Meta:
        ordering = ["-date_vente"]
        verbose_name = "Vente"
        verbose_name_plural = "Ventes"

    def __str__(self):
        date = self.date_vente.strftime("%d/%m/%Y %H:%M")

        return (
            f"Vente #{self.pk} - "
            f"{self.pharmacie.nom_pharmacie} - "
            f"{date}"
        )

    # =========================================================
    # MONTANT TOTAL APRÈS RETOURS PARTIELS
    # =========================================================
    @property
    def montant_total(self):
        """
        Somme réellement due par le client.

        Le calcul utilise sous_total_net :
        quantité gardée par le client × prix unitaire.

        Exemple :
        Vendu : 4 pièces
        Retourné : 2 pièces
        Client garde : 2 pièces
        """
        return sum(
            (
                ligne.sous_total_net
                for ligne in self.lignes.all()
            ),
            Decimal("0.00")
        )

    # =========================================================
    # MONTANT DÉJÀ PAYÉ
    #
    # Tous les paiements sont déjà convertis dans la devise
    # de la vente avec montant_equivalent_vente.
    # =========================================================
    @property
    def montant_paye(self):
        return sum(
            (
                paiement.montant_equivalent_vente
                for paiement in self.paiements.all()
            ),
            Decimal("0.00")
        )

    # =========================================================
    # RESTE À PAYER
    # =========================================================
    @property
    def montant_restant(self):
        """
        Montant que le client doit encore payer.

        Il ne sera jamais négatif.
        Si le client a payé trop après un retour,
        utilise montant_a_rembourser.
        """
        return max(
            self.montant_total - self.montant_paye,
            Decimal("0.00")
        )

    # =========================================================
    # SOMME À REMBOURSER
    # =========================================================
    @property
    def montant_a_rembourser(self):
        """
        Somme que la pharmacie doit rendre au client
        si le client avait déjà trop payé avant le retour.

        Exemple :
        Total après retour : 10 000 CDF
        Montant payé : 20 000 CDF
        À rembourser : 10 000 CDF
        """
        return max(
            self.montant_paye - self.montant_total,
            Decimal("0.00")
        )

    # =========================================================
    # COÛT ET BÉNÉFICE
    # (remis depuis la version d'origine — supprimés par erreur
    # par Cursor, mais utilisés par les vues de rapport)
    # =========================================================
    @property
    def cout_total(self):
        """
        Somme du coût d'achat de tous les produits réellement
        gardés par le client (hors quantités retournées).
        """
        return sum(
            (
                ligne.cout_total
                for ligne in self.lignes.all()
            ),
            Decimal("0.00")
        )

    @property
    def benefice_total(self):
        """
        Bénéfice brut de la vente = ce que le client doit - le coût.

        Exemple :
        montant_total = 10 000 CDF
        cout_total = 6 000 CDF
        benefice_total = 4 000 CDF
        """
        return self.montant_total - self.cout_total

    @property
    def marge_pourcentage(self):
        """
        Marge en pourcentage du chiffre d'affaires de cette vente.
        """
        if self.montant_total > Decimal("0.00"):
            return (
                self.benefice_total /
                self.montant_total *
                Decimal("100")
            ).quantize(
                Decimal("0.01"),
                rounding=ROUND_HALF_UP
            )
        return Decimal("0.00")

    # =========================================================
    # VENTE SOLDÉE
    # =========================================================
    @property
    def est_soldee(self):
        """
        Une vente est soldée seulement si :
        - il ne reste rien à payer ;
        - la pharmacie ne doit rien rembourser.

        Si le client a payé trop,
        la vente n'est pas complètement réglée tant que
        le remboursement n'est pas traité.
        """
        return (
            self.montant_restant <= Decimal("0.00") and
            self.montant_a_rembourser <= Decimal("0.00")
        )

    # =========================================================
    # MISE À JOUR DU STATUT
    # =========================================================
    def actualiser_statut(self):
        """
        Met à jour le statut après :
        - ajout d'un paiement ;
        - retour partiel ;
        - remboursement futur.
        """
        if self.statut == self.StatutVente.ANNULEE:
            return

        total = self.montant_total
        montant_paye = self.montant_paye
        montant_restant = self.montant_restant
        montant_a_rembourser = self.montant_a_rembourser

        # Si tout le contenu est retourné,
        # laisse la vente visible avec EN_ATTENTE.
        # Tu peux aussi décider de la passer à ANNULEE
        # avec une vue d'annulation complète.
        if total <= Decimal("0.00"):
            nouveau_statut = self.StatutVente.EN_ATTENTE

        # Aucun paiement : le client a encore tout à payer.
        elif montant_paye <= Decimal("0.00"):
            nouveau_statut = self.StatutVente.EN_ATTENTE

        # Client doit encore payer une partie.
        elif montant_restant > Decimal("0.00"):
            nouveau_statut = (
                self.StatutVente.PARTIELLEMENT_PAYEE
            )

        # Le client a trop payé après un retour :
        # on conserve PARTIELLEMENT_PAYEE tant que le
        # remboursement n'est pas encore géré.
        elif montant_a_rembourser > Decimal("0.00"):
            nouveau_statut = (
                self.StatutVente.PARTIELLEMENT_PAYEE
            )

        # Tout est payé exactement et aucun remboursement.
        else:
            nouveau_statut = self.StatutVente.PAYEE

        if self.statut != nouveau_statut:
            self.statut = nouveau_statut

            self.save(
                update_fields=["statut"]
            )

# ======================================================================
# ======================================================================

class LigneVente(models.Model):

    # =========================================================
    # RELATIONS
    # =========================================================
    vente = models.ForeignKey(
        "Vente",
        on_delete=models.CASCADE,
        related_name="lignes"
    )

    medicament = models.ForeignKey(
        "Medicament",
        on_delete=models.PROTECT,
        related_name="lignes_vente"
    )

    stock = models.ForeignKey(
        "Stock",
        on_delete=models.PROTECT,
        related_name="lignes_vente",
        help_text=(
            "Lot précis utilisé pour la vente. "
            "Il est choisi automatiquement avec FEFO."
        )
    )

    # =========================================================
    # QUANTITÉS
    # =========================================================
    quantite = models.PositiveIntegerField(
        help_text="Quantité vendue au client."
    )

    quantite_retournee = models.PositiveIntegerField(
        default=0,
        help_text=(
            "Quantité retournée par le client. "
            "Elle ne peut pas dépasser la quantité vendue."
        )
    )

    # =========================================================
    # PRIX HISTORIQUE
    # =========================================================
    prix_unitaire = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        editable=False,
        help_text=(
            "Prix figé depuis le lot "
            "au moment de la vente."
        )
    )

    class Meta:
        ordering = ["id"]
        verbose_name = "Ligne de vente"
        verbose_name_plural = "Lignes de vente"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(quantite__gt=0),
                name="ligne_vente_quantite_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(quantite_retournee__gte=0),
                name="ligne_vente_retour_non_negative",
            ),
            models.CheckConstraint(
                condition=models.Q(quantite_retournee__lte=models.F("quantite")),
                name="ligne_vente_retour_max_quantite",
            ),
        ]

    def __str__(self):
        return (
            f"{self.medicament.nom} "
            f"{self.medicament.dosage or ''} "
            f"x{self.quantite} "
            f"(retour : {self.quantite_retournee}) "
            f"- Vente #{self.vente_id}"
        )

    # =========================================================
    # QUANTITÉ QUE LE CLIENT GARDE
    # =========================================================
    @property
    def quantite_gardee(self):
        """
        Quantité finale conservée par le client.

        Exemple :
        vendu = 4
        retourné = 2
        gardé = 2
        """
        return max(
            self.quantite - self.quantite_retournee,
            0
        )

    # =========================================================
    # SOUS-TOTAL ORIGINAL
    # =========================================================
    @property
    def sous_total(self):
        """
        Montant initial de la ligne avant retour.
        """
        return self.quantite * self.prix_unitaire

    # =========================================================
    # MONTANT DU RETOUR
    # =========================================================
    @property
    def montant_retourne(self):
        """
        Valeur des produits retournés.

        Exemple :
        2 unités retournées × 5 000 CDF = 10 000 CDF.
        """
        return (
            self.quantite_retournee *
            self.prix_unitaire
        )

    # =========================================================
    # SOUS-TOTAL NET
    # =========================================================
    @property
    def sous_total_net(self):
        """
        Montant réellement dû après retour partiel.

        Exemple :
        vendu = 4
        retourné = 2
        prix = 5 000 CDF
        net = 2 × 5 000 = 10 000 CDF.
        """
        return (
            self.quantite_gardee *
            self.prix_unitaire
        )

    # =========================================================
    # COÛT ET BÉNÉFICE
    # (remis depuis la version d'origine — supprimés par erreur
    # par Cursor, mais utilisés par les vues de rapport)
    # =========================================================
    @property
    def cout_unitaire(self):
        """
        Coût d'achat d'une pièce, hérité du lot (stock) utilisé.
        """
        return self.stock.prix_achat_piece

    @property
    def cout_total(self):
        """
        Coût total pour la quantité réellement gardée par le client.

        Exemple :
        gardé = 2
        coût unitaire = 3 000 CDF
        coût total = 6 000 CDF
        """
        return (
            self.cout_unitaire *
            self.quantite_gardee
        ).quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP
        )

    @property
    def benefice(self):
        """
        Bénéfice net de cette ligne = ce qui est dû - ce que ça a coûté.

        Exemple :
        sous_total_net = 10 000 CDF
        cout_total = 6 000 CDF
        bénéfice = 4 000 CDF
        """
        return (
            self.sous_total_net -
            self.cout_total
        ).quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP
        )

    # =========================================================
    # VALIDATION
    # =========================================================
    def clean(self):
        super().clean()

        if self.quantite is not None and self.quantite <= 0:
            raise ValidationError({
                "quantite": "La quantité vendue doit être supérieure à zéro."
            })

        if (
            self.quantite_retournee is not None and
            self.quantite is not None and
            self.quantite_retournee > self.quantite
        ):
            raise ValidationError({
                "quantite_retournee": (
                    "La quantité retournée ne peut pas dépasser "
                    "la quantité vendue."
                )
            })

        # Une ligne doit avoir un stock et un médicament pour vérifier
        # la cohérence entre le lot, le médicament et la pharmacie.
        if not self.stock_id or not self.medicament_id:
            return

        # Le lot doit correspondre au médicament.
        if self.stock.medicament_id != self.medicament_id:
            raise ValidationError(
                "Le lot ne correspond pas au médicament vendu."
            )

        # Le lot doit appartenir à la même pharmacie.
        if self.vente_id:
            if (
                self.stock.pharmacie_id !=
                self.vente.pharmacie_id
            ):
                raise ValidationError(
                    "Le lot ne provient pas de la pharmacie "
                    "de cette vente."
                )

        # Le lot ne doit pas être périmé au moment
        # où il est choisi pour une nouvelle vente.
        #
        # Cette vérification ne bloque pas les anciennes ventes,
        # car elles utilisent déjà un lot historique.
        if (
            self.pk is None and
            self.stock.est_perime
        ):
            raise ValidationError(
                "Le lot est périmé et ne peut pas être vendu."
            )

    def save(self, *args, **kwargs):
        is_new = self.pk is None

        if is_new:
            if not self.stock_id:
                raise ValidationError(
                    {"stock": "Un lot de stock est obligatoire."}
                )
            if not self.prix_unitaire:
                self.prix_unitaire = self.stock.prix_vente_piece
            self.full_clean()

        return super().save(*args, **kwargs)

# =========================================================================
# =========================================================================
class PaiementVente(models.Model):

    class ModePaiement(models.TextChoices):
        ESPECES = "ESPECES", "Espèces"
        MOBILE_MONEY = "MOBILE_MONEY", "Mobile Money"
        CARTE = "CARTE", "Carte bancaire"
        VIREMENT = "VIREMENT", "Virement bancaire"
        AUTRE = "AUTRE", "Autre"

    class DevisePaiement(models.TextChoices):
        CDF = "CDF", "Franc Congolais"
        USD = "USD", "Dollar Américain"

    # =========================================================
    # RELATIONS
    # =========================================================
    vente = models.ForeignKey(
        "Vente",
        on_delete=models.CASCADE,
        related_name="paiements"
    )

    utilisateur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="paiements_ventes"
    )

    # =========================================================
    # CE QUE LE CLIENT A RÉELLEMENT DONNÉ
    # =========================================================
    montant = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text=(
            "Montant réellement remis par le client "
            "dans la devise de paiement."
        )
    )

    devise_paiement = models.CharField(
        max_length=3,
        choices=DevisePaiement.choices,
        default=DevisePaiement.CDF,
        help_text=(
            "Devise réellement donnée par le client : CDF ou USD."
        )
    )

    # =========================================================
    # HISTORIQUE DE CONVERSION
    # =========================================================
    taux_usd_cdf_applique = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text=(
            "Taux archivé lors du paiement. "
            "Exemple : 1 USD = 2300 CDF."
        )
    )

    montant_equivalent_vente = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        editable=False,
        help_text=(
            "Montant du paiement converti dans la devise "
            "de la vente. Utilisé pour calculer la dette."
        )
    )

    # =========================================================
    # INFORMATIONS COMPLÉMENTAIRES
    # =========================================================
    mode_paiement = models.CharField(
        max_length=20,
        choices=ModePaiement.choices,
        default=ModePaiement.ESPECES
    )

    reference = models.CharField(
        max_length=100,
        blank=True,
        null=True
    )

    note = models.CharField(
        max_length=255,
        blank=True,
        null=True
    )

    date_paiement = models.DateTimeField(
        auto_now_add=True
    )

    class Meta:
        ordering = ["-date_paiement"]
        verbose_name = "Paiement de vente"
        verbose_name_plural = "Paiements de ventes"

        constraints = [
            models.CheckConstraint(
                condition=models.Q(montant__gt=0),
                name="paiement_vente_montant_positif"
            )
        ]

    def __str__(self):
        return (
            f"Paiement {self.montant} {self.devise_paiement} "
            f"pour Vente #{self.vente_id}"
        )

    # =========================================================
    # CONVERSION VERS LA DEVISE DE LA VENTE
    # =========================================================
    def calculer_equivalent_vente(self):
        """
        Retourne la valeur du paiement dans la devise de la vente.

        Cas 1 :
        Vente CDF, client paie CDF
        5 000 CDF = 5 000 CDF

        Cas 2 :
        Vente CDF, client paie USD
        10 USD × 2 300 = 23 000 CDF

        Cas 3 :
        Vente USD, client paie USD
        10 USD = 10 USD

        Cas 4 :
        Vente USD, client paie CDF
        23 000 CDF ÷ 2 300 = 10 USD
        """
        if not self.vente_id:
            return Decimal("0.00")

        devise_vente = self.vente.devise
        devise_paiement = self.devise_paiement

        # Même devise : aucune conversion.
        if devise_vente == devise_paiement:
            return self.montant.quantize(
                Decimal("0.01"),
                rounding=ROUND_HALF_UP
            )

        # Conversion nécessaire : taux obligatoire.
        if (
            self.taux_usd_cdf_applique is None or
            self.taux_usd_cdf_applique <= Decimal("0.00")
        ):
            raise ValidationError(
                {
                    "taux_usd_cdf_applique": (
                        "Un taux USD/CDF actif est obligatoire "
                        "pour convertir ce paiement."
                    )
                }
            )

        # Client paie USD pour une vente en CDF.
        if (
            devise_vente == "CDF" and
            devise_paiement == "USD"
        ):
            return (
                self.montant *
                self.taux_usd_cdf_applique
            ).quantize(
                Decimal("0.01"),
                rounding=ROUND_HALF_UP
            )

        # Client paie CDF pour une vente en USD.
        if (
            devise_vente == "USD" and
            devise_paiement == "CDF"
        ):
            return (
                self.montant /
                self.taux_usd_cdf_applique
            ).quantize(
                Decimal("0.01"),
                rounding=ROUND_HALF_UP
            )

        raise ValidationError(
            {
                "devise_paiement": (
                    "Combinaison de devises non prise en charge."
                )
            }
        )

    # =========================================================
    # VALIDATION
    # =========================================================
    def clean(self):
        super().clean()

        if self.montant is None or self.montant <= Decimal("0.00"):
            raise ValidationError(
                {
                    "montant": (
                        "Le montant payé doit être supérieur à zéro."
                    )
                }
            )

        if not self.vente_id:
            return

        devise_vente = self.vente.devise

        # Une conversion est nécessaire : le taux appliqué doit
        # obligatoirement correspondre au taux actif de la pharmacie,
        # pour éviter qu'un taux périmé ou saisi manuellement de travers
        # ne soit utilisé.
        if devise_vente != self.devise_paiement:
            taux_change = getattr(self.vente.pharmacie, 'taux_change', None)

            if taux_change is None or not taux_change.est_actif:
                raise ValidationError({
                    'taux_usd_cdf_applique': (
                        "Aucun taux de change actif n'est défini pour "
                        "cette pharmacie. Impossible de convertir ce paiement."
                    )
                })

            if self.taux_usd_cdf_applique is None:
                # Pas de taux fourni : on applique automatiquement
                # le taux actif de la pharmacie.
                self.taux_usd_cdf_applique = taux_change.taux_usd_cdf
            elif self.taux_usd_cdf_applique != taux_change.taux_usd_cdf:
                raise ValidationError({
                    'taux_usd_cdf_applique': (
                        f"Le taux fourni ({self.taux_usd_cdf_applique}) ne "
                        f"correspond pas au taux actif de la pharmacie "
                        f"({taux_change.taux_usd_cdf})."
                    )
                })

        # Calculer le paiement dans la devise de la vente.
        equivalent = self.calculer_equivalent_vente()

        # Tous les paiements existants sont déjà enregistrés
        # dans montant_equivalent_vente, donc ils sont comparables.
        deja_paye = sum(
            (
                paiement.montant_equivalent_vente
                for paiement in self.vente.paiements.exclude(
                    pk=self.pk
                )
            ),
            Decimal("0.00")
        )

        montant_restant = max(
            self.vente.montant_total - deja_paye,
            Decimal("0.00")
        )

        # Interdire de payer plus que le restant.
        if equivalent > montant_restant:
            raise ValidationError(
                {
                    "montant": (
                        f"Paiement refusé. L'équivalent de ce paiement "
                        f"est {equivalent} {self.vente.devise}, mais "
                        f"le solde restant est seulement "
                        f"{montant_restant} {self.vente.devise}."
                    )
                }
            )

    # =========================================================
    # SAUVEGARDE
    # =========================================================
    def save(self, *args, **kwargs):
        # Le taux et le montant converti deviennent un historique.
        self.montant_equivalent_vente = (
            self.calculer_equivalent_vente()
        )

        self.full_clean()

        super().save(*args, **kwargs)

        self.vente.actualiser_statut()