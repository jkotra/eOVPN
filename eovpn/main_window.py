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

from .eovpn_base import Base, ThreadManager, get_standalone
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
        self.window = self.get_object("main_window")
        self.window.set_title("eOVPN")
        self.window.set_icon_name(self.APP_ID)

        self.app.add_window(self.window)
        self.store_widget("main_window", self.window)


    def show(self):
        self.window.show()




class MainWindowSignalHandler(Base):
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
        self.selected_cursor = None
        self.proto_override = None #consider true if it's either UDP or TCP
        self.is_connected = None
        self.no_network = False

        self.standalone_mode = False
        self.standalone_path = None

        self.se_enforcing = is_selinux_enforcing()
        logger.debug("SELinux_Enforcing={}".format(self.se_enforcing))

        #load_settings
        paned_height = self.get_setting(self.SETTING.TREEVIEW_HEIGHT)
        
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

        if (self.get_setting(self.SETTING.MANAGER) != "networkmanager"):
            self.builder.get_object("log_btn").set_sensitive(True)


        #reset session.log
        if os.path.exists(self.EOVPN_CONFIG_DIR) != True:
            os.mkdir(self.EOVPN_CONFIG_DIR)

        #if manager is None, set it according to compatibility (NM preferered)
        logger.debug("Testing if NM is supported...")
        is_nm_supported = NetworkManager().get_version()

        if self.get_setting(self.SETTING.MANAGER) is None:
            self.set_setting(self.SETTING.MANAGER, "networkmanager" if (is_nm_supported != None) else "openvpn")
        
        if (self.get_setting(self.SETTING.MANAGER) == "networkmanager") and (is_nm_supported is None):
            self.set_setting(self.SETTING.MANAGER, "openvpn")

        is_standalone, ovpn_config = get_standalone()
        if is_standalone:
            logger.info("Standalone Mode!")
            self.config_tree.set_sensitive(False)
            self.connect_btn.connect("clicked", self.on_connect_btn_clicked_standalone)
            self.standalone_mode = True
            self.standalone_path = ovpn_config
        else:
            self.connect_btn.connect("clicked", self.on_connect_btn_clicked)    


        self.conn_mgr = eOVPNConnectionManager(self.statusbar, self.statusbar_icon, self.spinner)
        self.conn_mgr.get_version(callback=self.on_version)
        current_manager = self.get_setting(self.SETTING.MANAGER)
        if current_manager == "networkmanager":
            watch_vpn_status(update_callback=self.on_nm_connent_event)     

        self.update_status_ip_loc_flag()

        if self.get_setting(self.SETTING.REMOTE_SAVEPATH) != None:
            load_configs_to_tree(self.config_storage, self.get_setting(self.SETTING.REMOTE_SAVEPATH))
        
        if self.get_setting(self.SETTING.LAST_CONNECTED) != None:
            logger.debug("last_connected = {}".format(self.get_setting(self.SETTING.LAST_CONNECTED)))
            if self.get_setting(self.SETTING.LAST_CONNECTED_CURSOR) != None:
                i = self.get_setting(self.SETTING.LAST_CONNECTED_CURSOR)
                self.config_tree.set_cursor(i)
                self.config_tree.scroll_to_cell(i)
                self.config_selected = self.get_setting(self.SETTING.LAST_CONNECTED)

                logger.debug("restored cursor = {} | config_selected = {}".format(i, self.config_selected))
                self.menu_view_config.set_sensitive(True)

                if self.get_setting(self.SETTING.CONNECT_ON_LAUNCH):
                    if (self.is_connected is False) and (self.no_network is False):
                        self.on_connect_btn_clicked(self.connect_btn)
        
        if self.get_setting(self.SETTING.UPDATE_ON_START):
            self.on_update_btn_clicked(self.update_btn)

        if self.standalone_mode and not self.is_connected:
            GLib.idle_add(self.on_connect_btn_clicked_standalone, self.connect_btn)



    #callbacks
    def on_connect(self, result, config_connected):
        logger.info("connect_callback={}".format(result))
        if result:

            #update_status_ip_loc_flag() is called inside watch_vpn_status(). so, dont update here.
            if self.get_setting(self.SETTING.MANAGER) != "networkmanager":      
                self.update_status_ip_loc_flag()
            
            connected_filename = os.path.split(config_connected)[-1]
            self.set_setting(self.SETTING.CURRENT_CONNECTED, connected_filename)
            self.set_setting(self.SETTING.LAST_CONNECTED, connected_filename)
            self.set_setting(self.SETTING.LAST_CONNECTED_CURSOR, self.selected_cursor)

            #send notification
            if self.get_setting(self.SETTING.NOTIFICATIONS) and (self.get_setting(self.SETTING.MANAGER) != "networkmanager"):
                self.send_notification(gettext.gettext("Connected"),
                                       gettext.gettext("Connected to {}").format(self.get_setting(self.SETTING.LAST_CONNECTED)),
                                        True)            

            logger.debug("saved to config: cursor={} config={}".format(self.config_selected, self.selected_cursor))
            self.is_connected = True
            return True
        else:
            self.statusbar.push(1, gettext.gettext("Failed to connect!"))
            self.is_connected = False
            return False

    def on_disconnect(self, result):
        logger.debug("disconnect_callback={}".format(result))
        if result:
            self.set_setting(self.SETTING.CURRENT_CONNECTED, None)
            if self.get_setting(self.SETTING.NOTIFICATIONS) and (self.get_setting(self.SETTING.MANAGER) != "networkmanager"):
                self.send_notification(gettext.gettext("Disconnected"),
                                       gettext.gettext("Disconnected from {}").format(self.get_setting(self.SETTING.LAST_CONNECTED)),
                                        False)

            if self.get_setting(self.SETTING.MANAGER) != "networkmanager":      
                self.update_status_ip_loc_flag()

    def on_version(self, result):

        logger.info("version_callback={}".format(result))
        if result:
            pass

        if result is False:
            self.connect_btn.set_sensitive(False)
            if self.get_setting(self.SETTING.MANAGER) == "openvpn":
                self.statusbar.push(1, gettext.gettext("OpenVPN not found!"))
            if self.get_setting(self.SETTING.MANAGER) == "networkmanager":
                self.set_setting(self.SETTING.MANAGER, "openvpn")
                self.conn_mgr.get_version(callable=self.on_version)

    def on_update(self, result):
        logger.debug(result)
        if result:
            self.config_tree.set_cursor(0)
            self.config_tree.scroll_to_cell(0)

    def on_nm_connent_event(self, connection_result=None, error=None):
        if connection_result is True:
            self.is_connected = True
            filename = self.get_setting(self.SETTING.CURRENT_CONNECTED)
            text = gettext.gettext("Connected to {}").format(filename)
            self.statusbar.push(1, text)
            self.statusbar_icon.set_from_icon_name("network-vpn-symbolic", 1)
            if self.get_setting(self.SETTING.NOTIFICATIONS):
                self.send_notification(gettext.gettext("Connected"),
                                       gettext.gettext("Connected to {}").format(self.get_setting(self.SETTING.LAST_CONNECTED)),
                                        True)
        elif connection_result is False:
            self.is_connected = False
            if self.get_setting(self.SETTING.NOTIFICATIONS):

                self.send_notification(gettext.gettext("Disconnected"),
                                        gettext.gettext("Disconnected from {}").format(self.get_setting(self.SETTING.LAST_CONNECTED)),
                                        False)
                
                #delete failed connection
                if error is not None:
                    logger.error(error)
                    self.conn_mgr.NM_cleanup_connection()
                    self.statusbar.pop(1)                                                       
        else:
            pass

        self.update_status_ip_loc_flag()
        self.spinner.stop()
    #end

    def on_main_paned_position_notify(self, paned, position):
        paned_height = self.paned.get_position()
        self.set_setting(self.SETTING.TREEVIEW_HEIGHT, paned_height)
        return True
    
    def on_connect_prefs_tcp_btn_clicked(self, btn):
        self.proto_override = "TCP"
        self.proto_choice["tcp"].show()
        self.proto_choice["udp"].hide()

    def on_connect_prefs_udp_btn_clicked(self, btn):
        self.proto_override = "UDP"
        self.proto_choice["udp"].show()
        self.proto_choice["tcp"].hide()
  
    def on_keyboard_shortcuts_btn_clicked(self, btn):
        builder = Gtk.Builder()
        builder.add_from_resource(self.EOVPN_GRESOURCE_PREFIX + "/ui/" + "keyboard_shortcuts.ui")
        window = builder.get_object("shortcuts")
        window.set_transient_for(self.get_widget("main_window"))
        window.show()

    #ping
    def on_ping_clicked(self, spinner):

        def test_ping():
            
            f = open(os.path.join(self.EOVPN_CONFIG_DIR, self.get_setting(self.SETTING.REMOTE_SAVEPATH), self.config_selected)).read()
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
            file = os.path.join(self.EOVPN_CONFIG_DIR, self.get_setting(self.SETTING.REMOTE_SAVEPATH), self.config_selected)
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
            self.menu_view_config.set_sensitive(True)

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


    def update_status_ip_loc_flag(self, nm_connected=None) -> None:

        LocationDetails().set(self.connection_details_widgets, self.conn_mgr.get_connection_status())
    
        if self.conn_mgr.get_connection_status():
            self.is_connected = True

            if self.standalone_mode:
                self.conn_mgr.openvpn_config_set_protocol(self.standalone_path, self.proto_label)
                self.proto_chooser_box.set_sensitive(False)
                return

            if self.get_setting(self.SETTING.CURRENT_CONNECTED) != None:
                self.conn_mgr.openvpn_config_set_protocol(os.path.join(self.EOVPN_CONFIG_DIR,
                                                  self.get_setting(self.SETTING.REMOTE_SAVEPATH),
                                                  self.get_setting(self.SETTING.CURRENT_CONNECTED)), self.proto_label)

        else:
            self.proto_label.hide()
            self.proto_chooser_box.set_sensitive(True)
            self.is_connected = False  


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

            try:
                download_remote_to_destination(self.get_setting(self.SETTING.REMOTE), self.get_setting(self.SETTING.REMOTE_SAVEPATH))
            except Exception as e:
                logger.error(e)
                self.spinner.stop()
                return False

            load_configs_to_tree(cs, self.get_setting(self.SETTING.REMOTE_SAVEPATH))
            self.spinner.stop()
            self.statusbar.push(1, gettext.gettext("Configs updated."))
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

        url = "file://{savepath}/{config}".format(savepath=self.get_setting(self.SETTING.REMOTE_SAVEPATH),
                                                  config=self.config_selected)
        Gio.AppInfo.launch_default_for_uri(url)


    def on_connect_btn_clicked(self, button):

        log_file = os.path.join(self.EOVPN_CONFIG_DIR, "session.log")

        if self.is_connected:
            self.conn_mgr.disconnect(self.on_disconnect)
            return True
        
        is_vpn_running = self.conn_mgr.get_connection_status()
        logger.debug("is_vpn_running={}".format(is_vpn_running))

        if is_vpn_running:
            dlg = self.builder.get_object("openvpn_running_dlg")
            dlg.run()
            return False

        try:
            config_file = os.path.join(self.get_setting(self.SETTING.REMOTE_SAVEPATH), self.config_selected)
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
        
        if self.get_setting(self.SETTING.REQ_AUTH):
            auth_file = os.path.join(self.EOVPN_CONFIG_DIR, "auth.txt")

        if self.get_setting(self.SETTING.CA) is not None:    
            crt = self.get_setting(self.SETTING.CA)
            if self.se_enforcing and (self.get_setting(self.SETTING.MANAGER) != "openvpn"):
                home_dir = GLib.get_home_dir()
                se_friendly_path = os.path.join(home_dir, ".cert")
                if not os.path.exists(se_friendly_path):
                    os.mkdir(se_friendly_path)
                shutil.copy(crt, se_friendly_path)
                crt = os.path.join(se_friendly_path, crt.split("/")[-1])
                logger.debug("crt={}".format(crt))
        
        self.conn_mgr.connect(config_file, auth_file, crt, log_file, self.on_connect)
    
    # ask_auth callback
    def ask_auth_save_clicked_cb(self, btn):
        ask_auth_builder = self.get_widget("ask_auth")
        username = ask_auth_builder.get_object("auth_user").get_text()
        password = ask_auth_builder.get_object("auth_pass").get_text()
        ca = ask_auth_builder.get_object("ca_chooser").get_filename()

        with open(os.path.join(os.path.dirname(self.standalone_path), "eovpn.json"), "w+") as f:
            f.write(json.dumps({"username": username, "password": password, "ca": ca}, indent=2))
            f.close()
        ask_auth_builder.get_object("ask_auth").destroy()
        self.on_connect_btn_clicked_standalone(None)

    def on_connect_btn_clicked_standalone(self, button):
        working_dir = os.path.dirname(self.standalone_path)
        config_name = os.path.basename(self.standalone_path)
        if working_dir == '':
            working_dir = os.getcwd()

        if self.is_connected:
            self.conn_mgr.disconnect(self.on_disconnect)
            return True
        
        is_vpn_running = self.conn_mgr.get_connection_status()
        logger.debug("is_vpn_running={}".format(is_vpn_running))

        if is_vpn_running:
            dlg = self.builder.get_object("openvpn_running_dlg")
            dlg.run()
            return False
        
        log_file = os.path.join(self.EOVPN_CONFIG_DIR, "session.log")
        config_file = os.path.join(working_dir, config_name)
        auth_file = os.path.join(working_dir,"auth.txt") #not applicable for NM
        crt = None

        if not os.path.exists(os.path.join(working_dir, "eovpn.json")) and self.conn_mgr.req_auth(config_file):
            builder = Gtk.Builder()
            builder.add_from_resource(self.EOVPN_GRESOURCE_PREFIX + '/ui/ask_auth.glade')
            self.store_widget("ask_auth", builder)
            builder.connect_signals(self)
            win = builder.get_object("ask_auth")
            if (self.get_setting(self.SETTING.MANAGER) == "networkmanager"):
                builder.get_object("overwrite_warning").show()

            ca_chooser = builder.get_object("ca_chooser")
            ca_filter = Gtk.FileFilter()
            ca_filter.add_pattern("*.ca")
            ca_filter.add_pattern("*.pem")
            ca_filter.add_pattern("*.crt")
            ca_chooser.set_filter(ca_filter)

            win.set_transient_for(self.get_widget("main_window"))
            win.set_type_hint(Gdk.WindowTypeHint.DIALOG) #required for Xorg session
            win.show()
            return

        auth_details = json.loads(open(os.path.join(working_dir, "eovpn.json"), 'r').read())
        crt = auth_details["ca"]


        if (self.get_setting(self.SETTING.MANAGER) == "openvpn"):
            with open(auth_file, "w+") as f:
                f.write("{}\n{}".format(auth_details["username"], auth_details["password"]))
                f.close()
               
        else:
            #manager is NM
            self.set_setting(self.SETTING.AUTH_USER, auth_details["username"])
            self.set_setting(self.SETTING.AUTH_PASS, auth_details["password"])
            self.set_setting(self.SETTING.CA, auth_details["ca"])
       
        if self.se_enforcing and (self.get_setting(self.SETTING.MANAGER) != "openvpn"):
            home_dir = GLib.get_home_dir()
            selinux_friendly_path = os.path.join(home_dir, ".cert")
            if not os.path.exists(selinux_friendly_path):
                os.mkdir(selinux_friendly_path)
            shutil.copy(auth_details["ca"], selinux_friendly_path)
            crt = os.path.join(selinux_friendly_path, auth_details["ca"])
            self.set_setting(self.SETTING.CA, crt)
        
        print(config_file, auth_file, crt)
        self.conn_mgr.connect(config_file, auth_file, crt, log_file, self.on_connect)