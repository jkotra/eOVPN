import logging

from gi.repository import GLib, Secret

from .eovpn_base import Base
from .networkmanager.bindings import NetworkManager as NMBindings
from .networkmanager.dbus import NMDbus
from .openvpn3.bindings import OpenVPN3 as OVPN3Bindings
from .openvpn3.dbus import OVPN3Dbus


logger = logging.getLogger(__name__)


class ConnectionManager(Base):

    def __init__(self, name):
        super().__init__()
        self.__NAME__ = name

    def get_name(self):
        return self.__NAME__

    def version(self) -> str:
        pass

    def connect(self, openvpn_config, dbus_callback=None):
        pass

    def disconnect(self):
        pass

    def status(self) -> bool:
        pass


class NetworkManager(ConnectionManager):

    def __init__(self):
        super().__init__("NetworkManager")
        self.uuid = None
        self.nm_manager = NMBindings()
        
        self.dbus = NMDbus()
        self.watch =False

    def connect(self, openvpn_config, dbus_callback=None):

        if not self.watch:
            # only subscribe once
            self.dbus.watch(dbus_callback)
            self.watch = True

        nm_username = self.get_setting(self.SETTING.AUTH_USER)
        nm_password = None
        nm_ca = self.get_setting(self.SETTING.CA)

        if nm_username is not None:
            try:
                nm_password = Secret.password_lookup_sync(self.EOVPN_SECRET_SCHEMA, {
                                                          "username": self.get_setting(self.SETTING.AUTH_USER)}, None)
            except Exception:
                nm_password = self.get_setting(self.SETTING.AUTH_PASS)

        uuid = self.nm_manager.add_connection(openvpn_config.encode('utf-8'),
                                            (nm_username.encode(
                                                'utf-8') if nm_username is not None else None),
                                            (nm_password.encode(
                                                'utf-8') if nm_password is not None else None),
                                            (nm_ca.encode('utf-8') if nm_ca is not None else None))
        connection_result = self.nm_manager.activate_connection(uuid)

        self.uuid = uuid
        self.set_setting(self.SETTING.NM_ACTIVE_UUID,
                             self.uuid.decode('utf-8'))

    def disconnect(self):
        if self.uuid is None:
            while(self.nm_manager.get_active_vpn_connection_uuid() is not None):
                self.nm_manager.disconnect(
                    self.nm_manager.get_active_vpn_connection_uuid())
            return

        is_uuid_found = self.nm_manager.is_vpn_activated(self.uuid)

        if (is_uuid_found == True):
            logger.info("current vpn UUID ({}).".format(self.uuid))
            self.nm_manager.disconnect(self.uuid)
            self.nm_manager.delete_connection(self.uuid)
            self.uuid = None
            self.set_setting(self.SETTING.NM_ACTIVE_UUID, None)

    def status(self) -> bool:
        return self.nm_manager.get_connection_status()

    def version(self) -> str:
        version = self.nm_manager.get_version()
        return version


class OpenVPN3(ConnectionManager):

    def __init__(self, dco, update_callback):
        super().__init__("OpenVPN3")
        self.ovpn3 = OVPN3Bindings()
        self.callback = update_callback
        self.session_path = None
        self.dbus = OVPN3Dbus()
        self.dbus.set_binding(self.ovpn3)
        self.watch = False
        

    def connect(self, openvpn_config, dbus_callback=None):
        if not self.watch:
            self.dbus.watch(dbus_callback)
            self.watch = True
            print("subscribed!")

        if (self.ovpn3.import_config(openvpn_config, self.get_setting(self.SETTING.CA)) != False):
            self.session_path = self.ovpn3.prepare_tunnel(dbus_callback)

    def disconnect(self):
        if self.session_path is not None:
            logger.info("Disconnecting from " + self.session_path.decode('utf-8'))
            self.ovpn3.disconnect()
        else:
            self.ovpn3.disconnect_all_sessions()
        self.session_path = None       
        GLib.timeout_add_seconds(1, self.callback, False)

    def pause(self):
        self.ovpn3.pause("User Action in eOVPN".encode("utf-8"))

    def resume(self):
        self.ovpn3.resume()    

    def version(self) -> str:
        return self.ovpn3.get_version()

    def status(self) -> bool:
        return self.ovpn3.get_connection_status()
