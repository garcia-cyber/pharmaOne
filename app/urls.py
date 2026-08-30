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
    
]
