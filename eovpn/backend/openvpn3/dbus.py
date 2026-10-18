from gi.repository import Gio, GLib, Secret
import logging
from eovpn.eovpn_base import Base
from eovpn.dialogs.otp import OTPInputWindow

logger = logging.getLogger(__name__)

try:
    from openvpn3 import constants as OVPN3Constants
except Exception as e:
    logger.warning("openvpn3 error: %s", e)


def to_session_str(session_path):
    if session_path is None:
        return None
    if isinstance(session_path, bytes):
        return session_path.decode("utf-8")
    return str(session_path)


class OVPN3Dbus(Base):

    def __init__(self):
        super().__init__()
        self.dbus_connection = None
        self.module = None
        self.attention_subscription = None
        self.event_subscriptions = []
        self.otp_dialog = None

        self.dbus_connection = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)

    def get_auth_password(self):
        username = self.get_setting(self.SETTING.AUTH_USER)
        pw = None
        if username:
            try:
                pw = Secret.password_lookup_sync(
                    self.EOVPN_SECRET_SCHEMA,
                    {"username": username},
                    None,
                )
            except Exception as e:
                logger.error("Secret password lookup failed: %s", e)
        if not pw:
            pw = self.get_setting(self.SETTING.AUTH_PASS)
        return pw

    def set_binding(self, binding):
        self.module = binding

    def subscribe_for_attention(self, session_path: str = None):
        # receive signals for ex: auth!
        if self.attention_subscription is not None:
            self.unsubscribe(self.attention_subscription)
            self.attention_subscription = None

        self.attention_subscription = self.dbus_connection.signal_subscribe(
            None,
            "net.openvpn.v3.sessions",
            "AttentionRequired",
            session_path,
            None,
            Gio.DBusSignalFlags.NONE,
            self.sub_attention_signal,
        )
        logger.info(
            "subscribed to AttentionRequired on %s (id = %s)",
            session_path,
            self.attention_subscription,
        )

    def subscribe_for_events(self, callback: callable, session_path: str = None):
        self.unsubscribe_events()
        sid = self.dbus_connection.signal_subscribe(
            None,
            "net.openvpn.v3.backends",
            "StatusChange",
            session_path,
            None,
            Gio.DBusSignalFlags.NONE,
            self.sub_status_signal,
            callback,
        )
        self.event_subscriptions.append(sid)
        logger.info("subscribed to StatusChange on %s (id = %s)", session_path, sid)

    def set_log_forward(self):
        if not self.module:
            return
        session_path = to_session_str(self.module.get_session_path())
        if not session_path:
            return
        try:
            self.dbus_connection.call_sync(
                "net.openvpn.v3.sessions",
                session_path,
                "net.openvpn.v3.sessions",
                "LogForward",
                GLib.Variant("(b)", (True,)),
                None,
                Gio.DBusSignalFlags.NONE,
                -1,
                None,
            )
        except Exception as e:
            logger.warning("LogForward call failed: %s", e)

    def unsubscribe(self, sub_id: int):
        logger.info("unsubscribing from signal id: %d", sub_id)
        try:
            self.dbus_connection.signal_unsubscribe(sub_id)
        except Exception as e:
            logger.debug("Failed to unsubscribe %s: %s", sub_id, e)

    def close_otp_dialog(self):
        if self.otp_dialog is not None:
            dialog = self.otp_dialog
            self.otp_dialog = None
            try:
                dialog.close()
            except Exception as e:
                logger.debug("Failed to close OTP dialog: %s", e)

    def unsubscribe_events(self):
        self.close_otp_dialog()
        for sid in self.event_subscriptions:
            self.unsubscribe(sid)
        self.event_subscriptions.clear()

    def unsubscribe_all(self):
        self.close_otp_dialog()
        self.unsubscribe_events()
        if self.attention_subscription is not None:
            self.unsubscribe(self.attention_subscription)
            self.attention_subscription = None

    def send_otp(
        self,
        otp: list[str] | list[int] | str,
        session_path=None,
        t=None,
        g=None,
        i: int = 0,
    ):
        if not self.module:
            logger.warning("No backend module available to send OTP")
            return

        if not session_path:
            session_path = self.module.get_session_path()

        if not session_path or self.module.get_session_path() is None:
            logger.error("Cannot send OTP: no active OpenVPN3 session")
            if self.module.callback:
                self.module.callback(False)
            return

        if isinstance(session_path, str):
            session_path = session_path.encode("utf-8")

        if t is None:
            t_val = OVPN3Constants.ClientAttentionType.CREDENTIALS.value
        elif hasattr(t, "value"):
            t_val = t.value
        else:
            t_val = int(t)

        if g is None:
            g_val = OVPN3Constants.ClientAttentionGroup.CHALLENGE_STATIC.value
        elif hasattr(g, "value"):
            g_val = g.value
        else:
            g_val = int(g)

        if isinstance(otp, (list, tuple)):
            otp_str = "".join(str(x) for x in otp)
        else:
            otp_str = str(otp)

        otp_bytes = otp_str.encode("utf-8")
        logger.info("sending OTP: %s", otp_bytes)

        try:
            self.module.ovpn3.send_auth(
                session_path,
                t_val,
                g_val,
                i,
                otp_bytes,
            )
        except Exception as e:
            logger.error("Failed to send OTP auth to OpenVPN3: %s", e)
            if self.module.callback:
                self.module.callback(False)
            return

        try:
            self.module.ovpn3.set_dco(
                session_path, self.get_setting(self.SETTING.OPENVPN3_DCO)
            )
        except Exception as e:
            logger.warning("Failed to set DCO: %s", e)

        self.try_to_connect(session_path)

    def try_to_connect(self, session_path=None):
        if not self.module:
            return
        if self.module.is_ready():
            logger.info("*** connecting to vpn...")
            self.set_log_forward()
            if session_path is None:
                session_path = self.module.get_session_path()
            session_path_str = to_session_str(session_path)
            if self.module.callback and session_path_str:
                self.subscribe_for_events(
                    self.module.callback, session_path_str
                )
            self.module.ovpn3.connect_vpn()
        else:
            logger.warning("VPN not ready to connect yet")

    def get_attention(self):
        if not self.module:
            return []
        session_path = to_session_str(self.module.get_session_path())
        if not session_path:
            return []

        try:
            typegroup = self.dbus_connection.call_sync(
                "net.openvpn.v3.sessions",
                session_path,
                "net.openvpn.v3.sessions",
                "UserInputQueueGetTypeGroup",
                None,
                GLib.VariantType("(a(uu))"),
                Gio.DBusSignalFlags.NONE,
                -1,
                None,
            )
        except Exception as e:
            logger.debug("UserInputQueueGetTypeGroup failed: %s", e)
            return []

        typegroup_arr = typegroup.get_child_value(0).unpack()
        logger.debug("type-group: %s", typegroup_arr)

        required_attentions = []

        for atn_type, atn_grp in typegroup_arr:
            params = GLib.Variant("(uu)", (atn_type, atn_grp))
            logger.debug("calling UserInputQueueCheck: %s", params)

            try:
                req_inputs = self.dbus_connection.call_sync(
                    "net.openvpn.v3.sessions",
                    session_path,
                    "net.openvpn.v3.sessions",
                    "UserInputQueueCheck",
                    params,
                    GLib.VariantType("(au)"),
                    Gio.DBusSignalFlags.NONE,
                    -1,
                    None,
                )
                req_inputs = req_inputs.get_child_value(0).unpack()
            except Exception as e:
                logger.debug("UserInputQueueCheck failed: %s", e)
                continue

            logger.debug("response from UserInputQueueCheck: %s", req_inputs)

            for _i in req_inputs:
                params = GLib.Variant("(uuu)", (atn_type, atn_grp, _i))
                logger.debug("calling UserInputQueueFetch: %s", params)
                try:
                    ask = self.dbus_connection.call_sync(
                        "net.openvpn.v3.sessions",
                        session_path,
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
                except Exception as e:
                    logger.debug("UserInputQueueFetch failed: %s", e)

        return required_attentions

    def handle_attention(self):
        if not self.module:
            return False
        session_path = self.module.get_session_path()
        if not session_path:
            return False

        attention = self.get_attention()
        if not attention:
            return False

        session_path_bytes = (
            session_path.encode("utf-8")
            if isinstance(session_path, str)
            else session_path
        )

        for t, g, i, a in attention:
            logger.info("processing required attention: %s %s %i %s", t, g, i, a)
            if a == "username":
                logger.info("sending %s", a)
                user = self.get_setting(self.SETTING.AUTH_USER) or ""
                self.module.ovpn3.send_auth(
                    session_path_bytes,
                    t.value,
                    g.value,
                    i,
                    user.encode("utf-8"),
                )
            elif a == "password":
                logger.info("sending %s", a)
                pw = self.get_auth_password() or ""
                self.module.ovpn3.send_auth(
                    session_path_bytes,
                    t.value,
                    g.value,
                    i,
                    pw.encode("utf-8"),
                )
            elif a == "static_challenge":
                if self.otp_dialog is not None:
                    logger.debug("OTP dialog already open, ignoring duplicate attention")
                    return True

                def on_otp_submitted(otp_code):
                    self.otp_dialog = None
                    self.send_otp(
                        otp_code,
                        session_path=session_path_bytes,
                        t=t,
                        g=g,
                        i=i,
                    )

                def on_otp_error():
                    self.otp_dialog = None
                    if self.module and self.module.callback:
                        self.module.callback(False)

                self.otp_dialog = OTPInputWindow(on_otp_submitted, on_otp_error)
                self.otp_dialog.show()
                return True
            else:
                logger.error("unknown input required! %s", a)

        self.module.ovpn3.set_dco(
            session_path_bytes, self.get_setting(self.SETTING.OPENVPN3_DCO)
        )
        self.try_to_connect(session_path_bytes)
        return True

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
        self.handle_attention()

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
            and minor
            in (
                OVPN3Constants.StatusMinor.CONN_AUTH_FAILED,
                OVPN3Constants.StatusMinor.CONN_FAILED,
            )
        ):
            logger.error(reason)
            self.unsubscribe_events()
            if self.module:
                self.module.disconnect()  # cleanup
            elif update_callback:
                update_callback(False)
        elif (
            major == OVPN3Constants.StatusMajor.CONNECTION
            and minor == OVPN3Constants.StatusMinor.CONN_CONNECTING
        ):
            if update_callback:
                update_callback([])
        elif (
            major == OVPN3Constants.StatusMajor.CONNECTION
            and minor == OVPN3Constants.StatusMinor.CONN_CONNECTED
        ):
            if update_callback:
                update_callback(True)
        elif (
            major == OVPN3Constants.StatusMajor.CONNECTION
            and minor == OVPN3Constants.StatusMinor.CONN_DISCONNECTED
        ):
            self.unsubscribe_events()
            if self.module:
                self.module.disconnect()
            elif update_callback:
                update_callback(False)
        elif (
            major == OVPN3Constants.StatusMajor.CONNECTION
            and minor == OVPN3Constants.StatusMinor.CONN_PAUSED
        ):
            if update_callback:
                update_callback(["pause"])
        elif (
            major == OVPN3Constants.StatusMajor.CONNECTION
            and minor == OVPN3Constants.StatusMinor.CONN_RESUMING
        ):
            if update_callback:
                update_callback(["resume"])
        else:
            pass
