import json
import logging
import os
from os import path
from urllib.parse import urlparse
import shutil
import gettext

from gi.repository import Gtk, Gio

from .eovpn_base import Base, SettingsManager, builder_record
from .connection_manager import eOVPNConnectionManager

from .utils import validate_remote
from .utils import load_configs_to_tree
from .utils import download_remote_to_destination
from .utils import message_dialog
from .utils import set_crt_auto

from .networkmanager.bindings import NetworkManager

logger = logging.getLogger(__name__)

class SettingsWindow(Base, Gtk.Builder):
    def __init__(self):
        super().__init__()
        Gtk.Builder.__init__(self)

        self.add_from_resource(self.EOVPN_GRESOURCE_PREFIX + "/ui/" + "settings.glade")
        self.connect_signals(SettingsWindowSignalHandler(self))
        self.window = self.get_object("settings_window")

    def show(self):
        self.window.show()    


class SettingsWindowSignalHandler(SettingsManager):
    def __init__(self, builder):
        super(SettingsWindowSignalHandler, self).__init__()
        self.builder = builder
        self.spinner = self.builder.get_object("settings_spinner")
        self.status_bar = self.builder.get_object("openvpn_settings_statusbar")
        self.ovpn = eOVPNConnectionManager(spinner = self.spinner)

        self.auth_file = os.path.join(self.EOVPN_CONFIG_DIR, "auth.txt")
        self.settings_file = os.path.join(self.EOVPN_CONFIG_DIR, "settings.json")
        
        self.remote_addr_entry = self.builder.get_object("openvpn_config_remote_addr")

        self.setting_saved_reveal = self.builder.get_object("reveal_settings_saved")
        self.inapp_notification_label = self.builder.get_object("inapp_notification")
        self.undo_reset_btn = self.builder.get_object("undo_reset") 
        #by default, it's not revealed (duh!)
        self.setting_saved_reveal.set_reveal_child(False)
        #only close the first time
        self.reveal_delay_close = False

        #radio button chooser
        self.nm_radio = self.builder.get_object("nm_radio_btn")
        if NetworkManager().get_version() == None:
            self.nm_radio.hide()
        self.ovpn_radio = self.builder.get_object("ovpn_radio_btn")

        self.nm_logo = self.builder.get_object("nm_logo")
        self.nm_logo.set_from_pixbuf(self.get_image("nm.svg", "icons", (48, 48)))

        self.ovpn_logo = self.builder.get_object("ovpn_logo")
        self.ovpn_logo.set_from_pixbuf(self.get_image("openvpn.svg", "icons", (48, 48)))

        self.on_mgr_change_revealer = self.builder.get_object("on_manager_change_revealer")
        self.initial_manager = self.get_setting("manager")
        self.remove_all_vpn_btn = self.builder.get_object("remove_all_vpn_nm_btn")

        #load tree from mainwindow
        main_builder = builder_record["main"]
        self.config_storage = main_builder.get_object("config_storage")
        self.menu_view_config = main_builder.get_object("view_config")
        self.paned = main_builder.get_object("main_paned")

        self.save_btn = self.builder.get_object("settings_apply_btn")
        self.save_btn.set_sensitive(False)

        self.req_auth = self.builder.get_object("req_auth")
        self.auth_user = self.builder.get_object("auth_user")
        self.auth_pass = self.builder.get_object("auth_pass")
        self.user_pass_box = self.builder.get_object("user_pass_box")

        self.crt_chooser = self.builder.get_object("crt_chooser")

        self.valid_result_lbl = self.builder.get_object("openvpn_settings_statusbar")

        #General Tab
        self.notification_switch = self.builder.get_object("notification_switch")
        self.update_on_launch_switch = self.builder.get_object("update_on_launch_switch")
        self.connect_on_launch_switch = self.builder.get_object("connect_on_launch_switch")

        self.are_you_sure = self.builder.get_object("settings_reset_ask_sure")

        self.update_settings_ui()
    
    def on_nm_radio_btn_toggled(self, radio_btn):
        if radio_btn.get_active():
            self.set_setting("manager", "networkmanager")
            if self.initial_manager == "networkmanager":
                self.on_mgr_change_revealer.set_reveal_child(False)
            else:
                self.on_mgr_change_revealer.set_reveal_child(True)
                self.remove_all_vpn_btn.set_visible(True)


    def on_ovpn_radio_btn_toggled(self, radio_btn):
        if radio_btn.get_active():
            self.set_setting("manager", "openvpn")
            self.remove_all_vpn_btn.set_visible(False)
            if self.initial_manager == "openvpn":
                self.on_mgr_change_revealer.set_reveal_child(False)
            else:
                self.on_mgr_change_revealer.set_reveal_child(True)
    
    def on_remove_all_vpn_nm_btn_clicked(self, btn):
        nm = NetworkManager()
        res = nm.delete_all_vpn_connections()
        if res:
            message_dialog(gettext.gettext("Deleted all VPN connections (if any)!"), "")
            

    def update_settings_ui(self):
        remote = self.get_setting("remote")
        if remote is not None:
            self.remote_addr_entry.set_text(remote)
        

        mgr = self.get_setting("manager")
        if mgr == "networkmanager":
            self.nm_radio.set_active(True)

        elif mgr == "openvpn":
            self.ovpn_radio.set_active(True)
        else:
            self.nm_radio.set_active(False)
            self.ovpn_radio.set_active(False)


        if self.get_setting("update_on_start"):
            self.update_on_launch_switch.set_state(True)

        if self.get_setting("notifications"):
            self.notification_switch.set_state(True)    
        
        if self.get_setting("req_auth"):
            self.req_auth.set_active(True)

            if self.get_setting("auth_user") is not None:
                self.auth_user.set_text(self.get_setting("auth_user"))

            
            if self.get_setting("auth_pass") is not None:
                self.auth_pass.set_text(self.get_setting("auth_pass"))

        else:
            self.req_auth.set_active(False)
            self.user_pass_box.set_sensitive(False)
        
        crt_path = self.get_setting("crt")
        if crt_path is not None:
            self.crt_chooser.set_filename(crt_path)

        if self.get_setting("connect_on_launch"):
            self.connect_on_launch_switch.set_state(True)


    def on_settings_window_delete_event(self, window, event) -> bool:
        window.hide()
        return True

    def on_settings_apply_btn_clicked(self, buttton):

        initial_remote = self.get_setting("remote")

        
        url = self.remote_addr_entry.get_text().strip()

        if url != '':
            self.set_setting("remote", url)
            folder_name = urlparse(url).netloc
            if folder_name == '':
                folder_name = "configs"

            self.set_setting("remote_savepath", path.join(self.EOVPN_CONFIG_DIR, folder_name))    
        
        else:
            self.set_setting("remote", None)
        
        #save folder name to config

        if self.req_auth.get_active():
            self.set_setting("req_auth", True)

            username = self.auth_user.get_text()
            self.set_setting("auth_user", username)

            password = self.auth_pass.get_text()
            self.set_setting("auth_pass", password)
            
            auth_file = os.path.join(self.EOVPN_CONFIG_DIR, "auth.txt")
            f = open(auth_file ,"w+")
            f.write("{user}\n{passw}".format(user=username, passw=password))
            f.close()
        
        if initial_remote is None:
            download_remote_to_destination(url, self.get_setting("remote_savepath"))
            load_configs_to_tree(self.config_storage ,self.get_setting("remote_savepath"))
        
        set_crt_auto()
        
        #show settings saved notfication
        self.inapp_notification_label.set_text(gettext.gettext("Settings Saved."))
        self.undo_reset_btn.hide()
        self.setting_saved_reveal.set_reveal_child(True)

    def on_revealer_close_btn_clicked(self, btn):
        self.setting_saved_reveal.set_reveal_child(False)

    def on_reset_btn_clicked(self, button):
        self.are_you_sure.run()
        
    
    def reset_yes_btn_clicked_cb(self, dialog):
        self.reset_settings()
        dialog.hide()
        return True

    def reset_cancel_btn_clicked_cb(self, dialog):
        dialog.hide()
        return True    

    def reset_settings(self):

        #backup to /tmp, give user choice to undo
        shutil.copytree(self.EOVPN_CONFIG_DIR, "/tmp/eovpn_reset_backup/", dirs_exist_ok=True)
        shutil.rmtree(self.EOVPN_CONFIG_DIR)
        os.mkdir(self.EOVPN_CONFIG_DIR)
        
        is_nm_supported = NetworkManager().get_version()
        logger.info("[reset] is_nm_supported={}".format(is_nm_supported))
        default = {"notifications": True, "manager": "networkmanager" if (is_nm_supported != None) else "openvpn"}
        default = json.dumps(default, indent=2)
        f = open(os.path.join(self.EOVPN_CONFIG_DIR, "settings.json"), "w+")
        f.write(default)
        f.close()

        #remove config from liststorage
        self.config_storage.clear()
        self.menu_view_config.hide()

        #remote GtkPaned size from Gsetting.
        settings = Gio.Settings.new(self.APP_ID)
        settings.reset("treeview-height")
        self.paned.set_position(250)

        self.remote_addr_entry.set_text("")

        self.nm_radio.set_active(False)
        self.ovpn_radio.set_active(False)

        # General Tab
        self.update_on_launch_switch.set_state(False)
        self.connect_on_launch_switch.set_state(False)
        self.notification_switch.set_state(False)

        self.req_auth.set_active(False)
        self.auth_user.set_text("")
        self.auth_pass.set_text("")
        self.crt_chooser.set_filename("")

        self.inapp_notification_label.set_text(gettext.gettext("Settings deleted."))
        self.undo_reset_btn.show()
        self.setting_saved_reveal.set_reveal_child(True)
        self.update_settings_ui()

    def on_undo_reset_clicked(self, button):
        shutil.copytree("/tmp/eovpn_reset_backup/", self.EOVPN_CONFIG_DIR, dirs_exist_ok=True)
        self.update_settings_ui()
        self.on_revealer_close_btn_clicked(None) #button is not actually used so it's okay.
        self.undo_reset_btn.hide()

    def on_crt_chooser_file_set(self, chooser):
        self.set_setting("crt", chooser.get_filename())
        self.set_setting("crt_set_explicit", True)

    def on_req_auth_toggled(self, toggle):
        self.set_setting("req_auth", toggle.get_active())
        self.user_pass_box.set_sensitive(toggle.get_active())

    def on_settings_validate_btn_clicked(self, entry):
        validate_remote(entry.get_text(), self.spinner)

    def save_btn_activate(self, editable):
        self.save_btn.set_sensitive(True)

    def on_crt_file_reset_clicked(self, button):
        self.crt_chooser.set_filename("")
        self.set_setting("crt", None)
        self.set_setting("crt_set_explicit", None)
    
    def on_show_password_btn_toggled(self, toggle):
        self.auth_pass.set_visibility(toggle.get_active())

    # General Tab
    def on_notification_switch_state_set(self, switch, state):
        self.set_setting("notifications", state)

    def on_update_on_launch_switch_state_set(self, switch, state):
        self.set_setting("update_on_start", state)

    def on_connect_on_launch_switch_state_set(self, switch, state):
        self.set_setting("connect_on_launch", state)     