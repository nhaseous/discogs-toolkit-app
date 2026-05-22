import requests
import json

def sample_wantlist(username):
    headers = {
        "User-Agent": "DiscogsToolkit/1.0 +https://github.com/nha/discogs-toolkit-app"
    }
    
    url = f"https://api.discogs.com/users/{username}/wants"
    resp = requests.get(url, headers=headers)
    data = resp.json()
    
    wants = data.get("wants", [])
    for w in wants[:5]:
        basic = w.get("basic_information", {})
        formats = basic.get("formats", [])
        if formats:
            print(f"Wantlist {w.get('id')}: {basic.get('title')} - {formats[0].get('descriptions')}")

if __name__ == "__main__":
    sample_wantlist("curefortheitch")
