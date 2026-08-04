"""
GTK4 / Libadwaita GUI for Lutris Cover Art Downloader.
"""
import threading
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import Gtk, Adw, GLib, GObject, GdkPixbuf, Gdk

import core


def run_async(work_fn, done_fn):
    """Run work_fn() in a background thread; call done_fn(result, error) on the
    GTK main thread when finished. error is None on success."""
    def worker():
        try:
            result = work_fn()
            GLib.idle_add(done_fn, result, None)
        except Exception as e:  # noqa: BLE001 - we want to surface any error to the UI
            GLib.idle_add(done_fn, None, e)
    threading.Thread(target=worker, daemon=True).start()


# ---------------------------------------------------------------------------
# Game row (checkbox list item)
# ---------------------------------------------------------------------------

class GameRow(Gtk.Box):
    def __init__(self, game, cover_type):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        self.game = game
        self.set_margin_top(6)
        self.set_margin_bottom(6)
        self.set_margin_start(12)
        self.set_margin_end(12)

        self.check = Gtk.CheckButton()
        self.append(self.check)

        label = Gtk.Label(label=game["name"], xalign=0)
        label.set_hexpand(True)
        self.append(label)

        has_cover = game["has_banner"] if cover_type == "banner" else game["has_cover"]
        status = Gtk.Label(label=("✓ has cover" if has_cover else "missing"))
        status.add_css_class("dim-label" if has_cover else "warning")
        self.append(status)

    def is_selected(self):
        return self.check.get_active()

    def set_selected(self, value):
        self.check.set_active(value)


# ---------------------------------------------------------------------------
# API key dialog
# ---------------------------------------------------------------------------

class ApiKeyDialog(Adw.Window):
    def __init__(self, parent, on_done):
        super().__init__(transient_for=parent, modal=True, title="SteamGridDB API Key")
        self.on_done = on_done
        self.set_default_size(420, -1)

        toolbar = Adw.ToolbarView()
        header = Adw.HeaderBar()
        toolbar.add_top_bar(header)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.set_margin_top(18)
        box.set_margin_bottom(18)
        box.set_margin_start(18)
        box.set_margin_end(18)

        info = Gtk.Label(
            label="Enter your SteamGridDB API key.\n"
                  "Get one from steamgriddb.com/profile/preferences/api",
            wrap=True,
        )
        box.append(info)

        self.entry = Gtk.Entry(placeholder_text="API key")
        self.entry.set_visibility(False)
        box.append(self.entry)

        self.status_label = Gtk.Label(label="")
        self.status_label.add_css_class("error")
        box.append(self.status_label)

        save_btn = Gtk.Button(label="Save & Continue")
        save_btn.add_css_class("suggested-action")
        save_btn.connect("clicked", self.on_save_clicked)
        box.append(save_btn)

        toolbar.set_content(box)
        self.set_content(toolbar)

    def on_save_clicked(self, _btn):
        key = self.entry.get_text().strip()
        if not key:
            return
        self.status_label.set_label("Checking key...")
        run_async(lambda: core.test_api_key(key), lambda ok, err: self._on_tested(key, ok, err))

    def _on_tested(self, key, ok, err):
        if err or not ok:
            self.status_label.set_label("Invalid key, or SteamGridDB unreachable. Try again.")
            return
        core.save_api_key(key)
        self.close()
        self.on_done(key)


# ---------------------------------------------------------------------------
# Match picker dialog (choose which SteamGridDB game matches, or re-search)
# ---------------------------------------------------------------------------

