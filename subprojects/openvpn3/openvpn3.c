#include <stdio.h>
#include <stdbool.h>
#include <gio/gio.h>
#include <glib.h>

GDBusProxy *UniqueSession = NULL;

GDBusProxy *_get_session_proxy()
{
    return UniqueSession;
}

GVariantIter *_get_all_sessions()
{

    GError *error = NULL;
    GDBusProxy *sessions_proxy = g_dbus_proxy_new_for_bus_sync(G_BUS_TYPE_SYSTEM,
                                                               G_DBUS_PROXY_FLAGS_NONE,
                                                               NULL,
                                                               "net.openvpn.v3.sessions",
                                                               "/net/openvpn/v3/sessions",
                                                               "net.openvpn.v3.sessions",
                                                               NULL,
                                                               &error);

    if (error != NULL)
    {
        g_warning("%s:%d -> %s", __FUNCTION__, __LINE__, error->message);
        g_error_free(error);
        return NULL;
    }
    
    error = NULL;
    GVariant *available_sessions = g_dbus_proxy_call_sync(sessions_proxy, "FetchAvailableSessions", g_variant_new("()"), G_DBUS_CALL_FLAGS_NONE, -1, NULL, &error);
    if (error != NULL){
        g_warning("%s:%d -> %s", __FUNCTION__, __LINE__, error->message);
        g_error_free(error);
        return NULL;
    }
    
    GVariant *active_sessions = g_variant_get_child_value(available_sessions, 0);
    gsize n_sessions = g_variant_n_children(active_sessions);
    g_message("Active Sessions  = %ld", n_sessions);
    GVariantIter *iter = g_variant_iter_new(active_sessions);
    return iter;
}

int get_connection_status()
{
    GVariantIter *iter = _get_all_sessions();
    gchar *path;

    if(iter == NULL){
        return -1;
    }

    while (g_variant_iter_next(iter, "o", &path))
    {

        GError *error = NULL;
        GDBusProxy *sessions_proxy = g_dbus_proxy_new_for_bus_sync(G_BUS_TYPE_SYSTEM,
                                                                   G_DBUS_PROXY_FLAGS_NONE,
                                                                   NULL,
                                                                   "net.openvpn.v3.sessions",
                                                                   path,
                                                                   "org.freedesktop.DBus.Properties",
                                                                   NULL,
                                                                   &error);
        if (error != NULL)
        {

            g_warning("%s:%d -> %s", __FUNCTION__, __LINE__, error->message);
            g_error_free(error);
            return -1;
        }
        
        error = NULL;
        GVariant *status = g_dbus_proxy_call_sync(sessions_proxy, "Get", g_variant_new("(ss)", "net.openvpn.v3.sessions", "status"), G_DBUS_CALL_FLAGS_NONE, -1, NULL, &error);

        if (error != NULL){
            g_warning("%s:%d -> %s", __FUNCTION__, __LINE__, error->message);
            g_error_free(error);
            return -1;
        }

        GVariant *v;
        guint16 major;
        guint16 minor;
        gchar *status_str;

        g_variant_get(status, "(v)", &v);
        g_variant_get(v, "(uus)", &major, &minor, &status_str);
        g_message("%u %u %s", major, minor, status_str);

        if ((major == 2) && (minor == 7))
        {
            g_variant_iter_free(iter);
            return true;
        }
    }
    
    g_variant_iter_free(iter);
    return false;
}

