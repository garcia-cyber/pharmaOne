from django.contrib import admin
from .models import *
from django.utils.html import format_html

# Register your models here.

#
# Pharmacie
@admin.register(Pharmacie)
class PharmacieAdmin(admin.ModelAdmin):
    list_display = ['id', 'nom_pharmacie', 'user_pharmacie__username', 'dateCreation']
    search_fields = ['nom_pharmacie', 'user_pharmacie__username']


# Type role
@admin.register(TypeRole)
class TypeRoleAdmin(admin.ModelAdmin):
    list_display = ['id', 'nom_typeRole']


#
# ROLE
@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ['id', 'role__nom_typeRole', 'userRole', 'statut']


#
# taux d'echange
@admin.register(TauxChange)
class TauxChangeAdmin(admin.ModelAdmin):
    list_display = [
        'pharmacie',
        'taux_usd_cdf',
        'date_mise_a_jour',
        'utilisateur',
        'est_actif',
        'afficher_taux_formate'
    ]
    list_filter = ['est_actif', 'date_mise_a_jour']
    search_fields = ['pharmacie__nom_pharmacie']
    readonly_fields = ['date_mise_a_jour', 'utilisateur', 'afficher_taux_formate']
    ordering = ['-date_mise_a_jour']

    fieldsets = (
        ('Informations principales', {
            'fields': ('pharmacie', 'taux_usd_cdf', 'est_actif')
        }),
        ('Informations de suivi', {
            'fields': ('utilisateur', 'date_mise_a_jour', 'afficher_taux_formate'),
            'classes': ('collapse',)
        }),
    )

    def afficher_taux_formate(self, obj):
        """Affiche le taux de manière lisible"""
        return f"1 USD = {obj.taux_usd_cdf:,.2f} CDF"
    afficher_taux_formate.short_description = 'Taux affiché'

    def save_model(self, request, obj, form, change):
        """
        Définit automatiquement l'utilisateur qui modifie le taux.
        Si c'est une modification, on garde l'utilisateur existant.
        """
        if not change:  # Nouvelle instance
            obj.utilisateur = request.user
        super().save_model(request, obj, form, change)


# Admin inline pour voir le taux directement dans la pharmacie
class TauxChangeInline(admin.StackedInline):
    model = TauxChange
    can_delete = False
    verbose_name = 'Taux de change'
    verbose_name_plural = 'Taux de change'
    fields = ['taux_usd_cdf', 'date_mise_a_jour', 'utilisateur', 'est_actif']
    readonly_fields = ['date_mise_a_jour', 'utilisateur', 'est_actif']
    extra = 0

    def has_add_permission(self, request, obj=None):
        # Empêcher l'ajout de multiple taux depuis l'inline
        if obj:
            return not hasattr(obj, 'taux_change') or not obj.taux_change.exists()
        return True


# ================================================
# ================================================
# Medicament
@admin.register(Medicament)
class MedicamentAdmin(admin.ModelAdmin):
    list_display = (
        'nom',
        'dosage',
        'forme',
        'categorie',
        'devise',
        'pharmacie',
        'quantite_par_carton',
        'prix_achat_carton',
        'prix_vente_piece',
        'utilisateur',
        'date_creation',
    )
    list_filter = (
        'pharmacie',
        'forme',
        'categorie',
        'devise',
    )
    search_fields = (
        'nom',
        'dosage',
        'fabricant',
    )
    ordering = ('nom',)
    readonly_fields = ('date_creation', 'date_modification')
    autocomplete_fields = ('pharmacie', 'utilisateur')

    fieldsets = (
        ('Identification', {
            'fields': ('nom', 'forme', 'categorie', 'dosage', 'fabricant', 'description')
        }),
        ('Devise et gestion des cartons', {
            'fields': ('devise', 'quantite_par_carton', 'prix_achat_carton', 'prix_vente_piece')
        }),
        ('Relations', {
            'fields': ('pharmacie', 'utilisateur')
        }),
        ('Métadonnées', {
            'fields': ('date_creation', 'date_modification')
        }),
    )

    def get_queryset(self, request):
        """Restreint la vue aux médicaments de la pharmacie de l'utilisateur connecté (sauf superuser)."""
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs

        pharmacie_obj = Pharmacie.objects.filter(user_pharmacie=request.user).first()
        if pharmacie_obj:
            return qs.filter(pharmacie=pharmacie_obj)
        return qs.none()

    def save_model(self, request, obj, form, change):
        """Assigne automatiquement l'utilisateur connecté et sa pharmacie à la création."""
        if not change:
            obj.utilisateur = request.user
            pharmacie_obj = Pharmacie.objects.filter(user_pharmacie=request.user).first()
            if pharmacie_obj:
                obj.pharmacie = pharmacie_obj
        super().save_model(request, obj, form, change)

    def get_readonly_fields(self, request, obj=None):
        """Empêche un non-superuser de changer la pharmacie d'un médicament après coup."""
        readonly = list(self.readonly_fields)
        if not request.user.is_superuser:
            readonly.append('pharmacie')
        return readonly


