"""Download licensed Dubai photographs from Wikimedia Commons.

For every entry in ``WIKI`` it takes the lead image of the matching Wikipedia article,
saves a 1400px copy under ``apps/web/public/images/dubai`` and records author, license
and source in ``apps/web/lib/image-credits.json``. Only freely licensed files are kept.
Entries without a usable image are skipped; the web app falls back by category.

Run:  python scripts/fetch_images.py
"""

from __future__ import annotations

import html
import json
import re
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "apps" / "web" / "public" / "images" / "dubai"
CREDITS = ROOT / "apps" / "web" / "lib" / "image-credits.json"
API = "https://commons.wikimedia.org/w/api.php"
EN_API = "https://en.wikipedia.org/w/api.php"
HEADERS = {"User-Agent": "DubaiJourneyAI/1.0 (student travel planner; contact: local)"}

# key -> Wikipedia article title. Keys for places use the seed place id without "place-".
WIKI: dict[str, str] = {
    "burj-khalifa": "Burj Khalifa",
    "downtown-dubai": "Downtown Dubai",
    "museum-of-the-future": "Museum of the Future",
    "dubai-marina": "Dubai Marina",
    "jumeirah-beach": "Jumeirah Beach",
    "palm-jumeirah": "Palm Jumeirah",
    "dubai-creek": "Dubai Creek",
    "al-fahidi-historical-neighbourhood": "Al Fahidi Historical Neighbourhood",
    "dubai-museum": "Dubai Museum",
    "gold-souk": "Gold Souk, Dubai",
    "spice-souk": "Spice Souk (Dubai)",
    "textile-souk": "Textile Souk",
    "heritage-village": "Heritage Village (Dubai)",
    "al-shindagha-museum": "Al Shindagha Museum",
    "jumeirah-mosque": "Jumeirah Mosque",
    "etihad-museum": "Etihad Museum",
    "alserkal-avenue": "Alserkal Avenue",
    "al-seef": "Al Seef",
    "dubai-frame": "Dubai Frame",
    "ain-dubai": "Ain Dubai",
    "burj-al-arab": "Burj Al Arab",
    "dubai-water-canal": "Dubai Water Canal",
    "bluewaters-island": "Bluewaters Island",
    "ras-al-khor-wildlife-sanctuary": "Ras Al Khor Wildlife Sanctuary",
    "emirates-towers": "Emirates Towers",
    "souk-al-bahar": "Souk Al Bahar",
    "dubai-opera": "Dubai Opera",
    "jbr-beach": "Jumeirah Beach Residence",
    "zabeel-park": "Zabeel Park",
    "safa-park": "Safa Park",
    "al-qudra-lakes": "Al Qudra Lakes",
    "dubai-miracle-garden": "Dubai Miracle Garden",
    "the-dubai-mall": "The Dubai Mall",
    "mall-of-the-emirates": "Mall of the Emirates",
    "ibn-battuta-mall": "Ibn Battuta Mall",
    "deira-city-centre": "Deira City Centre",
    "burjuman": "BurJuman",
    "img-worlds-of-adventure": "IMG Worlds of Adventure",
    "motiongate-dubai": "Motiongate Dubai",
    "legoland-dubai": "Legoland Dubai",
    "ski-dubai": "Ski Dubai",
    "wild-wadi-waterpark": "Wild Wadi Waterpark",
    "aquaventure-waterpark": "Aquaventure Waterpark",
    "the-lost-chambers-aquarium": "Atlantis, The Palm",
    "city-walk": "City Walk, Dubai",
    "global-village": "Global Village (Dubai)",
    "expo-city-dubai": "Expo City Dubai",
    "souk-madinat-jumeirah": "Souk Madinat Jumeirah",
    "dubai-fountain": "The Dubai Fountain",
    "dubai-creek-abra-crossing": "Abra (boat)",
    "desert": "Dubai Desert Conservation Reserve",
    "emirati-food": "Emirati cuisine",
    "dubai-skyline": "Skyline of Dubai",
}

# Commons search queries for hero style images (wide, skyline at golden hour / dusk).
SEARCH: dict[str, str] = {
    "hero-skyline": "Burj Khalifa worlds tallest building and the Dubai skyline",
    "desert-dunes": "Dubai desert dunes sunset safari",
    "dhow-creek": "Dubai Creek abra dhow Deira",
}

FREE = re.compile(r"^(CC0|CC BY|CC BY-SA|Public domain|PD|Attribution)", re.I)


