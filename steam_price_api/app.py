import datetime
from flask import Flask, jsonify, request, abort, render_template, redirect
from flask.ext.pymongo import PyMongo
from . import API_SECRET, MONGODB_HOST

VERSION = 1
api_secret = API_SECRET
app = Flask(__name__)
app.config['MONGO_DBNAME'] = 'prices'
app.config['MONGO_HOST'] = MONGODB_HOST
app.config['MONGO_CONNECT'] = False
app.debug = True
mongo = PyMongo(app)


@app.before_request
def before_request():
    api_key = request.args.get("key", request.form.get("key", None))
    if not api_key == api_secret:
        return abort(401)


@app.route('/', methods=["get"])
def index():
    data = {}
    success = True
    today_date = datetime.datetime.utcnow().date()
    today_start = datetime.datetime(year=today_date.year, month=today_date.month, day=today_date.day, hour=0, minute=0, second=0)
    today_end = datetime.datetime(year=today_date.year, month=today_date.month, day=today_date.day, hour=23, minute=59, second=59)

    avaialable_prices = mongo.db.items.find({'last_updated': {"$ne": None}}).count()
    queued_prices = mongo.db.items.find({'last_updated': None}).count()
    updated_today = mongo.db.items.find({'last_updated': {'$gte': today_start, '$lt': today_end}}).count()

    data["count"] = avaialable_prices
    data["queued"] = queued_prices
    data["updated"] = updated_today

    return jsonify({
        "version": VERSION,
        "data": data,
        "success": success
    })


@app.route('/price/', methods=["get"])
def price_edit():
    data = {}

    items = mongo.db.items.find({'last_updated': {"$ne": None}, 'manual': {"$ne": True}}, {
        "market_hash_name": 1,
        "average_price": 1,
        "lowest_price": 1,
        "sold_last_week": 1,
        "last_updated": 1,
        "manual": 1
    }).sort("average_price", -1)

    data["items"] = list(items)
    for item in data["items"]:
        if item.get("_id", False):
            item.pop("_id", None)

    manual_items = mongo.db.items.find({'manual': True}, {
        "market_hash_name": 1,
        "average_price": 1,
        "lowest_price": 1,
        "sold_last_week": 1,
        "last_updated": 1,
        "manual": 1
    }).sort("average_price", -1)

    data["manual_items"] = list(manual_items)
    for item in data["manual_items"]:
        if item.get("_id", False):
            item.pop("_id", None)

    data["count"] = len(data["items"])

    return render_template('index.jinja2', data=data, key=api_secret)


@app.route('/price/', methods=["POST"])
def price_edit_post():
    id = request.form.get('id')

    if id:
        item = mongo.db.items.find_one({"market_hash_name": id})
        if item:
            price = request.form.get('price')
            remove = request.form.get('remove')
            update = request.form.get('update', False)
            if price:
                if not update:
                    mongo.db.items.update({"_id": item.get('_id')}, {"$set": {
                        "last_updated": datetime.datetime.now(),
                        "manual": True,
                        "average_price": float(price)
                    }})
                else:
                    avg_price = (float(item.get("average_price", float(price))) + float(price)) / 2
                    avg_price = round(avg_price, 2)
                    mongo.db.items.update({"_id": item.get('_id')}, {"$set": {
                        "last_updated": datetime.datetime.now(),
                        "average_price": avg_price
                    }})

            elif remove:
                mongo.db.items.update({"_id": item.get('_id')}, {"$set": {
                    "last_updated": datetime.datetime.now(),
                    "average_price": -1
                }, "$unset": {
                    "manual": ""
                }})
    return redirect('/price/?key=' + api_secret)


@app.route('/price/available', methods=["get"])
def price_available():
    data = {}
    success = True

    items = mongo.db.items.find({'last_updated': {"$ne": None}}, {
        "market_hash_name": 1,
        "average_price": 1,
        "lowest_price": 1,
        "sold_last_week": 1
    }).sort("average_price", -1)

    data["items"] = list(items)
    for item in data["items"]:
        if item.get("_id", False):
            item.pop("_id", None)

    data["count"] = len(data["items"])

    return jsonify({
        "version": VERSION,
        "data": data,
        "success": success
    })


@app.route('/price/<market_hash_name>', methods=["get"])
def price_get(market_hash_name):
    data = {}
    success = True

    item = mongo.db.items.find_one({"market_hash_name": market_hash_name})
    if not item:
        success = False
    else:
        item["_id"] = str(item["_id"])
        item.pop("last_updated")
        data = {
            "item": item
        }

    return jsonify({
        "version": VERSION,
        "data": data,
        "success": success
    })


