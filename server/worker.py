from helper import pricechecker
import cloudscraper

# Worker node that loops its task (of scraping a seller's Discogs inventory)
# Has properties: url, status, and savedlist

class Worker:

    def __init__(self,seller):
        self.seller = seller
        self.active = True
        self.savedinventorylist = []

    # starts the Worker to loop these actions: scrape, compare, notify, and save
    def run(self):
        scraper = cloudscraper.create_scraper(browser={'browser': 'chrome','platform': 'android','desktop': False})
        inventory_list = []
        sorted_inventory_list = [[],[],[],[],[],[],[],[],[],[]]

        # scrapes and populates sorted & unsorted inventory lists
        inventory = pricechecker.get_inventory(self.seller, scraper)
        for release in inventory:
            pricechecker.get_listings(scraper, sorted_inventory_list, inventory_list, self.seller, release[0], release[1])

        # compare
        # pricechecker.compare_inventory_list(inventory_list)
        pricechecker.compare_inventory_list(inventory_list,self.savedinventorylist)

        # notify

        # makes a local save of the inventory list for the worker to compare later
        # pricechecker.save_state(inventory_list)
        self.savedinventorylist = inventory_list
