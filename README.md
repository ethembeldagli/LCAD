# Lutris Cover Art Downloader

A small GTK4/Libadwaita app that scans your Lutris library, lets you pick which
games to fetch artwork for, searches SteamGridDB, and saves banners/covers
where Lutris expects them (`~/.local/share/lutris/{banners,coverart}`).
Optionally restarts Lutris automatically when done.

## Files

```
main.py     - entry point
gui.py      - GTK4/Adwaita UI
core.py     - Lutris DB scanning, SteamGridDB API, downloads, restart logic
data/       - .desktop file + AppStream metainfo for packaging
io.github.lutriscoverdownloader.App.yml - Flatpak manifest
```

## Running it locally (without Flatpak)

You need GTK4 + libadwaita's Python bindings and `requests`. On most distros:

```bash
# Fedora/Bazzite
sudo dnf install python3-gobject gtk4 libadwaita
# Debian/Ubuntu
sudo apt install python3-gi gir1.2-gtk-4.0 gir1.2-adw-1

pip install requests --break-system-packages   # or use a venv
python3 main.py
```

## Building the Flatpak

1. Install flatpak-builder and the GNOME 47 runtime/SDK:
   ```bash
   flatpak install flathub org.gnome.Platform//47 org.gnome.Sdk//47
   ```

2. Generate the vendored `requests` module manifest (the app depends on
   `requests`, which isn't part of the GNOME runtime, so it needs to be
   built from source inside the Flatpak sandbox):
   ```bash
   pip install --user pipx
   pipx run --spec git+https://github.com/flatpak/flatpak-builder-tools \
       flatpak-pip-generator requests
   ```
   This produces `python3-requests.json`. Put it next to the manifest
   (`io.github.lutriscoverdownloader.App.yml`) - it's already referenced
   there as a module.

3. Build and install locally:
   ```bash
   flatpak-builder --user --install --force-clean build-dir \
       io.github.lutriscoverdownloader.App.yml
   ```

4. Run it:
   ```bash
   flatpak run io.github.lutriscoverdownloader.App
   ```

## Publishing to Flathub

1. Rename the app ID (`io.github.lutriscoverdownloader.App`) throughout the
   project (manifest filename, `app-id` field, `.desktop` file, metainfo
   file, and `application_id` in `gui.py`) to something under your own
   GitHub username, e.g. `io.github.YOUR_USERNAME.LutrisCoverDownloader`.
2. Add a proper icon (SVG, ~128x128) under `data/` and reference it in the
   manifest (`install -Dm644 data/icon.svg /app/share/icons/hicolor/scalable/apps/<app-id>.svg`)
   and in the `.desktop`/metainfo files.
3. Push this repo to GitHub, then follow Flathub's submission guide:
   https://docs.flathub.org/docs/for-app-authors/submission
   (short version: fork `flathub/flathub`, add a repo with your manifest,
   open a PR - their bots do most of the validation for you).

## Notes / things you may want to tweak

- The Flatpak sandbox needs `--talk-name=org.freedesktop.Flatpak` and calls
  `flatpak-spawn --host` to kill/relaunch Lutris on the host system, since a
  sandboxed app can't otherwise reach host processes. This is already wired
  up in `core.restart_lutris()`.
- API key is stored in plain text under
  `~/.config/lutris-cover-downloader/apikey.txt` (or the Flatpak-sandboxed
  equivalent). Fine for a personal SteamGridDB key, but not intended as a
  security boundary.