void disconnect_all_sessions()
{

    GVariantIter *iter = _get_all_sessions();
    gchar *path;

    if (iter == NULL)
    {
        return;
    }

    while (g_variant_iter_next(iter, "o", &path))
    {

        GError *error = NULL;
        GDBusProxy *sessions_proxy = g_dbus_proxy_new_for_bus_sync(G_BUS_TYPE_SYSTEM,
                                                                   G_DBUS_PROXY_FLAGS_NONE,
                                                                   NULL,
                                                                   "net.openvpn.v3.sessions",
                                                                   path,
                                                                   "org.freedesktop.DBus.Properties",
                                                                   NULL,
                                                                   &error);
        if (error != NULL)
        {

            g_warning("%s:%d -> %s", __FUNCTION__, __LINE__, error->message);
            g_error_free(error);
            continue;
        }

        GVariant *status = g_dbus_proxy_call_sync(sessions_proxy, "Get", g_variant_new("(ss)", "net.openvpn.v3.sessions", "status"), G_DBUS_CALL_FLAGS_NONE, -1, NULL, NULL);
        
        GVariant *v;
        guint16 major;
        guint16 minor;
        gchar *status_str;
        gchar *p_copy = path;

        g_variant_get(status, "(v)", &v);
        g_variant_get(v, "(uus)", &major, &minor, &status_str);
        g_message("status: %u %u %s", major, minor, status_str);


        if (((major == 2) && (minor == 7)) || ((major == 2) && (minor == 14)))
        {
            error = NULL;
            GDBusProxy *proxy = g_dbus_proxy_new_for_bus_sync(G_BUS_TYPE_SYSTEM,
                                                              G_DBUS_PROXY_FLAGS_NONE,
                                                              NULL,
                                                              "net.openvpn.v3.sessions",
                                                              p_copy,
                                                              "net.openvpn.v3.sessions",
                                                              NULL,
                                                              &error);

            g_dbus_proxy_call_sync(proxy, "Disconnect", g_variant_new("()"), G_DBUS_PROXY_FLAGS_NONE, -1, NULL, NULL);
            g_message("%s disconnected!", p_copy);
        }
    }

    g_variant_iter_free(iter);
}

int get_specific_connection_status(char *session_path)
{
    GError *error = NULL;
    GDBusProxy *sessions_proxy = g_dbus_proxy_new_for_bus_sync(G_BUS_TYPE_SYSTEM,
                                                               G_DBUS_PROXY_FLAGS_NONE,
                                                               NULL,
                                                               "net.openvpn.v3.sessions",
                                                               session_path,
                                                               "org.freedesktop.DBus.Properties",
                                                               NULL,
                                                               &error);
    if (error != NULL)
    {

        g_warning("%s:%d -> %s", __FUNCTION__, __LINE__, error->message);
        g_error_free(error);
        return false;
    }

    GVariant *status = g_dbus_proxy_call_sync(sessions_proxy, "Get", g_variant_new("(ss)", "net.openvpn.v3.sessions", "status"), G_DBUS_CALL_FLAGS_NONE, -1, NULL, NULL);
    guint16 major;
    guint16 minor;
    gchar *status_str;

    g_variant_get(status, "(uus)", &major, &minor, &status_str);

    if ((major == 2) && (minor == 2))
    {
        return true;
    }

    return false;
}

char *get_version()
{

    GError *error = NULL;
    GDBusProxy *proxy = g_dbus_proxy_new_for_bus_sync(G_BUS_TYPE_SYSTEM,
                                                      G_DBUS_PROXY_FLAGS_NONE,
                                                      NULL,
                                                      "net.openvpn.v3.configuration",
                                                      "/net/openvpn/v3/configuration",
                                                      "org.freedesktop.DBus.Properties",
                                                      NULL,
                                                      &error);

    if (error != NULL)
    {
        g_warning("%s:%d -> %s", __FUNCTION__, __LINE__, error->message);
        g_error_free(error);
        return NULL;
    }

    error = NULL;
    GVariant *version = g_dbus_proxy_call_sync(proxy, "Get", g_variant_new("(ss)", "net.openvpn.v3.configuration", "version"), G_DBUS_PROXY_FLAGS_NONE,
                                               -1,
                                               NULL, &error);
    if (error != NULL)
    {
        g_warning("%s:%d -> %s", __FUNCTION__, __LINE__, error->message);
        g_error_free(error);
        return NULL;
    }

    GVariant *version_v;
    const gchar *version_str;
    g_variant_get(version, "(v)", &version_v);
    g_variant_get(version_v, "s", &version_str);
    return (char *)version_str;
}

char *import_config(char *name, char *config_str)
{

    GError *error = NULL;
    GDBusProxy *import_proxy = g_dbus_proxy_new_for_bus_sync(G_BUS_TYPE_SYSTEM,
                                                             G_DBUS_PROXY_FLAGS_NONE,
                                                             NULL,
                                                             "net.openvpn.v3.configuration",
                                                             "/net/openvpn/v3/configuration",
                                                             "net.openvpn.v3.configuration",
                                                             NULL,
                                                             &error);

    if (error != NULL)
    {
        g_warning("%s:%d -> %s", __FUNCTION__, __LINE__, error->message);
        g_error_free(error);
        return NULL;
    }

    GVariant *params = g_variant_new("(ssbb)", name, config_str, TRUE, FALSE);

    error = NULL;
    GVariant *result = g_dbus_proxy_call_sync(import_proxy,
                                              "net.openvpn.v3.configuration.Import",
                                              params,
                                              G_DBUS_PROXY_FLAGS_NONE,
                                              -1,
                                              NULL,
                                              &error);

    if (error != NULL)
    {
        g_warning("%s:%d -> %s", __FUNCTION__, __LINE__, error->message);
        g_error_free(error);
        return NULL;
    }

    g_info("Result: %s", g_variant_get_type_string(result));

    const gchar *config_object;
    g_variant_get(result, "(o)", &config_object);
    g_info("%s", config_object);

    return (char *)config_object;
}

