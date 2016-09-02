# coding=utf-8
import requests
import time
import json
import vdf
import io
import os
import traceback
import datetime
from proxy import get_proxy_list
from random import choice
from . import STEAM_API_KEY
from requests.exceptions import ConnectTimeout

ITEMS_PATH = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'csgo_files/items_game.txt')
LANG_PATH = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'csgo_files/csgo_english.txt')


def dict_to_query(d):
    query = '?'
    for key in d.keys():
        query += str(key) + '=' + str(d[key]) + "&"
    return query


class SteamPriceBot(object):
    def __init__(self, api_host, api_port, secret, protocol="http"):
        self.host = api_host
        self.port = api_port
        self.protocol = protocol
        self.url = "%s://%s:%s" % (self.protocol, self.host, self.port) if self.port != 80 else "%s://%s" % (
            self.protocol, self.host)
        self.secret = secret
        self.proxies = []
        self.last_proxy = None
        self._session = requests.session()
        self._session.headers.update(
            {"Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8"})
        self._session.headers.update({"Accept-Encoding": "gzip, deflate, sdch"})
        self._session.headers.update({"Cache-Control": "no-cache"})
        self._session.headers.update({"Connection": "keep-alive"})
        self._session.headers.update({"Host": "steamcommunity.com"})
        self._session.headers.update({"Pragma": "no-cache"})
        self._session.headers.update({"Referer": "http://steamcommunity.com/market/"})
        self._session.headers.update({"Upgrade-Insecure-Requests": "1"})
        self._session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 6.3; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/47.0.2526.106 Safari/537.36"})

        try:
            self.authorized = self.test_connection()
        except:
            self.authorized = False

    def refresh_proxies(self):
        self.proxies = get_proxy_list()

    def run_forever(self):
        while True:
            queued_items = self.get_queued_items()
            if queued_items["data"].get("count", 0) == 0:
                default_item = self.get_default_item()
                if default_item.get("success", False):
                    self.get_item_price(int(default_item["data"]["item"]["appid"]),
                                        default_item["data"]["item"]["market_hash_name"])
                    time.sleep(2)
                else:
                    time.sleep(5)
            else:
                for queued in queued_items["data"]["items"]:
                    self.get_item_price(int(queued["appid"]), queued["market_hash_name"])
                    time.sleep(2)

            time.sleep(10)

    def get_queued_items(self):
        return self.request_api(method="get", path="/price/queued", data=None)

    def get_default_item(self):
        return self.request_api(method="get", path="/price/default", data=None)

    def clean_queue_item(self, market_hash_name, appid):
        return self.request_api(method="post", path="/price/remove",
                                data={"market_hash_name": market_hash_name, "appid": appid})

    def request_api(self, method="get", path="/", data=None):
        if not data:
            data = dict(key=self.secret)
        else:
            data["key"] = self.secret

        if method == 'post':
            response = self._session.post("%s%s" % (self.url, path), data=data)
        else:
            query = ''
            if data:
                query = dict_to_query(data)
            response = self._session.get("%s%s%s" % (self.url, path, query))

        return response.json()

    def test_connection(self):
        return self.request_api().get("success", False)

    def get_item_price(self, appid, market_hash_name):
        time.sleep(6.5)
        url = 'http://steamcommunity.com/market/priceoverview/?key=%s&currency=1&l=en&appid=%s&market_hash_name=%s' % (
            STEAM_API_KEY, appid, market_hash_name)
        price = self._session.get(url)

        used_proxies = []
        while price.status_code == 429:
            if len(self.proxies) == 0:
                self.refresh_proxies()

            if len(used_proxies) >= len(self.proxies):
                used_proxies = []
                self.proxies = []
                time.sleep(10)
                self.refresh_proxies()
                continue

            current_proxy = self.last_proxy if self.last_proxy and self.last_proxy not in used_proxies else choice(
                self.proxies)
            if current_proxy not in used_proxies:
                proxy_dict = {
                    "http": "http://%s" % current_proxy,
                    # "https": "https://%s" % current_proxy,
                }
                try:
                    price = self._session.get(url, proxies=proxy_dict, timeout=7)
                    if price.status_code == 500 or price.status_code == 200:
                        self.last_proxy = current_proxy
                        time.sleep(2.5)
                    elif price.status_code == 429:
                        used_proxies.append(current_proxy)
                except:
                    if price.status_code != 200:
                        self.last_proxy = None
                        time.sleep(1)
                    else:
                        self.last_proxy = current_proxy
                        time.sleep(2.5)

        if price.status_code == 400 or price.status_code == 500:
            self.clean_queue_item(market_hash_name, appid)
            return False

        price_data = {}
        try:
            price_data = json.loads(price.content.encode('utf-8'))
        except ValueError:
            return False

        if price_data.get("success", False):
            lowest_price = price_data.get('lowest_price', '&#36;-1')
            median_price = price_data.get('median_price', lowest_price)
            if lowest_price == '&#36;-1' and median_price != '&#36;-1':
                lowest_price = median_price
            try:
                new_median_price = float(median_price.split('&#36;')[1])
                new_lowest_price = float(lowest_price.split('&#36;')[1])
            except:
                try:
                    new_median_price = float(median_price.split('$')[1])
                    new_lowest_price = float(lowest_price.split('$')[1])
                except:
                    raise Exception('Convert error')

            sold_weekly = -1

            if new_lowest_price > 1:
                graph_price = self.get_graph_price(market_hash_name, appid, new_lowest_price)
                new_lowest_price = graph_price["price"]
                new_median_price = new_lowest_price
                sold_weekly = graph_price["sold_weekly"]

            return self.update_item_price(market_hash_name, appid, new_lowest_price, new_median_price,
                                          sold_weekly=sold_weekly).get("success", False)
        return False

    def get_available(self):
        return self.request_api(method="get", path="/price/available", data=None)

    def get_graph_price(self, market_hash_name, appid, lowest_price):
        url = 'http://steamcommunity.com/market/listings/%s/%s?l=en' % (appid, market_hash_name)
        tries = 0

        market_listing = self._session.get(url)
        while market_listing.status_code != 200 and tries < 10:
            market_listing = self._session.get(url)
            tries += 1
            time.sleep(15)

        if market_listing.status_code == 200:
            try:
                datetime_now = datetime.datetime.now()
                sold_weekly = 0

                html = market_listing.content
                graph_substr = "var line1="
                graph_index = html.find(graph_substr)
                if graph_index != -1:
                    substring_one = html[(graph_index + len(graph_substr)):]
                    graph_index_end = substring_one.find("g_timePriceHistoryEarliest = new Date();")
                    json_string = substring_one[:-(len(substring_one) - graph_index_end)].rstrip()[:-1]
                    graph_data = json.loads(json_string)
                    if len(graph_data) > 10:
                        to_count = 10
                    else:
                        to_count = len(graph_data)
                    price = 0

                    counted = 0
                    avg_price = 0
                    for i in range(len(graph_data) - to_count, len(graph_data)):

                        try:
                            sell_datetime_parts = graph_data[i][0].split(' ')
                            sell_datetime_string = "%s %s %s" % (
                                sell_datetime_parts[2],
                                sell_datetime_parts[0],
                                sell_datetime_parts[1]
                            )
                            sell_datetime = datetime.datetime.strptime(sell_datetime_string, "%Y %b	%d")

                            if sell_datetime > datetime_now - datetime.timedelta(days=7):
                                sold_weekly += int(graph_data[i][2])
                        except:
                            pass

                        avg_price += float(graph_data[i][1])
                        counted += 1
                    avg_price /= float(counted)

                    counted = 0
                    for i in range(len(graph_data) - to_count, len(graph_data)):
                        if float(graph_data[i][1]) <= (avg_price * 1.3):
                            price += float(graph_data[i][1])
                            counted += 1
                    price /= float(counted)

                    return dict(price=price, sold_weekly=sold_weekly)
            except:
                print "Error with %s " % market_hash_name
                traceback.print_exc()

        return dict(price=-1, sold_weekly=0)

    def update_item_price(self, market_hash_name, appid, lowest_price, median_price, sold_weekly=-1):
        data = {
            "market_hash_name": market_hash_name,
            "appid": appid,
            "lowest_price": lowest_price,
            "median_price": median_price
        }

        if sold_weekly != -1 and sold_weekly < 4:
            data["drop_price"] = "yes"

        data["sold_last_week"] = sold_weekly

        return self.request_api('post', '/price/upsert', data=data)

    # Required 2 fresh csgo files:
    # .. \Steam\steamapps\common\Counter-Strike Global Offensive\csgo\scripts\items\items_game.txt
    # .. \Steam\steamapps\common\Counter-Strike Global Offensive\csgo\resource\csgo_english.txt
    def preload_csgo(self):
        print "preload csgo items ..."
        items_game = vdf.load(open(ITEMS_PATH)).get('items_game', {})
        lang_file = vdf.load(io.open(LANG_PATH, 'r', encoding='utf-16')).get('lang', {})
        schema_data = \
            requests.get("https://api.steampowered.com/IEconItems_730/GetSchema/v2/?key=%s" % STEAM_API_KEY).json()[
                "result"]
        added_skins = []
        available = self.get_available()
        if available.get("success", False):
            added_skins = available["data"]["items"]
        print "OK"
        print ""

        def get_translation(token):
            return lang_file["Tokens"].get(token[1:], None)

        print "load source weapons from schema ..."
        source_weapons = {}

        for item in schema_data["items"]:
            if item.get("name", "").startswith("weapon_") and item.get("item_name", False):
                name = get_translation(item["item_name"])
                type = get_translation(item["item_type_name"])
                if name != type and type not in ['Grenade', 'C4']:
                    source_weapons[item["name"]] = name
        print "OK"
        print ""

        print "load case keys from items_game ..."
        case_keys = [u'CS:GO Case Key', u'eSports Key', u'CS:GO Capsule Key']

        for item in items_game["items"].iteritems():
            item = item[1]
            if item.get("prefab", "").startswith("weapon_case_key") and item.get("item_name", False):
                name = get_translation(item["item_name"])
                if name not in case_keys:
                    case_keys.append(name)
        print "OK"
        print ""

        print "load cases from items_game ..."
        cases = []

        for item in items_game["items"].iteritems():
            item = item[1]
            if (item.get("prefab", "").startswith("weapon_case") or item.get("prefab", "").startswith(
                    "weapon_case_base")) and item.get("item_name", False):
                name = get_translation(item["item_name"])
                if name not in cases and name not in case_keys:
                    cases.append(name)
        print "OK"
        print ""

        print "load music_definitions from items_game ..."
        music_kits = []

        for item in items_game["music_definitions"].iteritems():
            item = item[1]
            if item.get("name", "").find("valve") == -1:
                name = get_translation(item["loc_name"])
                if name not in music_kits:
                    music_kits.append(u"Music Kit | %s" % name)
        print "OK"
        print ""

        print "load stickers from items_game ..."
        stickers = []

        for item in items_game["sticker_kits"].iteritems():
            item = item[1]
            if item.get("name", "").find("default") == -1:
                name = get_translation(item["item_name"])
                if name not in stickers:
                    stickers.append(u"Sticker | %s" % name)
        print "OK"
        print ""

        print "load source skins from items_game ..."
        source_skins = []

        for key, weapon_icon in items_game.get('alternate_icons2', {})["weapon_icons"].iteritems():
            source_weapon_name = weapon_icon.get('icon_path', None)
            if source_weapon_name:
                source_weapon_name = source_weapon_name.split("generated/")[1]
                source_skins.append(source_weapon_name)
        print "OK"
        print ""

        print "load source paint kits from items_game ..."
        source_kits = {}

        for key, paint_kit in items_game["paint_kits"].iteritems():
            if paint_kit.get("description_tag", False):
                source_kits[paint_kit["name"]] = get_translation(paint_kit["description_tag"])
        print "OK"
        print ""

        print "compiling skins from source paint kits, source weapons and source skins ..."
        skins = []

        for source_skin in source_skins:
            for source_weapon in source_weapons.keys():
                if source_skin.startswith(source_weapon):
                    try:
                        kit_name_split = source_skin[len(source_weapon) + 1:].rsplit('_', 1)
                        kit_source_name = kit_name_split[0]
                        kit_source_type = kit_name_split[1]
                        new_skin = "%s | %s" % (source_weapons[source_weapon], source_kits[kit_source_name])
                        if new_skin not in skins:
                            skins.append(new_skin)
                        continue
                    except:
                        pass
        print "OK"
        print ""

        exteriors = [
            "Battle-Scarred",
            "Well-Worn",
            "Field-Tested",
            "Minimal Wear",
            "Factory New"
        ]

        print "updating case prices ..."
        for case in cases:
            if case not in added_skins:
                case = case.replace("/", "-")
                print ("\tupdating case - %s\t. . ." % case).encode('utf-8'),
                print str(self.get_item_price(730, case))
                added_skins.append(case)
        print "OK"
        print ""

        print "updating case keys prices ..."
        for case_key in case_keys:
            if case_key not in added_skins:
                print ("\tupdating case key - %s\t. . ." % case_key).encode('utf-8'),
                print str(self.get_item_price(730, case_key))
                added_skins.append(case_key)
        print "OK"
        print ""

        print "updating music kit prices ..."
        for music_kit in music_kits:
            market_hash_name = music_kit
            stattrack_version = "%s %s" % (u"StatTrak™", music_kit)
            if market_hash_name not in added_skins:
                print ("\tupdating music kit - %s\t. . ." % market_hash_name).encode('utf-8')
                print str(self.get_item_price(730, market_hash_name))
                added_skins.append(market_hash_name)
            if stattrack_version not in added_skins:
                print ("\tupdating music kit - %s\t. . ." % stattrack_version).encode('utf-8'),
                print str(self.get_item_price(730, stattrack_version))
                added_skins.append(stattrack_version)
        print "OK"
        print ""

        print "updating sticker prices ..."
        for sticker in stickers:
            if sticker not in added_skins and sticker.find("(Gold)") == -1:
                print ("\tupdating sticker - %s\t. . ." % sticker).encode('utf-8'),
                print str(self.get_item_price(730, sticker))
                added_skins.append(sticker)
        print "OK"
        print ""

        print "updating weapon skin prices ..."
        for skin in skins:
            for exterior in exteriors:
                market_hash_name = "%s (%s)" % (skin, exterior)
                stattrack_version = "%s %s" % (u"StatTrak™", market_hash_name)

                if skin.find("Knife") != -1 or skin.find("Bayonet") != -1 or skin.find("Karambit") != -1 or skin.find(
                        "Shadow Daggers") != -1:
                    market_hash_name = u"★ %s" % market_hash_name
                    stattrack_version = u"★ %s" % stattrack_version

                if market_hash_name not in added_skins:
                    print ("\tupdating weapon skin - %s\t. . ." % market_hash_name).encode('utf-8'),
                    print str(self.get_item_price(730, market_hash_name))
                    added_skins.append(market_hash_name)

                if stattrack_version not in added_skins:
                    print ("\tupdating weapon skin - %s\t. . ." % stattrack_version).encode('utf-8'),
                    print str(self.get_item_price(730, stattrack_version))
                    added_skins.append(stattrack_version)

        print "OK"
        print ""







