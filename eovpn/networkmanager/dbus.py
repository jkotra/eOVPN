import gi
from gi.repository import GLib, Gio
import logging

logger = logging.getLogger(__name__)


def callback(connection, sender_name, object_path, interface_name, signal_name, parameters, update_callback):
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

    if (status == 5 and reason == 1):
        logger.debug("VPN connected.")
        update_callback(True)   
    elif (status == 7 and reason == 2):
        logger.debug("VPN disconnected.")
        GLib.timeout_add_seconds(1, update_callback, False)
    else:
        pass    


def watch_vpn_status(update_callback):

    conn = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
    logger.debug(conn)

#(sender, interface_name, member, object_path, arg0, flags, callback, *user_data)
    conn.signal_subscribe( "org.freedesktop.NetworkManager",
                           "org.freedesktop.NetworkManager.VPN.Connection",
                           "VpnStateChanged",
                           None,
                           None,
                           Gio.DBusSignalFlags.NONE,
                           callback,
                           update_callback)