import requests
import json
import time

def analyze_collection(username):
    url = f"https://api.discogs.com/users/{username}/collection/folders/0/releases"
    params = {
        "page": 1,
        "per_page": 100,
        "sort": "artist",
        "sort_order": "asc"
    }
    headers = {
        "User-Agent": "DiscogsToolkit/1.0 +https://github.com/nha/discogs-toolkit-app"
    }
    
    unique_format_descriptions = set()
    unique_format_text = set()
    page = 1
    
    while True:
        print(f"Fetching collection page {page}...")
        response = requests.get(url, params=params, headers=headers)
        if response.status_code != 200:
            print(f"Error fetching collection: {response.status_code}")
            break
        
        data = response.json()
        releases = data.get("releases", [])
        if not releases:
            break
            
        for item in releases:
            basic = item.get("basic_information", {})
            formats = basic.get("formats", [])
            for f in formats:
                descriptions = f.get("descriptions", [])
                if descriptions:
                    for desc in descriptions:
                        unique_format_descriptions.add(desc)
                
                text = f.get("text")
                if text:
                    unique_format_text.add(text)
            
        pagination = data.get("pagination", {})
        if page >= pagination.get("pages", 1):
            break
        page += 1
        params["page"] = page
        time.sleep(0.5)

    print("\nUnique format-desc values found in Collection API:")
    for f in sorted(list(unique_format_descriptions)):
        print(f"- {f}")

    print("\nUnique format 'text' values found in Collection API:")
    for t in sorted(list(unique_format_text)):
        print(f"- {t}")

if __name__ == "__main__":
    analyze_collection("curefortheitch")
