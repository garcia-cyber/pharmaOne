from django.urls import path 
from . import views
from .views import * 


urlpatterns = [
    # ************************************
    # authentification 

    path('', login , name="login"),
    path('dashboard/', dashboard , name = 'dashboard'), 
    path('deco/', deco , name = 'deco') ,

    # ***********************************
    # settings 
    path('creer_taux_change/', creer_taux_change ,  name="creer_taux_change"),

    # ***********************************
    # Medicaments
    path('creer_medicament/', creer_medicament , name="creer_medicament"),
    path('liste_medicaments/',liste_medicaments ,name="liste_medicaments"), 
    path('modifier_medicament/<int:medicament_id>/', modifier_medicament , name="modifier_medicament") ,

    # *************************************
    # Stock
    path('creer_stock/', creer_stock , name="creer_stock"),  
    path('liste_stock/', liste_stock , name='liste_stock'),
    path('detail_stock/<int:stock_id>/', detail_stock ,  name ='detail_stock'),
    path("stock-par-medicament/",views.stock_par_medicament,name="stock_par_medicament"),
    path('historique_achat_stock/',historique_achat_stock , name = 'historique_achat_stock') ,
    path('export_historique_achat_stock/',export_historique_achat_stock , name = 'export_historique_achat_stock') ,
    path("modifier_stock/<int:stock_id>/",views.modifier_stock,name="modifier_stock"),
    
    
]
