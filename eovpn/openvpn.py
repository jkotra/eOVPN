import subprocess
import zipfile
import io
import re
import requests
import io
import threading
import os
from time import sleep
import logging
from gi.repository import Gtk,GLib

logger = logging.getLogger(__name__)

def message_dialog(title, primary_text, secondary_text):
    messagedialog = Gtk.MessageDialog(message_format="MessageDialog")
    messagedialog.set_title(title)
    messagedialog.set_markup("<span size='12000'><b>{}</b></span>".format(primary_text))
    messagedialog.format_secondary_text(secondary_text)
    messagedialog.add_button("_Close", Gtk.ResponseType.CLOSE)
    messagedialog.run()
    messagedialog.hide()


class OpenVPN:

    def __init__(self, statusbar, spinner, statusbar_icon=None, updater=None):
        self.spinner = spinner
        self.statusbar = statusbar
        self.statusbar_icon = statusbar_icon
        self.updater = updater

        self.ovpn = re.compile('.ovpn')
        self.crt = re.compile(r'.crt|cert')
    
    def __set_statusbar_icon(self, result: bool):
        if self.statusbar_icon is not None:
            if result is None:
                self.statusbar_icon.set_from_icon_name("dialog-information", 1)
            if result:
                self.statusbar_icon.set_from_icon_name("dialog-ok", 1)
            else:
                self.statusbar_icon.set_from_icon_name("dialog-warning", 1)
    

    def connect(self, openvpn_config, auth_file, ca=None, logfile=None):

        self.spinner.start()
        self.statusbar.push(1, "Connecting...")

        commands = ["pkexec", "openvpn"]
        commands.append("--config")
        commands.append(openvpn_config)
        commands.append("--auth-user-pass")
        commands.append(auth_file)

        if ca is not None:
            commands.append("--ca")
            commands.append(ca)

        if logfile is not None:
            commands.append("--log")
            commands.append(logfile)
        
        commands.append("--daemon")

        out = subprocess.run(commands, capture_output=True)
        
        
        while True:   
            if r := self.get_connection_status():
                self.updater()
                break
            else:
                logger.info("get_connection_status() = {}".format(r))
                sleep(1)

        self.spinner.stop()

        if out.returncode == 0:
            
            self.statusbar.push(1, "Connected to {}.".format(openvpn_config.split('/')[-1]))
            self.__set_statusbar_icon(True)
            return True
        else:
            self.statusbar.push(1, "Failed to connect!")
            self.__set_statusbar_icon(False)
            return False
        

    def disconnect(self, logfile):

        self.spinner.start()
        self.statusbar.push(1, "Disconnecting..")
        self.__set_statusbar_icon(None)

        subprocess.call(["pkexec", "killall", "openvpn"]) 

        while True:
            if (r := self.get_connection_status()) is False:
                self.updater()
                break
            else:
                logger.info("get_connection_status() = {}".format(r))
                sleep(1) 
        
        self.spinner.stop()
        self.statusbar.push(1, "Disconnected.")
        self.__set_statusbar_icon(None)
        return True
        
    def get_connection_status(self) -> bool:
        ip_output = subprocess.run(["ip", "link"], stdout=subprocess.PIPE).stdout.decode('utf-8')
        vmnet = re.compile("tun.*:")
        link = vmnet.findall(ip_output)
        
        if len(link) > 0:
            return True
        else:
            return False    

    def get_version(self):

        #find openvpn and display version if found
        opvpn_ver = re.compile("OpenVPN [0-9]*.[0-9]*.[0-9]")
        self.spinner.start()
        out = subprocess.run(["openvpn", "--version"], stdout=subprocess.PIPE)
        out = out.stdout.decode('utf-8')

        ver = opvpn_ver.findall(out)

        if len(ver) > 0:
            self.statusbar.push(1, ver[0])
            self.__set_statusbar_icon(None)
        else:
            self.statusbar.push(1, "OpenVPN not found.")
            self.__set_statusbar_icon(False)
        self.spinner.stop()
    
    def load_configs_to_tree(self, storage, config_folder):
        storage.clear()
        
        try:
            config_list = os.listdir(config_folder)
        except FileNotFoundError:
            return False

        if len(config_list) <= 0:
            return False

        config_list.sort()

        for f in config_list:
            if f.endswith("ovpn"):
                storage.append([f])

    def download_config(self, remote, destination):

        def download():

            self.spinner.start()

            try:
                test_remote = requests.get(remote)
                if test_remote.status_code == 200:

                    x_zip = zipfile.ZipFile(io.BytesIO(test_remote.content), "r")
                    

                    #remove path
                    #for file in x_zip.infolist():
                        #file.filename = os.path.basename(file.filename)


                    files_in_zip = x_zip.namelist()


                    configs = list( filter(self.ovpn.findall, files_in_zip) )
                    certs = list( filter(self.crt.findall, files_in_zip ) )
                    all_files = configs + certs
                    if len(configs) > 0:

                        for file_name in all_files:
                            
                            file = x_zip.getinfo(file_name)
                            file.filename = os.path.basename(file.filename)
                            logger.info(file.filename)
                            x_zip.extract(file, destination)

                        #x_zip.extractall(destination)
                        self.statusbar.push(1, "Config(s) updated!")
                        self.__set_statusbar_icon(True)
                    else:
                        self.statusbar.push(1, "No config(s) found!")
                        self.__set_statusbar_icon(False)

            except Exception as e:
                self.statusbar.push(1, str(e))

            self.spinner.stop()
        
        if not os.path.exists(destination):
            os.mkdir(destination)

        th = threading.Thread(target=download)
        th.start()


    
    def validate_remote(self, remote):


        def validate():
            self.spinner.start()

            try:
                test_remote = requests.get(remote, timeout=360)
                if test_remote.status_code == 200:
                    x_zip = zipfile.ZipFile(io.BytesIO(test_remote.content), "r")
                    configs = list( filter(self.ovpn.findall, x_zip.namelist() ) )
                    if len(configs) > 0:
                        GLib.idle_add(message_dialog, "Success", "Valid Remote", "{} OpenVPN configuration's found.".format(len(configs)))
                    else:
                        raise Exception("No configs found!")
            except Exception as e:
                GLib.idle_add(message_dialog, "Error", "Error", str(e))
            self.spinner.stop()
            

        th = threading.Thread(target=validate)
        th.start()    