def clean(value: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", value or "")).strip()


def api_get(url: str, params: dict, headers: dict, timeout: int) -> requests.Response:
    """GET that retries with growing waits when Wikimedia rate limits (HTML/429)."""
    for attempt in range(6):
        resp = requests.get(url, params=params, headers=headers, timeout=timeout)
        if resp.status_code == 200:
            try:
                resp.json()
                return resp
            except ValueError:
                pass
        wait = 15 * (attempt + 1)
        print(f"  rate limited ({resp.status_code}); waiting {wait}s")
        time.sleep(wait)
    raise RuntimeError("Wikimedia kept refusing the request")


def file_for_article(title: str) -> str | None:
    r = api_get(
        EN_API,
        params={
            "action": "query",
            "titles": title,
            "prop": "pageimages",
            "piprop": "name",
            "redirects": 1,
            "format": "json",
        },
        headers=HEADERS,
        timeout=30,
    )
    for page in r.json().get("query", {}).get("pages", {}).values():
        name = page.get("pageimage")
        if name:
            return "File:" + name
    return None


def file_for_search(query: str) -> str | None:
    r = api_get(
        API,
        params={
            "action": "query",
            "generator": "search",
            "gsrsearch": query,
            "gsrnamespace": 6,
            "gsrlimit": 5,
            "prop": "imageinfo",
            "iiprop": "size",
            "format": "json",
        },
        headers=HEADERS,
        timeout=30,
    )
    pages = r.json().get("query", {}).get("pages", {}).values()
    wide = [p for p in pages if p["imageinfo"][0]["width"] >= 2400 and p["title"].lower().endswith((".jpg", ".jpeg"))]
    return wide[0]["title"] if wide else None


def fetch(key: str, file_title: str) -> dict[str, str] | None:
    r = api_get(
        API,
        params={
            "action": "query",
            "titles": file_title,
            "prop": "imageinfo",
            "iiprop": "url|extmetadata|size",
            "iiurlwidth": 1280,
            "format": "json",
        },
        headers=HEADERS,
        timeout=30,
    )
    pages = list(r.json().get("query", {}).get("pages", {}).values())
    if not pages or "imageinfo" not in pages[0]:
        return None
    info = pages[0]["imageinfo"][0]
    meta = info.get("extmetadata", {})
    license_name = clean(meta.get("LicenseShortName", {}).get("value", ""))
    if not FREE.match(license_name):
        print(f"  skip {key}: license {license_name!r}")
        return None
    url = info.get("thumburl") or info["url"]
    if not url.lower().split("?")[0].endswith((".jpg", ".jpeg")):
        print(f"  skip {key}: not a jpeg")
        return None
    data = None
    for attempt in range(4):
        resp = requests.get(url, headers=HEADERS, timeout=60)
        if resp.status_code == 200:
            data = resp.content
            break
        time.sleep(15 * (attempt + 1))
    if data is None:
        print(f"  skip {key}: download failed")
        return None
    (OUT / f"{key}.jpg").write_bytes(data)
    return {
        "file": f"/images/dubai/{key}.jpg",
        "title": file_title.removeprefix("File:"),
        "author": clean(meta.get("Artist", {}).get("value", "")) or "Unknown",
        "license": license_name,
        "license_url": clean(meta.get("LicenseUrl", {}).get("value", "")),
        "source": info.get("descriptionurl", ""),
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    credits: dict[str, dict[str, str]] = {}
    if CREDITS.is_file():
        credits = json.loads(CREDITS.read_text(encoding="utf-8"))
    jobs: list[tuple[str, str | None, str]] = []
    jobs += [(k, None, t) for k, t in WIKI.items()]
    jobs += [(k, q, "") for k, q in SEARCH.items()]
    for key, query, title in jobs:
        if key in credits and (OUT / f"{key}.jpg").is_file():
            continue
        try:
            file_title = file_for_search(query) if query else file_for_article(title)
            if not file_title:
                print(f"- {key}: no image")
                continue
            entry = fetch(key, file_title)
            if entry:
                credits[key] = entry
                print(f"+ {key}: {entry['title']} ({entry['license']})")
        except Exception as exc:  # noqa: BLE001 - keep going, report at the end
            print(f"! {key}: {exc}")
        time.sleep(4)
    CREDITS.write_text(json.dumps(credits, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n{len(credits)} images saved; credits in {CREDITS}")


if __name__ == "__main__":
    main()
