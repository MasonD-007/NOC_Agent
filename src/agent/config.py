import os

NEBIUS_API_KEY = os.environ["NEBIUS_API_KEY"]
NEBIUS_BASE_URL = os.environ.get("NEBIUS_BASE_URL", "https://api.tokenfactory.nebius.com/v1/")
NEBIUS_MODEL = os.environ.get("NEBIUS_MODEL", "moonshotai/Kimi-K2.5-fast")
