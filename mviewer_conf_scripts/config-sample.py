OUTPUT_STUDIO_CONFIG_FILE = "/var/www/html/viewerstudio/config.json"
INPUT_STUDIO_CONFIG_FILE = "/apps/mviewerstudio-cas/mviewer_conf_scripts/config-idgo-base.json"
STUDIO_CONFIG_PROVIDER_TITLE_PREFIX = "IDéO BFC - "

# Same settings as the IDGO ones
DOMAIN_NAME = 'https://{{domain}}'
ORGANISATION_API_URL = DOMAIN_NAME + "/api/organisation/"
MRA = {
    'URL': 'http://{{mapserver_host}}:8001/',
    'DATAGIS_DB_USER': 'datagis',
    'PASSWORD': '{{db_datagis_password}}',
    'USERNAME': "admin"
}
OWS_URL_PATTERN = 'https://{{ogc_domain}}/maps/{organisation}'
