import sys
import os
import unittest
import pathlib

from eovpn.openvpn import OpenVPN_eOVPN

class OpenVPN_test(unittest.TestCase):

    def test_openvpn_config_download_zip(self):
        remote = "https://www.ipvanish.com/software/configs/configs.zip"
        openvpn = OpenVPN_eOVPN(None, None, None)

        pathlib.Path("tests/data/").mkdir(parents=True, exist_ok=True)
        self.assertTrue(openvpn.download_config_to_destination(remote, "tests/data/"))

if __name__ == '__main__':
    unittest.main()