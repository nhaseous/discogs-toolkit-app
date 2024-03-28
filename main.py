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

            # compares
            if request.args.get("compare","") == "yes":
                pricechecker.compare_inventory_list(inventory_list)
            
            # saves
            if request.args.get("save","") == "yes":
                pricechecker.save_state(inventory_list)
                print("Saved inventory list locally.\n")

        except AttributeError: # returns if given username does not match a Discogs store user
            output = "No user found."

        end_time = time.time()
        seller = "Seller: " + seller
        loadtime = "Search time: {0} seconds".format(round(end_time-start_time,2))

    return (
        
        # browser output
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
            <input type="checkbox" id="compare" name="compare" value="yes">
            <label for="compare">Compare</label><br>
            <input type="checkbox" id="save" name="save" value="yes">
            <label for="save">Save</label><br>        
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
        <div style="border-style:ridge; width:25%;padding-left:10px;">
        <h2>Matcher</h2></div>
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
        + output
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
