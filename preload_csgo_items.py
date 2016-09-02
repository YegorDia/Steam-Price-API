from steam_price_bot import API_HOST, API_PORT, API_SECRET, SteamPriceBot

if __name__ == "__main__":
    spb = SteamPriceBot(API_HOST, API_PORT, API_SECRET)
    spb.preload_csgo()