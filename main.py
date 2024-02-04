# coding=utf-8
import json
import sys
import time
from datetime import datetime

import requests
from config import *

MEDIA_PRE = "https://media-photos.depop.com/b1/"
WEB_API_PRE = "https://webapi.depop.com/api/v1/"
WEB_API_PRE_2 = "https://webapi.depop.com/api/v2/"
RELATIONSHIP_PRE = WEB_API_PRE + "follows/relationship/"
FOLLOW_PRE = WEB_API_PRE + "follows/"
SHOP_PRE = WEB_API_PRE + "shop/"
FOLLOWERS = WEB_API_PRE + "user/{0}/followers/"
LOGIN = WEB_API_PRE + "auth/login/"
DEVICES = WEB_API_PRE + "auth/mfa/devices/"
CHALLENGE = DEVICES + "{0}/challenge/"
LIKES = WEB_API_PRE + "likes/notifications/"
PRODUCT_BY_ID = WEB_API_PRE_2 + "product/by-id/{0}/"
OFFERS = WEB_API_PRE_2 + "offers/seller/products/{0}/offers/"
PRODUCTS = WEB_API_PRE + "shop/{0}/products/"
PRODUCT = WEB_API_PRE_2 + "products/{0}/"


def headers():
    return {
        "authority": "webapi.depop.com",
        "accept": "application/json",
        "accept-language": "en-GB,en-US;q=0.9,en;q=0.8",
        "depop-user-id": USER_ID,
        "origin": "https://www.depop.com",
        "referer": "https://www.depop.com/",
        "sec-ch-ua": "\"Chromium\";v=\"118\", \"Brave\";v=\"118\", \"Not=A?Brand\";v=\"99\"",
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": "\"Windows\"",
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-site",
        "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/104.0.5112.79 Safari/537.36 "
    }


def getsellers(session, remove_following=True, category=CATEGORY):
    products = f"https://webapi.depop.com/api/v2/search/products/?categories={category}&itemsPerPage={MAX_SELLERS}\
                &country=gb&currency=GBP&userId={USER_ID}&sort=relevance"
    response = session.get(products)
    sellers = []

    if response.status_code != 200:
        raise Exception(f"Bad response from server when getting products: {response.status_code}")

    data = response.json()
    if data["meta"]["resultCount"] == 0:
        raise Exception("No products found")

    for product in data["products"]:
        photo_url = list(product["preview"].values())[0]
        seller_id = photo_url.lstrip(MEDIA_PRE).split("/")[0]
        seller_name = product["slug"].split("-")[0]
        sellers.append((seller_id, seller_name))

    sellers = list(set(sellers))
    if remove_following:
        print("Removing sellers already followed")
        new_sellers = []
        for seller in sellers:
            sellerid = seller[0]
            try:
                following = isfollowing(session, sellerid)
                if not following:
                    new_sellers.append(seller)
            except Exception as e:
                print(f"Ignored adding seller {seller}-{sellerid} {e}")
                continue
        return new_sellers

    return sellers


def getfollowers(session, seller, remove_following=True, remove_inactive=True):
    heads = session.headers
    heads["authorization"] = f"Bearer {TOKEN}"
    url = FOLLOWERS.format(seller[0])

    response = session.get(url, headers=heads)
    if response.status_code != 200:
        if response.status_code == 429:
            print("Rate limited so sleeping 1 minute")
            time.sleep(60)
        raise Exception(f"Couldn't get followers {response.status_code}")

    followers = []
    flag = False
    count = 0
    max_recursion = MAX_SELLERS // 20

    while True:
        if flag:
            break
        if count > max_recursion:
            break
        count += 1

        for follower in response.json()["objects"]:
            sellerid = follower["id"]
            sellername = follower["username"]
            seller = (sellerid, sellername)

            try:
                following = False
                active = True
                if remove_following:
                    following = isfollowing(session, sellerid)
                if remove_inactive:
                    active = isactive(session, seller)
                if not following and active:
                    followers.append(seller)

            except Exception as e:
                print(f"Ignored adding follower {seller}-{sellerid} {e}")

        if response.json()["meta"]["end"]:
            flag = True
        else:
            newurl = url + f"?offset_id={response.json()['meta']['last_offset_id']}"

            response = session.get(newurl, headers=heads)
            if response.status_code != 200:
                if response.status_code == 429:
                    print("Rate limited so won't get all followers")
                    flag = True
                print(f"Couldn't get followers {response.status_code}")

    print(f"Added {len(followers)} followers")
    return followers


