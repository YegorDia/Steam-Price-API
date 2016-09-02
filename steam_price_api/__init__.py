from config import ConfigLoader
config = ConfigLoader()

API_SECRET = config['api']['secret']
MONGODB_HOST = config['api']['mongodb']

from app import app as application