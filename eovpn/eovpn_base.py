import os
import shutil
import logging
import threading
import json
import subprocess
import gettext
from pathlib import Path

import gi
gi.require_version('Notify', '0.7')
gi.require_version('Secret', '1')
from gi.repository import GObject, Gtk, Gio, GLib, GdkPixbuf, Notify, Secret

from .utils import download_remote_to_destination

_builder_record = {}
_storage_record = {}


_settings_backup = {}

EOVPN_SECRET_SCHEMA = Secret.Schema.new("com.github.jkotra.eovpn", Secret.SchemaFlags.NONE,
	                                          {
		                                        "username": Secret.SchemaAttributeType.STRING
	                                          }
                                        )

logger = logging.getLogger(__name__)

class ConfigItem(GObject.Object):
    def __init__(self, name, **kwargs):
        super(ConfigItem, self).__init__(**kwargs)
        self.name = name

    def __repr__(self):
        return str(self.name)

class StorageItem:
    MAIN_WINDOW = "main-window"
    SETTINGS_WINDOW = "settings-window"
    LISTBOX = "listbox"
    LISTBOX_ROWS = "listbox-rows"
    LISTSTORE = "liststore"
    CONFIGS_LIST = "listbox-rows-index"
    FLAG = "flag"

class Settings:
    CURRENT_CONNECTED = "current-connected"
    LAST_CONNECTED = "last-connected"
    LAST_CONNECTED_CURSOR = "last-connected-cursor"
    UPDATE_ON_START = "update-on-start"
    CONNECT_ON_LAUNCH = "connect-on-launch"
    NOTIFICATIONS = "notifications"
    MANAGER = "manager"
    REQ_AUTH = "req-auth"
    CA = "ca"
    CA_SET_EXPLICIT = "ca-set-explicit"
    REMOTE_TYPE = "remote-type"
    REMOTE = "remote"
    REMOTE_SAVEPATH = "remote-savepath"
    AUTH_USER = "auth-user"
    AUTH_PASS = "auth-pass"
    NM_ACTIVE_UUID = "nm-active-uuid"
    SHOW_FLAG = "show-flag"
    LISTBOX_V_ADJUST = "listbox-v-adjust"
    LAYOUT = "layout"
    DARK_THEME = "dark-theme"

    all_settings = ["current-connected", "last-connected", "last-connected-cursor", "update-on-start", "connect-on-launch",
    "notifications", "manager", "req-auth", "ca", "ca-set-explicit", "remote-type", "remote", "remote-savepath", "auth-user", "auth-pass", "nm-active-uuid", "show-flag", "listbox-v-adjust", "layout", "dark-theme"]

