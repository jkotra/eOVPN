
import logging
import os
import shutil
import gettext
import gettext
from sqlite3 import connect

from gi.repository import Gtk, Gio, GLib, Secret

from .eovpn_base import Base, StorageItem
from .utils import is_selinux_enforcing

from .networkmanager.bindings import NetworkManager
from .openvpn3.bindings import OpenVPN3

logger = logging.getLogger(__name__)



class SettingsWindow(Base, Gtk.Builder):
    def __init__(self):
        super().__init__()
        Gtk.Builder.__init__(self)
        self.signals = Signals()

        self.add_from_resource(self.EOVPN_GRESOURCE_PREFIX + "/ui/" + "settings.ui")
        self.window = self.get_object("settings_window")
        self.window.set_title("eOVPN Settings")

        self.window.set_transient_for(self.retrieve(StorageItem.MAIN_WINDOW))
        self.window.set_modal(True)
        self.store(StorageItem.SETTINGS_WINDOW, self.window)

    def setup(self):
        
        self.reset_btn = Gtk.Button.new_with_label(gettext.gettext("Reset"))
        self.reset_btn.get_style_context().add_class("destructive-action")
        self.header = self.get_object("settings_header_bar")
        self.header.pack_start(self.reset_btn)

        self.spinner = Gtk.Spinner()
        self.header.pack_end(self.spinner)
        
        self.stack = Gtk.Stack.new()
        self.stack.set_transition_type(Gtk.StackTransitionType.SLIDE_LEFT)
        self.stack_switcher = Gtk.StackSwitcher.new()
        self.stack_switcher.set_stack(self.stack)
        self.header.set_title_widget(self.stack_switcher)

        self.main_box = Gtk.Box.new(Gtk.Orientation.VERTICAL, 4)
        self.main_box.set_valign(Gtk.Align.CENTER)
        self.main_box.get_style_context().add_class("m-6")

        self.pref_box = Gtk.Box.new(Gtk.Orientation.VERTICAL, 0)
        self.backend_box = Gtk.Box.new(Gtk.Orientation.VERTICAL, 0)

        self.stack.add_titled(self.main_box, "setup", gettext.gettext("Setup"))
        self.stack.add_titled(self.pref_box, "general", gettext.gettext("General"))
        self.stack.add_titled(self.backend_box, "Backend", gettext.gettext("Backend"))

        
        label = Gtk.Label.new(gettext.gettext("Configuration Source"))
        label.set_halign(Gtk.Align.START)
        label.get_style_context().add_class("bold")
        self.main_box.append(label)

        configuration_source_hbox = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, 4)
        entry = Gtk.Entry.new()
        if (text := self.get_setting(self.SETTING.REMOTE)) is not None:
            entry.set_text(text)
        else:    
            entry.set_placeholder_text("https://example.com/vpn/configs.zip")
        zip_chooser_btn = Gtk.Button.new_from_icon_name("media-zip-symbolic")
        zip_chooser_btn.set_tooltip_text(gettext.gettext("Choose ZIP File"))
        entry.set_hexpand(True)
        configuration_source_hbox.append(entry)
        configuration_source_hbox.append(zip_chooser_btn)

        zip_file_chooser_dialog = Gtk.FileChooserNative(action=Gtk.FileChooserAction.OPEN)
        zip_file_chooser_dialog.set_transient_for(self.window)
        zip_filter = Gtk.FileFilter()
        zip_filter.set_name("ZIP")
        zip_filter.add_mime_type("application/zip")
        zip_file_chooser_dialog.add_filter(zip_filter)
        default_path = Gio.File.new_for_path(GLib.get_home_dir())
        zip_file_chooser_dialog.set_current_folder(default_path)

        zip_chooser_btn.connect("clicked", lambda btn: zip_file_chooser_dialog.show())

        self.main_box.append(configuration_source_hbox)

        self.revealer = Gtk.Revealer.new()
        self.validate_btn = Gtk.Button.new_with_label(gettext.gettext("Validate & Load"))
        self.validate_btn.get_style_context().add_class("suggested-action")

        self.revealer.set_child(self.validate_btn)
        self.main_box.append(self.revealer)
        self.revealer.set_reveal_child(False)

        self.auth_box = Gtk.Box.new(Gtk.Orientation.VERTICAL, 0)

        ask_auth_box = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, 4)
        ask_auth_box.get_style_context().add_class("m-4")
        label = Gtk.Label.new(gettext.gettext("Authentication"))
        label.set_halign(Gtk.Align.START)
        label.get_style_context().add_class("bold")
        ask_auth_box.append(label)

        self.ask_auth_switch = Gtk.Switch.new()
        self.ask_auth_switch.set_halign(Gtk.Align.END)
        ask_auth_box.append(self.ask_auth_switch)

        self.auth_box.append(ask_auth_box)

        #username
        username_box = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, 4)
        button = Gtk.Button.new_from_icon_name("avatar-default-symbolic")
        button.set_sensitive(False)
        username_box.append(button)
        self.username_entry = Gtk.Entry.new()
        self.username_entry.set_placeholder_text(gettext.gettext("Username / Email"))
        self.username_entry.set_hexpand(True)
        username_box.append(self.username_entry)

        #password
        password_box = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, 4)
        button = Gtk.Button.new_from_icon_name("dialog-password-symbolic")
        button.set_sensitive(False)
        password_box.append(button)
        self.password_entry = Gtk.PasswordEntry.new()
        self.password_entry.set_property("placeholder-text", gettext.gettext("Password"))
        self.password_entry.set_show_peek_icon(True)
        self.password_entry.set_hexpand(True)
        password_box.append(self.password_entry)

        #CA
        ca_box = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, 4)
        ca_box.get_style_context().add_class("mb-4")
        button = Gtk.Button.new_from_icon_name("application-certificate-symbolic")
        button.set_sensitive(False)
        ca_box.append(button)
        self.ca_chooser_btn = Gtk.Button.new_with_label("(None)")
        self.ca_chooser_btn.set_hexpand(True)

        #CA Filechooserdialog
        ca_file_chooser_dialog = Gtk.FileChooserNative(action=Gtk.FileChooserAction.OPEN)
        ca_file_chooser_dialog.set_transient_for(self.window)
        ca_filter = Gtk.FileFilter()
        ca_filter.set_name("CA / CRT")
        ca_filter.add_mime_type("application/pkix-cert")
        ca_file_chooser_dialog.add_filter(ca_filter)
        default_path = Gio.File.new_for_path(self.EOVPN_OVPN_CONFIG_DIR)
        ca_file_chooser_dialog.set_current_folder(default_path)

        self.ca_chooser_btn.connect("clicked", lambda btn: ca_file_chooser_dialog.show())

        ca_box.append(self.ca_chooser_btn)
        
        self.user_pass_ca_box = Gtk.Box.new(Gtk.Orientation.VERTICAL, 4)
        self.user_pass_ca_box.get_style_context().add_class("mt-4")
        self.user_pass_ca_box.append(username_box)
        self.user_pass_ca_box.append(password_box)
        self.user_pass_ca_box.append(ca_box)
        self.user_pass_ca_box.set_sensitive(False)
        self.auth_box.append(self.user_pass_ca_box)

        self.main_box.append(self.auth_box)
        if (_ := self.get_setting(self.SETTING.REQ_AUTH)) is not None:
            self.ask_auth_switch.set_state(_)
            self.user_pass_ca_box.set_sensitive(_)

            if (username := self.get_setting(self.SETTING.AUTH_USER)) is not None:
                self.username_entry.set_text(username)

            if (username := self.get_setting(self.SETTING.AUTH_USER)) is not None:
                
                def on_password_lookup(source, result):
                    logger.info(result.__str__())
                    try:
                        pwd = Secret.password_lookup_finish(result)
                    except Exception:
                        if (pwd := self.get_setting(self.SETTING.AUTH_PASS)) is not None:
                            self.password_entry.set_text(pwd)    
                    if pwd is None:
                        logger.warning("Password is empty!")
                        return
                    self.password_entry.set_text(pwd)

                Secret.password_lookup(self.EOVPN_SECRET_SCHEMA, {"username": username}, None, on_password_lookup)

            if (ca := self.get_setting(self.SETTING.CA)) is not None:
                self.ca_chooser_btn.set_label(os.path.basename(ca))  


        #Prefs - Setup
        frame = Gtk.Frame.new()
        list_box = Gtk.ListBox.new()
        frame.get_style_context().add_class("m-10")
        list_box.get_style_context().add_class("rich-list")
        
        ###########################################################
        # Notifications
        ###########################################################
        list_box_row = Gtk.ListBoxRow.new()
        h_box = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, 0)
        v_box = Gtk.Box.new(Gtk.Orientation.VERTICAL, 0)
        v_box.set_hexpand(True)

        label = Gtk.Label.new(gettext.gettext("Notifications"))
        v_box.set_valign(Gtk.Align.CENTER)
        v_box.append(label)

        img = Gtk.Image.new()
        img.set_from_icon_name("user-available-symbolic")
        h_box.append(img)

        h_box.append(v_box)

        self.notif_switch = Gtk.Switch.new()
        if self.get_setting(self.SETTING.NOTIFICATIONS) is True:
            self.notif_switch.set_state(True) 
        self.notif_switch.set_halign(Gtk.Align.CENTER)
        self.notif_switch.set_valign(Gtk.Align.CENTER)
        h_box.append(self.notif_switch)

        list_box_row.set_child(h_box)
        list_box_row.set_selectable(False)
        list_box.append(list_box_row)

        ###########################################################
        # END Notifications
        ###########################################################


        ###########################################################
        # Flag
        ###########################################################

        list_box_row = Gtk.ListBoxRow.new()
        h_box = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, 0)
        v_box = Gtk.Box.new(Gtk.Orientation.VERTICAL, 0)
        v_box.set_hexpand(True)

        label = Gtk.Label.new(gettext.gettext("Show Flag"))
        v_box.set_valign(Gtk.Align.CENTER)
        v_box.append(label)

        img = Gtk.Image.new()
        img.set_from_icon_name("preferences-desktop-locale-symbolic")

        h_box.append(img)

        h_box.append(v_box)

        self.flag_switch = Gtk.Switch.new()
        if self.get_setting(self.SETTING.SHOW_FLAG) is True:
            self.flag_switch.set_state(True) 
        self.flag_switch.set_halign(Gtk.Align.CENTER)
        self.flag_switch.set_valign(Gtk.Align.CENTER)
        h_box.append(self.flag_switch)

        list_box_row.set_child(h_box)
        list_box_row.set_selectable(False)
        list_box.append(list_box_row)

        ###########################################################
        # END FLAG
        ###########################################################

        ###########################################################
        # Dark Theme
        ###########################################################

        list_box_row = Gtk.ListBoxRow.new()
        h_box = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, 0)
        v_box = Gtk.Box.new(Gtk.Orientation.VERTICAL, 0)
        v_box.set_hexpand(True)

        label = Gtk.Label.new(gettext.gettext("Dark Theme"))
        v_box.set_valign(Gtk.Align.CENTER)
        v_box.append(label)

        img = Gtk.Image.new()
        img.set_from_icon_name("weather-clear-night-symbolic")

        h_box.append(img)

        h_box.append(v_box)

        self.dark_theme_switch = Gtk.Switch.new()
        if self.get_setting(self.SETTING.DARK_THEME) is True:
            self.dark_theme_switch.set_state(True) 
        self.dark_theme_switch.set_halign(Gtk.Align.CENTER)
        self.dark_theme_switch.set_valign(Gtk.Align.CENTER)
        h_box.append(self.dark_theme_switch)

        list_box_row.set_child(h_box)
        list_box_row.set_selectable(False)
        list_box.append(list_box_row)

        ###########################################################
        # END Dark Theme
        ###########################################################

        
        #attach to pref box
        frame.set_child(list_box)
        self.pref_box.append(frame)



        self.remove_all_vpn_btn = Gtk.Button.new_with_label(gettext.gettext("Delete All VPN Connections!"))
        self.remove_all_vpn_btn.get_style_context().add_class("m-6")
        self.remove_all_vpn_btn.get_style_context().add_class("destructive-action")
        self.remove_all_vpn_btn.set_valign(Gtk.Align.END)
        self.remove_all_vpn_btn.set_vexpand(True)
        self.pref_box.append(self.remove_all_vpn_btn)
        self.remove_all_vpn_btn.set_visible(True if self.get_setting(self.SETTING.MANAGER) == "networkmanager" else False)
        self.pref_box.set_vexpand(True)
        self.window.set_child(self.stack)


        ###########################################################
        # Manager (Tab - 3)
        ###########################################################

        
        box = Gtk.Box.new(Gtk.Orientation.VERTICAL, 4)

        label = Gtk.Label.new(gettext.gettext("Backend"))
        label.set_halign(Gtk.Align.START)
        label.get_style_context().add_class("bold")
        label.get_style_context().add_class("m-4")
        box.append(label)

        self.combobox = Gtk.ComboBoxText()
        version, ovpn_supported = NetworkManager().get_version()
        if (version != None and ovpn_supported):
            self.combobox.append("networkmanager", gettext.gettext("{} (OpenVPN 2)".format(version)))
        
        ovpn3_version = OpenVPN3().get_version()
        if ovpn3_version is not None:
            self.combobox.append("openvpn3", gettext.gettext("OpenVPN 3 {}".format(ovpn3_version.decode("utf-8"))))
        
        if (manager := self.get_setting(self.SETTING.MANAGER)) is not None:
            self.combobox.set_property("active-id", manager)
        self.combobox.get_style_context().add_class("mlr-6")
        box.append(self.combobox)
        
        note = Gtk.Label.new(gettext.gettext(gettext.gettext("* Changes will take effect ONLY after restart.")))
        note.get_style_context().add_class("dim-label")
        note.set_valign(Gtk.Align.END)
        note.set_vexpand(True)
        note.get_style_context().add_class("mb-4")
        box.append(note)

        self.backend_box.append(box)

        ###########################################################
        # END Manager
        ###########################################################
        

        #connect signals
        self.reset_btn.connect("clicked", self.signals.on_reset_btn_clicked, [entry, self.username_entry, self.password_entry], [self.ca_chooser_btn], [self.ask_auth_switch, self.notif_switch, self.flag_switch, self.dark_theme_switch], self.window)
        entry.connect("changed", self.signals.process_config_entry, self.revealer)
        zip_file_chooser_dialog.connect("response", self.signals.process_zip, entry, self.revealer)
        self.validate_btn.connect("clicked", self.signals.on_validate_btn_click, entry, self.ca_chooser_btn, self.spinner)
        self.username_entry.connect("changed", self.signals.process_username)
        self.password_entry.connect("changed", self.signals.process_password)
        ca_file_chooser_dialog.connect("response", self.signals.process_ca, self.ca_chooser_btn)
        self.ask_auth_switch.connect("state-set", self.signals.req_auth ,self.user_pass_ca_box)
        self.notif_switch.connect("state-set", self.signals.notification_set)
        self.flag_switch.connect("state-set", self.signals.show_flag_set)
        self.dark_theme_switch.connect("state-set", self.signals.dark_theme_set)
        self.remove_all_vpn_btn.connect("clicked", lambda _: NetworkManager().delete_all_vpn_connections())
        self.combobox.connect("changed", lambda box: self.set_setting(self.SETTING.MANAGER, box.get_property("active_id")) )


    def show(self):
        self.setup()
        self.window.show()


