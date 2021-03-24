#include <stdbool.h>
#include <stdlib.h>
#include <glib.h>
#include <NetworkManager.h>

/*
* gcc -shared -o eovpn_nm.so -fPIC eovpn_nm.c `pkg-config --libs --cflags libnm`
* [DEBUGGING]: gcc eovpn_nm.c `pkg-config --libs --cflags libnm`
*/

static void
add_cb(NMClient *client, GAsyncResult *result, GMainLoop *loop)
{
    GError *err = NULL;
    nm_client_add_connection_finish(client, result, &err);
    if (err != NULL)
    {
        /* https://developer.gnome.org/glib/stable/glib-Warnings-and-Assertions.html#g-printerr */
        g_printerr("Error: %s\n", err->message);
    }
    else
    {
        g_message("[NM] Connection Added!");
    }

    g_main_loop_quit(loop);
}

char *
add_connection(char *config_name, char *username, char *password, char *ca, int debug)
{

    GMainLoop *loop = g_main_loop_new(NULL, false);

    GSList *plugins = nm_vpn_plugin_info_list_load();
    NMVpnPluginInfo *plugin;
    GError *err = NULL;

    while (plugins != NULL)
    {
        plugin = plugins->data;
        const char *name = nm_vpn_plugin_info_get_name(plugin);
        if (debug) { g_print("%s\n", name); }

        if (strcmp("openvpn", name) == 0)
        {
            break;
        }

        plugins = plugins->next;
    }

    NMVpnEditorPlugin *editor = nm_vpn_plugin_info_load_editor_plugin(plugin, &err);
    if (err != NULL)
    {
        g_printerr(err->message);
        g_error_free(err);
        err = NULL;
    }

    NMConnection *conn = nm_vpn_editor_plugin_import(editor, config_name, &err);
    if (err != NULL)
    {
        g_printerr(err->message);
        g_error_free(err);
        err = NULL;
    }

    NMSettingVpn *vpn_settings = nm_connection_get_setting_vpn(conn);
    g_assert(vpn_settings != NULL);

    if (username != NULL)
    {
        nm_setting_vpn_add_data_item(vpn_settings, "username", username);
    }
    if (password != NULL)
    {
        nm_setting_vpn_add_secret(vpn_settings, "password", password);
    }
    if (ca != NULL)
    {
        nm_setting_vpn_add_data_item(vpn_settings, "ca", ca);
    }

    g_assert(conn != NULL);
    nm_connection_normalize(conn, NULL, NULL, NULL);

    if (debug){ nm_connection_dump(conn); }

    NMClient *client = nm_client_new(NULL, NULL);

    nm_client_add_connection_async(client, conn, TRUE, NULL, (GAsyncReadyCallback)add_cb, loop);
    g_main_loop_run(loop);

    return (char*)nm_connection_get_uuid(conn);
}

static void activate_cb(NMClient *client, GAsyncResult *result, GMainLoop *loop)
{
    
    GError *err = NULL;
    nm_client_activate_connection_finish(client, result, &err);
    if (err != NULL){
        g_printerr("Error: %s\n", err->message);
    }
    else{
        g_message("[NM] Connection Connected!");
    }

    g_main_loop_quit(loop);
}

int activate_connection(char *uuid)
{

    GMainLoop *loop = g_main_loop_new(NULL, FALSE);

    NMClient *client = nm_client_new(NULL, NULL);
    const GPtrArray *arr = nm_client_get_connections(client);
    NMConnection *target = NULL;

    for (size_t i = 0; i < arr->len; i++)
    {
        const char *current_uuid = nm_connection_get_uuid(NM_CONNECTION(arr->pdata[i]));
        if (strcmp(uuid, current_uuid) == 0)
        {
            target = NM_CONNECTION(arr->pdata[i]);
            break;
        }
    }

    g_assert(target != NULL);

    nm_client_activate_connection_async(client, target, NULL, NULL, NULL, (GAsyncReadyCallback)activate_cb, loop);
    g_main_loop_run(loop);
    return true;
}

static void disconnect_cb(NMClient *client, GAsyncResult *result, GMainLoop *loop)
{
    
    GError *err = NULL;
    nm_client_deactivate_connection_finish(client, result, &err);
    if (err != NULL){
        g_printerr("Error: %s\n", err->message);
    }
    else{
        g_message("[NM] Connection Disconnected!");
    }
    g_main_loop_quit(loop);
}

int disconnect(char *uuid, int debug)
{

    GMainLoop *loop = g_main_loop_new(NULL, FALSE);
    NMClient *client = nm_client_new(NULL, NULL);
    const GPtrArray *arr = nm_client_get_active_connections(client);
    NMActiveConnection *target = NULL;

    for (size_t i = 0; i < arr->len; i++)
    {

        const char *current_uuid = nm_active_connection_get_uuid(arr->pdata[i]);

        if (debug) { g_print("active connection uuid: %s\n", uuid); }

        if (strcmp(uuid, current_uuid) == 0)
        {
            target = arr->pdata[i];
            break;
        }
    }

    nm_client_deactivate_connection_async(client, target, NULL, (GAsyncReadyCallback)disconnect_cb, loop);
    g_main_loop_run(loop);

    return true;
}