class MatchPickerDialog(Adw.Window):
    def __init__(self, parent, game_display_name, initial_query, api_key, on_result):
        super().__init__(transient_for=parent, modal=True,
                          title=f"Match for {game_display_name}")
        self.api_key = api_key
        self.on_result = on_result
        self._decided = False
        self.set_default_size(460, 480)

        toolbar = Adw.ToolbarView()
        header = Adw.HeaderBar()
        toolbar.add_top_bar(header)

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        outer.set_margin_top(12)
        outer.set_margin_bottom(12)
        outer.set_margin_start(12)
        outer.set_margin_end(12)

        self.query_label = Gtk.Label(label=f"Results for \"{initial_query}\"", xalign=0)
        outer.append(self.query_label)

        scroller = Gtk.ScrolledWindow(vexpand=True)
        self.listbox = Gtk.ListBox()
        self.listbox.set_selection_mode(Gtk.SelectionMode.SINGLE)
        scroller.set_child(self.listbox)
        outer.append(scroller)

        search_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.search_entry = Gtk.Entry(placeholder_text="Search a different term...")
        self.search_entry.set_hexpand(True)
        self.search_entry.connect("activate", self.on_search_clicked)
        search_row.append(self.search_entry)
        search_btn = Gtk.Button(label="Search")
        search_btn.connect("clicked", self.on_search_clicked)
        search_row.append(search_btn)
        outer.append(search_row)

        btn_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        skip_btn = Gtk.Button(label="Skip this game")
        skip_btn.connect("clicked", lambda _b: self._finish(None))
        btn_row.append(skip_btn)

        use_btn = Gtk.Button(label="Use Selected")
        use_btn.add_css_class("suggested-action")
        use_btn.set_hexpand(True)
        use_btn.connect("clicked", self.on_use_clicked)
        btn_row.append(use_btn)
        outer.append(btn_row)

        toolbar.set_content(outer)
        self.set_content(toolbar)

        self.connect("close-request", lambda _w: self._finish(None) or False)

        self._populate(initial_query, results=None)  # results loaded async below
        self._run_search(initial_query)

    def _run_search(self, query):
        self.query_label.set_label(f"Searching for \"{query}\"...")
        run_async(lambda: core.search_game(query, self.api_key),
                  lambda results, err: self._populate(query, results, err))

    def _populate(self, query, results, err=None):
        # clear existing rows
        child = self.listbox.get_first_child()
        while child is not None:
            nxt = child.get_next_sibling()
            self.listbox.remove(child)
            child = nxt

        if results is None:
            return  # initial call before search resolves

        if err is not None:
            self.query_label.set_label(f"Search failed: {err}")
            return

        self.query_label.set_label(f"Results for \"{query}\"" if results else
                                    f"No results for \"{query}\"")

        for game in results:
            row = Gtk.ListBoxRow()
            label_text = game["name"]
            if game.get("release_date"):
                import datetime
                try:
                    year = datetime.datetime.fromtimestamp(game["release_date"]).year
                    label_text += f" ({year})"
                except (OverflowError, OSError, ValueError):
                    pass
            label = Gtk.Label(label=label_text, xalign=0)
            label.set_margin_top(6)
            label.set_margin_bottom(6)
            label.set_margin_start(6)
            label.set_margin_end(6)
            row.set_child(label)
            row.game_id = game["id"]
            self.listbox.append(row)"""
GTK4 / Libadwaita GUI for Lutris Cover Art Downloader.
"""
import threading
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import Gtk, Adw, GLib, GObject, GdkPixbuf, Gdk

import core


def run_async(work_fn, done_fn):
    """Run work_fn() in a background thread; call done_fn(result, error) on the
    GTK main thread when finished. error is None on success."""
    def worker():
        try:
            result = work_fn()
            GLib.idle_add(done_fn, result, None)
        except Exception as e:  # noqa: BLE001 - we want to surface any error to the UI
            GLib.idle_add(done_fn, None, e)
    threading.Thread(target=worker, daemon=True).start()


# ---------------------------------------------------------------------------
# Game row (checkbox list item)
# ---------------------------------------------------------------------------

class GameRow(Gtk.Box):
    def __init__(self, game, cover_type):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        self.game = game
        self.set_margin_top(6)
        self.set_margin_bottom(6)
        self.set_margin_start(12)
        self.set_margin_end(12)

        self.check = Gtk.CheckButton()
        self.append(self.check)

        label = Gtk.Label(label=game["name"], xalign=0)
        label.set_hexpand(True)
        self.append(label)

        has_cover = game["has_banner"] if cover_type == "banner" else game["has_cover"]
        status = Gtk.Label(label=("✓ has cover" if has_cover else "missing"))
        status.add_css_class("dim-label" if has_cover else "warning")
        self.append(status)

    def is_selected(self):
        return self.check.get_active()

    def set_selected(self, value):
        self.check.set_active(value)


# ---------------------------------------------------------------------------
# API key dialog
# ---------------------------------------------------------------------------

class ApiKeyDialog(Adw.Window):
    def __init__(self, parent, on_done):
        super().__init__(transient_for=parent, modal=True, title="SteamGridDB API Key")
        self.on_done = on_done
        self.set_default_size(420, -1)

        toolbar = Adw.ToolbarView()
        header = Adw.HeaderBar()
        toolbar.add_top_bar(header)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.set_margin_top(18)
        box.set_margin_bottom(18)
        box.set_margin_start(18)
        box.set_margin_end(18)

        info = Gtk.Label(
            label="Enter your SteamGridDB API key.\n"
                  "Get one from steamgriddb.com/profile/preferences/api",
            wrap=True,
        )
        box.append(info)

        self.entry = Gtk.Entry(placeholder_text="API key")
        self.entry.set_visibility(False)
        box.append(self.entry)

        self.status_label = Gtk.Label(label="")
        self.status_label.add_css_class("error")
        box.append(self.status_label)

        save_btn = Gtk.Button(label="Save & Continue")
        save_btn.add_css_class("suggested-action")
        save_btn.connect("clicked", self.on_save_clicked)
        box.append(save_btn)

        toolbar.set_content(box)
        self.set_content(toolbar)

    def on_save_clicked(self, _btn):
        key = self.entry.get_text().strip()
        if not key:
            return
        self.status_label.set_label("Checking key...")
        run_async(lambda: core.test_api_key(key), lambda ok, err: self._on_tested(key, ok, err))

    def _on_tested(self, key, ok, err):
        if err or not ok:
            self.status_label.set_label("Invalid key, or SteamGridDB unreachable. Try again.")
            return
        core.save_api_key(key)
        self.close()
        self.on_done(key)


