import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk
from eovpn.eovpn_base import Base, StorageItem


class OTPInputWindow(Base):
    def __init__(self, input_callback: callable, error_callback: callable) -> None:
        super().__init__()
        self.callback = input_callback
        self.error_callback = error_callback

        self.builder = Gtk.Builder()
        self.builder.add_from_resource(self.EOVPN_GRESOURCE_PREFIX + "/ui/" + "otp.ui")

        self.window = self.builder.get_object("OTpMainWindow")
        self.window.connect("close-request", self.manual_close)
        self.window.set_title("2FA OTP Input")
        self.window.set_default_size(600, 200)
        self.window.set_resizable(False)

        try:
            main_window = self.retrieve(StorageItem.MAIN_WINDOW)
            if main_window:
                self.window.set_transient_for(main_window)
        except KeyError:
            pass
        self.window.set_modal(True)

        self.submit_btn = self.builder.get_object("submit")
        self.submit_btn.set_sensitive(False)
        self.submit_btn.connect("clicked", lambda _: self.return_and_destroy())

        for i in range(1, 7):
            entry = self.builder.get_object(f"O{i}")
            entry.set_max_length(1)
            next_entry = self.builder.get_object(f"O{i+1}") if i < 6 else None
            entry.connect("changed", self.on_entry_changed, next_entry)
            entry.connect(
                "activate",
                lambda _: self.return_and_destroy()
                if len(self.gather_otp()) == 6
                else None,
            )

    def on_entry_changed(self, entry, next_entry):
        text: str = entry.get_text()
        if not text.isnumeric():
            entry.set_text("")
            return False
        if len(text) == 1 and next_entry is not None:
            next_entry.grab_focus()

        # check whether we can enable submit btn.
        if len(self.gather_otp()) == 6:
            self.submit_btn.set_sensitive(True)
        else:
            self.submit_btn.set_sensitive(False)

    def gather_otp(self):
        otp = []
        for i in range(1, 7):
            entry = self.builder.get_object(f"O{i}")
            if entry:
                text = entry.get_text()
                if len(text) == 1:
                    otp.append(text)
        return otp

    def return_and_destroy(self):
        otp = self.gather_otp()
        callback = self.callback
        self.callback = None
        self.error_callback = None
        if self.window:
            self.window.destroy()
            self.window = None
        if callback:
            callback(otp)

    def manual_close(self, window):
        err_cb = self.error_callback
        self.callback = None
        self.error_callback = None
        if err_cb:
            err_cb()
        return False

    def close(self):
        self.callback = None
        self.error_callback = None
        if self.window:
            self.window.destroy()
            self.window = None

    def show(self):
        if self.window:
            self.window.show()
