from json import loads
import logging
import glob
import os
from functools import wraps
import json

import flask
from flask import Flask, Response, send_from_directory, redirect, jsonify, abort
from flask_cas import CAS, logout
from flask_cas import login_required
from werkzeug.exceptions import BadRequest

import requests

import xmltodict
from slugify import slugify

import redis

app = Flask(__name__)
app.config.from_object("settings")
if app.config.get("LOGLEVEL"):
    logging.basicConfig(level=app.config.get("LOGLEVEL"))

ext_proxy = app.config.get("PROXY")
if ext_proxy:
    for env in ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy']:
        os.environ[env] = ext_proxy
if app.config.get("NO_PROXY"):
    os.environ['no_proxy'] = app.config.get("NO_PROXY")

VIEWER_STUDIO_PATH = app.config.get('VIEWER_STUDIO_PATH',
                                    "/var/www/html/viewerstudio/")
PATH_INFO = app.config.get("PATH_INFO", "/viewerstudio")
CAS_SERVER = app.config.get("CAS_SERVER")
API_PATH = app.config.get("API_PATH")
API_USER = app.config.get("API_USER")
API_PWD = app.config.get("API_PWD")


def get_user_info(user_name):
    r = redis.Redis()
    redis_key = 'mviewerstudio_cas_' + user_name
    if not r.get(redis_key):
        user_request_url = '/'.join(s.strip('/') for s in (API_PATH, "user", user_name))
        user_api_response = requests.request(method="GET", url=user_request_url,
            auth=requests.auth.HTTPBasicAuth(API_USER, API_PWD))
        if user_api_response.status_code != 200:
            return None
        r.set(redis_key, user_api_response.content, ex=300)
    return json.loads(r.get(redis_key).decode())


def get_org_info(org_name):
    r = redis.Redis()
    redis_key = 'mviewerstudio_cas_' + org_name
    if not r.get(redis_key):
        org_request_url = '/'.join(s.strip('/') for s in (API_PATH, "organisation", org_name))
        org_api_response = requests.request(method="GET", url=org_request_url,
            auth=requests.auth.HTTPBasicAuth(API_USER, API_PWD))
        r.set(redis_key, org_api_response.content, ex=300)
    return json.loads(r.get(redis_key).decode())


# get user groups
def get_user_groups(user):
    groups = []

    permission_model = app.config.get("PERMISSION_MODEL")

    # Org names: union of orgs for which the user is referent or contributor
    org_ids = set()
    if user.get("referent"):
        referent_orgs = [org.get("name") for org in user.get("referent")]
        org_ids.update(referent_orgs)
    if user.get("contribute"):
        contribute_orgs = [org.get("name") for org in user.get("contribute")]
        org_ids.update(contribute_orgs)

    for org_id in org_ids:
        org = get_org_info(org_id)
        if (permission_model == "datasud" and org.get("crige") == True) or permission_model != "datasud":
            user_role = "referent" if org_id in referent_orgs else "contributor"
            org_name = org.get("legal_name")
            groups.append(
                {
                    "id":         org_id,
                    "full_name":  org.get("legal_name"),
                    "slug_name":  slugify(org_name),
                    "user_role":  "referent",
                    "group_type": "organisation"
                }
            )

    logging.debug("user groups: {}".format(groups))

    return groups

# is the user an admin?
def is_user_admin(user):
    return user.get("admin")


# is the user a referent?
def is_user_referent(user):
    result = False
    if user.get("referent"):
        organisation_names = [org.get("name") for org in user.get("referent")]
        if len(organisation_names) > 0:
            result = True

    return result


# is the user a crige admin?
def is_user_crige_admin(user):
    return user.get("crige") and user.get("admin")


# is the user a CRIGE partner member?
def is_user_crige_partner_member(user):
    result = False
    if user.get("organisation"):
        org = get_org_info(user["organisation"].get("name"))
        result = (org.get("crige") == True)

    return result


# is the user a CRIGE partner contributor?
def is_user_crige_partner_contributor(user):
    result = False
    if user.get("contribute"):
        organisation_names = [org.get("name") for org in user.get("contribute")]
        for org_name in organisation_names:
            org = get_org_info(org_name)
            if org.get("crige"):
                result = True
                break

    return result


# is the user a CRIGE partner referent?
def is_user_crige_partner_referent(user):
    result = False
    if user.get("referent"):
        organisation_names = [org.get("name") for org in user.get("referent")]
        for org_name in organisation_names:
            org = get_org_info(org_name)
            if org.get("crige"):
                result = True
                break

    return result


