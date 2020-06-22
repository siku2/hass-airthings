BASE_URL = "https://api.airthin.gs/v1"

LOGIN_URL = f"{BASE_URL}/login"
REFRESH_URL = f"{BASE_URL}/refresh"

ME_URL = f"{BASE_URL}/me"
DEVICES_URL = f"{ME_URL}/devices"
SERIAL_NUMBERS_URL = f"{DEVICES_URL}/serialnumbers"
LATEST_SAMPLES_URL_TEMPLATE = f"{DEVICES_URL}/{{sn}}/segments/latest/samples"
