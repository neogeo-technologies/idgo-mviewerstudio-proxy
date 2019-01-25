# Lancer le proxy dans l'environnement de dev :

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
