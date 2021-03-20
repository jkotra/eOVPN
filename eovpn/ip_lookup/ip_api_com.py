import requests
import json
import logging

logger = logging.getLogger(__name__)

class IP_API_COM:

    def lookup(self, ip=None) -> None:
        try:
            if ip is None:
                ip_req = requests.get("http://ip-api.com/json/")
            else:
                ip_req = requests.get("http://ip-api.com/json/" + ip)     
            self.ip_details = json.loads(ip_req.content)
        except Exception as e:
            logger.error(str(e))
            raise(e)
    
    def get_ip(self) -> str:
        return self.ip_details['query']
    
    def get_country(self) -> str:
        return self.ip_details['country']

    def get_country_code(self) -> str:
        return self.ip_details['countryCode']












#get these - set_{ip, country{}, }