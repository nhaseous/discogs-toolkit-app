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
                print("Scraping: {0}... ({1})".format(self.seller,iteration))

                # scrapes and populates sorted & unsorted inventory lists
                release_titles_ids = pricechecker.get_inventory(self.seller, scraper)
                for release in release_titles_ids:
                    pricechecker.get_listings(scraper, inventory_list, sorted_inventory_list,
                                                self.seller, release[0], release[1]) # (title, id)
                    
                embeded_changes = []
                # if saved list exists, compares it to current inventory list
                if self.savedinventorylist != []:
                    compare_inventory_list(inventory_list, self.savedinventorylist,embeded_changes)

                # notifies Discord webhook if changes are found (non-empty string)
                if embeded_changes != []:
                    print("Changes detected for ({0}), alerting webhook.".format(self.seller))
                    count = 0
                    # converts the entries in the inventory list to be able to output to DiscordWebhooks as embded content
                    for embeded in embeded_changes:
                        webhook.add_embed(embeded)
                        count += 1

                        if count > 9:
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
                    print("No changes found for ({0}).".format(self.seller))

                end_time = time.time()
                print("Search time ({0}): {1}s".format(self.seller,round(end_time-start_time,2)))

                # makes a local save to compare later
                # save_state(inventory_list)
                self.savedinventorylist = inventory_list

                # randomizes rate of looping (in seconds)
                sleeptime = self.rate + random.randint(0,100)
                print("Sleeping... ({0}) ({1}s)\n".format(self.seller,sleeptime))
                time.sleep(sleeptime)

        except Exception as e:
            print("{0}: {1}".format(self.seller,e))


## Compare ##

# Compares inventory list with provided list for changes
def compare_inventory_list(inventory_list, saved_inventory_list, embeded_changes): 

    if saved_inventory_list:
        print("Loaded saved inventory state. ({0})\nComparing...".format(inventory_list[0].self))

        # iterate over the indices of both lists to look for changes
        for (i,j) in itertools.zip_longest(range(len(inventory_list)),range(len(saved_inventory_list))):

            changes = ""
            match_found = False

            # checks if an entry exists at that index for both the current and saved lists
            if i and j:

                # checks if the entries being compared are the same release (using url as an id)
                if inventory_list[i].url == saved_inventory_list[i].url:
                    changes += compare_entries(inventory_list[i], saved_inventory_list[i])

                # if the entries don't match up,
                else:
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
                            if saved_inventory_list[i].url == inventory_list[k].url:
                                changes += compare_entries(inventory_list[k], saved_inventory_list[i])
                                inventory_list[i], inventory_list[k] = inventory_list[k], inventory_list[i]
                                match_found = True

                    # if a matching entry isn't found in either list, return both entries at that index in the change log
                    if not match_found: 
                        print("Changes detected. ({0})".format(inventory_list[i].self))
                        embeded_changes.append(embed(inventory_list[i],"New entry found."))
                        embeded_changes.append(embed(saved_inventory_list[i],"New entry found."))

                # if the current release entry has changed, log the changes in an Emded object
                if changes != "":
                    print("Changes detected. Sending to webhook. ({0})".format(inventory_list[i].self))
                    embeded_changes.append(embed(inventory_list[i],changes))

            # if current entry exists at that index but not a saved entry, return the current entry
            elif i:
                embeded_changes.append(embed(inventory_list[i],"New entry added."))

        print("Finished comparison. ({0})".format(inventory_list[i].self))
                
    else:
        print("Nothing to load. ({0})\n".format(inventory_list[i].self))


# TBD: remove
# def compare_inventory_list_old(inventory_list, saved_inventory_list, embeded_changes): 

#     if saved_inventory_list:
#         print("Loaded saved inventory state.\n")

#         # compare size of current inventory list to saved list
#         if len(inventory_list) >= len(saved_inventory_list):

#             # iterate over the current inventory list to compare for changes
#             for i in range(len(inventory_list)):

#                 changes = ""
#                 match_found = False
                
#                 # checks if the entries being compared are the same release (using url as an id)
#                 if inventory_list[i].url == saved_inventory_list[i].url:
#                     changes += compare_entries(inventory_list[i], saved_inventory_list[i])

#                 else:
#                     # if the entries don't match up, find the matching entry/release by traversing the list
#                     for j in range(i+1,len(saved_inventory_list)):
#                         if inventory_list[i].url == saved_inventory_list[j].url:
#                             # if the matching entry is found, do a comparison
#                             # then a swap to reorganize list for future compares 
#                             changes += compare_entries(inventory_list[i], saved_inventory_list[j])
#                             saved_inventory_list[i], saved_inventory_list[j] = saved_inventory_list[j], saved_inventory_list[i]
#                             match_found = True

#                     # if a matching entry/release isn't found after the traversal, treat the corresponding entries in the current
#                     # and saved inventory lists both as new entries/changes to log
#                     if not match_found:
#                         print("Changes detected.")
#                         embeded_changes.append(embed(inventory_list[i],changes))
#                         embeded_changes.append(embed(saved_inventory_list[i],changes))
                
#                 # if the current release entry has changed, log the changes in an Emded object
#                 if changes != "":
#                     print("Changes detected. Sending to webhook.")
#                     embeded_changes.append(embed(inventory_list[i],changes))

#         else:
#             # TODO: current inventory list size smaller than last compared, do...
#             print("Inventory size changed.")
            
            
#         print("Finished comparison.")

#     else:
#         print("Nothing to load.\n")
            
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

    # trim HTML from the entry listings
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
