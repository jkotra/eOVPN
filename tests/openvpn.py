import unittest
import pathlib

from eovpn.utils import download_remote_to_destination

class OpenVPN_test(unittest.TestCase):

    def test_openvpn_config_download_zip(self):
        remote = "https://www.ipvanish.com/software/configs/configs.zip"

        pathlib.Path("tests/data/").mkdir(parents=True, exist_ok=True)
        self.assertTrue(download_remote_to_destination(remote, "tests/data/"))

if __name__ == '__main__':
    unittest.main()