from django.urls import path 
from . import views
from .views import * 


urlpatterns = [
    path('', login , name="login"),
    path('dashboard/', dashboard , name = 'dashboard'), 
    path('deco/', deco , name = 'deco') , 
    
]
