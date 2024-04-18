from discord_webhook import DiscordWebhook
import cloudscraper, time, random, sys

sys.path.insert(1, 'helper')
import pricechecker

# Worker node that loops its task (of scraping a seller's Discogs inventory)
# Has properties: url, status, and savedlist

## Classes ##

class Worker:

    def __init__(self,seller,rate,webhook):
        self.seller = seller
        self.rate = rate
        self.webhook = webhook # Discord webhook url to send notifications of changes to
        self.savedinventorylist = [] # local save of the inventory list
        self.active = True

    # starts the Worker to loop these actions: scrape, compare, notify, and save
    def run(self):
        try:
            # TBD: add lock/condition to shut off worker from main server
            # loops worker tasks delayed with the worker's rate
            while True:
                inventory_list, sorted_inventory_list = [], [ [] for _ in range(10) ]
                print("Scraping: {0}".format(self.seller))

                # scrapes and populates sorted & unsorted inventory lists
                scraper = cloudscraper.create_scraper(browser={'browser':'chrome','platform':'android','desktop':False})
                release_titles_ids = pricechecker.get_inventory(self.seller, scraper)
                for release in release_titles_ids:
                    pricechecker.get_listings(scraper, inventory_list, sorted_inventory_list,
                                                self.seller, release[0], release[1]) # (title, id)

                # compares inventory list with saved list to check for 
                changes = ""
                if self.savedinventorylist != []:
                    # if there is a saved list, do comparison and return changes
                    changes = compare_inventory_list(inventory_list, self.savedinventorylist)
                else:
                    changes = pricechecker.print_list(inventory_list) # if there's no saved inventory list, return the scraped list

                # notifies Discord webhook if changes are found (non-empty string)
                if changes != "":
                    webhook = DiscordWebhook(url=self.webhook, content=changes)
                    response = webhook.execute()
                    print("Changes detected, webhook alerted.".format)
                    
                # makes a local save to compare later
                # save_state(inventory_list)
                self.savedinventorylist = inventory_list
            
                # randomizes rate of looping (from 5 minutes to 10 minutes)
                time.sleep(self.rate + random.randint(0,5))

        except Exception as e:
            print(e)


## Compare ##

# Compares inventory list with provided list for changes
def compare_inventory_list(inventory_list, saved_inventory_list): 

    if saved_inventory_list:
        print("Loaded saved inventory state.\n")

        # checks if inventory size has changed
        if len(saved_inventory_list) == len(inventory_list):
            # compares 
            for count in range(len(saved_inventory_list)):
                compare_entries(inventory_list[count], saved_inventory_list[count], count)
        else:
            print("Inventory size changed.")
        print("Finished comparison.")
    else:
        print("Nothing to load.\n")
        
# Given an entry number and a saved entry, compares it to the corresponding entry in the provided inventory list
def compare_entries(current, saved_entry, count): 

    output = ""
    current_listings, saved_listings = current.listings, saved_entry.listings

    if current_listings != saved_listings:
        # writes to output to return after comparison if changes are found
        output = "({0}){1}\n{2}\n".format(count, saved_entry.title, saved_entry.url)

        # compares the current and saved versions of an entry's listings
        current_list, saved_list = current_listings.split("\n"), saved_listings.split("\n")
        for index in range(len(current_list)):
            try:
                current_listing, saved_listing = current_list[index], saved_list[index]

                # checks if there are changes to the current listing compared to the saved list
                if current_listing != saved_listing:
                    # checks if a listing has been inserted or removed (sequentially checks)
                    if saved_list[index+1] == current_list[index] or saved_list[index+1].split("(You)")[0] == current_list[index].split("(You)")[0]:
                        output += "{0} --> {1}\n".format(saved_listing, "Removed")
                        current_list.insert(index,saved_listing)
                    elif current_list[index+1] == saved_list[index] or current_list[index+1].split("(You)")[0] == saved_list[index].split("(You)")[0]:
                        output += "{0} --> {1}\n".format("Inserted", current_listing)
                        saved_list.insert(index,current_listing)

                    # checks if your listing has changed but no other changes on the market for your release
                    elif ("You" in saved_listing) and ("You" in current_listing):
                        if (saved_listing.split("You")[0] == current_listing.split("You")[0]):
                            output += "{0} --> {1}\n".format(saved_listing, current_listing.split("(You) ")[-1])
                        else:
                            output += "{0} --> {1}\n".format(saved_listing.split(" (You)")[0], current_listing)
                    else:
                        output += "{0} --> {1}\n".format(saved_listing, current_listing)
            except IndexError:
                # output += "Length of listings does not matched to saved listings."
                output += "{0} --> {1}\n".format("Inserted", current_list[index])

        if current.place != saved_entry.place:
            output += "Place: {0} --> {1}\n".format(saved_entry.place, current.place)

    return output # returns any changes as a string output; returns an empty string if there are no changes


# Compares inventory list with saved state/list for changes (this one uses Pickle to save state)
# def compare_inventory_list(inventory_list): 

#     saved_state = load_state()
    
#     if saved_state:
#         print("Loaded saved inventory state.\n")

#         if len(saved_state) == len(inventory_list):
#             for count in range(len(saved_state)):
#                 saved_entry = saved_state[count]
#                 compare_entries(inventory_list, saved_entry, count)
#         else:
#             print("Inventory size changed.")
#         print("Finished comparison.")
#     else:
#         print("Nothing to load.\n")
#         print_list(inventory_list)