char *prepare_tunnel(char *config_object)
{

    GError *error = NULL;
    GDBusProxy *sessions_proxy = g_dbus_proxy_new_for_bus_sync(G_BUS_TYPE_SYSTEM,
                                                               G_DBUS_PROXY_FLAGS_NONE,
                                                               NULL,
                                                               "net.openvpn.v3.sessions",
                                                               "/net/openvpn/v3/sessions",
                                                               "net.openvpn.v3.sessions",
                                                               NULL,
                                                               &error);

    if (error != NULL)
    {
        g_warning("%s:%d -> %s", __FUNCTION__, __LINE__, error->message);
        g_error_free(error);
        return NULL;
    }

    GVariant *params = g_variant_new("(o)", (gchar *)config_object);

    error = NULL;
    GVariant *result = g_dbus_proxy_call_sync(sessions_proxy,
                                              "net.openvpn.v3.sessions.NewTunnel",
                                              params,
                                              G_DBUS_PROXY_FLAGS_NONE,
                                              -1,
                                              NULL,
                                              &error);

    if (error != NULL)
    {
        g_warning("%s:%d -> %s", __FUNCTION__, __LINE__, error->message);
        g_error_free(error);
        return NULL;
    }

    g_info("Result: %s", g_variant_get_type_string(result));

    const gchar *session_object;
    g_variant_get(result, "(o)", &session_object);
    g_info("%s", session_object);

    return (char *)session_object;
}

void init_unique_session(char *session_object){

    GError *error = NULL;
    GDBusProxy *unique_session = g_dbus_proxy_new_for_bus_sync(
        G_BUS_TYPE_SYSTEM,
        G_DBUS_PROXY_FLAGS_NONE,
        NULL,
        "net.openvpn.v3.sessions",
        (gchar *)session_object,
        "net.openvpn.v3.sessions",
        NULL,
        &error);

    if (error != NULL)
    {
        g_warning("%s:%d -> %s", __FUNCTION__, __LINE__, error->message);
        g_error_free(error);
        return;
    }

    UniqueSession = unique_session;
    
}

void set_dco(char *session_object, int set_to)
{

    GError *error = NULL;
    GVariant *params = g_variant_new("(ssv)", "net.openvpn.v3.sessions", "dco", g_variant_new("b", set_to));

    GDBusProxy *sessions_proxy = g_dbus_proxy_new_for_bus_sync(G_BUS_TYPE_SYSTEM,
                                                               G_DBUS_PROXY_FLAGS_NONE,
                                                               NULL,
                                                               "net.openvpn.v3.sessions",
                                                               (gchar *)session_object,
                                                               "org.freedesktop.DBus.Properties",
                                                               NULL,
                                                               &error);
    if (error != NULL)
    {

        g_warning("%s:%d -> %s", __FUNCTION__, __LINE__, error->message);
        g_error_free(error);
        return;
    }

    g_dbus_proxy_call_sync(sessions_proxy, "Set", params, G_DBUS_PROXY_FLAGS_NONE, -1, NULL, NULL);
}

void set_receive_log_events(char *session_object, int set_to)
{

    GError *error = NULL;
    GVariant *params = g_variant_new("(ssv)", "net.openvpn.v3.sessions", "receive_log_events", g_variant_new("b", set_to));

    GDBusProxy *sessions_proxy = g_dbus_proxy_new_for_bus_sync(G_BUS_TYPE_SYSTEM,
                                                               G_DBUS_PROXY_FLAGS_NONE,
                                                               NULL,
                                                               "net.openvpn.v3.sessions",
                                                               (gchar *)session_object,
                                                               "org.freedesktop.DBus.Properties",
                                                               NULL,
                                                               &error);
    if (error != NULL)
    {

        g_warning("%s:%d -> %s", __FUNCTION__, __LINE__, error->message);
        g_error_free(error);
        return;
    }

    g_dbus_proxy_call_sync(sessions_proxy, "Set", params, G_DBUS_PROXY_FLAGS_NONE, -1, NULL, NULL);
}

