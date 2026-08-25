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
    return render(request, 'back-end/dashboard/index.html')

# ===================================================================================================
# ===================================================================================================
@login_required
def deco(request):
    logout(request)
    return redirect('login')