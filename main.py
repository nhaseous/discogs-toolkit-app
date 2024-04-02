from flask import Flask, request
from helper import pricechecker, matcher
import cloudscraper
import time, pprint

# Main

app = Flask(__name__)

# Routes

## Landing Page ##

@app.route("/")
def landingpage():
    return(
        """
        <div style="border-style:ridge; width:25%;padding-left:10px;">
        <h2>Discogs Toolkit</h2>
        </div><br>
        
        <hr width="25%" align="left">
        >  <a href="/pricechecker">Price Checker</a><br>
        >  <a href="/matcher">Matcher</a>
        """
    )

## Price Checker Module ##

@app.route("/pricechecker")
def pricecheckerpage():

    seller = request.args.get("seller", "")
    output = ""
    loadtime = ""

    if seller != "":
        start_time = time.time()
        try:
            inventory_list = []
            sorted_inventory_list = [[],[],[],[],[],[],[],[],[],[]]

            print("Loading inventory...")

            # initializes cloudscraper and gets a list of a store's releases & ids
            scraper = cloudscraper.create_scraper(browser={'browser': 'chrome','platform': 'android','desktop': False})
            inventory = pricechecker.get_inventory(seller, scraper)

            # populates sorted & unsorted inventory lists
            for release in inventory:
                pricechecker.get_listings(scraper, sorted_inventory_list, inventory_list, seller, release[0], release[1])

            # writes to output
            if request.args.get("sort","") == "yes":
                output = pricechecker.print_sorted_list(sorted_inventory_list) # Print sorted
            else:
                output = pricechecker.print_list(inventory_list) # Print unsorted

        except AttributeError: # returns if given username does not match a Discogs seller
            output = "No user found."

        end_time = time.time()
        seller = "Seller: " + seller
        loadtime = "Search time: {0} seconds".format(round(end_time-start_time,2))

    return (
        # browser output #
        """
        <div style="border-style:ridge; width:25%;padding-left:10px;">
        <h2>Price Checker</h2>
        </div><br>

        <hr width="25%" align="left"><br>
        <form action="" method="get">   
            Search seller: <input type="text" name="seller">
            <input type="submit" value="Search"><br>

            <input type="checkbox" id="sort" name="sort" value="yes">
            <label for="sort">Sort</label><br>
        </form>
        -
        <br><br>
        """
        + "{0}<br><br><b>{1}</b><br><br>{2}<br>".format(loadtime, seller, output)
        + """
        <hr width="25%" align="left">
        <a href="/">> Home</a><br>
        <a href="/pricechecker">> Reset</a> 
        """
    )

## Matcher Module ##

@app.route("/matcher")
def matcherpage():

    collection_user = request.args.get("collection", "")
    wantlist_user = request.args.get("wantlist", "")
    output = ""
    loadtime = ""

    start_time = time.time()
    if collection_user != "" and wantlist_user != "" :
        try:
            scraper = cloudscraper.create_scraper(browser={'browser': 'chrome','platform': 'android','desktop': False})

            # scrapes for the collections and wantlists
            collection = matcher.get_collection(collection_user, scraper)
            wantlist = matcher.get_wantlist(wantlist_user, scraper)

            # compare the sets to find matches between collection and wantlist
            matches = set(collection) & set(wantlist)
            for match in matches:
                output += "{0}<br>".format(match)

            output = """
            <b>Collection: {0} - {1}<br>
            Wantlist: {2} - {3}<br><br>
            Matches: {4}<br><br></b>
            &#123<br>{5}&#125
            """.format(len(collection), collection_user,len(wantlist), wantlist_user,len(matches),output)

        except AttributeError:
            output = "Unable to find a match." # returns if given username does not match a Discogs store user

        end_time = time.time()
        loadtime = "Load time: {0} seconds".format(round(end_time-start_time,2))

    return (
        # browser output #
        """
        <div style="border-style:ridge; width:25%;padding-left:10px;">
        <h2>Collection Matcher</h2></div>
        <br>

        <hr width="25%" align="left"><br>
        <form action="" method="get">
            Search collection: <input type="text" name="collection"><br>
            Search wantlist: <input type="text" name="wantlist">
            <input type="submit" value="Search"><br>
        </form>
        -
        <br><br>
        """
        + "{0}<br><br><br>{1}<br>".format(loadtime, output)
        + """
        <br><br>
        <hr width="25%" align="left">
        <a href="/">> Home</a><br>
        <a href="/matcher">> Reset</a> 
        """
    )

## Testing Page ##

@app.route("/test")
def testingpage():
    return (
        """
        <input type="text" name="wantlist">
        testing
        """
    )

# Helper Functions


# Local Testing

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8080, debug=True)
