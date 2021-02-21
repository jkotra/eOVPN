import os
import sys
from gi.repository import Gio
import subprocess
import logging

APP_NAME = "com.github.jkotra.eovpn"

sys.path.insert(1, os.getcwd())
sys.path.insert(1, os.getcwd() + "/eovpn/")

logging.basicConfig(level=logging.DEBUG, format='%(levelname)s:%(name)s.py:%(funcName)s:%(message)s')

from eovpn.application import launch_eovpn

if __name__ == "__main__":

    if not os.path.exists("build"):
        subprocess.run(["meson", "build"])
    try:
        gre_path = "build/data/com.github.jkotra.eovpn.gresource"
        subprocess.run(["ninja", "-C", "build"])
        resource = Gio.resource_load(gre_path)
    except Exception as e:
        print(e)
        exit(1)

    Gio.Resource._register(resource)
    launch_eovpn()