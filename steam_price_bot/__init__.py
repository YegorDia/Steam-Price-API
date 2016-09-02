from config import ConfigLoader
config = ConfigLoader()

API_HOST = config['steam-price-bot']['api_host']
API_PORT = config['steam-price-bot']['api_port']
API_SECRET = config['steam-price-bot']['secret']
STEAM_API_KEY = config['steam-price-bot']['steam_apikey']

from steam_price_bot import SteamPriceBot
