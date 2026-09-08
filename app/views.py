from django.shortcuts import render , redirect , get_object_or_404 , HttpResponse
from django.contrib.auth.decorators import login_required
from .forms import *
from .models import *
from django.contrib.auth import authenticate , login as auth_login , logout ,update_session_auth_hash
from django.core.paginator import Paginator
from django.db.models import Q, Sum, F, DecimalField, ExpressionWrapper ,Count,Min
from datetime import timedelta
from decimal import Decimal , ROUND_HALF_UP
from django.utils import timezone
from django.contrib import messages
from django.db import transaction
from django.http import JsonResponse
from django.core.paginator import Paginator
from datetime import datetime, timedelta
from decimal import Decimal
from django.contrib.auth.forms import PasswordChangeForm



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
    role_verify = (
        Role.objects
        .filter(userRole=request.user, statut='active')
        .select_related('role', 'pharmacie')
    )
    roles = [user_role.role.nom_typeRole for user_role in role_verify if user_role.role]
    roles_normalises = [role.lower().strip() for role in roles]

    if 'super admin' in roles_normalises:
        primary_role = 'super admin'
        pharmacies = Pharmacie.objects.all()
    else:
        if 'admin' in roles_normalises:
            primary_role = 'admin'
        elif 'gestionnaire' in roles_normalises:
            primary_role = 'gestionnaire'
        else:
            primary_role = 'visiteur'

        pharmacies = Pharmacie.objects.filter(
            Q(user_pharmacie=request.user) |
            Q(roles__userRole=request.user, roles__statut='active')
        ).distinct()

    pharmacie_noms = list(
        pharmacies.order_by('nom_pharmacie').values_list('nom_pharmacie', flat=True)
    )
    if primary_role == 'super admin':
        name_phar = 'Toutes les pharmacies'
    else:
        name_phar = ', '.join(pharmacie_noms) if pharmacie_noms else 'pas de nom'

    aujourd_hui = timezone.localdate()
    debut_semaine = aujourd_hui - timedelta(days=aujourd_hui.weekday())
    debut_mois = aujourd_hui.replace(day=1)
    debut_annee = aujourd_hui.replace(month=1, day=1)

    ventes = (
        Vente.objects
        .filter(
            pharmacie__in=pharmacies,
            statut__in=[
                Vente.StatutVente.EN_ATTENTE,
                Vente.StatutVente.PARTIELLEMENT_PAYEE,
                Vente.StatutVente.PAYEE,
            ],
        )
        .prefetch_related('lignes__stock')
    )

    def chiffre_affaires_par_devise(queryset):
        totaux = {'CDF': Decimal('0.00'), 'USD': Decimal('0.00')}
        for ligne in LigneVente.objects.filter(
            vente__in=queryset
        ).select_related('vente', 'stock'):
            devise = ligne.vente.devise
            if devise in totaux:
                totaux[devise] += ligne.sous_total_net
        return totaux

    ventes_jour = ventes.filter(date_vente__date=aujourd_hui)
    ventes_semaine = ventes.filter(date_vente__date__gte=debut_semaine)
    ventes_mois = ventes.filter(date_vente__date__gte=debut_mois)
    ventes_annee = ventes.filter(date_vente__date__gte=debut_annee)

    ca_jour = chiffre_affaires_par_devise(ventes_jour)
    ca_semaine = chiffre_affaires_par_devise(ventes_semaine)
    ca_mois = chiffre_affaires_par_devise(ventes_mois)
    ca_annee = chiffre_affaires_par_devise(ventes_annee)

    stocks = Stock.objects.filter(pharmacie__in=pharmacies)
    medicaments = Medicament.objects.filter(pharmacie__in=pharmacies)
    stock_faible = stocks.filter(quantite_restante__lte=10).count()

    context = {
        'primary_role': primary_role,
        'roles': roles,
        'name_phar': name_phar,
        'stats': {
            'nb_ordonnances_jour': ventes_jour.count(),
            'nb_ventes_mois': ventes_mois.count(),
            'nb_clients': ventes.values('client_telephone').exclude(
                client_telephone__isnull=True
            ).exclude(client_telephone='').distinct().count(),
            'nb_nouveaux_produits': medicaments.filter(
                date_creation__date__gte=debut_mois
            ).count(),
            'nb_medicaments': medicaments.count(),
            'nb_stocks': stocks.count(),
            'stock_faible': stock_faible,
            'ca_jour_cdf': ca_jour['CDF'],
            'ca_jour_usd': ca_jour['USD'],
            'ca_hebdo_cdf': ca_semaine['CDF'],
            'ca_hebdo_usd': ca_semaine['USD'],
            'ca_mensuel_cdf': ca_mois['CDF'],
            'ca_mensuel_usd': ca_mois['USD'],
            'ca_annuel_cdf': ca_annee['CDF'],
            'ca_annuel_usd': ca_annee['USD'],
        },
    }
    return render(request, 'back-end/dashboard/index.html', context)

# ===================================================================================================
# ===================================================================================================
# Deconnexion
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


# =====================================================================================
# =====================================================================================
# ENREGISTREMENT DE MEDICAMENT
@login_required()
def creer_medicament(request):
    msg = None

    pharmacie_obj = Pharmacie.objects.filter(user_pharmacie=request.user).first()
    name_phar = pharmacie_obj.nom_pharmacie if pharmacie_obj else 'pas de nom'

    if request.method == 'POST':
        form = MedicamentForm(request.POST)
        if form.is_valid():
            if pharmacie_obj is None:
                msg = "Vous devez d'abord créer votre pharmacie."
            else:
                medicament = form.save(commit=False)
                medicament.pharmacie = pharmacie_obj
                medicament.utilisateur = request.user
                medicament.save()
                msg = "Médicament enregistré avec succès"
                form = MedicamentForm()  # formulaire vide après succès
    else:
        form = MedicamentForm()

    # gestion de role
    role_verify = Role.objects.filter(userRole=request.user).select_related('role')
    roles = [r.role.nom_typeRole for r in role_verify if r.role]

    if 'super admin' in roles:
        primary_role = 'super admin'
    elif 'admin' in roles:
        primary_role = 'admin'
    else:
        primary_role = 'visiteur'

    return render(request, 'back-end/medicaments/medicament_form.html', {
        'form': form,
        'primary_role': primary_role,
        'roles': roles,
        'name_phar': name_phar,
        'msg': msg,
    })

# =========================================================================================
# =========================================================================================
# LISTE DE MEDICAMENT 
@login_required()
def liste_medicaments(request):
    pharmacie_obj = Pharmacie.objects.filter(user_pharmacie=request.user).first()
    name_phar = pharmacie_obj.nom_pharmacie if pharmacie_obj else 'pas de nom'

    medicaments = Medicament.objects.filter(pharmacie=pharmacie_obj) if pharmacie_obj else Medicament.objects.none()

    # recherche
    recherche = request.GET.get('q', '').strip()
    if recherche:
        medicaments = medicaments.filter(nom__icontains=recherche)

    # filtre par categorie
    categorie = request.GET.get('categorie', '').strip()
    if categorie:
        medicaments = medicaments.filter(categorie=categorie)

    # filtre par forme
    forme = request.GET.get('forme', '').strip()
    if forme:
        medicaments = medicaments.filter(forme=forme)

    medicaments = medicaments.order_by('nom')

    # gestion de role
    role_verify = Role.objects.filter(userRole=request.user).select_related('role')
    roles = [r.role.nom_typeRole for r in role_verify if r.role]

    if 'super admin' in roles:
        primary_role = 'super admin'
    elif 'admin' in roles:
        primary_role = 'admin'
    else:
        primary_role = 'visiteur'

    return render(request, 'back-end/medicaments/medicament_liste.html', {
        'medicaments': medicaments,
        'primary_role': primary_role,
        'roles': roles,
        'name_phar': name_phar,
        'recherche': recherche,
        'categorie_selectionnee': categorie,
        'forme_selectionnee': forme,
        'categories': Medicament.CategorieMedicament.choices,
        'formes': Medicament.FormePharmaceutique.choices,
    })

# =============================================================================================
# =============================================================================================
# Modification de medicament 
@login_required()
def modifier_medicament(request, medicament_id):
    msg = None

    pharmacie_obj = Pharmacie.objects.filter(user_pharmacie=request.user).first()
    name_phar = pharmacie_obj.nom_pharmacie if pharmacie_obj else 'pas de nom'

    if pharmacie_obj is None:
        return redirect('liste_medicaments')

    # get_object_or_404 avec filtre pharmacie : empêche un utilisateur
    # de modifier le médicament d'une autre pharmacie via l'URL
    medicament = get_object_or_404(
        Medicament,
        id=medicament_id,
        pharmacie=pharmacie_obj
    )

    if request.method == 'POST':
        form = MedicamentForm(request.POST, instance=medicament)
        if form.is_valid():
            medicament = form.save(commit=False)
            medicament.pharmacie = pharmacie_obj
            medicament.utilisateur = request.user
            medicament.save()
            msg = "Médicament mis à jour avec succès"
            return redirect('liste_medicaments')
    else:
        form = MedicamentForm(instance=medicament)

    # gestion de role
    role_verify = Role.objects.filter(userRole=request.user).select_related('role')
    roles = [r.role.nom_typeRole for r in role_verify if r.role]

    if 'super admin' in roles:
        primary_role = 'super admin'
    elif 'admin' in roles:
        primary_role = 'admin'
    else:
        primary_role = 'visiteur'

    return render(request, 'back-end/medicaments/medicament_form.html', {
        'form': form,
        'medicament': medicament,
        'primary_role': primary_role,
        'roles': roles,
        'name_phar': name_phar,
        'msg': msg,
    })

# ========================================================================================
# ========================================================================================
# ENREGISTREMENT DE L'APPROVISIONNEMENT 
@login_required
def creer_stock(request):
    msg = None

    # ---------------------------------------------------------
    # 1. Récupération de la pharmacie du user connecté
    # ---------------------------------------------------------
    pharmacie_obj = (
        Pharmacie.objects
        .filter(user_pharmacie=request.user)
        .first()
    )

    name_phar = (
        pharmacie_obj.nom_pharmacie
        if pharmacie_obj
        else "Aucune pharmacie créée"
    )

    # ---------------------------------------------------------
    # 2. Création / traitement du formulaire d'approvisionnement
    # ---------------------------------------------------------
    if request.method == "POST":
        form = StockForm(
            request.POST,
            user=request.user
        )

        # Le formulaire contient déjà une protection dans clean(),
        # mais ce message permet de guider directement l'utilisateur.
        if pharmacie_obj is None:
            msg = (
                "Vous devez d'abord créer votre pharmacie "
                "avant d'ajouter un stock."
            )

        elif form.is_valid():
            stock = form.save()

            msg = (
                f"Approvisionnement enregistré : "
                f"{stock.quantite_piece} pièce(s) ajoutée(s) pour "
                f"{stock.medicament.nom}."
            )

            # Formulaire vide après un enregistrement réussi.
            form = StockForm(user=request.user)

    else:
        form = StockForm(user=request.user)

    # ---------------------------------------------------------
    # 3. Récupération des rôles pour tes templates includes/sidebar
    # ---------------------------------------------------------
    role_verify = (
        Role.objects
        .filter(userRole=request.user)
        .select_related("role")
    )

    roles = [
        role.role.nom_typeRole
        for role in role_verify
        if role.role
    ]

    roles_normalises = [
        role.lower().strip()
        for role in roles
    ]

    if "super admin" in roles_normalises:
        primary_role = "super admin"
    elif "admin" in roles_normalises:
        primary_role = "admin"
    else:
        primary_role = "visiteur"

    # ---------------------------------------------------------
    # 4. Données pour JavaScript : aperçu après sélection
    # ---------------------------------------------------------
    medicaments_json = {}

    if pharmacie_obj:
        medicaments = (
            pharmacie_obj.medicaments
            .all()
            .order_by("nom", "dosage")
        )

        for medicament in medicaments:
            medicaments_json[str(medicament.id)] = {
                "nom": medicament.nom,
                "dosage": medicament.dosage or "",
                "forme": medicament.get_forme_display(),
                "quantite_par_carton": medicament.quantite_par_carton,
                "devise": medicament.devise,
                "prix_achat_carton": float(
                    medicament.prix_achat_carton
                ),
                "prix_vente_piece": float(
                    medicament.prix_vente_piece
                ),
            }

    # ---------------------------------------------------------
    # 5. Affichage de la page
    # ---------------------------------------------------------
    return render(request, "back-end/stocks/stock_form.html", {
        "form": form,
        "primary_role": primary_role,
        "roles": roles,
        "name_phar": name_phar,
        "msg": msg,
        "pharmacie_obj": pharmacie_obj,
        "medicaments_json": medicaments_json,
    })


