import logging
from .settings_window import SettingsWindow
from .connection_manager import NetworkManager, OpenVPN3
from gi.repository import Gtk, Gio, GLib, Gdk
from .ip_lookup.lookup import Lookup
from .utils import ovpn_is_auth_required
import os
import gettext
import webbrowser

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
        self.app.add_window(self.window)
        self.store(StorageItem.MAIN_WINDOW, self.window)

        self.selected_row = None
        self.selected_config = None
        self.connected_cursor = None
        self.signals = Signals()

        ###########################################################
        # Initialize and setup Connection Manager (CM)
        ###########################################################
        
        preferred = self.get_setting(self.SETTING.MANAGER)
        if preferred == "openvpn3":
            self.CM = OpenVPN3(True, self.on_connection_event)
            if self.CM.version() is not None:
                pass
            else:
                logger.error("openvpn3 version() fail! falling back to NM!")
                self.set_setting(self.SETTING.MANAGER, "networkmanager")
                self.CM = NetworkManager()
        else:
            self.CM = NetworkManager()        

        self.CM.start_watch(self.on_connection_event)

        self.critical_errors = []

        if self.CM.get_name().lower() == "networkmanager":
            nm_version, is_openvpn_available = self.CM.version()
            logger.debug("%s | %s", nm_version, is_openvpn_available)
            if nm_version is None:
                self.critical_errors.append("Unable to Find NetworkManager.")
            if is_openvpn_available is False:
                self.critical_errors.append("Unable to Find OpenVPN plugin for NetworkManager")
        else:
            version = self.CM.version()
            logger.debug("OpenVPN3 Version: %s", version)
            if version is None:
                self.critical_errors.append("Unable to find OpenVPN3.")


        self.lookup = Lookup()

    def get_selected_config(self):
        try:
            row = self.list_box.get_selected_row().get_child().get_label()
            return row
        except AttributeError:
            return None

    def row_changed(self, listbox, row):
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
        btn.get_style_context().add_class("destructive-action")

        box = dlg.get_message_area()
        for msg in error_message:
            box.append(Gtk.Label.new(msg))
        dlg.show()

    def setup(self):

        ###########################################################
        # Declare boxes for each major component.
        ###########################################################
        self.box = Gtk.Box.new(Gtk.Orientation.VERTICAL, 0) #top most box
        self.paned = Gtk.Paned.new(Gtk.Orientation.HORIZONTAL)

        self.inner_left = Gtk.Box.new(Gtk.Orientation.VERTICAL, 0) #ListBox
        self.paned.set_start_child(self.inner_left)
        self.inner_left.set_size_request(200, 200)

        self.inner_right = Gtk.Box.new(Gtk.Orientation.VERTICAL, 0) #Info
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
        lbl.get_style_context().add_class("bold")
        btn = Gtk.Button.new_with_label(gettext.gettext("Open Settings"))
        btn.get_style_context().add_class("suggested-action")
        btn.set_valign(Gtk.Align.START)
        btn.set_halign(Gtk.Align.CENTER)
        btn.connect("clicked", lambda x: SettingsWindow().show())
        v_box.append(lbl)
        v_box.append(btn)
        self.list_box.set_placeholder(v_box)

        self.scrolled_window.set_child(viewport)
        viewport.set_child(self.list_box)
        self.load_only()

        self.inner_left.append(self.scrolled_window)

        ###########################################################
        # Right Box
        ###########################################################
        img = Gtk.Picture.new()
        img.set_halign(Gtk.Align.CENTER)
        img.set_valign(Gtk.Align.CENTER)
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
        self.ip_addr.get_style_context().add_class("ip_text")
        self.ip_addr.set_vexpand(True)
        cpy_btn = Gtk.Button.new_from_icon_name("edit-copy-symbolic")
        cpy_btn.set_valign(Gtk.Align.CENTER)
        cpy_btn.set_halign(Gtk.Align.CENTER)
        cpy_btn.set_tooltip_text("Copy")
        cpy_btn.get_style_context().add_class("flat")

        h_box.append(self.ip_text)
        h_box.append(self.ip_addr)
        h_box.append(cpy_btn)

        self.inner_right.append(h_box)
        GLib.idle_add(self.update_set_ip_flag)

        self.csh = None # Connect signal handler
        self.psh = None # Pause Signal Handler

        self.connect_box = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, 6)
        self.connect_box.set_valign(Gtk.Align.END)
        self.connect_box.set_margin_start(10)
        self.connect_box.set_margin_end(10)
        self.connect_box.set_margin_bottom(10)
        self.connect_box.set_margin_top(10)

        self.connect_btn = Gtk.Button().new_with_label(gettext.gettext("Connect"))
        self.connect_btn.set_valign(Gtk.Align.FILL)
        self.connect_btn.set_hexpand(True)
        self.connect_btn.set_vexpand(True)
        
        self.connect_box.append(self.connect_btn)

        self.pause_resume_btn = Gtk.Button().new_from_icon_name("media-playback-pause-symbolic")
        self.pause_resume_btn.set_valign(Gtk.Align.END)
        self.pause_resume_btn.set_vexpand(True)
        self.pause_resume_btn.set_visible(False)

        self.csh = self.connect_btn.connect("clicked", self.signals.connect, self.get_selected_config, self.CM, self.pause_resume_btn)

        #Connects to pause()
        self.swap_pause_btn_signal_resume_to_pause()

        self.connect_box.append(self.pause_resume_btn)

        self.inner_right.append(self.connect_box)

        ###########################################################
        # Bottom Progress Bar
        ###########################################################
        self.progress_bar = Gtk.ProgressBar.new()
        
        #Initial connection check on startup + Progress bar update + signal connects
        if self.CM.status():
            self.connect_btn.set_label(gettext.gettext("Disconnect"))
            self.connect_btn.get_style_context().add_class("destructive-action")
            self.progress_bar.get_style_context().add_class("progress-full-green")
            self.progress_bar.set_fraction(1.0)
        else:
            self.progress_bar.get_style_context().add_class("progress-yellow")

        def open_about_dialog(widget, data):
            about = Gtk.AboutDialog.new()
            about.set_logo_icon_name("com.github.jkotra.eovpn")
            about.set_program_name("eOVPN")
            about.set_authors(["Jagadeesh Kotra"])
            about.set_artists(["Jagadeesh Kotra"])
            about.set_copyright("Jagadeesh Kotra")
            about.set_license_type(Gtk.License.LGPL_3_0)
            about.set_version(self.APP_VERSION)
            about.set_website("https://github.com/jkotra/eOVPN")
            about.set_system_information("Flatpak: \t {}".format("true" if os.getenv("FLATPAK_ID") is not None else "false"))
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

        action = Gio.SimpleAction().new("update", None)
        action.connect("activate", lambda x, d: self.validate_and_load(self.spinner) )
        self.app.add_action(action)

        action = Gio.SimpleAction().new("about", None)
        action.connect("activate", open_about_dialog)
        self.app.add_action(action)

        action = Gio.SimpleAction().new("donate", None)
        action.connect("activate", lambda x, d: webbrowser.open("https://ko-fi.com/jkotra"))
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
        self.csh = action.connect('activate', self.signals.connect_via_ks, self.get_selected_config, self.CM, self.pause_resume_btn)
        self.app.add_action(action)
        self.app.set_accels_for_action("app.connect", ["<Primary>C", "<Primary>D"])


        menu = Gio.Menu.new()
        menu.insert(0, gettext.gettext("Update"), "app.update")
        menu.insert(1, gettext.gettext("Settings"), "app.settings")
        menu.insert(2, gettext.gettext("Keyboard Shortcuts"), "app.keyboard_shortcuts")
        menu.insert(3, gettext.gettext("Donate"), "app.donate")
        menu.insert(4, gettext.gettext("About"), "app.about")
        popover = Gtk.PopoverMenu.new_from_model(menu)

        header_bar = self.get_object("header_bar")

        menu_button = Gtk.MenuButton.new()
        menu_button.set_icon_name("open-menu-symbolic")
        menu_button.set_popover(popover)
        header_bar.pack_end(menu_button)

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
        self.window.set_child(self.box)

        cpy_btn.connect("clicked", lambda x: Gdk.Display.get_default().get_clipboard().set(self.ip_addr.get_label()))

        logger.info(str(self.critical_errors))
        if len(self.critical_errors) > 0:
            GLib.idle_add(self.generic_critical_error_dialog, self.critical_errors)

    def update_set_ip_flag(self):
        self.lookup.update()
        self.retrieve(StorageItem.FLAG).set_pixbuf(self.get_country_pixbuf(self.lookup.country_code))
        self.ip_addr.set_label(self.lookup.ip)

    
    def swap_pause_btn_signal_pause_to_resume(self):
        self.pause_resume_btn.set_property("icon-name", "media-playback-start-symbolic")
        if self.psh is not None:
            self.pause_resume_btn.disconnect(self.psh)
        self.psh = self.pause_resume_btn.connect("clicked", self.signals.resume, self.CM)
        GLib.idle_add(self.update_set_ip_flag)
        
    def swap_pause_btn_signal_resume_to_pause(self):
        self.pause_resume_btn.set_property("icon-name", "media-playback-pause-symbolic")
        if self.psh is not None:
            self.pause_resume_btn.disconnect(self.psh)
        self.psh = self.pause_resume_btn.connect("clicked", self.signals.pause, self.CM)

    
    def on_connection_event(self, result, error=None):
        if error is not None:
            logger.error(error)
            self.progress_bar.set_text(error)
            self.progress_bar.set_fraction(1)
            return

        if type(result) is list:
            if len(result) == 1:
                status = result[-1]
                p_ctx = self.progress_bar.get_style_context()

                if status == "pause":
                    p_ctx.remove_class("progress-full-green")
                    p_ctx.add_class("progress-orange")
                    self.swap_pause_btn_signal_pause_to_resume()
                    return

                elif status == "resume":
                    p_ctx.remove_class("progress-orange")
                    p_ctx.add_class("progress-full-green")
                    self.swap_pause_btn_signal_resume_to_pause()
                    return

            logger.info(self.progress_bar.get_fraction())
            prev = self.progress_bar.get_fraction()
            if prev < 0.95:
                self.progress_bar.set_fraction(prev + 0.35)
            return

        if result:
            GLib.idle_add(self.update_set_ip_flag)
            self.connect_btn.set_label(gettext.gettext("Disconnect"))
            self.connect_btn.get_style_context().add_class("destructive-action")
            p_ctx = self.progress_bar.get_style_context()
            p_ctx.remove_class("progress-yellow")
            p_ctx.add_class("progress-full-green")
            self.progress_bar.set_fraction(1.0)
            self.set_setting(self.SETTING.LAST_CONNECTED, self.get_selected_config())
            self.send_connected_notification()
            # save last cursor
            adj = self.scrolled_window.get_vadjustment()
            self.set_setting(self.SETTING.LISTBOX_V_ADJUST, float(adj.get_value()))
            self.set_setting(self.SETTING.LAST_CONNECTED_CURSOR, self.retrieve(StorageItem.CONFIGS_LIST).index(self.get_selected_config()))
            
            self.swap_pause_btn_signal_resume_to_pause()

        else:
            GLib.idle_add(self.update_set_ip_flag)
            self.connect_btn.set_label(gettext.gettext("Connect"))
            self.connect_btn.get_style_context().remove_class("destructive-action")
            p_ctx = self.progress_bar.get_style_context()
            p_ctx.remove_class("progress-full-green")
            p_ctx.add_class("progress-yellow")
            self.progress_bar.set_fraction(0)
            self.send_disconnected_notification()
            
            self.swap_pause_btn_signal_pause_to_resume()

    def show(self):
        self.setup()
        self.window.show()



class Signals(Base):

    def __init__(self):
        super().__init__()

    def connect(self, button, config, manager, pause_resume_btn):
        if manager.status():
            pause_resume_btn.set_visible(False)
            self.disconnect(None, manager)
            return
        config = config()
        manager.connect(os.path.join(self.EOVPN_CONFIG_DIR, "CONFIGS", config))
        if manager.get_name().lower() == "openvpn3":
            pause_resume_btn.set_visible(True)

    def connect_via_ks(self, action, _args, config, manager, pause_resume_btn):
        #print("action received:", action, _args, config, manager, callback)
        self.connect(None, config, manager, pause_resume_btn)

    def disconnect(self, button, manager):
        manager.disconnect()

    def pause(self, button, manager):
        if hasattr(manager, "pause"):
            manager.pause()   

    def resume(self, button, manager):
        if hasattr(manager, "resume"):
            manager.resume()