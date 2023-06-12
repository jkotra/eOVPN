import logging
from pathlib import Path
import os

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



class ConnectionManager(Base):

    def __init__(self, name):
        super().__init__()
        self.__NAME__ = name

    def get_name(self):
        return self.__NAME__

    def version(self) -> str:
        pass

    def connect(self, openvpn_config):
        pass

    def start_dbus_watch(self, callback):
        pass

    def disconnect(self):
        pass

    def status(self) -> bool:
        pass


class NetworkManager(ConnectionManager):

    def __init__(self, callback, subscribe=True):
        super().__init__("NetworkManager")
        self.uuid = None
        self.nm_manager = _libeovpn_nm.lib
        self.ffi = _libeovpn_nm.ffi
        self.debug = int(True)
        self.callback = callback
        
        self.dbus = NMDbus()
        self.watch = False

        if subscribe: #DO NOT SUBSCRIBE / WATCH
            self.start_watch()
    
    
    def to_string(self, data, decode: bool = False):
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
                                            self.ffi.NULL,
                                            1)
        connection_result = self.nm_manager.activate_connection(self.to_string(uuid))

        self.uuid = self.to_string(uuid)
        self.set_setting(self.SETTING.NM_ACTIVE_UUID,
                             self.uuid.decode("utf-8"))

    def disconnect(self):
        if self.uuid is None:
            while(self.nm_manager.get_active_vpn_connection_uuid() is not None):
                self.nm_manager.disconnect(
                    self.to_string(self.nm_manager.get_active_vpn_connection_uuid()), self.debug)
            return

        is_uuid_found = self.nm_manager.is_vpn_activated(self.uuid)

        if (is_uuid_found):
            logger.info("current vpn UUID ({}).".format(self.uuid))
            self.nm_manager.disconnect(self.uuid, self.debug)
            self.nm_manager.delete_connection(self.uuid, self.debug)
            self.uuid = None
            self.set_setting(self.SETTING.NM_ACTIVE_UUID, None)
        self.dbus.remove_watch()

    def status(self) -> bool:
        return self.nm_manager.is_vpn_running()
    
    def delete_all_connections(self):
        self.nm_manager.delete_all_vpn_connections()

    def version(self) -> str:
        version = self.nm_manager.get_version()
        return self.to_string(version, True)
    
    def is_openvpn_plugin_available(self) -> bool:
        return bool(self.nm_manager.is_openvpn_plugin_available())


class OpenVPN3(ConnectionManager):

    def __init__(self, update_callback, subscribe=True):
        super().__init__("OpenVPN3")

        self.ovpn3 = _libopenvpn3.lib
        self.ffi = _libeovpn_nm.ffi

        self.callback = update_callback
        self.check_status_timeout = 30
        self.config_path = None
        self.session_path = None
        self.watch = False

        self.dbus = OVPN3Dbus()
        if subscribe:
            self.start_watch()

        
    def start_watch(self):
        if not self.watch:
            self.dbus.set_binding(self)
            self.dbus.watch(self.callback)
            self.watch = True

    def get_session_path(self):
        return self.session_path
    
    def check_status(self):
        status = self.status()
        self.check_status_timeout -= 1
        if status or (self.check_status == 0):
            return False
        return True
    
    def to_string(self, data, decode: bool = False):
        _str = self.ffi.string(data)
        if (decode):
            return _str.decode("utf-8")
        return _str

    def connect(self, openvpn_config):
        config_content = open(openvpn_config, "r").read()
        ca = self.get_setting(self.SETTING.CA)
        if ca is not None:
            ca_content = open(ca, "r").read()
            config_content += "\n<ca>\n{}\n</ca>\n".format(ca_content)
        config_content = config_content.encode('utf-8')

        config_path = self.ovpn3.import_config(os.path.basename(openvpn_config).encode('utf-8'), config_content)
        logger.info("config path: %s", self.to_string(config_path))
        self.config_path = self.to_string(config_path)
        self.status()

        session_path = self.ovpn3.prepare_tunnel(self.config_path)
        logger.info("session path: %s", self.to_string(session_path))
        self.session_path = self.to_string(session_path)
        GLib.timeout_add_seconds(1, self.check_status)

    def disconnect(self):
        if self.session_path is not None:
            logger.info("Disconnecting from " + self.session_path.decode('utf-8'))
            self.ovpn3.disconnect_vpn()
        else:
            self.ovpn3.disconnect_all_sessions()
        self.session_path = None       
        self.callback(False)

    def pause(self):
        self.ovpn3.pause_vpn("User Action in eOVPN".encode("utf-8"))
        self.status()

    def resume(self):
        self.ovpn3.resume_vpn()
        GLib.timeout_add_seconds(1, self.check_status)    

    def version(self) -> str:
        return self.to_string(self.ovpn3.p_get_version(), True)

    def status(self) -> bool:
        return self.ovpn3.p_get_connection_status()
