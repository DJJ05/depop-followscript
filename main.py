# coding=utf-8
import json
import sys

import requests
from config import *

PRODUCTS = f"https://webapi.depop.com/api/v2/search/products/?categories={CATEGORY}&itemsPerPage={MAX_SELLERS}\
            &country=gb&currency=GBP&userId={USER_ID}&sort=relevance "
MEDIA_PRE = "https://media-photos.depop.com/b1/"
RELATIONSHIP_PRE = "https://webapi.depop.com/api/v1/follows/relationship/"
FOLLOW_PRE = "https://webapi.depop.com/api/v1/follows/"


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


def getsellerids(session, remove_following=True):
    response = session.get(PRODUCTS)
    sellerids = []

    if response.status_code != 200:
        raise Exception(f"Bad response from server when getting products: {response.status_code}")

    data = response.json()
    if data["meta"]["resultCount"] == 0:
        raise Exception("No products found")

    for product in data["products"]:
        photo_url = list(product["preview"].values())[0]
        seller_id = photo_url.lstrip(MEDIA_PRE).split("/")[0]
        sellerids.append(seller_id)

    sellerids = list(set(sellerids))
    if remove_following:
        print("Removing sellers already followed")
        new_sellerids = []
        for sellerid in sellerids:
            try:
                following = isfollowing(session, sellerid)
                if not following:
                    new_sellerids.append(sellerid)
            except Exception as e:
                print(f"Ignored adding seller {sellerids.index(sellerid)}-{sellerid} {e}")
                continue
        return new_sellerids

    return sellerids


def isfollowing(session, sellerid):
    heads = session.headers
    heads["authorization"] = f"Bearer {TOKEN}"
    url = f"{RELATIONSHIP_PRE}{sellerid}"

    response = session.get(url, headers=heads)
    if response.status_code != 200:
        if response.status_code == 429:
            print("Rate limited so exiting")
            sys.exit()
        raise Exception(f"Couldn't check if following seller {response.status_code}")

    return response.json()["isFollowing"]


def changerelationship(session, sellerids, follow=True):
    print(f"Starting {'follow' if follow else 'unfollow'}ing sellers")
    worked = []
    heads = session.headers
    heads["authorization"] = f"Bearer {TOKEN}"

    for sellerid in sellerids:
        url = f"{FOLLOW_PRE}{sellerid}"

        if follow:
            response = session.put(url, headers=heads)
        else:
            response = session.delete(url, headers=heads)

        if response.status_code not in (202, 204):
            if response.status_code == 429:
                print("Rate limited so ending now")
                break
            print(f"Ignored {'following' if follow else 'unfollowing'} seller {sellerids.index(sellerid)} {response.status_code}")
        else:
            worked.append(sellerid)

    print(f"{len(worked)} out of {len(sellerids)} {'followed' if follow else 'unfollowed'}")
    return worked


def newfollowbatch(session):
    print(f"Starting new follow batch with max {MAX_SELLERS} sellers and category {CATEGORY}")
    sellerids = getsellerids(session)

    if len(sellerids) == 0:
        print("No new sellers found")
        sys.exit()

    print(f"Found {len(sellerids)} new sellers")
    followed = changerelationship(session, sellerids)
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
    sellerids = data["ids"]
    failed = []

    worked = changerelationship(session, sellerids, follow=False)
    print(f"Unfollowed {len(worked)} sellers")
    for sellerid in sellerids:
        if sellerid not in worked:
            failed.append(sellerid)

    print(f"Failed to unfollow {len(failed)} sellers")
    data["ids"] = failed
    with open("followed.json", "w") as f:
        json.dump(data, f, indent=4)
    print("Redumped")


def main():
    session = requests.Session()
    session.headers.update(headers())

    choice = input("Follow or unfollow? (f/u): ")
    if choice == "f":
        newfollowbatch(session)
    elif choice == "u":
        unfollowbatch(session)
    else:
        print("Invalid choice")
        sys.exit()


if __name__ == '__main__':
    main()
