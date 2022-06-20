from gi.repository import Gio, GLib, Secret
import logging
from eovpn.eovpn_base import Base

import sys
import pathlib

openvpn3_python_dir = pathlib.Path("/var/run/host/usr/lib/").glob("python*")
openvpn3_python_dir = next(openvpn3_python_dir) / "site-packages"
sys.path.append(f'{openvpn3_python_dir}/')
from openvpn3 import constants as OVPN3Constants

logger = logging.getLogger(__name__)

class OVPN3Dbus(Base):

    def __init__(self):
        super().__init__()
        self.conn = None
        self.module = None
        self.once = True

    def get_auth_password(self):

        try:
            return Secret.password_lookup_sync(self.EOVPN_SECRET_SCHEMA, {
                                    "username": self.get_setting(self.SETTING.AUTH_USER)
                                    },
                                    None)
        except Exception as e:
            logger.error(e)
            self.password = self.get_setting(self.SETTING.AUTH_PASS)

    def set_binding(self, binding):
        self.module = binding


    def watch(self, callback):
        self.conn = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)

        #(sender, interface_name, member, object_path, arg0, flags, callback, *user_data)
        self.conn.signal_subscribe("net.openvpn.v3.sessions",
                           None,
                           "StatusChange",
                           None,
                           None,
                           Gio.DBusSignalFlags.NONE,
                           self.sub_callback,
                           callback)
    
    def sub_callback(self, connection, sender_name, object_path, interface_name, signal_name, parameters, update_callback):
        
        # https://github.com/OpenVPN/openvpn3-linux/blob/master/src/dbus/constants.hpp
        status = GLib.Variant("(uus)", parameters)
        major = status.get_child_value(0).get_uint32()
        minor = status.get_child_value(1).get_uint32()
        reason = status.get_child_value(2).get_string()

        logger.debug("{} {} {}".format(major, minor, reason))

        if(major == OVPN3Constants.StatusMajor.CONNECTION.value and minor == OVPN3Constants.StatusMinor.CFG_REQUIRE_USER.value):
            if self.get_setting(self.SETTING.AUTH_USER) is None:
                update_callback(False, reason)
                return
            self.module.send_auth(self.get_setting(self.SETTING.AUTH_USER), self.get_auth_password())
            logger.info("Auth Sent!")
            self.module.connect()
        elif (major == OVPN3Constants.StatusMajor.CONNECTION.value and minor == OVPN3Constants.StatusMinor.CONN_AUTH_FAILED.value):
            logger.error(reason)
            update_callback(False, reason)
        elif (major == OVPN3Constants.StatusMajor.CONNECTION.value and minor == OVPN3Constants.StatusMinor.CONN_CONNECTING.value):
            update_callback([])
        elif (major == OVPN3Constants.StatusMajor.CONNECTION.value and minor == OVPN3Constants.StatusMinor.CONN_CONNECTED.value):
            update_callback(True)
        elif (major == OVPN3Constants.StatusMajor.CONNECTION.value and minor == OVPN3Constants.StatusMinor.CONN_DISCONNECTED.value):
            update_callback(False)
        elif (major == OVPN3Constants.StatusMajor.CONNECTION.value and minor == OVPN3Constants.StatusMinor.CONN_PAUSED.value):
            update_callback(["pause"])
        elif (major == OVPN3Constants.StatusMajor.CONNECTION.value and minor == OVPN3Constants.StatusMinor.CONN_RESUMING.value):
            update_callback(["resume"])
        elif (major == OVPN3Constants.StatusMajor.CONNECTION.value and minor == OVPN3Constants.StatusMinor.CFG_OK.value):
            if self.get_setting(self.SETTING.AUTH_USER) is None and self.once:
                logger.warning("username is None. Proceeding with connection without auth.")
                self.module.init_unique_session()
                self.module.connect()
                self.once = False
