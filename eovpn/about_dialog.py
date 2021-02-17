from .eovpn_base import Base

class AboutWindow(Base):
    def __init__(self):
        super(AboutWindow, self).__init__()
        self.builder = self.get_builder("about.glade")
        self.builder.connect_signals(AboutWindowSignalHandler())
        self.window = self.builder.get_object("about_dlg")
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