# ---------------------------------------------------------------------------
# Match picker dialog (choose which SteamGridDB game matches, or re-search)
# ---------------------------------------------------------------------------

class MatchPickerDialog(Adw.Window):
    def __init__(self, parent, game_display_name, initial_query, api_key, on_result):
        super().__init__(transient_for=parent, modal=True,
                          title=f"Match for {game_display_name}")
        self.api_key = api_key
        self.on_result = on_result
        self._decided = False
        self.set_default_size(460, 480)

        toolbar = Adw.ToolbarView()
        header = Adw.HeaderBar()
        toolbar.add_top_bar(header)

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        outer.set_margin_top(12)
        outer.set_margin_bottom(12)
        outer.set_margin_start(12)
        outer.set_margin_end(12)

        self.query_label = Gtk.Label(label=f"Results for \"{initial_query}\"", xalign=0)
        outer.append(self.query_label)

        scroller = Gtk.ScrolledWindow(vexpand=True)
        self.listbox = Gtk.ListBox()
        self.listbox.set_selection_mode(Gtk.SelectionMode.SINGLE)
        scroller.set_child(self.listbox)
        outer.append(scroller)

        search_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.search_entry = Gtk.Entry(placeholder_text="Search a different term...")
        self.search_entry.set_hexpand(True)
        self.search_entry.connect("activate", self.on_search_clicked)
        search_row.append(self.search_entry)
        search_btn = Gtk.Button(label="Search")
        search_btn.connect("clicked", self.on_search_clicked)
        search_row.append(search_btn)
        outer.append(search_row)

        btn_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        skip_btn = Gtk.Button(label="Skip this game")
        skip_btn.connect("clicked", lambda _b: self._finish(None))
        btn_row.append(skip_btn)

        use_btn = Gtk.Button(label="Use Selected")
        use_btn.add_css_class("suggested-action")
        use_btn.set_hexpand(True)
        use_btn.connect("clicked", self.on_use_clicked)
        btn_row.append(use_btn)
        outer.append(btn_row)

        toolbar.set_content(outer)
        self.set_content(toolbar)

        self.connect("close-request", lambda _w: self._finish(None) or False)

        self._populate(initial_query, results=None)  # results loaded async below
        self._run_search(initial_query)

    def _run_search(self, query):
        self.query_label.set_label(f"Searching for \"{query}\"...")
        run_async(lambda: core.search_game(query, self.api_key),
                  lambda results, err: self._populate(query, results, err))

    def _populate(self, query, results, err=None):
        # clear existing rows
        child = self.listbox.get_first_child()
        while child is not None:
            nxt = child.get_next_sibling()
            self.listbox.remove(child)
            child = nxt

        if results is None:
            return  # initial call before search resolves

        if err is not None:
            self.query_label.set_label(f"Search failed: {err}")
            return

        self.query_label.set_label(f"Results for \"{query}\"" if results else
                                    f"No results for \"{query}\"")

        for game in results:
            row = Gtk.ListBoxRow()
            label_text = game["name"]
            if game.get("release_date"):
                import datetime
                try:
                    year = datetime.datetime.fromtimestamp(game["release_date"]).year
                    label_text += f" ({year})"
                except (OverflowError, OSError, ValueError):
                    pass
            label = Gtk.Label(label=label_text, xalign=0)
            label.set_margin_top(6)
            label.set_margin_bottom(6)
            label.set_margin_start(6)
            label.set_margin_end(6)
            row.set_child(label)
            row.game_id = game["id"]
            self.listbox.append(row)

        first = self.listbox.get_row_at_index(0)
        if first is not None:
            self.listbox.select_row(first)

    def on_search_clicked(self, _widget):
        query = self.search_entry.get_text().strip()
        if query:
            self._run_search(query)

    def on_use_clicked(self, _btn):
        row = self.listbox.get_selected_row()
        if row is None:
            return
        self._finish(row.game_id)

    def _finish(self, game_id):
        if self._decided:
            return
        self._decided = True
        self.destroy()
        self.on_result(game_id)


def bytes_to_texture(data):
    loader = GdkPixbuf.PixbufLoader()
    loader.write(data)
    loader.close()
    pixbuf = loader.get_pixbuf()
    return Gdk.Texture.new_for_pixbuf(pixbuf)


