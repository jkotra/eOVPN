import json
import logging
import os
from os import path, stat
from urllib.parse import urlparse
import shutil
import zipfile
import gettext
import re
import io
import gettext

from gi.repository import Gtk, Gio, GLib, Gdk, Secret

from .eovpn_base import Base, ThreadManager
from .connection_manager import eOVPNConnectionManager
from .utils import validate_remote

from .networkmanager.bindings import NetworkManager

logger = logging.getLogger(__name__)



class SettingsWindow(Base, Gtk.Builder):
    def __init__(self):
        super().__init__()
        Gtk.Builder.__init__(self)
        self.signals = Signals()

        self.add_from_resource(self.EOVPN_GRESOURCE_PREFIX + "/ui/" + "settings.ui")
        self.window = self.get_object("settings_window")
        self.window.set_title("eOVPN Settings")

        self.window.set_transient_for(self.get_widget("main_window"))
        self.window.set_modal(True)
        self.store_widget("settings_window", self.window)

    def setup(self):
        
        self.reset_btn = Gtk.Button.new_with_label(gettext.gettext("Reset"))
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

        self.stack.add_titled(self.main_box, "setup", gettext.gettext("Setup"))
        self.stack.add_titled(self.pref_box, "general", gettext.gettext("General"))

        
        label = Gtk.Label.new(gettext.gettext("Configuration Source"))
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
        self.validate_btn = Gtk.Button.new_with_label(gettext.gettext("Validate & Load"))
        self.validate_btn.get_style_context().add_class("suggested-action")
        self.validate_btn.set_margin_start(12)
        self.validate_btn.set_margin_end(12)

        self.revealer.set_child(self.validate_btn)
        self.main_box.append(self.revealer)
        self.revealer.set_reveal_child(False)

        self.auth_box = Gtk.Box.new(Gtk.Orientation.VERTICAL, 4)
        self.auth_box.set_margin_top(12)

        ask_auth_box = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, 4)
        label = Gtk.Label.new(gettext.gettext("Authentication"))
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
        self.username_entry.set_placeholder_text(gettext.gettext("Username / Email"))
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
        self.password_entry.set_property("placeholder-text", gettext.gettext("Password"))
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

            if (ca := self.get_setting(self.SETTING.CA)) is not None:
                self.ca_chooser_btn.set_label(os.path.basename(ca))  


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


        ###########FLAG###########

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

        #############

        
        #attach to pref box
        frame.set_child(list_box)
        self.pref_box.append(frame)
        self.remove_all_vpn_btn = Gtk.Button.new_with_label(gettext.gettext("Delete All VPN Connections!"))
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
        self.validate_btn.connect("clicked", self.signals.on_validate_btn_click, entry)
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
        if state:
            self.get_widget("flag").show()
        else:
            self.get_widget("flag").hide()

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
        
        rows = self.get_something("config_rows")
        listbox = self.get_widget("config_box")

        for r in rows:
            listbox.remove(r)

        self.store_something("config_rows", [])

        #default values
        switches[0].set_state(False) #Notifications
        switches[1].set_state(True) #Flag
        self.get_widget("flag").hide()


    def on_validate_btn_click(self, button, entry):

        #remove all rows first
        rows = self.get_something("config_rows")
        listbox = self.get_widget("config_box")

        for r in rows:
            listbox.remove(r)

        validate_remote(entry.get_text())
        self.get_something("update_config_func")()