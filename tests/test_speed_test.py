import unittest
from unittest.mock import patch, MagicMock
import os
import socket
from eovpn.speed_test import parse_ovpn_remote, ping_host, test_single_ovpn

class TestSpeedTest(unittest.TestCase):
    def test_parse_ovpn_remote(self):
        # Create a temporary ovpn file
        test_file = "test_config.ovpn"
        with open(test_file, "w") as f:
            f.write("# comment\n")
            f.write("remote 127.0.0.1 443 tcp\n")
            f.write("remote google.com 80\n")
            f.write("remote fallback.net\n")

        remotes = parse_ovpn_remote(test_file)
        os.remove(test_file)

        self.assertEqual(len(remotes), 3)
        self.assertEqual(remotes[0], ("127.0.0.1", 443))
        self.assertEqual(remotes[1], ("google.com", 80))
        self.assertEqual(remotes[2], ("fallback.net", 1194))

    @patch('socket.socket')
    def test_ping_host_success(self, mock_socket):
        # Mock successful connection
        mock_s_inst = MagicMock()
        mock_socket.return_value = mock_s_inst

        rtt = ping_host("google.com", 80, timeout=2.0)
        self.assertIsNotNone(rtt)
        self.assertGreater(rtt, 0)
        mock_s_inst.connect.assert_called_once_with(("google.com", 80))
        mock_s_inst.close.assert_called_once()

    @patch('socket.socket')
    def test_ping_host_fail(self, mock_socket):
        # Mock connection failure (e.g., timeout exception)
        mock_s_inst = MagicMock()
        mock_s_inst.connect.side_effect = socket.timeout("timeout")
        mock_socket.return_value = mock_s_inst

        rtt = ping_host("192.0.2.1", 12345, timeout=0.5)
        self.assertIsNone(rtt)
        mock_s_inst.close.assert_called_once()

if __name__ == "__main__":
    unittest.main()
