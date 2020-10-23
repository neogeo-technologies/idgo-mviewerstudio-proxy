# IDGO Proxy Mviewerstudio

Ce proxy permet d'utiliser (mviewerstudio)[https://github.com/geobretagne/mviewerstudio] avec (IDGO)[https://github.com/neogeo-technologies/idgo]

Il repose quasi-exclusivement sur un seul script python : mviewerstudio_cas.py

L'accès à l'API IDGO est nécessaire pour obtenir les informations sur l'utilisateur
et les organisations pour lesquelles il est contributeur et/ou référent.

Le serveur REDIS est utilisé pour stocker et re-servir les informations obtenues par l'API afin de
ne pas refaire systématiquement des appels à l'API IDGO à chaque action.

Le proxy est utilisé lors des actions suivantes dans mviewerstudio :
* lors du chargement de mviewerstudio pour vérifier les droits de l'utilisateur et contextualiser l'application
* lors de l'enregistrement d'une carte
* lors du chargement d'une carte
* lors de la suppression d'une carte


## Gestion des permissions

Il existe 2 modèles de permissions pour accéder et utiliser mviewerstudio :
- le modèle **datasud**, appellation historique qui correspond au fonctionnement standard
- le modèle **ideo-bfc**, spécifique à un fonctionnement où les droits d'utilisateur
ne sont pas gérés par IDGO

### Modèle datasud
Pour pouvoir accéder au studio, l'utilisateur doit réunir les conditions suivantes :
- il doit être **admin** ET **partenaire "crige"**, ou bien rattaché à une **organisation partenaire "crige"**
- il doit être contributeur ou référent d'une **organisation partenaire "crige"**

### Modèle ideo-bfc
Dans ce modèle, il n'existe pas de notion de partenaire "crige", un utilisateur a accés
au studio dés lors qu'il a un statut d'admin ou de référent.
C'est plus ouvert que le modèle précédent mais par contre, les contributeurs n'ont pas accès.

## Chargement de l'application

Au chargement de mviewerstudio, le service **user_info** est appelé afin de connaître le contexte
de l'utilisateur pour personnaliser l'interface.
Ce service retourne les username, nom et prénom de l'utilisateur, ainsi que les organisations pour lesquelles
l'utilisateur est contributeur ou référent. Si l'utilisateur est contributeur ou réferent de plusieurs
organisation, mviwerstudio lui proposera au démarrage de choisir dans une liste celle pour laquelle
il souhaite créer ou modifier des cartes.

## Enregistrement d'une carte

Cette fonction remplace le script "store.php" proposé par défaut dans mviewerstudio_cas
La carte est enregistrée (format XML) en inscrivant le nom de l'utilisateur dans les metadonnées
afin que l'utilisateur puisse la retrouver par la suite et la recharger pour la modifier.

## Chargement d'une carte existant

Cette fonction remplace le script "list.php" proposé par défaut dans mviewerstudio_cas

En fonction de son statut (contributeur ou référent) par rapport à l'organisation pour laquelle
il travaille dans mviewerstudio, l'utilisateur n'a pas les mêmes possibilités :
* s'il est simple contributeur, il ne peut charger et modifier que les cartes qu'il a lui même enregistrées,
c'est à dire dans lesquelles son nom est inscrit (voir paragraphe précédent).
* s'il est référent, il peut charger et modifier toutes les cartes de l'organisation (idem si admin)

## Suppression des cartes d'un utilisateur

Cette fonction remplace le script "delete.php" proposé par défaut dans mviewerstudio_cas

__ à compléter__


# Installation et configuration

## Prerequis

Une Debian avec python 3.5/3.6/3.7, avec Redis et un serveur Apache/Nginx

## Lancer le proxy dans l'environnement de dev :

Lancer un tmux avec
```
tmux
```

Ensuite activer li'environnement virtuel :
```
. /mviewerstudio_venv/bin/activate
```

Ensuite on lance flask en mode dev :
```
FLASK_APP=mviewerstudio_cas/mviewerstudio_cas.py FLASK_ENV=development flask run --host=0.0.0.0
```

pour sortir de tmux proprement, c'est CTRL-B puis D

Pour y revenir :
```
tmux a
```

## Lancer avec gunicorn

```
sudo cp systemd/gunicorn.service  /etc/systemd/system/
# Editer les deux fichiers de configuration pour vérifier les chemins
sudo systemctl daemon-reload
sudo systemctl enable gunicorn
sudo systemctl start gunicorn
```

Ajouter ça dans la conf apache:
```
    <Location /studiocarto>
        ProxyPreserveHost On
        ProxyPass http://localhost:8000/studiocarto
    </Location>
```

## Configuration

créer un fichier 'settings.py' à la racine du virtualenv avec ces paramètres:

* LOGLEVEL
* CAS\_SERVER URL publique de IDGO
* PATH\_INFO chemin de l'URL où le proxy répond (Par défaut /viewerstudio")
* API\_PATH Chemin de IDGO où le questioner sur les utilisateurs/groupes
* API\_USER utilisateur IDGO pour faire les requêtes
* API\_PWD mot de passe  de l'utilisateur IDGO
* SECRET\_KEY un chaine de caractère secrête pour activer les sessions Flask
* PERMISSION\_MODEL "datasud" ou "ideo-bfc"
* REDIS\_URL Accès à Redis pour le cache utilisateur (par défaut 'redis://localhost:6379/0')
