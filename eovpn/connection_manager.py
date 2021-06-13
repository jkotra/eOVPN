import re
import logging
import gettext

from gi.repository import GLib, Secret

from .eovpn_base import Base, ThreadManager
from .openvpn import OpenVPN
from .networkmanager.bindings import NetworkManager


logger = logging.getLogger(__name__)

class eOVPNConnectionManager(Base):
    # this class deals with connecting and disconneting vpn

    def __init__(self, statusbar=None, statusbar_icon=None, spinner=None):

        super().__init__()
        
        self.openvpn_manager = None
        self.nm_manager = None

        self.spinner = spinner
        self.statusbar = statusbar
        self.statusbar_icon = statusbar_icon
        self.uuid = None

        self.is_openvpn = False
        self.is_nm = False

        self.current_manager = self.get_setting(self.SETTING.MANAGER)

        if self.current_manager == "openvpn":
            self.openvpn_manager = OpenVPN(60)
            self.is_openvpn = True
        elif self.current_manager == "networkmanager":
            self.nm_manager = NetworkManager()
            self.is_nm = True
        else:
            self._push_to_statusbar("Manager not selected.")
            self._set_statusbar_icon(False, False)
    
    def req_auth(self, config_file):
        f = open(config_file, "r")
        if "auth-user-pass\n" in f.read():
            return True
        else:
            return False    

    def _set_statusbar_icon(self, result: bool, connected: bool = False):
        if self.statusbar_icon is not None:
            if result and connected:
                self.statusbar_icon.set_from_icon_name("network-vpn-symbolic", 1)
            elif result is None:
                self.statusbar_icon.set_from_icon_name("emblem-important-symbolic", 1)
            elif result:
                self.statusbar_icon.set_from_icon_name("emblem-ok-symbolic", 1)
            else:
                self.statusbar_icon.set_from_icon_name("dialog-error-symbolic", 1)
    
    def _push_to_statusbar(self, message):
        if self.statusbar is not None:
            if type(message) is str:
                self.statusbar.push(1, message)

    def connect(self, openvpn_config, auth_file=None, ca=None, logfile=None, callback=None) -> bool:

        self.spinner.start()
        self._push_to_statusbar(gettext.gettext("Connecting.."))

        #check if config requires auth
        if self.req_auth(openvpn_config) and auth_file is None:
            self.spinner.stop()
            self._push_to_statusbar(gettext.gettext("Config requires authorization (auth-user-pass)"))
            self._set_statusbar_icon(False, False)
            return False
        
        if self.is_openvpn:
            logger.debug("\nc={}\na={}\nca={}\nl={}".format(openvpn_config, auth_file, ca, logfile))
            def connect_to_openvpn_cli():
                connection_result = self.openvpn_manager.connect("--config", openvpn_config, "--auth-user-pass", auth_file, "--ca", ca,
                     "--log", logfile, "--daemon")
                if type(connection_result) is not bool:
                    self._push_to_statusbar(connection_result)
                    self._set_statusbar_icon(False, False)
                    self.spinner.stop()
                    return False

                if connection_result:
                    self._push_to_statusbar(gettext.gettext("Connected to {}.").format(openvpn_config.split('/')[-1]))
                    self._set_statusbar_icon(True, connected=True)
                else:
                    self._set_statusbar_icon(False)
                
                self.spinner.stop()
                callback(connection_result, openvpn_config)    


            ThreadManager().create(connect_to_openvpn_cli, (), is_daemon=True)        

         
        elif self.is_nm:     
            nm_username = self.get_setting(self.SETTING.AUTH_USER)
            nm_password = None
            if nm_username is not None:
                nm_password = Secret.password_lookup_sync(self.EOVPN_SECRET_SCHEMA, {"username": self.get_setting(self.SETTING.AUTH_USER)}, None)

            uuid = self.nm_manager.add_connection(openvpn_config.encode('utf-8'),
                                               (nm_username.encode('utf-8') if nm_username is not None else None),
                                               (nm_password.encode('utf-8') if nm_password is not None else self.get_setting(self.SETTING.AUTH_PASS).encode('utf-8')),
                                               (ca.encode('utf-8') if ca is not None else ca))
            connection_result = self.nm_manager.activate_connection(uuid)

            self.uuid = uuid
            self.set_setting(self.SETTING.NM_ACTIVE_UUID, self.uuid.decode('utf-8'))

            if not connection_result:
                self._set_statusbar_icon(False)
            
            callback(connection_result, openvpn_config)
                
        else:
            pass                      
    
    def NM_cleanup_connection(self):

        """ delete connection/vpn if it failed for whatever reason """
        self.nm_manager.delete_connection(self.uuid)


    def disconnect(self, callback=None):

        disconnect_result = None

        self.spinner.start()
        
        if self.is_openvpn:

            def disconnect_openvpn_cli():
                disconnect_result = self.openvpn_manager.disconnect()
                self.spinner.stop()
                if disconnect_result:
                    self._push_to_statusbar(gettext.gettext("Disconnected."))
                callback(disconnect_result)

            ThreadManager().create(disconnect_openvpn_cli, (), is_daemon=True)    

        elif self.is_nm:
            if (self.get_setting(self.SETTING.NM_ACTIVE_UUID) != None):
                self.uuid = self.get_setting(self.SETTING.NM_ACTIVE_UUID).encode('utf-8')

                is_uuid_found = self.nm_manager.is_vpn_activated(self.uuid)

                if (is_uuid_found == True) or (is_uuid_found != -1):
                    logger.info("current vpn UUID ({}) matches one in settings.json.".format(self.uuid))
                else:
                    self.uuid = None
            
            if self.uuid is None:
                logger.info("unknown UUID!")
                while(self.nm_manager.get_active_vpn_connection_uuid() is not None):
                    self.nm_manager.disconnect(self.nm_manager.get_active_vpn_connection_uuid())
                return True
                            
            disconnect_result = self.nm_manager.disconnect(self.uuid)
            self.nm_manager.delete_connection(self.uuid)
            self.uuid = None
            self.set_setting(self.SETTING.NM_ACTIVE_UUID, None)

            self.spinner.stop()
            if disconnect_result:
                self._push_to_statusbar(gettext.gettext("Disconnected."))
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
            callback(version)
            self._push_to_statusbar(version)
        
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