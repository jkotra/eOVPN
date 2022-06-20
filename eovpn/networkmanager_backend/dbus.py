import gi
gi.require_version("NM", "1.0")
from gi.repository import GLib, Gio, NM
import os
import logging

logger = logging.getLogger(__name__)

error_reasons = [
                "The reason for the VPN connection state change is unknown.",
                "No reason was given for the VPN connection state change.",
                "The VPN connection changed state because the user disconnected it.",
                "The VPN connection changed state because the device it was using was disconnected.",
                "The service providing the VPN connection was stopped.",
                "The IP config of the VPN connection was invalid.",
                "The connection attempt to the VPN service timed out.",
                "A timeout occurred while starting the service providing the VPN connection.",
                "Starting the service starting the service providing the VPN connection failed.",
                "Necessary secrets for the VPN connection were not provided.",
                "Authentication to the VPN server failed.",
                "The connection was deleted from settings." 
                ]

class NMDbus:

    def __init__(self):
        self.conn = None

    def watch(self, callback):

        self.conn = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
        logger.debug(self.conn)

        #(sender, interface_name, member, object_path, arg0, flags, callback, *user_data)
        self.conn.signal_subscribe( "org.freedesktop.NetworkManager",
                           "org.freedesktop.NetworkManager.VPN.Connection",
                           "VpnStateChanged",
                           None,
                           None,
                           Gio.DBusSignalFlags.NONE,
                           self.sub_callback,
                           callback)
    
    def sub_callback(self, connection, sender_name, object_path, interface_name, signal_name, parameters, update_callback):
        logger.debug("{} {}".format(signal_name, parameters))
    
        x = GLib.Variant("(uu)", parameters)
        status = x.get_child_value(0).get_uint32()
        reason = x.get_child_value(1).get_uint32()
    
        """ u state:
            (NMVpnConnectionState) The new state of the VPN connection.

           u reason:
            (NMActiveConnectionStateReason) Reason code describing the change to the new state.

            https://developer.gnome.org/NetworkManager/stable/nm-vpn-dbus-types.html
        """

        if (status == NM.VpnConnectionState.ACTIVATED):
            logger.debug("VPN connected.")
            update_callback(True)   
        elif ((status == NM.VpnConnectionState.DISCONNECTED) or (status == NM.VpnConnectionState.FAILED)):
           logger.debug("VPN disconnected.")
           is_connection_deletion_required = reason in [5, 6, 7, 8 , 9, 10]
           GLib.timeout_add_seconds(1, update_callback, False, (error_reasons[reason] if is_connection_deletion_required else None))
        else:
            update_callback([status, reason])