static void delete_cb(NMRemoteConnection *conn, GAsyncResult *result, GMainLoop *loop)
{
    
    GError *err = NULL;
    nm_remote_connection_delete_finish(conn, result, &err);
    if (err != NULL){
        g_printerr("Error: %s\n", err->message);
    }
    else{
        g_message("[NM] Connection Deleted!");
    }
    g_main_loop_quit(loop);
}

int delete_connection(char *uuid, int debug)
{

    GMainLoop *loop = g_main_loop_new(NULL, FALSE);

    NMClient *client = nm_client_new(NULL, NULL);
    const GPtrArray *arr = nm_client_get_connections(client);
    NMRemoteConnection *target = NULL;

    for (size_t i = 0; i < arr->len; i++)
    {
        const char *current_uuid = nm_connection_get_uuid(NM_CONNECTION(arr->pdata[i]));
        if (strcmp(uuid, current_uuid) == 0)
        {
            if (debug) { g_print("[%s] uuid match: %s\n", __FUNCTION__, uuid); }
            target = NM_REMOTE_CONNECTION(arr->pdata[i]);
            break;
        }
    }

    nm_remote_connection_delete_async(target, NULL, (GAsyncReadyCallback)delete_cb, loop);
    g_main_loop_run(loop);

    return true;
}

int delete_all_vpn_connections(void)
{

    NMClient *client = nm_client_new(NULL, NULL);
    const GPtrArray *arr = nm_client_get_connections(client);

    char vpn_uuid[arr->len][40];
    int vpn_uuid_count = 0;

    for (size_t i = 0; i < arr->len; i++)
    {

        const char *uuid = nm_connection_get_uuid(arr->pdata[i]);
        NMSetting *is_vpn = nm_connection_get_setting_by_name(arr->pdata[i], "vpn");
        g_print("[%s] uuid = %s\n", __FUNCTION__, uuid);
        if (is_vpn != NULL)
        {
            g_print("[%s] *VPN = %s\n", __FUNCTION__, uuid);
            strcpy(vpn_uuid[vpn_uuid_count], uuid);
            vpn_uuid_count++;
        }
    }

    for (size_t i = 0; i < vpn_uuid_count; i++)
    {
        delete_connection(vpn_uuid[i], 0);
    }
    

    return true;
}

int is_vpn_running(void)
{

    NMClient *client = nm_client_new(NULL, NULL);
    const GPtrArray *arr = nm_client_get_active_connections(client);

    for (size_t i = 0; i < arr->len; i++)
    {
        const char *con_type = nm_active_connection_get_connection_type(arr->pdata[i]);

        if (strcmp("vpn", con_type) == 0)
        {
            return true;
        }
    }
    return false;
}

int is_vpn_activated(char *uuid)
{

    /*
    https://people.freedesktop.org/~lkundrak/nm-docs/nm-vpn-dbus-types.html
    NM_VPN_CONNECTION_STATE_ACTIVATED = 5 //return true
    NM_VPN_CONNECTION_STATE_FAILED = 6 /return false
    */

    NMClient *client = nm_client_new(NULL, NULL);
    const GPtrArray *arr = nm_client_get_active_connections(client);
    g_assert(arr != NULL);
    NMActiveConnection *target = NULL;
    
    for (size_t i = 0; i < arr->len; i++)
    {

        const char *current_uuid = nm_active_connection_get_uuid(arr->pdata[i]);

        if (strcmp(uuid, current_uuid) == 0)
        {
            target = arr->pdata[i];
            break;
        }
    }

    if (target == NULL){
        return -1;
    }

    NMVpnConnectionState state = nm_vpn_connection_get_vpn_state(NM_VPN_CONNECTION(target));
    return state;
}


char* get_version(void){

    NMClient *client = nm_client_new(NULL, NULL);
    g_assert(client != NULL);
    return (char*)nm_client_get_version(client);
}

int is_openvpn_plugin_available(void){

    // this need to be used after checking version.

    GSList *plugins = nm_vpn_plugin_info_list_load();
    g_assert(plugins != NULL);
    GSList *iter;

    for (iter = plugins; iter; iter=iter->next)
    {
        if (strcmp("openvpn", nm_vpn_plugin_info_get_name(iter->data)) == 0){
            return true;
        }
    }

    return false;

}


/*
int main(){
    g_print("%s\n", get_version());
    g_print("%d\n", is_openvpn_plugin_available());
}
*/