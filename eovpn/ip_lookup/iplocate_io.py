import requests
import json
import logging

logger = logging.getLogger(__name__)

class IPLOCATE_IO:

    def lookup(self, ip=None) -> None:
        try:
            if ip is None:
                ip_req = requests.get("https://www.iplocate.io/api/lookup/")
            else:
                ip_req = requests.get("https://www.iplocate.io/api/lookup/" + ip) 
            self.ip_details = json.loads(ip_req.content) 
        except Exception as e:
            logger.error(str(e))
            raise(e)
    
    def get_ip(self) -> str:
        return self.ip_details['ip']
    
    def get_country(self) -> str:
        return self.ip_details['country']

    def get_country_code(self) -> str:
        return self.ip_details['country_code']