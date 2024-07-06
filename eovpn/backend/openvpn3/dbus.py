from gi.repository import Gio, GLib, Secret
import logging
from eovpn.eovpn_base import Base

logger = logging.getLogger(__name__)

try:
    from openvpn3 import constants as OVPN3Constants
except:
    logger.warning("cannot import openvpn3")


class OVPN3Dbus(Base):

    def __init__(self):
        super().__init__()
        self.dbus_connection = None
        self.module = None
        self.status_change_sub_id = True

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
        self.dbus_connection = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)

        # receive signals for auth!
        self.dbus_connection.signal_subscribe("net.openvpn.v3.sessions",
                           None,
                           "AttentionRequired",
                           None,
                           None,
                           Gio.DBusSignalFlags.NONE,
                           self.sub_attention_signal,
                           callback)
    
    def set_log_forward(self):
        self.dbus_connection.call_sync("net.openvpn.v3.sessions",
                                                self.module.get_session_path().decode("utf-8"),
                                                "net.openvpn.v3.sessions",
                                                "LogForward",
                                                GLib.Variant('(b)',(True,)),
                                                None,
                                                Gio.DBusSignalFlags.NONE,
                                                -1,
                                                None)

    def watch_for_status(self, session_path: str, callback: callable):
        self.set_log_forward()
        sub = self.dbus_connection.signal_subscribe("net.openvpn.v3.log",
                           "net.openvpn.v3.backends",
                           "StatusChange",
                           session_path,
                           None,
                           Gio.DBusSignalFlags.NONE,
                           self.sub_status_signal,
                           callback)
        logger.info("subscribed to StatusChange: %d", sub)
        self.status_change_sub_id = sub

    def unsubscribe(self, sub_id: int):
        logger.info("unsubscribing from signal: %d", sub_id)
        self.dbus_connection.signal_unsubscribe(sub_id)
    
    def get_attention(self):
        typegroup = self.dbus_connection.call_sync("net.openvpn.v3.sessions",
                                    self.module.get_session_path().decode("utf-8"),
                                    "net.openvpn.v3.sessions",
                                    "UserInputQueueGetTypeGroup",
                                    None,
                                    GLib.VariantType("(a(uu))"),
                                    Gio.DBusSignalFlags.NONE,
                                    -1,
                                    None)
        
        typegroup_arr = typegroup.get_child_value(0)

        for atn_x in range(0, typegroup_arr.n_children()):
            atn_type = OVPN3Constants.ClientAttentionType(typegroup_arr.get_child_value(0).get_child_value(atn_x).get_uint32())
            atn_grp = OVPN3Constants.ClientAttentionGroup(typegroup_arr.get_child_value(0).get_child_value(atn_x).get_uint32())
            
            if (atn_type == OVPN3Constants.ClientAttentionType.CREDENTIALS and atn_grp == OVPN3Constants.ClientAttentionGroup.USER_PASSWORD):

                params = GLib.Variant('(uu)', (atn_type.value, atn_grp.value) )
                inputs = []

                req_inputs = self.dbus_connection.call_sync("net.openvpn.v3.sessions",
                                                self.module.get_session_path().decode("utf-8"),
                                                "net.openvpn.v3.sessions",
                                                "UserInputQueueCheck",
                                                params,
                                                GLib.VariantType("(au)"),
                                                Gio.DBusSignalFlags.NONE,
                                                -1,
                                                None)
                
                req_inputs = req_inputs.get_child_value(0)

                for i in range(0, req_inputs.n_children()):
                    _i = req_inputs.get_child_value(i).get_uint32()
                    inputs.append((atn_type, atn_grp, _i))
                
                return inputs

    def sub_attention_signal(self, connection, sender_name, object_path, interface_name, signal_name, parameters, on_connection_cb: callable):
        status = GLib.Variant("(uus)", parameters)
        major = OVPN3Constants.StatusMajor(status.get_child_value(0).get_uint32())
        minor = OVPN3Constants.StatusMinor(status.get_child_value(1).get_uint32())
        reason = status.get_child_value(2).get_string()

        logger.debug("{}({}) {}({}) {}".format(major, status.get_child_value(0).get_uint32(), minor, status.get_child_value(1).get_uint32(), reason))
        
        attention = self.get_attention()
        for (t, g, i) in attention:
            logger.info("%s %s %i", t, g, i)
            if i == 0:
                self.module.ovpn3.send_auth(self.module.get_session_path(), t.value, g.value, i, self.get_setting(self.SETTING.AUTH_USER).encode("utf-8"))
            elif i == 1:
                self.module.ovpn3.send_auth(self.module.get_session_path(), t.value, g.value, i, self.get_auth_password().encode("utf-8"))
            else:
                logger.error("unknown input required!")
        self.module.ovpn3.set_dco(self.module.get_session_path(), self.get_setting(self.SETTING.OPENVPN3_DCO))
        self.watch_for_status(self.module.get_session_path().decode("utf-8"), on_connection_cb)
        self.module.ovpn3.connect_vpn()
        logger.info("connecting to vpn...")
    
    def sub_status_signal(self, connection, sender_name, object_path, interface_name, signal_name, parameters, update_callback):
        status = GLib.Variant("(uus)", parameters)
        major = OVPN3Constants.StatusMajor(status.get_child_value(0).get_uint32())
        minor = OVPN3Constants.StatusMinor(status.get_child_value(1).get_uint32())
        reason = status.get_child_value(2).get_string()
        logger.debug("{}({}) {}({}) {}".format(major, status.get_child_value(0).get_uint32(), minor, status.get_child_value(1).get_uint32(), reason))

        if (major == OVPN3Constants.StatusMajor.CONNECTION and minor == OVPN3Constants.StatusMinor.CONN_AUTH_FAILED):
            logger.error(reason)
            update_callback(False, reason)
        elif (major == OVPN3Constants.StatusMajor.CONNECTION and minor == OVPN3Constants.StatusMinor.CONN_CONNECTING):
            update_callback([])
        elif (major == OVPN3Constants.StatusMajor.CONNECTION and minor == OVPN3Constants.StatusMinor.CONN_CONNECTED):
            update_callback(True)
        elif (major == OVPN3Constants.StatusMajor.CONNECTION and minor == OVPN3Constants.StatusMinor.CONN_DISCONNECTED):
            self.unsubscribe(self.status_change_sub_id)
            update_callback(False)
        elif (major == OVPN3Constants.StatusMajor.CONNECTION and minor == OVPN3Constants.StatusMinor.CONN_PAUSED):
            update_callback(["pause"])
        elif (major == OVPN3Constants.StatusMajor.CONNECTION and minor == OVPN3Constants.StatusMinor.CONN_RESUMING):
            update_callback(["resume"])