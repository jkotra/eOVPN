import re
import logging
import gettext

from gi.repository import GLib, Secret

from .eovpn_base import Base, ThreadManager
from .networkmanager.bindings import NetworkManager


logger = logging.getLogger(__name__)

class eOVPNConnectionManager(Base):
    # this class deals with connecting and disconneting vpn

    def __init__(self):
        super().__init__()   
        self.uuid = None
        self.nm_manager = NetworkManager()
    
    def req_auth(self, config_file):
        f = open(config_file, "r")
        if "auth-user-pass\n" in f.read():
            return True
        else:
            return False    


    def connect(self, openvpn_config, callback=None) -> bool:

        if self.get_connection_status():
            self.disconnect()
            return
         
        nm_username = self.get_setting(self.SETTING.AUTH_USER)
        nm_password = None
        nm_ca = self.get_setting(self.SETTING.CA)

        if nm_username is not None:
            try:
                nm_password = Secret.password_lookup_sync(self.EOVPN_SECRET_SCHEMA, {"username": self.get_setting(self.SETTING.AUTH_USER)}, None)
            except Exception:
                nm_password = self.get_setting(self.SETTING.AUTH_PASS)
                
            uuid = self.nm_manager.add_connection(openvpn_config.encode('utf-8'),
                                               (nm_username.encode('utf-8')),
                                               (nm_password.encode('utf-8')),
                                               (nm_ca.encode('utf-8')))
            connection_result = self.nm_manager.activate_connection(uuid)

            self.uuid = uuid
            self.set_setting(self.SETTING.NM_ACTIVE_UUID, self.uuid.decode('utf-8'))

        else:
            pass                      
    
    def NM_cleanup_connection(self):

        """ delete connection/vpn if it failed for whatever reason """
        self.nm_manager.delete_connection(self.uuid)


    def disconnect(self):
        
        if self.uuid is None:
            while(self.nm_manager.get_active_vpn_connection_uuid() is not None):
                self.nm_manager.disconnect(self.nm_manager.get_active_vpn_connection_uuid())
            return 

        is_uuid_found = self.nm_manager.is_vpn_activated(self.uuid)

        if (is_uuid_found == True):
            logger.info("current vpn UUID ({}).".format(self.uuid))
            self.nm_manager.disconnect(self.uuid)
            self.nm_manager.delete_connection(self.uuid)
            self.uuid = None
            self.set_setting(self.SETTING.NM_ACTIVE_UUID, None)
        
    def get_connection_status(self) -> bool:
        return self.nm_manager.get_connection_status()

    
    def get_version(self, callback=None) -> str:
        version = self.nm_manager.get_version()
        if callable(callback):
            callback(version)
        return version