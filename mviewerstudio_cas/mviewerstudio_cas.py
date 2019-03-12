from json import loads
import logging
from stat import S_ISREG, ST_MTIME, ST_MODE
import os
import sys
from functools import wraps

import flask
from flask import Flask, Response, send_from_directory, redirect, jsonify, abort
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

logging.basicConfig(level=logging.DEBUG)
app = Flask(__name__)
app.config.from_object("settings")
VIEWER_STUDIO_PATH = "/var/www/html/viewerstudio/"
PATH_INFO = app.config.get('PATH_INFO', "/viewerstudio")


def privileged_user_required(func):
    # Access to mviewerstudio is only given to CRIGE admins, CRIGE partners referents and CRIGE parteners contributors
    @wraps(func)
    def decorated_view(*args, **kwargs):
        # Preprocessing
        user = User.objects.get(username=cas.username, is_active=True)

        is_user_crige_partner_member = False
        is_user_crige_partner_contributor = False
        is_user_crige_partner_referent = False

        # is the user a CRIGE partner member?
        if user.profile.organisation:
            is_user_crige_partner_member = user.profile.organisation.is_crige_partner

        # is the user a CRIGE partner contributor?
        for organisation in user.profile.contribute_for:
            if organisation.is_crige_partner:
                is_user_crige_partner_contributor = True
                break

        # is the user a CRIGE partner referent?
        for organisation in user.profile.referent_for:
            if organisation.is_crige_partner:
                is_user_crige_partner_referent = True
                break

        is_user_allowed = (user.profile.is_crige_admin or is_user_crige_partner_member) and \
                          (is_user_crige_partner_contributor or is_user_crige_partner_referent)

        if not is_user_allowed:
            abort(403)
        return func(*args, **kwargs)
        # Postprocessing
    return decorated_view


@app.errorhandler(403)
def error_403(e):
    return send_from_directory(VIEWER_STUDIO_PATH, "403.html")


@app.route("/")
@login_required
def route_root():
    return redirect(PATH_INFO + "/")


@app.route(PATH_INFO + "/logout")
def rt_logout():
    return logout()


@app.route(PATH_INFO)
@app.route(PATH_INFO + "/")
@login_required
@privileged_user_required
def send_viewerstudio_index():
    return send_from_directory(VIEWER_STUDIO_PATH, "index.html")


@app.route(PATH_INFO + "/<path:path>")
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


@app.route(PATH_INFO + "/srv/delete.php")
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


@app.route(PATH_INFO + "/user_info")
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
            if organisation.is_crige_partner:
                org_name = organisation.slug
                if org_name not in organisations:
                    organisations.add(org_name)
                    data["userGroups"].append(
                        {
                            "fullName": organisation.legal_name,
                            "slugName": organisation.slug,
                            "userRole": "referent",
                            "groupType": "organisation"
                        }
                    )

        for organisation in user.profile.contribute_for:
            if organisation.is_crige_partner:
                org_name = organisation.slug
                if org_name not in organisations:
                    organisations.add(org_name)
                    data["userGroups"].append(
                        {
                            "fullName": organisation.legal_name,
                            "slugName": organisation.slug,
                            "userRole": "contributor",
                            "groupType": "organisation"
                        }
                    )

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
                try:
                    xml = xmltodict.parse(f.read(), process_namespaces=False)

                    # admin user can access any xml file
                    # referent user can access any xml file for all organisation he is a referent for
                    # contributor user can access xml files of which he is the creator
                    description = xml["config"]["metadata"]["rdf:RDF"]["rdf:Description"]
                    if ((user_role == "contributor" and description["dc:creator"] == cas.username) or
                        user_role == "referent"):
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
                except Exception as e:
                    logging.error("An error occured while reading {}".format(filename))
                    logging.error(e)

    except FileNotFoundError as e:
        logging.debug(e)

    return user_content


@app.route(PATH_INFO + "/srv/list.php")
@login_required
@privileged_user_required
def viewerstudio_list_user_content():
    conf = get_conf()
    user = User.objects.get(username=cas.username, is_active=True)

    folders = set()
    user_content = []

    for organisation in user.profile.referent_for:
        if organisation.is_crige_partner:
            folder = os.path.join(conf["export_conf_folder"], organisation.slug)
            if folder not in folders:
                folders.add(folder)
                user_content.extend(get_user_content_in_folder(folder=folder, user_role="referent"))

    for organisation in user.profile.contribute_for:
        if organisation.is_crige_partner:
            folder = os.path.join(conf["export_conf_folder"], organisation.slug)
            if folder not in folders:
                folders.add(folder)
                user_content.extend(get_user_content_in_folder(folder=folder, user_role="contributor"))

    return jsonify(user_content)


@app.route(PATH_INFO + "/srv/store.php", methods=["POST"])
@login_required
@privileged_user_required
def viewerstudio_store_user_content():
    user = User.objects.get(username=cas.username, is_active=True)

    conf = get_conf()
    xml0 = flask.request.data
    xml = xml0.decode().replace("anonymous", cas.username)

    # Retrieve title
    _xml = xmltodict.parse(xml0, process_namespaces=False)

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


@app.route(PATH_INFO + "/proxy/", methods=["GET", "POST", "HEAD"])
def proxy():

    if flask.request.method not in ("GET", "POST", "HEAD"):
        raise BadRequest("Unauthorized method")

    response = requests.request(
        method=flask.request.method,
        url=flask.request.args["url"],
        headers={key: value for (key, value) in flask.request.headers if key != 'Host'},
        data=flask.request.get_data(),
        cookies=flask.request.cookies,
        allow_redirects=False)

    excluded_headers = ['content-encoding', 'content-length', 'transfer-encoding', 'connection']
    headers = [(name, value) for (name, value) in response.raw.headers.items()
               if name.lower() not in excluded_headers]

    return Response(response.content, mimetype=response.headers.get("content-type"),
                    status=response.status_code, headers=headers)


cas = CAS(app, PATH_INFO + "/cas")
app.config["CAS_AFTER_LOGIN"] = "send_viewerstudio_index"
app.config["CAS_LOGIN_ROUTE"] = "/signin"
app.config["SESSION_TYPE"] = "filesystem"

# For mod_wgsi compatibility
application = app

if __name__ == "__main__":
    app.debug = True
    app.run()
