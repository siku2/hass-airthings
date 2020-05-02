from yarl import URL

ACCOUNTS_BASE_URL = URL("https://accounts-api.airthings.com/v1/")
TOKEN_URL = ACCOUNTS_BASE_URL.join(URL("token"))

WEB_API_BASE_URL = URL("https://web-api.airthin.gs/v1/")
ME_URL = WEB_API_BASE_URL.join(URL("me"))

