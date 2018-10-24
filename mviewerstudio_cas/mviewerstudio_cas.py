import flask
from flask import Flask, send_from_directory, redirect
from flask_cas import CAS, logout
from flask_cas import login_required

app = Flask(__name__)


@app.route('/')
@login_required
def route_root():
#    import rpdb; rpdb.set_trace()
    return redirect("/viewerstudio/")

@app.route("/logout")
def rt_logout():
    return logout()

@app.route('/viewerstudio')
@app.route('/viewerstudio/')
@login_required
def send_viewerstudio_index():
    return send_from_directory('/var/www/html/viewerstudio/', "index.html")

@app.route('/viewerstudio/<path:path>')
@login_required
def send_viewerstudio_files(path):
    print(path)
    return send_from_directory('/var/www/html/viewerstudio/', path)

cas = CAS(app, '/cas')
app.config['CAS_SERVER'] = 'https://admin.dev.idgo.neogeo.fr'
app.config['CAS_AFTER_LOGIN'] = 'route_root'
app.config['CAS_LOGIN_ROUTE'] = '/signin'

app.secret_key='Hohvian8Zaiw6oohainoeS0VeSh4ees3Mu6waiwuKooxeth9CooP3AhNeajoh1Ie'
app.config['SESSION_TYPE'] = 'filesystem'
if __name__ == "__main__":
    app.debug = True
    app.run()
