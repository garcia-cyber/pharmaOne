from django.contrib import admin
from .models import * 

# Register your models here.

#
# Pharmacie
@admin.register(Pharmacie)
class PharmacieAdmin(admin.ModelAdmin):
    list_display = ['id','nom_pharmacie','user_pharmacie__username','dateCreation']

# Type role 
@admin.register(TypeRole)
class TypeRoleAdmin(admin.ModelAdmin):
    list_display = ['id','nom_typeRole']

#
# ROLE 
@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ['id','role__nom_typeRole','userRole','statut'] 

    
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

