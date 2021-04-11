import json
import logging
import os
from os import path
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

        self.add_from_resource(self.EOVPN_GRESOURCE_PREFIX + "/ui/" + "settings.glade")
        self.connect_signals(SettingsWindowSignalHandler(self))
        self.window = self.get_object("settings_window")
        self.window.set_title("eOVPN Settings")

        self.window.set_transient_for(self.get_widget("main_window"))
        self.window.set_type_hint(Gdk.WindowTypeHint.DIALOG) #required for Xorg session

    def show(self):
        self.window.show()    


class SettingsWindowSignalHandler(Base):
    def __init__(self, builder):
        super(SettingsWindowSignalHandler, self).__init__()
        self.builder = builder
        self.spinner = self.builder.get_object("settings_spinner")
        self.status_bar = self.builder.get_object("openvpn_settings_statusbar")
        self.ovpn = eOVPNConnectionManager(spinner = self.spinner)

        self.auth_file = os.path.join(self.EOVPN_CONFIG_DIR, "auth.txt")
        self.settings_file = os.path.join(self.EOVPN_CONFIG_DIR, "settings.json")
        
        self.url_radio_btn = self.builder.get_object("url_radio_btn")
        self.zip_radio_btn = self.builder.get_object("zip_radio_btn")
        self.dir_radio_btn = self.builder.get_object("dir_radio_btn")
        self.selected_remote_type = None

        self.remote_addr_entry = self.builder.get_object("url_entry")
        self.source_file_chooser = self.builder.get_object("source_file_chooser")
        zip_file_filter = Gtk.FileFilter()
        zip_file_filter.add_pattern("*.zip")
        self.source_file_chooser.set_filter(zip_file_filter)
        self.source_folder_chooser = self.builder.get_object("source_folder_chooser")
        self.validate_revealer = self.builder.get_object("validate_revealer")

        self.setting_saved_reveal = self.builder.get_object("reveal_settings_saved")
        self.inapp_notification_label = self.builder.get_object("inapp_notification")
        self.undo_reset_btn = self.builder.get_object("undo_reset") 
        #by default, it's not revealed (duh!)
        self.setting_saved_reveal.set_reveal_child(False)

        #radio button chooser
        self.nm_radio = self.builder.get_object("nm_radio_btn")
        self.ovpn_radio = self.builder.get_object("openvpn2xcli_radio_btn")
        self.ovpn3_radio = self.builder.get_object("openvpn3_radio_btn")
        
        #TODO: move this to update UI elements
        self.is_nm_supported = NetworkManager().get_version() != None
        if not self.is_nm_supported:
            logger.warning("NM not found. hiding nm_radio btn.")
            self.nm_radio.hide()

        self.nm_logo = self.builder.get_object("nm_logo")
        self.nm_logo.set_from_pixbuf(self.get_image("nm.svg", "icons", (48, 48)))

        self.ovpn_logo = self.builder.get_object("ovpn_logo")
        self.ovpn_logo.set_from_pixbuf(self.get_image("openvpn.svg", "icons", (48, 48)))

        self.on_mgr_change_revealer = self.builder.get_object("on_manager_change_revealer")
        self.initial_manager = self.get_setting(self.SETTING.MANAGER)
        self.remove_all_vpn_btn = self.builder.get_object("remove_all_vpn_nm_btn")

        self.save_btn = self.builder.get_object("settings_apply_btn")
        self.save_btn.set_sensitive(False)
        
        self.reset_tmp_path = os.path.join(GLib.get_tmp_dir(), "eovpn_reset_backup")

        self.req_auth = self.builder.get_object("req_auth")
        self.auth_user = self.builder.get_object("auth_user")
        self.auth_pass = self.builder.get_object("auth_pass")
        self.user_pass_box = self.builder.get_object("user_pass_box")

        self.ca_chooser = self.builder.get_object("ca_chooser")
        ca_filter = Gtk.FileFilter()
        ca_filter.add_pattern("*.ca")
        ca_filter.add_pattern("*.pem")
        ca_filter.add_pattern("*.crt")
        self.ca_chooser.set_filter(ca_filter)

        self.valid_result_lbl = self.builder.get_object("openvpn_settings_statusbar")

        #General Tab
        self.notification_switch = self.builder.get_object("notification_switch")
        self.update_on_launch_switch = self.builder.get_object("update_on_launch_switch")
        self.connect_on_launch_switch = self.builder.get_object("connect_on_launch_switch")

        self.are_you_sure = self.builder.get_object("settings_reset_ask_sure")

        self.update_settings_ui()

    def on_url_radio_btn_toggled(self, radio_btn):
        self.selected_remote_type = 0
        self.source_file_chooser.hide()
        self.source_folder_chooser.hide()
        self.remote_addr_entry.show()

        if self.remote_addr_entry.get_text() != '':
            self.validate_revealer.set_reveal_child(True)
        else:
            self.validate_revealer.set_reveal_child(False)


    def on_zip_radio_btn_toggled(self, radio_btn):
        self.selected_remote_type = 1
        self.remote_addr_entry.hide()
        self.source_folder_chooser.hide()
        self.source_file_chooser.show()

        if self.source_file_chooser.get_filename() is not None:
            self.validate_revealer.set_reveal_child(True)
        else:
            self.validate_revealer.set_reveal_child(False)

    def on_dir_radio_btn_toggled(self, radio_btn):
        self.selected_remote_type = 2
        self.remote_addr_entry.hide()
        self.source_file_chooser.hide()
        self.source_folder_chooser.show()
        
        if self.source_folder_chooser.get_filename() is not None:
            self.validate_revealer.set_reveal_child(True)
        else:
            self.validate_revealer.set_reveal_child(False)


    def on_nm_radio_btn_toggled(self, radio_btn):
        if radio_btn.get_active():
            self.set_setting(self.SETTING.MANAGER, "networkmanager")
            if self.initial_manager == "networkmanager":
                self.on_mgr_change_revealer.set_reveal_child(False)
            else:
                self.on_mgr_change_revealer.set_reveal_child(True)
                self.remove_all_vpn_btn.set_visible(True)
                self.builder.get_object("password_stored_in_keyring_notice_box").show()
    
    def on_openvpn3_radio_btn_toggled(self, radio_btn):
        pass

    def on_openvpn2xcli_radio_btn_toggled(self, radio_btn):
        if radio_btn.get_active():
            self.set_setting(self.SETTING.MANAGER, "openvpn")
            self.remove_all_vpn_btn.set_visible(False)
            if self.initial_manager == "openvpn":
                self.on_mgr_change_revealer.set_reveal_child(False)
            else:
                self.on_mgr_change_revealer.set_reveal_child(True)
    
    def on_remove_all_vpn_nm_btn_clicked(self, btn):
        nm = NetworkManager()
        res = nm.delete_all_vpn_connections()
        if res:
            message_dialog("", gettext.gettext("Deleted all VPN connections (if any)!"))
            

    def update_settings_ui(self):

        """ this function updates ui widgets as per settings.json """

        remote_type = self.get_setting(self.SETTING.REMOTE_TYPE)

        if (remote_type == "zip"):
            if self.get_setting(self.SETTING.REMOTE) is not None:
                self.source_file_chooser.set_filename(self.get_setting(self.SETTING.REMOTE))
            self.zip_radio_btn.set_active(True)
            self.on_zip_radio_btn_toggled(None)
        elif (remote_type == "dir"):
            if self.get_setting(self.SETTING.REMOTE) is not None:
                self.source_folder_chooser.set_filename(self.get_setting(self.SETTING.REMOTE))
            self.dir_radio_btn.set_active(True)
            self.on_dir_radio_btn_toggled(None)  
        else:
            if remote_type is None:
                self.set_setting(self.SETTING.REMOTE_TYPE, "url")
            remote = self.get_setting(self.SETTING.REMOTE)
            self.url_radio_btn.set_active(True)
            if remote is not None:
                self.remote_addr_entry.set_text(remote)
            self.on_url_radio_btn_toggled(None)

        mgr = self.get_setting(self.SETTING.MANAGER)
        if mgr == "networkmanager":
            self.nm_radio.set_active(True)

        elif mgr == "openvpn":
            self.ovpn_radio.set_active(True)
        else:
            self.nm_radio.set_active(False)
            self.ovpn_radio.set_active(False)


        if self.get_setting(self.SETTING.UPDATE_ON_START):
            self.update_on_launch_switch.set_state(True)

        if self.get_setting(self.SETTING.NOTIFICATIONS):
            self.notification_switch.set_state(True)
        
        if self.get_setting(self.SETTING.REQ_AUTH):
            self.req_auth.set_active(True)

            if self.get_setting(self.SETTING.AUTH_USER) is not None:
                self.auth_user.set_text(self.get_setting(self.SETTING.AUTH_USER))

                if self.get_setting(self.SETTING.MANAGER) == "networkmanager":
                    nm_password = Secret.password_lookup_sync(self.EOVPN_SECRET_SCHEMA, {"username": self.get_setting(self.SETTING.AUTH_USER)}, None)
                    if nm_password is not None:
                        self.auth_pass.set_text(nm_password)


            if self.get_setting(self.SETTING.AUTH_PASS) is not None:
                self.auth_pass.set_text(self.get_setting(self.SETTING.AUTH_PASS))

        else:
            self.req_auth.set_active(False)
            self.user_pass_box.set_sensitive(False)
        
        ca_path = self.get_setting(self.SETTING.CA)
        if ca_path is not None:
            self.ca_chooser.set_filename(ca_path)

        if self.get_setting(self.SETTING.CONNECT_ON_LAUNCH):
            self.connect_on_launch_switch.set_state(True)


    def on_settings_window_delete_event(self, window, event) -> bool:
        window.hide()
        return True

    def __download_and_load_configs(self):
        self.spinner.start()

        try:
            download_remote_to_destination(self.get_setting(self.SETTING.REMOTE), self.get_setting(self.SETTING.REMOTE_SAVEPATH))
            set_ca_automatic(self)
            load_configs_to_tree(self.get_widget("config_storage") ,self.get_setting(self.SETTING.REMOTE_SAVEPATH))
        except Exception as e:
            logger.error(e)

        self.spinner.stop()
        self.update_settings_ui()

    def on_settings_apply_btn_clicked(self, buttton):

        initial_remote = self.get_setting(self.SETTING.REMOTE)

        if self.url_radio_btn.get_active():
            url = self.remote_addr_entry.get_text().strip()
            self.set_setting(self.SETTING.REMOTE_TYPE, "url")
        elif self.zip_radio_btn.get_active():
            url = self.source_file_chooser.get_filename()
            self.set_setting(self.SETTING.REMOTE_TYPE, "zip")
        elif self.dir_radio_btn.get_active():
            url = self.source_folder_chooser.get_filename()
            self.set_setting(self.SETTING.REMOTE_TYPE, "dir")

            #make sure there is no dir inside
            all_files = [f for f in os.listdir(url)]
            is_dir = [os.path.isdir(os.path.join(url, x)) for x in all_files]
            assert(any(is_dir) == False)

        else:
            return False            

        if (url != '') or (url is not None):
            self.set_setting(self.SETTING.REMOTE, url)
            folder_name = urlparse(url).netloc
            if folder_name == '':
                folder_name = "configs"
            self.set_setting(self.SETTING.REMOTE_SAVEPATH, path.join(self.EOVPN_CONFIG_DIR, folder_name)) 
        else:
            self.set_setting(self.SETTING.REMOTE, None)

        if self.req_auth.get_active():
            self.set_setting(self.SETTING.REQ_AUTH, True)

            username = self.auth_user.get_text()
            self.set_setting(self.SETTING.AUTH_USER, username)

            password = self.auth_pass.get_text()
            self.set_setting(self.SETTING.AUTH_PASS, password)
            
            auth_file = os.path.join(self.EOVPN_CONFIG_DIR, "auth.txt")
            if self.get_setting(self.SETTING.MANAGER) == "networkmanager":
                if os.path.isfile(auth_file):
                    os.remove(auth_file)
                self.set_setting(self.SETTING.AUTH_PASS, None)    

                attributes = { "username": username}
                result = Secret.password_store_sync(self.EOVPN_SECRET_SCHEMA, attributes, Secret.COLLECTION_DEFAULT,
                                                    "password", password, None)
                if result:
                    logger.info("password stored to keyring!")     

            else:
                self.set_setting(self.SETTING.AUTH_PASS, password)
                f = open(auth_file ,"w+")
                f.write("{}\n{}".format(username, password))
                f.close()

        
        if initial_remote is None:
            ThreadManager().create(self.__download_and_load_configs, (), True)
        
        if initial_remote is not None:
            set_ca_automatic(self)
            
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
        
        if self.get_setting(self.SETTING.AUTH_USER) is not None:
            result = Secret.password_clear_sync(self.EOVPN_SECRET_SCHEMA, { "username": self.get_setting(self.SETTING.AUTH_USER) }, None)
            if result:
                logger.info("password deleted from keyring!")


        #backup to /tmp, give user choice to undo
        try:
            shutil.copytree(self.EOVPN_CONFIG_DIR, self.reset_tmp_path, dirs_exist_ok=True)
            shutil.rmtree(self.EOVPN_CONFIG_DIR)
            os.mkdir(self.EOVPN_CONFIG_DIR)
        except Exception as e:
            logger.error(e)    
        
        #reset settings
        self.reset_all_settings()

        #default settings
        self.set_setting(self.SETTING.NOTIFICATIONS, True)
        self.set_setting(self.SETTING.MANAGER, "networkmanager" if (self.is_nm_supported != None) else "openvpn")

        #remote GtkPaned size from Gsetting.
        settings = Gio.Settings.new(self.APP_ID)
        settings.reset("treeview-height")
        self.get_widget("main_paned").set_position(250)
        
        #Setup Tab
        self.nm_radio.set_active(False)
        self.ovpn_radio.set_active(False)
        self.req_auth.set_active(False)
        self.auth_user.set_text("")
        self.auth_pass.set_text("")
        
        self.remote_addr_entry.set_text("")
        self.source_file_chooser.unselect_all()
        self.source_folder_chooser.unselect_all()
        self.ca_chooser.unselect_all()

        # General Tab
        self.update_on_launch_switch.set_state(False)
        self.connect_on_launch_switch.set_state(False)
        self.notification_switch.set_state(False)
        
        #remove config from liststorage
        self.get_widget("config_storage").clear()
        self.get_widget("menu_view_config").hide()

        self.inapp_notification_label.set_text(gettext.gettext("Settings deleted."))
        self.undo_reset_btn.show()
        self.setting_saved_reveal.set_reveal_child(True)
        self.update_settings_ui()

    def on_undo_reset_clicked(self, button):
        try:
            shutil.copytree(self.reset_tmp_path, self.EOVPN_CONFIG_DIR, dirs_exist_ok=True)
        except Exception as e:
            logger.error(e)

        ThreadManager().create(self.__download_and_load_configs, ())
        self.update_settings_ui()
        self.on_revealer_close_btn_clicked(None) #button is not actually used so it's okay.
        self.undo_reset_btn.hide()

    def on_ca_chooser_file_set(self, chooser):
        self.set_setting(self.SETTING.CA, chooser.get_filename())
        self.set_setting(self.SETTING.CA_SET_EXPLICIT, True)

    def on_req_auth_toggled(self, toggle):
        self.set_setting(self.SETTING.REQ_AUTH, toggle.get_active())
        self.user_pass_box.set_sensitive(toggle.get_active())

    def on_settings_validate_btn_clicked(self, btn):

        if self.selected_remote_type == 0:
            remote = self.remote_addr_entry.get_text()
        elif self.selected_remote_type == 1:
            remote = self.source_file_chooser.get_filename()
        elif self.selected_remote_type == 2:
            remote = self.source_folder_chooser.get_filename()

            #make sure there is no dir inside
            all_files = [f for f in os.listdir(remote)]
            is_dir = [os.path.isdir(os.path.join(remote, x)) for x in all_files]
            assert(any(is_dir) == False)


        validate_remote(remote, self.spinner)

    def save_btn_activate(self, editable):
        self.save_btn.set_sensitive(True)

    def on_url_source_set(self, userdata):
        is_url_source_set = self.remote_addr_entry.get_text() != ''
        if is_url_source_set and self.url_radio_btn.get_active():
            self.validate_revealer.set_reveal_child(True)
            self.save_btn.set_sensitive(True)
        else:
            self.validate_revealer.set_reveal_child(False)


    def on_zip_source_set(self, user_data):
        is_zip_source_set = self.source_file_chooser.get_filename() is not None
        if is_zip_source_set and self.zip_radio_btn.get_active():
            self.validate_revealer.set_reveal_child(True)
            self.save_btn.set_sensitive(True)
        else:
            self.validate_revealer.set_reveal_child(False)
    
    def on_dir_source_set(self, user_data):
        is_dir_source_set = self.source_folder_chooser.get_filename() is not None
        if is_dir_source_set and self.dir_radio_btn.get_active():
            self.validate_revealer.set_reveal_child(True)
            self.save_btn.set_sensitive(True)
        else:
            self.validate_revealer.set_reveal_child(False)

    def on_ca_file_reset_clicked(self, button):
        self.ca_chooser.set_filename("")
        self.set_setting(self.SETTING.CA, None)
        self.set_setting(self.SETTING.CA_SET_EXPLICIT, None)
    
    def on_show_password_btn_toggled(self, toggle):
        self.auth_pass.set_visibility(toggle.get_active())

    # General Tab
    def on_notification_switch_state_set(self, switch, state):
        self.set_setting(self.SETTING.NOTIFICATIONS, state)

    def on_update_on_launch_switch_state_set(self, switch, state):
        self.set_setting(self.SETTING.UPDATE_ON_START, state)

    def on_connect_on_launch_switch_state_set(self, switch, state):
        self.set_setting(self.SETTING.CONNECT_ON_LAUNCH, state)     