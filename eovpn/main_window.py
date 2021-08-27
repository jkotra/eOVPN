import logging
from .settings_window import SettingsWindow
from .connection_manager import eOVPNConnectionManager
from .networkmanager.dbus import NMDbus
from gi.repository import Gtk, Gio, GdkPixbuf, GObject
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
        self.signals = Signals()
        self.CM = eOVPNConnectionManager()
        self.nmdbus = NMDbus()
        self.nmdbus.watch(self.on_nm_connection_event)
    

    def setup(self):
        box = Gtk.Box.new(Gtk.Orientation.VERTICAL, 0) #top most box
        main_box = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, 0) #main
        box.append(main_box)

        inner_left = Gtk.Box.new(Gtk.Orientation.VERTICAL, 0) #ListBox
        inner_left.set_hexpand(True)

        inner_right = Gtk.Box.new(Gtk.Orientation.VERTICAL, 0)
        inner_right.set_hexpand(True)

        main_box.append(inner_left)
        main_box.append(inner_right)

        viewport = Gtk.Viewport().new()
        viewport.set_vexpand(True)
        viewport.set_hexpand(True)

        scrolled_window = Gtk.ScrolledWindow().new()


        def row_selected(box, row):
            self.selected_row = row

        list_box = Gtk.ListBox.new()
        self.store_widget("config_box", list_box)
        list_box.connect("row-selected", row_selected)
        config_rows = []
        
        def update_config_rows():
            try:
               configs = os.listdir(os.path.join(self.EOVPN_CONFIG_DIR, "CONFIGS"))
            except:
               configs = []    
            
            configs.sort()
        
            for file in configs:
                row = Gtk.ListBoxRow.new()
                label = Gtk.Label.new(file)
                label.set_halign(Gtk.Align.START)
                row.set_child(label)
                config_rows.append(row)
        
            for r in config_rows:
                list_box.append(r)
        
        update_config_rows()
        self.store_widget("config_rows", config_rows)
        self.store_something("update_config_func", update_config_rows)
        scrolled_window.set_child(list_box)
        viewport.set_child(scrolled_window)
        inner_left.append(viewport)

        # Right Side
        #this contains - Country Image(Optional), IP, Location
        top_info_box = Gtk.Box().new(Gtk.Orientation.VERTICAL, 4)
        top_info_box.set_margin_top(12)
        top_info_box.set_vexpand(True)
        inner_right.append(top_info_box)

        ## image
        pixbuf = GdkPixbuf.Pixbuf.new_from_resource_at_scale(self.EOVPN_GRESOURCE_PREFIX + "/country_flags/svg/us.svg",
                                                             128,
                                                             -1,
                                                             True)
        img = Gtk.Picture.new_for_pixbuf(pixbuf)
        img.set_halign(Gtk.Align.CENTER)
        top_info_box.append(img)
        if self.get_setting(self.SETTING.SHOW_FLAG) is False:
            img.hide()
        self.store_widget("flag", img)    

        ip_addr = Gtk.Label().new("IP: 127.0.0.1")
        ip_addr.get_style_context().add_class("ip_text")
        top_info_box.append(ip_addr)
        top_info_box.append(Gtk.Label().new("Location: New York"))

        self.connect_btn = Gtk.Button().new_with_label("Connect")
        self.connect_btn.set_margin_top(15)
        self.connect_btn.set_margin_bottom(15)
        self.connect_btn.set_margin_start(15)
        self.connect_btn.set_margin_end(15)
        self.connect_btn.set_valign(Gtk.Align.END)
        self.connect_btn.connect("clicked", lambda _: self.signals.connect(self.selected_row.get_child().get_label(), self.CM, self.progress_bar))
        inner_right.append(self.connect_btn)


        # END OF RIGHT
        
        self.progress_bar = Gtk.ProgressBar().new()
        box.append(self.progress_bar)

        if self.CM.get_connection_status():
            self.connect_btn.set_label("Disconnect")
            self.connect_btn.get_style_context().add_class("destructive-action")
            self.progress_bar.set_fraction(1.0)
            self.progress_bar.get_style_context().add_class("progress-green")
            self.connect_btn.connect("clicked", self.signals.disconnect, self.CM)
        else:
            self.progress_bar.get_style_context().add_class("progress-yellow")
            self.progress_bar.set_pulse_step(0.05)   

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

        action = Gio.SimpleAction().new("about", None)
        action.connect("activate", open_about_dialog)
        self.app.add_action(action)

        def open_settings_window(widget, data):
            window = SettingsWindow()
            window.show()



        action = Gio.SimpleAction().new("settings", None)
        action.connect("activate", open_settings_window)
        self.app.add_action(action)

        menu = Gio.Menu().new()
        menu.insert(0, "Update")
        menu.insert(1, "Settings", "app.settings")
        menu.insert(2, "About", "app.about")
        popover = Gtk.PopoverMenu().new_from_model(menu)

        header_bar = self.get_object("header_bar")
        
        menu_button = Gtk.MenuButton().new()
        menu_button.set_icon_name("open-menu-symbolic")
        menu_button.set_popover(popover)
        header_bar.pack_end(menu_button)

        spinner = Gtk.Spinner()
        header_bar.pack_end(spinner)

        self.window.set_child(box)    

    def on_nm_connection_event(self, result, error=None):
        if error is not None:
            print(error)
            return

        if result:
            self.connect_btn.set_label("Disconnect")
            self.connect_btn.get_style_context().add_class("destructive-action")
            self.progress_bar.set_fraction(1.0)
            self.progress_bar.get_style_context().add_class("progress-green")
            self.connect_btn.connect("clicked", self.signals.disconnect, self.CM)
        else:
            self.connect_btn.set_label("Connect")
            self.connect_btn.get_style_context().remove_class("destructive-action")
            self.progress_bar.set_fraction(0)

    def show(self):
        self.setup()
        self.window.show()



class Signals(Base):

    def __init__(self):
        super().__init__()
    
    def connect(self, config, manager, progressbar):
        print(config, manager, progressbar)
        manager.connect("/home/jkotra/Documents/ipvanish/" + config)

    def disconnect(self, button, manager):
        manager.disconnect()