class ImagePickerDialog(Adw.Window):
    """Shows a thumbnail gallery of every available cover image for a game
    and lets the user pick exactly which one to use."""

    MAX_IMAGES = 40

    def __init__(self, parent, game_display_name, images, cover_type, on_result):
        super().__init__(transient_for=parent, modal=True,
                          title=f"Choose cover for {game_display_name}")
        self.on_result = on_result
        self.images = images[: self.MAX_IMAGES]
        self.cover_type = cover_type
        self.selected_url = None
        self._decided = False
        self.set_default_size(680, 620)

        # Thumbnail preview size = exact target resolution scaled down 1/3,
        # so the aspect ratio matches precisely: 600x900 or 460x215.
        if cover_type == "vertical":
            self.thumb_w, self.thumb_h = 200, 400  # 600x900 / 3
        else:
            self.thumb_w, self.thumb_h = 153, 72  # 460x215 / 3 (rounded)

        toolbar = Adw.ToolbarView()
        header = Adw.HeaderBar()
        toolbar.add_top_bar(header)

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        outer.set_margin_top(12)
        outer.set_margin_bottom(12)
        outer.set_margin_start(12)
        outer.set_margin_end(12)

        count_label = Gtk.Label(
            label=(f"{len(images)} images found"
                   + (f" (showing first {self.MAX_IMAGES})" if len(images) > self.MAX_IMAGES else "")),
            xalign=0,
        )
        outer.append(count_label)

        scroller = Gtk.ScrolledWindow(vexpand=True)
        self.flowbox = Gtk.FlowBox()
        self.flowbox.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.flowbox.set_max_children_per_line(3 if cover_type == "vertical" else 4)
        self.flowbox.set_homogeneous(False)
        self.flowbox.set_row_spacing(8)
        self.flowbox.set_column_spacing(8)
        self.flowbox.connect("child-activated", self.on_child_activated)
        self.flowbox.connect("selected-children-changed", self.on_selection_changed)
        scroller.set_child(self.flowbox)
        outer.append(scroller)

        btn_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        skip_btn = Gtk.Button(label="Skip this game")
        skip_btn.connect("clicked", lambda _b: self._finish(None))
        btn_row.append(skip_btn)

        self.use_btn = Gtk.Button(label="Use Selected Image")
        self.use_btn.add_css_class("suggested-action")
        self.use_btn.set_hexpand(True)
        self.use_btn.set_sensitive(False)
        self.use_btn.connect("clicked", self.on_use_clicked)
        btn_row.append(self.use_btn)
        outer.append(btn_row)

        toolbar.set_content(outer)
        self.set_content(toolbar)

        self.connect("close-request", lambda _w: self._finish(None) or False)

        self._populate()

    def _populate(self):
        for image in self.images:
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
            box.set_size_request(self.thumb_w, self.thumb_h)
            box.set_halign(Gtk.Align.CENTER)
            box.set_valign(Gtk.Align.CENTER)
            box.set_hexpand(False)
            box.set_vexpand(False)
            picture = Gtk.Picture()
            picture.set_content_fit(Gtk.ContentFit.COVER)
            picture.set_size_request(self.thumb_w, self.thumb_h)
            picture.set_halign(Gtk.Align.CENTER)
            picture.set_valign(Gtk.Align.CENTER)
            picture.set_hexpand(False)
            picture.set_vexpand(False)
            box.append(picture)

            dims_label = Gtk.Label(label=f"{image.get('width')}x{image.get('height')}")
            dims_label.add_css_class("dim-label")
            dims_label.add_css_class("caption")
            box.append(dims_label)
            box.image_url = image["url"]
            box.picture = picture
            self.flowbox.append(box)

            run_async(lambda img=image: core.download_bytes(img["thumb"]),
                      lambda data, err, pic=picture: self._on_thumb_loaded(pic, data, err))

    def _on_thumb_loaded(self, picture, data, err):
        if err is not None or data is None:
            return
        try:
            texture = bytes_to_texture(data)
            picture.set_paintable(texture)
        except GLib.Error:
            pass

    def on_selection_changed(self, flowbox):
        self.use_btn.set_sensitive(bool(flowbox.get_selected_children()))

    def on_child_activated(self, _flowbox, _child):
        self.on_use_clicked(None)

    def on_use_clicked(self, _btn):
        child = self.flowbox.get_selected_children()
        if not child:
            return
        box = child[0].get_child()
        self._finish(box.image_url)

    def _finish(self, url):
        if self._decided:
            return
        self._decided = True
        self.destroy()
        self.on_result(url)



