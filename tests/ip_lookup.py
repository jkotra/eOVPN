import unittest
from eovpn.ip_lookup.lookup import IP_API_COM, IPLOCATE_IO, IPINFO_IO, IP2C_ORG


class ip_lookup_tests(unittest.TestCase):

    def test_ip_api(self):
        _ = IP_API_COM()
        _.lookup()
        self.assertEqual(type(_.get_ip()), str)
        self.assertEqual(type(_.get_country()), str)
        self.assertEqual(type(_.get_country_code()), str)

    def test_iplocate_io(self):
        _ = IPLOCATE_IO()
        _.lookup()
        self.assertEqual(type(_.get_ip()), str)
        self.assertEqual(type(_.get_country()), str)
        self.assertEqual(type(_.get_country_code()), str)

    def test_ipinfo_io(self):
        _ = IPINFO_IO()
        _.lookup()
        self.assertEqual(type(_.get_ip()), str)
        self.assertEqual(type(_.get_country()), str)
        self.assertEqual(type(_.get_country_code()), str)

    def test_ip2c_org(self):
        _ = IP2C_ORG()
        _.lookup()
        self.assertEqual(type(_.get_country()), str)
        self.assertEqual(type(_.get_country_code()), str)

if __name__ == '__main__':
    unittest.main()