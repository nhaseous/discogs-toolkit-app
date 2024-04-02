import collections
collections.Callable = collections.abc.Callable

from bs4 import BeautifulSoup
import math

# Discogs Collection Matcher Module
# Compares 2 public Discogs lists (option for Collection or Wantlist), and returns matching titles from both lists.

## Get ##

def get_collection(username, scraper):

    URL = "https://www.discogs.com/user/{0}/collection?header=1".format(username)
    pages = count_pages(URL, scraper)

    return parse_list(URL, pages, scraper)

def get_wantlist(username, scraper):

    URL = "https://www.discogs.com/wantlist?user={0}".format(username)
    pages = count_pages(URL, scraper)

    return parse_list(URL, pages, scraper)

## Helper Functions ##

# Takes URL of a collection or wantlist, returns the releases as a list.
def parse_list(URL, pages, scraper):

    new_list = []

    for page in range(1, pages + 1):
        html = scraper.get("{0}&sort=artist&sort_order=asc&page={1}".format(URL,page)).content
        soup = BeautifulSoup(html, 'html.parser')

        list_items = soup.find_all("tr", class_="shortcut_navigable")
        for item in list_items:
            release = item.find("span", class_="release_title").find_all("a")
            format = item.find_all("td")[3].text
            new_list.append("{0} - {1} ({2})".format(release[0].text, release[1].text, format))

    return new_list

# Takes URL for either collection or wantlist, returns the number of pages.
def count_pages(URL, scraper):
    html = scraper.get(URL).content
    soup = BeautifulSoup(html, 'html.parser')

    collection_size = int(soup.find("li", class_="active_header_section").find("small", class_="facet_count").text.strip().replace(",",""))
    pages = math.ceil(collection_size/25)

    return pages