class MainWindow(Adw.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title="Lutris Cover Art Downloader")
        self.set_default_size(560, 640)

        self.api_key = core.load_api_key()
        self.cover_type = "vertical"  # or "banner"
        self.games = []
        self.download_queue = []
        self.queue_total = 0

        toolbar = Adw.ToolbarView()
        header = Adw.HeaderBar()
        toolbar.add_top_bar(header)

        self.cover_dropdown = Gtk.DropDown.new_from_strings(
            ["Vertical (600x900)", "Banner (460x215)"]
        )
        self.cover_dropdown.connect("notify::selected", self.on_cover_type_changed)
        header.pack_start(self.cover_dropdown)

        rescan_btn = Gtk.Button(icon_name="view-refresh-symbolic", tooltip_text="Rescan library")
        rescan_btn.connect("clicked", lambda _b: self.scan_library())
        header.pack_end(rescan_btn)

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        content.set_margin_top(8)
        content.set_margin_bottom(8)
        content.set_margin_start(8)
        content.set_margin_end(8)

        select_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        select_missing_btn = Gtk.Button(label="Select all missing")
        select_missing_btn.connect("clicked", lambda _b: self.select_missing())
        select_row.append(select_missing_btn)
        select_none_btn = Gtk.Button(label="Select none")
        select_none_btn.connect("clicked", lambda _b: self.select_none())
        select_row.append(select_none_btn)
        content.append(select_row)

        scroller = Gtk.ScrolledWindow(vexpand=True)
        self.listbox = Gtk.ListBox()
        self.listbox.add_css_class("boxed-list")
        scroller.set_child(self.listbox)
        content.append(scroller)

        self.status_label = Gtk.Label(label="Scanning library...", xalign=0)
        content.append(self.status_label)

        self.progress = Gtk.ProgressBar(visible=False)
        content.append(self.progress)

        bottom_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.restart_switch_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.restart_switch_row.append(Gtk.Label(label="Restart Lutris when done"))
        self.restart_switch = Gtk.Switch(active=True, valign=Gtk.Align.CENTER)
        self.restart_switch_row.append(self.restart_switch)
        bottom_row.append(self.restart_switch_row)

        download_btn = Gtk.Button(label="Download Covers for Selected")
        download_btn.add_css_class("suggested-action")
        download_btn.set_hexpand(True)
        download_btn.connect("clicked", self.on_download_clicked)
        bottom_row.append(download_btn)
        content.append(bottom_row)

        toolbar.set_content(content)
        self.set_content(toolbar)

        GLib.idle_add(self.scan_library)

    # -- library scanning -------------------------------------------------

    def scan_library(self):
        self.status_label.set_label("Scanning Lutris library...")
        run_async(core.list_games, self.on_scanned)

    def on_scanned(self, games, err):
        if err is not None:
            self.status_label.set_label(f"Error: {err}")
            return
        self.games = games
        self._rebuild_rows()
        self.status_label.set_label(f"Found {len(games)} games.")

    def _rebuild_rows(self):
        child = self.listbox.get_first_child()
        while child is not None:
            nxt = child.get_next_sibling()
            self.listbox.remove(child)
            child = nxt
        for game in self.games:
            row = GameRow(game, self.cover_type)
            self.listbox.append(row)

    def on_cover_type_changed(self, _dropdown, _pspec):
        self.cover_type = "vertical" if self.cover_dropdown.get_selected() == 0 else "banner"
        self._rebuild_rows()

    def select_missing(self):
        for row in self._rows():
            has_cover = row.game["has_banner"] if self.cover_type == "banner" else row.game["has_cover"]
            row.set_selected(not has_cover)

    def select_none(self):
        for row in self._rows():
            row.set_selected(False)

    def _rows(self):
        row = self.listbox.get_first_child()
        while row is not None:
            game_row = row.get_child()  # unwrap the auto-added Gtk.ListBoxRow
            if game_row is not None:
                yield game_row
            row = row.get_next_sibling()

    # -- download flow ------------------------------------------------------

    def on_download_clicked(self, _btn):
        selected = [r.game for r in self._rows() if r.is_selected()]
        if not selected:
            self.status_label.set_label("No games selected.")
            return

        if not self.api_key:
            ApiKeyDialog(self, self._start_download_with_key_bound(selected)).present()
            return

        self._start_download(selected)

    def _start_download_with_key_bound(self, selected):
        def on_key_ready(key):
            self.api_key = key
            self._start_download(selected)
        return on_key_ready

    def _start_download(self, selected):
        self.download_queue = list(selected)
        self.queue_total = len(selected)
        self.progress.set_visible(True)
        self.progress.set_fraction(0)
        self._process_next()

    def _process_next(self):
        if not self.download_queue:
            self._finish_download()
            return

        remaining = len(self.download_queue)
        done_count = self.queue_total - remaining
        self.progress.set_fraction(done_count / self.queue_total if self.queue_total else 1)

        game = self.download_queue.pop(0)
        query = game["name"]
        self.status_label.set_label(f"Searching for {game['name']}... ({done_count + 1}/{self.queue_total})")

        run_async(lambda: core.search_game(query, self.api_key),
                  lambda results, err: self._on_search_done(game, results, err))

    def _on_search_done(self, game, results, err):
        if err is not None:
            self.status_label.set_label(f"Search failed for {game['name']}: {err}")
            self._process_next()
            return
        if not results:
            self.status_label.set_label(f"No results for {game['name']}, skipping.")
            self._process_next()
            return

        MatchPickerDialog(
            self, game["name"], game["name"], self.api_key,
            on_result=lambda game_id: self._on_match_chosen(game, game_id),
        ).present()

    def _on_match_chosen(self, game, game_id):
        if game_id is None:
            self.status_label.set_label(f"Skipped {game['name']}.")
            self._process_next()
            return

        self.status_label.set_label(f"Loading cover images for {game['name']}...")
        dims = core.get_query_dims(self.cover_type)

        run_async(lambda: core.get_grid_images(game_id, dims, self.api_key, self.cover_type),
                  lambda images, err: self._on_images_loaded(game, images, err))

    def _on_images_loaded(self, game, images, err):
        if err is not None:
            self.status_label.set_label(f"Failed to load images for {game['name']}: {err}")
            self._process_next()
            return
        if not images:
            self.status_label.set_label(f"No cover images available for {game['name']}.")
            self._process_next()
            return

        ImagePickerDialog(
            self, game["name"], images, self.cover_type,
            on_result=lambda url: self._on_image_chosen(game, url),
        ).present()

    def _on_image_chosen(self, game, url):
        if url is None:
            self.status_label.set_label(f"Skipped {game['name']}.")
            self._process_next()
            return

        self.status_label.set_label(f"Downloading cover for {game['name']}...")

        def work():
            data = core.download_bytes(url)
            return core.save_cover_bytes(data, game["slug"], self.cover_type)

        run_async(work, lambda path, err: self._on_download_done(game, path, err))

    def _on_download_done(self, game, path, err):
        if err is not None:
            self.status_label.set_label(f"Failed to download cover for {game['name']}: {err}")
        elif path is None:
            self.status_label.set_label(f"No cover image available for {game['name']}.")
        else:
            self.status_label.set_label(f"Saved cover for {game['name']}.")
        self._process_next()

    def _finish_download(self):
        self.progress.set_fraction(1)
        self.status_label.set_label("All done!")
        self.scan_library()

        if self.restart_switch.get_active():
            self.status_label.set_label("Restarting Lutris...")
            run_async(core.restart_lutris, lambda _r, _e: self.status_label.set_label("Done. Lutris restarted."))