void set_log_forward(){

    g_assert(UniqueSession != NULL);

    GError *error = NULL;
    g_dbus_proxy_call_sync( UniqueSession,
                            "net.openvpn.v3.sessions.LogForward",
                            g_variant_new("(b)", true),
                            G_DBUS_PROXY_FLAGS_NONE,
                            -1,
                            NULL,
                            &error );
    
    if (error != NULL)
    {
        g_warning("%s:%d -> %s", __FUNCTION__, __LINE__, error->message);
        g_error_free(error);
        return;
    }

}

char* is_ready_to_connect(){

    g_assert(UniqueSession != NULL);

    GError *error = NULL;
    g_dbus_proxy_call_sync( UniqueSession,
                            "net.openvpn.v3.sessions.Ready",
                            NULL,
                            G_DBUS_PROXY_FLAGS_NONE,
                            -1,
                            NULL,
                            &error );
    
    if (error != NULL)
    {
        g_warning("%s:%d -> %s", __FUNCTION__, __LINE__, error->message);
        char* error_msg = error->message;
        g_error_free(error);
        return error_msg;
    }

    return NULL;

}

void send_auth(char *session_object, char *username, char *password)
{

    GError *error = NULL;
    GDBusProxy *unique_session = g_dbus_proxy_new_for_bus_sync(
        G_BUS_TYPE_SYSTEM,
        G_DBUS_PROXY_FLAGS_NONE,
        NULL,
        "net.openvpn.v3.sessions",
        (gchar *)session_object,
        "net.openvpn.v3.sessions",
        NULL,
        &error);

    if (error != NULL)
    {
        g_warning("%s:%d -> %s", __FUNCTION__, __LINE__, error->message);
        g_error_free(error);
        return;
    }

    UniqueSession = unique_session;

    GVariant *params_for_username = g_variant_new("(uuus)", 1, 1, 0, username);
    GVariant *params_for_password = g_variant_new("(uuus)", 1, 1, 1, password);

    g_dbus_proxy_call_sync(UniqueSession, "UserInputProvide", params_for_username, G_DBUS_PROXY_FLAGS_NONE, -1, NULL, NULL);
    g_dbus_proxy_call_sync(UniqueSession, "UserInputProvide", params_for_password, G_DBUS_PROXY_FLAGS_NONE, -1, NULL, NULL);
}

void connect_vpn()
{
    g_assert(UniqueSession != NULL);
    g_dbus_proxy_call_sync(UniqueSession, "Connect", g_variant_new("()"), G_DBUS_PROXY_FLAGS_NONE, -1, NULL, NULL);
}

void disconnect_vpn()
{
    g_assert(UniqueSession != NULL);
    g_dbus_proxy_call_sync(UniqueSession, "Disconnect", g_variant_new("()"), G_DBUS_PROXY_FLAGS_NONE, -1, NULL, NULL);
    UniqueSession = NULL;
}

void pause_vpn(char *reason)
{
    g_assert(UniqueSession != NULL);
    g_dbus_proxy_call_sync(UniqueSession, "Pause", g_variant_new("(s)", reason), G_DBUS_PROXY_FLAGS_NONE, -1, NULL, NULL);
}

void resume_vpn()
{
    g_assert(UniqueSession != NULL);
    g_dbus_proxy_call_sync(UniqueSession, "Resume", g_variant_new("()"), G_DBUS_PROXY_FLAGS_NONE, -1, NULL, NULL);
}

/* Ducttape code until dbus issue fixes upstream!
   Refer: https://github.com/OpenVPN/openvpn3-linux/issues/100

   _p = p stands for persistence.
*/

char* p_get_version(){

    int max_tries = 6;

    while(max_tries != 0){
        char* ver = get_version();
        if (ver != NULL){
            return ver;
        }
        else{
            max_tries--;
        }
    }

    return NULL;
}

int p_get_connection_status(){

    int max_tries = 6;

    while(max_tries != 0){
        int status = get_connection_status();
        if (status != -1){
            return status;
        }
        else{
            max_tries--;
        }
    }

    return -1;
}