# --------------------------------------------------------------------------
# LISTE DE STOCKS
# --------------------------------------------------------------------------
@login_required
def liste_stock(request):
    # ---------------------------------------------------------
    # 1. Récupérer la pharmacie appartenant à l'utilisateur connecté
    # ---------------------------------------------------------
    pharmacie_obj = (
        Pharmacie.objects
        .filter(user_pharmacie=request.user)
        .first()
    )

    name_phar = (
        pharmacie_obj.nom_pharmacie
        if pharmacie_obj
        else "Aucune pharmacie créée"
    )

    # ---------------------------------------------------------
    # 2. Valeurs initiales si l'utilisateur n'a pas de pharmacie
    # ---------------------------------------------------------
    stocks = Stock.objects.none()

    total_lots = 0
    total_pieces_restantes = 0
    valeur_achat_totale = Decimal("0.00")
    valeur_vente_potentielle = Decimal("0.00")

    # Récupération des paramètres de recherche / filtres.
    recherche = request.GET.get("q", "").strip()
    filtre_peremption = request.GET.get("peremption", "").strip()

    # ---------------------------------------------------------
    # 3. Stock de la pharmacie connectée uniquement
    # ---------------------------------------------------------
    if pharmacie_obj:
        stocks = (
            Stock.objects
            .filter(pharmacie=pharmacie_obj)
            .select_related(
                "medicament",
                "pharmacie",
                "utilisateur"
            )
            .order_by(
                "date_peremption",
                "-date_achat"
            )
        )

        # -----------------------------------------------------
        # 4. Recherche : médicament, dosage ou numéro de lot
        # -----------------------------------------------------
        if recherche:
            stocks = stocks.filter(
                Q(medicament__nom__icontains=recherche) |
                Q(medicament__dosage__icontains=recherche) |
                Q(numero_lot__icontains=recherche)
            )

        # -----------------------------------------------------
        # 5. Filtres de péremption
        # valeurs possibles :
        # - perime
        # - proche
        # - disponible
        # - rupture
        # -----------------------------------------------------
        today = timezone.localdate()
        limite_proche_peremption = today + timedelta(days=90)

        if filtre_peremption == "perime":
            stocks = stocks.filter(
                date_peremption__lt=today
            )

        elif filtre_peremption == "proche":
            stocks = stocks.filter(
                date_peremption__gte=today,
                date_peremption__lte=limite_proche_peremption,
                quantite_restante__gt=0
            )

        elif filtre_peremption == "disponible":
            stocks = stocks.filter(
                date_peremption__gt=limite_proche_peremption,
                quantite_restante__gt=0
            )

        elif filtre_peremption == "rupture":
            stocks = stocks.filter(
                quantite_restante=0
            )

        # -----------------------------------------------------
        # 6. Statistiques globales des stocks filtrés
        # -----------------------------------------------------
        total_lots = stocks.count()

        total_pieces_restantes = (
            stocks.aggregate(
                total=Sum("quantite_restante")
            )["total"]
            or 0
        )

        valeur_achat_expression = ExpressionWrapper(
            F("nombre_cartons") * F("prix_achat_carton"),
            output_field=DecimalField(
                max_digits=18,
                decimal_places=2
            )
        )

        valeur_vente_expression = ExpressionWrapper(
            F("quantite_restante") * F("prix_vente_piece"),
            output_field=DecimalField(
                max_digits=18,
                decimal_places=2
            )
        )

        valeur_achat_totale = (
            stocks.aggregate(
                total=Sum(valeur_achat_expression)
            )["total"]
            or Decimal("0.00")
        )

        valeur_vente_potentielle = (
            stocks.aggregate(
                total=Sum(valeur_vente_expression)
            )["total"]
            or Decimal("0.00")
        )

    # ---------------------------------------------------------
    # 7. Pagination
    # ---------------------------------------------------------
    paginator = Paginator(stocks, 15)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    # ---------------------------------------------------------
    # 8. Rôles de l'utilisateur connecté pour tes includes
    # ---------------------------------------------------------
    role_verify = (
        Role.objects
        .filter(userRole=request.user)
        .select_related("role")
    )

    roles = [
        role.role.nom_typeRole
        for role in role_verify
        if role.role
    ]

    roles_normalises = [
        role.lower().strip()
        for role in roles
    ]

    if "super admin" in roles_normalises:
        primary_role = "super admin"
    elif "admin" in roles_normalises:
        primary_role = "admin"
    else:
        primary_role = "visiteur"

    # ---------------------------------------------------------
    # 9. Envoi au template
    # ---------------------------------------------------------
    return render(request, "back-end/stocks/stock_list.html", {
        "stocks": page_obj,
        "page_obj": page_obj,
        "paginator": paginator,

        "pharmacie_obj": pharmacie_obj,
        "name_phar": name_phar,

        "recherche": recherche,
        "filtre_peremption": filtre_peremption,

        "today": timezone.localdate(),
        "limite_proche_peremption": (
            timezone.localdate() + timedelta(days=90)
        ),

        "total_lots": total_lots,
        "total_pieces_restantes": total_pieces_restantes,
        "valeur_achat_totale": valeur_achat_totale,
        "valeur_vente_potentielle": valeur_vente_potentielle,

        "primary_role": primary_role,
        "roles": roles,
    })

# ----------------------------------------------------------------------------------------
# detail de stock
# ----------------------------------------------------------------------------------------
@login_required
def detail_stock(request, stock_id):
    # ---------------------------------------------------------
    # 1. Récupérer la pharmacie liée au user connecté
    # ---------------------------------------------------------
    pharmacie_obj = (
        Pharmacie.objects
        .filter(user_pharmacie=request.user)
        .first()
    )

    # Nom affiché dans header / template.
    name_phar = (
        pharmacie_obj.nom_pharmacie
        if pharmacie_obj
        else "Aucune pharmacie créée"
    )

    # ---------------------------------------------------------
    # 2. Récupérer le lot uniquement dans cette pharmacie
    #
    # Sécurité :
    # /stock/15/ ne sera visible que si Stock 15 appartient
    # à la pharmacie de request.user.
    # ---------------------------------------------------------
    stock = get_object_or_404(
        Stock.objects.select_related(
            "medicament",
            "pharmacie",
            "utilisateur"
        ),
        id=stock_id,
        pharmacie=pharmacie_obj
    )

    # ---------------------------------------------------------
    # 3. Déterminer le statut du lot
    # ---------------------------------------------------------
    if stock.quantite_restante == 0:
        statut_stock = "rupture"
        libelle_statut = "Rupture de stock"

    elif stock.est_perime:
        statut_stock = "perime"
        libelle_statut = "Lot périmé"

    else:
        statut_stock = "disponible"
        libelle_statut = "Disponible"

    # ---------------------------------------------------------
    # 4. Récupérer les rôles pour header.html et aside.html
    # ---------------------------------------------------------
    role_verify = (
        Role.objects
        .filter(userRole=request.user)
        .select_related("role")
    )

    roles = [
        role.role.nom_typeRole
        for role in role_verify
        if role.role
    ]

    roles_normalises = [
        role.lower().strip()
        for role in roles
    ]

    if "super admin" in roles_normalises:
        primary_role = "super admin"
    elif "admin" in roles_normalises:
        primary_role = "admin"
    else:
        primary_role = "visiteur"

    # ---------------------------------------------------------
    # 5. Afficher la page de détail
    # ---------------------------------------------------------
    return render(request, "back-end/stocks/stock_detail.html", {
        "stock": stock,
        "pharmacie_obj": pharmacie_obj,
        "name_phar": name_phar,

        "statut_stock": statut_stock,
        "libelle_statut": libelle_statut,

        "primary_role": primary_role,
        "roles": roles,
    })

# ----------------------------------------------------------------------------------------------------------
#
# ----------------------------------------------------------------------------------------------------------
@login_required
def stock_par_medicament(request):
    recherche = request.GET.get("q", "").strip()

    # Pharmacie du user connecté.
    pharmacie_obj = (
        Pharmacie.objects
        .filter(user_pharmacie=request.user)
        .first()
    )

    name_phar = (
        pharmacie_obj.nom_pharmacie
        if pharmacie_obj
        else "Aucune pharmacie créée"
    )

    today = timezone.localdate()
    limite_proche_peremption = today + timedelta(days=90)

    medicaments_stock = Stock.objects.none()

    total_medicaments = 0
    total_pieces_restantes = 0
    total_lots = 0

    if pharmacie_obj:
        stocks = (
            Stock.objects
            .filter(pharmacie=pharmacie_obj)
            .select_related("medicament")
        )

        # Recherche sur le médicament.
        if recherche:
            stocks = stocks.filter(
                Q(medicament__nom__icontains=recherche) |
                Q(medicament__dosage__icontains=recherche) |
                Q(medicament__forme__icontains=recherche) |
                Q(medicament__categorie__icontains=recherche)
            )

        # Une ligne = un médicament.
        medicaments_stock = (
            stocks
            .values(
                "medicament_id",
                "medicament__nom",
                "medicament__dosage",
                "medicament__forme",
                "medicament__categorie",
                "medicament__devise",
                "medicament__prix_vente_piece",
            )
            .annotate(
                total_pieces=Sum("quantite_restante"),
                total_pieces_entrees=Sum("quantite_piece"),
                nombre_lots=Count("id"),
                prochain_peremption=Min("date_peremption"),
                lots_en_rupture=Count(
                    "id",
                    filter=Q(quantite_restante=0)
                ),
            )
            .order_by(
                "medicament__nom",
                "medicament__dosage"
            )
        )

        total_medicaments = medicaments_stock.count()

        total_pieces_restantes = (
            stocks.aggregate(
                total=Sum("quantite_restante")
            )["total"]
            or 0
        )

        total_lots = stocks.count()

    paginator = Paginator(medicaments_stock, 15)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    # Rôles, nécessaires à header.html et aside.html.
    role_verify = (
        Role.objects
        .filter(userRole=request.user)
        .select_related("role")
    )

    roles = [
        role.role.nom_typeRole
        for role in role_verify
        if role.role
    ]

    roles_normalises = [
        role.lower().strip()
        for role in roles
    ]

    if "super admin" in roles_normalises:
        primary_role = "super admin"
    elif "admin" in roles_normalises:
        primary_role = "admin"
    else:
        primary_role = "visiteur"

    return render(
        request,
        "back-end/stocks/stock_par_medicament.html",
        {
            "medicaments_stock": page_obj,
            "page_obj": page_obj,
            "paginator": paginator,

            "pharmacie_obj": pharmacie_obj,
            "name_phar": name_phar,

            "recherche": recherche,
            "today": today,
            "limite_proche_peremption": limite_proche_peremption,

            "total_medicaments": total_medicaments,
            "total_pieces_restantes": total_pieces_restantes,
            "total_lots": total_lots,

            "primary_role": primary_role,
            "roles": roles,
        }
    )

