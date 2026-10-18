import sys
import os
import unittest
import tempfile
from unittest.mock import MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("Secret", "1")
from gi.repository import Gio, Gtk

root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
gre_path = os.path.join(root_dir, "build/data/com.github.jkotra.eovpn.gresource")
if os.path.exists(gre_path):
    try:
        resource = Gio.resource_load(gre_path)
        Gio.Resource._register(resource)
    except Exception:
        pass
os.environ["GSETTINGS_SCHEMA_DIR"] = os.path.join(root_dir, "data")

from eovpn.connection_manager import NetworkManager, OpenVPN3


class ConnectionManagerTest(unittest.TestCase):
    def setUp(self):
        self.nm = NetworkManager(lambda x: None)
        self.ovpn3_callbacks = []
        self.ovpn3 = OpenVPN3(lambda x: self.ovpn3_callbacks.append(x))

    def test_nm_connect_with_none_credentials(self):
        """Ensure connect() does not raise TypeError when credentials are None."""
        self.nm.set_setting(self.nm.SETTING.AUTH_USER, None)
        self.nm.set_setting(self.nm.SETTING.AUTH_PASS, None)

        with tempfile.NamedTemporaryFile("w", suffix=".ovpn", delete=False) as f:
            f.write("client\ndev tun\nremote 127.0.0.1 1194\n")
            cfg_path = f.name

        try:
            # Should not raise TypeError: initializer for ctype 'char *' must be a cdata pointer, not NoneType
            self.nm.connect(cfg_path)
        finally:
            if os.path.exists(cfg_path):
                os.remove(cfg_path)

    def test_nm_disconnect_without_active_vpn(self):
        """Ensure disconnect() does not crash or infinite loop when no VPN is active."""
        self.nm.uuid = None
        self.nm.disconnect()
        self.assertIsNone(self.nm.uuid)

    def test_openvpn3_version_and_status(self):
        """Ensure OpenVPN3 can query version and status."""
        version = self.ovpn3.version()
        self.assertIsNotNone(version)
        self.assertIn("v", version)
        status = self.ovpn3.status()
        self.assertIn(status, [0, 1])

    def test_openvpn3_import_prepare_and_disconnect(self):
        """Ensure OpenVPN3 can import config, prepare tunnel, check readiness, and disconnect."""
        sample_config = (
            "client\n"
            "dev tun\n"
            "proto udp\n"
            "remote 127.0.0.1 1194\n"
            "resolv-retry infinite\n"
            "nobind\n"
            "persist-key\n"
            "persist-tun\n"
            "verb 3\n"
        )
        with tempfile.NamedTemporaryFile("w", suffix=".ovpn", delete=False) as f:
            f.write(sample_config)
            cfg_path = f.name

        try:
            self.ovpn3.connect(cfg_path)
            self.assertIsNotNone(self.ovpn3.config_path)
            self.assertIsNotNone(self.ovpn3.session_path)
            self.assertTrue(self.ovpn3.is_ready())
            self.ovpn3.disconnect()
            self.assertIsNone(self.ovpn3.session_path)
            self.assertIsNone(self.ovpn3.config_path)
            self.assertIn(False, self.ovpn3_callbacks)
        finally:
            if os.path.exists(cfg_path):
                os.remove(cfg_path)

    def test_inline_ovpn_config_content(self):
        """Ensure inline_ovpn_config_content inlines external ca, cert, key, tls-auth."""
        from eovpn.utils import inline_ovpn_config_content

        with tempfile.TemporaryDirectory() as tmpdir:
            ca_path = os.path.join(tmpdir, "ca.crt")
            with open(ca_path, "w") as f:
                f.write("-----BEGIN CERTIFICATE-----\nCA_DATA\n-----END CERTIFICATE-----")

            ta_path = os.path.join(tmpdir, "ta.key")
            with open(ta_path, "w") as f:
                f.write("-----BEGIN OpenVPN Static key V1-----\nTA_DATA\n-----END OpenVPN Static key V1-----")

            raw_ovpn = (
                "client\n"
                "dev tun\n"
                "auth-user-pass creds.txt\n"
                "ca ca.crt\n"
                "tls-auth ta.key 1\n"
            )

            inlined = inline_ovpn_config_content(raw_ovpn, search_dirs=[tmpdir], ca_override=ca_path)
            self.assertIn("<ca>\n-----BEGIN CERTIFICATE-----\nCA_DATA\n-----END CERTIFICATE-----\n</ca>", inlined)
            self.assertIn("<tls-auth>\n-----BEGIN OpenVPN Static key V1-----\nTA_DATA\n-----END OpenVPN Static key V1-----\n</tls-auth>", inlined)
            self.assertIn("key-direction 1", inlined)
            self.assertIn("# inlined: ca ca.crt", inlined)
            self.assertIn("# inlined: tls-auth ta.key 1", inlined)
            self.assertNotIn("creds.txt", inlined)

    def test_openvpn3_connect_with_credentials_and_separate_ca(self):
        """Ensure OpenVPN3 can import and prepare config with separate CA and credentials."""
        playground_dir = "/home/jkotra/agy-playground/openvpn-playground/clients/2-userpass-separate-ca"
        cfg_file = os.path.join(playground_dir, "client2-userpass-separate.ovpn")
        ca_file = os.path.join(playground_dir, "ca.crt")
        if not os.path.exists(cfg_file) or not os.path.exists(ca_file):
            self.skipTest("Playground client 2 not found")

        self.ovpn3.set_setting(self.ovpn3.SETTING.AUTH_USER, "vpnuser")
        self.ovpn3.set_setting(self.ovpn3.SETTING.AUTH_PASS, "vpnuser123")
        self.ovpn3.set_setting(self.ovpn3.SETTING.CA, ca_file)

        self.ovpn3.start_watch()
        try:
            self.ovpn3.connect(cfg_file)
            self.assertIsNotNone(self.ovpn3.config_path)
            self.assertIsNotNone(self.ovpn3.session_path)
            # After handle_attention sends credentials, is_ready() should be True
            self.assertTrue(self.ovpn3.is_ready())
        finally:
            self.ovpn3.disconnect()
            self.assertIsNone(self.ovpn3.session_path)

    def test_openvpn3_send_otp_when_session_is_none(self):
        """Ensure send_otp does not crash with TypeError when session_path is None."""
        self.ovpn3.session_path = None
        self.ovpn3_callbacks.clear()
        # Should not raise TypeError: initializer for ctype 'char *' must be a cdata pointer, not NoneType
        self.ovpn3.dbus.send_otp(["1", "2", "3", "4", "5", "6"])
        self.assertIn(False, self.ovpn3_callbacks)

    def test_openvpn3_send_otp_formats_and_calls_send_auth(self):
        """Ensure send_otp encodes bytes properly and invokes send_auth and set_dco."""
        mock_ovpn3 = MagicMock()
        mock_ovpn3.is_ready_to_connect.return_value = self.ovpn3.ffi.NULL

        orig_ovpn3 = self.ovpn3.ovpn3
        self.ovpn3.ovpn3 = mock_ovpn3

        try:
            test_session = b"/net/openvpn/v3/sessions/test1234"
            self.ovpn3.session_path = test_session

            self.ovpn3.dbus.send_otp(["8", "2", "2", "6", "8", "2"])

            mock_ovpn3.send_auth.assert_called_once()
            args = mock_ovpn3.send_auth.call_args[0]
            self.assertEqual(args[0], test_session)
            self.assertEqual(args[4], b"822682")
            mock_ovpn3.set_dco.assert_called_once()
            mock_ovpn3.connect_vpn.assert_called_once()
        finally:
            self.ovpn3.ovpn3 = orig_ovpn3

    def test_openvpn3_otp_dialog_cleanup_on_disconnect(self):
        """Ensure active OTP dialog is closed when disconnecting."""
        mock_dialog = MagicMock()
        self.ovpn3.dbus.otp_dialog = mock_dialog

        self.ovpn3.disconnect()
        mock_dialog.close.assert_called_once()
        self.assertIsNone(self.ovpn3.dbus.otp_dialog)

    def test_otp_input_window_lifecycle(self):
        """Ensure OTPInputWindow gathers OTP before destroy and handles cancel cleanly."""
        from eovpn.dialogs.otp import OTPInputWindow

        received = []
        err = []
        w = OTPInputWindow(lambda code: received.append(code), lambda: err.append(True))
        for i, d in enumerate(["8", "2", "2", "6", "8", "2"], 1):
            w.builder.get_object(f"O{i}").set_text(d)

        self.assertTrue(w.submit_btn.get_sensitive())
        w.return_and_destroy()
        self.assertEqual(received, [["8", "2", "2", "6", "8", "2"]])
        self.assertEqual(err, [])

        # Test manual close invokes error callback
        received.clear()
        err.clear()
        w2 = OTPInputWindow(lambda code: received.append(code), lambda: err.append(True))
        w2.manual_close(w2.window)
        self.assertEqual(received, [])
        self.assertEqual(err, [True])


if __name__ == "__main__":
    unittest.main()
