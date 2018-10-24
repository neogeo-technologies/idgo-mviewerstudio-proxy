import flask
from flask import Flask
from flask_cas import CAS, logout
from flask_cas import login_required

app = Flask(__name__)


logout
@app.route('/')
@login_required
def route_root():
#    import rpdb; rpdb.set_trace()
    return "user: %s, display_name: %s" % (cas.username, cas.attributes)

@app.route("/logout")
def rt_logout():
    return logout()

cas = CAS(app, '/cas')
app.config['CAS_SERVER'] = 'https://admin.dev.idgo.neogeo.fr'
app.config['CAS_AFTER_LOGIN'] = 'route_root'
app.config['CAS_LOGIN_ROUTE'] = '/signin'

app.secret_key='Hohvian8Zaiw6oohainoeS0VeSh4ees3Mu6waiwuKooxeth9CooP3AhNeajoh1Ie'
app.config['SESSION_TYPE'] = 'filesystem'
app.debug = True
app.run()