# =============================================================================================
# =============================================================================================
#
# Stock (approvisionnement)
@admin.register(Stock)
class StockAdmin(admin.ModelAdmin):
    list_display = (
        'medicament',
        'numero_lot',
        'pharmacie',
        'nombre_cartons',
        'quantite_piece',
        'quantite_restante',
        'devise',
        'date_peremption',
        'date_achat',
        'utilisateur',
        'afficher_statut_peremption',
    )
    list_filter = (
        'pharmacie',
        'devise',
        'date_peremption',
        'date_achat',
    )
    search_fields = (
        'medicament__nom',
        'numero_lot',
    )
    ordering = ('date_peremption',)
    readonly_fields = (
        'quantite_piece',
        'quantite_restante',
        'date_achat',
    )
    autocomplete_fields = ('medicament', 'pharmacie', 'utilisateur')

    fieldsets = (
        ('Médicament et lot', {
            'fields': ('medicament', 'numero_lot', 'date_peremption')
        }),
        ('Quantités', {
            'fields': ('nombre_cartons', 'quantite_piece', 'quantite_restante')
        }),
        ('Tarification', {
            'fields': ('devise', 'prix_achat_carton', 'prix_vente_piece')
        }),
        ('Relations', {
            'fields': ('pharmacie', 'utilisateur')
        }),
        ('Métadonnées', {
            'fields': ('date_achat',)
        }),
    )

    def afficher_statut_peremption(self, obj):
        """Affiche si le lot est périmé ou non."""
        return "⚠️ Périmé" if obj.est_perime else "✅ Valide"
    afficher_statut_peremption.short_description = 'Statut'

    def get_queryset(self, request):
        """Restreint la vue aux stocks de la pharmacie de l'utilisateur connecté (sauf superuser)."""
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs

        pharmacie_obj = Pharmacie.objects.filter(user_pharmacie=request.user).first()
        if pharmacie_obj:
            return qs.filter(pharmacie=pharmacie_obj)
        return qs.none()

    def save_model(self, request, obj, form, change):
        """Assigne automatiquement l'utilisateur connecté et sa pharmacie à la création."""
        if not change:
            obj.utilisateur = request.user
            pharmacie_obj = Pharmacie.objects.filter(user_pharmacie=request.user).first()
            if pharmacie_obj:
                obj.pharmacie = pharmacie_obj
        super().save_model(request, obj, form, change)

    def get_readonly_fields(self, request, obj=None):
        """Empêche un non-superuser de changer la pharmacie après coup."""
        readonly = list(self.readonly_fields)
        if not request.user.is_superuser:
            readonly.append('pharmacie')
        return readonly

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """Limite le choix du médicament à ceux de la pharmacie de l'utilisateur (sauf superuser)."""
        if db_field.name == 'medicament' and not request.user.is_superuser:
            pharmacie_obj = Pharmacie.objects.filter(user_pharmacie=request.user).first()
            if pharmacie_obj:
                kwargs['queryset'] = Medicament.objects.filter(pharmacie=pharmacie_obj)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

