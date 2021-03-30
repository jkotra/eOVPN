from gi.repository import Gtk
from .eovpn_base import Base

class LogWindow(Base, Gtk.Builder):
    def __init__(self):
        super().__init__()
        Gtk.Builder.__init__(self)

        self.add_from_resource(self.EOVPN_GRESOURCE_PREFIX + "/ui/" + "log.glade")
        self.connect_signals(LogWindowSignalHandler())

        self.window = self.get_object("log_window")

    def show(self):
        self.window.show()


class LogWindowSignalHandler(Base):
        def __init__(self):
            super(LogWindowSignalHandler, self).__init__()
        
        def on_log_window_show(self, log_area):
            textbuf = Gtk.TextBuffer()
            textbuf.set_text(open(self.EOVPN_CONFIG_DIR + "/session.log", "r+").read())
            log_area.set_buffer(textbuf)

        def on_log_window_delete_event(self, window, event):
            window.hide()
            return True

        def on_log_close_btn_clicked(self, window):
            window.hide()
            return True


