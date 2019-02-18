from json import loads
import logging
from stat import S_ISREG, ST_MTIME, ST_MODE
import os
import sys
from functools import wraps

import flask
from flask import Flask, send_from_directory, redirect, jsonify, abort
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

logging.basicConfig(level=logging.DEBUG)
app = Flask(__name__)
VIEWER_STUDIO_PATH = "/var/www/html/viewerstudio/"


def privileged_user_required(func):
    @wraps(func)
    def decorated_view(*args, **kwargs):
        # Pré-traitement
        user = User.objects.get(username=cas.username, is_active=True).profile
        if not (user.is_admin or user.is_referent or user.is_contributor):
            abort(403)
        return func(*args, **kwargs)
        # Post-traitement
    return decorated_view


@app.errorhandler(403)
def error_403(e):
    return send_from_directory(VIEWER_STUDIO_PATH, "403.html")


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
@privileged_user_required
def send_viewerstudio_index():
    return send_from_directory(VIEWER_STUDIO_PATH, "index.html")


@app.route("/viewerstudio/<path:path>")
@login_required
@privileged_user_required
def send_viewerstudio_files(path):
    logging.info("File transfered: {}".format(path))
    return send_from_directory(VIEWER_STUDIO_PATH, path)


def get_conf():
    logging.info(os.path.join(VIEWER_STUDIO_PATH, "config.json"))
    with open(
        os.path.join(VIEWER_STUDIO_PATH, "config.json"), encoding="utf-8"
    ) as config_file:
        conf = loads(config_file.read())["app_conf"]
    return conf


@app.route("/viewerstudio/srv/delete.php")
@login_required
@privileged_user_required
def viewerstudio_delete_user_content():
    conf = get_conf()

    export_folder = conf["export_conf_folder"]

    entries = []
    for (dir_path, dir_names, file_names) in os.walk(export_folder):
        entries += [os.path.join(dir_path, file) for file in file_names]
    counter = 0

    for filename in sorted(entries):
        with open(filename, encoding="utf-8") as f:
            xml = xmltodict.parse(f.read(), process_namespaces=False)

        # logging.info(xml["config"]["metadata"]["rdf:RDF"])
        description = xml["config"]["metadata"]["rdf:RDF"]["rdf:Description"]
        if description["dc:creator"] == cas.username:
            counter += 1
            logging.info(
                "removing {filename} of '{creator}'".format(
                    filename=filename, creator=cas.username
                )
            )
            os.unlink(filename)

    return jsonify({"deleted_files": counter})


@app.route("/viewerstudio/user_info")
@login_required
@privileged_user_required
def viewerstudio_user_info():
    user = User.objects.get(username=cas.username, is_active=True)
    data = {}

    try:
        data["userName"] = user.username
        data["firstName"] = user.first_name
        data["lastName"] = user.last_name
        data["userGroups"] = []

        organisations = set()

        for organisation in user.profile.referent_for:
            org_name = organisation.ckan_slug
            if org_name not in organisations:
                organisations.add(org_name)
                data["userGroups"].append(
                    {
                        "fullName": organisation.name,
                        "slugName": organisation.ckan_slug,
                        "userRole": "referent",
                        "groupType": "organisation"
                    }
                )

        for organisation in user.profile.contribute_for:
            org_name = organisation.ckan_slug
            if org_name not in organisations:
                organisations.add(org_name)
                data["userGroups"].append(
                    {
                        "fullName": organisation.name,
                        "slugName": organisation.ckan_slug,
                        "userRole": "contributor",
                        "groupType": "organisation"
                    }
                )

        logging.info(data)

    except (FieldError, ValueError) as e:
        logging.error(e)
        return flask.abort(400)
    else:
        if not data:
            raise flask.abort(404)
        else:
            return jsonify(data)


def get_user_content_in_folder(folder, user_role):
    conf = get_conf()
    user_content = []

    # List regular XML files
    try:
        entries = (os.path.join(folder, fn) for fn in os.listdir(folder))
        entries = ((os.stat(path), path) for path in entries)
        entries = (
            path
            for stat, path in entries
            if S_ISREG(stat[ST_MODE]) and path.endswith(".xml")
        )

        for filename in entries:
            with open(filename, encoding="utf-8") as f:
                xml = xmltodict.parse(f.read(), process_namespaces=False)

                # admin user can access any xml file
                # referent user can access any xml file for all organisation he is a referent for
                # contributor user can access xml files of which he is the creator
                description = xml["config"]["metadata"]["rdf:RDF"]["rdf:Description"]
                if not (user_role == "contributor" and description["dc:creator"] == cas.username):
                    url = filename.replace(
                        conf["export_conf_folder"], conf["conf_path_from_mviewer"]
                    )
                    metadata = {
                        "url": url,
                        "creator": description["dc:creator"],
                        "date": description.get("dc:date", ""),
                        "title": description.get("dc:title", ""),
                        "subjects": description.get("dc:subject", ""),
                        "group": os.path.basename(folder),
                    }
                    user_content.append(metadata)
    except FileNotFoundError as e:
        logging.debug(e)

    return user_content


@app.route("/viewerstudio/srv/list.php")
@login_required
@privileged_user_required
def viewerstudio_list_user_content():
    conf = get_conf()
    user = User.objects.get(username=cas.username, is_active=True)

    folders = set()
    user_content = []

    for organisation in user.profile.referent_for:
        folder = os.path.join(conf["export_conf_folder"], organisation.ckan_slug)
        if folder not in folders:
            folders.add(folder)
            user_content.extend(get_user_content_in_folder(folder=folder, user_role="referent"))

    for organisation in user.profile.contribute_for:
        folder = os.path.join(conf["export_conf_folder"], organisation.ckan_slug)
        if folder not in folders:
            folders.add(folder)
            user_content.extend(get_user_content_in_folder(folder=folder, user_role="contributor"))

    return jsonify(user_content)


@app.route("/viewerstudio/srv/store.php", methods=["POST"])
@login_required
@privileged_user_required
def viewerstudio_store_user_content():
    user = User.objects.get(username=cas.username, is_active=True)

    conf = get_conf()
    xml0 = flask.request.data
    xml = xml0.decode().replace("anonymous", cas.username)

    # Retrieve title
    _xml = xmltodict.parse(xml0, process_namespaces=False)

    logging.info("config/metadata: " + str(_xml["config"]["metadata"]))

    description = _xml["config"]["metadata"]["rdf:RDF"]["rdf:Description"]
    _map_title = slugify(description.get("dc:title", ""))

    # Retrieve publisher
    # Create organization repo if not exists
    publisher = description.get("dc:publisher", "")
    _map_directory = os.path.join(
        conf["export_conf_folder"], publisher
    )
    if not os.path.exists(_map_directory):
        os.makedirs(_map_directory)

    filename = "{filename}.xml".format(filename=_map_title)

    file_path = os.path.join(_map_directory, filename)
    relative_file_path = "{}/{}".format(publisher, filename)

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(xml)

    return jsonify(
        {
            "success": True,
            "filepath": relative_file_path,
            "group": publisher,
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
app.config.from_object("settings")
app.config["CAS_AFTER_LOGIN"] = "route_root"
app.config["CAS_LOGIN_ROUTE"] = "/signin"
app.config["SESSION_TYPE"] = "filesystem"

# For mod_wgsi compatibility
application = app

if __name__ == "__main__":
    app.debug = True
    app.run()
