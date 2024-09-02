import sys
import argparse
import logging

import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, GLib, Gio, Gdk

logger = logging.getLogger(__name__)

from .eovpn_base import Base
from .main_window import MainWindow

class eovpn(Base):
    def __init__(self, app):
        super(eovpn, self).__init__()
        self.app = app

    def start(self):
        css_provider = Gtk.CssProvider()
        css_provider.load_from_resource(self.EOVPN_GRESOURCE_PREFIX + "/css/main.css")
        display = Gdk.Display.get_default()
        Gtk.StyleContext.add_provider_for_display(display, css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)


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
    
    #handle --config -c
    parser = argparse.ArgumentParser(prog="eovpn", add_help=False)
    args, _ = parser.parse_known_args(sys.argv[1:])


    # as glib dont support custom commands, remove these from sys.argv.
    # the above declared `add_main_option` is essentially a dummy placeholder.
    if "-c" in sys.argv: sys.argv.remove("-c")
    if "--config" in sys.argv: sys.argv.remove("--config")

    exit_code = app.run(sys.argv)
    return exit_code

def do_command_line(app, args):

    args = args.get_options_dict()

    if args.contains("debug"):
        debug_lvl = args.lookup_value("debug", None)
        debug_lvl = debug_lvl.get_string()
        if debug_lvl.isnumeric():
            debug_lvl = int(debug_lvl)
            assert(debug_lvl <= 50)
        else:
            assert(debug_lvl in ["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG", "NOTSET"])    

        if debug_lvl is not None:
            logging.basicConfig(level=debug_lvl, format='%(levelname)s:%(name)s.py:%(funcName)s:%(message)s')

    app.activate()
    return True