from eovpn_base import Base, SettingsManager
from openvpn import OpenVPN_eOVPN
import requests
import typing
import json
import logging
import subprocess
import re
import os
from os import path
from urllib.parse import urlparse
import shutil


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
        self.ovpn = OpenVPN_eOVPN(self.status_bar, self.spinner, None)
        
        self.remote_addr_entry = self.builder.get_object("openvpn_config_remote_addr")
        self.update_on_start = self.builder.get_object("update_on_start")

        self.req_auth = self.builder.get_object("req_auth")
        self.auth_user = self.builder.get_object("auth_user")
        self.auth_pass = self.builder.get_object("auth_pass")
        self.user_pass_box = self.builder.get_object("user_pass_box")

        self.crt_chooser = self.builder.get_object("crt_chooser")

        self.valid_result_lbl = self.builder.get_object("openvpn_settings_statusbar")

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



    def on_settings_window_delete_event(self, window, event) -> bool:
        window.hide()
        return True

    def on_settings_apply_btn_clicked(self, buttton):

        #to set sensitive based on remote value
        _builder = self.get_builder("main.glade")
        main_window_update_btn = _builder.get_object("update_btn")
        
        url = self.remote_addr_entry.get_text().strip()

        if url != '':
            self.set_setting("remote", url)
            main_window_update_btn.set_sensitive(True)
            folder_name = urlparse(url).netloc
            if folder_name == '':
                folder_name = "configs"

            self.set_setting("remote_savepath", path.join(self.EOVPN_CONFIG_DIR, folder_name))    
        
        else:
            self.set_setting("remote", None)
            main_window_update_btn.set_sensitive(False)
        
        #save folder name to config

        if self.req_auth.get_active():
            self.set_setting("req_auth", True)

            username = self.auth_user.get_text()
            self.set_setting("auth_user", username)

            password = self.auth_pass.get_text()
            self.set_setting("auth_pass", password)

            f = open(self.EOVPN_CONFIG_DIR + "/auth.txt","w+")
            f.write("{user}\n{passw}".format(user=username, passw=password))
            f.close()                         


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
        subprocess.run(["rm", self.EOVPN_CONFIG_DIR + "/settings.json"])
        #TODO - reset elements to blank

        self.remote_addr_entry.set_text("")
        self.update_on_start.set_active(False)

        self.req_auth.set_active(False)
        self.auth_user.set_text("")
        self.auth_pass.set_text("")

        self.crt_chooser.set_filename("")

        if self.get_setting("remote_savepath") != None:
            shutil.rmtree(self.get_setting("remote_savepath"))
        

        auth_file = os.path.join(self.EOVPN_CONFIG_DIR, "auth.txt")
        if os.path.exists(auth_file):
            logging.debug("{} removed".format(auth_file))
            os.remove(auth_file)


    def on_update_on_start_toggled(self, toggle):
        self.set_setting("update_on_start", toggle.get_active())

    def on_crt_chooser_file_set(self, chooser):
        self.set_setting("crt", chooser.get_filename())
        self.set_setting("crt_set_explicit", True)

    def on_req_auth_toggled(self, toggle):
        self.set_setting("req_auth", toggle.get_active())
        self.user_pass_box.set_sensitive(toggle.get_active())

    def on_settings_validate_btn_clicked(self, entry):
        self.ovpn.validate_remote(entry.get_text())