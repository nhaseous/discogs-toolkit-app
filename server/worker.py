from discord_webhook import DiscordWebhook, DiscordEmbed
import cloudscraper, time, random, sys, itertools

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

            scraper = cloudscraper.create_scraper(browser={'browser':'chrome','platform':'android','desktop':False})

            webhook = DiscordWebhook(url=self.webhook, content="Server restarted. Watching: {0}".format(self.seller))
            response = webhook.execute()
            webhook = DiscordWebhook(url=self.webhook,rate_limit_retry=True)

            # loops worker tasks delayed with the worker's rate
            iteration = 0
            while True:
                start_time = time.time()
                iteration += 1

                inventory_list, sorted_inventory_list = [], [ [] for _ in range(10) ]
                print("({0}) Scraping... ({1})".format(self.seller,iteration))

                # scrapes and populates sorted & unsorted inventory lists
                release_titles_ids = pricechecker.get_inventory(self.seller, scraper)
                print("({0}) Fetched inventory. Parsing..".format(self.seller))

                for (title,id) in release_titles_ids:
                    pricechecker.get_listings(scraper, inventory_list, sorted_inventory_list,
                                                self.seller, title, id)
                print("({0}) Finished scraping.".format(self.seller))
                    
                embeded_changes = []
                # if saved list exists, compares it to current inventory list
                if self.savedinventorylist != []:
                    compare_inventory_list(inventory_list, self.savedinventorylist,embeded_changes)

                # notifies Discord webhook if changes are found (non-empty string)
                if embeded_changes != []:
                    print("({0}) Changes detected, notifying Discord.".format(self.seller))
                    count = 0
                    # converts the entries in the inventory list to be able to output to DiscordWebhooks as embded content
                    for embeded in embeded_changes:
                        webhook.add_embed(embeded)
                        count += 1

                        if count > 4:
                            response = webhook.execute(remove_embeds=True)
                            count = 0

                    response = webhook.execute(remove_embeds=True)

                # if no changes, just output the original inventory list
                # elif self.savedinventorylist == []:
                #     print("No changes found, returning the original list.")
                #     count = 0
                #     for entry in inventory_list:
                #         embeded = embed(entry)
                #         webhook.add_embed(embeded)
                #         count += 1

                #         if count > 9:
                #             response = webhook.execute(remove_embeds=True)
                #             count = 0

                #     response = webhook.execute(remove_embeds=True)

                else:
                    print("({0}) No changes found.".format(self.seller))

                end_time = time.time()
                print("({0}) Search time: {1}s".format(self.seller,round(end_time-start_time)))

                # makes a local save to compare later
                # save_state(inventory_list)
                self.savedinventorylist = inventory_list

                # randomizes rate of looping (in seconds)
                sleeptime = self.rate + random.randint(0,100)
                print("({0}) Sleeping... ({1}s)\n".format(self.seller,sleeptime))
                time.sleep(sleeptime)

        except Exception as e:
            print("{0}: {1}: {2}".format("run",self.seller,e))


## Compare ##

# Compares inventory list with provided list for changes
def compare_inventory_list(inventory_list, saved_inventory_list, embeded_changes): 

    if saved_inventory_list:
        # print("({0}) Loaded save. Comparing...".format(inventory_list[0].self))
        # print("Inventory list: {0} / Saved list: {1}".format(len(inventory_list),len(saved_inventory_list)))

        try:
            # iterate over the indices of both lists to look for changes
            for (i,j) in itertools.zip_longest(range(len(inventory_list)),range(len(saved_inventory_list))):

                changes = ""
                match_found = False

                # checks if an entry exists at that index for both the current and saved lists
                if i == j:

                    # print("i: {0} / j: {1}".format(i,j))
                    # print("inventory-list: {0} / saved-list: {1}".format(inventory_list[i].title,saved_inventory_list[i].title))

                    # checks if the entries being compared are the same release (using url as an id)
                    if inventory_list[i].url == saved_inventory_list[i].url:
                        changes += compare_entries(inventory_list[i], saved_inventory_list[i])

                    # if the entries don't match up,
                    else:
                        if i+1 < len(saved_inventory_list):
                            # find matching entry for current entry by traversing the saved list
                            for k in range(i+1,len(saved_inventory_list)):
                                # if the matching entry is found, do a comparison
                                if inventory_list[i].url == saved_inventory_list[k].url:
                                    changes += compare_entries(inventory_list[i], saved_inventory_list[k])
                                    # swap to reorganize list for future compares
                                    saved_inventory_list[i], saved_inventory_list[k] = saved_inventory_list[k], saved_inventory_list[i]
                                    match_found = True

                        # find matching entry for saved entry by traversing the current list if not found yet
                        if not match_found:
                            for k in range(i,len(inventory_list)):
                                # print("k: {0}".format(k))
                                if saved_inventory_list[i].url == inventory_list[k].url:
                                    changes += compare_entries(inventory_list[k], saved_inventory_list[i])
                                    inventory_list[i], inventory_list[k] = inventory_list[k], inventory_list[i]
                                    match_found = True

                        # if a matching entry isn't found in either list, return both entries at that index in the change log
                        if not match_found: 
                            print("({0}) Changes detected.".format(inventory_list[i].self))
                            embeded_changes.append(embed(inventory_list[i],"New listing found."))
                            embeded_changes.append(embed(saved_inventory_list[i],"New listing found."))

                    # if the current release entry has changed, log the changes in an Emded object
                    if changes != "":
                        print("({0}) Changes detected. Sending to webhook.".format(inventory_list[i].self))
                        embeded_changes.append(embed(inventory_list[i],changes))

                # if current entry exists at that index but not a saved entry, return the current entry
                elif i:
                    # print("i: {0}".format(i))
                    embeded_changes.append(embed(inventory_list[i],"New listing added."))

                elif j:
                    changes = "Listing removed."
                    changes += "(Place) {0} --> {1}".format(saved_inventory_list[j].place, 0)
                    embeded_changes.append(embed(saved_inventory_list[j],changes))

        except Exception as e:
            print("{0}: {1}: {2}".format("compare_inventory_list",inventory_list[0].self,e))

        print("({0}) Finished comparison.".format(inventory_list[0].self))
                
    else:
        print("({0}) Nothing to load.\n".format(inventory_list[0].self))
            
