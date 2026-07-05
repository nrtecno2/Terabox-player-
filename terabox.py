"""
terabox.py
Terabox share links se file info + direct download link nikalne ke liye.
Koi official/paid Terabox API use nahi hota - jo endpoint terabox ki website
khud browser me use karti hai, wahi endpoint yahan call kiya jata hai.

IMPORTANT (update): Terabox ne ab bina login/cookie ke public endpoint
access restrict kar diya hai. Isliye ab is module ko kaam karne ke liye
ek REAL Terabox account ka cookie chahiye (TERABOX_COOKIE environment
variable me set karna hoga). Cookie nikalne ka tareeka README me hai.

NOTE: Terabox apni website ka structure/endpoint kabhi kabhi change karta hai.
Agar ye kaam karna band kar de, to is file ke jsToken-extraction regex ya
endpoint path update karne se dobara chalu ho sakta hai.
"""

import os
import re
import requests

TERABOX_COOKIE = os.environ.get("TERABOX_COOKIE", "").strip()

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.terabox.com/",
}

# Terabox ke alag alag domain variants jo log share karte hain
TERABOX_DOMAINS = [
    "terabox.com", "1024terabox.com", "teraboxapp.com", "freeterabox.com",
    "nephobox.com", "4funbox.com", "mirrobox.com", "momerybox.com",
    "teraboxshare.com", "terafileshare.com", "1024tera.com", "1024tera.cn",
    "terasharelink.com", "teraboxlink.com",
]


def is_terabox_link(url: str) -> bool:
    return any(d in url for d in TERABOX_DOMAINS)


def _headers_with_cookie():
    h = dict(HEADERS)
    if TERABOX_COOKIE:
        h["Cookie"] = TERABOX_COOKIE
    return h


def _extract_surl(session: requests.Session, url: str):
    """Link ko follow karke final URL se short-url (surl) nikalta hai."""
    resp = session.get(url, headers=_headers_with_cookie(), allow_redirects=True, timeout=20)
    final_url = resp.url

    match = re.search(r"surl=([^&]+)", final_url)
    if match:
        return match.group(1), final_url, resp.text

    match = re.search(r"/s/1([A-Za-z0-9_\-]+)", final_url)
    if match:
        return "1" + match.group(1), final_url, resp.text

    match = re.search(r"/s/([A-Za-z0-9_\-]+)", final_url)
    if match:
        return match.group(1), final_url, resp.text

    return None, final_url, resp.text


def _extract_js_token(html: str):
    """
    Share page ki HTML me jsToken embed hota hai (URL-encoded JS ke andar).
    Alag alag patterns try karte hain kyunki Terabox format kabhi kabhi
    thoda badalta rehta hai.
    """
    patterns = [
        r"fn%28%22(.*?)%22%29",
        r'window\.jsToken\s*=\s*"(.*?)"',
        r'jsToken["\']?\s*[:=]\s*["\'](.*?)["\']',
    ]
    for pattern in patterns:
        match = re.search(pattern, html)
        if match:
            return match.group(1)
    return None


def get_terabox_files(share_url: str):
    """
    Terabox share link se file list nikalta hai.
    Return: list of dicts -> [{name, size, dlink, thumb, fs_id}, ...]
    Error hone par: raises Exception with readable message.
    """
    if not TERABOX_COOKIE:
        raise Exception(
            "Server par TERABOX_COOKIE set nahi hai. Admin ko bataayein ki "
            "TERABOX_COOKIE environment variable configure karein."
        )

    session = requests.Session()
    surl, final_url, html = _extract_surl(session, share_url)
    if not surl:
        raise Exception("Ye link valid Terabox share link nahi lag raha hai.")

    domain_match = re.search(r"https?://([^/]+)/", final_url + "/")
    base_domain = domain_match.group(1) if domain_match else "www.terabox.com"

    js_token = _extract_js_token(html)
    if not js_token:
        raise Exception(
            "jsToken nahi mil paaya - shayad link expired/invalid hai, "
            "ya Terabox ne page ka structure change kar diya hai."
        )

    share_api = f"https://{base_domain}/share/list"
    share_params = {
        "app_id": "250528",
        "web": "1",
        "channel": "dubox",
        "clienttype": "0",
        "jsToken": js_token,
        "shorturl": surl,
        "root": "1",
    }
    r = session.get(share_api, headers=_headers_with_cookie(), params=share_params, timeout=20)
    if r.status_code != 200:
        raise Exception("Terabox se file info nahi mil paayi (server error).")

    try:
        data = r.json()
    except ValueError:
        raise Exception("Terabox se aaya response samajh nahi aaya (structure change ho sakta hai).")

    if data.get("errno") != 0:
        raise Exception(
            f"Ye link expired ho chuka hai ya private/invalid hai. (errno={data.get('errno')})"
        )

    file_list = data.get("list", [])
    if not file_list:
        raise Exception("Is link me koi file nahi mili.")

    results = []
    for f in file_list:
        if str(f.get("isdir")) == "1":
            continue
        dlink = f.get("dlink")
        if not dlink:
            continue
        results.append({
            "name": f.get("server_filename", "file"),
            "size": int(f.get("size", 0)),
            "dlink": dlink,
            "thumb": (f.get("thumbs") or {}).get("url3", ""),
            "fs_id": f.get("fs_id"),
        })

    if not results:
        raise Exception("Direct download link generate nahi ho paaya. Link expired ho sakta hai.")

    return results


def download_file(dlink: str, dest_path: str, max_bytes: int = 1_900_000_000):
    """File ko stream karke local disk par download karta hai."""
    session = requests.Session()
    with session.get(dlink, headers=_headers_with_cookie(), stream=True, timeout=60) as r:
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
    
