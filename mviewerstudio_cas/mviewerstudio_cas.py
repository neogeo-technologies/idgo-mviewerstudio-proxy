from hashlib import md5
from json import loads, dumps
import logging
from stat import S_ISREG, ST_MTIME, ST_MODE
import os
import sys

import flask
from flask import Flask, send_from_directory, redirect, jsonify
from flask_cas import CAS, logout
from flask_cas import login_required
import requests
from werkzeug.exceptions import BadRequest
import xmltodict

from django.utils.text import slugify

import django

sys.path.append("/idgo_venv/")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()
from django.contrib.auth.models import User  # noqa: E402
from idgo_admin.api.views.user import serializer  # noqa: E402

app = Flask(__name__)

VIEWER_STUDIO_PATH = "/var/www/html/viewerstudio/"


@app.route("/")
@login_required
def route_root():
    return redirect("/viewerstudio/")


@app.route("/logout")
def rt_logout():
    return logout()


@app.route("/viewerstudio")
@app.route("/viewerstudio/")
@login_required
def send_viewerstudio_index():
    logging.error(cas)
    #    import rpdb; rpdb.set_trace()
    return send_from_directory(VIEWER_STUDIO_PATH, "index.html")


@app.route("/viewerstudio/<path:path>")
@login_required
def send_viewerstudio_files(path):
    print(path)
    return send_from_directory(VIEWER_STUDIO_PATH, path)


def get_conf():
    with open(os.path.join(VIEWER_STUDIO_PATH, "config.json")) as config_file:
        conf = loads(config_file.read())["app_conf"]
    return conf


@app.route("/viewerstudio/srv/delete.php")
@login_required
def viewerstudio_delete_user_content():
    conf = get_conf()

    export_folder = conf["export_conf_folder"]

    entries = (
        os.path.join(export_folder, fn)
        for fn in os.listdir(export_folder)
        if fn.endswith(".xml")
    )

    counter = 0

    for filename in sorted(entries):
        # logging.error(filename)
        with open(filename) as f:
            xml = xmltodict.parse(f.read(), process_namespaces=False)

        logging.error(xml["config"]["metadata"]["rdf:RDF"])
        description = xml["config"]["metadata"]["rdf:RDF"]["rdf:Description"]
        if description["dc:creator"] == cas.username:
            counter += 1
            logging.error(
                "removing {filename} of '{creator}'".format(
                    filename=filename, creator=cas.username
                )
            )
            os.unlink(filename)

    return jsonify({"deleted_files": counter})


@app.route("/viewerstudio/user_info")
@login_required
def viewerstudio_est():
    user_dj = User.objects.get(username=cas.username, is_active=True)

    try:
        data = serializer(user_dj)
    except (FieldError, ValueError):
        return flask.abort(400)
    else:
        if len(data) == 0:
            raise flask.abort(404)
        else:
            return jsonify(data)


@app.route("/viewerstudio/srv/list.php")
@login_required
def viewerstudio_list_user_content():
    conf = get_conf()
    _user = User.objects.get(username=cas.username, is_active=True)

    # export_folder = conf['export_conf_folder']
    export_folder = os.path.join(
        conf["export_conf_folder"], _user.profile.organisation.ckan_slug
    )

    # sort files by age
    entries = (os.path.join(export_folder, fn) for fn in os.listdir(export_folder))
    entries = ((os.stat(path), path) for path in entries)
    entries = (
        (stat[ST_MTIME], path)
        for stat, path in entries
        if S_ISREG(stat[ST_MODE]) and path.endswith(".xml")
    )

    data = []

    for _, filename in sorted(entries):
        # logging.error(filename)
        with open(filename) as f:
            xml = xmltodict.parse(f.read(), process_namespaces=False)

        # logging.error(xml["config"]["metadata"]["rdf:RDF"])
        description = xml["config"]["metadata"]["rdf:RDF"]["rdf:Description"]
        if description["dc:creator"] == cas.username:
            url = filename.replace(
                conf["export_conf_folder"], conf["conf_path_from_mviewer"]
            )
            metadata = {
                "url": url,
                "creator": description["dc:creator"],
                "date": description.get("dc:date", ""),
                "title": description.get("dc:title", ""),
                "subjects": description.get("dc:subject", ""),
            }
            data.append(metadata)

    return jsonify(data)


@app.route("/viewerstudio/srv/store.php", methods=["POST"])
@login_required
def viewerstudio_store_user_content():

    _user = User.objects.get(username=cas.username, is_active=True)

    conf = get_conf()
    xml0 = flask.request.data
    xml = xml0.decode().replace("anonymous", cas.username)

    # Retrieve title
    _xml = xmltodict.parse(xml0, process_namespaces=False)

    logging.error(_xml["config"]["metadata"])
    from pprint import pprint

    # pprint(_xml["config"]["metadata"])
    description = _xml["config"]["metadata"]["rdf:RDF"]["rdf:Description"]
    _map_title = slugify(description.get("dc:title", ""))

    # Create organization repo if not exists
    _map_directory = os.path.join(
        conf["export_conf_folder"], _user.profile.organisation.ckan_slug
    )
    if not os.path.exists(_map_directory):
        os.makedirs(_map_directory)

    # filename = "{filename}.xml".format(filename=md5(xml.encode()).hexdigest())
    filename = "{filename}.xml".format(filename=_map_title)

    with open(os.path.join(_map_directory, filename), "w") as f:
        f.write(xml)

    return jsonify(
        {
            "success": True,
            "filepath": filename,
            "organisation": _user.profile.organisation.ckan_slug,
        }
    )


@app.route("/proxy/", methods=["GET", "POST"])
def proxy():

    if flask.request.method == "GET":
        return requests.get(flask.request.args["url"]).content
    elif flask.request.method == "POST":
        return requests.post(flask.request.args["url"], data=flask.request.data).content
    else:
        raise BadRequest("Unauthorized method")


cas = CAS(app, "/cas")
app.config["CAS_SERVER"] = "https://admin.dev.idgo.neogeo.fr"
app.config["CAS_AFTER_LOGIN"] = "route_root"
app.config["CAS_LOGIN_ROUTE"] = "/signin"

app.secret_key = "Hohvian8Zaiw6oohainoeS0VeSh4ees3Mu6waiwuKooxeth9CooP3AhNeajoh1Ie"
app.config["SESSION_TYPE"] = "filesystem"
if __name__ == "__main__":
    app.debug = True
    app.run()
