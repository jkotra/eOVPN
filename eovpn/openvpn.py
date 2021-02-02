import subprocess
import zipfile
import io
import re
import requests
import io
import os
import time
import logging
from gi.repository import GLib
import platform
import psutil
import shutil

from .eovpn_base import Base, ThreadManager, SettingsManager

logger = logging.getLogger(__name__)


class OpenVPN:

    def __init__(self, timeout=120):
        self.timeout = timeout    

    def get_connection_status(self) -> bool:

        nif = psutil.net_if_stats()

        for nif_a in nif.keys():
            if "tun" in nif_a:
                if nif[nif_a].isup:
                    return True

        return False


    def connect(self, *args):

        args = list(args)

        openvpn_exe_cmd = []

        if os.getenv("FLATPAK_ID") is not None:
            openvpn_exe_cmd.append("flatpak-spawn")
            openvpn_exe_cmd.append("--host")

        openvpn_exe_cmd.append("pkexec")
        openvpn_exe_cmd.append("openvpn")

        for arg in args:
            try:
                if arg is None:
                    openvpn_exe_cmd.pop()
                    continue

                openvpn_exe_cmd.append(arg)    
            except IndexError:
                pass

        
        logger.info("args = {}".format(openvpn_exe_cmd))

        out = subprocess.run(openvpn_exe_cmd, stdout=subprocess.PIPE)
        start_time = time.time()

        while True and ((time.time() - start_time) <= self.timeout):
            connection_status = self.get_connection_status()
            logger.debug("status = {} timeout = {}".format(connection_status, time.time() - start_time))

            if connection_status:
                return True
            else:
                time.sleep(1)
        return False

    def disconnect(self):

        commands = []

        if os.getenv("FLATPAK_ID") is not None:
            commands.append("flatpak-spawn")
            commands.append("--host")

        commands.append("pkexec")
        commands.append("killall")
        commands.append("openvpn")    

        subprocess.call(commands)
        start_time = time.time()

        while True and ((time.time() - start_time) <= self.timeout):
            connection_status = self.get_connection_status()
            logger.debug("status = {} timeout = {}".format(connection_status, time.time() - start_time))

            if not connection_status:
                return True
            else:
                time.sleep(1)    

        return False

    def get_version(self):

        opvpn_ver = re.compile("OpenVPN [0-9]*.[0-9]*.[0-9]")

        commands = []
        if os.getenv("FLATPAK_ID") is not None:
            commands.append("flatpak-spawn")
            commands.append("--host")
        
        commands.append("openvpn")
        commands.append("--version")
        try:
            out = subprocess.run(commands, stdout=subprocess.PIPE)
        except Exception as e:
            logger.critical(str(e))
            return False
  
        out = out.stdout.decode('utf-8')
        ver = opvpn_ver.findall(out)

        if len(ver) > 0:
            return ver[0]

        return False