# ------------------------------------------------------------------------------------------
# HISTORIQUE D'ACHAT
# ------------------------------------------------------------------------------------------
@login_required
def historique_achat_stock(request):
    from datetime import datetime
    from decimal import Decimal
    # ---------------------------------------------------------
    # 1. Paramètres reçus depuis l'URL
    # Exemple :
    # /historique_achat_stock/?q=para&date_debut=2026-01-01
    # ---------------------------------------------------------
    recherche = request.GET.get("q", "").strip()
    date_debut_str = request.GET.get("date_debut", "").strip()
    date_fin_str = request.GET.get("date_fin", "").strip()
    medicament_id = request.GET.get("medicament", "").strip()

    # ---------------------------------------------------------
    # 2. Récupération de la pharmacie du user connecté
    # ---------------------------------------------------------
    pharmacie_obj = (
        Pharmacie.objects
        .filter(user_pharmacie=request.user)
        .first()
    )

    name_phar = (
        pharmacie_obj.nom_pharmacie
        if pharmacie_obj
        else "Aucune pharmacie créée"
    )

    # ---------------------------------------------------------
    # 3. Valeurs initiales
    # ---------------------------------------------------------
    achats = Stock.objects.none()
    medicaments = []

    total_achats = 0
    total_cartons = 0
    total_pieces_achetees = 0
    montant_total_achat = Decimal("0.00")

    # Dates converties depuis le formulaire HTML.
    date_debut = None
    date_fin = None

    # ---------------------------------------------------------
    # 4. Conversion sécurisée des dates
    # ---------------------------------------------------------
    if date_debut_str:
        try:
            date_debut = datetime.strptime(
                date_debut_str,
                "%Y-%m-%d"
            ).date()
        except ValueError:
            date_debut = None

    if date_fin_str:
        try:
            date_fin = datetime.strptime(
                date_fin_str,
                "%Y-%m-%d"
            ).date()
        except ValueError:
            date_fin = None

    # ---------------------------------------------------------
    # 5. Historique de la pharmacie connectée uniquement
    # ---------------------------------------------------------
    if pharmacie_obj:
        achats = (
            Stock.objects
            .filter(pharmacie=pharmacie_obj)
            .select_related(
                "medicament",
                "pharmacie",
                "utilisateur"
            )
            .order_by(
                "-date_achat",
                "-id"
            )
        )

        # Liste destinée au filtre médicament dans le template.
        medicaments = (
            pharmacie_obj.medicaments
            .all()
            .order_by("nom", "dosage")
        )

        # -----------------------------------------------------
        # Recherche : médicament, dosage, lot ou utilisateur
        # -----------------------------------------------------
        if recherche:
            achats = achats.filter(
                Q(medicament__nom__icontains=recherche) |
                Q(medicament__dosage__icontains=recherche) |
                Q(numero_lot__icontains=recherche) |
                Q(utilisateur__username__icontains=recherche) |
                Q(utilisateur__first_name__icontains=recherche) |
                Q(utilisateur__last_name__icontains=recherche)
            )

        # -----------------------------------------------------
        # Filtre médicament sélectionné
        # -----------------------------------------------------
        if medicament_id.isdigit():
            achats = achats.filter(
                medicament_id=int(medicament_id)
            )

        # -----------------------------------------------------
        # Filtre période d'achat
        # -----------------------------------------------------
        if date_debut and date_fin:
            achats = achats.filter(
                date_achat__range=(
                    date_debut,
                    date_fin
                )
            )

        elif date_debut:
            achats = achats.filter(
                date_achat__gte=date_debut
            )

        elif date_fin:
            achats = achats.filter(
                date_achat__lte=date_fin
            )

        # -----------------------------------------------------
        # 6. Statistiques sur les achats filtrés
        # -----------------------------------------------------
        total_achats = achats.count()

        total_cartons = (
            achats.aggregate(
                total=Sum("nombre_cartons")
            )["total"]
            or 0
        )

        total_pieces_achetees = (
            achats.aggregate(
                total=Sum("quantite_piece")
            )["total"]
            or 0
        )

        valeur_achat_expression = ExpressionWrapper(
            F("nombre_cartons") * F("prix_achat_carton"),
            output_field=DecimalField(
                max_digits=18,
                decimal_places=2
            )
        )

        montant_total_achat = (
            achats.aggregate(
                total=Sum(valeur_achat_expression)
            )["total"]
            or Decimal("0.00")
        )

    # ---------------------------------------------------------
    # 7. Pagination
    # ---------------------------------------------------------
    paginator = Paginator(achats, 15)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    # ---------------------------------------------------------
    # 8. Rôles pour tes include header.html / aside.html
    # ---------------------------------------------------------
    role_verify = (
        Role.objects
        .filter(userRole=request.user)
        .select_related("role")
    )

    roles = [
        role.role.nom_typeRole
        for role in role_verify
        if role.role
    ]

    roles_normalises = [
        role.lower().strip()
        for role in roles
    ]

    if "super admin" in roles_normalises:
        primary_role = "super admin"
    elif "admin" in roles_normalises:
        primary_role = "admin"
    else:
        primary_role = "visiteur"

    # ---------------------------------------------------------
    # 9. Affichage
    # ---------------------------------------------------------
    return render(
        request,
        "back-end/stocks/historique_achat_stock.html",
        {
            "achats": page_obj,
            "page_obj": page_obj,
            "paginator": paginator,

            "pharmacie_obj": pharmacie_obj,
            "name_phar": name_phar,

            "medicaments": medicaments,

            "recherche": recherche,
            "date_debut": date_debut_str,
            "date_fin": date_fin_str,
            "medicament_id": medicament_id,

            "total_achats": total_achats,
            "total_cartons": total_cartons,
            "total_pieces_achetees": total_pieces_achetees,
            "montant_total_achat": montant_total_achat,

            "primary_role": primary_role,
            "roles": roles,
        }
    )

# ------------------------------------------------------------------------
# EXPORTE EN FICHIER EXCEL 
# ------------------------------------------------------------------------
@login_required
def export_historique_achat_stock(request):
    import csv

    from datetime import datetime

    recherche = request.GET.get("q", "").strip()
    date_debut_str = request.GET.get("date_debut", "").strip()
    date_fin_str = request.GET.get("date_fin", "").strip()
    medicament_id = request.GET.get("medicament", "").strip()

    # Pharmacie de l'utilisateur connecté.
    pharmacie_obj = (
        Pharmacie.objects
        .filter(user_pharmacie=request.user)
        .first()
    )

    # Sécurité : pas d'export si l'utilisateur n'a pas de pharmacie.
    if pharmacie_obj is None:
        return HttpResponse(
            "Aucune pharmacie associée à votre compte.",
            status=403
        )

    # Tous les achats de la pharmacie connectée.
    achats = (
        Stock.objects
        .filter(pharmacie=pharmacie_obj)
        .select_related(
            "medicament",
            "pharmacie",
            "utilisateur"
        )
        .order_by("-date_achat", "-id")
    )

    # Recherche.
    if recherche:
        achats = achats.filter(
            Q(medicament__nom__icontains=recherche) |
            Q(medicament__dosage__icontains=recherche) |
            Q(numero_lot__icontains=recherche) |
            Q(utilisateur__username__icontains=recherche) |
            Q(utilisateur__first_name__icontains=recherche) |
            Q(utilisateur__last_name__icontains=recherche)
        )

    # Filtre médicament.
    if medicament_id.isdigit():
        achats = achats.filter(
            medicament_id=int(medicament_id)
        )

    # Conversion dates.
    date_debut = None
    date_fin = None

    if date_debut_str:
        try:
            date_debut = datetime.strptime(
                date_debut_str,
                "%Y-%m-%d"
            ).date()
        except ValueError:
            date_debut = None

    if date_fin_str:
        try:
            date_fin = datetime.strptime(
                date_fin_str,
                "%Y-%m-%d"
            ).date()
        except ValueError:
            date_fin = None

    # Filtre période.
    if date_debut and date_fin:
        achats = achats.filter(
            date_achat__range=(date_debut, date_fin)
        )

    elif date_debut:
        achats = achats.filter(
            date_achat__gte=date_debut
        )

    elif date_fin:
        achats = achats.filter(
            date_achat__lte=date_fin
        )

    # Réponse CSV compatible Excel.
    response = HttpResponse(
        content_type="text/csv; charset=utf-8"
    )

    response["Content-Disposition"] = (
        'attachment; filename="historique_achats_stock.csv"'
    )

    # BOM UTF-8 : Excel affiche correctement les accents.
    response.write("\ufeff")

    writer = csv.writer(
        response,
        delimiter=";"
    )

    writer.writerow([
        "Date achat",
        "Médicament",
        "Dosage",
        "Forme",
        "Numéro de lot",
        "Date péremption",
        "Nombre de cartons",
        "Quantité entrée",
        "Quantité restante",
        "Devise",
        "Prix achat carton",
        "Prix achat pièce",
        "Prix vente pièce",
        "Montant total achat",
        "Valeur vente potentielle",
        "Enregistré par",
        "Pharmacie",
    ])

    for achat in achats:
        nom_utilisateur = (
            achat.utilisateur.get_full_name().strip()
            or achat.utilisateur.username
        )

        writer.writerow([
            achat.date_achat.strftime("%d/%m/%Y"),
            achat.medicament.nom,
            achat.medicament.dosage or "",
            achat.medicament.get_forme_display(),
            achat.numero_lot,
            achat.date_peremption.strftime("%d/%m/%Y"),
            achat.nombre_cartons,
            achat.quantite_piece,
            achat.quantite_restante,
            achat.devise,
            achat.prix_achat_carton,
            achat.prix_achat_piece,
            achat.prix_vente_piece,
            achat.valeur_totale_achat,
            achat.valeur_totale_vente_potentielle,
            nom_utilisateur,
            achat.pharmacie.nom_pharmacie,
        ])

    return response

# -------------------------------------------------------------------------------------------------------------------
# MODIFICATION DE STOCK 
# -------------------------------------------------------------------------------------------------------------------
@login_required
def modifier_stock(request, stock_id):
    from django.contrib import messages
    # ---------------------------------------------------------
    # 1. Récupérer la pharmacie de l'utilisateur connecté
    # ---------------------------------------------------------
    pharmacie_obj = (
        Pharmacie.objects
        .filter(user_pharmacie=request.user)
        .first()
    )

    # Si l'utilisateur ne possède pas de pharmacie, il ne peut
    # pas modifier un stock.
    if pharmacie_obj is None:
        messages.error(
            request,
            "Vous devez d'abord créer votre pharmacie."
        )
        return redirect("liste_stock")

    # ---------------------------------------------------------
    # 2. Récupérer uniquement un stock de cette pharmacie
    #
    # Sécurité :
    # même si l'utilisateur écrit manuellement /modifier_stock/8/,
    # il ne peut pas modifier un lot d'une autre pharmacie.
    # ---------------------------------------------------------
    stock = get_object_or_404(
        Stock.objects.select_related(
            "medicament",
            "pharmacie",
            "utilisateur"
        ),
        id=stock_id,
        pharmacie=pharmacie_obj
    )

    name_phar = pharmacie_obj.nom_pharmacie

    # ---------------------------------------------------------
    # 3. Modifier le lot
    # ---------------------------------------------------------
    if request.method == "POST":
        form = StockModificationForm(
            request.POST,
            instance=stock,
            user=request.user
        )

        if form.is_valid():
            stock_modifie = form.save()

            messages.success(
                request,
                f"Le lot {stock_modifie.numero_lot} a été modifié avec succès."
            )

            return redirect(
                "detail_stock",
                stock_id=stock_modifie.id
            )
    else:
        form = StockModificationForm(
            instance=stock,
            user=request.user
        )

    # ---------------------------------------------------------
    # 4. Récupération des rôles pour header.html et aside.html
    # ---------------------------------------------------------
    role_verify = (
        Role.objects
        .filter(userRole=request.user)
        .select_related("role")
    )

    roles = [
        role.role.nom_typeRole
        for role in role_verify
        if role.role
    ]

    roles_normalises = [
        role.lower().strip()
        for role in roles
    ]

    if "super admin" in roles_normalises:
        primary_role = "super admin"
    elif "admin" in roles_normalises:
        primary_role = "admin"
    else:
        primary_role = "visiteur"

    # ---------------------------------------------------------
    # 5. Affichage du formulaire de modification
    # ---------------------------------------------------------
    return render(
        request,
        "back-end/stocks/stock_edit.html",
        {
            "form": form,
            "stock": stock,
            "pharmacie_obj": pharmacie_obj,
            "name_phar": name_phar,
            "primary_role": primary_role,
            "roles": roles,
        }
    )

