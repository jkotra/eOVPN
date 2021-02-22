import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, GLib, Gio

import os, sys
import logging

from .eovpn_base import Base
from .main_window import MainWindow

class eovpn(Base):
    def __init__(self, app):
        super(eovpn, self).__init__()
        self.app = app

    def start(self):
        css = Gtk.CssProvider()
        css.load_from_resource(self.EOVPN_CSS)
        context = Gtk.StyleContext()
        screen = Gdk.Screen.get_default()
        context.add_provider_for_screen(screen, css,
                                        Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        main_window = MainWindow(self.app)
        main_window.show()                            


def on_activate(app):
    main = eovpn(app)
    main.start()

def launch_eovpn():
    app = Gtk.Application(application_id='com.github.jkotra.eovpn',
                          flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE)

    app.add_main_option("debug", ord("d"), GLib.OptionFlags.NONE,
                        GLib.OptionArg.STRING, "Show Debug Messages.", "[CRITICAL|ERROR|WARNING|INFO|DEBUG]")                    

    app.connect('activate', on_activate)
    app.connect('command-line', do_command_line)
    exit_code = app.run(sys.argv)
    return exit_code

def do_command_line(app, args):

    args = args.get_options_dict()

    if args.contains("debug"):
        debug_lvl = args.lookup_value("debug", None)
        debug_lvl = debug_lvl.get_string()

        if debug_lvl is not None:
            logging.basicConfig(level=debug_lvl, format='%(levelname)s:%(name)s.py:%(funcName)s:%(message)s')

    app.activate()
    return True