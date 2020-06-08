# IDGO Proxy Mviewerstudio

Ce proxy permet d'utiliser (mviewerstudio)[https://github.com/geobretagne/mviewerstudio] avec (IDGO)[https://github.com/neogeo-technologies/idgo]

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
