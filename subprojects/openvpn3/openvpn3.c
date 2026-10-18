#define G_LOG_DOMAIN "eovpn"

#include <stdio.h>
#include <stdbool.h>
#include <gio/gio.h>
#include <glib.h>
#include "openvpn3.h"
#include "enums.h"

GDBusProxy *UniqueSession = NULL;

GDBusProxy *
_get_session_proxy ()
{
    return UniqueSession;
}

GVariantIter *
_get_all_sessions ()
{
    GError *error = NULL;
    GDBusProxy *sessions_proxy = NULL;
    GVariant *available_sessions = NULL;
    int max_tries = 8;

    while (max_tries > 0)
        {
            if (sessions_proxy == NULL)
                {
                    error = NULL;
                    sessions_proxy = g_dbus_proxy_new_for_bus_sync (
                        G_BUS_TYPE_SYSTEM,
                        G_DBUS_PROXY_FLAGS_DO_NOT_LOAD_PROPERTIES,
                        NULL,
                        "net.openvpn.v3.sessions",
                        "/net/openvpn/v3/sessions",
                        "net.openvpn.v3.sessions",
                        NULL,
                        &error);

                    if (error != NULL)
                        {
                            g_warning ("%s:%d -> %s", __FUNCTION__, __LINE__, error->message);
                            g_clear_error (&error);
                            g_clear_object (&sessions_proxy);
                            max_tries--;
                            g_usleep (150000);
                            continue;
                        }
                }

            error = NULL;
            available_sessions = g_dbus_proxy_call_sync (
                sessions_proxy,
                "FetchAvailableSessions",
                g_variant_new ("()"),
                G_DBUS_CALL_FLAGS_NONE,
                -1,
                NULL,
                &error);

            if (error != NULL)
                {
                    g_warning ("%s:%d -> %s", __FUNCTION__, __LINE__, error->message);
                    g_clear_error (&error);
                    g_clear_object (&sessions_proxy);
                    max_tries--;
                    if (max_tries > 0)
                        g_usleep (150000);
                    continue;
                }

            break;
        }

    g_clear_object (&sessions_proxy);

    if (available_sessions == NULL)
        {
            return NULL;
        }

    GVariant *active_sessions = g_variant_get_child_value (available_sessions, 0);
    gsize n_sessions = g_variant_n_children (active_sessions);
    g_debug ("Active Sessions = %lu", (unsigned long) n_sessions);
    GVariantIter *iter = g_variant_iter_new (active_sessions);
    g_variant_unref (active_sessions);
    g_variant_unref (available_sessions);
    return iter;
}

int
get_connection_status ()
{
    GVariantIter *iter = _get_all_sessions ();
    gchar *path = NULL;

    if (iter == NULL)
        {
            return -1;
        }

    gboolean connected = FALSE;

    while (g_variant_iter_next (iter, "o", &path))
        {
            GError *error = NULL;
            GDBusProxy *sessions_proxy = g_dbus_proxy_new_for_bus_sync (
                G_BUS_TYPE_SYSTEM,
                G_DBUS_PROXY_FLAGS_NONE,
                NULL,
                "net.openvpn.v3.sessions",
                path,
                "org.freedesktop.DBus.Properties",
                NULL,
                &error);

            if (error != NULL)
                {
                    g_warning ("%s:%d -> %s", __FUNCTION__, __LINE__, error->message);
                    g_clear_error (&error);
                    g_free (path);
                    continue;
                }

            error = NULL;
            GVariant *status = g_dbus_proxy_call_sync (
                sessions_proxy,
                "Get",
                g_variant_new ("(ss)", "net.openvpn.v3.sessions", "status"),
                G_DBUS_CALL_FLAGS_NONE,
                -1,
                NULL,
                &error);

            g_clear_object (&sessions_proxy);

            if (error != NULL)
                {
                    g_warning ("%s:%d -> %s", __FUNCTION__, __LINE__, error->message);
                    g_clear_error (&error);
                    g_free (path);
                    continue;
                }

            GVariant *v = NULL;
            guint32 major = 0;
            guint32 minor = 0;
            gchar *status_str = NULL;

            g_variant_get (status, "(v)", &v);
            g_variant_get (v, "(uus)", &major, &minor, &status_str);
            g_debug ("%u %u %s", major, minor, status_str);

            if ((major == MAJOR_CONNECTION) &&
                ((minor == MINOR_CONN_CONNECTED) ||
                 (minor == MINOR_CONN_PAUSED)))
                {
                    connected = TRUE;
                }

            g_free (status_str);
            g_variant_unref (v);
            g_variant_unref (status);
            g_free (path);

            if (connected)
                break;
        }

    g_variant_iter_free (iter);
    return connected;
}

