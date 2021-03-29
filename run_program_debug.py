import os
import sys
from gi.repository import Gio
import subprocess
import logging
import shutil

APP_NAME = "com.github.jkotra.eovpn"

sys.path.insert(1, os.getcwd())
sys.path.insert(1, os.getcwd() + "/eovpn/")
os.environ["GSETTINGS_SCHEMA_DIR"] = "data/"

from eovpn.application import launch_eovpn

if __name__ == "__main__":
    
    if not os.path.exists("build"):
        subprocess.run(["meson", "build", "-Dprefix=/usr"])
    try:
        gre_path = "build/data/com.github.jkotra.eovpn.gresource"
        subprocess.run(["ninja", "-C", "build"])
        
        try:
            shutil.copyfile("build/subprojects/networkmanager/libeovpn_nm.so",
                            "eovpn/networkmanager/libeovpn_nm.so")
        except Exception as e:
            print(e)

        resource = Gio.resource_load(gre_path)
        subprocess.run(["glib-compile-schemas", "data/"])
        sys.argv.append("--debug")
        sys.argv.append("DEBUG")
    except Exception as e:
        print(e)
        exit(1)

    Gio.Resource._register(resource)
    launch_eovpn()