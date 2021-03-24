import ctypes
from ctypes import CDLL
import os
import time
import logging
import gi

gi.require_version("NM", "1.0")
from gi.repository import GLib, NM


logger = logging.getLogger(__name__)

class NetworkManager:

    def __init__(self, debug=False) -> None:
        
        self.__NAME__ = "NetworkManager"
        path = os.path.join(os.path.dirname(os.path.realpath(__file__)), "libeovpn_nm.so")
        #load .so file
        self.eovpn_nm = CDLL(path)
        self.debug = int(debug)
        self.uuid = None

        self.VPN_ACTIVATED = 5

    def add_connection(self, config: str, username:str = None, password: str = None, ca: str = None) -> str:

        # arguments must be encode before being passed to this function!
        # ex: a.encode('utf-8')
        self.eovpn_nm.add_connection.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_int]
        self.eovpn_nm.add_connection.restype = ctypes.c_char_p

        uuid = self.eovpn_nm.add_connection(config, username, password, ca, self.debug)
        
        if uuid is not None:
            self.uuid = uuid
            return uuid
        
    def activate_connection(self, uuid: str) -> bool:

        self.eovpn_nm.activate_connection.argtypes = [ctypes.c_char_p]
        self.eovpn_nm.activate_connection.restype = ctypes.c_int

        res = self.eovpn_nm.activate_connection(uuid)
        return bool(res)

    def disconnect(self, uuid: str) -> bool:

        self.eovpn_nm.disconnect.argtypes = [ctypes.c_char_p, ctypes.c_int]
        self.eovpn_nm.disconnect.restype = ctypes.c_int
        res = self.eovpn_nm.disconnect(uuid, self.debug)
        return bool(res)

    def delete_connection(self, uuid: str) -> bool:

        self.eovpn_nm.delete_connection.argtypes = [ctypes.c_char_p, ctypes.c_int]
        self.eovpn_nm.delete_connection.restype = ctypes.c_int

        res = self.eovpn_nm.delete_connection(uuid, self.debug)
        return bool(res)

    def delete_all_vpn_connections(self) -> bool:

        res = self.eovpn_nm.delete_all_vpn_connections(None)
        return bool(res)

    def get_version(self) -> str:
        self.eovpn_nm.get_version.restype = ctypes.c_char_p
        self.eovpn_nm.is_openvpn_plugin_available.restype = ctypes.c_int

        ver = self.eovpn_nm.get_version()
        is_openvpn_available = self.eovpn_nm.is_openvpn_plugin_available()
        
        if ver is not None:
            ver = ver.decode('utf-8')
            ver = self.__NAME__ + " " + ver

        if (ver != None) and is_openvpn_available:
            return ver

    def get_connection_status(self) -> bool:
        self.eovpn_nm.is_vpn_running.restype = ctypes.c_int
        res = bool(self.eovpn_nm.is_vpn_running())
        logger.debug("eovpn_nm.is_vpn_running() = {}".format(res))
        if res:
            return True #or res, both are same.
        return False

    def is_vpn_activated(self) -> bool:
        self.eovpn_nm.is_vpn_activated.restype = ctypes.c_int
        self.eovpn_nm.is_vpn_activated.argtypes = [ctypes.c_char_p]

        res = self.eovpn_nm.is_vpn_activated(self.uuid)
        logger.debug("eovpn_nm.is_vpn_activated = {}".format(res))

        if res == self.VPN_ACTIVATED:
            return True
        else:
            return res