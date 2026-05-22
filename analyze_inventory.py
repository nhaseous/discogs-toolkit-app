import requests
import json

def analyze_inventory(username):
    url = f"https://api.discogs.com/users/{username}/inventory"
    params = {
        "page": 1,
        "per_page": 100,
        "status": "For Sale"
    }
    headers = {
        "User-Agent": "DiscogsToolkit/1.0 +https://github.com/nha/discogs-toolkit-app"
    }
    
    unusual_tags = ['"Bl', '2-Y', 'Bab', 'Bei', 'Bla', 'Clo', 'Dee', 'MRP', 'Ser']
    found_unusual = {}
    
    page = 1
    while True:
        response = requests.get(url, params=params, headers=headers)
        if response.status_code != 200: break
        data = response.json()
        listings = data.get("listings", [])
        if not listings: break
            
        for listing in listings:
            release = listing.get("release", {})
            fmt_str = release.get("format", "")
            title = release.get("title", "")
            artist = release.get("artist", "")
            
            parts = fmt_str.replace("+", ",").split(",")
            for p in parts:
                tag = p.strip()
                if tag in unusual_tags:
                    if tag not in found_unusual:
                        found_unusual[tag] = []
                    found_unusual[tag].append(f"{artist} - {title} ({fmt_str})")
            
        pagination = data.get("pagination", {})
        if page >= pagination.get("pages", 1): break
        page += 1
        params["page"] = page

    print("\nInvestigation of unusual tags:")
    for tag, examples in found_unusual.items():
        print(f"\nTag: {tag}")
        for ex in examples[:3]:
            print(f"  - {ex}")

if __name__ == "__main__":
    analyze_inventory("curefortheitch")
