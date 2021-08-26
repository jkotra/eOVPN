import json
import logging
import os
from os import path, stat
from urllib.parse import urlparse
import shutil
import requests
import zipfile
import gettext
import re
import io

from gi.repository import Gtk, Gio, GLib, Gdk, Secret

from .eovpn_base import Base, ThreadManager
from .connection_manager import eOVPNConnectionManager

from .utils import validate_remote
from .utils import load_configs_to_tree
from .utils import download_remote_to_destination
from .utils import message_dialog
from .utils import set_ca_automatic

from .networkmanager.bindings import NetworkManager

logger = logging.getLogger(__name__)

def download_remote_to_destination(remote, destination):

    ovpn = re.compile('.ovpn')
    crt = re.compile(r'.crt|cert|pem')
     
    def make_zip_from_b(content):
        return zipfile.ZipFile(io.BytesIO(content), "r")

    def download_zip(remote):
        remote_c = requests.get(remote, timeout=360)  
        zip_file = make_zip_from_b(remote_c.content)
        return zip_file

    remote = os.path.expanduser(remote)
    zip_file = download_zip(remote)
        
    #list of files inside zip
    files_in_zip = zip_file.namelist()

    configs = list( filter(ovpn.findall, files_in_zip) )
    certs = list( filter(crt.findall, files_in_zip) )
    all_files = configs + certs
    if len(configs) > 0:
        for file_name in all_files:      
            file = zip_file.getinfo(file_name)
            file.filename = os.path.basename(file.filename) #remove nested dir
            logger.info(file.filename)
            zip_file.extract(file, destination)
        return True

    return False  

def validate_remote(remote):
    tmp_path = os.path.join(GLib.get_tmp_dir(), "eovpn_validate")
    logger.debug("tmp_path={}".format(tmp_path))

    return download_remote_to_destination(remote, tmp_path)