@app.route('/price/many', methods=["get"])
def price_many():
    data = {}
    success = True
    market_hash_names = list(set(request.args.get("market_hash_names", "").split(';')))
    appid = request.args.get("appid", 730)

    if len(market_hash_names) <= 0:
        success = False
    else:
        items = list(mongo.db.items.find({"market_hash_name": {"$in": market_hash_names}}))
        found_market_hash_names = [item["market_hash_name"] for item in items]
        not_found_market_hash_names = []
        for market_hash_name in market_hash_names:
            if market_hash_name not in found_market_hash_names and len(market_hash_name) > 0:
                not_found_market_hash_names.append(market_hash_name)

        items_to_place_in_queue = [{
            "market_hash_name": not_found_market_hash_name,
            "appid": int(appid),
            "last_updated": None
        } for not_found_market_hash_name in not_found_market_hash_names]

        if len(items_to_place_in_queue) > 0:
            try:
                result = mongo.db.items.insert(items_to_place_in_queue)
            except:
                success = False
                data["error"] = "Cannot put new items in queue"

        data["items"] = items

        for item in data["items"]:
            item["_id"] = str(item["_id"])
            item.pop("last_updated")

        data["queued"] = len(not_found_market_hash_names)
        data["count"] = len(found_market_hash_names)

    return jsonify({
        "version": VERSION,
        "data": data,
        "success": success
    })


@app.route('/price/default', methods=["get"])
def price_default():
    data = {}
    success = True

    week_above = datetime.datetime.now() + datetime.timedelta(weeks=1)

    item = list(mongo.db.items.find({
        "last_updated": {
            "$lte": week_above
        },
        "manual": {"$ne": True}
    }).sort("last_updated", 1).limit(1))
    if len(item) <= 0:
        success = False
    else:
        item = item[0]
        item.pop("last_updated")
        item.pop("_id")
        item.pop("lowest_price")
        item.pop("median_price")
        data = {
            "item": item
        }

    return jsonify({
        "version": VERSION,
        "data": data,
        "success": success
    })


@app.route('/price/queued', methods=["get"])
def price_queued():
    data = {}
    success = True

    items = mongo.db.items.find({'last_updated': None})
    # items = mongo.db.items.find({}).limit(5) # test
    data["items"] = []
    for item in items:
        data["items"].append({"market_hash_name": item["market_hash_name"], "appid": item["appid"]})

    data["count"] = len(data["items"])

    return jsonify({
        "version": VERSION,
        "data": data,
        "success": success
    })


@app.route('/price/queue', methods=["post"])
def price_queue_to_refresh():
    data = {}
    success = True

    market_hash_name = request.form.get("market_hash_name", None)
    appid = request.form.get("appid", None)
    if market_hash_name and appid:
        result = mongo.db.items.insert({
            "market_hash_name": market_hash_name,
            "appid": int(appid),
            "last_updated": None
        })
        if result.get("ok", 0) != 1:
            success = False

    return jsonify({
        "version": VERSION,
        "data": data,
        "success": success
    })


@app.route('/price/remove', methods=["post"])
def price_remove():
    data = {}
    success = True
    market_hash_name = request.form.get("market_hash_name", None)
    appid = request.form.get("appid", None)

    result = mongo.db.items.remove({"market_hash_name": market_hash_name, "appid": int(appid)})
    if result.get("ok", 0) != 1:
        success = False

    data["removed"] = result.get("n", 0)

    return jsonify({
        "version": VERSION,
        "data": data,
        "success": success
    })


@app.route('/price/upsert', methods=["post"])
def price_upsert():
    data = {}
    success = True
    market_hash_name = request.form.get("market_hash_name", None)
    appid = request.form.get("appid", 730)
    lowest_price = request.form.get("lowest_price", None)
    median_price = request.form.get("median_price", None)
    sold_last_week = request.form.get("sold_last_week", -1)
    drop_price = request.form.get("drop_price", None)
    if market_hash_name and lowest_price and median_price and appid and sold_last_week:
        if drop_price:
            lowest_price = -1
            median_price = -1
            avg_price = -1
        else:
            lowest_price = float(lowest_price)
            median_price = float(median_price)
            avg_price = float(lowest_price)

            if lowest_price > 0:
                db_item = mongo.db.items.find_one({"market_hash_name": market_hash_name, "appid": int(appid)})
                if db_item and "average_price" in db_item:
                    avg_price = (float(db_item["average_price"]) + avg_price) / 2
                avg_price = round(avg_price, 2)

        result = mongo.db.items.update({"market_hash_name": market_hash_name, "appid": int(appid)}, {
            "market_hash_name": market_hash_name,
            "appid": int(appid),
            "lowest_price": lowest_price,
            "median_price": median_price,
            "sold_last_week": int(sold_last_week),
            "last_updated": datetime.datetime.utcnow()
        }, upsert=True)

        mongo.db.items.update({"market_hash_name": market_hash_name, "appid": int(appid)}, {"$set": {
            "average_price": avg_price
        }})

        if result.get("ok", 0) != 1:
            success = False
        else:
            if result.get("updatedExisting", False):
                data["updated"] = True
            if result.get("upserted", False):
                data["upserted"] = str(result["upserted"])

    return jsonify({
        "version": VERSION,
        "data": data,
        "success": success
    })
