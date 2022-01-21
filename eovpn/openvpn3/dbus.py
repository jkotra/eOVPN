from gi.repository import Gio, GLib, Secret
import logging
from eovpn.eovpn_base import Base

logger = logging.getLogger(__name__)

class OVPN3Dbus(Base):

    def __init__(self):
        super().__init__()
        self.conn = None
        self.mo = None

        self.username = self.get_setting(self.SETTING.AUTH_USER)
        self.password = None

        if self.username is not None:
            try:
                self.password = Secret.password_lookup_sync(self.EOVPN_SECRET_SCHEMA, {
                                                       "username": self.get_setting(self.SETTING.AUTH_USER)}, None)
            except Exception as e:
                self.password = self.get_setting(self.SETTING.AUTH_PASS)

    def set_binding(self, bo):
        self.mo = bo


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
    
        x = GLib.Variant("(uus)", parameters)
        major = x.get_child_value(0).get_uint32()
        minor = x.get_child_value(1).get_uint32()
        reason = x.get_child_value(2).get_string()

        logger.debug("{} {} {}".format(major, minor, reason))

        if(major == 2 and minor == 4):
            self.mo.send_auth(self.username, self.password)
            logger.info("Auth Sent!")
            self.mo.connect()
        elif (major == 2 and minor == 6):
            #in progress 
            update_callback([])
        elif (major == 2 and minor == 7):
            update_callback(True)
            pass
        elif (major == 2 and minor == 14):
            update_callback(["pause"])
            pass
        elif (major == 2 and minor == 15):
            update_callback(["resume"])
            pass
