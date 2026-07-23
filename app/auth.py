import requests

from app.config import (
    CDEK_API,
    CLIENT_ID,
    CLIENT_SECRET,
)


def get_token():

    url = f"{CDEK_API}/v2/oauth/token"

    response = requests.post(
        url,
        data={
            "grant_type": "client_credentials",
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
        },
    )

    response.raise_for_status()

    return response.json()