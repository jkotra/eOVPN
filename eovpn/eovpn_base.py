import os
import subprocess
import re
import json
import logging
import threading

import gi
gi.require_version('Notify', '0.7')
gi.require_version('Secret', '1')
from gi.repository import Gtk, Gio, GLib, GdkPixbuf, Notify, Secret

eovpn_standalone = {"is_standalone": False, "path": None}
_builder_record = {}
_widget_record = {}

_settings_backup = {}

logger = logging.getLogger(__name__)

def set_standalone(path):
    eovpn_standalone["is_standalone"] = True
    eovpn_standalone["path"] = path

def get_standalone():
    return (eovpn_standalone["is_standalone"], eovpn_standalone["path"])


class Settings:
    CURRENT_CONNECTED = "current-connected"
    LAST_CONNECTED = "last-connected"
    LAST_CONNECTED_CURSOR = "last-connected-cursor"
    UPDATE_ON_START = "update-on-start"
    CONNECT_ON_LAUNCH = "connect-on-launch"
    NOTIFICATIONS = "notifications"
    TREEVIEW_HEIGHT = "treeview-height"
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

    all_settings = ["current-connected", "last-connected", "last-connected-cursor", "update-on-start", "connect-on-launch",
    "notifications", "treeview-height", "manager", "req-auth", "ca", "ca-set-explicit", "remote-type", "remote", "remote-savepath", "auth-user", "auth-pass", "nm-active-uuid"]

class Base:

    def __init__(self):
        self.APP_NAME = "eOVPN"
        self.APP_ID = "com.github.jkotra.eovpn"
        self.APP_VERSION = "0.30"
        self.AUTHOR = "Jagadeesh Kotra"
        self.AUTHOR_MAIL = "jagadeesh@stdin.top"
        self.AUTHOR_MAIL_SECONDARY = "jagadeesh.01101011@gmail.com"
        
        # tip to translators - add yourself to the dict.
        #
        #   ex: "Name": ["Lang"]
        #
        self.TRANSLATORS = {
        #    "Jagadeesh Kotra": ["Telugu"],
        }

        self.EOVPN_SECRET_SCHEMA = Secret.Schema.new(self.APP_ID, Secret.SchemaFlags.NONE,
	                                          {
		                                        "username": Secret.SchemaAttributeType.STRING
	                                          }
                                                    )


        self.EOVPN_CONFIG_DIR = os.path.join(GLib.get_user_config_dir(), "eovpn")
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
    
    def get_widget(self, widget_name):
        if widget_name in _widget_record.keys():
            return _widget_record[widget_name]

    def store_widget(self, name, widget):
        _widget_record[name] = widget


    def get_logo(self):
        img = GdkPixbuf.Pixbuf.new_from_resource_at_scale(self.EOVPN_GRESOURCE_PREFIX + "/icons/com.github.jkotra.eovpn.svg", -1, 128, True)
        return img

    def get_image(self, image_name, image_cat, scale=False):
        img = GdkPixbuf.Pixbuf.new_from_resource(self.EOVPN_GRESOURCE_PREFIX + "/{}/".format(image_cat) + image_name)
        if scale is not False:
            w, h = scale
            img = img.scale_simple(w, h, GdkPixbuf.InterpType.BILINEAR)
        return img


    def get_country_image(self, country_alpha_code):

        try:
            img = GdkPixbuf.Pixbuf.new_from_resource_at_scale(self.EOVPN_GRESOURCE_PREFIX + "/country_flags/svg/" + country_alpha_code.lower() + ".svg", 72, -1, True)
        except Exception as e:
            logger.error(str(e))
            img = GdkPixbuf.Pixbuf.new_from_resource_at_scale(self.EOVPN_GRESOURCE_PREFIX + "/country_flags/svg/uno.svg", 72, -1, True)

        return img

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

class ThreadManager:
    
    def create(self, function_to_run, arguments, is_daemon=False, join=False):

        if arguments is None:
            th = threading.Thread(target=function_to_run)
        else:
            th = threading.Thread(target=function_to_run, args=arguments)
        th.daemon = is_daemon
        th.start()
        
        if join:
            self._join_thread(th)
    
    def _join_thread(self, thread):
        thread.join()
        logger.info("{} joined!".format(str(thread)))