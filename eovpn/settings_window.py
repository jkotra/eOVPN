from .eovpn_base import Base, SettingsManager, ThreadManager
from .openvpn import OpenVPN_eOVPN
import requests
import typing
import json
import logging
import subprocess
import re
import os
from os import path
import time
from gi.repository import GLib
from urllib.parse import urlparse
import shutil

logger = logging.getLogger(__name__)

class SettingsWindow(Base):
    def __init__(self):
        super(SettingsWindow, self).__init__()

        self.builder = self.get_builder("settings.glade")
        self.builder.connect_signals(SettingsWindowSignalHandler(self.builder))
        self.window = self.builder.get_object("settings_window")

    def show(self):
        self.window.show()    


class SettingsWindowSignalHandler(SettingsManager):
    def __init__(self, builder):
        super(SettingsWindowSignalHandler, self).__init__()
        self.builder = builder
        self.spinner = self.builder.get_object("settings_spinner")
        self.status_bar = self.builder.get_object("openvpn_settings_statusbar")
        self.ovpn = OpenVPN_eOVPN(spinner = self.spinner)
        
        self.remote_addr_entry = self.builder.get_object("openvpn_config_remote_addr")
        self.update_on_start = self.builder.get_object("update_on_start")

        self.setting_saved_reveal = self.builder.get_object("reveal_settings_saved")
        #by default, it's not revealed (duh!)
        self.setting_saved_reveal.set_reveal_child(False)
        #only close the first time
        self.reveal_delay_close = False
        
        #load tree from mainwindow
        main_builder = self.get_builder("main.glade")
        self.config_storage = main_builder.get_object("config_storage")

        self.save_btn = self.builder.get_object("settings_apply_btn")
        self.save_btn.set_sensitive(False)

        self.req_auth = self.builder.get_object("req_auth")
        self.auth_user = self.builder.get_object("auth_user")
        self.auth_pass = self.builder.get_object("auth_pass")
        self.user_pass_box = self.builder.get_object("user_pass_box")

        self.crt_chooser = self.builder.get_object("crt_chooser")

        self.valid_result_lbl = self.builder.get_object("openvpn_settings_statusbar")
        self.connect_on_launch = self.builder.get_object("connect_on_launch_chkbox")
        self.notifications_chkbox = self.builder.get_object("notifications_chkbox")

        self.are_you_sure = self.builder.get_object("settings_reset_ask_sure")

        self.update_settings_ui()
    
    def push_to_statusbar(self, message):
        pass
    
    def update_settings_ui(self):
        remote = self.get_setting("remote")
        if remote is not None:
            self.remote_addr_entry.set_text(remote)

        if self.get_setting("update_on_start"):
            self.update_on_start.set_active(True)

        if self.get_setting("notifications"):
            self.notifications_chkbox.set_active(True)    
        
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

        is_connect_on_launch = self.get_setting("connect_on_launch")

        if is_connect_on_launch:
            self.connect_on_launch.set_active(True)


    def on_settings_window_delete_event(self, window, event) -> bool:
        window.hide()
        return True

    def on_settings_apply_btn_clicked(self, buttton):

        initial_remote = self.get_setting("remote")

        #to set sensitive based on remote value
        _builder = self.get_builder("main.glade")
        
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
            self.ovpn.download_config(url,
                                self.get_setting("remote_savepath"),
                                self.config_storage)

        #show settings saved notfication
        self.setting_saved_reveal.set_reveal_child(True)
        if self.reveal_delay_close == False:
            ThreadManager().create(self.close_revealer_after_sec, (5, self.setting_saved_reveal,), False)

    def close_revealer_after_sec(self, sec: int, revealer):
        time.sleep(sec)
        if self.setting_saved_reveal.get_reveal_child() and self.reveal_delay_close == False:
            revealer.set_reveal_child(False)
            self.reveal_delay_close = True

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

        self.remote_addr_entry.set_text("")
        self.update_on_start.set_active(False)

        self.req_auth.set_active(False)
        self.auth_user.set_text("")
        self.auth_pass.set_text("")

        self.crt_chooser.set_filename("")
        
        #remove config dir
        if self.get_setting("remote_savepath") != None:
            if os.path.exists(self.get_setting("remote_savepath")):
                logger.debug("removing {}".format(self.get_setting("remote_savepath")))
                shutil.rmtree(self.get_setting("remote_savepath"))
                self.config_storage.clear()


        auth_file = os.path.join(self.EOVPN_CONFIG_DIR, "auth.txt")
        if os.path.exists(auth_file):
            logger.debug("removing {}".format(auth_file))
            os.remove(auth_file)

        subprocess.run(["rm", self.EOVPN_CONFIG_DIR + "/settings.json"])


    def on_update_on_start_toggled(self, toggle):
        self.set_setting("update_on_start", toggle.get_active())

    def on_crt_chooser_file_set(self, chooser):
        self.set_setting("crt", chooser.get_filename())
        self.set_setting("crt_set_explicit", True)

    def on_req_auth_toggled(self, toggle):
        self.set_setting("req_auth", toggle.get_active())
        self.user_pass_box.set_sensitive(toggle.get_active())

    def on_connect_on_launch_chkbox_toggled(self, toggle):
        self.set_setting("connect_on_launch", toggle.get_active())

    def on_settings_validate_btn_clicked(self, entry):
        self.ovpn.validate_remote(entry.get_text())

    def save_btn_activate(self, editable):
        self.save_btn.set_sensitive(True)

    def on_notifications_chkbox_toggled(self, toggle):
        self.set_setting("notifications", toggle.get_active())    