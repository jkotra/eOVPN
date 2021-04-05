import os
import logging
import zipfile
import io
import shutil
import re
import subprocess
import requests

from gi.repository import GLib, Gtk, GLib
import gettext

from .eovpn_base import ThreadManager, SettingsManager
import re
import subprocess

logger = logging.getLogger(__name__)

ovpn = re.compile('.ovpn')
crt = re.compile(r'.crt|cert|pem')

def message_dialog(primary_text, secondary_text):
    messagedialog = Gtk.MessageDialog(message_format="MessageDialog")
    messagedialog.set_markup("<span size='12000'><b>{}</b></span>".format(primary_text))
    messagedialog.format_secondary_text(secondary_text)
    messagedialog.add_button("_Close", Gtk.ResponseType.CLOSE)
    messagedialog.run()
    messagedialog.hide()

def load_configs_to_tree(storage, config_folder):
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


def download_remote_to_destination(remote, destination):
     
    def make_zip_from_b(content):
        return zipfile.ZipFile(io.BytesIO(content), "r")

    def download_zip(remote):
        try:
            remote_c = requests.get(remote, timeout=360)
        except Exception as e:
            logger.error(str(e))
            raise(e)
            
        zip_file = make_zip_from_b(remote_c.content)
        return zip_file

    remote = os.path.expanduser(remote)
    
    logger.info("remote={}, isdir={}, iszip={}".format(remote, os.path.isdir(remote), os.path.isfile(remote) and remote.endswith("zip") == True))
    if os.path.isdir(remote):
        logger.debug("remote is a local directory!")
        shutil.copytree(remote, destination, dirs_exist_ok=True)
        return True

    elif os.path.isfile(remote) and remote.endswith("zip") == True:
        logger.debug("remote is a local zip file!")
        zip_file = make_zip_from_b(open(remote, "rb").read())
    else:
        zip_file = download_zip(remote)
        
    #list of files inside zip
    files_in_zip = zip_file.namelist()

    configs = list(filter(ovpn.findall, files_in_zip))
    certs = list(filter(crt.findall, files_in_zip ))
    all_files = configs + certs
    if len(configs) > 0:
        for file_name in all_files:      
            file = zip_file.getinfo(file_name)
            file.filename = os.path.basename(file.filename) #remove nested dir
            logger.info(file.filename)
            zip_file.extract(file, destination)
        return True

    return False  


def validate_remote(remote, spinner = None):

    tmp_path = os.path.join(GLib.get_tmp_dir(), "eovpn_validate")

    def remote_validate():
        if spinner is not None:
            spinner.start()

        if os.path.isdir(tmp_path):
            try:
                shutil.rmtree(tmp_path)
            except Exception as e:
                logger.error(e)

        else:
            os.mkdir(tmp_path)    
            
        try:
            res = download_remote_to_destination(remote, tmp_path)
        except Exception as e:
            logger.error(e)
            if spinner is not None:
                spinner.stop()
            return False    

        if res == False:
            return False

        all_files = os.listdir(tmp_path)

        configs = list(filter(ovpn.findall, all_files))
        if len(configs) > 0:
            #show message dialog
            GLib.idle_add(message_dialog,
            gettext.gettext("Valid Remote"), 
            gettext.gettext("{} OpenVPN configuration's found.").format(len(configs)))
        if spinner is not None:
            spinner.stop()
        

    ThreadManager().create(remote_validate, None, True)    


def set_crt_auto():

    settings = SettingsManager()

    if not settings.get_setting("crt_set_explicit") and settings.get_setting("crt") is None:

        files = os.listdir(settings.get_setting("remote_savepath"))                       
        crt_found = list(filter(crt.findall, files))
        print(crt_found)

        logger.debug("crt.findall = {}".format(crt_found))

        if len(crt_found) >= 1 and settings.get_setting("crt_set_explicit") != True:
            settings.set_setting("crt", os.path.join(settings.get_setting("remote_savepath"),
                                                 crt_found[-1]))        

def is_selinux_enforcing():
    try:
        commands = []
        if os.getenv("FLATPAK_ID") is not None:
            commands.append("flatpak-spawn")
            commands.append("--host")
        
        commands.append("sestatus")

        out = subprocess.run(commands, stdout=subprocess.PIPE)
    except:
        return False
    out = out.stdout.decode('utf-8')
    if ("enabled" in out) and ("enforcing" in out):
        return True
    return False            
