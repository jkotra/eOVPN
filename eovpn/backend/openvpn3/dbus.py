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
    
    def get_attention(self):
        print(self.module.get_session_path())
        typegroup = self.conn.call_sync("net.openvpn.v3.sessions",
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

                parmas = GLib.Variant('(uu)', (atn_type.value, atn_grp.value) )
                inputs = []

                req_inputs = self.conn.call_sync("net.openvpn.v3.sessions",
                                                self.module.get_session_path().decode("utf-8"),
                                                "net.openvpn.v3.sessions",
                                                "UserInputQueueCheck",
                                                parmas,
                                                GLib.VariantType("(au)"),
                                                Gio.DBusSignalFlags.NONE,
                                                -1,
                                                None)
                
                req_inputs = req_inputs.get_child_value(0)

                for i in range(0, req_inputs.n_children()):
                    _i = req_inputs.get_child_value(i).get_uint32()
                    inputs.append((atn_type, atn_grp, _i))
                
                return inputs



    def sub_callback(self, connection, sender_name, object_path, interface_name, signal_name, parameters, update_callback):
        
        # https://github.com/OpenVPN/openvpn3-linux/blob/master/src/dbus/constants.hpp
        status = GLib.Variant("(uus)", parameters)
        major = OVPN3Constants.StatusMajor(status.get_child_value(0).get_uint32())
        minor = OVPN3Constants.StatusMinor(status.get_child_value(1).get_uint32())
        reason = status.get_child_value(2).get_string()

        logger.debug("{}({}) {}({}) {}".format(major, status.get_child_value(0).get_uint32(), minor, status.get_child_value(1).get_uint32(), reason))

        if(major == OVPN3Constants.StatusMajor.CONNECTION and minor == OVPN3Constants.StatusMinor.CFG_REQUIRE_USER):
            if self.get_setting(self.SETTING.AUTH_USER) is None:
                update_callback(False, reason)
                return

            attention = self.get_attention()
            for (t, g, i) in attention:
                logger.info("%s %s %i", t, g, i)
                if i == 0:
                    self.module.ovpn3.send_auth(self.module.get_session_path(), t.value, g.value, i, self.get_setting(self.SETTING.AUTH_USER).encode("utf-8"))
                elif i == 1:
                    self.module.ovpn3.send_auth(self.module.get_session_path(), t.value, g.value, i, self.get_auth_password().encode("utf-8"))
                else:
                    logger.debug("unknown input required!")
            self.module.ovpn3.set_dco(self.module.get_session_path(), 1)
            self.module.ovpn3.set_log_forward()
            self.module.ovpn3.connect_vpn()
        elif (major == OVPN3Constants.StatusMajor.CONNECTION and minor == OVPN3Constants.StatusMinor.CONN_AUTH_FAILED):
            logger.error(reason)
            update_callback(False, reason)
        elif (major == OVPN3Constants.StatusMajor.CONNECTION and minor == OVPN3Constants.StatusMinor.CONN_CONNECTING):
            update_callback([])
        elif (major == OVPN3Constants.StatusMajor.CONNECTION and minor == OVPN3Constants.StatusMinor.CONN_CONNECTED):
            update_callback(True)
        elif (major == OVPN3Constants.StatusMajor.CONNECTION and minor == OVPN3Constants.StatusMinor.CONN_DISCONNECTED):
            update_callback(False)
        elif (major == OVPN3Constants.StatusMajor.CONNECTION and minor == OVPN3Constants.StatusMinor.CONN_PAUSED):
            update_callback(["pause"])
        elif (major == OVPN3Constants.StatusMajor.CONNECTION and minor == OVPN3Constants.StatusMinor.CONN_RESUMING):
            update_callback(["resume"])
        elif (major == OVPN3Constants.StatusMajor.CONNECTION and minor == OVPN3Constants.StatusMinor.CFG_OK):
            if self.get_setting(self.SETTING.AUTH_USER) is None and self.once:
                logger.warning("username is None. Proceeding with connection without auth.")
                self.module.ovpn3.init_unique_session()
                self.module.ovpn3.connect_vpn()
                self.once = False
