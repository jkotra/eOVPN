from gi.repository import Gtk, GLib, Gdk, GdkPixbuf, Gio

from .eovpn_base import Base, SettingsManager, ThreadManager, get_standalone
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
import socket
import gettext

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
        self.paned = self.builder.get_object("main_paned")
        self.config_storage = self.builder.get_object("config_storage")
        self.config_tree = self.builder.get_object("config_treeview")
        self.statusbar_icon = self.builder.get_object("statusbar_icon")
        self.proto_label = self.builder.get_object("openvpn_proto")

        self.config_selected = None
        self.config_connected = None
        self.selected_cursor = None
        self.proto_override = None #consider true if it's either UDP or TCP
        self.is_connected = False
        self.no_network = False

        self.standalone_mode = False
        self.standalone_path = None

        #load_settings
        self.settings = Gio.Settings.new(self.APP_ID)
        paned_height = self.settings.get_int("treeview-height")
        logger.debug("paned_height={}".format(paned_height))
        
        if paned_height != -1:
            self.paned.set_position(paned_height)
        else:
            self.paned.set_position(350)
        
        #connect_prefs
        self.connect_prefs = self.builder.get_object("connect_prefs")
        self.connect_popover = self.builder.get_object("connect_popover")
        self.connect_prefs_ping_label = self.builder.get_object("connect_menu_ms")
        self.proto_chooser_box = self.builder.get_object("proto_choose_box")

        self.proto_choice = {"tcp": self.builder.get_object("on_connect_prefs_tcp_btn_tick"),
                            "udp": self.builder.get_object("on_connect_prefs_udp_btn_tick")}

        self.country_predetails = {"box": self.builder.get_object("connect_prefs_country_details"),
                                   "sep": self.builder.get_object("country_section_sep"),
                                   "img": self.builder.get_object("connection_prefs_country_image"),
                                   "name": self.builder.get_object("connection_prefs_country_name")}                    
       

        self.menu_view_config = self.builder.get_object("view_config")
        self.connect_btn = self.builder.get_object("connect_btn")
        self.update_btn = self.builder.get_object("update_btn")

        #reset session.log
        if os.path.exists(self.EOVPN_CONFIG_DIR) != True:
            os.mkdir(self.EOVPN_CONFIG_DIR)

        self.ovpn = OpenVPN_eOVPN(self.statusbar, self.spinner, self.statusbar_icon)
        self.ovpn.get_version_eovpn(callback=self.on_version)

        self.update_status_ip_loc_flag()

        is_standalone, ovpn_config = get_standalone()
        if is_standalone:
            logger.info("Standalone Mode!")
            self.config_tree.set_sensitive(False)
            self.connect_btn.connect("clicked", self.on_connect_btn_clicked_standalone)
            self.standalone_mode = True
            self.standalone_path = ovpn_config
            GLib.idle_add(self.on_connect_btn_clicked_standalone, self.connect_btn)


        if self.get_setting("remote_savepath") != None:
            self.ovpn.load_configs_to_tree(self.config_storage, self.get_setting("remote_savepath"))
        
        if self.get_setting("last_connected") != None:
            logger.debug("last_connected = {}".format(self.get_setting("last_connected")))
            if self.get_setting("last_connected_cursor") != None:
                i = self.get_setting("last_connected_cursor")
                self.config_tree.set_cursor(i)
                self.config_tree.scroll_to_cell(i)
                self.config_selected = self.get_setting("last_connected")

                logger.debug("restored cursor = {} | config_selected = {}".format(i, self.config_selected))
                self.menu_view_config.show()

                if self.get_setting("connect_on_launch") and is_standalone == False:
                    if (self.is_connected is False) and (self.no_network is False):
                        self.on_connect_btn_clicked(self.connect_btn)
        
        if self.get_setting("update_on_start") and is_standalone == False:
            self.on_update_btn_clicked(self.update_btn)


    #callbacks passed to OpenVPN_eOVPN

    def on_connect(self, result):
        logger.debug("result = {}".format(result))
        if result:
            self.update_status_ip_loc_flag()
            if not self.standalone_mode:
                self.set_setting("last_connected", self.config_selected)
                self.set_setting("last_connected_cursor", self.selected_cursor)

            #send notification
            if self.get_setting("notifications"):
                self.send_notification("Connected", "Connected to {}".format(self.get_setting("last_connected")), True)            

            logger.debug("saved to config: cursor={} config={}".format(self.config_selected, self.selected_cursor))
        else:
            self.statusbar.push(1, gettext.gettext("Failed to connect!"))

    def on_disconnect(self, result):
        logger.debug("result = {}".format(result))
        if result:
            if self.get_setting("notifications"):
                self.send_notification("Disconnected", "Disconnected from {}".format(
                    self.get_setting("last_connected")
                    ), False)
            self.update_status_ip_loc_flag()

    def on_version(self, result):
        if result:
            img = self.get_image("openvpn_black.svg","icons", (16,16))
            statusbar_icon = self.builder.get_object("statusbar_icon")
            statusbar_icon.set_from_pixbuf(img)

        if result is False:
            self.connect_btn.set_sensitive(False)

    def on_update(self, result):
        logger.debug(result)
        if result:
            self.config_tree.set_cursor(0)
            self.config_tree.scroll_to_cell(0)
    #end

    def on_mainwindow_destroy(self, application):
        paned_height = self.paned.get_position()
        logger.debug("saving paned_height={}".format(paned_height))
        self.settings.set_int("treeview-height", paned_height)
        return True

    def on_menu_exit_clicked(self, window):
        window.close()
    
    def on_connect_prefs_tcp_btn_clicked(self, btn):
        self.proto_override = "TCP"
        self.proto_choice["tcp"].show()
        self.proto_choice["udp"].hide()

    def on_connect_prefs_udp_btn_clicked(self, btn):
        self.proto_override = "UDP"
        self.proto_choice["udp"].show()
        self.proto_choice["tcp"].hide()
  

    #ping
    def on_ping_clicked(self, spinner):

        openvpn_addr = None

        def test_ping():
            
            f = open(os.path.join(self.EOVPN_CONFIG_DIR, self.get_setting("remote_savepath"), self.config_selected)).read()
            for line in f.split("\n"):
                if "remote" in line:
                    openvpn_addr = line.split(" ")[1]
                    break

            logger.debug(openvpn_addr)
            out = subprocess.run(["ping", "-c", "1", openvpn_addr], stdout=subprocess.PIPE)
            out = out.stdout.decode('utf-8')

            ping_re = re.compile(r"time=.*")
            res = ping_re.findall(out)

            self.connect_prefs_ping_label.set_label(res[-1].split("=")[-1])
            self.connect_prefs_ping_label.show()
            
            ip = socket.gethostbyname(openvpn_addr)
            logger.debug(ip)

            ip_req = requests.get("http://ip-api.com/json/{}".format(ip))
            ip_details = json.loads(ip_req.content)
            logger.debug(ip_details)

            country_id = ip_details['countryCode'].lower()
            pic = self.get_country_image(country_id)
            self.country_predetails["img"].set_from_pixbuf(pic)
            self.country_predetails["name"].set_label(ip_details['country'])

            self.country_predetails["box"].show()

            spinner.stop()

        if self.config_selected is not None:
            file = os.path.join(self.EOVPN_CONFIG_DIR, self.get_setting("remote_savepath"), self.config_selected)
            if os.path.isfile(file):
                spinner.start()
                ThreadManager().create(test_ping, (), True)
            else:
                logger.debug("config file dont exist!")
        else:
            logger.debug("self.config_selected is None")                

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
            self.menu_view_config.show()

            #hide ping in connect_prefs
            self.connect_prefs_ping_label.hide()

            #hide all country details section.
            self.country_predetails["box"].hide()

        except IndexError:
            return False

        try:
            model_iter = model.get_iter(path)
            self.config_selected = model.get_value(model_iter, 0)

        except Exception as e:
            logger.error(str(e))    


    def update_status_ip_loc_flag(self) -> None:

        ctx = self.status_label.get_style_context()

        try:
            ip = requests.get("http://ip-api.com/json/")
            logger.debug(ip.content)
            
        except Exception as e:
            logging.warning(e)

            #set no network label and uno image as country.
            ctx.add_class("bg_black")
            self.status_label.set_text(gettext.gettext("No Network"))
            uno = self.get_country_image("uno")
            self.country_image.set_from_pixbuf(uno)
            self.no_network = True

            self.connect_btn.set_sensitive(False)
            return False

        if ip.status_code != 200:
            return None
        else:
            ip = json.loads(ip.content)    
        
        

        if self.ovpn.get_connection_status_eovpn():
            self.status_label.set_text(gettext.gettext("Connected"))
            
            ctx.remove_class("bg_red")
            ctx.add_class("bg_green")
            
            if self.config_selected != None:
                self.ovpn.openvpn_config_set_protocol(os.path.join(self.EOVPN_CONFIG_DIR,
                                                  self.get_setting("remote_savepath"),
                                                  self.config_selected), self.proto_label)
            
            if self.standalone_mode:
                self.ovpn.openvpn_config_set_protocol(self.standalone_path, self.proto_label)

            logger.info("connection status = True")
            #change btn text (this also changes signal we set for standalone mode, which should work fine!)
            self.connect_btn.set_label(gettext.gettext("Disconnect!"))
            self.is_connected = True

            self.proto_chooser_box.set_sensitive(False)

        else:

            self.status_label.set_text(gettext.gettext("Disconnected"))
            
            ctx.remove_class("bg_green")
            ctx.add_class("bg_red")

            self.proto_label.hide()

            self.connect_btn.set_label(gettext.gettext("Connect!"))
            
            logger.info("connection status = False")
            self.is_connected = False

            self.proto_chooser_box.set_sensitive(True)

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
        self.ovpn.download_config_and_update_liststore(self.get_setting("remote"),
                                  self.get_setting("remote_savepath"),
                                  self.config_storage,
                                  self.on_update)
            

    def on_open_vpn_running_kill_btn_clicked(self, dlg):
        ThreadManager().create(self.ovpn.disconnect_eovpn, (self.on_disconnect,), True)
        dlg.hide()
        return True

    def on_open_vpn_running_cancel_btn_clicked(self, dlg):
        dlg.hide()
        return True

    def on_view_config_clicked(self, user_data):

        url = "file://{savepath}/{config}".format(savepath=self.get_setting("remote_savepath"),
                                                  config=self.config_selected)
        Gio.AppInfo.launch_default_for_uri(url)


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
            if self.proto_override is not None:
                config_content = open(config_file, "r").read()
                for line in config_content.split("\n"):
                    if "proto" in line:

                        config_content = config_content.replace(line, "proto " + self.proto_override.lower())

                        f = open(config_file, "w")
                        f.write(config_content)
                        f.close()
                        logger.debug("proto override to {}".format(self.proto_override.lower()))

                        break
        except TypeError:
            self.statusbar.push(1, gettext.gettext("No config selected."))
            self.statusbar_icon.set_from_icon_name("dialog-warning-symbolic", 1)
            return False

        auth_file = None
        crt = None
        
        if self.get_setting("req_auth"):
            auth_file = os.path.join(self.EOVPN_CONFIG_DIR, "auth.txt")

        if self.get_setting("crt") is not None:    
            crt = self.get_setting("crt")
        
        ThreadManager().create(self.ovpn.connect_eovpn, (config_file, auth_file, crt, log_file, self.on_connect),  is_daemon=True)


    def on_connect_btn_clicked_standalone(self, button):
        working_dir = os.path.dirname(self.standalone_path)

        if self.is_connected:
            return False
        
        is_ovpn_running, _ = is_openvpn_running()

        if is_ovpn_running:
            dlg = self.builder.get_object("openvpn_running_dlg")
            dlg.run()
            return False        
        
        log_file = os.path.join(self.EOVPN_CONFIG_DIR, "session.log")

        config_file = self.standalone_path
        
        auth_file = None
        crt = None

        if os.path.isfile(os.path.join(working_dir, "auth.txt")):
            auth_file = os.path.join(working_dir, "auth.txt")

        crt_re = re.compile(r'.crt|cert')
        files = os.listdir(working_dir)                       
        crt_result = list(filter(crt_re.findall, files))
        if len(crt_result) >= 1:
            crt = os.path.join(working_dir, crt_result[-1])


        ThreadManager().create(self.ovpn.connect_eovpn, (config_file, auth_file, crt, log_file, self.on_connect),  is_daemon=True)   