# =======================================================
# =======================================================
# mouvement de medecament
#
# Mouvement de stock
@admin.register(MouvementStock)
class MouvementStockAdmin(admin.ModelAdmin):
    list_display = (
        'medicament',
        'type_mouvement',
        'quantite',
        'quantite_avant',
        'quantite_apres',
        'pharmacie',
        'stock',
        'utilisateur',
        'date_mouvement',
    )
    list_filter = (
        'pharmacie',
        'type_mouvement',
        'date_mouvement',
    )
    search_fields = (
        'medicament__nom',
        'stock__numero_lot',
        'motif',
    )
    ordering = ('-date_mouvement',)
    readonly_fields = (
        'stock',
        'medicament',
        'pharmacie',
        'utilisateur',
        'type_mouvement',
        'quantite',
        'quantite_avant',
        'quantite_apres',
        'motif',
        'date_mouvement',
    )
    autocomplete_fields = ('medicament', 'pharmacie', 'utilisateur')

    fieldsets = (
        ('Mouvement', {
            'fields': ('type_mouvement', 'quantite', 'quantite_avant', 'quantite_apres', 'motif')
        }),
        ('Relations', {
            'fields': ('stock', 'medicament', 'pharmacie', 'utilisateur')
        }),
        ('Métadonnées', {
            'fields': ('date_mouvement',)
        }),
    )

    def get_queryset(self, request):
        """Restreint la vue aux mouvements de la pharmacie de l'utilisateur connecté (sauf superuser)."""
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs

        pharmacie_obj = Pharmacie.objects.filter(user_pharmacie=request.user).first()
        if pharmacie_obj:
            return qs.filter(pharmacie=pharmacie_obj)
        return qs.none()

    def has_add_permission(self, request):
        """Empêche la création manuelle : les mouvements sont générés automatiquement (Stock.save(), Vente...)."""
        return False

    def has_change_permission(self, request, obj=None):
        """Empêche toute modification : un mouvement de stock est un historique, il ne doit jamais être modifié."""
        return False

    def has_delete_permission(self, request, obj=None):
        """Empêche la suppression : garder une traçabilité complète et fiable."""
        return request.user.is_superuser


# -------------------------------------------------------------------------------------------
# vente et ligne vente 
#
# Ligne de vente (inline, affichée dans VenteAdmin)
class LigneVenteInline(admin.TabularInline):
    model = LigneVente
    extra = 0
    fields = ('medicament', 'stock', 'quantite', 'prix_unitaire', 'sous_total_affiche')
    readonly_fields = ('sous_total_affiche',)
    autocomplete_fields = ('medicament', 'stock')

    def sous_total_affiche(self, obj):
        if obj.pk:
            return f"{obj.sous_total:,.2f}"
        return "-"
    sous_total_affiche.short_description = 'Sous-total'

    def has_delete_permission(self, request, obj=None):
        """Empêche la suppression d'une ligne déjà enregistrée : ça déséquilibrerait le stock."""
        return False


