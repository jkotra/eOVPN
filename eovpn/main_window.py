import logging
from .settings_window import SettingsWindow
from .connection_manager import eOVPNConnectionManager
from .networkmanager.dbus import NMDbus
from gi.repository import Gtk, Gio, GdkPixbuf, GObject, GLib, Gdk
from .ip_lookup.lookup import Lookup
from .utils import ovpn_is_auth_required, validate_remote
import os
import time
import threading

from .eovpn_base import Base, ThreadManager
logger = logging.getLogger(__name__)

def on_connect_event(result, error):
    print(result, error)

class MainWindow(Base, Gtk.Builder):
    def __init__(self, app):
        super().__init__()
        Gtk.Builder.__init__(self)
        self.app = app
        
        self.add_from_resource(self.EOVPN_GRESOURCE_PREFIX + "/ui/" + "main.ui")
        self.window = self.get_object("main_window")
        self.window.set_title("eOVPN")
        self.window.set_icon_name(self.APP_ID)
        self.app.add_window(self.window)
        self.store_widget("main_window", self.window)
        
        self.selected_row = None
        self.selected_config = None
        self.connected_cursor = None
        self.signals = Signals()
        self.CM = eOVPNConnectionManager()
        self.nmdbus = NMDbus()
        self.lookup = Lookup()
        self.nmdbus.watch(self.on_nm_connection_event)
    
    def on_select_row(self, listbox, row):
        self.selected_row = row
        self.selected_config = self.selected_row.get_child().get_label()
        if ovpn_is_auth_required(self.EOVPN_OVPN_CONFIG_DIR + "/" + row.get_child().get_label()):
            if self.get_setting(self.SETTING.REQ_AUTH) is False:
                self.connect_btn.set_sensitive(False)
            else:
                self.connect_btn.set_sensitive(True)


    def get_selected_config(self):
        try:
            row = self.list_box.get_selected_row().get_child().get_label()
            return row
        except AttributeError:
            return None                                                    

    def setup(self):
        self.box = Gtk.Box.new(Gtk.Orientation.VERTICAL, 0) #top most box
        self.paned = Gtk.Paned.new(Gtk.Orientation.HORIZONTAL)

        self.inner_left = Gtk.Box.new(Gtk.Orientation.VERTICAL, 0) #ListBox
        self.paned.set_start_child(self.inner_left)
        self.inner_left.set_size_request(200, 200)

        self.inner_right = Gtk.Box.new(Gtk.Orientation.VERTICAL, 0) #Info
        self.paned.set_end_child(self.inner_right)

        viewport = Gtk.Viewport().new()
        viewport.set_vexpand(True)
        viewport.set_hexpand(True)
        
        scrolled_window = Gtk.ScrolledWindow().new()

        self.list_box = Gtk.ListBox.new()
        self.store_widget("config_box", self.list_box)
        self.list_box.connect("row-selected", self.on_select_row)
        self.available_configs = []
        self.list_box_rows = []
        
        def update_config_rows():
            try:
               configs = os.listdir(os.path.join(self.EOVPN_CONFIG_DIR, "CONFIGS"))
            except:
               configs = []    
            
            configs.sort()
            self.available_configs = []
            self.list_box_rows = []
        
            for file in configs:
                if not file.endswith("ovpn"):
                    continue
                row = Gtk.ListBoxRow.new()
                label = Gtk.Label.new(file)
                label.set_halign(Gtk.Align.START)
                row.set_child(label)
                self.list_box.append(row)
                self.list_box_rows.append(row)
                self.available_configs.append(file)

            if cur := self.get_setting(self.SETTING.LAST_CONNECTED_CURSOR) != -1:
                self.list_box.select_row(self.list_box_rows[cur])
                self.list_box.grab_focus()


        
        update_config_rows()
        self.store_something("config_rows", self.list_box_rows)
        self.store_something("update_config_func", update_config_rows)

        scrolled_window.set_child(viewport)
        viewport.set_child(self.list_box)

        self.inner_left.append(scrolled_window)

        # Right Side
        img = Gtk.Picture.new()
        img.set_halign(Gtk.Align.CENTER)
        self.store_something("flag", img)
        if self.get_setting(self.SETTING.SHOW_FLAG) is False:
            img.hide()
        self.inner_right.append(img)

        #this contains - OpenVPN info
        h_box = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, 6)
        h_box.set_halign(Gtk.Align.CENTER)
        self.ip_text = Gtk.Label.new("IP: ")
        self.ip_addr = Gtk.Label.new("0.0.0.0")
        self.ip_addr.set_valign(Gtk.Align.CENTER)
        self.ip_addr.get_style_context().add_class("ip_text")
        self.ip_addr.set_vexpand(True)
        cpy_btn = Gtk.Button.new_from_icon_name("edit-copy-symbolic")
        cpy_btn.set_valign(Gtk.Align.CENTER)
        cpy_btn.set_halign(Gtk.Align.CENTER)
        cpy_btn.connect("clicked", lambda x: Gdk.Display.get_default().get_clipboard().set(self.ip_addr.get_label()))

        h_box.append(self.ip_text)
        h_box.append(self.ip_addr)
        h_box.append(cpy_btn)

        self.inner_right.append(h_box)
        ThreadManager().create(self.update_set_ip_flag, ())

        self.connect_btn = Gtk.Button().new_with_label("Connect")
        self.connect_btn.set_margin_top(10)
        self.connect_btn.set_margin_bottom(10)
        self.connect_btn.set_margin_start(10)
        self.connect_btn.set_margin_end(10)
        self.connect_btn.set_valign(Gtk.Align.END)
        self.connect_btn.set_vexpand(True)

        self.connect_btn.connect("clicked", self.signals.connect, self.get_selected_config, self.CM)
        self.inner_right.append(self.connect_btn)
        # END OF RIGHT

        self.progress_bar = Gtk.ProgressBar.new()
        #self.progress_bar.set_valign(Gtk.Align.END)
        #self.box.append(self.progress_bar)

        if self.CM.get_connection_status():
            self.connect_btn.set_label("Disconnect")
            self.connect_btn.get_style_context().add_class("destructive-action")
            self.progress_bar.get_style_context().add_class("progress-full-green")
            self.progress_bar.set_fraction(1.0)
        else:
            self.progress_bar.get_style_context().add_class("progress-yellow")

        # popover
        def open_about_dialog(widget, data):
            about = Gtk.AboutDialog().new()
            about.set_logo_icon_name("com.github.jkotra.eovpn")
            about.set_program_name("eOVPN")
            about.set_authors(["Jagadeesh Kotra"])
            about.set_artists(["Jagadeesh Kotra"])
            about.set_copyright("Jagadeesh Kotra")
            about.set_license_type(Gtk.License.LGPL_3_0)
            about.set_version("1.0")
            about.set_website("https://github.com/jkotra/eOVPN")
            about.set_transient_for(self.window)
            about.show()
        
        action = Gio.SimpleAction().new("update", None)
        action.connect("activate", lambda x, d: validate_remote(self.get_setting(self.SETTING.REMOTE)))
        self.app.add_action(action)

        action = Gio.SimpleAction().new("about", None)
        action.connect("activate", open_about_dialog)
        self.app.add_action(action)

        action = Gio.SimpleAction().new("settings", None)
        action.connect("activate", lambda x, d: SettingsWindow().show())
        self.app.add_action(action)

        menu = Gio.Menu().new()
        menu.insert(0, "Update", "app.update")
        menu.insert(1, "Settings", "app.settings")
        menu.insert(2, "About", "app.about")
        popover = Gtk.PopoverMenu().new_from_model(menu)

        header_bar = self.get_object("header_bar")
        
        menu_button = Gtk.MenuButton().new()
        menu_button.set_icon_name("open-menu-symbolic")
        menu_button.set_popover(popover)
        header_bar.pack_end(menu_button)
        
        #finally!
        self.box.append(self.paned)
        self.box.append(self.progress_bar)
        self.window.set_child(self.box) 
    
    def update_set_ip_flag(self):
        self.lookup.update()
        self.get_something("flag").set_pixbuf(self.get_country_pixbuf(self.lookup.country_code))
        self.ip_addr.set_label(self.lookup.ip)

    def on_nm_connection_event(self, result, error=None):
        if error is not None:
            print(error)
            self.progress_bar.set_text(error)
            self.progress_bar.set_fraction(1)
            return

        if type(result) is list:
            print(self.progress_bar.get_fraction())
            prev = self.progress_bar.get_fraction()
            if prev < 0.95:
                self.progress_bar.set_fraction(prev + 0.25)
            return

        if result:
            ThreadManager().create(self.update_set_ip_flag, ())
            self.connect_btn.set_label("Disconnect")
            self.connect_btn.get_style_context().add_class("destructive-action")
            p_ctx = self.progress_bar.get_style_context()
            p_ctx.remove_class("progress-yellow")
            p_ctx.add_class("progress-full-green")
            self.progress_bar.set_fraction(1.0) 
            self.set_setting(self.SETTING.LAST_CONNECTED, self.get_selected_config())
            self.send_connected_notification()
            # save last cursor
            self.set_setting(self.SETTING.LAST_CONNECTED_CURSOR, self.available_configs.index(self.get_selected_config()))
                      
        else:
            ThreadManager().create(self.update_set_ip_flag, ())
            self.connect_btn.set_label("Connect")
            self.connect_btn.get_style_context().remove_class("destructive-action")
            p_ctx = self.progress_bar.get_style_context()
            p_ctx.remove_class("progress-full-green")
            p_ctx.add_class("progress-yellow")
            self.progress_bar.set_fraction(0)
            self.send_disconnected_notification()

    def show(self):
        self.setup()
        self.window.show()



class Signals(Base):

    def __init__(self):
        super().__init__()
    
    def connect(self, button, config, manager):
        config = config()
        if config is None and manager.get_connection_status():
            manager.connect(None)
            return
        manager.connect(self.EOVPN_CONFIG_DIR + "/CONFIGS/" + config)

    def disconnect(self, button, manager):
        manager.disconnect()