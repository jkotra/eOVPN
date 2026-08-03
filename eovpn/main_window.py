import logging
from time import sleep
from .settings_window import SettingsWindow
from .connection_manager import NetworkManager, OpenVPN3
from gi.repository import Gtk, Gio, GLib, Gdk, Adw
from .ip_lookup.lookup import Lookup
from .utils import ovpn_is_auth_required
import os
import gettext
import webbrowser
import threading

from .eovpn_base import Base, StorageItem
logger = logging.getLogger(__name__)


class MainWindow(Base, Gtk.Builder):
    def __init__(self, app):
        super().__init__()
        Gtk.Builder.__init__(self)
        self.app = app
        
        if self.get_setting(self.SETTING.DARK_THEME) is True:
            gtk_settings = Gtk.Settings().get_default()
            gtk_settings.set_property("gtk-application-prefer-dark-theme", True)

        self.add_from_resource(self.EOVPN_GRESOURCE_PREFIX + "/ui/" + "main.ui")
        self.window = self.get_object("main_window")
        self.window.set_title("eOVPN")
        self.window.set_icon_name(self.APP_ID)

        self.toast_overlay = Adw.ToastOverlay()

        self.app.add_window(self.window)
        self.store(StorageItem.MAIN_WINDOW, self.window)
        self.store("main_window_instance", self)

        self.selected_row = None
        self.manual_disconnect = False
        self.selected_config = None
        self.connected_cursor = None
        self.signals = Signals()
        self.latencies = {}
        self.sort_by_speed_active = False

        ###########################################################
        # Initialize and setup Connection Manager (CM)
        ###########################################################
        preferred = self.get_setting(self.SETTING.MANAGER)
        self.store("CM", {"name": preferred,
                        "instance": NetworkManager(self.on_connection_event)
                        if preferred == "networkmanager"
                        else OpenVPN3(self.on_connection_event)})
        self.store("on_connection_event", self.on_connection_event)
        self.CM = lambda: self.retrieve("CM")["instance"]

        self.lookup = Lookup()

    def get_selected_config(self) -> str:
        try:
            row = self.list_box.get_selected_row().get_child()
            self.selected_row = row
            label = row.get_child_at(0, 0).get_label()
            edit_action = row.get_child_at(2, 0)
            edit_action.set_visible(True)
            return label
        except AttributeError:
            return None

    def row_changed(self, listbox, row):
        try:
            self.selected_row.get_child_at(2, 0).set_visible(False)
        except:
            pass
        if (selected := self.get_selected_config()) is not None:
            if self.get_setting(self.SETTING.REQ_AUTH) is True:
                if ovpn_is_auth_required(os.path.join(self.EOVPN_OVPN_CONFIG_DIR, selected)) and self.get_setting(self.SETTING.AUTH_USER) is None:
                    self.connect_btn.set_sensitive(False)
                    self.connect_btn.set_tooltip_text(gettext.gettext("Authentication Required!"))
                    return

        self.connect_btn.set_sensitive(True)
        self.connect_btn.set_tooltip_text("")

    def generic_critical_error_dialog(self, error_message):

        def cb(dialog, res):
            Gio.Application.quit(self.app)

        dlg = Gtk.MessageDialog()
        dlg.set_transient_for(self.window)
        dlg.set_modal(True)

        dlg.set_property("message-type", Gtk.MessageType.ERROR)
        dlg.set_property("use-markup", True)
        dlg.set_property("text", "<span weight='bold'>Error</span>")
        dlg.connect("response", cb)

        btn = dlg.add_button("Exit", 1)
        btn.add_css_class("destructive-action")

        box = dlg.get_message_area()
        for msg in error_message:
            box.append(Gtk.Label.new(msg))
        dlg.show()

    def setup(self):

        ###########################################################
        # Declare boxes for each major component.
        ###########################################################
        self.box = Gtk.Box.new(Gtk.Orientation.VERTICAL, 0) #top most box

        self.inner_left = Gtk.Box.new(Gtk.Orientation.VERTICAL, 0) #ListBox
        self.inner_right = Gtk.Box.new(Gtk.Orientation.VERTICAL, 0) #Info
        self.paned = Gtk.Paned.new(Gtk.Orientation.HORIZONTAL)

        def update_layout():
            if (self.get_setting(self.SETTING.LAYOUT) == "card-h"):
                self.paned.set_orientation(Gtk.Orientation.HORIZONTAL)
                self.inner_left.set_size_request(200, -1)
                self.window.set_default_size(800, 400)
            else:
                self.paned.set_orientation(Gtk.Orientation.VERTICAL)
                self.inner_left.set_size_request(-1, 100)
                self.window.set_default_size(400, 800)
        
        update_layout()
        self.paned.set_start_child(self.inner_left)
        self.paned.set_end_child(self.inner_right)


        ###########################################################
        # Left Box
        ###########################################################

        viewport = Gtk.Viewport.new()
        viewport.set_vexpand(True)
        viewport.set_hexpand(True)

        self.scrolled_window = Gtk.ScrolledWindow().new()

        self.list_box = Gtk.ListBox.new()
        self.list_box.connect("row-selected", self.row_changed)
        self.store(StorageItem.LISTBOX, self.list_box)

        #add placeholder
        v_box = Gtk.Box.new(Gtk.Orientation.VERTICAL, 4)
        v_box.set_valign(Gtk.Align.CENTER)
        lbl = Gtk.Label.new(gettext.gettext("No Configs Added!"))
        lbl.add_css_class("bold")
        btn = Gtk.Button.new_with_label(gettext.gettext("Open Settings"))
        btn.add_css_class("suggested-action")
        btn.set_valign(Gtk.Align.START)
        btn.set_halign(Gtk.Align.CENTER)
        btn.connect("clicked", lambda x: SettingsWindow().show())
        v_box.append(lbl)
        v_box.append(btn)
        self.list_box.set_placeholder(v_box)

        self.scrolled_window.set_child(viewport)
        viewport.set_child(self.list_box)
        self.load_only()

        # Set up sort function
        self.list_box.set_sort_func(self.list_box_sort_func)

        # Pro Features Toolbar
        self.pro_box = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, 6)
        self.pro_box.set_margin_start(10)
        self.pro_box.set_margin_end(10)
        self.pro_box.set_margin_top(6)
        self.pro_box.set_margin_bottom(6)
        self.pro_box.add_css_class("linked")

        self.speed_test_btn = Gtk.Button.new_with_label(gettext.gettext("Speed Test"))
        self.speed_test_btn.set_tooltip_text(gettext.gettext("Test latency of all VPN servers"))
        self.speed_test_btn.connect("clicked", lambda b: self.trigger_speed_test())

        self.sort_btn = Gtk.ToggleButton.new_with_label(gettext.gettext("Sort"))
        self.sort_btn.set_tooltip_text(gettext.gettext("Sort servers by lowest latency"))
        self.sort_btn.connect("toggled", self.on_sort_toggled)

        self.fastest_btn = Gtk.Button.new_with_label(gettext.gettext("Select Fastest"))
        self.fastest_btn.set_tooltip_text(gettext.gettext("Auto-select server with the lowest latency"))
        self.fastest_btn.connect("clicked", self.select_fastest)

        self.pro_box.append(self.speed_test_btn)
        self.pro_box.append(self.sort_btn)
        self.pro_box.append(self.fastest_btn)

        self.inner_left.append(self.pro_box)

        self.inner_left.append(self.scrolled_window)

        ###########################################################
        # Right Box
        ###########################################################
        img = Gtk.Picture.new()
        img.set_halign(Gtk.Align.CENTER)
        img.set_valign(Gtk.Align.CENTER)
        img.add_css_class("rounded")
        self.store(StorageItem.FLAG, img)
        if self.get_setting(self.SETTING.SHOW_FLAG) is False:
            img.hide()
        self.inner_right.append(img)

        #this contains - OpenVPN info
        h_box = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, 6)
        h_box.set_halign(Gtk.Align.CENTER)
        self.ip_text = Gtk.Label.new(gettext.gettext("IP: "))
        self.ip_addr = Gtk.Label.new("0.0.0.0")
        self.ip_addr.set_valign(Gtk.Align.CENTER)
        self.ip_addr.add_css_class("ip_text")
        self.ip_addr.set_vexpand(True)
        cpy_btn = Gtk.Button.new_from_icon_name("edit-copy-symbolic")
        cpy_btn.set_valign(Gtk.Align.CENTER)
        cpy_btn.set_halign(Gtk.Align.CENTER)
        cpy_btn.set_tooltip_text("Copy")
        cpy_btn.add_css_class("flat")

        h_box.append(self.ip_text)
        h_box.append(self.ip_addr)
        h_box.append(cpy_btn)

        self.inner_right.append(h_box)

        # Traffic & Speed panel
        self.traffic_box = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, 12)
        self.traffic_box.set_halign(Gtk.Align.CENTER)
        self.traffic_box.set_margin_top(8)
        self.traffic_box.set_margin_bottom(8)

        self.dl_speed_label = Gtk.Label.new("")
        self.dl_speed_label.set_markup("⬇️ <span weight='bold'>0.0 B/s</span>")

        self.ul_speed_label = Gtk.Label.new("")
        self.ul_speed_label.set_markup("⬆️ <span weight='bold'>0.0 B/s</span>")

        self.total_traffic_label = Gtk.Label.new("")
        self.total_traffic_label.set_markup("📊 <span weight='bold'>0 B</span>")

        self.traffic_box.append(self.dl_speed_label)
        self.traffic_box.append(self.ul_speed_label)
        self.traffic_box.append(self.total_traffic_label)

        self.inner_right.append(self.traffic_box)

        #TODO: define it better!
        self.psh = None

        self.connect_box = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, 6)
        self.connect_box.set_valign(Gtk.Align.END)
        self.connect_box.add_css_class("m-10")
        self.connect_btn = Gtk.Button().new_with_label(gettext.gettext("Connect"))
        self.connect_btn.set_valign(Gtk.Align.FILL)
        self.connect_btn.set_hexpand(True)
        self.connect_btn.set_vexpand(True)
        
        self.connect_box.append(self.connect_btn)

        self.pause_resume_btn = Gtk.Button().new_from_icon_name("media-playback-pause-symbolic")
        self.pause_resume_btn.set_valign(Gtk.Align.END)
        self.pause_resume_btn.set_vexpand(True)
        self.pause_resume_btn.set_visible(False)

        self.connect_btn.connect("clicked", self.signals.connect, self.get_selected_config)

        #Connects to pause()
        self.swap_pause_btn_signal_resume_to_pause()

        self.connect_box.append(self.pause_resume_btn)

        self.inner_right.append(self.connect_box)

        ###########################################################
        # Bottom Progress Bar
        ###########################################################
        self.progress_bar = Gtk.ProgressBar.new()
        
        #Initial connection check on startup + Progress bar update + signal connects
        if self.CM().status():
            self.connect_btn.set_label(gettext.gettext("Disconnect"))
            self.connect_btn.add_css_class("destructive-action")
            self.progress_bar.add_css_class("progress-full-green")
            self.progress_bar.set_fraction(1.0)
        else:
            self.progress_bar.add_css_class("progress-yellow")

        def open_about_dialog(widget, data):
            about = Gtk.AboutDialog.new()
            about.set_logo_icon_name(self.APP_ID)
            about.set_program_name(self.APP_NAME)
            about.set_authors([self.AUTHOR])
            about.set_artists([self.AUTHOR])
            about.set_copyright(self.AUTHOR)
            about.set_license_type(Gtk.License.LGPL_3_0)
            about.set_version(self.APP_VERSION)
            website = self.AUTHOR_WEBSITE
            if not website.startswith("http"):
                website = "https://" + website
            about.set_website(website)
            about.set_system_information("Flatpak: \t {}\nCommit: \t {}".format("true" if os.getenv("FLATPAK_ID") is not None else "false", self.APP_COMMIT))
            about.set_transient_for(self.window)
            about.set_modal(True)
            about.show()

        def open_ks(widget, data):
            builder = Gtk.Builder()
            builder.add_from_resource(self.EOVPN_GRESOURCE_PREFIX + "/ui/keyboard_shortcuts.ui")
            window = builder.get_object("shortcuts_window")
            window.set_transient_for(self.window)
            window.set_modal(True)
            window.show()

        def on_layout_update(action, value):
            logger.info(value)
            action.set_state(value)
            self.set_setting(self.SETTING.LAYOUT, str(value).replace("'", ""))
            update_layout()


        action = Gio.SimpleAction().new_stateful(
            "radiogroup",
            GLib.VariantType.new("s"),
            GLib.Variant("s", self.get_setting(self.SETTING.LAYOUT))
        )
        action.connect("activate", on_layout_update)
        self.app.add_action(action)

        action = Gio.SimpleAction().new("update", None)
        action.connect("activate", lambda x, d: self.validate_and_load(self.spinner) )
        self.app.add_action(action)

        action = Gio.SimpleAction().new("about", None)
        action.connect("activate", open_about_dialog)
        self.app.add_action(action)

        action = Gio.SimpleAction().new("donate", None)
        action.connect("activate", lambda x, d: webbrowser.open(self.AUTHOR_DONATE))
        self.app.add_action(action)

        action = Gio.SimpleAction().new("keyboard_shortcuts", None)
        action.connect("activate", open_ks)
        self.app.add_action(action)

        action = Gio.SimpleAction().new("settings", None)
        action.connect("activate", lambda x, d: SettingsWindow().show())
        self.app.add_action(action)

        #add shortcuts
        self.app.set_accels_for_action("app.keyboard_shortcuts", ["<Primary>question"])
        self.app.set_accels_for_action("app.settings", ["<Primary>S"])
        self.app.set_accels_for_action("app.update", ["<Primary>U"])
        self.app.set_accels_for_action("app.about", ["<Primary>A"])
        
        action = Gio.SimpleAction.new("connect", None)
        action.connect('activate', self.signals.connect_via_ks, self.get_selected_config)
        self.app.add_action(action)
        self.app.set_accels_for_action("app.connect", ["<Primary>C", "<Primary>D"])


        menu = Gio.Menu()
        layout_menu = Gio.Menu()
        item = Gio.MenuItem.new(gettext.gettext("Vertical"), "card-v")
        item.set_action_and_target_value("app.radiogroup", GLib.Variant.new_string("card-v"))
        layout_menu.append_item(item)

        item = Gio.MenuItem.new(gettext.gettext("Horizontal"), "card-h")
        item.set_action_and_target_value("app.radiogroup", GLib.Variant.new_string("card-h"))
        layout_menu.append_item(item)
        

        menu.append(gettext.gettext("Update"), "app.update")
        menu.append(gettext.gettext("Settings"), "app.settings")
        menu.append(gettext.gettext("Keyboard Shortcuts"), "app.keyboard_shortcuts")
        menu.append_submenu(gettext.gettext("Layout"), layout_menu)
        menu.append(gettext.gettext("Donate"), "app.donate")
        menu.append(gettext.gettext("About"), "app.about")
        popover = Gtk.PopoverMenu.new_from_model(menu)


        header_bar = self.get_object("header_bar")

        menu_button = Gtk.MenuButton.new()
        menu_button.set_icon_name("open-menu-symbolic")
        menu_button.set_popover(popover)
        header_bar.pack_end(menu_button)

        # Dedicated Sponsor/Donate Button (❤️)
        self.donate_btn_header = Gtk.Button.new_from_icon_name("emblem-favorite-symbolic")
        self.donate_btn_header.set_tooltip_text(gettext.gettext("Sponsor & Donate (حمایت مالی)"))
        self.donate_btn_header.add_css_class("flat")
        self.donate_btn_header.connect("clicked", lambda b: webbrowser.open(self.AUTHOR_DONATE))
        header_bar.pack_end(self.donate_btn_header)

        self.spinner = Gtk.Spinner()
        header_bar.pack_end(self.spinner)

        if (cur := self.get_setting(self.SETTING.LAST_CONNECTED_CURSOR)) != -1:
            try:
                self.list_box.select_row(self.retrieve(StorageItem.LISTBOX_ROWS)[cur])
                adj = self.scrolled_window.get_vadjustment()
                v = self.get_setting(self.SETTING.LISTBOX_V_ADJUST)
                adj.set_value(v)
                adj.set_upper(v)
                adj.set_lower(v+1)
            except Exception as e:
                logger.error(e)
                pass

        #finally!
        self.box.append(self.paned)
        self.box.append(self.progress_bar)
        self.toast_overlay.set_child(self.box)
        self.window.set_child(self.toast_overlay)

        def copy_ip(btn: Gtk.Button):
            toast = Adw.Toast.new(gettext.gettext("IP Address copied to Clipboard!"))
            toast.set_timeout(1)
            Gdk.Display.get_default().get_clipboard().set(self.ip_addr.get_label())
            self.toast_overlay.add_toast(toast)

        cpy_btn.connect("clicked", copy_ip)

    def list_box_sort_func(self, row1, row2, *args):
        if not getattr(self, "sort_by_speed_active", False):
            # Sort alphabetically (default)
            try:
                file1 = row1.get_child().get_child_at(0, 0).get_label()
                file2 = row2.get_child().get_child_at(0, 0).get_label()
                return 1 if file1 > file2 else -1
            except Exception:
                return 0
        try:
            grid1 = row1.get_child()
            grid2 = row2.get_child()
            if not grid1 or not grid2:
                return 0
            file1 = grid1.get_child_at(0, 0).get_label()
            file2 = grid2.get_child_at(0, 0).get_label()
        except Exception:
            return 0

        rtt1 = self.latencies.get(file1, None)
        rtt2 = self.latencies.get(file2, None)

        if rtt1 is None and rtt2 is None:
            return 1 if file1 > file2 else -1
        if rtt1 is None:
            return 1
        if rtt2 is None:
            return -1

        if rtt1 < rtt2:
            return -1
        elif rtt1 > rtt2:
            return 1
        else:
            return 1 if file1 > file2 else -1

    def trigger_speed_test(self):
        if not getattr(self, "speed_test_btn", None) or not self.speed_test_btn.get_sensitive():
            return
        self.speed_test_btn.set_sensitive(False)
        self.speed_test_btn.set_label(gettext.gettext("Testing..."))
        self.spinner.start()

        def worker():
            from .speed_test import test_all_configs
            configs_list = self.retrieve(StorageItem.CONFIGS_LIST)
            latencies = test_all_configs(self.EOVPN_OVPN_CONFIG_DIR, configs_list)
            GLib.idle_add(self.on_speed_test_complete, latencies)

        th = threading.Thread(target=worker)
        th.daemon = True
        th.start()

    def on_speed_test_complete(self, latencies):
        self.latencies = latencies
        latency_labels = self.retrieve("latency_labels")

        for file, rtt in latencies.items():
            if file in latency_labels:
                label_widget = latency_labels[file]
                if rtt is not None:
                    if rtt < 100:
                        label_widget.set_markup(f"<span foreground='#2ec27e' weight='bold'>{rtt} ms</span>")
                    elif rtt < 250:
                        label_widget.set_markup(f"<span foreground='#e5a50a' weight='bold'>{rtt} ms</span>")
                    else:
                        label_widget.set_markup(f"<span foreground='#e01b24' weight='bold'>{rtt} ms</span>")
                else:
                    label_widget.set_markup("<span foreground='#e01b24' alpha='60%'>Error</span>")

        if self.sort_by_speed_active:
            self.list_box.invalidate_sort()

        self.speed_test_btn.set_sensitive(True)
        self.speed_test_btn.set_label(gettext.gettext("Speed Test"))
        self.spinner.stop()

        if getattr(self, "auto_select_after_test", False):
            self.auto_select_after_test = False
            self.select_fastest(None)

    def on_sort_toggled(self, button):
        self.sort_by_speed_active = button.get_active()
        if self.sort_by_speed_active:
            button.add_css_class("suggested-action")
            if not self.latencies:
                self.trigger_speed_test()
        else:
            button.remove_css_class("suggested-action")
        self.list_box.invalidate_sort()

    def select_fastest(self, button):
        if not self.latencies:
            self.auto_select_after_test = True
            self.trigger_speed_test()
            return

        valid_latencies = {k: v for k, v in self.latencies.items() if v is not None}
        if not valid_latencies:
            toast = Adw.Toast.new(gettext.gettext("No reachable servers found! Please run speed test."))
            self.toast_overlay.add_toast(toast)
            return

        fastest_file = min(valid_latencies, key=valid_latencies.get)

        configs_list = self.retrieve(StorageItem.CONFIGS_LIST)
        try:
            idx = configs_list.index(fastest_file)
            rows = self.retrieve(StorageItem.LISTBOX_ROWS)
            row_to_select = rows[idx]
            self.list_box.select_row(row_to_select)

            toast = Adw.Toast.new(gettext.gettext(f"Selected fastest server: {fastest_file} ({valid_latencies[fastest_file]} ms)"))
            self.toast_overlay.add_toast(toast)
        except Exception as e:
            logger.error(f"Error selecting fastest: {e}")

    def start_network_monitor(self):
        self.stop_network_monitor()
        self.last_rx = 0
        self.last_tx = 0
        import time as pytime
        self.last_time = pytime.time()
        self.network_monitor_id = GLib.timeout_add_seconds(1, self.update_network_speed)

    def stop_network_monitor(self):
        if hasattr(self, "network_monitor_id") and self.network_monitor_id:
            GLib.source_remove(self.network_monitor_id)
            self.network_monitor_id = None

    def update_network_speed(self):
        try:
            rx, tx = 0, 0
            if os.path.exists("/proc/net/dev"):
                with open("/proc/net/dev", "r") as f:
                    for line in f:
                        if ":" in line:
                            parts = line.split(":")
                            if len(parts) == 2:
                                if any(x in parts[0] for x in ["tun", "tap", "ovpn", "ppp", "wg"]):
                                    stats = parts[1].split()
                                    rx += int(stats[0])
                                    tx += int(stats[8])

            if rx == 0 and tx == 0:
                if os.path.exists("/proc/net/dev"):
                    with open("/proc/net/dev", "r") as f:
                        for line in f:
                            if ":" in line:
                                parts = line.split(":")
                                if len(parts) == 2:
                                    if "lo" not in parts[0]:
                                        stats = parts[1].split()
                                        rx += int(stats[0])
                                        tx += int(stats[8])

            import time as pytime
            now = pytime.time()
            dt = now - getattr(self, "last_time", now - 1.0)
            if dt <= 0:
                dt = 1.0

            last_rx = getattr(self, "last_rx", 0)
            last_tx = getattr(self, "last_tx", 0)

            if last_rx > 0 and last_tx > 0:
                dl_speed = (rx - last_rx) / dt
                ul_speed = (tx - last_tx) / dt

                def format_speed(bytes_per_sec):
                    if bytes_per_sec < 1024:
                        return f"{bytes_per_sec:.1f} B/s"
                    elif bytes_per_sec < 1024 * 1024:
                        return f"{bytes_per_sec / 1024:.1f} KB/s"
                    else:
                        return f"{bytes_per_sec / (1024 * 1024):.1f} MB/s"

                def format_size(bytes_total):
                    if bytes_total < 1024:
                        return f"{bytes_total} B"
                    elif bytes_total < 1024 * 1024:
                        return f"{bytes_total / 1024:.1f} KB"
                    elif bytes_total < 1024 * 1024 * 1024:
                        return f"{bytes_total / (1024 * 1024):.1f} MB"
                    else:
                        return f"{bytes_total / (1024 * 1024 * 1024):.1f} GB"

                self.dl_speed_label.set_markup(f"⬇️ <span weight='bold'>{format_speed(dl_speed)}</span>")
                self.ul_speed_label.set_markup(f"⬆️ <span weight='bold'>{format_speed(ul_speed)}</span>")
                self.total_traffic_label.set_markup(f"📊 <span weight='bold'>{format_size(rx + tx)}</span>")

            self.last_rx = rx
            self.last_tx = tx
            self.last_time = now
        except Exception as e:
            logger.error(f"Error in network monitor: {e}")

        return True

    def trigger_reconnect(self):
        selected = self.get_selected_config()
        if selected:
            logger.info(f"Auto-reconnecting to {selected}")
            self.signals.connect(None, self.get_selected_config)
        return False

    def update_set_ip_flag(self):
        self.spinner.start()
        if os.environ.get("FLATPAK_ID") is not None:
            sleep(1.25)
        self.lookup.update()
        self.retrieve(StorageItem.FLAG).set_pixbuf(self.get_country_pixbuf(self.lookup.country_code))
        self.ip_addr.set_label(self.lookup.ip)
        self.spinner.stop()

    
    def swap_pause_btn_signal_pause_to_resume(self):
        self.pause_resume_btn.set_property("icon-name", "media-playback-start-symbolic")
        if self.psh is not None:
            self.pause_resume_btn.disconnect(self.psh)
        self.psh = self.pause_resume_btn.connect("clicked", self.signals.resume, self.CM())
        self.update_ip_flag_async()
        
    def swap_pause_btn_signal_resume_to_pause(self):
        self.pause_resume_btn.set_property("icon-name", "media-playback-pause-symbolic")
        if self.psh is not None:
            self.pause_resume_btn.disconnect(self.psh)
        self.psh = self.pause_resume_btn.connect("clicked", self.signals.pause, self.CM())

    
    def on_connection_event(self, result, error=None):
        if error is not None:
            logger.error(error)
            self.send_error_notification(error)
            self.progress_bar.set_fraction(0)
            return

        if type(result) is list:
            if len(result) == 1:
                status = result[-1]

                if status == "pause":
                    self.progress_bar.remove_css_class("progress-full-green")
                    self.progress_bar.add_css_class("progress-orange")
                    self.swap_pause_btn_signal_pause_to_resume()
                    return

                elif status == "resume":
                    self.progress_bar.remove_css_class("progress-orange")
                    self.progress_bar.add_css_class("progress-full-green")
                    self.swap_pause_btn_signal_resume_to_pause()
                    return

            logger.info(self.progress_bar.get_fraction())
            prev = self.progress_bar.get_fraction()
            if prev < 0.95:
                self.progress_bar.set_fraction(prev + 0.35)
            return

        if result:
            self.start_network_monitor()
            self.was_connected = True
            self.update_ip_flag_async()
            self.connect_btn.set_label(gettext.gettext("Disconnect"))
            self.connect_btn.add_css_class("destructive-action")

            self.progress_bar.remove_css_class("progress-yellow")
            self.progress_bar.remove_css_class("progress-orange")
            self.progress_bar.add_css_class("progress-full-green")

            self.progress_bar.set_fraction(1.0)
            self.set_setting(self.SETTING.LAST_CONNECTED, self.get_selected_config())
            self.send_connected_notification()
            # save last cursor
            adj = self.scrolled_window.get_vadjustment()
            self.set_setting(self.SETTING.LISTBOX_V_ADJUST, float(adj.get_value()))
            self.set_setting(self.SETTING.LAST_CONNECTED_CURSOR, self.retrieve(StorageItem.CONFIGS_LIST).index(self.get_selected_config()) - 1)
            
            self.swap_pause_btn_signal_resume_to_pause()

            if self.CM().get_name().lower() == "openvpn3":
                if self.CM().config_path != None:
                    self.pause_resume_btn.set_visible(True)

        else:
            self.stop_network_monitor()
            self.dl_speed_label.set_markup("⬇️ <span weight='bold'>0.0 B/s</span>")
            self.ul_speed_label.set_markup("⬆️ <span weight='bold'>0.0 B/s</span>")
            self.total_traffic_label.set_markup("📊 <span weight='bold'>0 B</span>")

            should_reconnect = getattr(self, "was_connected", False) and self.get_setting(self.SETTING.AUTO_RECONNECT) and not getattr(self, "manual_disconnect", False)
            self.was_connected = False
            self.manual_disconnect = False

            self.update_ip_flag_async()
            self.connect_btn.set_label(gettext.gettext("Connect"))
            self.connect_btn.remove_css_class("destructive-action")
            self.progress_bar.remove_css_class("progress-full-green")
            self.progress_bar.add_css_class("progress-yellow")
            self.progress_bar.set_fraction(0)
            self.send_disconnected_notification()
            
            self.swap_pause_btn_signal_pause_to_resume()
            self.pause_resume_btn.set_visible(False)

            if should_reconnect:
                logger.info("Connection lost. Auto-reconnecting in 3 seconds...")
                toast = Adw.Toast.new(gettext.gettext("Connection lost. Reconnecting in 3 seconds..."))
                self.toast_overlay.add_toast(toast)
                GLib.timeout_add_seconds(3, self.trigger_reconnect)

    def show(self):
        self.setup()
        self.update_ip_flag_async()
        if logger.getEffectiveLevel() == 10:
            self.window.add_css_class("devel")
        self.window.show()

    def update_ip_flag_async(self):
        th = threading.Thread(target = self.update_set_ip_flag)
        th.daemon = True
        th.start()


class Signals(Base):

    def __init__(self):
        super().__init__()

    def connect(self, button, config):
        manager = self.retrieve("CM")["instance"]
        manager.start_watch()
        if manager.status():
            self.disconnect(None, manager)
            return
        try:
            mw = self.retrieve("main_window_instance")
            mw.manual_disconnect = False
        except Exception:
            pass
        config = config()
        manager.connect(os.path.join(self.EOVPN_CONFIG_DIR, "CONFIGS", config))

    def connect_via_ks(self, action, _args, config):
        #FIXME: shortcuts
        self.connect(None, config)

    def disconnect(self, button, manager):
        try:
            mw = self.retrieve("main_window_instance")
            mw.manual_disconnect = True
        except Exception:
            pass
        manager.disconnect()

    def pause(self, button, manager):
        if hasattr(manager, "pause"):
            manager.pause()   

    def resume(self, button, manager):
        if hasattr(manager, "resume"):
            manager.resume()