# ---------------------------------------------------------------------------------------------
# Mouvement du stock
# ---------------------------------------------------------------------------------------------
@login_required
def liste_mouvements_stock(request):
    from datetime import datetime
    # ---------------------------------------------------------
    # 1. Pharmacie de l'utilisateur connecté
    # ---------------------------------------------------------
    pharmacie_obj = (
        Pharmacie.objects
        .filter(user_pharmacie=request.user)
        .first()
    )

    name_phar = (
        pharmacie_obj.nom_pharmacie
        if pharmacie_obj
        else "Aucune pharmacie créée"
    )

    # ---------------------------------------------------------
    # 2. Paramètres de recherche et filtres
    # ---------------------------------------------------------
    recherche = request.GET.get("q", "").strip()
    type_mouvement = request.GET.get(
        "type_mouvement",
        ""
    ).strip()

    date_debut_str = request.GET.get(
        "date_debut",
        ""
    ).strip()

    date_fin_str = request.GET.get(
        "date_fin",
        ""
    ).strip()

    # ---------------------------------------------------------
    # 3. Queryset limité à la pharmacie connectée
    # ---------------------------------------------------------
    mouvements = MouvementStock.objects.none()

    if pharmacie_obj:
        mouvements = (
            MouvementStock.objects
            .filter(pharmacie=pharmacie_obj)
            .select_related(
                "medicament",
                "stock",
                "utilisateur"
            )
            .order_by("-date_mouvement")
        )

        # Recherche sur médicament ou lot.
        if recherche:
            mouvements = mouvements.filter(
                Q(medicament__nom__icontains=recherche) |
                Q(medicament__dosage__icontains=recherche) |
                Q(stock__numero_lot__icontains=recherche)
            )

        # Filtre par type : ENTREE, VENTE, ANNULATION,
        # AJUSTEMENT, PEREMPTION, PERTE.
        if type_mouvement:
            mouvements = mouvements.filter(
                type_mouvement=type_mouvement
            )

        # -----------------------------------------------------
        # 4. Dates : conversion sécurisée du format HTML YYYY-MM-DD
        # -----------------------------------------------------
        date_debut = None
        date_fin = None

        if date_debut_str:
            try:
                date_debut = datetime.strptime(
                    date_debut_str,
                    "%Y-%m-%d"
                ).date()
            except ValueError:
                date_debut = None

        if date_fin_str:
            try:
                date_fin = datetime.strptime(
                    date_fin_str,
                    "%Y-%m-%d"
                ).date()
            except ValueError:
                date_fin = None

        if date_debut:
            mouvements = mouvements.filter(
                date_mouvement__date__gte=date_debut
            )

        if date_fin:
            mouvements = mouvements.filter(
                date_mouvement__date__lte=date_fin
            )

    # ---------------------------------------------------------
    # 5. Pagination
    # ---------------------------------------------------------
    paginator = Paginator(mouvements, 20)

    page_number = request.GET.get("page")

    page_obj = paginator.get_page(page_number)

    # ---------------------------------------------------------
    # 6. Gestion des rôles
    # ---------------------------------------------------------
    role_verify = (
        Role.objects
        .filter(userRole=request.user)
        .select_related("role")
    )

    roles = [
        role.role.nom_typeRole
        for role in role_verify
        if role.role
    ]

    roles_normalises = [
        role.lower().strip()
        for role in roles
    ]

    if "super admin" in roles_normalises:
        primary_role = "super admin"
    elif "admin" in roles_normalises:
        primary_role = "admin"
    else:
        primary_role = "visiteur"

    # ---------------------------------------------------------
    # 7. Template
    # ---------------------------------------------------------
    return render(
        request,
        "back-end/stocks/mouvement_stock_liste.html",
        {
            "mouvements": page_obj,
            "page_obj": page_obj,
            "paginator": paginator,

            "pharmacie_obj": pharmacie_obj,
            "name_phar": name_phar,

            "primary_role": primary_role,
            "roles": roles,

            "recherche": recherche,
            "type_mouvement_selectionne": type_mouvement,
            "date_debut": date_debut_str,
            "date_fin": date_fin_str,

            "types_mouvement": (
                MouvementStock.TypeMouvement.choices
            ),
        }
    )

# ---------------------------------------------------------------------------------------------
# LISTE DE MEDICAMENT PEREMPTIONS
# ---------------------------------------------------------------------------------------------
@login_required()
def liste_peremptions(request):
    
    pharmacie_obj = Pharmacie.objects.filter(user_pharmacie=request.user).first()
    name_phar = pharmacie_obj.nom_pharmacie if pharmacie_obj else 'pas de nom'

    stocks = Stock.objects.filter(pharmacie=pharmacie_obj) if pharmacie_obj else Stock.objects.none()
    stocks = stocks.select_related('medicament').filter(quantite_restante__gt=0)

    # nombre de jours à surveiller (par défaut 30)
    try:
        seuil_jours = int(request.GET.get('jours', 30))
    except ValueError:
        seuil_jours = 30

    aujourdhui = timezone.localdate()
    date_limite = aujourdhui + timedelta(days=seuil_jours)

    # lots déjà périmés
    stocks_perimes = stocks.filter(date_peremption__lt=aujourdhui).order_by('date_peremption')

    # lots qui périment bientôt (mais pas encore périmés)
    stocks_proches = stocks.filter(
        date_peremption__gte=aujourdhui,
        date_peremption__lte=date_limite
    ).order_by('date_peremption')

    # recherche par médicament
    recherche = request.GET.get('q', '').strip()
    if recherche:
        stocks_perimes = stocks_perimes.filter(medicament__nom__icontains=recherche)
        stocks_proches = stocks_proches.filter(medicament__nom__icontains=recherche)

    # gestion de role
    role_verify = Role.objects.filter(userRole=request.user).select_related('role')
    roles = [r.role.nom_typeRole for r in role_verify if r.role]

    if 'super admin' in roles:
        primary_role = 'super admin'
    elif 'admin' in roles:
        primary_role = 'admin'
    else:
        primary_role = 'visiteur'

    return render(request, 'back-end/stocks/peremptions_liste.html', {
        'stocks_perimes': stocks_perimes,
        'stocks_proches': stocks_proches,
        'primary_role': primary_role,
        'roles': roles,
        'name_phar': name_phar,
        'recherche': recherche,
        'seuil_jours': seuil_jours,
        'nb_perimes': stocks_perimes.count(),
        'nb_proches': stocks_proches.count(),
    })

# -------------------------------------------------------------------------------------
# LISTE DES STOCKS FAIBLES
# -------------------------------------------------------------------------------------
@login_required()
def liste_stock_faible(request):
    pharmacie_obj = Pharmacie.objects.filter(user_pharmacie=request.user).first()
    name_phar = pharmacie_obj.nom_pharmacie if pharmacie_obj else 'pas de nom'

    # seuil d'alerte réglable via l'URL (par défaut 10 pièces)
    try:
        seuil = int(request.GET.get('seuil', 10))
    except ValueError:
        seuil = 10

    medicaments = Medicament.objects.filter(pharmacie=pharmacie_obj) if pharmacie_obj else Medicament.objects.none()

    # somme des quantite_restante sur tous les lots actifs (non périmés) de chaque médicament
    medicaments = medicaments.annotate(
        stock_total=Sum(
            'stocks__quantite_restante',
            filter=models.Q(stocks__date_peremption__gte=timezone.localdate())
        )
    )

    # médicaments dont le stock total est en dessous du seuil (ou nul/aucun lot)
    medicaments_stock_faible = medicaments.filter(
        models.Q(stock_total__lt=seuil) | models.Q(stock_total__isnull=True)
    ).order_by('stock_total')

    # recherche par nom
    recherche = request.GET.get('q', '').strip()
    if recherche:
        medicaments_stock_faible = medicaments_stock_faible.filter(nom__icontains=recherche)

    # gestion de role
    role_verify = Role.objects.filter(userRole=request.user).select_related('role')
    roles = [r.role.nom_typeRole for r in role_verify if r.role]

    if 'super admin' in roles:
        primary_role = 'super admin'
    elif 'admin' in roles:
        primary_role = 'admin'
    else:
        primary_role = 'visiteur'

    return render(request, 'back-end/stocks/stock_faible_liste.html', {
        'medicaments_stock_faible': medicaments_stock_faible,
        'primary_role': primary_role,
        'roles': roles,
        'name_phar': name_phar,
        'recherche': recherche,
        'seuil': seuil,
        'nb_stock_faible': medicaments_stock_faible.count(),
    })

# -------------------------------------------------------------------------------------
# VENTE DE MEDICAMENT
# -------------------------------------------------------------------------------------
def recuperer_taux_actif(pharmacie_obj):
    """
    Récupère le taux actif USD -> CDF de la pharmacie.

    Exemple :
    1 USD = 2300 CDF
    retourne Decimal("2300.00").

    Retourne None si aucun taux actif n'existe.
    """
    if pharmacie_obj is None:
        return None

    taux_obj = (
        TauxChange.objects
        .filter(
            pharmacie=pharmacie_obj,
            est_actif=True
        )
        .first()
    )

    if taux_obj is None:
        return None

    return taux_obj.taux_usd_cdf