class LutrisCoverDownloaderApp(Adw.Application):
    def __init__(self):
        super().__init__(application_id="io.ethembeldagli.lutriscoverdownloader.App")

    def do_activate(self):
        win = self.props.active_window
        if not win:
            win = MainWindow(self)
        win.present()


        first = self.listbox.get_row_at_index(0)
        if first is not None:
            self.listbox.select_row(first)

    def on_search_clicked(self, _widget):
        query = self.search_entry.get_text().strip()
        if query:
            self._run_search(query)

    def on_use_clicked(self, _btn):
        row = self.listbox.get_selected_row()
        if row is None:
            return
        self._finish(row.game_id)

    def _finish(self, game_id):
        if self._decided:
            return
        self._decided = True
        self.destroy()
        self.on_result(game_id)


def bytes_to_texture(data):
    loader = GdkPixbuf.PixbufLoader()
    loader.write(data)
    loader.close()
    pixbuf = loader.get_pixbuf()
    return Gdk.Texture.new_for_pixbuf(pixbuf)


class ImagePickerDialog(Adw.Window):
    """Shows a thumbnail gallery of every available cover image for a game
    and lets the user pick exactly which one to use."""

    MAX_IMAGES = 40

    def __init__(self, parent, game_display_name, images, cover_type, on_result):
        super().__init__(transient_for=parent, modal=True,
                          title=f"Choose cover for {game_display_name}")
        self.on_result = on_result
        self.images = images[: self.MAX_IMAGES]
        self.cover_type = cover_type
        self.selected_url = None
        self._decided = False
        self.set_default_size(680, 620)

        # Thumbnail preview size = exact target resolution scaled down 1/3,
        # so the aspect ratio matches precisely: 600x900 or 460x215.
        if cover_type == "vertical":
            self.thumb_w, self.thumb_h = 200, 400  # 600x900 / 3
        else:
            self.thumb_w, self.thumb_h = 153, 72  # 460x215 / 3 (rounded)

        toolbar = Adw.ToolbarView()
        header = Adw.HeaderBar()
        toolbar.add_top_bar(header)

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        outer.set_margin_top(12)
        outer.set_margin_bottom(12)
        outer.set_margin_start(12)
        outer.set_margin_end(12)

        count_label = Gtk.Label(
            label=(f"{len(images)} images found"
                   + (f" (showing first {self.MAX_IMAGES})" if len(images) > self.MAX_IMAGES else "")),
            xalign=0,
        )
        outer.append(count_label)

        scroller = Gtk.ScrolledWindow(vexpand=True)
        self.flowbox = Gtk.FlowBox()
        self.flowbox.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.flowbox.set_max_children_per_line(3 if cover_type == "vertical" else 4)
        self.flowbox.set_homogeneous(False)
        self.flowbox.set_row_spacing(8)
        self.flowbox.set_column_spacing(8)
        self.flowbox.connect("child-activated", self.on_child_activated)
        self.flowbox.connect("selected-children-changed", self.on_selection_changed)
        scroller.set_child(self.flowbox)
        outer.append(scroller)

        btn_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        skip_btn = Gtk.Button(label="Skip this game")
        skip_btn.connect("clicked", lambda _b: self._finish(None))
        btn_row.append(skip_btn)

        self.use_btn = Gtk.Button(label="Use Selected Image")
        self.use_btn.add_css_class("suggested-action")
        self.use_btn.set_hexpand(True)
        self.use_btn.set_sensitive(False)
        self.use_btn.connect("clicked", self.on_use_clicked)
        btn_row.append(self.use_btn)
        outer.append(btn_row)

        toolbar.set_content(outer)
        self.set_content(toolbar)

        self.connect("close-request", lambda _w: self._finish(None) or False)

        self._populate()

    def _populate(self):
        for image in self.images:
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
            box.set_size_request(self.thumb_w, self.thumb_h)
            box.set_halign(Gtk.Align.CENTER)
            box.set_valign(Gtk.Align.CENTER)
            box.set_hexpand(False)
            box.set_vexpand(False)
            picture = Gtk.Picture()
            picture.set_content_fit(Gtk.ContentFit.COVER)
            picture.set_size_request(self.thumb_w, self.thumb_h)
            picture.set_halign(Gtk.Align.CENTER)
            picture.set_valign(Gtk.Align.CENTER)
            picture.set_hexpand(False)
            picture.set_vexpand(False)
            box.append(picture)

            dims_label = Gtk.Label(label=f"{image.get('width')}x{image.get('height')}")
            dims_label.add_css_class("dim-label")
            dims_label.add_css_class("caption")
            box.append(dims_label)
            box.image_url = image["url"]
            box.picture = picture
            self.flowbox.append(box)

            run_async(lambda img=image: core.download_bytes(img["thumb"]),
                      lambda data, err, pic=picture: self._on_thumb_loaded(pic, data, err))

    def _on_thumb_loaded(self, picture, data, err):
        if err is not None or data is None:
            return
        try:
            texture = bytes_to_texture(data)
            picture.set_paintable(texture)
        except GLib.Error:
            pass

    def on_selection_changed(self, flowbox):
        self.use_btn.set_sensitive(bool(flowbox.get_selected_children()))

    def on_child_activated(self, _flowbox, _child):
        self.on_use_clicked(None)

    def on_use_clicked(self, _btn):
        child = self.flowbox.get_selected_children()
        if not child:
            return
        box = child[0].get_child()
        self._finish(box.image_url)

    def _finish(self, url):
        if self._decided:
            return
        self._decided = True
        self.destroy()
        self.on_result(url)



