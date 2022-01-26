import urllib
import json


class Lookup:

    def __init__(self):
        self.ip = None
        self.country = None
        self.country_code = None

    def update(self):
        req = urllib.request.urlopen("http://ip-api.com/json/")
        data = json.loads(req.read())
        self.ip = data["query"]
        self.country = data["country"]
        self.country_code = data["countryCode"].lower()