# -----------------------
@login_required
def creer_vente(request):
    # =========================================================
    # 1. PHARMACIE DE L'UTILISATEUR CONNECTÉ
    # =========================================================
    pharmacie_obj = (
        Pharmacie.objects
        .filter(user_pharmacie=request.user)
        .first()
    )

    name_phar = (
        pharmacie_obj.nom_pharmacie
        if pharmacie_obj
        else "Aucune pharmacie créée"
    )

    # =========================================================
    # 2. RÔLES POUR header.html ET aside.html
    # =========================================================
    role_verify = (
        Role.objects
        .filter(userRole=request.user)
        .select_related("role")
    )

    roles = [
        user_role.role.nom_typeRole
        for user_role in role_verify
        if user_role.role
    ]

    roles_normalises = [
        role.lower().strip()
        for role in roles
    ]

    if "super admin" in roles_normalises:
        primary_role = "super admin"

    elif "admin" in roles_normalises:
        primary_role = "admin"

    else:
        primary_role = "visiteur"

    # =========================================================
    # 3. SI AUCUNE PHARMACIE
    # =========================================================
    if pharmacie_obj is None:
        messages.error(
            request,
            "Vous devez d'abord créer votre pharmacie "
            "avant d'enregistrer une vente."
        )

        return render(
            request,
            "back-end/ventes/vente_form.html",
            {
                "form": VenteForm(),
                "formset": LigneVenteFormSet(),
                "pharmacie_obj": None,
                "name_phar": name_phar,
                "primary_role": primary_role,
                "roles": roles,
                "taux_usd_cdf": None,
            }
        )

    # =========================================================
    # 4. RÉCUPÉRER LE TAUX DE CHANGE DE CETTE PHARMACIE
    #
    # Ton modèle utilise :
    # related_name="taux_change"
    #
    # Donc le taux est accessible avec :
    # pharmacie_obj.taux_change
    # =========================================================
    try:
        taux_usd_cdf = pharmacie_obj.taux_change.taux_usd_cdf

    except TauxChange.DoesNotExist:
        taux_usd_cdf = None

    # =========================================================
    # 5. INSTANCE TEMPORAIRE POUR LE FORMSET
    # =========================================================
    vente_temporaire = Vente(
        pharmacie=pharmacie_obj,
        utilisateur=request.user
    )

    # =========================================================
    # 6. POST : ENREGISTRER LA VENTE
    # =========================================================
    if request.method == "POST":
        form = VenteForm(request.POST)

        formset = LigneVenteFormSet(
            request.POST,
            instance=vente_temporaire,
            form_kwargs={
                "pharmacie": pharmacie_obj,
            }
        )

        if form.is_valid() and formset.is_valid():
            try:
                with transaction.atomic():

                    # -------------------------------------------------
                    # A. CRÉER LA VENTE PRINCIPALE
                    # -------------------------------------------------
                    vente = form.save(commit=False)

                    vente.pharmacie = pharmacie_obj
                    vente.utilisateur = request.user
                    vente.statut = Vente.StatutVente.EN_ATTENTE

                    vente.save()

                    # -------------------------------------------------
                    # B. LIGNES DE VENTE ET SORTIE DE STOCK FEFO
                    # -------------------------------------------------
                    for ligne_form in formset.forms:
                        if not hasattr(
                            ligne_form,
                            "cleaned_data"
                        ):
                            continue

                        if ligne_form.cleaned_data.get("DELETE"):
                            continue

                        medicament = ligne_form.cleaned_data.get(
                            "medicament"
                        )

                        quantite_demandee = ligne_form.cleaned_data.get(
                            "quantite"
                        )

                        if not medicament or not quantite_demandee:
                            continue

                        # Lots disponibles, non périmés,
                        # classés FEFO et verrouillés.
                        #
                        # IMPORTANT :
                        # Pas de filtre par devise ici.
                        # La devise différente est seulement
                        # une question de paiement.
                        lots_fefo = list(
                            Stock.objects
                            .select_for_update()
                            .filter(
                                pharmacie=pharmacie_obj,
                                medicament=medicament,
                                quantite_restante__gt=0,
                                date_peremption__gt=(
                                    timezone.localdate()
                                )
                            )
                            .order_by(
                                "date_peremption",
                                "id"
                            )
                        )

                        stock_total = sum(
                            lot.quantite_restante
                            for lot in lots_fefo
                        )

                        if stock_total < quantite_demandee:
                            raise ValueError(
                                f"Stock insuffisant pour "
                                f"{medicament.nom} "
                                f"{medicament.dosage or ''}. "
                                f"Demandé : {quantite_demandee} pièce(s), "
                                f"disponible : {stock_total} pièce(s)."
                            )

                        # La demande peut être répartie automatiquement
                        # sur plusieurs lots suivant FEFO.
                        quantite_restante_a_vendre = (
                            quantite_demandee
                        )

                        for lot in lots_fefo:
                            if quantite_restante_a_vendre <= 0:
                                break

                            quantite_du_lot = min(
                                quantite_restante_a_vendre,
                                lot.quantite_restante
                            )

                            quantite_avant = lot.quantite_restante

                            # Déduire le stock.
                            lot.quantite_restante = (
                                lot.quantite_restante -
                                quantite_du_lot
                            )

                            lot.save(
                                update_fields=[
                                    "quantite_restante"
                                ]
                            )

                            # Créer la ligne de vente.
                            # Prix figé depuis le lot.
                            LigneVente.objects.create(
                                vente=vente,
                                medicament=medicament,
                                stock=lot,
                                quantite=quantite_du_lot,
                                prix_unitaire=(
                                    lot.prix_vente_piece
                                )
                            )

                            # Tracer la sortie de stock.
                            MouvementStock.objects.create(
                                stock=lot,
                                medicament=medicament,
                                pharmacie=pharmacie_obj,
                                utilisateur=request.user,
                                type_mouvement=(
                                    MouvementStock.TypeMouvement.VENTE
                                ),
                                quantite=quantite_du_lot,
                                quantite_avant=quantite_avant,
                                quantite_apres=(
                                    lot.quantite_restante
                                ),
                                motif=f"Vente #{vente.id}"
                            )

                            quantite_restante_a_vendre -= (
                                quantite_du_lot
                            )

                    # -------------------------------------------------
                    # C. PAIEMENT INITIAL ET CONVERSION USD / CDF
                    # -------------------------------------------------
                    paiement_initial = (
                        form.cleaned_data.get(
                            "paiement_initial"
                        ) or Decimal("0.00")
                    )

                    # Devise que le client donne réellement.
                    # Exemple : client donne USD pour une vente CDF.
                    devise_paiement = (
                        form.cleaned_data.get(
                            "devise_paiement"
                        ) or vente.devise
                    )

                    mode_paiement = (
                        form.cleaned_data.get(
                            "mode_paiement"
                        ) or PaiementVente.ModePaiement.ESPECES
                    )

                    if paiement_initial > Decimal("0.00"):
                        taux_applique = None

                        # Si le paiement est dans une devise
                        # différente de celle de la facture :
                        # récupérer et verrouiller le taux ACTIF de cette
                        # pharmacie pour l'archiver dans le paiement.
                        if devise_paiement != vente.devise:
                            taux_obj = (
                                TauxChange.objects
                                .select_for_update()
                                .filter(
                                    pharmacie=pharmacie_obj,
                                    est_actif=True
                                )
                                .first()
                            )

                            if (
                                taux_obj is None or
                                taux_obj.taux_usd_cdf is None or
                                taux_obj.taux_usd_cdf <= Decimal("0.00")
                            ):
                                raise ValueError(
                                    "Paiement impossible : aucun "
                                    "taux USD/CDF actif n'est "
                                    "enregistré pour cette pharmacie."
                                )

                            taux_applique = (
                                taux_obj.taux_usd_cdf
                            )

                        # Le modèle PaiementVente doit :
                        # - calculer montant_equivalent_vente ;
                        # - vérifier le montant restant ;
                        # - refuser un dépassement ;
                        # - mettre à jour le statut de la vente.
                        PaiementVente.objects.create(
                            vente=vente,
                            utilisateur=request.user,
                            montant=paiement_initial,
                            devise_paiement=devise_paiement,
                            taux_usd_cdf_applique=taux_applique,
                            mode_paiement=mode_paiement
                        )

                    # EN_ATTENTE / PARTIELLEMENT_PAYEE / PAYEE.
                    vente.actualiser_statut()

                # -----------------------------------------------------
                # FIN DE TRANSACTION : VENTE VALIDÉE
                # -----------------------------------------------------
                messages.success(
                    request,
                    f"Vente #{vente.id} enregistrée avec succès. "
                    f"Total : {vente.montant_total} "
                    f"{vente.devise}. "
                    f"Reste à payer : {vente.montant_restant} "
                    f"{vente.devise}."
                )

                return redirect(
                    "detail_vente",
                    vente_id=vente.id
                )

            except ValueError as erreur:
                form.add_error(
                    None,
                    str(erreur)
                )

            except Exception as erreur:
                form.add_error(
                    None,
                    f"Erreur lors de l'enregistrement : "
                    f"{erreur}"
                )

    # =========================================================
    # 7. GET : FORMULAIRE VIDE
    # =========================================================
    else:
        form = VenteForm(
            initial={
                # Devise de la facture / de la dette.
                "devise": "CDF",

                # 0 = vente à crédit.
                "paiement_initial": "0.00",

                # Devise physique remise par le client.
                "devise_paiement": "CDF",

                "mode_paiement": (
                    PaiementVente.ModePaiement.ESPECES
                ),
            }
        )

        formset = LigneVenteFormSet(
            instance=vente_temporaire,
            form_kwargs={
                "pharmacie": pharmacie_obj,
            }
        )

    # =========================================================
    # 8. AFFICHER LE TEMPLATE
    # =========================================================
    return render(
        request,
        "back-end/ventes/vente_form.html",
        {
            "form": form,
            "formset": formset,

            "pharmacie_obj": pharmacie_obj,
            "name_phar": name_phar,

            "primary_role": primary_role,
            "roles": roles,

            # Pour afficher le taux dans le HTML.
            "taux_usd_cdf": taux_usd_cdf,
        }
    )
# -----------------------------------------------------------------------------------------------------
# detail vente 
# -----------------------------------------------------------------------------------------------------
@login_required
def detail_vente(request, vente_id):
    # =========================================================
    # 1. RÉCUPÉRER LA PHARMACIE DU USER CONNECTÉ
    # =========================================================
    pharmacie_obj = (
        Pharmacie.objects
        .filter(user_pharmacie=request.user)
        .first()
    )

    name_phar = (
        pharmacie_obj.nom_pharmacie
        if pharmacie_obj
        else "Aucune pharmacie créée"
    )

    # =========================================================
    # 2. RÉCUPÉRER LA VENTE UNIQUEMENT DANS CETTE PHARMACIE
    #
    # Sécurité :
    # un utilisateur ne peut consulter que les ventes de sa
    # propre pharmacie.
    # =========================================================
    vente = get_object_or_404(
        Vente.objects
        .select_related(
            "pharmacie",
            "utilisateur"
        )
        .prefetch_related(
            "lignes__medicament",
            "lignes__stock",
            "paiements",
            "paiements__utilisateur"
        ),
        id=vente_id,
        pharmacie=pharmacie_obj
    )

    # =========================================================
    # 3. LIGNES DE VENTE
    # =========================================================
    lignes = vente.lignes.all()

    nombre_lignes = lignes.count()

    total_quantite = sum(
        ligne.quantite
        for ligne in lignes
    )

    # =========================================================
    # 4. PAIEMENTS DE LA VENTE
    #
    # Chaque paiement contient :
    # - montant : ce que le client a remis réellement ;
    # - devise_paiement : CDF ou USD ;
    # - montant_equivalent_vente : valeur convertie dans la
    #   devise de la vente.
    # =========================================================
    paiements = vente.paiements.all()

    nombre_paiements = paiements.count()

    # Total réellement encaissé physiquement en CDF.
    total_recu_cdf = sum(
        (
            paiement.montant
            for paiement in paiements
            if paiement.devise_paiement == "CDF"
        ),
        Decimal("0.00")
    )

    # Total réellement encaissé physiquement en USD.
    total_recu_usd = sum(
        (
            paiement.montant
            for paiement in paiements
            if paiement.devise_paiement == "USD"
        ),
        Decimal("0.00")
    )

    # Somme de tous les paiements convertis dans la devise
    # de la facture/vente.
    total_paye_equivalent = sum(
        (
            paiement.montant_equivalent_vente
            for paiement in paiements
        ),
        Decimal("0.00")
    )

    # Le modèle Vente calcule normalement déjà ceci.
    # Cette variable est envoyée au template pour être claire.
    reste_a_payer = vente.montant_restant

    # =========================================================
    # 5. RÔLES POUR header.html ET aside.html
    # =========================================================
    role_verify = (
        Role.objects
        .filter(userRole=request.user)
        .select_related("role")
    )

    roles = [
        user_role.role.nom_typeRole
        for user_role in role_verify
        if user_role.role
    ]

    roles_normalises = [
        role.lower().strip()
        for role in roles
    ]

    if "super admin" in roles_normalises:
        primary_role = "super admin"

    elif "admin" in roles_normalises:
        primary_role = "admin"

    else:
        primary_role = "visiteur"

    # =========================================================
    # 6. AFFICHER LA PAGE
    # =========================================================
    return render(
        request,
        "back-end/ventes/vente_detail.html",
        {
            # Vente
            "vente": vente,
            "lignes": lignes,
            "nombre_lignes": nombre_lignes,
            "total_quantite": total_quantite,

            # Paiements
            "paiements": paiements,
            "nombre_paiements": nombre_paiements,

            # Sommes reçues dans les devises physiques
            "total_recu_cdf": total_recu_cdf,
            "total_recu_usd": total_recu_usd,

            # Somme convertie dans la devise de vente
            "total_paye_equivalent": total_paye_equivalent,
            "reste_a_payer": reste_a_payer,

            # Header et aside
            "pharmacie_obj": pharmacie_obj,
            "name_phar": name_phar,
            "primary_role": primary_role,
            "roles": roles,
        }
    )

