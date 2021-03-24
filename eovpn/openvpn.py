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
        logger.info("openvpn version output: " + out)
        ver = opvpn_ver.findall(out)

        if len(ver) > 0:
            return ver[0]

        return False