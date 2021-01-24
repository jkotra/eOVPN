import sys
import os
import unittest

import gi
gi.require_version('Gtk', '3.0')


from eovpn.openvpn import OpenVPN_eOVPN

class OpenVPN_test(unittest.TestCase):

    def test_openvpn_config_download(self):
        remote = "https://www.ipvanish.com/software/configs/configs.zip"
        openvpn = OpenVPN_eOVPN(None, None, None)
        self.assertTrue(openvpn.download_config_to_dest_plain(remote, "."))

if __name__ == '__main__':
    unittest.main()