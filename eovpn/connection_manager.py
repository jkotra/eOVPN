import logging
from pathlib import Path
import os
from abc import ABC, abstractmethod

import gi
gi.require_version('Secret', '1')
from gi.repository import Secret, GLib

from .eovpn_base import Base
from .utils import inline_ovpn_config_content
from .backend.networkmanager import _libeovpn_nm
from .backend.networkmanager.dbus import NMDbus

logger = logging.getLogger(__name__)

try:
    from .backend.openvpn3 import _libopenvpn3
    from .backend.openvpn3.dbus import OVPN3Dbus
except Exception as e:
    logger.warning("openvpn error: %s", e)



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

        config_path_obj = Path(openvpn_config)
        search_dirs = [
            str(config_path_obj.parent),
            self.EOVPN_OVPN_CONFIG_DIR,
        ]
        if nm_ca:
            search_dirs.append(str(Path(nm_ca).parent))

        raw_config = config_path_obj.read_text(encoding="utf-8", errors="replace")
        inlined_config = inline_ovpn_config_content(
            raw_config,
            search_dirs=search_dirs,
            ca_override=nm_ca,
        )

        tmp_config = Path(GLib.get_tmp_dir()) / os.path.basename(openvpn_config)
        tmp_config.write_text(inlined_config, encoding="utf-8")

        if nm_username is not None:
            try:
                nm_password = Secret.password_lookup_sync(
                    self.EOVPN_SECRET_SCHEMA,
                    {"username": nm_username},
                    None,
                )
            except Exception:
                nm_password = self.get_setting(self.SETTING.AUTH_PASS)
            if not nm_password:
                nm_password = self.get_setting(self.SETTING.AUTH_PASS)

        c_username = (
            nm_username.encode("utf-8") if nm_username else self.ffi.NULL
        )
        c_password = (
            nm_password.encode("utf-8") if nm_password else self.ffi.NULL
        )

        uuid = self.nm_manager.add_connection(
            str(tmp_config).encode("utf-8"),
            c_username,
            c_password,
            self.ffi.NULL,
        )

        c_uuid = self.to_cffi_string(uuid)
        if not c_uuid:
            logger.error("Failed to add connection in NetworkManager")
            return

        connection_result = self.nm_manager.activate_connection(c_uuid)

        self.uuid = c_uuid
        self.set_setting(
            self.SETTING.NM_ACTIVE_UUID, self.uuid.decode("utf-8")
        )

    def disconnect(self):
        if self.uuid is None:
            saved_uuid = self.get_setting(self.SETTING.NM_ACTIVE_UUID)
            if saved_uuid:
                self.uuid = saved_uuid.encode("utf-8")

        if self.uuid is None:
            while True:
                active_cdata = self.nm_manager.get_active_vpn_connection_uuid()
                if active_cdata == self.ffi.NULL:
                    break
                active_uuid = self.to_cffi_string(active_cdata)
                if not active_uuid:
                    break
                self.nm_manager.disconnect(active_uuid)
            return

        uuid_bytes = (
            self.uuid.encode("utf-8") if isinstance(self.uuid, str) else self.uuid
        )
        is_uuid_found = self.nm_manager.is_vpn_activated(uuid_bytes)

        if is_uuid_found != -1 and is_uuid_found:
            logger.info("current vpn UUID ({}).".format(self.uuid))
            self.nm_manager.disconnect(uuid_bytes)
            self.nm_manager.delete_connection(uuid_bytes)
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
        self.dbus.set_binding(self)

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
        logger.debug("OpenVPN3 readiness check: %s", status)
        return False

    def connect(self, openvpn_config):
        self.start_watch()
        config_path_obj = Path(openvpn_config)
        search_dirs = [
            str(config_path_obj.parent),
            self.EOVPN_OVPN_CONFIG_DIR,
        ]
        ca = self.get_setting(self.SETTING.CA)
        if ca:
            search_dirs.append(str(Path(ca).parent))

        raw_config = config_path_obj.read_text(encoding="utf-8", errors="replace")
        inlined_config = inline_ovpn_config_content(
            raw_config,
            search_dirs=search_dirs,
            ca_override=ca,
        )
        config_content = inlined_config.encode("utf-8")

        config_path = self.ovpn3.import_config(
            os.path.basename(openvpn_config).encode("utf-8"), config_content
        )
        logger.info("config path: %s", self.to_cffi_string(config_path))
        self.config_path = self.to_cffi_string(config_path)
        if not self.config_path:
            logger.error("Failed to import config into OpenVPN3")
            return

        session_path = self.ovpn3.prepare_tunnel(self.config_path)
        logger.info("session path: %s", self.to_cffi_string(session_path))
        self.session_path = self.to_cffi_string(session_path)
        if not self.session_path:
            logger.error("Failed to prepare tunnel in OpenVPN3")
            return

        if not self.dbus.handle_attention():
            if self.is_ready():
                self.dbus.try_to_connect()
        self.status()

    def disconnect(self):
        if getattr(self, "_disconnecting", False):
            return
        self._disconnecting = True
        try:
            if self.session_path is not None:
                session_str = (
                    self.session_path.decode("utf-8")
                    if isinstance(self.session_path, bytes)
                    else str(self.session_path)
                )
                logger.info("Disconnecting from %s", session_str)
                self.ovpn3.disconnect_vpn()
            else:
                self.ovpn3.disconnect_all_sessions()
            self.dbus.unsubscribe_events()
            self.session_path = None
            self.config_path = None
            if self.callback:
                self.callback(False)
        finally:
            self._disconnecting = False

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
