from gi.repository import Gtk, GLib, Gdk, GdkPixbuf, Gio

from .eovpn_base import Base, SettingsManager, ThreadManager
from .settings_window import SettingsWindow
from .log_window import LogWindow
from .about_dialog import AboutWindow
from .openvpn import OpenVPN_eOVPN, is_openvpn_running
import requests
import os
import typing
import json
import re
import subprocess
import logging
import io
import zipfile
import time
import datetime
import psutil

logger = logging.getLogger(__name__)

class MainWindow(Base):
    def __init__(self, app):
        super(MainWindow, self).__init__()
        self.app = app
        self.builder = self.get_builder("main.glade")
        self.builder.connect_signals(MainWindowSignalHandler(self.builder))
        self.window = self.builder.get_object("mainwindow")

        self.window.set_title("eOVPN")
        self.window.set_icon_name(self.APP_ID)

        self.app.add_window(self.window)


    def show(self):
        self.window.show()




class MainWindowSignalHandler(SettingsManager):
    def __init__(self, builder):
        super(MainWindowSignalHandler, self).__init__()
        
        self.builder = builder

        # info box items
        self.status_label = self.builder.get_object("status_lbl")
        self.country_image = self.builder.get_object("country_image")
        self.ip_label = self.builder.get_object("ip_lbl")
        self.location_label = self.builder.get_object("location_lbl")

        self.statusbar = self.builder.get_object("statusbar")
        self.spinner = self.builder.get_object("main_spinner")
        self.config_storage = self.builder.get_object("config_storage")
        self.config_tree = self.builder.get_object("config_treeview")
        self.statusbar_icon = self.builder.get_object("statusbar_icon")
        self.proto_label = self.builder.get_object("openvpn_proto")

        self.config_selected = None
        self.selected_cursor = None
        self.is_connected = False
        self.connect_btn = self.builder.get_object("connect_btn")
        self.update_btn = self.builder.get_object("update_btn")

        #reset session.log
        if os.path.exists(self.EOVPN_CONFIG_DIR) != True:
            os.mkdir(self.EOVPN_CONFIG_DIR)

        self.ovpn = OpenVPN_eOVPN(self.statusbar, self.spinner, self.statusbar_icon)
        self.ovpn.get_version_eovpn(callback=self.on_version)

        self.update_status_ip_loc_flag()

        if self.get_setting("remote_savepath") != None:
            self.ovpn.load_configs_to_tree(self.config_storage, self.get_setting("remote_savepath"))

        if self.get_setting("last_connected") != None:
            if self.get_setting("last_connected_cursor") != None:
                i = self.get_setting("last_connected_cursor")
                self.config_tree.set_cursor(i)
                self.config_tree.scroll_to_cell(i)
                self.config_selected = self.get_setting("last_connected")

                logger.debug("restored cursor= {} | config_selected={}".format(i, self.config_selected))

                if self.get_setting("connect_on_launch"):
                    if self.is_connected is False:
                        self.on_connect_btn_clicked(self.connect_btn)
        
        if self.get_setting("update_on_start"):
            self.on_update_btn_clicked(self.update_btn)


    #callbacks passed to OpenVPN_eOVPN

    def on_connect(self, result):
        logger.debug("result = {}".format(result))
        if result:
            self.update_status_ip_loc_flag()
            self.set_setting("last_connected", self.config_selected)
            self.set_setting("last_connected_cursor", self.selected_cursor)

            logger.debug("cursor={} config={}".format(self.config_selected, self.selected_cursor))
        else:
            self.statusbar.push(1, "Failed to connect!")

    def on_disconnect(self, result):
        logger.debug("result = {}".format(result))
        if result:
            self.update_status_ip_loc_flag()

    def on_version(self, result):
        if result:
            img = self.get_image("openvpn_black.svg","icons", (16,16))
            statusbar_icon = self.builder.get_object("statusbar_icon")
            statusbar_icon.set_from_pixbuf(img)

        if result is False:
            
            self.connect_btn.set_sensitive(False)        

    #end

    def on_menu_exit_clicked(self, window):
        window.close()

    def on_settings_btn_clicked(self, button):
        settings_window = SettingsWindow()
        settings_window.show()

    def on_log_btn_clicked(self, button):
        log_window = LogWindow()
        log_window.show()


    def on_about_btn_clicked(self, button):
        about_window = AboutWindow()
        about_window.show()


    def on_config_treeview_cursor_changed(self, tree):
        model, path = tree.get_selection().get_selected_rows()

        try:
            self.selected_cursor = path[-1].get_indices()[-1]
        except IndexError:
            return False

        try:
            model_iter = model.get_iter(path)
            self.config_selected = model.get_value(model_iter, 0)

        except Exception as e:
            logger.error(str(e))    


    def update_status_ip_loc_flag(self) -> None:
        try:
            ip = requests.get("http://ip-api.com/json/")
            logger.debug(ip.content)
            
        except Exception as e:
            logging.warning(e)
            return False

        if ip.status_code != 200:
            return None
        else:
            ip = json.loads(ip.content)    
        
        ctx = self.status_label.get_style_context()

        if self.ovpn.get_connection_status_eovpn():
            self.status_label.set_text("Connected")
            
            ctx.remove_class("bg_red")
            ctx.add_class("bg_green")
            
            if self.config_selected != None:
                self.ovpn.openvpn_config_set_protocol(os.path.join(self.EOVPN_CONFIG_DIR,
                                                  self.get_setting("remote_savepath"),
                                                  self.config_selected), self.proto_label )
            

            logger.info("connection status = True")
            #change btn text
            self.connect_btn.set_label("Disconnect!")
            self.is_connected = True

        else:

            self.status_label.set_text("Disconnected")
            
            ctx.remove_class("bg_green")
            ctx.add_class("bg_red")

            self.proto_label.hide()

            self.connect_btn.set_label("Connect!")
            
            logger.info("connection status = False")
            self.is_connected = False

        self.ip_label.set_text(ip['query'])
        
        self.location_label.set_text(ip['country'])
        logger.info("location={}".format(ip['country']))

        country_id = ip['countryCode'].lower()
        pic = self.get_country_image(country_id)
        self.country_image.set_from_pixbuf(pic)

    def on_copy_btn_clicked(self, ip):
        ip = ip.get_text()
        clip = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
        clip.set_text(ip, -1)
        logger.info("{} copied to clipboard.".format(ip))

    def on_update_btn_clicked(self, button):
        self.ovpn.download_config(self.get_setting("remote"),
                                  self.get_setting("remote_savepath"),
                                  self.config_storage)


        if not self.get_setting("crt_set_explicit") and self.get_setting("crt") is None:
            crt_re = re.compile(r'.crt')

            files = os.listdir(self.get_setting("remote_savepath"))                       
            crt = list(filter(crt_re.findall, files))

            if len(crt) >= 1:
                self.set_setting("crt", os.path.join(self.get_setting("remote_savepath"),
                                                    crt[-1]))
            

    def on_open_vpn_running_kill_btn_clicked(self, dlg):
        ThreadManager().create(self.ovpn.disconnect_eovpn, (self.on_disconnect,), True)
        dlg.hide()
        return True

    def on_open_vpn_running_cancel_btn_clicked(self, dlg):
        dlg.hide()
        return True

    def on_connect_btn_clicked(self, button):

        log_file = os.path.join(self.EOVPN_CONFIG_DIR, "session.log")

        if self.is_connected:
            ThreadManager().create(self.ovpn.disconnect_eovpn, (self.on_disconnect,), True)
            return True
        
        is_ovpn_running, _ = is_openvpn_running()

        if is_ovpn_running:
            dlg = self.builder.get_object("openvpn_running_dlg")
            dlg.run()
            return False

        try:
            config_file = os.path.join(self.get_setting("remote_savepath"), self.config_selected)
        except TypeError:
            self.statusbar.push(1, "No config selected.")
            self.statusbar_icon.set_from_icon_name("dialog-warning-symbolic", 1)
            return False

        auth_file = None
        crt = None
        
        if self.get_setting("req_auth"):
            auth_file = os.path.join(self.EOVPN_CONFIG_DIR, "auth.txt")

        if self.get_setting("crt") is not None:    
            crt = self.get_setting("crt")
        
        ThreadManager().create(self.ovpn.connect_eovpn, (config_file, auth_file, crt, log_file, self.on_connect),  is_daemon=True)