class OpenVPN_eOVPN(SettingsManager):

    def __init__(self, statusbar=None, spinner=None, statusbar_icon=None):

        super(OpenVPN_eOVPN, self).__init__()
        self.openvpn = OpenVPN(60)

        self.spinner = spinner
        self.statusbar = statusbar
        self.statusbar_icon = statusbar_icon

        self.ovpn = re.compile('.ovpn')
        self.crt = re.compile(r'.crt|cert')
    
    def __set_statusbar_icon(self, result: bool, connected: bool = False):
        if self.statusbar_icon is not None:
            if result and connected:
                self.statusbar_icon.set_from_icon_name("network-vpn-symbolic", 1)
            elif result is None:
                self.statusbar_icon.set_from_icon_name("emblem-important-symbolic", 1)
            elif result:
                self.statusbar_icon.set_from_icon_name("emblem-ok-symbolic", 1)
            else:
                self.statusbar_icon.set_from_icon_name("dialog-error-symbolic", 1)


    def connect_eovpn(self, openvpn_config, auth_file, ca=None, logfile=None, callback=None) -> bool:

        self.spinner.start()
        self.statusbar.push(1, "Connecting..")

        connection_result = self.openvpn.connect("--config", openvpn_config, "--auth-user-pass", auth_file, "--ca", ca,
                     "--log", logfile, "--daemon")

        if connection_result:
            self.statusbar.push(1, "Connected to {}.".format(openvpn_config.split('/')[-1]))
            self.__set_statusbar_icon(True, connected=True)
        else:
            self.__set_statusbar_icon(False)

        callback(connection_result)
        self.spinner.stop()
        return connection_result  
        

    def disconnect_eovpn(self, callback=None):

        self.spinner.start()
        self.statusbar.push(1, "Disconnecting..")
        self.__set_statusbar_icon(None)

        disconnect_result = self.openvpn.disconnect()
  
        self.spinner.stop()
        if disconnect_result:
            self.statusbar.push(1, "Disconnected.")

        callback(disconnect_result)
        return disconnect_result
        
    def get_connection_status_eovpn(self) -> bool:
        return self.openvpn.get_connection_status()


    def get_version_eovpn(self, callback=None):
        self.spinner.stop()
        version = self.openvpn.get_version()

        result = False

        def not_found():
            self.statusbar.push(1, "OpenVPN not found.")
            self.__set_statusbar_icon(False)

        if version is False:
            not_found()
            result = False
        else:
            self.statusbar.push(1, version)
            result = True    

        if callback is not None:
            callback(result)
    
    def load_configs_to_tree(self, storage, config_folder):
        try:
            config_list = os.listdir(config_folder)
            config_list.sort()
        except Exception as e:
            logger.error(str(e))
            return False

        try:
            try:
                storage.clear()
            except AttributeError:
                pass

            if len(config_list) <= 0:
                return False

        except Exception as e:
            logger.error(str(e))    

        for f in config_list:
            if f.endswith(".ovpn"):
                storage.append([f])
    
    def download_config_to_dest_plain(self, remote, destination):

        try:
            test_remote = requests.get(remote, timeout=360)
        except Exception as e:
            logger.error(str(e))

        if test_remote.status_code == 200:

            x_zip = zipfile.ZipFile(io.BytesIO(test_remote.content), "r")
            files_in_zip = x_zip.namelist()

            configs = list( filter(self.ovpn.findall, files_in_zip) )
            certs = list( filter(self.crt.findall, files_in_zip ) )
            all_files = configs + certs
            if len(configs) > 0:

                for file_name in all_files:
                            
                    file = x_zip.getinfo(file_name)
                    file.filename = os.path.basename(file.filename) #remove nested dir
                    logger.info(file.filename)
                    x_zip.extract(file, destination)
                return True
            return False  


    def download_config(self, remote, destination, storage):

        def download():

            self.spinner.start()

            if self.download_config_to_dest_plain(remote, destination):

                self.statusbar.push(1, "Config(s) updated!")
                self.__set_statusbar_icon(True)
                GLib.idle_add(self.load_configs_to_tree,
                              storage,
                              self.get_setting("remote_savepath"))
            else:
                self.statusbar.push(1, "No config(s) found!")
                self.__set_statusbar_icon(False)

            self.spinner.stop()
        
        if not os.path.exists(destination):
            os.mkdir(destination)
        
        if os.path.isdir(os.path.expanduser(remote)):
            
            #this is a local directory
            remote = os.path.expanduser(remote)
            
            shutil.copytree(remote, destination, dirs_exist_ok=True)
            GLib.idle_add(self.load_configs_to_tree,
                              storage,
                              self.get_setting("remote_savepath"))
            return True

        ThreadManager().create(download, None, True)



    def validate_remote(self, remote):

        def remote_validate():
            self.spinner.start()

            try:
                test_remote = requests.get(remote, timeout=360)
                if test_remote.status_code == 200:
                    x_zip = zipfile.ZipFile(io.BytesIO(test_remote.content), "r")
                    configs = list( filter(self.ovpn.findall, x_zip.namelist() ) )
                    if len(configs) > 0:
                        GLib.idle_add(self.message_dialog, "Success", "Valid Remote", "{} OpenVPN configuration's found.".format(len(configs)))
                    else:
                        raise Exception("No configs found!")
            except Exception as e:
                GLib.idle_add(self.message_dialog, "Validate Error", "Error", str(e))
            self.spinner.stop()
        
        if os.path.isdir(os.path.expanduser(remote)):
            remote = os.path.expanduser(remote)
            configs = list( filter(self.ovpn.findall, os.listdir(remote) ) )
            if len(configs) > 0:
                GLib.idle_add(self.message_dialog, "Success", "Valid Source", "{} OpenVPN configuration's found.".format(len(configs)))
            else:
                raise Exception("No configs found!")
        else:
            ThreadManager().create(remote_validate, None, True)    


        

    def openvpn_config_set_protocol(self,config, label):
        proto = re.compile("proto [tcp|udp]*")
        f = open(config).read()

        matches = proto.search(f)
        
        try:
            protocol = matches.group().split(" ")[-1]
            label.set_text(protocol.upper())
            label.show()
        except Exception as e:
            logger.error(str(e))    
            