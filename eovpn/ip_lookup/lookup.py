import gi
import time
import urllib
import json
gi.require_version('Geoclue', '2.0') 
from gi.repository import Geoclue
import xml.etree.ElementTree as ET


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