class Base:

    def __init__(self):
        metadata = json.loads(open(os.path.dirname(__file__) + "/" + "metadata.json", "r").read())
        self.APP_NAME = metadata["APP_NAME"]
        self.APP_ID = metadata["APP_ID"]
        self.APP_VERSION = metadata["APP_VERSION"]
        self.APP_COMMIT = metadata["COMMIT"]
        self.AUTHOR = metadata["AUTHOR"]
        self.AUTHOR_MAIL = metadata["AUTHOR_MAIL"]
        self.AUTHOR_MAIL_SECONDARY = metadata["AUTHOR_MAIL_SECONDARY"]
        
        # tip to translators - add yourself to the dict.
        #
        #   ex: "Name": ["Lang"]
        #
        self.TRANSLATORS = {
        #    "Jagadeesh Kotra": ["Telugu"],
        }

        self.EOVPN_SECRET_SCHEMA = EOVPN_SECRET_SCHEMA


        self.EOVPN_CONFIG_DIR = os.path.join(GLib.get_user_config_dir(), "eovpn")
        self.EOVPN_OVPN_CONFIG_DIR = os.path.join(self.EOVPN_CONFIG_DIR, "CONFIGS")
        self.EOVPN_GRESOURCE_PREFIX = "/com/github/jkotra/" + self.APP_NAME.lower()
        self.EOVPN_CSS = self.EOVPN_GRESOURCE_PREFIX + "/css/main.css"
        self.SETTING = Settings()
        self.__settings = Gio.Settings.new(self.APP_ID)
    
    def get_builder(self, ui_resource_name):
        if ui_resource_name not in _builder_record.keys():
            builder = Gtk.Builder()
            builder.add_from_resource(self.EOVPN_GRESOURCE_PREFIX + "/ui/" + ui_resource_name)
            _builder_record[ui_resource_name] = builder
            return builder
        else:
            return _builder_record[ui_resource_name]

    def store(self, item, obj):
        _storage_record[item] = obj

    def retrieve(self, item):
        return _storage_record[item]

    def send_connected_notification(self):
        if self.get_setting(self.SETTING.NOTIFICATIONS) is False:
            return
        Notify.init("com.github.jkotra.eovpn")
        notif = Notify.Notification.new("Connected", "Connected to VPN")
        pixbuf = GdkPixbuf.Pixbuf.new_from_resource_at_scale(self.EOVPN_GRESOURCE_PREFIX + "/icons/notification_connected.svg",
                                                             128,
                                                             -1,
                                                             True)
        notif.set_image_from_pixbuf(pixbuf)
        notif.show()

    def send_disconnected_notification(self):
        if self.get_setting(self.SETTING.NOTIFICATIONS) is False:
            return
        Notify.init("com.github.jkotra.eovpn")
        notif = Notify.Notification.new("Disconnected", "Disconnected from VPN")
        pixbuf = GdkPixbuf.Pixbuf.new_from_resource_at_scale(self.EOVPN_GRESOURCE_PREFIX + "/icons/notification_disconnected.svg",
                                                             128,
                                                             -1,
                                                             True)
        notif.set_image_from_pixbuf(pixbuf)
        notif.show()

    def send_error_notification(self, error_message):
        if self.get_setting(self.SETTING.NOTIFICATIONS) is False:
            return
        Notify.init("com.github.jkotra.eovpn")
        notif = Notify.Notification.new("Error", error_message)
        pixbuf = GdkPixbuf.Pixbuf.new_from_resource_at_scale(self.EOVPN_GRESOURCE_PREFIX + "/icons/notification_disconnected.svg",
                                                             128,
                                                             -1,
                                                             True)
        notif.set_image_from_pixbuf(pixbuf)
        notif.show()

    def get_country_pixbuf(self, country_code):

        try:
            return GdkPixbuf.Pixbuf.new_from_resource_at_scale(self.EOVPN_GRESOURCE_PREFIX + "/country_flags/svg/" + country_code + ".svg",
                                                               -1,
                                                               128,
                                                               True)
        except Exception as e:
            logger.error(str(e))
            return GdkPixbuf.Pixbuf.new_from_resource_at_scale(self.EOVPN_GRESOURCE_PREFIX + "/country_flags/svg/uno.svg",
                                                               -1,
                                                               128,
                                                               True)

    def send_notification(self, action, message, connection_event=None):
        Notify.init("com.github.jkotra.eovpn")
        notif = Notify.Notification.new(action, message)
        if connection_event is True:
            notif.set_image_from_pixbuf(self.get_image("notification_connected.svg", "icons", (64, 64)))
        elif connection_event is False:
            notif.set_image_from_pixbuf(self.get_image("notification_disconnected.svg", "icons", (64,64)))     
        else:
            notif.set_image_from_pixbuf(self.get_image("com.github.jkotra.eovpn.svg", "icons", (64,64)))   
        notif.show()

    def get_setting(self, key):
        v = self.__settings.get_value(key)
        v_type = v.get_type_string()

        if v_type == 'b':
            v = v.get_boolean()
        elif v_type == 'i':
            v = v.get_int32()
        elif v_type == 's':
            v = v.get_string()
            if v == "null":
                v = None
        elif v_type == "d":
            v = v.get_double()        
        else:
            pass

        logger.debug("{} {}".format(key, v))
        return v            

    def set_setting(self, key, value):
        g_value = None

        if value is None:
            g_value = self.__settings.reset(key)
            return

        if type(value) is bool:
            g_value = GLib.Variant.new_boolean(value)
        if type(value) is int:
            g_value = GLib.Variant.new_int32(value)
        if type(value) is float:
            g_value = GLib.Variant.new_double(value)    
        if type(value) is str:
            g_value = GLib.Variant.new_string(value)
        else:
            pass
        
        logger.debug("{} {}".format(key, g_value))
        if g_value is not None:
            self.__settings.set_value(key, g_value)

    def reset_all_settings(self):
        for key in self.SETTING.all_settings:

            #backup first
            v = self.__settings.get_value(key)
            _settings_backup[key] = v

            #reset
            self.__settings.reset(key)
        self.__settings.sync()    
    
    def undo_reset_settings(self):
        for k,v in _settings_backup.items():
            self.__settings.set_value(k,v) 
        self.__settings.sync()
    
    def reset_paths(self):
        if os.path.exists(self.EOVPN_OVPN_CONFIG_DIR):
            if len(os.listdir(self.EOVPN_OVPN_CONFIG_DIR)) > 1:
                shutil.rmtree(self.EOVPN_OVPN_CONFIG_DIR)
        else:
            os.makedirs(self.EOVPN_OVPN_CONFIG_DIR)

    def load_only(self) -> int | None:

        def widget_factory(item):
            row = Gtk.ListBoxRow.new()
            
            # TODO: use `Gtk.Grid` 
            label_and_actions_box = Gtk.Grid()
            label = Gtk.Label.new(str(item))
            label.set_halign(Gtk.Align.START)
            edit_action = Gtk.Button.new_from_icon_name("document-edit-symbolic")
            edit_action.set_has_frame(False)
            edit_action.set_tooltip_text(gettext.gettext("Edit"))
            edit_action.set_margin_end(4)
            edit_action.set_halign(Gtk.Align.END)
            edit_action.set_hexpand(True)
            edit_action.set_visible(False)
            edit_action.get_style_context().add_class("btn-no-dec")
            f = Path(self.EOVPN_OVPN_CONFIG_DIR).joinpath(str(item))
            edit_action.connect("clicked", lambda w: subprocess.run(["xdg-open", str(f)]) )

            label_and_actions_box.attach(label, 0, 0, 1, 1)
            label_and_actions_box.attach(edit_action, 1, 0, 1, 1)
            row.set_child(label_and_actions_box)
            self.retrieve(StorageItem.LISTBOX_ROWS).append(row)
            return row

        box = self.retrieve(StorageItem.LISTBOX)
        
        try:
            configs = os.listdir(self.EOVPN_OVPN_CONFIG_DIR)
            configs.sort()
        except:
            configs = []

        liststore = Gio.ListStore.new(ConfigItem)
        box.bind_model(liststore, widget_factory)
        
        self.store(StorageItem.LISTSTORE, liststore)
        self.store(StorageItem.CONFIGS_LIST, configs)  
        self.store(StorageItem.LISTBOX_ROWS, [])  

        for file in configs:
            if not file.endswith("ovpn"):
                continue
            liststore.append(ConfigItem(file))
        return len(configs)

    def remove_only(self, remove_path=False):
        if remove_path:
            self.reset_paths()
        self.retrieve(StorageItem.LISTSTORE).remove_all()
        self.store(StorageItem.LISTBOX_ROWS, [])
        self.store(StorageItem.CONFIGS_LIST, [])  

    
    
    def validate_and_load(self, spinner=None, ca_button=None):

        if self.get_setting(self.SETTING.REMOTE) is None:
            logger.error("remote is empty!")
            return
        
        def fade_tick(tick):
            if tick.get_opacity() == 0:
                tick.hide()
                return False
            tick.set_opacity(tick.get_opacity() - 0.05)
            return True

        def glib_func():
            self.remove_only()
            n_added = self.load_only()
            if n_added is not None:
                tick = self.retrieve("settings_tick")
                tick.show()
                GLib.timeout_add(15, fade_tick, tick)
            if spinner is not None:
                spinner.stop()    
            return False

        def dispatch():
            cert = download_remote_to_destination(self.get_setting(self.SETTING.REMOTE), self.EOVPN_OVPN_CONFIG_DIR)
            if len(cert) > 0:
                ca_path = os.path.join(self.EOVPN_OVPN_CONFIG_DIR, cert[-1])
                self.set_setting(self.SETTING.CA, ca_path)
                
                if ca_button is not None:
                    # if it's None, assume update is not needed!
                    ca_button.set_label(cert[-1])

            GLib.idle_add(glib_func)

        
        self.reset_paths()
        
        thread = threading.Thread(target=dispatch)
        thread.daemon = True
        thread.start()
        if spinner is not None:
            spinner.start()