def isactive(session, seller):
    sellername = seller[1]
    url = f"{SHOP_PRE}{sellername}"

    response = session.get(url)
    if response.status_code != 200:
        if response.status_code == 429:
            print("Rate limited so sleeping 1 minute")
            time.sleep(60)
        print(f"Couldn't check if seller active {response.status_code}")

    lastseen = response.json()["last_seen"]
    lastseen = datetime.strptime(lastseen, "%Y-%m-%dT%H:%M:%S.%fZ")

    diff = datetime.now() - lastseen
    return diff.seconds < 604800


def isfollowing(session, sellerid):
    heads = session.headers
    heads["authorization"] = f"Bearer {TOKEN}"
    url = f"{RELATIONSHIP_PRE}{sellerid}"

    response = session.get(url, headers=heads)
    if response.status_code != 200:
        if response.status_code == 429:
            print("Rate limited so sleeping 1 minute")
            time.sleep(60)
        raise Exception(f"Couldn't check if following seller {response.status_code}")

    return response.json()["isFollowing"]


def changerelationship(session, sellers, follow=True):
    print(f"Starting {'follow' if follow else 'unfollow'}ing sellers")
    worked = []
    heads = session.headers
    heads["authorization"] = f"Bearer {TOKEN}"

    for seller in sellers:
        sellerid = seller[0]
        url = f"{FOLLOW_PRE}{sellerid}"

        if follow:
            response = session.put(url, headers=heads)
        else:
            response = session.delete(url, headers=heads)

        if response.status_code not in (202, 204):
            if response.status_code == 429:
                print("Rate limited so ending now")
                break
            print(f"Ignored {'following' if follow else 'unfollowing'} seller \
                    {seller} {response.status_code}")
        else:
            worked.append(seller)

    print(f"{len(worked)} out of {len(sellers)} {'followed' if follow else 'unfollowed'}")
    return worked


def newfollowbatch(session, category=CATEGORY):
    print(f"Starting new follow batch with max {MAX_SELLERS} sellers and category {category}")
    sellers = getsellers(session, category=category)

    if len(sellers) == 0:
        print("No new sellers found")
        sys.exit()

    print(f"Found {len(sellers)} new sellers")
    followed = changerelationship(session, sellers)
    print(f"Followed {len(followed)} new sellers")

    with open("followed.json") as f:
        data = json.load(f)
    data["ids"].extend(followed)
    with open("followed.json", "w") as f:
        json.dump(data, f, indent=4)

    print("Complete dump")


def shopfollowbatch(session):
    print(f"Starting shop follow batch with max {MAX_SELLERS} sellers")

    sellerid = input("Enter seller id: ")
    sellername = input("Enter seller name: ")
    seller = (sellerid, sellername)
    followers = getfollowers(session, seller, remove_inactive=NOINACTIVES)

    if len(followers) == 0:
        print("No new sellers found")
        sys.exit()

    print(f"Found {len(followers)} new sellers")
    followed = changerelationship(session, followers)
    print(f"Followed {len(followed)} new sellers")

    with open("followed.json") as f:
        data = json.load(f)
    data["ids"].extend(followed)
    with open("followed.json", "w") as f:
        json.dump(data, f, indent=4)

    print("Complete dump")


def unfollowbatch(session):
    print(f"Starting unfollow batch")
    with open("followed.json") as f:
        data = json.load(f)
    sellers = data["ids"]
    failed = []

    worked = changerelationship(session, sellers, follow=False)
    print(f"Unfollowed {len(worked)} sellers")
    for seller in sellers:
        if seller not in worked:
            failed.append(seller)

    print(f"Failed to unfollow {len(failed)} sellers")
    data["ids"] = failed
    with open("followed.json", "w") as f:
        json.dump(data, f, indent=4)
    print("Redumped")


def loginwithuserpass(session):
    data = {
        "username": USERNAME,
        "password": PASSW
    }

    response = session.post(LOGIN, data=data)
    if response.status_code != 403:
        print(f"Error encountered when logging in {response.status_code} {response.json()}")
        sys.exit()
    print("MFA required, fetching")

    mfa_token = response.json()["mfa_token"]
    heads = session.headers
    heads["authorization"] = f"Bearer {mfa_token}"

    response = session.get(DEVICES, headers=heads)
    if response.status_code != 200:
        print(f"Error encountered when getting devices {response.status_code} {response.json()}")
        sys.exit()

    device = None
    for phone in response.json():
        if phone.get("isDefault", None):
            device = phone
            break

    if not device:
        print("No default device found")
        sys.exit()

    url = CHALLENGE.format(device["id"])
    response = session.post(url, headers=heads)
    if response.status_code != 200:
        print(f"Error encountered when challenging {response.status_code} {response.json()}")
        sys.exit()

    respdata = response.json()
    challenge_id = respdata["challengeId"]
    remaining = respdata["challengesRemaining"]

    print(f"Challenge id {challenge_id} sent to {device['phoneNumber']}, remaining {remaining} challenges")
    mfa_code = input("MFA code: ")

    data = {
        "bindingCode": mfa_code,
        "challengeId": challenge_id,
        "mfaToken": mfa_token
    }
    resp = session.post(LOGIN, data=data)
    if resp.status_code != 200:
        print(f"Error encountered when logging in {resp.status_code} {resp.json()}")
        sys.exit()

    token = resp.json()["token"]
    print(f"Fetched token '{token}'. Please enter into config.py")


