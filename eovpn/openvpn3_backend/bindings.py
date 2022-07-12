import ctypes
from ctypes import CDLL
import os
import logging

logger = logging.getLogger(__name__)


class OpenVPN3:
    
    def __init__(self) -> None:

        self.__NAME__ = "OpenVPN3"
        self.lib_load_fail = None
        path = os.path.join(os.path.dirname(os.path.realpath(__file__)), "libopenvpn3.so")

        try:
            self.eovpn_ovpn3 = CDLL(path)
        except Exception as e:
            logger.error("%s", e)
            self.lib_load_fail = True

        self.session_path = None
        self.config_path = None

    def import_config(self, config: str, ca: str = None) -> str:

        # arguments must be encode before being passed to this function!
        # ex: a.encode('utf-8')

        self.eovpn_ovpn3.import_config.argtypes = [
            ctypes.c_char_p, ctypes.c_char_p]
        self.eovpn_ovpn3.import_config.restype = ctypes.c_char_p

        config_content = open(config, "r").read()
        if ca is not None:
            ca_content = open(ca, "r").read()
            config_content += "\n<ca>\n{}\n</ca>\n".format(ca_content)
        config_content = config_content.encode('utf-8')

        self.config_path = self.eovpn_ovpn3.import_config(
            os.path.basename(config).encode('utf-8'), config_content)
        if self.config_path is None:
            return False
        logger.info(self.config_path)

    def prepare_tunnel(self, dbus_callback) -> bool:
        self.eovpn_ovpn3.prepare_tunnel.argtypes = [ctypes.c_char_p]
        self.eovpn_ovpn3.prepare_tunnel.restype = ctypes.c_char_p

        self.session_path = self.eovpn_ovpn3.prepare_tunnel(self.config_path)
        if self.session_path is None:
            return False
        logger.info(self.session_path)
        self.get_connection_status()
        return self.session_path

    def send_auth(self, input_for: tuple, value: str):
        #type, group, input
        t, g, i = input_for
        self.eovpn_ovpn3.send_auth.argtypes = [ctypes.c_char_p, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_char_p]
        self.eovpn_ovpn3.send_auth(self.session_path, t, g, i, value.encode('utf-8'))

    def is_ready_to_connect(self):
        self.eovpn_ovpn3.is_ready_to_connect.restype = ctypes.c_char_p
        reason = self.eovpn_ovpn3.is_ready_to_connect()
        if reason is not None:
            return reason
        else:
            return True

    def connect(self):
        self.eovpn_ovpn3.p_get_version.argtypes = [
            ctypes.c_char_p, ctypes.c_int]
        self.eovpn_ovpn3.set_dco(self.session_path, 1)
        self.eovpn_ovpn3.set_log_forward()
        logger.info("log forward enabled!")
        self.get_connection_status()

        if (reason := self.is_ready_to_connect()) == True:
            self.eovpn_ovpn3.connect_vpn()
            self.get_connection_status()
        else:
            logger.error(reason)    

    def get_connection_status(self):
        self.eovpn_ovpn3.p_get_connection_status.restype = ctypes.c_int
        if (status := self.eovpn_ovpn3.p_get_connection_status()) != -1:
            return bool(status)
        return False

    def init_unique_session(self):
        self.eovpn_ovpn3.init_unique_session.argtypes = [ctypes.c_char_p]
        self.eovpn_ovpn3.init_unique_session(self.session_path)

    def disconnect(self):
        self.eovpn_ovpn3.disconnect_vpn()

    def disconnect_all_sessions(self):
        self.eovpn_ovpn3.disconnect_all_sessions()

    def pause(self, reason: str):
        self.eovpn_ovpn3.pause_vpn.argtypes = [ctypes.c_char_p]
        self.eovpn_ovpn3.pause_vpn(reason)

    def resume(self):
        self.eovpn_ovpn3.resume_vpn()

    def get_version(self):
        # DBus call to get version
        #self.eovpn_ovpn3.p_get_version.restype = ctypes.c_char_p
        #ver = self.eovpn_ovpn3.p_get_version()
        #return ver

        if self.lib_load_fail:
            return None
            
        try:
            from openvpn3 import constants as OVPN3Constants
            return OVPN3Constants.VERSION
        except ImportError:
            return None
