import os
import sys
from gi.repository import Gio
import subprocess
import argparse
import logging



logging.basicConfig(level=logging.DEBUG, format='%(levelname)s:%(name)s:%(funcName)s:%(message)s')

parser = argparse.ArgumentParser()
parser.add_argument('-b', action="store_true", required=False)
args = parser.parse_args()

APP_NAME = "com.github.jkotra.eovpn"

sys.path.insert(1, os.getcwd())
sys.path.insert(1, os.getcwd() + "/eovpn/")

from eovpn.application import app

if __name__ == "__main__":

    if not os.path.exists("build"):
        subprocess.run(["meson", "build"])

    try:
        gre_path = "build/data/com.github.jkotra.eovpn.gresource"
        if args.b:
            subprocess.run(["ninja", "-C", "build"])

        resource = Gio.resource_load(gre_path)
    except Exception as e:
        print(e)
        exit(1)

    Gio.Resource._register(resource)
    app.run(None)