#
# Vente
@admin.register(Vente)
class VenteAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'pharmacie',
        'client_nom',
        'statut',
        'devise',
        'montant_total_affiche',
        'montant_paye_affiche',
        'montant_restant_affiche',
        'utilisateur',
        'date_vente',
    )
    list_filter = (
        'pharmacie',
        'statut',
        'devise',
        'date_vente',
    )
    search_fields = (
        'client_nom',
        'client_telephone',
        'id',
    )
    ordering = ('-date_vente',)
    readonly_fields = (
        'date_vente',
        'montant_total_affiche',
        'montant_paye_affiche',
        'montant_restant_affiche',
    )
    autocomplete_fields = ('pharmacie', 'utilisateur')
    inlines = [LigneVenteInline]

    fieldsets = (
        ('Client', {
            'fields': ('client_nom', 'client_telephone')
        }),
        ('Vente', {
            'fields': ('devise', 'statut', 'notes')
        }),
        ('Montants', {
            'fields': ('montant_total_affiche', 'montant_paye_affiche', 'montant_restant_affiche')
        }),
        ('Relations', {
            'fields': ('pharmacie', 'utilisateur')
        }),
        ('Métadonnées', {
            'fields': ('date_vente',)
        }),
    )

    def montant_total_affiche(self, obj):
        return f"{obj.montant_total:,.2f} {obj.devise}"
    montant_total_affiche.short_description = 'Montant total'

    def montant_paye_affiche(self, obj):
        return f"{obj.montant_paye:,.2f} {obj.devise}"
    montant_paye_affiche.short_description = 'Montant payé'

    def montant_restant_affiche(self, obj):
        return f"{obj.montant_restant:,.2f} {obj.devise}"
    montant_restant_affiche.short_description = 'Montant restant'

    def get_queryset(self, request):
        """Restreint la vue aux ventes de la pharmacie de l'utilisateur connecté (sauf superuser)."""
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs

        pharmacie_obj = Pharmacie.objects.filter(user_pharmacie=request.user).first()
        if pharmacie_obj:
            return qs.filter(pharmacie=pharmacie_obj)
        return qs.none()

    def save_model(self, request, obj, form, change):
        """Assigne automatiquement l'utilisateur connecté et sa pharmacie à la création."""
        if not change:
            obj.utilisateur = request.user
            pharmacie_obj = Pharmacie.objects.filter(user_pharmacie=request.user).first()
            if pharmacie_obj:
                obj.pharmacie = pharmacie_obj
        super().save_model(request, obj, form, change)

    def get_readonly_fields(self, request, obj=None):
        """Empêche un non-superuser de changer la pharmacie après coup."""
        readonly = list(self.readonly_fields)
        if not request.user.is_superuser:
            readonly.append('pharmacie')
        return readonly


#
# Ligne de vente (vue indépendante, en lecture seule pour consultation/recherche)
@admin.register(LigneVente)
class LigneVenteAdmin(admin.ModelAdmin):
    list_display = (
        'vente',
        'medicament',
        'stock',
        'quantite',
        'prix_unitaire',
        'sous_total_affiche',
    )
    list_filter = (
        'vente__pharmacie',
    )
    search_fields = (
        'medicament__nom',
        'stock__numero_lot',
        'vente__id',
    )
    autocomplete_fields = ('vente', 'medicament', 'stock')

    def sous_total_affiche(self, obj):
        return f"{obj.sous_total:,.2f}"
    sous_total_affiche.short_description = 'Sous-total'

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs

        pharmacie_obj = Pharmacie.objects.filter(user_pharmacie=request.user).first()
        if pharmacie_obj:
            return qs.filter(vente__pharmacie=pharmacie_obj)
        return qs.none()

    def has_add_permission(self, request):
        """Empêche la création manuelle isolée : une ligne doit toujours être créée via une Vente (pour bien décrémenter le stock)."""
        return False

    def has_change_permission(self, request, obj=None):
        """Empêche la modification : changer une ligne après coup désynchroniserait quantite_restante et les mouvements de stock."""
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser

# ==========================================================================
# ==========================================================================
@admin.register(PaiementVente)
class PaiementVenteAdmin(admin.ModelAdmin):

    # =========================================================
    # COLONNES DANS LA LISTE DES PAIEMENTS
    # =========================================================
    list_display = (
        "id",
        "vente_numero",
        "pharmacie",
        "client",
        "montant_affiche",
        "devise",
        "mode_paiement",
        "utilisateur",
        "date_paiement",
    )

    # =========================================================
    # FILTRES À DROITE DANS L'ADMIN
    # =========================================================
    list_filter = (
        "mode_paiement",
        "date_paiement",
        "vente__devise",
        "vente__pharmacie",
    )

    # =========================================================
    # BARRE DE RECHERCHE
    # =========================================================
    search_fields = (
        "id",
        "reference",
        "note",
        "vente__id",
        "vente__client_nom",
        "vente__client_telephone",
        "vente__pharmacie__nom_pharmacie",
        "utilisateur__username",
        "utilisateur__first_name",
        "utilisateur__last_name",
    )

    # =========================================================
    # TRI PAR DÉFAUT
    # =========================================================
    ordering = (
        "-date_paiement",
    )

    # =========================================================
    # ÉVITE DES REQUÊTES INUTILES POUR vente, pharmacie et user
    # =========================================================
    list_select_related = (
        "vente",
        "vente__pharmacie",
        "utilisateur",
    )

    # =========================================================
    # CHAMPS MODIFIABLES DIRECTEMENT DANS LA LISTE
    #
    # Pour éviter les erreurs comptables, on ne rend aucun
    # montant modifiable dans la liste.
    # =========================================================
    list_editable = ()

    # =========================================================
    # PAGE D'AJOUT / MODIFICATION
    # =========================================================
    fieldsets = (
        (
            "Paiement",
            {
                "fields": (
                    "vente",
                    "montant",
                    "mode_paiement",
                )
            }
        ),

        (
            "Informations complémentaires",
            {
                "fields": (
                    "reference",
                    "note",
                )
            }
        ),

        (
            "Traçabilité",
            {
                "fields": (
                    "utilisateur",
                    "date_paiement",
                )
            }
        ),
    )

    # date_paiement est créé automatiquement.
    readonly_fields = (
        "date_paiement",
    )

    # =========================================================
    # MÉTHODES D'AFFICHAGE
    # =========================================================
    @admin.display(
        description="Vente",
        ordering="vente__id"
    )
    def vente_numero(self, obj):
        return f"Vente #{obj.vente_id}"

    @admin.display(
        description="Pharmacie",
        ordering="vente__pharmacie__nom_pharmacie"
    )
    def pharmacie(self, obj):
        return obj.vente.pharmacie.nom_pharmacie

    @admin.display(
        description="Client",
        ordering="vente__client_nom"
    )
    def client(self, obj):
        if obj.vente.client_nom:
            return obj.vente.client_nom

        return "Client non renseigné"

    @admin.display(
        description="Devise",
        ordering="vente__devise"
    )
    def devise(self, obj):
        return obj.vente.devise

    @admin.display(
        description="Montant",
        ordering="montant"
    )
    def montant_affiche(self, obj):
        if obj.vente.devise == "USD":
            couleur = "#2563eb"
        else:
            couleur = "#15803d"

        return format_html(
            '<strong style="color: {};">{} {}</strong>',
            couleur,
            obj.montant,
            obj.vente.devise
        )

    # =========================================================
    # À LA CRÉATION :
    # L'UTILISATEUR CONNECTÉ DANS L'ADMIN DEVIENT LE CAISSIER.
    # =========================================================
    def save_model(self, request, obj, form, change):
        if not obj.utilisateur_id:
            obj.utilisateur = request.user

        super().save_model(
            request,
            obj,
            form,
            change
        )

    # =========================================================
    # APRÈS CRÉATION :
    # on bloque la modification des éléments comptables.
    #
    # Un paiement ne devrait normalement pas être modifié.
    # Si une erreur est commise, il vaut mieux créer un
    # règlement inverse / annulation, selon tes règles métier.
    # =========================================================
    def get_readonly_fields(self, request, obj=None):
        if obj is not None:
            return (
                "vente",
                "montant",
                "mode_paiement",
                "reference",
                "note",
                "utilisateur",
                "date_paiement",
            )

        return (
            "date_paiement",
        )

    # =========================================================
    # L'UTILISATEUR CONNECTÉ EST IMPOSÉ À LA CRÉATION.
    # Il n'apparaît donc pas comme champ à sélectionner.
    # =========================================================
    def get_fields(self, request, obj=None):
        if obj is None:
            return (
                "vente",
                "montant",
                "mode_paiement",
                "reference",
                "note",
                "date_paiement",
            )

        return super().get_fields(
            request,
            obj
        )

    # =========================================================
    # L'utilisateur est automatiquement ajouté par save_model.
    # Donc, il ne faut pas le demander lors de l'ajout.
    # =========================================================
    def get_fieldsets(self, request, obj=None):
        if obj is None:
            return (
                (
                    "Paiement",
                    {
                        "fields": (
                            "vente",
                            "montant",
                            "mode_paiement",
                        )
                    }
                ),
                (
                    "Informations complémentaires",
                    {
                        "fields": (
                            "reference",
                            "note",
                        )
                    }
                ),
                (
                    "Traçabilité",
                    {
                        "fields": (
                            "date_paiement",
                        )
                    }
                ),
            )

        return self.fieldsets