def continuousfollow(session):
    try:
        while True:
            for category in range(1, 10):
                newfollowbatch(session, category=category)
                time.sleep(120)
    except KeyboardInterrupt:
        print("Interrupted")


def getlikes(session):
    heads = session.headers
    heads["authorization"] = f"Bearer {TOKEN}"
    likes = session.get(LIKES, headers=heads)
    return likes.json()


def sendoffer(session, buyer_id, product_id, newprice):
    url = OFFERS.format(product_id)
    heads = session.headers
    heads["authorization"] = f"Bearer {TOKEN}"
    json_data = {
        'offer_recipient_id': int(buyer_id),
        'offer_value': str(newprice)[0:2],
        'offer_currency': 'GBP',
    }
    _ = session.options(url, headers=heads, data=json_data)
    response = session.post(url, headers=heads, data=json_data)
    return response


def offers_to_likers(session, initial=45.00, lower_by=5):
    likes = getlikes(session)
    for like in likes["actionableLikes"]:
        description = like['product']['description'].split('\n')[0]
        buyer_id = like['sender']['id']
        product_id = like['product']['id']
        product = session.get(PRODUCT_BY_ID.format(product_id)).json()

        if float(product['price']['priceAmount']) != initial:
            print(f"Price for {description} is not {initial}")
            continue
        if not like['canSendOffer']:
            print(f"Can't send offer to {like['sender']['username']} for {description}")
            continue

        print(f"Sending offer to {like['sender']['username']} for {description}")
        resp = sendoffer(session, buyer_id, product_id, initial - lower_by)
        print(f"Response was {resp.status_code} {resp.json()}")


def getproducts(session, seller_id=USER_ID):
    heads = session.headers
    heads["authorization"] = f"Bearer {TOKEN}"
    products = session.get(PRODUCTS.format(seller_id), headers=heads)
    return products.json()['products']


def transformproductdata(product):
    product.pop("id")
    product["pictureIds"] = [picture[0]["id"] for picture in product["pictures"]]
    product.pop("pictures")
    product["nationalShippingCost"] = product["price"]["nationalShippingCost"]
    product["priceAmount"] = product["price"]["priceAmount"]
    product["priceCurrency"] = product["price"]["currencyName"]
    product.pop("price")
    product.pop("slug")
    product.pop("status")
    return product


def updatelistings(session):
    heads = session.headers
    heads["authorization"] = f"Bearer {TOKEN}"
    products = [product for product in getproducts(session) if not product['sold']][::-1]
    for product in products:
        productdata = session.get(PRODUCT.format(product['slug']), headers=heads)
        productdata = transformproductdata(productdata.json())
        session.headers["content-type"] = "application/json"
        session.headers['accept'] = 'application/json, text/plain, */*'
        productdata = json.dumps(productdata)
        resp = session.put(PRODUCT.format(product['slug']), headers=heads, data=productdata)
        print(f"Updated {product['slug']} with response {resp.status_code}")


def updatelistingloop(session, wait=300):
    print(f"Starting listing update loop with wait {wait}s")
    while True:
        updatelistings(session)
        print("Updated successfully, waiting...")
        time.sleep(wait)


def main():
    session = requests.Session()
    session.headers.update(headers())

    choice = input("Follow / unfollow / shop follow / token get / continuous follow / offers to likers / listing update? (f/u/s/t/c/o/l): ")
    if choice == "f":
        newfollowbatch(session)
    elif choice == "u":
        unfollowbatch(session)
    elif choice == "s":
        shopfollowbatch(session)
    elif choice == "t":
        loginwithuserpass(session)
    elif choice == "c":
        continuousfollow(session)
    elif choice == "o":
        offers_to_likers(session)
    elif choice == "l":
        updatelistingloop(session)
    else:
        print("Invalid choice")
        sys.exit()


if __name__ == '__main__':
    main()

