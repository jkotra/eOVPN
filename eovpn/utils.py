import os
import logging
import zipfile
import io
import shutil
import re
import subprocess
import gettext
import urllib.request

from gi.repository import GLib, Gtk, GLib
import gettext

import re
import subprocess

logger = logging.getLogger(__name__)


class NotZipException(Exception):
    pass

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
            hdr = {'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.11 (KHTML, like Gecko) Chrome/23.0.1271.64 Safari/537.11',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Charset': 'ISO-8859-1,utf-8;q=0.7,*;q=0.3',
            'Accept-Encoding': 'none',
            'Accept-Language': 'en-US,en;q=0.8',
            'Connection': 'keep-alive'}
            req = urllib.request.Request(remote, headers=hdr)
            remote_c = urllib.request.urlopen(req)  
            return make_zip_from_b(remote_c.read())

    remote = os.path.expanduser(remote)

    try:
        zip_file = download_zip(remote)
    except:
        raise NotZipException(gettext.gettext("Configuration Source MUST be a ZIP file."))    
        
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
    
    return certs

def ovpn_is_auth_required(ovpn_file):
    f = open(ovpn_file, "r")
    data = f.read()

    if "auth-user-pass" in data:
        return True
    else:
        return False