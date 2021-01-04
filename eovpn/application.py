import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, GLib, Gio

import os, sys

from eovpn_base import Base
from main_window import MainWindow

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
        main_window = MainWindow(app)
        main_window.show()                                


def on_activate(app):
    main = eovpn(app)
    main.start()


app = Gtk.Application(application_id='com.github.jkotra.eovpn')
app.connect('activate', on_activate)