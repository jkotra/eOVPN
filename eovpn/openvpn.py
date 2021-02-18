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
import psutil
import shutil
import gettext

from .eovpn_base import Base, ThreadManager, SettingsManager

logger = logging.getLogger(__name__)

def is_openvpn_running():

    #for flatpak
    is_flatpak = os.getenv("FLATPAK_ID") is not None
    logger.debug("flatpak = {}".format(is_flatpak))

    if is_flatpak:
        out = subprocess.run(["flatpak-spawn", "--host", "pgrep", "openvpn"], stdout=subprocess.PIPE)
        if out.returncode != 0:
            return False, -1
        else:
            out = out.stdout.decode('utf-8')

            try:
                pid = int(out)
                return True, pid
            except Exception as e:
                logger.error(str(e))
                return False, -1 

    for proc in psutil.process_iter():
        if proc.name().lower() == "openvpn":
            return True, proc.pid

    return False, -1 

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
        
        if os.geteuid != 0:
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

        
        logger.info("openvpn_exe_cmd = {}".format(openvpn_exe_cmd))


        log_file_opt = openvpn_exe_cmd.index("--log")
        log_file = openvpn_exe_cmd[log_file_opt + 1]

        assert type(log_file) == str
        
        #open and close / create new log file
        open(log_file, 'w+').close()

        out = subprocess.run(openvpn_exe_cmd, stdout=subprocess.PIPE)
        if out.returncode != 0:
            return False

        start_time = time.time()

        while True and ((time.time() - start_time) <= self.timeout):
            connection_status = self.get_connection_status()
            logger.debug("status = {} timeout = {}".format(connection_status, time.time() - start_time))
            

            if connection_status:
                return True
            else:
                #check for errors.

                f = open(log_file, "r")
                for line in f.readlines():
                    for word in line.split(" "):

                        if "AUTH_FAILED" in word:
                            return gettext.gettext("Authentication failed.")

                        elif "SIGTERM" in word:
                            return gettext.gettext("OpenVPN Killed!")

                        elif "ERROR:" in word:
                            return line.split(":")[-1]
                        else:
                            continue  


                f.close()            
                    

            time.sleep(1)
        return False

    def disconnect(self):

        commands = []

        if os.getenv("FLATPAK_ID") is not None:
            commands.append("flatpak-spawn")
            commands.append("--host")
        
        status, pid = is_openvpn_running()
        logger.debug("openvpn_running={} pid={}".format(status, pid))

        if not status:
            return False
    
        commands.append("pkexec")
        commands.append("kill")
        commands.append("-15") #SIGTERM
        commands.append(str(pid))

        logger.debug("disconnect_cmd = {}".format(commands))

        out = subprocess.run(commands, stdout=subprocess.PIPE)
        if out.returncode != 0:
            return False        
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

    def __set_crt_auto(self):

        if not self.get_setting("crt_set_explicit") and self.get_setting("crt") is None:
            crt_re = re.compile(r'.crt')

            files = os.listdir(self.get_setting("remote_savepath"))                       
            crt = list(filter(crt_re.findall, files))

            logger.debug("{}".format(crt))

            if len(crt) >= 1 and self.get_setting("crt_set_explicit") != True:
                self.set_setting("crt", os.path.join(self.get_setting("remote_savepath"),
                                                    crt[-1]))        
    

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
    
    def __push_to_statusbar(self, message):
        if self.statusbar is not None:
            self.statusbar.push(1, message)

    def connect_eovpn(self, openvpn_config, auth_file, ca=None, logfile=None, callback=None) -> bool:

        self.spinner.start()
        self.__push_to_statusbar(gettext.gettext("Connecting.."))

        #check if config requires auth
        f = open(openvpn_config, "r")
        if "auth-user-pass" in f.read() and auth_file is None:
            self.spinner.stop()
            self.__push_to_statusbar(gettext.gettext("Config requires authorization (auth-user-pass)"))
            self.__set_statusbar_icon(False, False)
            return False

        connection_result = self.openvpn.connect("--config", openvpn_config, "--auth-user-pass", auth_file, "--ca", ca,
                     "--log", logfile, "--daemon")

        if type(connection_result) is not bool:
            # this is a error message

            self.__push_to_statusbar(connection_result)
            self.__set_statusbar_icon(False, False)
            self.spinner.stop()
            return False        

        if connection_result:
            self.__push_to_statusbar(gettext.gettext("Connected to {}.").format(openvpn_config.split('/')[-1]))
            self.__set_statusbar_icon(True, connected=True)
        else:
            self.__set_statusbar_icon(False)

        callback(connection_result)
        self.spinner.stop()
        return connection_result  
        

    def disconnect_eovpn(self, callback=None):

        self.spinner.start()

        disconnect_result = self.openvpn.disconnect()
  
        self.spinner.stop()

        if disconnect_result:
            self.__push_to_statusbar(gettext.gettext("Disconnected."))

        callback(disconnect_result)
        return disconnect_result
        
    def get_connection_status_eovpn(self) -> bool:
        return self.openvpn.get_connection_status()


    def get_version_eovpn(self, callback=None):
        self.spinner.stop()
        version = self.openvpn.get_version()

        result = False

        def not_found():
            self.__push_to_statusbar(gettext.gettext("OpenVPN not found."))
            self.__set_statusbar_icon(False)

        if version is False:
            not_found()
            result = False
        else:
            self.__push_to_statusbar(version)
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
    
    def download_config_to_destination(self, remote, destination):
        
        def make_zip_from_b(content):
            return zipfile.ZipFile(io.BytesIO(content), "r")

        def download_zip(remote):
            try:
                remote_c = requests.get(remote, timeout=360)
            except Exception as e:
                logger.error(str(e))
                return False
            
            zip_file = make_zip_from_b(remote_c.content)
            return zip_file

        remote = os.path.expanduser(remote)

        if os.path.isdir(remote) and remote.endswith("zip") == False:
            shutil.copytree(remote, destination, dirs_exist_ok=True)
            return True

        elif os.path.isfile(remote) and remote.endswith("zip") == True:
            zip_file = make_zip_from_b(open(remote, "rb").read())
        else:
            zip_file = download_zip(remote)
        
        #list of files inside zip
        files_in_zip = zip_file.namelist()

        configs = list(filter(self.ovpn.findall, files_in_zip))
        certs = list(filter(self.crt.findall, files_in_zip ))
        all_files = configs + certs
        if len(configs) > 0:
            for file_name in all_files:      
                file = zip_file.getinfo(file_name)
                file.filename = os.path.basename(file.filename) #remove nested dir
                logger.info(file.filename)
                zip_file.extract(file, destination)
            return True

        return False  

    #this function is used to update
    def download_config_and_update_liststore(self, remote, destination, storage, callback):
        
        if remote == None or remote == "":
            self.__push_to_statusbar(gettext.gettext("Invalid Remote"))
            self.__set_statusbar_icon(False)
            return False
        
        self.spinner.start()
        self.__push_to_statusbar(gettext.gettext("Updating..."))

        def download():

            result = None

            if self.download_config_to_destination(remote, destination):
                self.__push_to_statusbar(gettext.gettext("Config(s) updated!"))
                self.__set_statusbar_icon(True)
                GLib.idle_add(self.load_configs_to_tree,
                              storage,
                              self.get_setting("remote_savepath"))
                result = True
                self.__set_crt_auto()              
            else:
                self.__push_to_statusbar(gettext.gettext("No config(s) found!"))
                self.__set_statusbar_icon(False)
                result = False

            self.spinner.stop()
            if callback is not None:
                callback(result)
        
        if not os.path.exists(destination):
            os.mkdir(destination)

        ThreadManager().create(download, None, True)



    def validate_remote(self, remote):

        def remote_validate():

            self.spinner.start()

            tmp_path = "/tmp/eovpn_validate/"
            if os.path.isdir(tmp_path):
                shutil.rmtree(tmp_path)
            else:
                os.mkdir(tmp_path)    

            res = self.download_config_to_destination(remote, tmp_path)
            if res == False:
                logger.debug("Cannot download / save from remote!")
                return False

            all_files = os.listdir(tmp_path)
            print(all_files)

            configs = list(filter(self.ovpn.findall, all_files))
            if len(configs) > 0:
                #show message dialog
                GLib.idle_add(self.message_dialog, gettext.gettext("Success"),
                 gettext.gettext("Valid Remote"), 
                gettext.gettext("{} OpenVPN configuration's found.").format(len(configs)))
            else:
                GLib.idle_add(self.message_dialog, 
                gettext.gettext("Validate Error"), 
                gettext.gettext("Error"),
                 gettext.gettext("Unknown error! check debug log for more information"))

            self.spinner.stop()
        

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