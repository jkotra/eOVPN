import logging
from .settings_window import SettingsWindow
from gi.repository import Gtk, Gio, GdkPixbuf

from .eovpn_base import Base
logger = logging.getLogger(__name__)

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

        list_box = Gtk.ListBox.new()
     

        row = Gtk.ListBoxRow.new()
        h_box = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, 0)
        label = Gtk.Label.new("test-03.ovpn")
        label.set_halign(Gtk.Align.START)
        h_box.append(label)
        
        star = Gtk.Button()
        star.set_icon_name("non-starred-symbolic")
        star.set_hexpand(True)
        star.set_valign(Gtk.Align.CENTER)
        star.set_halign(Gtk.Align.END)
        star.connect("clicked", lambda button: star.set_icon_name("starred-symbolic"))
        star.get_style_context().add_class("star")


        h_box.append(star)
        row.set_child(h_box)
        list_box.append(row)
        
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
        pixbuf = GdkPixbuf.Pixbuf.new_from_resource_at_scale(self.EOVPN_GRESOURCE_PREFIX + "/country_flags/svg/au.svg",
                                                             128,
                                                             -1,
                                                             True)
        img = Gtk.Picture.new_for_pixbuf(pixbuf)
        img.set_halign(Gtk.Align.CENTER)
        top_info_box.append(img)
        #img.hide()

        ip_addr = Gtk.Label().new("IP: 127.0.0.1")
        ip_addr.get_style_context().add_class("ip_text")
        top_info_box.append(ip_addr)
        top_info_box.append(Gtk.Label().new("Location: Zurich"))

        connect_btn = Gtk.Button().new_with_label("Connect")
        connect_btn.set_margin_top(15)
        connect_btn.set_margin_bottom(15)
        connect_btn.set_margin_start(15)
        connect_btn.set_margin_end(15)
        connect_btn.set_valign(Gtk.Align.END)
        inner_right.append(connect_btn)
        

        # END OF RIGHT
        
        progress_bar = Gtk.ProgressBar().new()
        progress_bar.set_fraction(0.75)
        box.append(progress_bar)

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


    def show(self):
        self.setup()
        self.window.show()

