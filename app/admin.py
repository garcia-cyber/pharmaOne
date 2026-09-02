from django.contrib import admin
from .models import *

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