from django.db import models
from django.contrib.auth.models import  User 

# Create your models here.



#
# creation de la class pharmacie pour chaque user puisse affiche les nom des sa pharmacie
class Pharmacie(models.Model):
    nom_pharmacie = models.CharField(max_length= 30)
    user_pharmacie = models.ForeignKey(User , on_delete= models.SET_NULL , null = True , blank= True) 
    dateCreation = models.DateField(auto_now_add= True)


    def __str__(self):
        return self.nom_pharmacie

#
#
# creation de la type de role 
class TypeRole(models.Model):
    nom_typeRole = models.CharField(max_length= 40)

    def __str__(self):
        return self.nom_typeRole

#
#
# creation de role dans le systeme 
class Role(models.Model):
    role = models.ForeignKey(TypeRole , on_delete= models.SET_NULL, null= True , blank= True, verbose_name= 'roleType')
    userRole = models.ForeignKey(User , on_delete= models.SET_NULL, verbose_name= 'userRole', null= True)
    pharmacie = models.ForeignKey(Pharmacie , on_delete= models.SET_NULL, verbose_name= 'pharmacieRole', null= True ) 
    statut = models.CharField(max_length=10, default='active') 

    
    def __str__(self):
        return self.statut

#
#
# taux d'echange pour chaque pharmacie
class TauxChange(models.Model):
    pharmacie = models.OneToOneField(
        Pharmacie, 
        on_delete=models.CASCADE, 
        related_name='taux_change',
        verbose_name='Pharmacie'
    )
    taux_usd_cdf = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        verbose_name='Taux USD vers CDF',
        help_text='Ex: 1 USD = 2500 CDF'
    )
    date_mise_a_jour = models.DateTimeField(auto_now=True)
    utilisateur = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True,
        verbose_name='Utilisateur ayant défini le taux'
    )
    est_actif = models.BooleanField(default=True, verbose_name='Taux actif')
    
    class Meta:
        verbose_name = 'Taux de change'
        verbose_name_plural = 'Taux de change'
        ordering = ['-date_mise_a_jour']
        constraints = [
            models.UniqueConstraint(
                fields=['pharmacie', 'est_actif'],
                condition=models.Q(est_actif=True),
                name='unique_taux_actif_par_pharmacie'
            )
        ]
    
    def __str__(self):
        return f"{self.pharmacie.nom_pharmacie} - 1 USD = {self.taux_usd_cdf} CDF"
    