void
disconnect_all_sessions ()
{
    GVariantIter *iter = _get_all_sessions ();
    gchar *path = NULL;

    if (iter == NULL)
        {
            g_clear_object (&UniqueSession);
            return;
        }

    while (g_variant_iter_next (iter, "o", &path))
        {
            GError *error = NULL;
            GDBusProxy *sessions_proxy = g_dbus_proxy_new_for_bus_sync (
                G_BUS_TYPE_SYSTEM,
                G_DBUS_PROXY_FLAGS_NONE,
                NULL,
                "net.openvpn.v3.sessions",
                path,
                "org.freedesktop.DBus.Properties",
                NULL,
                &error);

            if (error != NULL)
                {
                    g_warning ("%s:%d -> %s", __FUNCTION__, __LINE__, error->message);
                    g_clear_error (&error);
                    g_free (path);
                    continue;
                }

            error = NULL;
            GVariant *status = g_dbus_proxy_call_sync (
                sessions_proxy,
                "Get",
                g_variant_new ("(ss)", "net.openvpn.v3.sessions", "status"),
                G_DBUS_CALL_FLAGS_NONE,
                -1,
                NULL,
                &error);

            g_clear_object (&sessions_proxy);

            if (error != NULL)
                {
                    g_warning ("%s:%d -> %s", __FUNCTION__, __LINE__, error->message);
                    g_clear_error (&error);
                    g_free (path);
                    continue;
                }

            GVariant *v = NULL;
            guint32 major = 0;
            guint32 minor = 0;
            gchar *status_str = NULL;

            g_variant_get (status, "(v)", &v);
            g_variant_get (v, "(uus)", &major, &minor, &status_str);
            g_debug ("status: %u %u %s", major, minor, status_str);

            if (!(major == MAJOR_CONNECTION &&
                  (minor == MINOR_CONN_DISCONNECTED ||
                   minor == MINOR_CONN_DISCONNECTING ||
                   minor == MINOR_CONN_DONE)))
                {
                    error = NULL;
                    GDBusProxy *proxy = g_dbus_proxy_new_for_bus_sync (
                        G_BUS_TYPE_SYSTEM,
                        G_DBUS_PROXY_FLAGS_NONE,
                        NULL,
                        "net.openvpn.v3.sessions",
                        path,
                        "net.openvpn.v3.sessions",
                        NULL,
                        &error);

                    if (error != NULL)
                        {
                            g_warning ("%s:%d -> %s", __FUNCTION__, __LINE__, error->message);
                            g_clear_error (&error);
                        }
                    else
                        {
                            GVariant *res = g_dbus_proxy_call_sync (
                                proxy,
                                "Disconnect",
                                g_variant_new ("()"),
                                G_DBUS_CALL_FLAGS_NONE,
                                -1,
                                NULL,
                                NULL);
                            if (res != NULL)
                                g_variant_unref (res);
                            g_debug ("%s disconnected!", path);
                            g_clear_object (&proxy);
                        }
                }

            g_free (status_str);
            g_variant_unref (v);
            g_variant_unref (status);
            g_free (path);
        }

    g_variant_iter_free (iter);
    g_clear_object (&UniqueSession);
}

