import urllib
import json
import logging
import socket

logger = logging.getLogger(__name__)

class Lookup:

    def __init__(self):
        self.ip = None
        self.country = None
        self.country_code = None

        self.fallback = [self.ip_api]

    def update(self):
        try:
            self.cloudflare()
        except Exception as e:
            logging.error(str(e))

            for f in self.fallback:
                logging.info("falling back to %s", f.__name__)
                try:
                    f()
                except:
                    continue

    def ip_api(self):
        req = urllib.request.urlopen("http://ip-api.com/json/")
        data = json.loads(req.read())
        logger.debug("ip-api.com: %s", data)
        self.ip = data["query"]
        self.country = data["country"]
        self.country_code = data["countryCode"].lower()

    def cloudflare(self):
        #cf_ipv6 = socket.getaddrinfo("cloudflare.com", 80, socket.AF_INET6)
        req = urllib.request.urlopen(f"http://{socket.gethostbyname('www.cloudflare.com')}/cdn-cgi/trace/")
        data = req.read().decode("utf-8")
        lines = data.strip().split("\n")
        for line in lines:
            _sp = line.split("=")
            key = _sp[0]
            value = _sp[1]

            logger.debug("Cloudflare: k = %s | v = %s", key, value)

            if key == "ip":
                self.ip = value
            if key == "loc":
                self.country_code = value.lower()
        
