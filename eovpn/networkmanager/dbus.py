import gi
from gi.repository import GLib, Gio
import logging

logger = logging.getLogger(__name__)


def callback(connection, sender_name, object_path, interface_name, signal_name, parameters, update_callback):
    logger.debug("{} {}".format(signal_name, parameters))
    
    x = GLib.Variant("(uu)", parameters)
    status = x.get_child_value(0).get_uint32()
    reason = x.get_child_value(1).get_uint32()

    if (status == 5):
        logger.debug("calling callback update fn")
        update_callback()    
    elif (status == 7):
        GLib.timeout_add_seconds(1, update_callback)


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