int
get_specific_connection_status (char *session_path)
{
    if (session_path == NULL)
        return false;

    GError *error = NULL;
    GDBusProxy *sessions_proxy =
        g_dbus_proxy_new_for_bus_sync (G_BUS_TYPE_SYSTEM,
                                       G_DBUS_PROXY_FLAGS_NONE,
                                       NULL,
                                       "net.openvpn.v3.sessions",
                                       session_path,
                                       "org.freedesktop.DBus.Properties",
                                       NULL,
                                       &error);
    if (error != NULL)
        {
            g_warning ("%s:%d -> %s", __FUNCTION__, __LINE__, error->message);
            g_clear_error (&error);
            return false;
        }

    error = NULL;
    GVariant *status = g_dbus_proxy_call_sync (
        sessions_proxy,
        "Get",
        g_variant_new ("(ss)", "net.openvpn.v3.sessions", "status"),
        G_DBUS_CALL_FLAGS_NONE,
        -1,
        NULL,
        &error);

    g_clear_object (&sessions_proxy);

    if (error != NULL)
        {
            g_warning ("%s:%d -> %s", __FUNCTION__, __LINE__, error->message);
            g_clear_error (&error);
            return false;
        }

    if (status == NULL)
        return false;

    GVariant *v = NULL;
    guint32 major = 0;
    guint32 minor = 0;
    gchar *status_str = NULL;
    gboolean is_connected = FALSE;

    g_variant_get (status, "(v)", &v);
    g_variant_get (v, "(uus)", &major, &minor, &status_str);

    if ((major == MAJOR_CONNECTION) && (minor == MINOR_CONN_CONNECTED))
        {
            is_connected = TRUE;
        }

    g_free (status_str);
    g_variant_unref (v);
    g_variant_unref (status);

    return is_connected;
}

char *
get_version ()
{
    static char version_buffer[128];
    GError *error = NULL;
    GDBusProxy *proxy =
        g_dbus_proxy_new_for_bus_sync (G_BUS_TYPE_SYSTEM,
                                       G_DBUS_PROXY_FLAGS_DO_NOT_LOAD_PROPERTIES,
                                       NULL,
                                       "net.openvpn.v3.configuration",
                                       "/net/openvpn/v3/configuration",
                                       "org.freedesktop.DBus.Properties",
                                       NULL,
                                       &error);

    if (error != NULL)
        {
            g_warning ("%s:%d -> %s", __FUNCTION__, __LINE__, error->message);
            g_clear_error (&error);
            return NULL;
        }

    error = NULL;
    GVariant *version = g_dbus_proxy_call_sync (
        proxy,
        "Get",
        g_variant_new ("(ss)", "net.openvpn.v3.configuration", "version"),
        G_DBUS_CALL_FLAGS_NONE,
        -1,
        NULL,
        &error);

    g_clear_object (&proxy);

    if (error != NULL)
        {
            g_warning ("%s:%d -> %s", __FUNCTION__, __LINE__, error->message);
            g_clear_error (&error);
            return NULL;
        }

    if (version == NULL)
        return NULL;

    GVariant *version_v = NULL;
    const gchar *version_str = NULL;
    g_variant_get (version, "(v)", &version_v);
    g_variant_get (version_v, "&s", &version_str);
    g_strlcpy (version_buffer, version_str, sizeof (version_buffer));
    g_variant_unref (version_v);
    g_variant_unref (version);

    return version_buffer;
}

char *
import_config (char *name, char *config_str)
{
    static char config_path_buffer[512];
    GError *error = NULL;
    GDBusProxy *import_proxy = NULL;
    GVariant *result = NULL;
    int max_tries = 8;

    while (max_tries > 0)
        {
            if (import_proxy == NULL)
                {
                    error = NULL;
                    import_proxy = g_dbus_proxy_new_for_bus_sync (
                        G_BUS_TYPE_SYSTEM,
                        G_DBUS_PROXY_FLAGS_DO_NOT_LOAD_PROPERTIES,
                        NULL,
                        "net.openvpn.v3.configuration",
                        "/net/openvpn/v3/configuration",
                        "net.openvpn.v3.configuration",
                        NULL,
                        &error);

                    if (error != NULL)
                        {
                            g_warning ("%s:%d -> %s", __FUNCTION__, __LINE__, error->message);
                            g_clear_error (&error);
                            g_clear_object (&import_proxy);
                            max_tries--;
                            g_usleep (150000);
                            continue;
                        }
                }

            GVariant *params = g_variant_new ("(ssbb)", name, config_str, TRUE, FALSE);

            error = NULL;
            result = g_dbus_proxy_call_sync (
                import_proxy,
                "Import",
                params,
                G_DBUS_CALL_FLAGS_NONE,
                -1,
                NULL,
                &error);

            if (error != NULL)
                {
                    g_warning ("%s:%d -> %s", __FUNCTION__, __LINE__, error->message);
                    g_clear_error (&error);
                    g_clear_object (&import_proxy);
                    max_tries--;
                    if (max_tries > 0)
                        g_usleep (150000);
                    continue;
                }

            break;
        }

    g_clear_object (&import_proxy);

    if (result == NULL)
        {
            return NULL;
        }

    g_info ("Result: %s", g_variant_get_type_string (result));

    const gchar *config_object = NULL;
    g_variant_get (result, "(&o)", &config_object);
    g_info ("%s", config_object);
    g_strlcpy (config_path_buffer, config_object, sizeof (config_path_buffer));
    g_variant_unref (result);

    return config_path_buffer;
}