# Given an entry number and a saved entry, compares it to the corresponding entry in the provided inventory list
# returns any changes as a string output; returns an empty string if there are no changes
def compare_entries(current, saved_entry): 

    current_listings = current.listings.replace("<mark>"," ").replace("</mark>"," ")
    saved_listings = saved_entry.listings.replace("<mark>"," ").replace("</mark>"," ")
    change_log = ""

    if current_listings != saved_listings:
        # compares the current and saved versions of an entry's listings
        # writes any changes to change log to return
        current_list, saved_list = current_listings.split("<br>"), saved_listings.split("<br>")
        for index in range(len(current_list)):
            try:
                current_listing, saved_listing = current_list[index], saved_list[index]
                # checks if there are changes to the current listing
                if current_listing != saved_listing:

                    # checks if a listing has been inserted or removed (sequential check)
                    if saved_list[index+1] == current_list[index] or saved_list[index+1].split("(You)")[0] == current_list[index].split("(You)")[0]:
                        change_log += "{0} --> {1}\n".format(saved_listing, "Removed")
                        current_list.insert(index,saved_listing)
                    elif current_list[index+1] == saved_list[index] or current_list[index+1].split("(You)")[0] == saved_list[index].split("(You)")[0]:
                        change_log += "{0} --> {1}\n".format("Inserted", current_listing)
                        saved_list.insert(index,current_listing)

                    # checks if the current listing is yours, and if it has changed
                    elif ("You" in saved_listing) and ("You" in current_listing):
                        if (saved_listing.split("You")[0] == current_listing.split("You")[0]):
                            change_log += "{0} --> {1}\n".format(saved_listing, current_listing.split("(You) ")[-1])
                        else:
                            change_log += "{0} --> {1}\n".format(saved_listing.split(" (You)")[0], current_listing)

                    # if listing has changed but unable to detect change, outputs the before and after for manual comparison
                    else:
                        change_log += "{0} --> {1}\n".format(saved_listing, current_listing)

            except IndexError:
                change_log += "{0} --> {1}\n".format("Inserted", current_list[index])

        # checks if your place has changed on the list
        if current.place != saved_entry.place:
            change_log += "(Place) {0} --> {1}".format(saved_entry.place, current.place)
        else:
            # if your place has not changed, do not report changes to the listings even if there are any
            change_log = ""
        
    return change_log


## Helper Functions ##

# Converts a FormattedEntry object to a DiscordEmbed and returns it
def embed(entry,changes=""):

    try:
        # trim HTML from the entry listings
        # if entry.listings.count("<br>") > 20:
        formatted_listings = entry.listings.replace("<br>","\n").replace("<mark>", "\> ").replace("(You)","").replace("</mark>","")
        place = entry.place
        if "(Place)" in changes:
            place = changes.split("(Place) ")[1]
            changes = changes.split("(Place) ")[0]

        # embed = DiscordEmbed(title=entry.title, description=entry.url.split("?")[0], color="03b2f8")
        embed = DiscordEmbed(title=entry.title, description=entry.url, color="03b2f8")
        embed.set_thumbnail(url=entry.imgUrl)
        embed.add_embed_field(name="Listings", value=formatted_listings, inline=False)
        embed.add_embed_field(name="Place", value=place)
        embed.add_embed_field(name="Total", value=entry.total)

        # if changes detected, add a Changes field to webhook embed
        if changes != "":
            embed.add_embed_field(name="Changes", value =changes, inline=False)


        embed.set_footer(text=entry.self)
        embed.set_timestamp()

        return embed
    
    except Exception as e:
        print("{0}: {1}: {2}".format("embded",entry.self,e))
