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

from .eovpn_base import ThreadManager
import re
import subprocess

logger = logging.getLogger(__name__)


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