void
init_unique_session (char *session_object)
{
    if (session_object == NULL)
        return;

    GError *error = NULL;
    GDBusProxy *unique_session =
        g_dbus_proxy_new_for_bus_sync (G_BUS_TYPE_SYSTEM,
                                       G_DBUS_PROXY_FLAGS_NONE,
                                       NULL,
                                       "net.openvpn.v3.sessions",
                                       (gchar *) session_object,
                                       "net.openvpn.v3.sessions",
                                       NULL,
                                       &error);

    if (error != NULL)
        {
            g_warning ("%s:%d -> %s", __FUNCTION__, __LINE__, error->message);
            g_clear_error (&error);
            return;
        }

    if (UniqueSession != NULL)
        {
            g_object_unref (UniqueSession);
        }
    UniqueSession = unique_session;
}

char *
prepare_tunnel (char *config_object)
{
    static char session_path_buffer[512];
    GError *error = NULL;
    GDBusProxy *sessions_proxy = NULL;
    GVariant *result = NULL;
    int max_tries = 8;

    while (max_tries > 0)
        {
            if (sessions_proxy == NULL)
                {
                    error = NULL;
                    sessions_proxy = g_dbus_proxy_new_for_bus_sync (
                        G_BUS_TYPE_SYSTEM,
                        G_DBUS_PROXY_FLAGS_DO_NOT_LOAD_PROPERTIES,
                        NULL,
                        "net.openvpn.v3.sessions",
                        "/net/openvpn/v3/sessions",
                        "net.openvpn.v3.sessions",
                        NULL,
                        &error);

                    if (error != NULL)
                        {
                            g_warning ("%s:%d -> %s", __FUNCTION__, __LINE__, error->message);
                            g_clear_error (&error);
                            g_clear_object (&sessions_proxy);
                            max_tries--;
                            g_usleep (150000);
                            continue;
                        }
                }

            error = NULL;
            GVariant *params = g_variant_new ("(o)", (gchar *) config_object);
            result = g_dbus_proxy_call_sync (
                sessions_proxy,
                "NewTunnel",
                params,
                G_DBUS_CALL_FLAGS_NONE,
                -1,
                NULL,
                &error);

            if (error != NULL)
                {
                    g_warning ("%s:%d -> %s", __FUNCTION__, __LINE__, error->message);
                    g_clear_error (&error);
                    g_clear_object (&sessions_proxy);
                    max_tries--;
                    if (max_tries > 0)
                        g_usleep (150000);
                    continue;
                }

            break;
        }

    g_clear_object (&sessions_proxy);

    if (result == NULL)
        {
            return NULL;
        }

    g_info ("Result: %s", g_variant_get_type_string (result));

    const gchar *session_object = NULL;
    g_variant_get (result, "(&o)", &session_object);
    g_info ("%s", session_object);
    g_strlcpy (session_path_buffer, session_object, sizeof (session_path_buffer));
    g_variant_unref (result);

    init_unique_session (session_path_buffer);

    return session_path_buffer;
}

