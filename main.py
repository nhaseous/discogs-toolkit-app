from flask import Flask, request
from helper import pricechecker, matcher
import cloudscraper
import time, pprint

# Main

app = Flask(__name__)

# Routes

## Landing Page

@app.route("/")
def landingpage():
    return(
        """
        <hr width="25%" align="left"><h2>| Discogs Toolkit </h2><hr width="25%" align="left">
        > <a href="/pricechecker">Price Checker</a><br>
        > <a href="/matcher">Matcher</a>
        """
    )

## Price Checker Module

@app.route("/pricechecker")
def pricecheckerpage():

    seller = request.args.get("seller", "")
    sort = request.args.get("sort", "")
    output = ""

    if seller != "":
        start_time = time.time()
        try:
            inventory_list = []
            sorted_inventory_list = [[],[],[],[],[],[],[],[],[],[]]

            print("Loading inventory...")
            # initializes cloudscraper and gets a list of a store's releases and their item ids
            scraper = cloudscraper.create_scraper(browser={'browser': 'chrome','platform': 'android','desktop': False})
            inventory = pricechecker.get_inventory(seller, scraper)

            # populates inventory lists of each release's listings in sorted order
            for release in inventory:
                pricechecker.get_listings(scraper, sorted_inventory_list, inventory_list, seller, release[0], release[1])

            # writes to output either the sorted or the unsorted inventory list
            if sort == "sorted":
                output = pricechecker.print_sorted_list(sorted_inventory_list) # Print sorted
            elif sort == "unsorted":
                output = pricechecker.print_list(inventory_list) # Print unsorted

        except AttributeError:
            output = "No user found." # returns if given username does not match a Discogs store user

        end_time = time.time()
        print("Time to load: {0} seconds".format(end_time-start_time))

    return (
        """
        <hr width="25%" align="left"><h2>| Price Checker </h2><hr width="25%" align="left">
        <form action="" method="get">
            Search seller: <input type="text" name="seller">
            <input type="submit" value="Search"><br>
            <input type="radio" id="unsorted" name="sort" value="unsorted" checked="checked">
            <label for="unsorted">Unsorted</label><br>
            <input type="radio" id="sorted" name="sort" value="sorted">
            <label for="sorted">Sorted</label><br>
        </form>
        """
        + "Seller: {0}<br><br>{1}".format(seller, output)
    )

## Matcher Module

@app.route("/matcher")
def matcherpage():

    collection_user = request.args.get("collection", "")
    wantlist_user = request.args.get("wantlist", "")
    output = ""

    if collection_user != "" and wantlist_user != "" :
        start_time = time.time()
        try:
            scraper = cloudscraper.create_scraper(browser={'browser': 'chrome','platform': 'android','desktop': False})

            collection = matcher.get_collection(collection_user, scraper)
            output += "Collection: {0} - {1}<br>".format(len(collection), collection_user)

            wantlist = matcher.get_wantlist(wantlist_user, scraper)
            output += "Wantlist: {0} - {1}<br>".format(len(wantlist), wantlist_user)

            matches = set(collection) & set(wantlist)
            output += "<br>Matches: {0}<br>&#123<br>".format(len(matches))
            for match in matches:
                output += "{0}<br>".format(match)
            output += "&#125"

        except AttributeError:
            output = "Could not find user(s)." # returns if given username does not match a Discogs store user

        end_time = time.time()
        print("Time to load: {0} seconds".format(end_time-start_time))

    return (
        """
        <hr width="25%" align="left"><h2>| Matcher </h2><hr width="25%" align="left">
        <form action="" method="get">
            Search collection: <input type="text" name="collection"><br>
            Search wantlist: <input type="text" name="wantlist">
            <input type="submit" value="Search"><br>
        </form>
        """
        + "<br><br>{0}".format(output)
    )

## Testing Page

@app.route("/test")
def testingpage():
    return (
        "testing"
    )

# Helper Functions


# Local Testing

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8080, debug=True)
