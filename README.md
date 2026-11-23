<div align="center">

<img src="lcad_nobg.png" width="128" alt="LCAD icon">

# LCAD

**Lutris Cover Art Downloader**

Fill your Lutris library with proper cover art from SteamGridDB, in a few clicks.

</div>

## What it does

LCAD reads your Lutris library, shows which games are missing artwork, and downloads the images you pick from [SteamGridDB](https://www.steamgriddb.com) straight into the folders Lutris uses.

- **Three kinds of artwork:** vertical covers (600×900), banners (460×215) and square icons.
- **See what's missing:** every game is listed with whether it already has art, and *Select all missing* picks just those.
- **You choose the match:** search results and artwork previews come up for each game, so you pick the right title and the image you like, or skip it.
- **Restarts Lutris for you** when it's done, so the new art shows up straight away (you can turn this off).
- **Native Linux app:** Python with a GTK 4 / libadwaita interface. Downloads run in the background, so the window never freezes.

## Install

### Quick install (Flatpak, DEB or RPM)

```bash
curl -fsSL https://raw.githubusercontent.com/ethembeldagli/lcad/main/install.sh | bash
```

The script detects your distro and asks whether you want the Flatpak or a native package:

| Distro | Options |
| --- | --- |
| Bazzite and other atomic Fedora | Flatpak, or RPM via `rpm-ostree` |
| Fedora, RHEL, openSUSE | Flatpak or RPM |
| Debian, Ubuntu, Linux Mint | Flatpak or DEB |
| Anything else | Flatpak |

You can also download the packages yourself from the [Releases](https://github.com/ethembeldagli/lcad/releases) page.

### Run from source

You need Python 3, PyGObject with GTK 4 and libadwaita, and `requests`.

```bash
git clone https://github.com/ethembeldagli/lcad
cd lcad
python3 main.py
```

## How to use it

1. **Add your SteamGridDB API key.** LCAD asks for it on first launch. Get a free one from your [SteamGridDB preferences](https://www.steamgriddb.com/profile/preferences/api). It's checked, then saved in `~/.config/lcad/apikey.txt`.
2. **Pick the artwork type**: Vertical, Banner or Icon.
3. **Select games**, or click *Select all missing*.
4. Click **Download Media for Selected**. For each game, confirm the right SteamGridDB match, then choose an image.
5. LCAD saves the files and restarts Lutris.

## Where files go

| Type | Saved to |
| --- | --- |
| Vertical covers | `~/.local/share/lutris/coverart/<game>.jpg` |
| Banners | `~/.local/share/lutris/banners/<game>.jpg` |
| Icons | `~/.local/share/icons/hicolor/128x128/apps/lutris_<game>.png` and `~/.local/share/lutris/icons/<game>.png` |

LCAD reads your game list from `~/.local/share/lutris/pga.db`, so you need at least one game added in Lutris.

## Project layout

| File | What it is |
| --- | --- |
| `main.py` | Entry point |
| `gui.py` | GTK 4 / libadwaita interface |
| `core.py` | Lutris database, SteamGridDB API and file saving (no UI code) |
| `install.sh` | Multi-distro installer |
| `io.github.ethembeldagli.lcad.yml` | Flatpak manifest |

---

LCAD isn't affiliated with Lutris or SteamGridDB.