void
set_dco (char *session_object, int state)
{
    GError *error = NULL;
    GDBusProxy *sessions_proxy =
        g_dbus_proxy_new_for_bus_sync (G_BUS_TYPE_SYSTEM,
                                       G_DBUS_PROXY_FLAGS_NONE,
                                       NULL,
                                       "net.openvpn.v3.sessions",
                                       (gchar *) session_object,
                                       "org.freedesktop.DBus.Properties",
                                       NULL,
                                       &error);
    if (error != NULL)
        {
            g_warning ("%s:%d -> %s", __FUNCTION__, __LINE__, error->message);
            g_clear_error (&error);
            return;
        }

    GVariant *params = g_variant_new (
        "(ssv)", "net.openvpn.v3.sessions", "dco", g_variant_new ("b", state));

    error = NULL;
    GVariant *res = g_dbus_proxy_call_sync (
        sessions_proxy, "Set", params, G_DBUS_CALL_FLAGS_NONE, -1, NULL, &error);
    if (error != NULL)
        {
            g_warning ("%s:%d -> %s", __FUNCTION__, __LINE__, error->message);
            g_clear_error (&error);
        }
    if (res != NULL)
        g_variant_unref (res);

    g_clear_object (&sessions_proxy);
}

void
set_receive_log_events (char *session_object, int set_to)
{
    GError *error = NULL;
    GDBusProxy *sessions_proxy =
        g_dbus_proxy_new_for_bus_sync (G_BUS_TYPE_SYSTEM,
                                       G_DBUS_PROXY_FLAGS_NONE,
                                       NULL,
                                       "net.openvpn.v3.sessions",
                                       (gchar *) session_object,
                                       "org.freedesktop.DBus.Properties",
                                       NULL,
                                       &error);
    if (error != NULL)
        {
            g_warning ("%s:%d -> %s", __FUNCTION__, __LINE__, error->message);
            g_clear_error (&error);
            return;
        }

    GVariant *params = g_variant_new ("(ssv)",
                                      "net.openvpn.v3.sessions",
                                      "receive_log_events",
                                      g_variant_new ("b", set_to));

    error = NULL;
    GVariant *res = g_dbus_proxy_call_sync (
        sessions_proxy, "Set", params, G_DBUS_CALL_FLAGS_NONE, -1, NULL, &error);
    if (error != NULL)
        {
            g_warning ("%s:%d -> %s", __FUNCTION__, __LINE__, error->message);
            g_clear_error (&error);
        }
    if (res != NULL)
        g_variant_unref (res);

    g_clear_object (&sessions_proxy);
}

void
set_log_forward ()
{
    if (UniqueSession == NULL)
        {
            g_warning ("%s: UniqueSession is NULL", __FUNCTION__);
            return;
        }

    GError *error = NULL;
    GVariant *res = g_dbus_proxy_call_sync (UniqueSession,
                            "LogForward",
                            g_variant_new ("(b)", true),
                            G_DBUS_CALL_FLAGS_NONE,
                            -1,
                            NULL,
                            &error);

    if (error != NULL)
        {
            g_warning ("%s:%d -> %s", __FUNCTION__, __LINE__, error->message);
            g_clear_error (&error);
            return;
        }

    if (res != NULL)
        g_variant_unref (res);
}

char *
is_ready_to_connect ()
{
    static char error_msg_buffer[512];
    if (UniqueSession == NULL)
        {
            g_warning ("%s: UniqueSession is NULL", __FUNCTION__);
            g_strlcpy (error_msg_buffer, "Session not initialized", sizeof (error_msg_buffer));
            return error_msg_buffer;
        }

    GError *error = NULL;
    GVariant *res = g_dbus_proxy_call_sync (UniqueSession,
                            "Ready",
                            g_variant_new ("()"),
                            G_DBUS_CALL_FLAGS_NONE,
                            -1,
                            NULL,
                            &error);

    if (error != NULL)
        {
            g_warning ("%s:%d -> %s", __FUNCTION__, __LINE__, error->message);
            g_strlcpy (error_msg_buffer, error->message, sizeof (error_msg_buffer));
            g_clear_error (&error);
            return error_msg_buffer;
        }

    if (res != NULL)
        g_variant_unref (res);

    return NULL;
}