# --------------------------------------------------------------------------------------
#  API POUR LE PAIEMENT
# --------------------------------------------------------------------------------------
@login_required
def api_medicament_vente(request, medicament_id):
    # Récupérer la pharmacie du user connecté.
    pharmacie_obj = (
        Pharmacie.objects
        .filter(user_pharmacie=request.user)
        .first()
    )

    if pharmacie_obj is None:
        return JsonResponse(
            {
                "success": False,
                "message": (
                    "Aucune pharmacie n'est associée "
                    "à cet utilisateur."
                )
            },
            status=403
        )

    # Récupérer le médicament seulement s'il appartient
    # à la pharmacie de l'utilisateur connecté.
    medicament = (
        Medicament.objects
        .filter(
            id=medicament_id,
            pharmacie=pharmacie_obj
        )
        .first()
    )

    if medicament is None:
        return JsonResponse(
            {
                "success": False,
                "message": (
                    "Médicament introuvable dans votre pharmacie."
                )
            },
            status=404
        )

    # Lots disponibles, non périmés, rangés selon FEFO.
    lots = (
        Stock.objects
        .filter(
            pharmacie=pharmacie_obj,
            medicament=medicament,
            quantite_restante__gt=0,
            date_peremption__gt=timezone.localdate()
        )
        .order_by(
            "date_peremption",
            "id"
        )
    )

    # Premier lot qui expire : lot FEFO.
    lot_fefo = lots.first()

    if lot_fefo is None:
        return JsonResponse(
            {
                "success": False,
                "message": (
                    "Aucun lot disponible et non périmé "
                    "pour ce médicament."
                )
            },
            status=404
        )

    # Somme de tous les lots disponibles pour ce médicament.
    stock_total = sum(
        lot.quantite_restante
        for lot in lots
    )

    return JsonResponse(
        {
            "success": True,

            "medicament": {
                "id": medicament.id,
                "nom": medicament.nom,
                "dosage": medicament.dosage or "",
                "forme": medicament.get_forme_display(),
            },

            "fefo": {
                "numero_lot": lot_fefo.numero_lot,
                "date_peremption": (
                    lot_fefo.date_peremption.strftime("%d/%m/%Y")
                ),
                "quantite_restante": lot_fefo.quantite_restante,
            },

            "stock_total": stock_total,

            "prix_vente_piece": str(
                lot_fefo.prix_vente_piece
            ),

            "devise": lot_fefo.devise,
        }
    )

# --------------------------------------------------------------------------------
# PAIEMENT DE LA DETTE MEDICAMENT
# --------------------------------------------------------------------------------
@login_required
def ajouter_reglement_vente(request, vente_id):
    # =========================================================
    # 1. PHARMACIE DU USER CONNECTÉ
    # =========================================================
    pharmacie_obj = (
        Pharmacie.objects
        .filter(user_pharmacie=request.user)
        .first()
    )

    if pharmacie_obj is None:
        messages.error(
            request,
            "Aucune pharmacie n'est associée à votre compte."
        )

        return redirect("creer_vente")

    # =========================================================
    # 2. VENTE DE LA MÊME PHARMACIE
    # =========================================================
    vente = get_object_or_404(
        Vente.objects,
        id=vente_id,
        pharmacie=pharmacie_obj
    )

    # Une vente annulée ne peut pas recevoir un paiement.
    if vente.statut == Vente.StatutVente.ANNULEE:
        messages.error(
            request,
            "Impossible d'enregistrer un paiement "
            "sur une vente annulée."
        )

        return redirect(
            "detail_vente",
            vente_id=vente.id
        )

    # Une vente déjà soldée ne doit pas recevoir un autre paiement.
    if vente.est_soldee:
        messages.info(
            request,
            "Cette vente est déjà entièrement payée."
        )

        return redirect(
            "detail_vente",
            vente_id=vente.id
        )

    # =========================================================
    # 3. POST : CRÉATION DU RÈGLEMENT
    # =========================================================
    if request.method == "POST":
        form = ReglementVenteForm(request.POST)

        if form.is_valid():
            try:
                with transaction.atomic():
                    # Verrouille la vente afin d'empêcher deux
                    # caissiers de payer le même reste en même temps.
                    vente_verrouillee = (
                        Vente.objects
                        .select_for_update()
                        .get(
                            id=vente.id,
                            pharmacie=pharmacie_obj
                        )
                    )

                    reglement = form.save(commit=False)

                    reglement.vente = vente_verrouillee
                    reglement.utilisateur = request.user

                    # Si le client paie dans une autre devise
                    # que la vente, récupérer le taux ACTIF de la pharmacie.
                    if (
                        reglement.devise_paiement !=
                        vente_verrouillee.devise
                    ):
                        taux_obj = (
                            TauxChange.objects
                            .select_for_update()
                            .filter(
                                pharmacie=pharmacie_obj,
                                est_actif=True
                            )
                            .first()
                        )

                        if (
                            taux_obj is None or
                            taux_obj.taux_usd_cdf is None or
                            taux_obj.taux_usd_cdf <= Decimal("0.00")
                        ):
                            raise ValueError(
                                "Aucun taux USD/CDF actif n'est "
                                "enregistré pour cette pharmacie."
                            )

                        reglement.taux_usd_cdf_applique = (
                            taux_obj.taux_usd_cdf
                        )

                    # Le save() du modèle PaiementVente :
                    # - calcule montant_equivalent_vente ;
                    # - vérifie le solde ;
                    # - refuse les dépassements ;
                    # - actualise le statut de la vente.
                    reglement.save()

                messages.success(
                    request,
                    f"Paiement enregistré avec succès. "
                    f"Reste à payer : "
                    f"{vente_verrouillee.montant_restant} "
                    f"{vente_verrouillee.devise}."
                )

                return redirect(
                    "detail_vente",
                    vente_id=vente_verrouillee.id
                )

            except ValueError as erreur:
                form.add_error(
                    None,
                    str(erreur)
                )

            except Exception as erreur:
                form.add_error(
                    None,
                    f"Erreur lors du règlement : {erreur}"
                )

    # =========================================================
    # 4. GET : AFFICHER LE FORMULAIRE
    # =========================================================
    else:
        form = ReglementVenteForm(
            initial={
                "devise_paiement": vente.devise,
                "mode_paiement": (
                    PaiementVente.ModePaiement.ESPECES
                ),
            }
        )

    # =========================================================
    # 5. RÔLES POUR LES INCLUDES
    # =========================================================
    role_verify = (
        Role.objects
        .filter(userRole=request.user)
        .select_related("role")
    )

    roles = [
        user_role.role.nom_typeRole
        for user_role in role_verify
        if user_role.role
    ]

    roles_normalises = [
        role.lower().strip()
        for role in roles
    ]

    if "super admin" in roles_normalises:
        primary_role = "super admin"
    elif "admin" in roles_normalises:
        primary_role = "admin"
    else:
        primary_role = "visiteur"

    try:
        taux_usd_cdf = pharmacie_obj.taux_change.taux_usd_cdf
    except TauxChange.DoesNotExist:
        taux_usd_cdf = None

    return render(
        request,
        "back-end/ventes/reglement_vente.html",
        {
            "form": form,
            "vente": vente,
            "pharmacie_obj": pharmacie_obj,
            "name_phar": pharmacie_obj.nom_pharmacie,
            "primary_role": primary_role,
            "roles": roles,
            "taux_usd_cdf": taux_usd_cdf,
        }
    )

# --------------------------------------------------------------------------------------
#  LISTE DES VENTES 
# --------------------------------------------------------------------------------------
@login_required
def liste_ventes(request):
    # =========================================================
    # 1. RÉCUPÉRER LA PHARMACIE DU USER CONNECTÉ
    # =========================================================
    pharmacie_obj = (
        Pharmacie.objects
        .filter(user_pharmacie=request.user)
        .first()
    )

    # Si aucune pharmacie n'est liée au user.
    if pharmacie_obj is None:
        messages.error(
            request,
            "Vous devez d'abord créer votre pharmacie "
            "avant de consulter les ventes."
        )

        return redirect("creer_vente")

    name_phar = pharmacie_obj.nom_pharmacie

    # =========================================================
    # 2. RÔLES POUR header.html ET aside.html
    # =========================================================
    role_verify = (
        Role.objects
        .filter(userRole=request.user)
        .select_related("role")
    )

    roles = [
        user_role.role.nom_typeRole
        for user_role in role_verify
        if user_role.role
    ]

    roles_normalises = [
        role.lower().strip()
        for role in roles
    ]

    if "super admin" in roles_normalises:
        primary_role = "super admin"

    elif "admin" in roles_normalises:
        primary_role = "admin"

    else:
        primary_role = "visiteur"

    # =========================================================
    # 3. RÉCUPÉRER LES VENTES DE CETTE PHARMACIE UNIQUEMENT
    # =========================================================
    ventes = (
        Vente.objects
        .filter(pharmacie=pharmacie_obj)
        .select_related(
            "utilisateur",
            "pharmacie"
        )
        .prefetch_related(
            "lignes",
            "paiements"
        )
        .order_by("-date_vente")
    )

    # =========================================================
    # 4. RECHERCHE : NUMÉRO, NOM CLIENT OU TÉLÉPHONE
    #
    # Exemple :
    # ?q=Jean
    # ?q=0812345678
    # ?q=15
    # =========================================================
    recherche = request.GET.get(
        "q",
        ""
    ).strip()

    if recherche:
        recherches = (
            Q(client_nom__icontains=recherche) |
            Q(client_telephone__icontains=recherche)
        )

        # Si la recherche est un nombre,
        # chercher aussi par numéro de vente.
        if recherche.isdigit():
            recherches |= Q(id=int(recherche))

        ventes = ventes.filter(
            recherches
        )

    # =========================================================
    # 5. FILTRE PAR STATUT
    #
    # Exemples :
    # ?statut=EN_ATTENTE
    # ?statut=PARTIELLEMENT_PAYEE
    # ?statut=PAYEE
    # =========================================================
    statut_selectionne = request.GET.get(
        "statut",
        ""
    ).strip()

    statuts_valides = [
        valeur
        for valeur, label in Vente.StatutVente.choices
    ]

    if statut_selectionne in statuts_valides:
        ventes = ventes.filter(
            statut=statut_selectionne
        )

    # =========================================================
    # 6. STATISTIQUES RAPIDES DE LA LISTE
    #
    # Les ventes sont toutes dans la même pharmacie,
    # mais elles peuvent être en CDF ou USD.
    # Donc on compte séparément les devises.
    # =========================================================
    total_ventes = ventes.count()

    ventes_payees = ventes.filter(
        statut=Vente.StatutVente.PAYEE
    ).count()

    ventes_partiellement_payees = ventes.filter(
        statut=Vente.StatutVente.PARTIELLEMENT_PAYEE
    ).count()

    ventes_en_attente = ventes.filter(
        statut=Vente.StatutVente.EN_ATTENTE
    ).count()

    # =========================================================
    # 7. PAGINATION : 15 VENTES PAR PAGE
    # =========================================================
    paginator = Paginator(
        ventes,
        15
    )

    numero_page = request.GET.get(
        "page"
    )

    page_obj = paginator.get_page(
        numero_page
    )

    # =========================================================
    # 8. AFFICHER LE TEMPLATE
    # =========================================================
    return render(
        request,
        "back-end/ventes/liste_ventes.html",
        {
            # Liste paginée.
            "page_obj": page_obj,
            "ventes": page_obj.object_list,

            # Filtres.
            "recherche": recherche,
            "statut_selectionne": statut_selectionne,
            "statuts": Vente.StatutVente.choices,

            # Compteurs.
            "total_ventes": total_ventes,
            "ventes_payees": ventes_payees,
            "ventes_partiellement_payees": (
                ventes_partiellement_payees
            ),
            "ventes_en_attente": ventes_en_attente,

            # Includes header et aside.
            "pharmacie_obj": pharmacie_obj,
            "name_phar": name_phar,
            "primary_role": primary_role,
            "roles": roles,
        }
    )

