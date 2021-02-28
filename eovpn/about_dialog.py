from .eovpn_base import Base
from gi.repository import Gtk

class AboutWindow(Base, Gtk.Builder):
    def __init__(self):
        super().__init__()
        Gtk.Builder.__init__(self)

        self.add_from_resource(self.EOVPN_GRESOURCE_PREFIX + "/ui/" + "about.glade")
        self.connect_signals(AboutWindowSignalHandler())
        self.window = self.get_object("about_dlg")
        self.window.set_version(self.APP_VERSION)
        
        translation_credits = ""
        for person in self.TRANSLATORS.keys():
            translator_name = person
            translator_lang = ", ".join(self.TRANSLATORS[person])
            translation_credits += translator_name + ' (' + translator_lang + ')' + '\n'

        self.window.set_translator_credits(translation_credits) 
        self.window.set_logo(self.get_logo())


    def show(self):
        self.window.show()

class AboutWindowSignalHandler:

    def on_about_dlg_delete_event(self, window, event):
        window.hide()
        return True