void
send_auth (char *session_object, int type, int group, int id, char *value)
{
    if (UniqueSession == NULL ||
        g_strcmp0 (g_dbus_proxy_get_object_path (UniqueSession), session_object) != 0)
        {
            init_unique_session (session_object);
            if (UniqueSession == NULL)
                return;
        }

    GVariant *params = g_variant_new ("(uuus)", type, group, id, value);
    GError *error = NULL;
    GVariant *res = g_dbus_proxy_call_sync (UniqueSession,
                            "UserInputProvide",
                            params,
                            G_DBUS_CALL_FLAGS_NONE,
                            -1,
                            NULL,
                            &error);

    if (error != NULL)
        {
            g_warning ("%s:%d -> %s", __FUNCTION__, __LINE__, error->message);
            g_clear_error (&error);
            return;
        }

    if (res != NULL)
        g_variant_unref (res);
}

void
connect_vpn ()
{
    if (UniqueSession == NULL)
        {
            g_warning ("%s: UniqueSession is NULL", __FUNCTION__);
            return;
        }

    GError *error = NULL;
    GVariant *res = g_dbus_proxy_call_sync (UniqueSession,
                            "Connect",
                            g_variant_new ("()"),
                            G_DBUS_CALL_FLAGS_NONE,
                            -1,
                            NULL,
                            &error);
    if (error != NULL)
        {
            g_warning ("%s:%d -> %s", __FUNCTION__, __LINE__, error->message);
            g_clear_error (&error);
        }
    if (res != NULL)
        g_variant_unref (res);
}

void
disconnect_vpn ()
{
    if (UniqueSession != NULL)
        {
            GError *error = NULL;
            GVariant *res = g_dbus_proxy_call_sync (UniqueSession,
                                                    "Disconnect",
                                                    g_variant_new ("()"),
                                                    G_DBUS_CALL_FLAGS_NONE,
                                                    -1,
                                                    NULL,
                                                    &error);
            if (error != NULL)
                {
                    g_warning ("%s:%d -> %s", __FUNCTION__, __LINE__, error->message);
                    g_clear_error (&error);
                    disconnect_all_sessions ();
                }
            if (res != NULL)
                g_variant_unref (res);

            g_clear_object (&UniqueSession);
        }
    else
        {
            disconnect_all_sessions ();
        }
}

void
pause_vpn (char *reason)
{
    if (UniqueSession == NULL)
        {
            g_warning ("%s: UniqueSession is NULL", __FUNCTION__);
            return;
        }

    GError *error = NULL;
    GVariant *res = g_dbus_proxy_call_sync (UniqueSession,
                            "Pause",
                            g_variant_new ("(s)", reason),
                            G_DBUS_CALL_FLAGS_NONE,
                            -1,
                            NULL,
                            &error);
    if (error != NULL)
        {
            g_warning ("%s:%d -> %s", __FUNCTION__, __LINE__, error->message);
            g_clear_error (&error);
        }
    if (res != NULL)
        g_variant_unref (res);
}

void
resume_vpn ()
{
    if (UniqueSession == NULL)
        {
            g_warning ("%s: UniqueSession is NULL", __FUNCTION__);
            return;
        }

    GError *error = NULL;
    GVariant *res = g_dbus_proxy_call_sync (UniqueSession,
                            "Resume",
                            g_variant_new ("()"),
                            G_DBUS_CALL_FLAGS_NONE,
                            -1,
                            NULL,
                            &error);
    if (error != NULL)
        {
            g_warning ("%s:%d -> %s", __FUNCTION__, __LINE__, error->message);
            g_clear_error (&error);
        }
    if (res != NULL)
        g_variant_unref (res);
}

/* Ducttape code until dbus issue fixes upstream!
   Refer: https://github.com/OpenVPN/openvpn3-linux/issues/100

   _p = p stands for persistence.
*/

char *
p_get_version ()
{
    int max_tries = 6;

    while (max_tries > 0)
        {
            char *ver = get_version ();
            if (ver != NULL)
                {
                    return ver;
                }
            max_tries--;
            if (max_tries > 0)
                g_usleep (150000);
        }

    return NULL;
}

int
p_get_connection_status ()
{
    int max_tries = 6;

    while (max_tries > 0)
        {
            int status = get_connection_status ();
            if (status != -1)
                {
                    char *version = get_version ();
                    if (version != NULL)
                        g_debug ("OpenVPN3 version = %s", version);
                    return status;
                }
            max_tries--;
            if (max_tries > 0)
                g_usleep (150000);
        }

    return false;
}