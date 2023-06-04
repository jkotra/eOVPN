import os
import sys
from gi.repository import Gio
import subprocess
import shutil

OPENVPN3 = True

try:
    import openvpn3
except:
    OPENVPN3 = False

APP_NAME = "com.github.jkotra.eovpn"

sys.path.insert(1, os.getcwd())
sys.path.insert(1, os.getcwd() + "/eovpn/")
os.environ["GSETTINGS_SCHEMA_DIR"] = "data/"

def reset():
    subprocess.run(["rm", "-rf", "build"])
    subprocess.run(["meson", "setup", "build", "-Dprefix=/usr", f"-Dopenvpn3={OPENVPN3}"])
    subprocess.run(["ninja", "-C", "build"])

def copy_libs():
    shutil.copyfile("build/subprojects/networkmanager/libeovpn_nm.so", "eovpn/backend/networkmanager/libeovpn_nm.so")
    shutil.copyfile("build/subprojects/networkmanager/_libeovpn_nm.so", "eovpn/backend/networkmanager/_libeovpn_nm.so")

    if OPENVPN3:
        shutil.copyfile("build/subprojects/openvpn3/libopenvpn3.so", "eovpn/backend/openvpn3/libopenvpn3.so")
        shutil.copyfile("build/subprojects/openvpn3/_libopenvpn3.so", "eovpn/backend/openvpn3/_libopenvpn3.so")

    shutil.copyfile("build/eovpn/metadata.json", "eovpn/metadata.json")

if __name__ == "__main__":
    reset()
    copy_libs()

    from eovpn.application import launch_eovpn

    gre_path = "build/data/com.github.jkotra.eovpn.gresource"
    resource = Gio.resource_load(gre_path)
    subprocess.run(["glib-compile-schemas", "data/"])
    sys.argv.append("--debug")
    sys.argv.append("DEBUG")
    Gio.Resource._register(resource)

    launch_eovpn()