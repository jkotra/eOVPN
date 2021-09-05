import os
import logging
import zipfile
import io
import shutil
import re
import subprocess
import urllib.request

from gi.repository import GLib, Gtk, GLib
import gettext

from .eovpn_base import ThreadManager
import re
import subprocess

logger = logging.getLogger(__name__)

def download_remote_to_destination(remote, destination):

    ovpn = re.compile('.ovpn')
    crt = re.compile(r'.crt|cert|pem')
     
    def make_zip_from_b(content):
        return zipfile.ZipFile(io.BytesIO(content), "r")

    def download_zip(remote):
        if os.path.exists(remote):
            f = open(remote, "rb")
            return make_zip_from_b(f.read())
        else:
            remote_c = urllib.request.urlopen(remote)  
            return make_zip_from_b(remote_c.read())

    remote = os.path.expanduser(remote)
    zip_file = download_zip(remote)
        
    #list of files inside zip
    files_in_zip = zip_file.namelist()

    configs = list( filter(ovpn.findall, files_in_zip) )
    certs = list( filter(crt.findall, files_in_zip) )
    all_files = configs + certs
    if len(configs) > 0:
        for file_name in all_files:      
            file = zip_file.getinfo(file_name)
            file.filename = os.path.basename(file.filename) #remove nested dir
            logger.info(file.filename)
            zip_file.extract(file, destination)
        return True

    return False  

def validate_remote(remote):
    save_path = os.path.join(GLib.get_user_config_dir(), "eovpn", "CONFIGS")
    
    if os.path.exists(save_path):
        if len(os.listdir(save_path)) > 1:
            shutil.rmtree(save_path)
    else:
        os.makedirs(save_path)        


    return download_remote_to_destination(remote, save_path)

def ovpn_is_auth_required(ovpn_file):
    f = open(ovpn_file, "r")
    data = f.read()

    if "auth-user-pass" in data:
        return True
    else:
        pass

def is_selinux_enforcing():
    
    #try if we can import selinux python bindings (preferred way of checking)
    try:
        import selinux
        return bool(selinux.is_selinux_enabled()) and bool(selinux.security_getenforce())
    except Exception as e:
        logger.error(e)

    if os.getenv("FLATPAK_ID") is not None:
        commands = []
        commands.append("flatpak-spawn")
        commands.append("--host")
        commands.append("sestatus")

        try:
            out = subprocess.run(commands, stdout=subprocess.PIPE)
            out = out.stdout.decode('utf-8')
            logger.debug(out)
            if ("enabled" in out) and ("enforcing" in out):
                return True
        except:
            return False

    return False