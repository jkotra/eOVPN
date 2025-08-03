
import logging
import os
import shutil
import gettext

import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, Gio, GLib, Secret

from .eovpn_base import Base, StorageItem

from .connection_manager import NetworkManager, OpenVPN3

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
    
    def generate_option_row(self, name, icon_name, switch_state):
        list_box_row = Gtk.ListBoxRow.new()
        h_box = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, 0)
        v_box = Gtk.Box.new(Gtk.Orientation.VERTICAL, 0)
        v_box.set_hexpand(True)

        label = Gtk.Label.new(name)
        v_box.set_valign(Gtk.Align.CENTER)
        v_box.append(label)

        img = Gtk.Image.new()
        img.set_from_icon_name(icon_name)
        h_box.append(img)

        h_box.append(v_box)

        switch = Gtk.Switch.new()
        switch.set_halign(Gtk.Align.CENTER)
        switch.set_valign(Gtk.Align.CENTER)
        switch.set_state(switch_state)
        switch.set_active(switch_state) 

        h_box.append(switch)

        list_box_row.set_child(h_box)
        list_box_row.set_selectable(False)

        return list_box_row, switch

    def setup(self):
        
        self.reset_btn = Gtk.Button.new_with_label(gettext.gettext("Reset"))
        self.reset_btn.add_css_class("destructive-action")
        self.header = self.get_object("settings_header_bar")
        self.header.pack_start(self.reset_btn)

        self.spinner = Gtk.Spinner()

        self.tick_mark = Gtk.Image()
        self.tick_mark.set_from_icon_name("object-select-symbolic")
        self.tick_mark.hide()
        self.store("settings_tick", self.tick_mark)
        
        self.header.pack_end(self.tick_mark)
        self.header.pack_end(self.spinner)
        
        self.stack = Gtk.Stack.new()
        self.stack.set_transition_type(Gtk.StackTransitionType.SLIDE_LEFT)
        self.stack_switcher = Gtk.StackSwitcher.new()
        self.stack_switcher.set_stack(self.stack)
        self.header.set_title_widget(self.stack_switcher)

        self.main_box = Gtk.Box.new(Gtk.Orientation.VERTICAL, 4)
        self.main_box.set_valign(Gtk.Align.CENTER)
        self.main_box.add_css_class("m-6")

        self.pref_box = Gtk.Box.new(Gtk.Orientation.VERTICAL, 0)
        self.backend_box = Gtk.Box.new(Gtk.Orientation.VERTICAL, 0)

        self.stack.add_titled(self.main_box, "setup", gettext.gettext("Setup"))
        self.stack.add_titled(self.pref_box, "general", gettext.gettext("General"))
        self.stack.add_titled(self.backend_box, "Backend", gettext.gettext("Backend"))

        
        label = Gtk.Label.new(gettext.gettext("Configuration Source"))
        label.set_halign(Gtk.Align.START)
        label.add_css_class("bold")
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
        self.validate_btn.add_css_class("suggested-action")

        self.revealer.set_child(self.validate_btn)
        self.main_box.append(self.revealer)
        self.revealer.set_reveal_child(False)

        self.auth_box = Gtk.Box.new(Gtk.Orientation.VERTICAL, 0)

        ask_auth_box = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, 4)
        ask_auth_box.add_css_class("m-4")
        label = Gtk.Label.new(gettext.gettext("Authentication"))
        label.set_halign(Gtk.Align.START)
        label.add_css_class("bold")
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
        ca_box.add_css_class("mb-4")
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
        self.user_pass_ca_box.add_css_class("mt-4")
        self.user_pass_ca_box.append(username_box)
        self.user_pass_ca_box.append(password_box)
        self.user_pass_ca_box.append(ca_box)
        self.user_pass_ca_box.set_sensitive(False)
        self.auth_box.append(self.user_pass_ca_box)

        self.main_box.append(self.auth_box)
        if (auth_status_opt := self.get_setting(self.SETTING.REQ_AUTH)) is not None:
            self.ask_auth_switch.set_state(auth_status_opt)
            self.ask_auth_switch.set_active(auth_status_opt)
            self.user_pass_ca_box.set_sensitive(auth_status_opt)

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


        ###########################################################
        # Prefs - Setup
        ###########################################################
        frame = Gtk.Frame.new()
        list_box = Gtk.ListBox.new()
        frame.add_css_class("m-10")
        list_box.add_css_class("rich-list")

        self.switches = []
        self.switches.append(self.ask_auth_switch)

        row, switch = self.generate_option_row(gettext.gettext("Notifications"), "user-available-symbolic", self.get_setting(self.SETTING.NOTIFICATIONS))
        switch.connect("state-set", self.signals.notification_set)
        self.switches.append(switch)
        list_box.append(row)

        row, switch = self.generate_option_row(gettext.gettext("Flag"), "preferences-desktop-locale-symbolic", self.get_setting(self.SETTING.SHOW_FLAG))
        switch.connect("state-set", self.signals.show_flag_set)
        self.switches.append(switch)
        list_box.append(row)

        row, switch = self.generate_option_row(gettext.gettext("Dark Theme"), "weather-clear-night-symbolic", self.get_setting(self.SETTING.DARK_THEME))
        switch.connect("state-set", self.signals.dark_theme_set)
        self.switches.append(switch)
        list_box.append(row)

        
        #attach to pref box
        frame.set_child(list_box)
        self.pref_box.append(frame)



        self.remove_all_vpn_btn = Gtk.Button.new_with_label(gettext.gettext("Delete All VPN Connections!"))
        self.remove_all_vpn_btn.add_css_class("m-6")
        self.remove_all_vpn_btn.add_css_class("destructive-action")
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
        label.add_css_class("bold")
        label.add_css_class("m-4")
        box.append(label)

        self.combobox = Gtk.ComboBoxText()
        version = NetworkManager(None).version()
        if (version):
            self.combobox.append("networkmanager", gettext.gettext("{} (OpenVPN 2)".format(version)))
        
        try:
            ovpn3_version = OpenVPN3(None).version()
            if (ovpn3_version):
                self.combobox.append("openvpn3", gettext.gettext("OpenVPN 3 {}".format(ovpn3_version)))
        except NameError:
            logger.error("unable to use openvpn3 module!")

        if (manager := self.get_setting(self.SETTING.MANAGER)) is not None:
            self.combobox.set_property("active-id", manager)
        self.combobox.add_css_class("mlr-6")
        box.append(self.combobox)

        self.backend_box.append(box)

        ###########################################################
        # END Manager
        ###########################################################
        

        #connect signals
        self.reset_btn.connect("clicked",
                                self.signals.on_reset_btn_clicked,
                                [entry, self.username_entry, self.password_entry],
                                [self.ca_chooser_btn],
                                self.switches,
                                self.window)
        entry.connect("changed", self.signals.process_config_entry, self.revealer)
        zip_file_chooser_dialog.connect("response", self.signals.process_zip, entry, self.revealer)
        self.validate_btn.connect("clicked", self.signals.on_validate_btn_click, entry, self.ca_chooser_btn, self.spinner)
        self.username_entry.connect("changed", self.signals.process_username)
        self.password_entry.connect("changed", self.signals.process_password)
        ca_file_chooser_dialog.connect("response", self.signals.process_ca, self.ca_chooser_btn)
        self.ask_auth_switch.connect("state-set", self.signals.req_auth ,self.user_pass_ca_box)
        self.remove_all_vpn_btn.connect("clicked", lambda _: NetworkManager(None).delete_all_connections())
        
        self.combobox.connect("changed", self.signals.on_backend_selected)


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
            except Exception as e:
                #save as plain text
                logger.error("error while saving password: %s", e)
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
        self.retrieve(StorageItem.FLAG).hide()

    def on_backend_selected(self, box):
        id = box.get_property("active_id")
        self.set_setting(self.SETTING.MANAGER, id)
        callback = self.retrieve("on_connection_event")
        self.store("CM", {"name": id, "instance": NetworkManager(callback) if id == "networkmanager" else OpenVPN3(callback)})

    def on_validate_btn_click(self, button, entry, ca_button, spinner):
        self.validate_and_load(spinner, ca_button)