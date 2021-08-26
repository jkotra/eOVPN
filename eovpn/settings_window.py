import json
import logging
import os
from os import path, stat
from urllib.parse import urlparse
import shutil
import gettext

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
        button.set_margin_start(4)
        username_box.append(button)
        self.username_entry = Gtk.Entry.new()
        self.username_entry.set_hexpand(True)
        self.username_entry.set_margin_start(6)
        self.username_entry.set_margin_end(6)
        username_box.append(self.username_entry)

        #password
        password_box = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, 0)
        button = Gtk.Button.new_from_icon_name("dialog-password-symbolic")
        button.set_margin_start(4)
        password_box.append(button)
        self.password_entry = Gtk.PasswordEntry.new()
        self.password_entry.set_show_peek_icon(True)
        self.password_entry.set_hexpand(True)
        self.password_entry.set_margin_start(6)
        self.password_entry.set_margin_end(6)
        password_box.append(self.password_entry)

        #CA
        ca_box = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, 0)
        button = Gtk.Button.new_from_icon_name("application-certificate-symbolic")
        button.set_margin_start(4)
        ca_box.append(button)
        self.ca_chooser_btn = Gtk.Button.new_with_label("(None)")
        self.ca_chooser_btn.set_hexpand(True)
        self.ca_chooser_btn.set_margin_start(6)
        self.ca_chooser_btn.set_margin_end(6)

        #Filechooserdialog
        file_chooser_dialog = Gtk.FileChooserNative(action=Gtk.FileChooserAction.OPEN)
        
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

            if (password := self.get_setting(self.SETTING.AUTH_PASS)) is not None:
                # load from keyring
                pass


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
        self.notif_switch.set_halign(Gtk.Align.CENTER)
        self.notif_switch.set_valign(Gtk.Align.CENTER)
        h_box.append(self.notif_switch)

        list_box_row.set_child(h_box)
        list_box_row.set_selectable(False)
        list_box.append(list_box_row)


        ###########FLAG###########

        # Notifications
        list_box_row = Gtk.ListBoxRow.new()
        h_box = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, 0)
        v_box = Gtk.Box.new(Gtk.Orientation.VERTICAL, 0)
        v_box.set_hexpand(True)

        label = Gtk.Label.new("Show Flag")
        v_box.set_valign(Gtk.Align.CENTER)
        v_box.append(label)

        img = Gtk.Image.new()
        img.set_from_resource(self.EOVPN_GRESOURCE_PREFIX + "/icons/flag.svg")

        h_box.append(img)

        h_box.append(v_box)

        self.flag_switch = Gtk.Switch.new()
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
        self.window.set_child(self.stack)
        

        #connect signals
        self.reset_btn.connect("clicked", self.signals.on_reset_btn_clicked, [entry, self.username_entry, self.password_entry], [self.ca_chooser_btn], [self.ask_auth_switch, self.notif_switch, self.flag_switch])
        entry.connect("changed", self.signals.process_config_entry, self.revealer)
        self.validate_btn.connect("clicked", self.signals.on_validate_btn_click)
        self.username_entry.connect("changed", self.signals.process_username)
        self.password_entry.connect("changed", self.signals.process_password)
        file_chooser_dialog.connect("response", self.signals.process_ca, self.ca_chooser_btn)
        self.ca_chooser_btn.connect("clicked", choose_ca)
        self.ask_auth_switch.connect("state-set", self.signals.req_auth ,self.user_pass_ca_box)
        self.notif_switch.connect("state-set", self.signals.notification_set)
        self.flag_switch.connect("state-set", self.signals.show_flag_set)


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
            self.set_setting(self.SETTING.AUTH_PASS, entry.get_text())
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

    def on_reset_btn_clicked(self, button, entries, buttons, switches):
        self.reset_all_settings()

        for e in entries:
            e.set_text('')

        for b in buttons:
            b.set_label('(None)')     

        for s in switches:
            s.set_state(False)

    def on_validate_btn_click(self, button):
        pass
