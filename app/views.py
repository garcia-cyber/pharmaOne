from django.shortcuts import render , redirect , get_object_or_404
from django.contrib.auth.decorators import login_required
from .forms import *
from .models import *
from django.contrib.auth import authenticate , login as auth_login , logout ,update_session_auth_hash

# Create your views here.
# **********************************************************
# 01
def login(request):
    return render(request,'back-end/authentifications/auth-login.html') 