# ----------------------------------------------------------------------------------------------
# ANNULE UNE VENTE 
# ----------------------------------------------------------------------------------------------
@login_required
def annuler_vente(request, vente_id):
    # =========================================================
    # 1. PHARMACIE DU USER CONNECTÉ
    # =========================================================
    pharmacie_obj = (
        Pharmacie.objects
        .filter(user_pharmacie=request.user)
        .first()
    )

    if pharmacie_obj is None:
        messages.error(
            request,
            "Aucune pharmacie n'est associée à votre compte."
        )

        return redirect("liste_ventes")

    # Pour éviter une annulation depuis une simple URL GET.
    if request.method != "POST":
        messages.error(
            request,
            "L'annulation doit être confirmée."
        )

        return redirect(
            "detail_vente",
            vente_id=vente_id
        )

    try:
        with transaction.atomic():

            # =================================================
            # 2. VERROUILLER LA VENTE
            # =================================================
            vente = (
                Vente.objects
                .select_for_update()
                .select_related(
                    "pharmacie",
                    "utilisateur"
                )
                .get(
                    id=vente_id,
                    pharmacie=pharmacie_obj
                )
            )

            # =================================================
            # 3. EMPÊCHER UNE DOUBLE ANNULATION
            # =================================================
            if vente.statut == Vente.StatutVente.ANNULEE:
                raise ValueError(
                    "Cette vente est déjà annulée."
                )

            # =================================================
            # 4. CHOIX MÉTIER :
            #
            # Cette règle bloque l'annulation si un paiement
            # existe déjà. Tu peux enlever ce bloc si tu veux
            # permettre l'annulation avec remboursement.
            # =================================================
            if vente.montant_paye > 0:
                raise ValueError(
                    "Impossible d'annuler cette vente car "
                    "elle possède déjà un paiement enregistré. "
                    "Créez d'abord un remboursement ou annulez "
                    "les règlements selon votre procédure."
                )

            # =================================================
            # 5. REMETTRE CHAQUE LIGNE DANS SON LOT
            # =================================================
            lignes = (
                vente.lignes
                .select_related(
                    "stock",
                    "medicament"
                )
                .all()
            )

            for ligne in lignes:
                # Verrouiller le stock/lot concerné.
                stock = (
                    Stock.objects
                    .select_for_update()
                    .get(
                        id=ligne.stock_id,
                        pharmacie=pharmacie_obj
                    )
                )

                quantite_avant = stock.quantite_restante

                # Remettre la quantité dans le lot.
                stock.quantite_restante = (
                    stock.quantite_restante +
                    ligne.quantite
                )

                stock.save(
                    update_fields=[
                        "quantite_restante"
                    ]
                )

                # Créer une trace de retour du stock.
                MouvementStock.objects.create(
                    stock=stock,
                    medicament=ligne.medicament,
                    pharmacie=pharmacie_obj,
                    utilisateur=request.user,
                    type_mouvement=(
                        MouvementStock.TypeMouvement.ANNULATION
                    ),
                    quantite=ligne.quantite,
                    quantite_avant=quantite_avant,
                    quantite_apres=stock.quantite_restante,
                    motif=(
                        f"Annulation de la vente "
                        f"#{vente.id}"
                    )
                )

            # =================================================
            # 6. PASSER LA VENTE À ANNULEE
            # =================================================
            vente.statut = Vente.StatutVente.ANNULEE

            vente.save(
                update_fields=[
                    "statut"
                ]
            )

        messages.success(
            request,
            f"Vente #{vente.id} annulée avec succès. "
            "Le stock a été remis à jour."
        )

    except Vente.DoesNotExist:
        messages.error(
            request,
            "Vente introuvable ou non autorisée."
        )

    except ValueError as erreur:
        messages.error(
            request,
            str(erreur)
        )

    return redirect(
        "detail_vente",
        vente_id=vente_id
    )


# -------------------------------------------------------------------------------------------
# ANNULE PARTIELEMENT
# -------------------------------------------------------------------------------------------
@login_required
def retour_partiel_vente(request, vente_id):
    # =========================================================
    # 1. PHARMACIE DU USER CONNECTÉ
    # =========================================================
    pharmacie_obj = (
        Pharmacie.objects
        .filter(user_pharmacie=request.user)
        .first()
    )

    if pharmacie_obj is None:
        messages.error(
            request,
            "Aucune pharmacie n'est associée à votre compte."
        )

        return redirect("liste_ventes")

    # =========================================================
    # 2. RÉCUPÉRER LA VENTE DE LA PHARMACIE CONNECTÉE
    # =========================================================
    vente = get_object_or_404(
        Vente.objects
        .select_related("pharmacie", "utilisateur")
        .prefetch_related("lignes__medicament", "lignes__stock"),
        id=vente_id,
        pharmacie=pharmacie_obj
    )

    # Une vente annulée totalement ne peut plus avoir de retour partiel.
    if vente.statut == Vente.StatutVente.ANNULEE:
        messages.error(
            request,
            "Impossible d'effectuer un retour sur une vente annulée."
        )

        return redirect(
            "detail_vente",
            vente_id=vente.id
        )

    # =========================================================
    # 3. LIGNES DE LA VENTE
    # =========================================================
    lignes = (
        vente.lignes
        .select_related("medicament", "stock")
        .all()
    )

    # Important pour le template :
    # quantité que le client peut encore retourner pour chaque ligne.
    #
    # Exemple :
    # quantité vendue = 10
    # déjà retournée = 3
    # quantité possible = 7
    for ligne in lignes:
        ligne.quantite_possible_retour = (
            ligne.quantite -
            ligne.quantite_retournee
        )

    # Données initiales du FormSet.
    donnees_initiales = [
        {
            "ligne_vente_id": ligne.id,
            "quantite_retour": 0,
        }
        for ligne in lignes
    ]

    # =========================================================
    # 4. POST : ENREGISTRER L'ANNULATION PARTIELLE
    # =========================================================
    if request.method == "POST":
        formset = RetourLigneVenteFormSet(request.POST)

        if formset.is_valid():
            try:
                with transaction.atomic():

                    # Verrouillage de la vente pour éviter les retours
                    # simultanés effectués par deux utilisateurs.
                    vente_verrouillee = (
                        Vente.objects
                        .select_for_update()
                        .get(
                            id=vente.id,
                            pharmacie=pharmacie_obj
                        )
                    )

                    # Vérification supplémentaire après verrouillage.
                    if vente_verrouillee.statut == Vente.StatutVente.ANNULEE:
                        raise ValueError(
                            "Cette vente est déjà annulée."
                        )

                    retour_effectue = False

                    # Parcours de tous les formulaires du FormSet.
                    for retour_form in formset:
                        ligne_vente_id = (
                            retour_form.cleaned_data.get(
                                "ligne_vente_id"
                            )
                        )

                        quantite_retour = (
                            retour_form.cleaned_data.get(
                                "quantite_retour"
                            ) or 0
                        )

                        # Rien à faire si le vendeur a laissé 0.
                        if quantite_retour <= 0:
                            continue

                        # La ligne doit obligatoirement appartenir
                        # à cette vente précise.
                        ligne = (
                            LigneVente.objects
                            .select_for_update()
                            .select_related(
                                "medicament",
                                "stock"
                            )
                            .get(
                                id=ligne_vente_id,
                                vente=vente_verrouillee
                            )
                        )

                        # Quantité encore autorisée au retour.
                        quantite_possible = (
                            ligne.quantite -
                            ligne.quantite_retournee
                        )

                        if quantite_possible <= 0:
                            raise ValueError(
                                f"Le médicament "
                                f"« {ligne.medicament.nom} » "
                                f"a déjà été entièrement retourné."
                            )

                        if quantite_retour > quantite_possible:
                            raise ValueError(
                                f"Retour impossible pour "
                                f"{ligne.medicament.nom} "
                                f"{ligne.medicament.dosage or ''}. "
                                f"Le client peut retourner au maximum "
                                f"{quantite_possible} pièce(s)."
                            )

                        # Verrouillage du lot de stock utilisé pendant
                        # la vente afin de remettre le retour dans ce lot.
                        stock = (
                            Stock.objects
                            .select_for_update()
                            .get(
                                id=ligne.stock_id,
                                pharmacie=pharmacie_obj
                            )
                        )

                        quantite_avant = stock.quantite_restante

                        # Remettre les pièces retournées dans le lot.
                        stock.quantite_restante = (
                            stock.quantite_restante +
                            quantite_retour
                        )

                        stock.save(
                            update_fields=[
                                "quantite_restante"
                            ]
                        )

                        # Sauvegarder la quantité déjà retournée
                        # dans la ligne de vente.
                        ligne.quantite_retournee = (
                            ligne.quantite_retournee +
                            quantite_retour
                        )

                        ligne.save(
                            update_fields=[
                                "quantite_retournee"
                            ]
                        )

                        # Créer l'historique du mouvement de stock.
                        MouvementStock.objects.create(
                            stock=stock,
                            medicament=ligne.medicament,
                            pharmacie=pharmacie_obj,
                            utilisateur=request.user,
                            type_mouvement=(
                                MouvementStock.TypeMouvement.RETOUR_CLIENT
                            ),
                            quantite=quantite_retour,
                            quantite_avant=quantite_avant,
                            quantite_apres=stock.quantite_restante,
                            motif=(
                                f"Retour partiel client - "
                                f"Vente #{vente_verrouillee.id}"
                            )
                        )

                        retour_effectue = True

                    # Le formulaire ne peut pas être envoyé avec
                    # toutes les quantités à zéro.
                    if not retour_effectue:
                        raise ValueError(
                            "Saisissez au moins une quantité "
                            "supérieure à zéro à retourner."
                        )

                    # Cette méthode doit recalculer :
                    # - montant_total ;
                    # - montant_restant ;
                    # - statut de vente ;
                    # - éventuel trop-perçu.
                    vente_verrouillee.actualiser_statut()

                messages.success(
                    request,
                    f"Annulation partielle enregistrée avec succès. "
                    f"Nouveau total : "
                    f"{vente_verrouillee.montant_total} "
                    f"{vente_verrouillee.devise}. "
                    f"Reste à payer : "
                    f"{vente_verrouillee.montant_restant} "
                    f"{vente_verrouillee.devise}."
                )

                return redirect(
                    "detail_vente",
                    vente_id=vente_verrouillee.id
                )

            except LigneVente.DoesNotExist:
                formset.add_error(
                    None,
                    "Une ligne de vente est introuvable ou "
                    "ne correspond pas à cette vente."
                )

            except Stock.DoesNotExist:
                formset.add_error(
                    None,
                    "Le lot de stock concerné est introuvable."
                )

            except ValueError as erreur:
                formset.add_error(
                    None,
                    str(erreur)
                )

    # =========================================================
    # 5. GET : AFFICHER LE FORMULAIRE
    # =========================================================
    else:
        formset = RetourLigneVenteFormSet(
            initial=donnees_initiales
        )

    # =========================================================
    # 6. LIER CHAQUE FORMULAIRE À SA LIGNE DE VENTE
    # =========================================================
    # Très important :
    # Le template doit faire :
    #
    # {% for ligne, retour_form in lignes_formulaires %}
    #
    # Cela corrige l'erreur :
    # Failed lookup for key [quantite_retournee] in ''
    lignes_formulaires = list(zip(lignes, formset))

    # =========================================================
    # 7. RÔLES POUR NAVBAR / SIDEBAR
    # =========================================================
    role_verify = (
        Role.objects
        .filter(userRole=request.user)
        .select_related("role")
    )

    roles = [
        user_role.role.nom_typeRole
        for user_role in role_verify
        if user_role.role
    ]

    roles_normalises = [
        role.lower().strip()
        for role in roles
    ]

    if "super admin" in roles_normalises:
        primary_role = "super admin"

    elif "admin" in roles_normalises:
        primary_role = "admin"

    else:
        primary_role = "visiteur"

    # =========================================================
    # 8. AFFICHER LE TEMPLATE
    # =========================================================
    return render(
        request,
        "back-end/ventes/retour_partiel_vente.html",
        {
            "vente": vente,
            "lignes": lignes,
            "formset": formset,

            # Utilise cette variable dans le HTML.
            "lignes_formulaires": lignes_formulaires,

            "pharmacie_obj": pharmacie_obj,
            "name_phar": pharmacie_obj.nom_pharmacie,

            "primary_role": primary_role,
            "roles": roles,
        }
    )


