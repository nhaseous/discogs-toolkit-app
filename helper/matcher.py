from bs4 import BeautifulSoup
import math

# Compares 2 public Discogs lists (option for Collection or Wantlist), and returns matching titles from both lists.


# Helper Functions

def get_collection(username, scraper):

    URL = "https://www.discogs.com/user/{0}/collection?header=1".format(username)
    pages = count_pages(URL, scraper)

    return parse_list(URL, pages, scraper)

def get_wantlist(username, scraper):

    URL = "https://www.discogs.com/wantlist?user={0}".format(username)
    pages = count_pages(URL, scraper)

    return parse_list(URL, pages, scraper)

def count_pages(URL, scraper): # Takes URL for either collection or wantlist, returns the number of pages.
    html = scraper.get(URL).content
    soup = BeautifulSoup(html, 'html.parser')

    collection_size = int(soup.find("li", class_="active_header_section").find("small", class_="facet_count").text)
    pages = math.ceil(collection_size/25)

    return pages

def parse_list(URL, pages, scraper): # Takes URL of a collection or wantlist, returns the releases as a list.

    new_list = []

    for page in range(1, pages + 1):
        new_URL = URL + "&sort=artist&sort_order=asc&page={0}".format(page)
        html = scraper.get(new_URL).content
        soup = BeautifulSoup(html, 'html.parser')

        list_items = soup.find_all("tr", class_="shortcut_navigable")
        for item in list_items:
            release = item.find("span", class_="release_title").find_all("a")
            format = item.find_all("td")[3].text

            new_list_item = "{0} - {1} ({2})".format(release[0].text, release[1].text, format)

            # removes consecutive duplicates in the list
            # if len(new_list) > 0 and new_list[-1] != new_list_item:
            #     new_list.append(new_list_item)
            # elif len(new_list) == 0:
            #     new_list.append(new_list_item)

            new_list.append(new_list_item)

    return new_list
