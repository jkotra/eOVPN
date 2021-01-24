import gi
gi.require_version('Gtk', '3.0')

import sys
import os
sys.path.insert(1, os.getcwd() + "/eovpn/")

from .openvpn import *