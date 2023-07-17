from flask import Flask
from flask import request
from pricechecker import pricechecker
import time
import cloudscraper

# Main

app = Flask(__name__)

# Routes

@app.route("/")
def index():

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
        """<form action="" method="get">
                Search seller: <input type="text" name="seller">
                <input type="submit" value="Search"><br>
                <input type="radio" id="unsorted" name="sort" value="unsorted" checked="checked">
                <label for="unsorted">Unsorted</label><br>
                <input type="radio" id="sorted" name="sort" value="sorted">
                <label for="sorted">Sorted</label><br>
              </form>"""
        + "Seller: {0}<br><br>{1}".format(seller, output)
    )

# testing
@app.route("/test")
def test():
    return (
        "testing"
    )

# Helper Functions


# Local Testing

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8080, debug=True)
