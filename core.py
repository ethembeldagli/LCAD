"""
Core logic for Lutris Cover Art Downloader.
No GTK/UI code here - keeps this testable and reusable.
"""
import os
import sqlite3
import subprocess
import time
import requests

STEAMGRIDDB_BASE = "https://www.steamgriddb.com/api/v2"

BANNER_DIMS_SAVE = "460x215"
BANNER_DIMS_QUERY = "460x215,920x430"  # 920x430 = same aspect ratio, 2x res
VERTICAL_DIMS_SAVE = "600x900"
VERTICAL_DIMS_QUERY = "600x900,342x482,660x930"  # same ~2:3 aspect ratio, other res

REQUEST_TIMEOUT = 15


# ---------------------------------------------------------------------------
# Lutris library
# ---------------------------------------------------------------------------

def get_db_path():
    return os.path.expanduser("~/.local/share/lutris/pga.db")


def get_cover_dir(cover_type):
    """cover_type: 'banner' or 'vertical'"""
    base = os.path.expanduser("~/.local/share/lutris")
    return os.path.join(base, "banners" if cover_type == "banner" else "coverart")


def get_query_dims(cover_type):
    return BANNER_DIMS_QUERY if cover_type == "banner" else VERTICAL_DIMS_QUERY


def list_games():
    """Scan the Lutris pga.db and return a list of dicts describing each game."""
    dbpath = get_db_path()
    if not os.path.isfile(dbpath):
        raise FileNotFoundError(
            f"Lutris database not found at {dbpath}. "
            "Is Lutris installed and have you added at least one game?"
        )

    conn = sqlite3.connect(dbpath)
    try:
        cur = conn.execute(
            "SELECT slug, name FROM games WHERE slug IS NOT NULL ORDER BY name COLLATE NOCASE"
        )
        rows = cur.fetchall()
    finally:
        conn.close()

    banner_dir = get_cover_dir("banner")
    cover_dir = get_cover_dir("vertical")

    games = []
    seen_slugs = set()
    for slug, name in rows:
        if not slug or slug in seen_slugs:
            continue
        seen_slugs.add(slug)
        games.append({
            "slug": slug,
            "name": name or slug.replace("-", " ").title(),
            "has_banner": os.path.isfile(os.path.join(banner_dir, slug + ".jpg")),
            "has_cover": os.path.isfile(os.path.join(cover_dir, slug + ".jpg")),
        })
    return games


# ---------------------------------------------------------------------------
# API key storage (kept in XDG config dir so it survives Flatpak sandboxing)
# ---------------------------------------------------------------------------

def api_key_path():
    cfg_dir = os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config"))
    d = os.path.join(cfg_dir, "lutris-cover-downloader")
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, "apikey.txt")


def load_api_key():
    path = api_key_path()
    if os.path.isfile(path):
        with open(path) as f:
            key = f.read().strip()
            if key:
                return key
    return None


def save_api_key(key):
    with open(api_key_path(), "w") as f:
        f.write(key.strip())


def test_api_key(key):
    headers = {"Authorization": f"Bearer {key}"}
    try:
        r = requests.get(
            f"{STEAMGRIDDB_BASE}/grids/game/1?dimensions=600x900",
            headers=headers, timeout=REQUEST_TIMEOUT,
        )
        return r.status_code == 200
    except requests.RequestException:
        return False


# ---------------------------------------------------------------------------
# SteamGridDB search / download
# ---------------------------------------------------------------------------

def search_game(query, api_key):
    """Return a list of {id, name, release_date} dicts matching the query."""
    headers = {"Authorization": f"Bearer {api_key}"}
    url = f"{STEAMGRIDDB_BASE}/search/autocomplete/{requests.utils.quote(query)}"
    r = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
    r.raise_for_status()
    data = r.json()
    if not data.get("success"):
        return []
    return [
        {
            "id": g["id"],
            "name": g.get("name", "Unknown"),
            "release_date": g.get("release_date"),
        }
        for g in data.get("data", [])
    ]


ALLOWED_DIMS = {
    "banner": {(460, 215), (920, 430)},
    "vertical": {(600, 900), (342, 482), (660, 930)},
}


def get_grid_images(game_id, dims_query, api_key, cover_type=None):
    """Return the full list of available grid images for a game as
    {id, url, thumb, width, height, style} dicts (not just the first one).

    If cover_type is given, results are filtered client-side to only include
    images whose actual width/height match that cover type's allowed sizes -
    the API's own `dimensions` query param filtering isn't always reliable.
    """
    headers = {"Authorization": f"Bearer {api_key}"}
    url = f"{STEAMGRIDDB_BASE}/grids/game/{game_id}?dimensions={dims_query}"
    r = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
    if r.status_code != 200:
        return []
    data = r.json()
    if not data.get("success") or not data.get("data"):
        return []

    images = [
        {
            "id": g["id"],
            "url": g["url"],
            "thumb": g.get("thumb", g["url"]),
            "width": g.get("width"),
            "height": g.get("height"),
            "style": g.get("style"),
        }
        for g in data["data"]
    ]

    if cover_type and cover_type in ALLOWED_DIMS:
        allowed = ALLOWED_DIMS[cover_type]
        images = [img for img in images if (img["width"], img["height"]) in allowed]

    return images


def get_grid_image_url(game_id, dims_query, api_key):
    """Return the URL of the first matching grid image, or None."""
    images = get_grid_images(game_id, dims_query, api_key)
    return images[0]["url"] if images else None


def download_bytes(url):
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    return r.content


def save_cover_bytes(data, slug, cover_type):
    """Write already-downloaded image bytes to the right Lutris cover dir."""
    dest_dir = get_cover_dir(cover_type)
    os.makedirs(dest_dir, exist_ok=True)
    dest_path = os.path.join(dest_dir, slug + ".jpg")
    with open(dest_path, "wb") as f:
        f.write(data)
    return dest_path


def download_and_save(url, slug, cover_type):
    """Download an image URL and save it as <slug>.jpg in the right Lutris dir."""
    data = download_bytes(url)
    return save_cover_bytes(data, slug, cover_type)


# ---------------------------------------------------------------------------
# Restart Lutris
# ---------------------------------------------------------------------------

def restart_lutris():
    """Kill any running Lutris process and relaunch it.

    Works both for a normal desktop session and when this app itself is
    running sandboxed inside Flatpak (uses flatpak-spawn --host in that case).
    """
    host_prefix = ["flatpak-spawn", "--host"] if os.environ.get("FLATPAK_ID") else []

    try:
        subprocess.run(host_prefix + ["pkill", "-x", "lutris"], check=False)
    except FileNotFoundError:
        pass

    time.sleep(1.5)

    try:
        subprocess.Popen(host_prefix + ["lutris"])
    except FileNotFoundError:
        pass
