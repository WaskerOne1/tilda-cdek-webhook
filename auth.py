import requests
from config import CDEK_API, CLIENT_ID, CLIENT_SECRET


def get_token():
    url = f"{CDEK_API}/v2/oauth/token"

    data = {
        "grant_type": "client_credentials",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
    }

    response = requests.post(url, data=data)
    response.raise_for_status()

    return response.json()["access_token"]