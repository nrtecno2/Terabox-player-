"""
terabox.py
Terabox share links se file info + direct download link nikalne ke liye.
Koi official/paid Terabox API use nahi hota - jo endpoint terabox ki website
khud browser me use karti hai, wahi endpoint yahan call kiya jata hai.

NOTE: Terabox apni website ka structure/endpoint kabhi kabhi change karta hai.
Agar ye kaam karna band kar de, to sirf DOMAIN_HOSTS list aur API path
update karne se dobara chalu ho sakta hai.
"""

import re
import requests

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.9",
}

# Terabox ke alag alag domain variants jo log share karte hain
TERABOX_DOMAINS = [
    "terabox.com", "1024terabox.com", "teraboxapp.com", "freeterabox.com",
    "nephobox.com", "4funbox.com", "mirrobox.com", "momerybox.com",
    "teraboxshare.com", "terafileshare.com", "1024tera.com", "1024tera.cn",
]


def is_terabox_link(url: str) -> bool:
    return any(d in url for d in TERABOX_DOMAINS)


def _extract_surl(session: requests.Session, url: str):
    """Link ko follow karke final URL se short-url (surl) nikalta hai."""
    resp = session.get(url, headers=HEADERS, allow_redirects=True, timeout=20)
    final_url = resp.url

    match = re.search(r"surl=([^&]+)", final_url)
    if match:
        return match.group(1), final_url

    match = re.search(r"/s/1([A-Za-z0-9_\-]+)", final_url)
    if match:
        return "1" + match.group(1), final_url

    match = re.search(r"/s/([A-Za-z0-9_\-]+)", final_url)
    if match:
        return match.group(1), final_url

    return None, final_url


def get_terabox_files(share_url: str):
    """
    Terabox share link se file list nikalta hai.
    Return: list of dicts -> [{name, size, dlink, thumb, is_dir, fs_id}, ...]
    Error hone par: raises Exception with readable message.
    """
    session = requests.Session()
    surl, final_url = _extract_surl(session, share_url)
    if not surl:
        raise Exception("Ye link valid Terabox share link nahi lag raha hai.")

    # final_url ke domain ko use karo, taaki jo bhi mirror domain ho use ho
    domain_match = re.search(r"https?://([^/]+)/", final_url + "/")
    base_domain = domain_match.group(1) if domain_match else "www.terabox.com"

    list_api = f"https://{base_domain}/api/shorturlinfo"
    params = {
        "app_id": "250528",
        "web": "1",
        "channel": "dubox",
        "clienttype": "0",
        "shorturl": surl,
        "root": "1",
    }

    r = session.get(list_api, headers=HEADERS, params=params, timeout=20)
    if r.status_code != 200:
        raise Exception("Terabox se file info nahi mil paayi (server error).")

    data = r.json()
    if data.get("errno") != 0:
        raise Exception("Ye link expired ho chuka hai ya private/invalid hai.")

    file_list = data.get("list", [])
    if not file_list:
        raise Exception("Is link me koi file nahi mili.")

    # Ab actual download link (dlink) fetch karo share/list endpoint se
    share_api = f"https://{base_domain}/share/list"
    share_params = {
        "app_id": "250528",
        "web": "1",
        "channel": "dubox",
        "clienttype": "0",
        "shorturl": surl,
        "root": "1",
    }
    r2 = session.get(share_api, headers=HEADERS, params=share_params, timeout=20)
    share_data = r2.json() if r2.status_code == 200 else {}
    dlink_map = {}
    if share_data.get("errno") == 0:
        for item in share_data.get("list", []):
            dlink_map[item.get("fs_id")] = item.get("dlink")

    results = []
    for f in file_list:
        if f.get("isdir") == "1" or f.get("isdir") == 1:
            continue
        fs_id = f.get("fs_id")
        dlink = dlink_map.get(fs_id) or f.get("dlink")
        if not dlink:
            continue
        results.append({
            "name": f.get("server_filename", "file"),
            "size": int(f.get("size", 0)),
            "dlink": dlink,
            "thumb": (f.get("thumbs") or {}).get("url3", ""),
            "fs_id": fs_id,
        })

    if not results:
        raise Exception("Direct download link generate nahi ho paaya. Link expired ho sakta hai.")

    return results


def resolve_direct_link(session: requests.Session, dlink: str) -> str:
    """dlink ek redirect hota hai, final CDN link (d-xx.terabox.com) nikalta hai."""
    r = session.head(dlink, headers=HEADERS, allow_redirects=True, timeout=20)
    return r.url


def download_file(dlink: str, dest_path: str, max_bytes: int = 1_900_000_000):
    """File ko stream karke local disk par download karta hai."""
    session = requests.Session()
    with session.get(dlink, headers=HEADERS, stream=True, timeout=60) as r:
        r.raise_for_status()
        total = 0
        with open(dest_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=1024 * 1024):
                if not chunk:
                    continue
                total += len(chunk)
                if total > max_bytes:
                    raise Exception("File size limit se zyada hai.")
                f.write(chunk)
    return dest_path
