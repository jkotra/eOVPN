import re
import logging
import gettext

from gi.repository import GLib

from .eovpn_base import ThreadManager, SettingsManager
from .openvpn import OpenVPN
from .networkmanager.bindings import NetworkManager


logger = logging.getLogger(__name__)

class eOVPNConnectionManager(SettingsManager):

    # this class deals with connecting and disconneting vpn

    def __init__(self, statusbar=None, statusbar_icon=None, spinner=None):

        super().__init__()
        
        self.openvpn_manager = OpenVPN(60)
        self.nm_manager = NetworkManager()

        self.spinner = spinner
        self.statusbar = statusbar
        self.statusbar_icon = statusbar_icon
        self.uuid = None

        self.is_openvpn = False
        self.is_nm = False

        self.current_manager = self.get_setting("manager")

        if self.current_manager == "openvpn":
            self.is_openvpn = True
        elif self.current_manager == "networkmanager":
            self.is_nm = True
        else:
            self.__push_to_statusbar("Manager not selected.")
            self.__set_statusbar_icon(False, False)

    def __set_statusbar_icon(self, result: bool, connected: bool = False):
        if self.statusbar_icon is not None:
            if result and connected:
                self.statusbar_icon.set_from_icon_name("network-vpn-symbolic", 1)
            elif result is None:
                self.statusbar_icon.set_from_icon_name("emblem-important-symbolic", 1)
            elif result:
                self.statusbar_icon.set_from_icon_name("emblem-ok-symbolic", 1)
            else:
                self.statusbar_icon.set_from_icon_name("dialog-error-symbolic", 1)
    
    def __push_to_statusbar(self, message):
        if self.statusbar is not None:
            self.statusbar.push(1, message)

    def connect(self, openvpn_config, auth_file=None, ca=None, logfile=None, callback=None) -> bool:

        self.spinner.start()
        self.__push_to_statusbar(gettext.gettext("Connecting.."))

        #check if config requires auth
        f = open(openvpn_config, "r")
        if "auth-user-pass" in f.read() and auth_file is None:
            self.spinner.stop()
            self.__push_to_statusbar(gettext.gettext("Config requires authorization (auth-user-pass)"))
            self.__set_statusbar_icon(False, False)
            return False
        
        if self.is_openvpn:
            def connect_to_openvpn_cli():
                connection_result = self.openvpn_manager.connect("--config", openvpn_config, "--auth-user-pass", auth_file, "--ca", ca,
                     "--log", logfile, "--daemon")
                if type(connection_result) is not bool:
                    self.__push_to_statusbar(connection_result)
                    self.__set_statusbar_icon(False, False)
                    self.spinner.stop()
                    return False

                if connection_result:
                    self.__push_to_statusbar(gettext.gettext("Connected to {}.").format(openvpn_config.split('/')[-1]))
                    self.__set_statusbar_icon(True, connected=True)
                else:
                    self.__set_statusbar_icon(False)
 
                callback(connection_result, openvpn_config)    


            ThreadManager().create(connect_to_openvpn_cli, (), is_daemon=True)        

         
        elif self.is_nm:     
            uuid = self.nm_manager.add_connection(openvpn_config.encode('utf-8'),
                                               self.get_setting('auth_user').encode('utf-8'),
                                               self.get_setting('auth_pass').encode('utf-8'),
                                               (ca.encode('utf-8') if ca != None else ca))
            connection_result = self.nm_manager.activate_connection(uuid)

            self.uuid = uuid
            self.set_setting("nm_active_uuid", self.uuid.decode('utf-8'))

            if not connection_result:
                self.__set_statusbar_icon(False)
            
            callback(connection_result, openvpn_config)
                
        else:
            pass                      

    def disconnect(self, callback=None):

        disconnect_result = None

        self.spinner.start()
        
        if self.is_openvpn:

            def disconnect_openvpn_cli():
                disconnect_result = self.openvpn_manager.disconnect()
                self.spinner.stop()
                if disconnect_result:
                    self.__push_to_statusbar(gettext.gettext("Disconnected."))
                callback(disconnect_result)

            ThreadManager().create(disconnect_openvpn_cli, (), is_daemon=True)    

        elif self.is_nm:
            if (self.get_setting("nm_active_uuid") != None):
                self.uuid = self.get_setting("nm_active_uuid").encode('utf-8')    
            disconnect_result = self.nm_manager.disconnect(self.uuid)
            self.nm_manager.delete_connection(self.uuid)
            self.uuid = None

            self.spinner.stop()
            if disconnect_result:
                self.__push_to_statusbar(gettext.gettext("Disconnected."))
            callback(disconnect_result)

        else:
            pass

        
    def get_connection_status(self) -> bool:
        if self.is_openvpn:
            return self.openvpn_manager.get_connection_status()
        elif self.is_nm:
            return self.nm_manager.get_connection_status()
        else:
            pass    
    
    def get_version(self, callback=None) -> str:

        if self.is_openvpn:
            version = self.openvpn_manager.get_version()
        elif self.is_nm:
            version = self.nm_manager.get_version()
        else:
            pass

        if callable(callback):
            callback((version != None) or (version != False))
            self.__push_to_statusbar(version)
        
        if self.is_openvpn:
            img = self.get_image("openvpn_black.svg","icons", (16,16))
        elif self.is_nm:
            img = self.get_image("nm_black.svg","icons", (16,16))
        else:
            pass

        self.statusbar_icon.set_from_pixbuf(img)

        self.spinner.stop()
        return version

    def openvpn_config_set_protocol(self,config, label):

        # this is kinda general purpose.

        proto = re.compile("proto [tcp|udp]*")
        f = open(config).read()
        matches = proto.search(f)
        
        try:
            protocol = matches.group().split(" ")[-1]
            label.set_text(protocol.upper())
            label.show()
        except Exception as e:
            logger.error(str(e))

        return False