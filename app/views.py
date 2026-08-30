from django.shortcuts import render , redirect , get_object_or_404 
from django.contrib.auth.decorators import login_required
from .forms import *
from .models import *
from django.contrib.auth import authenticate , login as auth_login , logout ,update_session_auth_hash


# Create your views here.
# **********************************************************
# 01
def login(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    msg = None 
    if request.method == "POST":
        form = LoginForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')

            user = authenticate(request , username = username , password = password) 
            if user is not None:
                if user.is_active:
                    auth_login(request, user)
                    return redirect('dashboard')
                else:
                    msg = "Votre compte est désactivé."
            else:
                msg = "Identifiants invalides. Veuillez réessayer. 🤞"

    else:
        form = LoginForm()


    
    return render(request,'back-end/authentifications/auth-login.html',{'form': form , 'msg': msg})


# ===================================================================================================
# ===================================================================================================
@login_required()
def dashboard(request):
    role_verify = Role.objects.filter(userRole = request.user).select_related('role') 
    roles       = [r.role.nom_typeRole for r in role_verify if r.role ] 
    
    if 'super admin' in roles :
        primary_role = 'super admin' 
    elif 'admin' in roles :
        primary_role = 'admin'
    else :
        primary_role = 'visiteur' 


    #
    # pahrmacie nom
    pharmacie_obj = Pharmacie.objects.filter(user_pharmacie = request.user).first()
    name_phar = pharmacie_obj.nom_pharmacie if pharmacie_obj else 'pas de nom'

    context = {
        'primary_role': primary_role ,
        'roles' : roles 
    }
    return render(request, 'back-end/dashboard/index.html',context)

# ===================================================================================================
# ===================================================================================================
@login_required
def deco(request):
    logout(request)
    return redirect('login') 

# **************************************************************
# FORMULAIRE DE TAUX D'ECHANGE
# **************************************************************
@login_required()
def creer_taux_change(request):
    msg = None

    pharmacie_obj = Pharmacie.objects.filter(user_pharmacie=request.user).first()
    name_phar = pharmacie_obj.nom_pharmacie if pharmacie_obj else 'pas de nom'

    # taux existant pour cette pharmacie, s'il y en a un
    taux_existant = None
    if pharmacie_obj:
        taux_existant = TauxChange.objects.filter(pharmacie=pharmacie_obj).first()

    if request.method == 'POST':
        form = TauxChangeForm(request.POST, instance=taux_existant)
        if form.is_valid():
            if pharmacie_obj is None:
                msg = "Vous devez d'abord créer votre pharmacie."
            else:
                taux = form.save(commit=False)
                taux.pharmacie = pharmacie_obj
                taux.utilisateur = request.user
                taux.save()
                msg = "Taux de change mis à jour" if taux_existant else "Taux de change créé"
                taux_existant = taux  # pour que le form réaffiché reste en mode "édition"
    else:
        form = TauxChangeForm(instance=taux_existant)

    # gestion de role
    role_verify = Role.objects.filter(userRole=request.user).select_related('role')
    roles = [r.role.nom_typeRole for r in role_verify if r.role]

    if 'super admin' in roles:
        primary_role = 'super admin'
    elif 'admin' in roles:
        primary_role = 'admin'
    else:
        primary_role = 'visiteur'
    
    return render(request, 'back-end/settings/taux_change_form.html', {
        'form': form,
        'primary_role': primary_role,
        'roles': roles,
        'name_phar': name_phar,
        'msg': msg,
    })