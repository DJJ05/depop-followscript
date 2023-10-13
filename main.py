# coding=utf-8
import json
import sys

import requests

PRODUCTS = "https://webapi.depop.com/api/v2/search/products/?categories=1&itemsPerPage=200&country=gb&currency=GBP&userId=USERID&sort=relevance"
MEDIA_PRE = "https://media-photos.depop.com/b1/"
RELATIONSHIP_PRE = "https://webapi.depop.com/api/v1/follows/relationship/"
FOLLOW_PRE = "https://webapi.depop.com/api/v1/follows/"
TOKEN = "TOKEN HERE"


def headers():
    return {
        "authority": "webapi.depop.com",
        "accept": "application/json",
        "accept-language": "en-GB,en-US;q=0.9,en;q=0.8",
        "depop-user-id": "USER ID",
        "origin": "https://www.depop.com",
        "referer": "https://www.depop.com/",
        "sec-ch-ua": "\"Chromium\";v=\"118\", \"Brave\";v=\"118\", \"Not=A?Brand\";v=\"99\"",
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": "\"Windows\"",
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-site",
        "user-agent": "USER AGENT HERE"
    }


def getsellerids(session, remove_following=True):
    response = session.get(PRODUCTS)
    sellerids = []

    if response.status_code != 200:
        raise Exception("Bad response from server")

    data = response.json()
    if data["meta"]["resultCount"] == 0:
        raise Exception("No products found")

    for product in data["products"]:
        photo_url = list(product["preview"].values())[0]
        seller_id = photo_url.lstrip(MEDIA_PRE).split("/")[0]
        sellerids.append(seller_id)

    sellerids = list(set(sellerids))
    if remove_following:
        print("Removing following")
        new_sellerids = []
        for sellerid in sellerids:
            try:
                following = isfollowing(session, sellerid)
                if not following:
                    new_sellerids.append(sellerid)
            except Exception as e:
                print(f"Ignored seller {sellerids.index(sellerid)} {e}")
                continue
        return new_sellerids

    return sellerids


def isfollowing(session, sellerid):
    heads = session.headers
    heads["authorization"] = f"Bearer {TOKEN}"
    url = f"{RELATIONSHIP_PRE}{sellerid}"

    response = session.get(url, headers=heads)
    if response.status_code != 200:
        raise Exception(f"{response.status_code}")

    return response.json()["isFollowing"]


def changerelationship(session, sellerids, follow=True):
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
            print(f"Ignored {'following' if follow else 'unfollowing'} seller {sellerids.index(sellerid)} {response.status_code}")
        else:
            worked.append(sellerid)

    return worked


def newfollowbatch(session):
    sellerids = getsellerids(session)

    if len(sellerids) == 0:
        print("No new sellers found")
        sys.exit()

    input(f"Found {len(sellerids)} new sellers, continue to follow and dump ids?")
    followed = changerelationship(session, sellerids)
    print(f"Followed {len(followed)} new sellers")

    with open("followed.json") as f:
        data = json.load(f)
    data["ids"].extend(followed)
    with open("followed.json", "w") as f:
        json.dump(data, f, indent=4)

    print("Complete dump")


def unfollowbatch(session):
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
