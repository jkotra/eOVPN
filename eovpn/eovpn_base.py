import gi
gi.require_version('Notify', '0.7')
from gi.repository import Gtk, GLib, GdkPixbuf, Notify
import os
import subprocess
import re
import json
import logging
import threading

eovpn_standalone = {"is_standalone": False, "path": None}
builder_record = {}

logger = logging.getLogger(__name__)

def set_standalone(path):
    eovpn_standalone["is_standalone"] = True
    eovpn_standalone["path"] = path

def get_standalone():
    return (eovpn_standalone["is_standalone"], eovpn_standalone["path"])

class Base:

    def __init__(self):
        self.APP_NAME = "eOVPN"
        self.APP_ID = "com.github.jkotra.eovpn"
        self.APP_VERSION = "0.17.2"
        self.AUTHOR = "Jagadeesh Kotra"
        self.AUTHOR_MAIL = "jagadeesh@stdin.top"
        self.AUTHOR_MAIL_SECONDARY = "jagadeesh.01101011@gmail.com"
        
        self.TRANSLATORS = {
            "Jagadeesh Kotra": ["Telugu"],
            }

        self.EOVPN_CONFIG_DIR = os.path.join(GLib.get_user_config_dir(), "eovpn")
        self.EOVPN_GRESOURCE_PREFIX = "/com/github/jkotra/" + self.APP_NAME.lower()
        self.EOVPN_CSS = self.EOVPN_GRESOURCE_PREFIX + "/css/main.css"
    
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

    def message_dialog(self, title, primary_text, secondary_text):
        messagedialog = Gtk.MessageDialog(message_format="MessageDialog")
        messagedialog.set_title(title)
        messagedialog.set_markup("<span size='12000'><b>{}</b></span>".format(primary_text))
        messagedialog.format_secondary_text(secondary_text)
        messagedialog.add_button("_Close", Gtk.ResponseType.CLOSE)
        messagedialog.run()
        messagedialog.hide()   

class ThreadManager:
    
    def create(self, function_to_run, arguments, is_daemon=False, join=False):

        if arguments is None:
            th = threading.Thread(target=function_to_run)
        else:
            th = threading.Thread(target=function_to_run, args=arguments)
        th.daemon = is_daemon
        th.start()
        
        if join:
            self.__join_thread(th)
    
    def __join_thread(self, thread):

        logger.info("join request for {}".format(str(thread)))
        thread.join()


class SettingsManager(Base):

    
    def __init_config(self) -> bool:
        if os.path.exists(self.EOVPN_CONFIG_DIR + "/settings.json"):
            return True
        else:
            try:
                f = open(self.EOVPN_CONFIG_DIR + "/settings.json", 'w+')

                settings = {}
                f.write(json.dumps(settings, indent=2))

                f.close()
            except Exception as e:
                #TODO - LOG to stdout
                logger.critical(str(e))
                return False

            return True

    def get_setting(self, setting):
        self.__init_config()

        f = open(self.EOVPN_CONFIG_DIR + "/settings.json", 'r')
        content = f.read()
        
        json_content = json.loads(content)
        try:
            return json_content[setting]
        except:
            return None

    def set_setting(self, setting, value):
        self.__init_config()

        f = open(self.EOVPN_CONFIG_DIR + "/settings.json", 'r')
        content = f.read()

        json_content = json.loads(content)

        f = open(self.EOVPN_CONFIG_DIR + "/settings.json", 'w')
        json_content[setting] = value
        f.write(json.dumps(json_content, indent=2))
        f.close()

        logger.debug(json_content)