class Signals(Base):

    def __init__(self):
        super().__init__()

    def process_config_entry(self, entry, revealer):
        if entry.get_text() != "":
            self.set_setting(self.SETTING.REMOTE, entry.get_text())
            revealer.set_reveal_child(True)
        else:
            self.set_setting(self.SETTING.REMOTE, None)
            revealer.set_reveal_child(False)

    def process_zip(self, chooser, response, entry, revealer):
        path = chooser.get_file().get_path()
        eb = Gtk.EntryBuffer()
        eb.set_text(path, len(path))
        self.set_setting(self.SETTING.REMOTE, path)
        entry.set_buffer(eb)
        revealer.set_reveal_child(True)


    def req_auth(self, swich, state, auth_box):
        self.set_setting(self.SETTING.REQ_AUTH, state)
        if state:
            auth_box.set_sensitive(True)
        else:
            auth_box.set_sensitive(False)

    def process_username(self, entry):
        if entry.get_text() != "":
            self.set_setting(self.SETTING.AUTH_USER, entry.get_text())
        else:
            self.set_setting(self.SETTING.AUTH_USER, None)


    def process_password(self, entry):

        def on_password_stored(source, result):
            try:
                is_pwd_stored = Secret.password_store_finish(result)
                logger.debug(is_pwd_stored)
            except Exception:
                #save as plain text
                self.set_setting(self.SETTING.AUTH_PASS, entry.get_text())
                logger.warning("Password saved as plain text!") 


        if entry.get_text() != "":
            attributes = { "username": self.get_setting(self.SETTING.AUTH_USER)}
            if attributes["username"] is None:
                entry.set_text("")
                return
            Secret.password_store(self.EOVPN_SECRET_SCHEMA, attributes, Secret.COLLECTION_DEFAULT,
                                                    "password", entry.get_text(), None, on_password_stored)
        else:
            self.set_setting(self.SETTING.AUTH_PASS, None)

    def process_ca(self, chooser, response, button):
        if response == Gtk.ResponseType.ACCEPT:
            ca_path = chooser.get_file().get_path()
            if is_selinux_enforcing():
                home_dir = GLib.get_home_dir()
                se_friendly_path = os.path.join(home_dir, ".cert")
                if not os.path.exists(se_friendly_path):
                    os.mkdir(se_friendly_path)
                shutil.copy(ca_path, se_friendly_path)
                self.set_setting(self.SETTING.CA, os.path.join(se_friendly_path, os.path.basename(ca_path)))
            else:
                self.set_setting(self.SETTING.CA, ca_path)
            button.set_label(chooser.get_file().get_basename())      

    def notification_set(self, switch, state):
        self.set_setting(self.SETTING.NOTIFICATIONS, state)

    def show_flag_set(self, switch, state):
        self.set_setting(self.SETTING.SHOW_FLAG, state)
        if state:
            self.retrieve(StorageItem.FLAG).show()
        else:
            self.retrieve(StorageItem.FLAG).hide()

    def dark_theme_set(self, switch, state):
        gtk_settings = Gtk.Settings().get_default()
        self.set_setting(self.SETTING.DARK_THEME, state)
        gtk_settings.set_property("gtk-application-prefer-dark-theme", state)


    def on_reset_btn_clicked(self, button, entries, buttons, switches, window):
        self.reset_all_settings()
        
        try:
            shutil.rmtree(os.path.join(self.EOVPN_CONFIG_DIR, "CONFIGS"))
        except Exception:
            pass    

        for e in entries:
            e.set_text('')

        for b in buttons:
            b.set_label('(None)')     

        for s in switches:
            s.set_state(False)

        GLib.idle_add(self.remove_only, True)

        #default values
        switches[0].set_state(False) #Notifications
        switches[1].set_state(True) #Flag
        switches[2].set_state(False) #Dark Theme
        self.retrieve(StorageItem.FLAG).hide()


    def on_validate_btn_click(self, button, entry, ca_button, spinner):
        self.validate_and_load(spinner, ca_button)