import os

from dotenv import load_dotenv

load_dotenv()

CDEK_API = os.getenv("CDEK_API")

CLIENT_ID = os.getenv("CLIENT_ID")

CLIENT_SECRET = os.getenv("CLIENT_SECRET")