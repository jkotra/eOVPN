import os
import json
import re
import subprocess
import logging
import time
import socket
import pathlib
import shutil

import gettext

from gi.repository import Gtk, GLib, Gdk, GdkPixbuf, Gio

from .eovpn_base import Base, SettingsManager, ThreadManager, get_standalone
from .settings_window import SettingsWindow
from .log_window import LogWindow
from .about_dialog import AboutWindow
from .connection_manager import eOVPNConnectionManager
from .openvpn import is_openvpn_running
from .networkmanager.dbus import watch_vpn_status
from .networkmanager.bindings import NetworkManager
from .utils import download_remote_to_destination, load_configs_to_tree, is_selinux_enforcing
from .ip_lookup.lookup import LocationDetails

logger = logging.getLogger(__name__)

class MainWindow(Base, Gtk.Builder):
    def __init__(self, app):
        super().__init__()
        Gtk.Builder.__init__(self)
        self.app = app
        
        self.add_from_resource(self.EOVPN_GRESOURCE_PREFIX + "/ui/" + "main.glade")
        self.connect_signals(MainWindowSignalHandler(self))
        self.window = self.get_object("mainwindow")
        self.store_widget("mainwindow", self.window)

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
        self.connect_btn = self.builder.get_object("connect_btn")
        self.update_btn = self.builder.get_object("update_btn")

        self.statusbar = self.builder.get_object("statusbar")
        self.spinner = self.builder.get_object("main_spinner")

        self.paned = self.builder.get_object("main_paned")
        self.store_widget("main_paned", self.paned)
        
        self.config_storage = self.builder.get_object("config_storage")
        self.store_widget("config_storage", self.config_storage)

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

        self.se_enforcing = is_selinux_enforcing()
        logger.debug("SELinux_Enforcing={}".format(self.se_enforcing))

        #load_settings
        self.settings = Gio.Settings.new(self.APP_ID)
        paned_height = self.settings.get_int("treeview-height")
        
        if paned_height != -1:
            self.paned.set_position(paned_height)
        else:
            self.paned.set_position(250)
        logger.debug("GtkPaned position={}".format(self.paned.get_position()))
        
        #connect_prefs
        self.connect_prefs = self.builder.get_object("connect_prefs")
        self.connect_popover = self.builder.get_object("connect_popover")
        self.connect_prefs_ping_label = self.builder.get_object("connect_menu_ms")
        self.proto_chooser_box = self.builder.get_object("proto_choose_box")
        
        self.connection_details_widgets = { "ip_label": self.ip_label,
                                            "status_label": self.status_label,
                                            "location_label": self.location_label,
                                            "country_image": self.country_image,
                                            "is_connected": self.is_connected,
                                            "connect_btn": self.connect_btn}

        self.proto_choice = {"tcp": self.builder.get_object("on_connect_prefs_tcp_btn_tick"),
                            "udp": self.builder.get_object("on_connect_prefs_udp_btn_tick")}

        self.country_predetails = {"box": self.builder.get_object("connect_prefs_country_details"),
                                   "sep": self.builder.get_object("country_section_sep"),
                                   "img": self.builder.get_object("connection_prefs_country_image"),
                                   "name": self.builder.get_object("connection_prefs_country_name")}                    
       

        self.menu_view_config = self.builder.get_object("view_config")
        self.store_widget("menu_view_config", self.menu_view_config)

        #reset session.log
        if os.path.exists(self.EOVPN_CONFIG_DIR) != True:
            os.mkdir(self.EOVPN_CONFIG_DIR)

        #if manager is None, set it according to compatibility (NM preferered)
        logger.debug("Testing if NM is supported...")
        is_nm_supported = NetworkManager().get_version()

        if self.get_setting("manager") is None:
            self.set_setting("manager", "networkmanager" if (is_nm_supported != None) else "openvpn")
        
        if (self.get_setting("manager") == "networkmanager") and (is_nm_supported is None):
            self.set_setting("manager", "openvpn")


        self.conn_mgr = eOVPNConnectionManager(self.statusbar, self.statusbar_icon, self.spinner)
        self.conn_mgr.get_version(callback=self.on_version)
        self.current_manager = self.get_setting("manager")
        watch_vpn_status(update_callback=self.update_status_ip_loc_flag)

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
            load_configs_to_tree(self.config_storage, self.get_setting("remote_savepath"))
        
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


    #callbacks
    def on_connect(self, result, config_connected):
        logger.info("result = {}".format(result))
        if result:

            #update_status_ip_loc_flag() is called inside watch_vpn_status(). so, dont update here.
            if self.current_manager != "networkmanager":      
                self.update_status_ip_loc_flag()

            self.config_connected = config_connected
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
            self.config_connected = None
            if self.get_setting("notifications"):
                self.send_notification("Disconnected", "Disconnected from {}".format(
                    self.get_setting("last_connected")
                    ), False)

            if self.current_manager != "networkmanager":      
                self.update_status_ip_loc_flag()

    def on_version(self, result):

        logger.info("version_callback={}".format(result))
        if result:
            pass

        if result is False:
            self.connect_btn.set_sensitive(False)
            if self.get_setting("manager") == "networkmanager":
                self.set_setting("manager", "openvpn")
                self.conn_mgr.get_version(callable=self.on_version)

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

        def test_ping():
            
            f = open(os.path.join(self.EOVPN_CONFIG_DIR, self.get_setting("remote_savepath"), self.config_selected)).read()
            for line in f.split("\n"):
                if "remote" in line:
                    openvpn_addr = line.split(" ")[1]
                    break

            logger.debug(openvpn_addr)

            commands = []
            if os.getenv("FLATPAK_ID") is not None:
                commands.append("flatpak-spawn")
                commands.append("--host")

            commands.append("ping")
            commands.append("-c")
            commands.append("1")
            commands.append(openvpn_addr)

            out = subprocess.run(commands, stdout=subprocess.PIPE)
            out = out.stdout.decode('utf-8')

            ping_re = re.compile(r"time=.*")
            res = ping_re.findall(out)

            self.connect_prefs_ping_label.set_label(res[-1].split("=")[-1])
            self.connect_prefs_ping_label.show()
            
            ip = socket.gethostbyname(openvpn_addr)
            logger.debug(ip)
            
            LocationDetails().set_ping_ip_details(ip, self.country_predetails)
            
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

        LocationDetails().set(self.connection_details_widgets, self.conn_mgr.get_connection_status())
    
        if self.conn_mgr.get_connection_status():
            if self.config_selected != None:

                if self.current_manager == "networkmanager":
                    self.statusbar.push(1, gettext.gettext("Connected to {}").format(self.config_connected.split("/")[-1]))
                    self.statusbar_icon.set_from_icon_name("network-vpn-symbolic", 1)

                self.conn_mgr.openvpn_config_set_protocol(os.path.join(self.EOVPN_CONFIG_DIR,
                                                  self.get_setting("remote_savepath"),
                                                  self.config_selected), self.proto_label)
            if self.standalone_mode:
                self.conn_mgr.openvpn_config_set_protocol(self.standalone_path, self.proto_label)
            self.proto_chooser_box.set_sensitive(False)
            self.is_connected = True
        else:
            self.proto_label.hide()
            self.proto_chooser_box.set_sensitive(True)
            self.is_connected = False

        self.spinner.stop()    


    def on_copy_btn_clicked(self, ip):
        ip = ip.get_text()
        clip = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
        clip.set_text(ip, -1)
        logger.info("{} copied to clipboard.".format(ip))

    def on_update_btn_clicked(self, button):

        def update():
            self.spinner.start()
            builder = self.get_builder("main.glade")
            cs = builder.get_object("config_storage")
            download_remote_to_destination(self.get_setting("remote"), self.get_setting("remote_savepath"))
            load_configs_to_tree(cs, self.get_setting("remote_savepath"))
            self.spinner.stop()
            logger.debug("configs updated!")

        ThreadManager().create(update, (), True)

    def on_open_vpn_running_kill_btn_clicked(self, dlg):
        self.conn_mgr.disconnect(self.on_disconnect)
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
            self.conn_mgr.disconnect(self.on_disconnect)
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
            if self.se_enforcing and (self.get_setting("manager") != "openvpn"):
                home_dir = GLib.get_home_dir()
                se_friendly_path = os.path.join(home_dir, ".cert")
                if not os.path.exists(se_friendly_path):
                    os.mkdir(se_friendly_path)
                shutil.copy(crt, se_friendly_path)
                crt = os.path.join(se_friendly_path, crt.split("/")[-1])
                logger.debug("crt={}".format(crt))
        
        self.conn_mgr.connect(config_file, auth_file, crt, log_file, self.on_connect)

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
            auth_file = os.path.join(working_dir, "auth.txt") #1st preference
        else:
            if self.get_setting("req_auth"):
                auth_file = os.path.join(self.EOVPN_CONFIG_DIR, "auth.txt") #2nd preference

        crt_re = re.compile(r'.crt|cert')
        files = os.listdir(working_dir)                       
        crt_result = list(filter(crt_re.findall, files))
        if len(crt_result) >= 1:
            crt = os.path.join(working_dir, crt_result[-1])

        self.conn_mgr.connect(config_file, auth_file, crt, log_file, self.on_connect)