from bs4 import BeautifulSoup
import math, pickle
import collections
collections.Callable = collections.abc.Callable

# Discogs Price Checker Module
# Takes a public Discogs store inventory and returns pricing information on other listings on the market.

## Classes ##

class FormattedEntry: # Formatted marketplace entry for a single release and its listings

    def __init__(self,username,title,url,imgUrl,listings,place,total):
        self.self = username
        self.title = title
        self.url = url
        self.imgUrl = imgUrl
        self.listings = listings
        self.place = place
        self.total = total
        # self.total = "> Total: {0}".format(total)

    def __str__(self):
        return "{0}<br><a href=\"{1}\">Link</a><br>{2}<br>> Total: {3}<br>".format(self.title,self.url,self.listings,self.total)

## Get ##

# get_inventory_ids: main
# get_listings: get listings for a release id
# get_price: get price of a listing

# Given a seller username, returns a list of the releases in their inventory and their item ids.
def get_inventory_ids(username, scraper):

    URL = "https://www.discogs.com/seller/{0}/profile".format(username)
    pages = count_pages(URL, scraper) # gets the number of pages in a store

    new_list = []

    for page in range(1, pages + 1):
        html = scraper.get(URL + "?&sort=price&sort_order=asc&page={0}".format(page)).content
        soup = BeautifulSoup(html, 'html.parser')

        # scrapes for all the releases on a store page
        list_items = soup.find(id="pjax_container").find("tbody").find_all("tr")
        for item in list_items: # scrapes for the release title and item id of each release
            release = item.find("td", class_="item_description")

            title = release.find("strong").text.strip()
            item_id = release.find("a", class_="item_release_link")["href"].split("-")[0].strip("/release/")

            # checks if item id has been added to the list already
            found = False
            for (name,id) in new_list:
                if id == item_id:
                    found = True
            # if seller has multiple copies of the same release listed, only add it to the list once for scraping
            if not found:
                new_list_item = (title, item_id)
                new_list.append(new_list_item)

    return new_list

# Given username and item_id, scrapes marketplace for listings and stores them in provided list.
def get_listings(scraper, inventory_list, sorted_inventory_list, username, release_title, item_id):

    URL, imgURL = "https://www.discogs.com/sell/release/{0}?ships_from=United+States&sort=price%2Casc".format(item_id), ""
    html = scraper.get(URL).content

    soup = BeautifulSoup(html, 'html.parser')

    count, your_place, total = 0, 0, 0
    formatted_listings, listings = "", []

    # scrapes for all the listings for a given release
    if soup.find("table", class_="mpitems"):
        listings = soup.find("table", class_="mpitems").find_all("tr", class_="shortcut_navigable")
        total = (soup.find("strong", class_="pagination_total").text.split(" of "))[-1] # total number of listings for a release
        # imgURL = soup.find("a", class_="thumbnail_link").find("img")["src"]
    elif soup.find("title").text.find("Page is Unavailable"):
        print("get_listings_error: page_unavailable: {0}".format(release_title))
    else:
        print("get_listings_error: {0}: {1}".format(release_title,html))

    user_found = False
    # TBD: account for when user has multiple listings
    # compiles the prices of all the listings for a release
    for listing in listings:
        count += 1
        # checks if a listing belongs to the user provided
        if is_user(username, listing) and not user_found:
            formatted_listings += "<mark>{0} (You) ({1})</mark><br>".format(get_price(listing), count)
            your_place = count
            user_found = True
        elif is_user(username, listing):
            formatted_listings += "{0} (You)<br>".format(get_price(listing))
        # checks if a seller has 0% feedback rating
        elif check_scam(listing):
            formatted_listings += "{0} (SCAM)<br>".format(get_price(listing))
        else:
            formatted_listings += "{0}<br>".format(get_price(listing))

    # compiles info and listing prices for a release, then adds it to the inventory lists
    entry = FormattedEntry(username,release_title,URL,imgURL,formatted_listings,your_place,total)
    if your_place < 10:
        (sorted_inventory_list[your_place - 1]).append(entry)
    else:
        sorted_inventory_list[9].append(entry)
    inventory_list.append(entry)

    return

# Gets the price of a provided listing.
def get_price(listing): 

    try:
        item_condition = listing.find("p", class_="item_condition").text
        formatted_condition = format_condition(item_condition)

        if listing.find(string="New seller"):
            return "{0} {1} (New)".format(listing.find("span", class_="converted_price").text.strip(), formatted_condition)
        else:
            return "{0} {1}".format(listing.find("span", class_="converted_price").text.strip(), formatted_condition)

    except AttributeError:
        return "n/a"


## Print ##

# print_list
# print_sorted_list

# Prints unsorted inventory list.
def print_list(unsorted_inventory_list): 

    count = 0
    output = ""

    # an entry is a release to print out
    for entry in unsorted_inventory_list:
        count += 1
        output += "<b>({0})</b><br>".format(count)
        output += "{0}<br>".format(entry)

    return output

# Prints a sorted inventory list.
def print_sorted_list(sorted_inventory_list): 

    output = ""
    count = 0 # count is the current number item being printed

    for index in range(len(sorted_inventory_list)):
        
        if sorted_inventory_list[index]:
            output += "({0}) Place: {1}<br><br>".format(index+1, len(sorted_inventory_list[index]))

        # an entry is a release to print out    
        for entry in sorted_inventory_list[index]:
            count += 1
            output += "({0})<br>{1}<br>".format(count, entry)

        # prints if current place has an entry
        if len(sorted_inventory_list[index]) > 0:
            output += "({0}) Place: {1}".format(index+1, len(sorted_inventory_list[index]))
            output += "<hr width=\"25%\" align=\"left\">"

    # prints out a list of places and the number of listings a seller has belonging to each place
    places = "Place<br>"
    for index in range(len(sorted_inventory_list)):
        places += "{0}: {1}<br>".format(index+1, len(sorted_inventory_list[index]))

    return places + "<br><hr width=\"25%\" align=\"left\">" + output


## Helper Functions ##

# count_pages
# format_condition
# is_user
# check_scam

# Takes URL for a Discogs store, returns the number of pages.
def count_pages(URL, scraper):

    html = scraper.get(URL).content
    soup = BeautifulSoup(html, 'html.parser')

    # scrapes for the total inventory size
    inventory_size = int(soup.find(id="pjax_container").find("strong", class_="pagination_total").text.strip().split("of ")[1])
    pages = math.ceil(inventory_size/25)

    return pages

# Formats the item condition to (Media/Sleeve).
def format_condition(item_condition):

    media = (item_condition.split("("))[1].split(")")[0]
    try:
        sleeve = (item_condition.split("("))[2].split(")")[0]

    except IndexError:
        return "({0})".format(media.split(" or")[0])

    media = media.split(" or")[0]
    sleeve = sleeve.split(" or")[0]

    return "({0}/{1})".format(media, sleeve)

# Checks if a marketplace listing matches the provided username.
def is_user(username, listing):

    return listing.find(string=username)

# Checks if a listing is a scam (has 0.0% seller rating).
def check_scam(listing):

    return listing.find(string="0.0%")


## State ##

# # Pickles an inventory list as a save state in a bin file.
# def save_state(inventory_list): 

#     with open("state.bin", "wb") as f:
#         pickle.dump(inventory_list, f)

# # Loads a pickled inventory list from a bin file.
# def load_state(): 

#     with open("state.bin", "rb") as f:
#         try:
#             pickled_list = pickle.load(f)
#             return pickled_list
#         except pickle.UnpicklingError:
#             return []
