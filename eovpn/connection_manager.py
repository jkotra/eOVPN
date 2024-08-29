import logging
from pathlib import Path
import os
from abc import ABC, abstractmethod

from gi.repository import Secret, GLib

from .eovpn_base import Base
from .backend.networkmanager import _libeovpn_nm
from .backend.networkmanager.dbus import NMDbus

logger = logging.getLogger(__name__)

try:
    from .backend.openvpn3 import _libopenvpn3
except:
    logger.error("cannot import openvpn3")
from .backend.openvpn3.dbus import OVPN3Dbus



class ConnectionManager(ABC, Base):
    def __init__(self, name):
        super().__init__()
        self.__NAME__ = name

    @abstractmethod
    def get_name(self):
        return self.__NAME__
    
    @abstractmethod
    def start_watch(self):
        pass

    @abstractmethod
    def version(self) -> str:
        pass

    @abstractmethod
    def connect(self, openvpn_config):
        pass

    @abstractmethod
    def disconnect(self):
        pass
    
    @abstractmethod
    def status(self) -> bool:
        pass


class NetworkManager(ConnectionManager):

    def __init__(self, callback):
        super().__init__("NetworkManager")
        self.uuid = None
        self.nm_manager = _libeovpn_nm.lib
        self.ffi = _libeovpn_nm.ffi
        self.callback = callback
        
        self.dbus = NMDbus()
        self.watch = False

    def get_name(self):
        return "networkmanager"
    
    def to_cffi_string(self, data, decode: bool = False):
        if data == self.ffi.NULL:
            return None
        _str = self.ffi.string(data)
        if (decode):
            return _str.decode("utf-8")
        return _str

    def start_watch(self):
        if not self.watch:
            # only subscribe once
            self.dbus.watch(self.callback)
            self.watch = True

    def connect(self, openvpn_config):

        nm_username = self.get_setting(self.SETTING.AUTH_USER)
        nm_password = None
        nm_ca = self.get_setting(self.SETTING.CA)
    
        tmp_config = Path(GLib.get_tmp_dir()) / os.path.basename(openvpn_config)

        with open(tmp_config, "w+") as f:
            data = f"{open(openvpn_config).read()}\n"
            if nm_ca is not None:
                data += f"\n<ca>\n{open(nm_ca).read()}\n</ca>\n"
            f.write(data)

        if nm_username is not None:
            try:
                nm_password = Secret.password_lookup_sync(self.EOVPN_SECRET_SCHEMA, {
                                                          "username": self.get_setting(self.SETTING.AUTH_USER)}, None)
            except Exception:
                nm_password = self.get_setting(self.SETTING.AUTH_PASS)

        uuid = self.nm_manager.add_connection(str(tmp_config).encode("utf-8"),
                                            (nm_username.encode(
                                                'utf-8') if nm_username is not None else None),
                                            (nm_password.encode(
                                                'utf-8') if nm_password is not None else None),
                                            self.ffi.NULL,)
        connection_result = self.nm_manager.activate_connection(self.to_cffi_string(uuid))

        self.uuid = self.to_cffi_string(uuid)
        self.set_setting(self.SETTING.NM_ACTIVE_UUID,
                             self.uuid.decode("utf-8"))

    def disconnect(self):
        if self.uuid is None:
            while(self.nm_manager.get_active_vpn_connection_uuid() is not None):
                self.nm_manager.disconnect(
                    self.to_cffi_string(self.nm_manager.get_active_vpn_connection_uuid()))
            return

        is_uuid_found = self.nm_manager.is_vpn_activated(self.uuid)

        if (is_uuid_found):
            logger.info("current vpn UUID ({}).".format(self.uuid))
            self.nm_manager.disconnect(self.uuid)
            self.nm_manager.delete_connection(self.uuid)
            self.uuid = None
            self.set_setting(self.SETTING.NM_ACTIVE_UUID, None)

    def status(self) -> bool:
        return self.nm_manager.is_vpn_running()
    
    def delete_all_connections(self):
        self.nm_manager.delete_all_vpn_connections()

    def version(self) -> str:
        version = self.nm_manager.get_version()
        return self.to_cffi_string(version, True)
    
    def is_openvpn_plugin_available(self) -> bool:
        return bool(self.nm_manager.is_openvpn_plugin_available())


class OpenVPN3(ConnectionManager):

    def __init__(self, update_callback):
        super().__init__("OpenVPN3")

        self.ovpn3 = _libopenvpn3.lib
        self.ffi = _libopenvpn3.ffi

        self.callback = update_callback

        self.config_path = None
        self.session_path = None

        self.watch = False
        self.dbus = OVPN3Dbus()

    def get_name(self):
        return "openvpn3"

    def to_cffi_string(self, data, decode: bool = False):
        if data == self.ffi.NULL:
            return None
        _str = self.ffi.string(data)
        if (decode):
            return _str.decode("utf-8")
        return _str
        
    def start_watch(self):
        if not self.watch:
            self.dbus.set_binding(self)

            # subscribe for all events. NOTE: not required as we subscribe to signal for session before connection.
            # self.dbus.subscribe_for_events(self.callback)
            
            self.dbus.subscribe_for_attention()

            self.watch = True

    def get_session_path(self):
        return self.session_path
    
    def is_ready(self):
        status = self.to_cffi_string(self.ovpn3.is_ready_to_connect())
        if status is None:
            return True
        return False

    def connect(self, openvpn_config):
        config_content = open(openvpn_config, "r").read()
        ca = self.get_setting(self.SETTING.CA)
        if ca is not None:
            ca_content = open(ca, "r").read()
            config_content += "\n<ca>\n{}\n</ca>\n".format(ca_content)
        config_content = config_content.encode('utf-8')

        config_path = self.ovpn3.import_config(os.path.basename(openvpn_config).encode('utf-8'), config_content)
        logger.info("config path: %s", self.to_cffi_string(config_path))
        self.config_path = self.to_cffi_string(config_path)

        session_path = self.ovpn3.prepare_tunnel(self.config_path)
        logger.info("session path: %s", self.to_cffi_string(session_path))
        self.session_path = self.to_cffi_string(session_path)
        self.status()

    def disconnect(self):
        if self.session_path is not None:
            logger.info("Disconnecting from %s", self.session_path.decode('utf-8'))
            self.ovpn3.disconnect_vpn()
        else:
            self.ovpn3.disconnect_all_sessions()
            self.callback(False)
        self.session_path = None

    def pause(self):
        self.ovpn3.pause_vpn("User Action in eOVPN".encode("utf-8"))

    def resume(self):
        self.ovpn3.resume_vpn()

    def version(self) -> str:
        v = self.ovpn3.p_get_version()
        if v:
            return self.to_cffi_string(self.ovpn3.p_get_version(), True)
        return None

    def status(self) -> bool:
        return self.ovpn3.p_get_connection_status()