def privileged_user_required(func):
    # Access to mviewerstudio is only given to admins and referents
    @wraps(func)
    def decorated_view(*args, **kwargs):
        # Preprocessing

        logging.debug("cas.username: {}".format(cas.username))
        user = get_user_info(cas.username)
        logging.debug("File get_user_info result: {}".format(user))

        if not user:
            abort(401)

        permission_model = app.config.get("PERMISSION_MODEL")

        # Datasud
        if permission_model == "datasud":
            is_user_allowed = (is_user_crige_admin(user) or is_user_crige_partner_member(user)) and \
                              (is_user_crige_partner_contributor(user) or is_user_crige_partner_referent(user))
        # IDéO BFC
        elif permission_model == "ideo-bfc":
            is_user_allowed = (is_user_admin(user) or is_user_referent(user))
        # Autre
        else:
            is_user_allowed = False

        logging.debug("is_user_allowed: {}".format(is_user_allowed))

        if not is_user_allowed:
            abort(403)
        return func(*args, **kwargs)

        # Postprocessing
    return decorated_view


@app.errorhandler(401)
def error_401(e):
    return send_from_directory(VIEWER_STUDIO_PATH, "401.html"), 401


@app.errorhandler(403)
def error_403(e):
    return send_from_directory(VIEWER_STUDIO_PATH, "403.html"), 403


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

conf = get_conf()

@app.route(PATH_INFO + "/srv/delete.php")
@login_required
@privileged_user_required
def viewerstudio_delete_user_content():
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
    user = get_user_info(cas.username)
    data = {}

    try:
        data["user_name"] = user.get("username")
        data["first_name"] = user.get("first_name")
        data["last_name"] = user.get("last_name")
        data["user_groups"] = get_user_groups(user)

    except (KeyError, ValueError) as e:
        logging.error(e)
        return flask.abort(400)
    else:
        if not data:
            raise flask.abort(404)
        else:
            return jsonify(data)


def get_user_content_in_folder(folder, user_role):
    user_content = []

    # List regular XML files
    entries = glob.glob(os.path.join(folder, "*.xml"))

    for entry in entries:
        file_path = os.path.join(folder, entry)
        try:
            log_message = "get_user_content_in_folder: reading file {}... folder: {}; user_role: {}".format(
                file_path, folder, user_role)
            logging.debug(log_message)

            with open(file_path, encoding="utf-8") as f:
                try:
                    xml = xmltodict.parse(f.read(), process_namespaces=False)

                    # admin user can access any xml file
                    # referent user can access any xml file for all organisation he is a referent for
                    # contributor user can access xml files of which he is the creator
                    description = xml["config"]["metadata"]["rdf:RDF"]["rdf:Description"]
                    if ((user_role == "contributor" and description["dc:creator"] == cas.username) or
                        user_role == "referent"):
                        url = file_path.replace(
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
                    logging.error("An error occurred while reading {}".format(file_path))
                    logging.error(e)

        except FileNotFoundError as e:
            log_message = "File not found exception while running get_user_content_in_folder function. " \
                          "folder: {}; user_role: {}; exception message: {}".format(folder, user_role, e)
            logging.debug(log_message)

    return user_content


@app.route(PATH_INFO + "/srv/list.php")
@login_required
@privileged_user_required
def viewerstudio_list_user_content():
    user = get_user_info(cas.username)
    user_groups = get_user_groups(user)
    user_content = []

    for group in user_groups:
        folder_name = group["slug_name"]
        user_role = group["user_role"]
        folder = os.path.join(conf["export_conf_folder"], folder_name)
        user_content.extend(get_user_content_in_folder(folder=folder, user_role=user_role))

    log_message = "user: {}; user content: {}".format(user, jsonify(user_content))
    logging.debug(log_message)

    return jsonify(user_content)


@app.route(PATH_INFO + "/srv/store.php", methods=["POST"])
@login_required
@privileged_user_required
def viewerstudio_store_user_content():

    xml0 = flask.request.data

    # Insert real user name
    user = get_user_info(cas.username)
    user_real_name = "{} {}".format(user.get("first_name"), user.get("last_name"))
    xml = xml0.decode().replace("anonymous", user_real_name)

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

    if os.path.exists(_map_directory):
        os.chmod(_map_directory, mode=0o770)
        logging.debug("directory stats after chmod: {}".format(str(os.stat(_map_directory))))

    filename = "{filename}.xml".format(filename=_map_title)

    file_path = os.path.join(_map_directory, filename)
    relative_file_path = "{}/{}".format(publisher, filename)

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(xml)
    os.chmod(file_path, mode=0o660)

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
