import gi
import requests
import time
gi.require_version('Geoclue', '2.0') 
from gi.repository import Geoclue
import xml.etree.ElementTree as ET


class Lookup:

    def __init__(self):
        self.ip = None
        self.country = None
        self.country_code = None

    def update(self):
        req = requests.get("http://ip-api.com/json/")
        data = req.json()

        self.ip = data["query"]
        self.country = data["country"]
        self.country_code = data["countryCode"].lower()