class MainWindow(Adw.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title="Lutris Cover Art Downloader")
        self.set_default_size(560, 640)

        self.api_key = core.load_api_key()
        self.cover_type = "vertical"  # or "banner"
        self.games = []
        self.download_queue = []
        self.queue_total = 0

        toolbar = Adw.ToolbarView()
        header = Adw.HeaderBar()
        toolbar.add_top_bar(header)

        self.cover_dropdown = Gtk.DropDown.new_from_strings(
            ["Vertical (600x900)", "Banner (460x215)"]
        )
        self.cover_dropdown.connect("notify::selected", self.on_cover_type_changed)
        header.pack_start(self.cover_dropdown)

        rescan_btn = Gtk.Button(icon_name="view-refresh-symbolic", tooltip_text="Rescan library")
        rescan_btn.connect("clicked", lambda _b: self.scan_library())
        header.pack_end(rescan_btn)

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        content.set_margin_top(8)
        content.set_margin_bottom(8)
        content.set_margin_start(8)
        content.set_margin_end(8)

        select_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        select_missing_btn = Gtk.Button(label="Select all missing")
        select_missing_btn.connect("clicked", lambda _b: self.select_missing())
        select_row.append(select_missing_btn)
        select_none_btn = Gtk.Button(label="Select none")
        select_none_btn.connect("clicked", lambda _b: self.select_none())
        select_row.append(select_none_btn)
        content.append(select_row)

        scroller = Gtk.ScrolledWindow(vexpand=True)
        self.listbox = Gtk.ListBox()
        self.listbox.add_css_class("boxed-list")
        scroller.set_child(self.listbox)
        content.append(scroller)

        self.status_label = Gtk.Label(label="Scanning library...", xalign=0)
        content.append(self.status_label)

        self.progress = Gtk.ProgressBar(visible=False)
        content.append(self.progress)

        bottom_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.restart_switch_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.restart_switch_row.append(Gtk.Label(label="Restart Lutris when done"))
        self.restart_switch = Gtk.Switch(active=True, valign=Gtk.Align.CENTER)
        self.restart_switch_row.append(self.restart_switch)
        bottom_row.append(self.restart_switch_row)

        download_btn = Gtk.Button(label="Download Covers for Selected")
        download_btn.add_css_class("suggested-action")
        download_btn.set_hexpand(True)
        download_btn.connect("clicked", self.on_download_clicked)
        bottom_row.append(download_btn)
        content.append(bottom_row)

        toolbar.set_content(content)
        self.set_content(toolbar)

        GLib.idle_add(self.scan_library)

    # -- library scanning -------------------------------------------------

    def scan_library(self):
        self.status_label.set_label("Scanning Lutris library...")
        run_async(core.list_games, self.on_scanned)

    def on_scanned(self, games, err):
        if err is not None:
            self.status_label.set_label(f"Error: {err}")
            return
        self.games = games
        self._rebuild_rows()
        self.status_label.set_label(f"Found {len(games)} games.")

    def _rebuild_rows(self):
        child = self.listbox.get_first_child()
        while child is not None:
            nxt = child.get_next_sibling()
            self.listbox.remove(child)
            child = nxt
        for game in self.games:
            row = GameRow(game, self.cover_type)
            self.listbox.append(row)

    def on_cover_type_changed(self, _dropdown, _pspec):
        self.cover_type = "vertical" if self.cover_dropdown.get_selected() == 0 else "banner"
        self._rebuild_rows()

    def select_missing(self):
        for row in self._rows():
            has_cover = row.game["has_banner"] if self.cover_type == "banner" else row.game["has_cover"]
            row.set_selected(not has_cover)

    def select_none(self):
        for row in self._rows():
            row.set_selected(False)

    def _rows(self):
        row = self.listbox.get_first_child()
        while row is not None:
            game_row = row.get_child()  # unwrap the auto-added Gtk.ListBoxRow
            if game_row is not None:
                yield game_row
            row = row.get_next_sibling()

    # -- download flow ------------------------------------------------------

    def on_download_clicked(self, _btn):
        selected = [r.game for r in self._rows() if r.is_selected()]
        if not selected:
            self.status_label.set_label("No games selected.")
            return

        if not self.api_key:
            ApiKeyDialog(self, self._start_download_with_key_bound(selected)).present()
            return

        self._start_download(selected)

    def _start_download_with_key_bound(self, selected):
        def on_key_ready(key):
            self.api_key = key
            self._start_download(selected)
        return on_key_ready

    def _start_download(self, selected):
        self.download_queue = list(selected)
        self.queue_total = len(selected)
        self.progress.set_visible(True)
        self.progress.set_fraction(0)
        self._process_next()

    def _process_next(self):
        if not self.download_queue:
            self._finish_download()
            return

        remaining = len(self.download_queue)
        done_count = self.queue_total - remaining
        self.progress.set_fraction(done_count / self.queue_total if self.queue_total else 1)

        game = self.download_queue.pop(0)
        query = game["name"]
        self.status_label.set_label(f"Searching for {game['name']}... ({done_count + 1}/{self.queue_total})")

        run_async(lambda: core.search_game(query, self.api_key),
                  lambda results, err: self._on_search_done(game, results, err))

    def _on_search_done(self, game, results, err):
        if err is not None:
            self.status_label.set_label(f"Search failed for {game['name']}: {err}")
            self._process_next()
            return
        if not results:
            self.status_label.set_label(f"No results for {game['name']}, skipping.")
            self._process_next()
            return

        MatchPickerDialog(
            self, game["name"], game["name"], self.api_key,
            on_result=lambda game_id: self._on_match_chosen(game, game_id),
        ).present()

    def _on_match_chosen(self, game, game_id):
        if game_id is None:
            self.status_label.set_label(f"Skipped {game['name']}.")
            self._process_next()
            return

        self.status_label.set_label(f"Loading cover images for {game['name']}...")
        dims = core.get_query_dims(self.cover_type)

        run_async(lambda: core.get_grid_images(game_id, dims, self.api_key, self.cover_type),
                  lambda images, err: self._on_images_loaded(game, images, err))

    def _on_images_loaded(self, game, images, err):
        if err is not None:
            self.status_label.set_label(f"Failed to load images for {game['name']}: {err}")
            self._process_next()
            return
        if not images:
            self.status_label.set_label(f"No cover images available for {game['name']}.")
            self._process_next()
            return

        ImagePickerDialog(
            self, game["name"], images, self.cover_type,
            on_result=lambda url: self._on_image_chosen(game, url),
        ).present()

    def _on_image_chosen(self, game, url):
        if url is None:
            self.status_label.set_label(f"Skipped {game['name']}.")
            self._process_next()
            return

        self.status_label.set_label(f"Downloading cover for {game['name']}...")

        def work():
            data = core.download_bytes(url)
            return core.save_cover_bytes(data, game["slug"], self.cover_type)

        run_async(work, lambda path, err: self._on_download_done(game, path, err))

    def _on_download_done(self, game, path, err):
        if err is not None:
            self.status_label.set_label(f"Failed to download cover for {game['name']}: {err}")
        elif path is None:
            self.status_label.set_label(f"No cover image available for {game['name']}.")
        else:
            self.status_label.set_label(f"Saved cover for {game['name']}.")
        self._process_next()

    def _finish_download(self):
        self.progress.set_fraction(1)
        self.status_label.set_label("All done!")
        self.scan_library()

        if self.restart_switch.get_active():
            self.status_label.set_label("Restarting Lutris...")
            run_async(core.restart_lutris, lambda _r, _e: self.status_label.set_label("Done. Lutris restarted."))


class LutrisCoverDownloaderApp(Adw.Application):
    def __init__(self):
        super().__init__(application_id="io.ethembeldagli.lutriscoverdownloader.App")

    def do_activate(self):
        win = self.props.active_window
        if not win:
            win = MainWindow(self)
        win.present()