# ----------------------------------------------------------------------------------------------------------
# RAPPORT FINANCIER
# ----------------------------------------------------------------------------------------------------------
@login_required
def rapport_benefice(request):
    """
    Affiche le bénéfice (chiffre d'affaires, coût, bénéfice net)
    sur une période donnée, pour la pharmacie de l'utilisateur connecté.
    """

    pharmacie = get_object_or_404(
        Pharmacie, user_pharmacie=request.user
    )

    # ---------------------------------------------------------
    # Rôles de l'utilisateur (même logique que dashboard)
    # ---------------------------------------------------------
    role_verify = Role.objects.filter(userRole=request.user).select_related('role')
    roles = [r.role.nom_typeRole for r in role_verify if r.role]

    if 'super admin' in roles:
        primary_role = 'super admin'
    elif 'admin' in roles:
        primary_role = 'admin'
    else:
        primary_role = 'visiteur'

    devise = request.GET.get('devise', 'CDF')
    periode = request.GET.get('periode', 'mois')

    aujourdhui = timezone.localdate()

    if periode == 'jour':
        date_debut = date_fin = aujourdhui
    elif periode == 'semaine':
        date_debut = aujourdhui - timedelta(days=aujourdhui.weekday())
        date_fin = aujourdhui
    elif periode == 'personnalise':
        try:
            date_debut = datetime.strptime(
                request.GET.get('date_debut', ''), '%Y-%m-%d'
            ).date()
            date_fin = datetime.strptime(
                request.GET.get('date_fin', ''), '%Y-%m-%d'
            ).date()
        except ValueError:
            date_debut = aujourdhui.replace(day=1)
            date_fin = aujourdhui
    else:
        date_debut = aujourdhui.replace(day=1)
        date_fin = aujourdhui

    ventes = (
        Vente.objects
        .filter(
            pharmacie=pharmacie,
            devise=devise,
            date_vente__date__gte=date_debut,
            date_vente__date__lte=date_fin,
        )
        .exclude(statut=Vente.StatutVente.ANNULEE)
        .prefetch_related('lignes', 'lignes__stock')
    )

    chiffre_affaires = Decimal('0.00')
    cout_total = Decimal('0.00')

    for vente in ventes:
        for ligne in vente.lignes.all():
            chiffre_affaires += ligne.sous_total_net
            cout_total += ligne.cout_total

    benefice_total = chiffre_affaires - cout_total

    marge_pourcentage = (
        (benefice_total / chiffre_affaires * 100).quantize(Decimal('0.01'))
        if chiffre_affaires > 0 else Decimal('0.00')
    )

    context = {
        'pharmacie': pharmacie,
        'name_phar': pharmacie.nom_pharmacie,
        'primary_role': primary_role,
        'roles': roles,
        'periode': periode,
        'devise': devise,
        'date_debut': date_debut,
        'date_fin': date_fin,
        'chiffre_affaires': chiffre_affaires,
        'cout_total': cout_total,
        'benefice_total': benefice_total,
        'marge_pourcentage': marge_pourcentage,
        'nombre_ventes': ventes.count(),
    }

    return render(request, 'back-end/finances/rapport_benefice.html', context)  


# **********************************************************************************************************
# RAPPORT PERTE
# **********************************************************************************************************
@login_required
def rapport_perte(request):
    """
    Affiche les pertes de stock (péremptions, casses, vols, ajustements négatifs)
    sur une période donnée, pour la pharmacie de l'utilisateur connecté.
    """

    pharmacie = get_object_or_404(
        Pharmacie, user_pharmacie=request.user
    )

    role_verify = Role.objects.filter(userRole=request.user).select_related('role')
    roles = [r.role.nom_typeRole for r in role_verify if r.role]

    if 'super admin' in roles:
        primary_role = 'super admin'
    elif 'admin' in roles:
        primary_role = 'admin'
    else:
        primary_role = 'visiteur'

    periode = request.GET.get('periode', 'mois')
    type_perte = request.GET.get('type_perte', '')

    aujourdhui = timezone.localdate()

    if periode == 'jour':
        date_debut = date_fin = aujourdhui
    elif periode == 'semaine':
        date_debut = aujourdhui - timedelta(days=aujourdhui.weekday())
        date_fin = aujourdhui
    elif periode == 'personnalise':
        try:
            date_debut = datetime.strptime(
                request.GET.get('date_debut', ''), '%Y-%m-%d'
            ).date()
            date_fin = datetime.strptime(
                request.GET.get('date_fin', ''), '%Y-%m-%d'
            ).date()
        except ValueError:
            date_debut = aujourdhui.replace(day=1)
            date_fin = aujourdhui
    else:
        date_debut = aujourdhui.replace(day=1)
        date_fin = aujourdhui

    types_cibles = [type_perte] if type_perte else [
        MouvementStock.TypeMouvement.PEREMPTION,
        MouvementStock.TypeMouvement.PERTE,
    ]

    mouvements = (
        MouvementStock.objects
        .filter(
            stock__pharmacie=pharmacie,
            type_mouvement__in=types_cibles,
            date_mouvement__date__gte=date_debut,
            date_mouvement__date__lte=date_fin,
        )
        .select_related('stock', 'stock__medicament')
        .order_by('-date_mouvement')
    )

    valeur_totale_perdue = Decimal('0.00')
    quantite_totale_perdue = 0
    detail_par_medicament = {}

    for mvt in mouvements:
        quantite_perdue = mvt.quantite_avant - mvt.quantite_apres
        if quantite_perdue <= 0:
            continue

        stock = mvt.stock
        cout_unitaire = (
            stock.prix_achat_carton / stock.quantite_par_carton
            if stock.quantite_par_carton else Decimal('0.00')
        )
        valeur_perdue = (cout_unitaire * quantite_perdue).quantize(Decimal('0.01'))

        valeur_totale_perdue += valeur_perdue
        quantite_totale_perdue += quantite_perdue

        medicament = stock.medicament
        if medicament.id not in detail_par_medicament:
            detail_par_medicament[medicament.id] = {
                'medicament': medicament,
                'quantite_perdue': 0,
                'valeur_perdue': Decimal('0.00'),
            }
        detail_par_medicament[medicament.id]['quantite_perdue'] += quantite_perdue
        detail_par_medicament[medicament.id]['valeur_perdue'] += valeur_perdue

    context = {
        'pharmacie': pharmacie,
        'name_phar': pharmacie.nom_pharmacie,
        'primary_role': primary_role,
        'roles': roles,
        'periode': periode,
        'type_perte': type_perte,
        'date_debut': date_debut,
        'date_fin': date_fin,
        'mouvements': mouvements,
        'quantite_totale_perdue': quantite_totale_perdue,
        'valeur_totale_perdue': valeur_totale_perdue,
        'detail_par_medicament': sorted(
            detail_par_medicament.values(),
            key=lambda d: d['valeur_perdue'],
            reverse=True,
        ),
    }

    return render(request, 'back-end/finances/rapport_perte.html', context)


# ***************************************************************************
# Rapport financier
# ***************************************************************************
@login_required
def rapport_financier(request):
    """
    Vue d'ensemble financière de la pharmacie sur une période donnée.
    """

    pharmacie = get_object_or_404(
        Pharmacie, user_pharmacie=request.user
    )

    role_verify = Role.objects.filter(userRole=request.user).select_related('role')
    roles = [r.role.nom_typeRole for r in role_verify if r.role]

    if 'super admin' in roles:
        primary_role = 'super admin'
    elif 'admin' in roles:
        primary_role = 'admin'
    else:
        primary_role = 'visiteur'

    devise = request.GET.get('devise', 'CDF')
    periode = request.GET.get('periode', 'mois')

    aujourdhui = timezone.localdate()

    if periode == 'jour':
        date_debut = date_fin = aujourdhui
    elif periode == 'semaine':
        date_debut = aujourdhui - timedelta(days=aujourdhui.weekday())
        date_fin = aujourdhui
    elif periode == 'personnalise':
        try:
            date_debut = datetime.strptime(
                request.GET.get('date_debut', ''), '%Y-%m-%d'
            ).date()
            date_fin = datetime.strptime(
                request.GET.get('date_fin', ''), '%Y-%m-%d'
            ).date()
        except ValueError:
            date_debut = aujourdhui.replace(day=1)
            date_fin = aujourdhui
    else:
        date_debut = aujourdhui.replace(day=1)
        date_fin = aujourdhui

    ventes = (
        Vente.objects
        .filter(
            pharmacie=pharmacie,
            devise=devise,
            date_vente__date__gte=date_debut,
            date_vente__date__lte=date_fin,
        )
        .exclude(statut=Vente.StatutVente.ANNULEE)
        .prefetch_related('lignes', 'lignes__stock', 'paiements')
    )

    chiffre_affaires = Decimal('0.00')
    cout_total = Decimal('0.00')
    montant_encaisse = Decimal('0.00')

    for vente in ventes:
        for ligne in vente.lignes.all():
            chiffre_affaires += ligne.sous_total_net
            cout_total += ligne.cout_total
        for paiement in vente.paiements.all():
            montant_encaisse += paiement.montant

    benefice_brut = chiffre_affaires - cout_total
    montant_restant_du = chiffre_affaires - montant_encaisse

    mouvements_perte = (
        MouvementStock.objects
        .filter(
            stock__pharmacie=pharmacie,
            type_mouvement__in=[
                MouvementStock.TypeMouvement.PEREMPTION,
                MouvementStock.TypeMouvement.PERTE,
            ],
            date_mouvement__date__gte=date_debut,
            date_mouvement__date__lte=date_fin,
        )
        .select_related('stock')
    )

    valeur_pertes = Decimal('0.00')
    for mvt in mouvements_perte:
        quantite_perdue = mvt.quantite_avant - mvt.quantite_apres
        if quantite_perdue <= 0:
            continue
        cout_unitaire = (
            mvt.stock.prix_achat_carton / mvt.stock.quantite_par_carton
            if mvt.stock.quantite_par_carton else Decimal('0.00')
        )
        valeur_pertes += (cout_unitaire * quantite_perdue).quantize(Decimal('0.01'))

    benefice_net = benefice_brut - valeur_pertes

    marge_pourcentage = (
        (benefice_net / chiffre_affaires * 100).quantize(Decimal('0.01'))
        if chiffre_affaires > 0 else Decimal('0.00')
    )

    context = {
        'pharmacie': pharmacie,
        'name_phar': pharmacie.nom_pharmacie,
        'primary_role': primary_role,
        'roles': roles,
        'periode': periode,
        'devise': devise,
        'date_debut': date_debut,
        'date_fin': date_fin,
        'chiffre_affaires': chiffre_affaires,
        'cout_total': cout_total,
        'benefice_brut': benefice_brut,
        'valeur_pertes': valeur_pertes,
        'benefice_net': benefice_net,
        'marge_pourcentage': marge_pourcentage,
        'montant_encaisse': montant_encaisse,
        'montant_restant_du': montant_restant_du,
        'nombre_ventes': ventes.count(),
    }

    return render(request, 'back-end/finances/rapport_financier.html', context) 


# ***********************************************************************
# CHANGEMENT DU MOT DE PASSE 
# ***********************************************************************
@login_required
def changer_mot_de_passe(request):
    pharmacie_obj = Pharmacie.objects.filter(user_pharmacie=request.user).first()
    name_phar = pharmacie_obj.nom_pharmacie if pharmacie_obj else 'pas de nom'

    role_verify = Role.objects.filter(userRole=request.user).select_related('role')
    roles = [r.role.nom_typeRole for r in role_verify if r.role]

    if 'super admin' in roles:
        primary_role = 'super admin'
    elif 'admin' in roles:
        primary_role = 'admin'
    else:
        primary_role = 'visiteur'

    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)
            messages.success(request, 'Votre mot de passe a été modifié avec succès.')
            return redirect('changer_mot_de_passe')
    else:
        form = PasswordChangeForm(request.user)

    return render(request, 'back-end/authentifications/password_change.html', {
        'form': form,
        'primary_role': primary_role,
        'roles': roles,
        'name_phar': name_phar,
    })