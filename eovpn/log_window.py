from .eovpn_base import Base
from gi.repository import Gtk

class LogWindow(Base):
    def __init__(self):
        super(LogWindow, self).__init__()

        self.builder = self.get_builder("log.glade")
        self.builder.connect_signals(LogWindowSignalHandler())
        self.window = self.builder.get_object("log_window")
        self.log_area = self.builder.get_object("log_area")

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


