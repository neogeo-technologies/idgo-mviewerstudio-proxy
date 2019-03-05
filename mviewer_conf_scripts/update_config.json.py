# -*- coding: utf-8 -*-

import logging
import sys
import requests
import xml.etree.ElementTree as ET
import json

import config

logging.basicConfig(level=logging.DEBUG)


if __name__ == '__main__':
    idgo_settings_dir_path =None
    mra_settings = None
    mviewerstudio_config_file_path = None
    et_mra_workspaces = None
    et_workspace_names = None
    mra_workspaces_names = []
    organisations = []
    organisation_api_url = None
    ogc_url_pattern = None

    # Read script config file
    idgo_settings_dir_path = config.IDGO_ADMIN_SETTINGS_FILE_DIR
    logging.info("IDGO settings file directory path: {}".format(idgo_settings_dir_path))

    # Get MRA parameters
    sys.path.append(idgo_settings_dir_path)
    import settings as idgo_settings
    mra_settings = idgo_settings.MRA
    logging.debug("MRA settings: {}".format(mra_settings))
    ogc_url_pattern = idgo_settings.OWS_URL_PATTERN
    logging.debug("OGC URL pattern: {}".format(ogc_url_pattern))
    ogc_url_beginning = ogc_url_pattern.split("{")[0]
    logging.info("OGC URL beginning: {}".format(ogc_url_beginning))

    # Ask MRA for the list of workspaces
    mra_worspaces_url = mra_settings["URL"] + "workspaces.xml"
    logging.info("MRA request URL for workspaces: {}".format(mra_worspaces_url))

    r = requests.get(mra_worspaces_url, auth=(mra_settings["USERNAME"], mra_settings["PASSWORD"]))
    if r.status_code != 200:
        logging.error("MRA request aborted")
        logging.error("Request URL: {}".format(mra_worspaces_url))
        logging.error("Request status code: {}".format(r.status_code))
        logging.error("Request response: {}".format(r.text))
        sys.exit("MRA request aborted")

    et_mra_workspaces = ET.fromstring(r.text)
    et_workspace_names = et_mra_workspaces.findall("./workspace/name")
    for et_name in et_workspace_names:
        mra_workspaces_names.append(et_name.text)

    logging.info("MRA workspaces names: {}".format(mra_workspaces_names))

    # Organisation API calls
    organisation_api_url = idgo_settings.DOMAIN_NAME + "/api/organisation/"

    for organisation_slug_name in mra_workspaces_names:
        organisation_name = None
        organisation_wms_url = None

        r = requests.get(organisation_api_url + organisation_slug_name)

        if r.status_code == 200:
            organisation = json.loads(r.text)
            organisations.append({
                "name": organisation["name"],
                "legal_name": organisation["legal_name"],
                "wms_url": ogc_url_pattern.format(organisation=organisation_slug_name)
            })

    logging.info("Organisations and WMS URLs: {}".format(organisations))

    # Read studio config file
    mviewerstudio_config_file_path = config.STUDIO_CONFIG_FILE
    logging.info("Studio config file path: {}".format(mviewerstudio_config_file_path))
    studio_conf = None
    with open(mviewerstudio_config_file_path) as f:
        studio_conf = json.load(f)

    # Remove existing data providers
    studio_conf["app_conf"]["data_providers"]["wms"] = \
        [wms for wms in studio_conf["app_conf"]["data_providers"]["wms"] if not wms["url"].startswith(ogc_url_beginning)]

    # Insert data providers
    provider_title_prefix = config.STUDIO_CONFIG_PROVIDER_TITLE_PREFIX
    for organisation in organisations:
        studio_conf["app_conf"]["data_providers"]["wms"].append(
            {
                "url": organisation["wms_url"],
                "title": "{}{}".format(provider_title_prefix, organisation["legal_name"])
            })

    # Save config file
    with open(mviewerstudio_config_file_path, 'w') as f:
        json.dump(studio_conf, f, indent=4, sort_keys=True)
