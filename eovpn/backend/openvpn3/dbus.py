from gi.repository import Gio, GLib, Secret
import logging
from eovpn.eovpn_base import Base
from eovpn.dialogs.otp import OTPInputWindow

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
        self.subscriptions = []

        self.dbus_connection = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)

    def get_auth_password(self):
        try:
            return Secret.password_lookup_sync(
                self.EOVPN_SECRET_SCHEMA,
                {"username": self.get_setting(self.SETTING.AUTH_USER)},
                None,
            )
        except Exception as e:
            logger.error(e)
            self.password = self.get_setting(self.SETTING.AUTH_PASS)

    def set_binding(self, binding):
        self.module = binding

    def subscribe_for_attention(self, session_path: str = None):
        # receive signals for ex: auth!
        sid = self.dbus_connection.signal_subscribe(
            "net.openvpn.v3.sessions",
            None,
            "AttentionRequired",
            session_path,
            None,
            Gio.DBusSignalFlags.NONE,
            self.sub_attention_signal,
        )
        logger.info(
            "subscribed to AttentionRequired on %s (id = %s)", session_path, sid
        )

    def subscribe_for_events(self, callback: callable, session_path: str = None):
        sid = self.dbus_connection.signal_subscribe(
            "net.openvpn.v3.log",
            "net.openvpn.v3.backends",
            "StatusChange",
            session_path,
            None,
            Gio.DBusSignalFlags.NONE,
            self.sub_status_signal,
            callback,
        )
        self.subscriptions.append(sid)
        logger.info("subscribed to StatusChange on %s (id = %s)", session_path, sid)

    def set_log_forward(self):
        self.dbus_connection.call_sync(
            "net.openvpn.v3.sessions",
            self.module.get_session_path().decode("utf-8"),
            "net.openvpn.v3.sessions",
            "LogForward",
            GLib.Variant("(b)", (True,)),
            None,
            Gio.DBusSignalFlags.NONE,
            -1,
            None,
        )

    def unsubscribe(self, sub_id: int):
        logger.info("unsubscribing from signal id: %d", sub_id)
        self.dbus_connection.signal_unsubscribe(sub_id)

    def unsubscribe_all(self):
        for sid in self.subscriptions:
            self.unsubscribe(sid)
        self.subscriptions.clear()

    def send_otp(self, otp: list[int]):
        t = OVPN3Constants.ClientAttentionType.CREDENTIALS
        g = OVPN3Constants.ClientAttentionGroup.CHALLENGE_AUTH_PENDING
        i = 0

        otp = "".join(otp).encode("utf-8")
        logger.info("sending OTP: %s", otp)

        self.module.ovpn3.send_auth(
            self.module.get_session_path(),
            t.value,
            g.value,
            i,
            otp,
        )
        self.try_to_connect()

    def try_to_connect(self):
        if self.module.is_ready():
            logger.info("*** connecting to vpn...")
            self.set_log_forward()
            self.subscribe_for_events(
                self.module.callback, self.module.get_session_path().decode("utf-8")
            )
            self.module.ovpn3.connect_vpn()

    def get_attention(self):
        typegroup = self.dbus_connection.call_sync(
            "net.openvpn.v3.sessions",
            self.module.get_session_path().decode("utf-8"),
            "net.openvpn.v3.sessions",
            "UserInputQueueGetTypeGroup",
            None,
            GLib.VariantType("(a(uu))"),
            Gio.DBusSignalFlags.NONE,
            -1,
            None,
        )

        typegroup_arr = typegroup.get_child_value(0).unpack()
        logger.debug("type-group: %s", typegroup_arr)

        required_attentions = []

        for atn_type, atn_grp in typegroup_arr:
            params = GLib.Variant("(uu)", (atn_type, atn_grp))
            logger.debug("calling UserInputQueueCheck: %s", params)

            req_inputs = self.dbus_connection.call_sync(
                "net.openvpn.v3.sessions",
                self.module.get_session_path().decode("utf-8"),
                "net.openvpn.v3.sessions",
                "UserInputQueueCheck",
                params,
                GLib.VariantType("(au)"),
                Gio.DBusSignalFlags.NONE,
                -1,
                None,
            )

            req_inputs = req_inputs.get_child_value(0).unpack()
            logger.debug("response from UserInputQueueCheck: %s", req_inputs)

            for _i in req_inputs:
                params = GLib.Variant("(uuu)", (atn_type, atn_grp, _i))
                logger.debug("calling UserInputQueueFetch: %s", params)
                ask = self.dbus_connection.call_sync(
                    "net.openvpn.v3.sessions",
                    self.module.get_session_path().decode("utf-8"),
                    "net.openvpn.v3.sessions",
                    "UserInputQueueFetch",
                    params,
                    GLib.VariantType("(uuussb)"),
                    Gio.DBusSignalFlags.NONE,
                    -1,
                    None,
                )
                ask = ask.get_child_value(3).unpack()
                logger.debug("Response from UserInputQueueFetch: %s", ask)
                required_attentions.append(
                    (
                        OVPN3Constants.ClientAttentionType(atn_type),
                        OVPN3Constants.ClientAttentionGroup(atn_grp),
                        _i,
                        ask,
                    )
                )

        return required_attentions

    def sub_attention_signal(
        self,
        connection,
        sender_name,
        object_path,
        interface_name,
        signal_name,
        parameters,
    ):
        status = GLib.Variant("(uus)", parameters)
        major = OVPN3Constants.StatusMajor(status.get_child_value(0).get_uint32())
        minor = OVPN3Constants.StatusMinor(status.get_child_value(1).get_uint32())
        reason = status.get_child_value(2).get_string()

        logger.debug(
            "AttentionRequired: {}({}) {}({}) {}".format(
                major,
                status.get_child_value(0).get_uint32(),
                minor,
                status.get_child_value(1).get_uint32(),
                reason,
            )
        )

        attention = self.get_attention()

        for t, g, i, a in attention:
            logger.info("processing required attention: %s %s %i %s", t, g, i, a)
            if a == "username":
                logger.info("sending %s", a)
                self.module.ovpn3.send_auth(
                    self.module.get_session_path(),
                    t.value,
                    g.value,
                    i,
                    self.get_setting(self.SETTING.AUTH_USER).encode("utf-8"),
                )
            elif a == "password":
                logger.info("sending %s", a)
                self.module.ovpn3.send_auth(
                    self.module.get_session_path(),
                    t.value,
                    g.value,
                    i,
                    self.get_auth_password().encode("utf-8"),
                )
            elif a == "auth_pending":
                OTPInputWindow(self.send_otp, lambda: self.module.callback(False)).show()
            else:
                logger.error("unknown input required!")

        self.module.ovpn3.set_dco(
            self.module.get_session_path(), self.get_setting(self.SETTING.OPENVPN3_DCO)
        )

        self.try_to_connect()

    def sub_status_signal(
        self,
        connection,
        sender_name,
        object_path,
        interface_name,
        signal_name,
        parameters,
        update_callback,
    ):
        status = GLib.Variant("(uus)", parameters)
        major = OVPN3Constants.StatusMajor(status.get_child_value(0).get_uint32())
        minor = OVPN3Constants.StatusMinor(status.get_child_value(1).get_uint32())
        reason = status.get_child_value(2).get_string()
        logger.debug(
            "StatusChange: {}({}) {}({}) {}".format(
                major,
                status.get_child_value(0).get_uint32(),
                minor,
                status.get_child_value(1).get_uint32(),
                reason,
            )
        )

        if (
            major == OVPN3Constants.StatusMajor.CONNECTION
            and minor == OVPN3Constants.StatusMinor.CONN_AUTH_FAILED
        ):
            logger.error(reason)
            update_callback(False, reason)
            self.unsubscribe_all()
            self.module.disconnect()  # cleanup
        elif (
            major == OVPN3Constants.StatusMajor.CONNECTION
            and minor == OVPN3Constants.StatusMinor.CONN_CONNECTING
        ):
            update_callback([])
        elif (
            major == OVPN3Constants.StatusMajor.CONNECTION
            and minor == OVPN3Constants.StatusMinor.CONN_CONNECTED
        ):
            update_callback(True)
        elif (
            major == OVPN3Constants.StatusMajor.CONNECTION
            and minor == OVPN3Constants.StatusMinor.CONN_DISCONNECTED
        ):
            self.unsubscribe_all()
            update_callback(False)
        elif (
            major == OVPN3Constants.StatusMajor.CONNECTION
            and minor == OVPN3Constants.StatusMinor.CONN_PAUSED
        ):
            update_callback(["pause"])
        elif (
            major == OVPN3Constants.StatusMajor.CONNECTION
            and minor == OVPN3Constants.StatusMinor.CONN_RESUMING
        ):
            update_callback(["resume"])
        else:
            pass