class SettingsWindow(Base, Gtk.Builder):
    def __init__(self):
        super().__init__()
        Gtk.Builder.__init__(self)
        self.signals = Signals()

        self.add_from_resource(self.EOVPN_GRESOURCE_PREFIX + "/ui/" + "settings.ui")
        self.window = self.get_object("settings_window")
        self.window.set_title("eOVPN Settings")

        self.window.set_transient_for(self.get_widget("main_window"))
        self.store_widget("settings_window", self.window)

    def setup(self):
        
        self.reset_btn = Gtk.Button.new_with_label("Reset")
        self.reset_btn.get_style_context().add_class("destructive-action")
        self.header = self.get_object("settings_header_bar")
        self.header.pack_start(self.reset_btn)
        
        self.stack = Gtk.Stack.new()
        self.stack.set_transition_type(Gtk.StackTransitionType.SLIDE_LEFT)
        self.stack_switcher = Gtk.StackSwitcher.new()
        self.stack_switcher.set_stack(self.stack)
        self.header.set_title_widget(self.stack_switcher)

        self.main_box = Gtk.Box.new(Gtk.Orientation.VERTICAL, 4)
        self.main_box.set_margin_top(12)
        self.main_box.set_margin_bottom(4)

        self.pref_box = Gtk.Box.new(Gtk.Orientation.VERTICAL, 4)

        self.stack.add_titled(self.main_box, "setup", "Setup")
        self.stack.add_titled(self.pref_box, "general", "General")

        
        label = Gtk.Label.new("Configuration Source")
        label.set_halign(Gtk.Align.START)
        label.set_margin_start(4)
        label.get_style_context().add_class("bold")
        self.main_box.append(label)

        entry = Gtk.Entry.new()
        if (text := self.get_setting(self.SETTING.REMOTE)) is not None:
            entry.set_text(text)
        else:    
            entry.set_placeholder_text("https://example.com/vpn/configs.zip")
        entry.set_margin_start(6)
        entry.set_margin_end(6)
        self.main_box.append(entry)

        self.revealer = Gtk.Revealer.new()
        self.validate_btn = Gtk.Button.new_with_label("Validate")
        self.validate_btn.get_style_context().add_class("suggested-action")
        self.validate_btn.set_margin_start(12)
        self.validate_btn.set_margin_end(12)

        self.revealer.set_child(self.validate_btn)
        self.main_box.append(self.revealer)
        self.revealer.set_reveal_child(False)

        self.auth_box = Gtk.Box.new(Gtk.Orientation.VERTICAL, 4)
        self.auth_box.set_margin_top(12)

        ask_auth_box = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, 4)
        label = Gtk.Label.new("Authentication")
        label.set_halign(Gtk.Align.START)
        label.set_margin_start(4)
        label.get_style_context().add_class("bold")
        ask_auth_box.append(label)

        self.ask_auth_switch = Gtk.Switch.new()
        self.ask_auth_switch.set_halign(Gtk.Align.END)
        self.ask_auth_switch.set_margin_start(12)
        ask_auth_box.append(self.ask_auth_switch)

        self.auth_box.append(ask_auth_box)

        #username
        username_box = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, 0)
        button = Gtk.Button.new_from_icon_name("avatar-default-symbolic")
        button.set_sensitive(False)
        button.set_margin_start(4)
        username_box.append(button)
        self.username_entry = Gtk.Entry.new()
        self.username_entry.set_placeholder_text("Username / Email")
        self.username_entry.set_hexpand(True)
        self.username_entry.set_margin_start(6)
        self.username_entry.set_margin_end(6)
        username_box.append(self.username_entry)

        #password
        password_box = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, 0)
        button = Gtk.Button.new_from_icon_name("dialog-password-symbolic")
        button.set_sensitive(False)
        button.set_margin_start(4)
        password_box.append(button)
        self.password_entry = Gtk.PasswordEntry.new()
        self.password_entry.set_property("placeholder-text", "Password")
        self.password_entry.set_show_peek_icon(True)
        self.password_entry.set_hexpand(True)
        self.password_entry.set_margin_start(6)
        self.password_entry.set_margin_end(6)
        password_box.append(self.password_entry)

        #CA
        ca_box = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, 0)
        button = Gtk.Button.new_from_icon_name("application-certificate-symbolic")
        button.set_sensitive(False)
        button.set_margin_start(4)
        ca_box.append(button)
        self.ca_chooser_btn = Gtk.Button.new_with_label("(None)")
        self.ca_chooser_btn.set_hexpand(True)
        self.ca_chooser_btn.set_margin_start(6)
        self.ca_chooser_btn.set_margin_end(6)

        #Filechooserdialog
        file_chooser_dialog = Gtk.FileChooserNative(action=Gtk.FileChooserAction.OPEN)
        file_chooser_dialog.set_transient_for(self.window)
        ca_filter = Gtk.FileFilter()
        ca_filter.add_mime_type("application/pkix-cert")
        file_chooser_dialog.add_filter(ca_filter)

        
        def choose_ca(button):
            file_chooser_dialog.show()

        ca_box.append(self.ca_chooser_btn)
        
        self.user_pass_ca_box = Gtk.Box.new(Gtk.Orientation.VERTICAL, 4)
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
                if (password := Secret.password_lookup_sync(self.EOVPN_SECRET_SCHEMA, {"username": username}, None)) is not None:
                    self.password_entry.set_text(password)


        #Prefs - Setup
        frame = Gtk.Frame.new()
        list_box = Gtk.ListBox.new()
        frame.set_margin_start(20)
        frame.set_margin_end(20)
        frame.set_margin_top(20)
        frame.set_margin_bottom(20)
        list_box.get_style_context().add_class("rich-list")
        
        # Notifications
        list_box_row = Gtk.ListBoxRow.new()
        h_box = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, 0)
        v_box = Gtk.Box.new(Gtk.Orientation.VERTICAL, 0)
        v_box.set_hexpand(True)

        label = Gtk.Label.new("Notifications")
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


        ###########FLAG###########

        list_box_row = Gtk.ListBoxRow.new()
        h_box = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, 0)
        v_box = Gtk.Box.new(Gtk.Orientation.VERTICAL, 0)
        v_box.set_hexpand(True)

        label = Gtk.Label.new("Show Flag")
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

        #############

        
        #attach to pref box
        frame.set_child(list_box)
        self.pref_box.append(frame)
        self.remove_all_vpn_btn = Gtk.Button.new_with_label("Delete All VPN Connections!")
        self.remove_all_vpn_btn.set_margin_start(4)
        self.remove_all_vpn_btn.set_margin_end(4)
        self.remove_all_vpn_btn.set_margin_bottom(8)
        self.remove_all_vpn_btn.set_margin_top(8)
        self.remove_all_vpn_btn.get_style_context().add_class("destructive-action")
        self.remove_all_vpn_btn.set_valign(Gtk.Align.END)
        self.remove_all_vpn_btn.set_vexpand(True)
        self.pref_box.append(self.remove_all_vpn_btn)
        self.pref_box.set_vexpand(True)
        self.window.set_child(self.stack)
        

        #connect signals
        self.reset_btn.connect("clicked", self.signals.on_reset_btn_clicked, [entry, self.username_entry, self.password_entry], [self.ca_chooser_btn], [self.ask_auth_switch, self.notif_switch, self.flag_switch], self.window)
        entry.connect("changed", self.signals.process_config_entry, self.revealer)
        self.validate_btn.connect("clicked", self.signals.on_validate_btn_click, entry, self.window)
        self.username_entry.connect("changed", self.signals.process_username)
        self.password_entry.connect("changed", self.signals.process_password)
        file_chooser_dialog.connect("response", self.signals.process_ca, self.ca_chooser_btn)
        self.ca_chooser_btn.connect("clicked", choose_ca)
        self.ask_auth_switch.connect("state-set", self.signals.req_auth ,self.user_pass_ca_box)
        self.notif_switch.connect("state-set", self.signals.notification_set)
        self.flag_switch.connect("state-set", self.signals.show_flag_set)
        self.remove_all_vpn_btn.connect("clicked", lambda _: NetworkManager().delete_all_vpn_connections())


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
        if entry.get_text() != "":
            attributes = { "username": self.get_setting(self.SETTING.AUTH_USER)}
            if attributes["username"] is None:
                entry.set_text("")
                return
            Secret.password_store(self.EOVPN_SECRET_SCHEMA, attributes, Secret.COLLECTION_DEFAULT,
                                                    "password", entry.get_text(), None)
        else:
            self.set_setting(self.SETTING.AUTH_PASS, None)

    def process_ca(self, chooser, response, button):
        if response == Gtk.ResponseType.ACCEPT:
            self.set_setting(self.SETTING.CA, chooser.get_file().get_path())
            button.set_label(chooser.get_file().get_basename())      

    def notification_set(self, switch, state):
        self.set_setting(self.SETTING.NOTIFICATIONS, state)

    def show_flag_set(self, switch, state):
        self.set_setting(self.SETTING.SHOW_FLAG, state)

    def on_reset_btn_clicked(self, button, entries, buttons, switches, window):
        self.reset_all_settings()

        for e in entries:
            e.set_text('')

        for b in buttons:
            b.set_label('(None)')     

        for s in switches:
            s.set_state(False)

    def on_validate_btn_click(self, button, entry, window):
        if validate_remote(entry.get_text()):
            md = Gtk.MessageDialog()
            md.set_property("message-type", Gtk.MessageType.INFO)
            md.set_transient_for(window)
            md.set_markup("Valid Remote")
            md.add_button("_Ok", 1)
            md.connect("response", lambda x, d: md.hide())
            md.show()