import requests
import json
import logging

logger = logging.getLogger(__name__)

class IP2C_ORG:

    def lookup(self, ip=None) -> None:
        try:
            if ip is None:
                ip_req = requests.get("https://ip2c.org/self")
            else:
                ip_req = requests.get("https://ip2c.org/?dec=" + ip) 

            self.ip_details = ip_req.content.decode('utf-8')
            self.ip_details = self.ip_details.split(";")
        except Exception as e:
            logger.error(str(e))
            raise(e)
    
    def get_ip(self) -> str:
        return "-"
    
    def get_country(self) -> str:
        return self.ip_details[-1]

    def get_country_code(self) -> str:
        return self.ip_details[1]