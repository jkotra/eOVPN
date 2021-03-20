from typing import Dict

from .ip_api_com import IP_API_COM
from .ip2c_org import IP2C_ORG
from .iplocate_io import IPLOCATE_IO
from .ipinfo_io import IPINFO_IO

from eovpn.eovpn_base import Base
import gettext

class LocationDetails(Base):
    def __init__(self):
        super().__init__()
        self.available = [IP_API_COM(), IPLOCATE_IO(), IPINFO_IO(), IP2C_ORG()]

    def set(self, widgets: Dict, connection_status: bool):
        
        # connection_status = True = Connected
        # connection_status = False = Disconnected
        
        ip = None
        country = None
        country_code = None
        ctx = widgets["status_label"].get_style_context()

        for api in self.available:
            try:
                api.lookup()
            except:
                continue
            ip = api.get_ip()
            country = api.get_country()
            country_code = api.get_country_code()
            break

        if ip is None:
            widgets["status_label"].set_text(gettext.gettext("No Network"))
            uno = self.get_country_image("uno")
            widgets["country_image"].set_from_pixbuf(uno)
            ctx.add_class("bg_black")
            return

        widgets["ip_label"].set_label(ip)
        widgets["location_label"].set_label(country)

        country_image = self.get_country_image(country_code.lower())
        widgets["country_image"].set_from_pixbuf(country_image)

        if connection_status:
            ctx.remove_class("bg_red")
            ctx.add_class("bg_green")
            widgets["status_label"].set_label(gettext.gettext("Connected"))
            widgets["connect_btn"].set_label(gettext.gettext("Disconnect!"))
        else:
            ctx.add_class("bg_red")
            ctx.remove_class("bg_green")
            widgets["status_label"].set_label(gettext.gettext("Disconnected"))
            widgets["connect_btn"].set_label(gettext.gettext("Connect!"))


    def set_ping_ip_details(self, ip, widgets):

        country = None
        country_code = None


        for api in self.available:
            try:
                api.lookup(ip)
            except:
                continue
            country = api.get_country()
            country_code = api.get_country_code()
            break

        widgets["img"].set_from_pixbuf(self.get_country_image(country_code.lower()))
        widgets["name"].set_label(country)


        

