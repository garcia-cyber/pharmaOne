from django.shortcuts import render , redirect , get_object_or_404 , HttpResponse
from django.contrib.auth.decorators import login_required
from .forms import *
from .models import *
from django.contrib.auth import authenticate , login as auth_login , logout ,update_session_auth_hash
from django.core.paginator import Paginator
from django.db.models import Q, Sum, F, DecimalField, ExpressionWrapper ,Count,Min
from datetime import timedelta
from decimal import Decimal


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
        'roles' : roles  ,
        'name_phar' : name_phar
    }
    return render(request, 'back-end/dashboard/index.html',context)

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
        limite_proche_peremption = today + timezone.timedelta(days=90)

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
            timezone.localdate() + timezone.timedelta(days=90)
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