#define G_LOG_DOMAIN "eovpn"

#include <stdbool.h>
#include <stdlib.h>
#include <string.h>
#include <glib.h>
#include <NetworkManager.h>
#include "eovpn_nm.h"

#define NM_OPENVPN_KEY_USERNAME "username"
#define NM_OPENVPN_KEY_PASSWORD "password"
#define NM_OPENVPN_KEY_CA "ca"

static void
add_cb (NMClient *client, GAsyncResult *result, GMainLoop *loop)
{
    GError *err = NULL;
    NMRemoteConnection *remote_conn =
        nm_client_add_connection_finish (client, result, &err);
    if (err != NULL)
        {
            g_print ("Error: %s\n", err->message);
            g_clear_error (&err);
        }
    else
        {
            g_debug ("[NM] Connection Added!");
            if (remote_conn != NULL)
                g_clear_object (&remote_conn);
        }

    g_main_loop_quit (loop);
}

char *
add_connection (char *config_name, char *username, char *password, char *ca)
{
    static char uuid_buffer[64];
    GMainLoop *loop = g_main_loop_new (NULL, FALSE);

    GSList *plugins = nm_vpn_plugin_info_list_load ();
    GSList *iter = NULL;
    NMVpnPluginInfo *plugin = NULL;
    GError *err = NULL;

    for (iter = plugins; iter != NULL; iter = iter->next)
        {
            NMVpnPluginInfo *info = NM_VPN_PLUGIN_INFO (iter->data);
            const char *name = nm_vpn_plugin_info_get_name (info);
            g_debug ("%s\n", name);

            if (name != NULL && strcmp ("openvpn", name) == 0)
                {
                    plugin = info;
                    break;
                }
        }

    if (plugin == NULL)
        {
            g_printerr ("OpenVPN plugin not found\n");
            if (plugins != NULL)
                g_slist_free_full (plugins, g_object_unref);
            g_main_loop_unref (loop);
            return NULL;
        }

    NMVpnEditorPlugin *editor = nm_vpn_plugin_info_load_editor_plugin (plugin, &err);
    if (err != NULL || editor == NULL)
        {
            if (err != NULL)
                {
                    g_printerr ("%s\n", err->message);
                    g_clear_error (&err);
                }
            g_slist_free_full (plugins, g_object_unref);
            g_main_loop_unref (loop);
            return NULL;
        }

    NMConnection *conn = nm_vpn_editor_plugin_import (editor, config_name, &err);
    /* editor is owned by plugin, so do not unref editor directly */
    g_slist_free_full (plugins, g_object_unref);

    if (err != NULL || conn == NULL)
        {
            if (err != NULL)
                {
                    g_printerr ("%s\n", err->message);
                    g_clear_error (&err);
                }
            if (conn != NULL)
                g_clear_object (&conn);
            g_main_loop_unref (loop);
            return NULL;
        }

    NMSettingVpn *vpn_settings = nm_connection_get_setting_vpn (conn);
    if (vpn_settings != NULL)
        {
            if (username != NULL)
                {
                    nm_setting_vpn_add_data_item (
                        vpn_settings, NM_OPENVPN_KEY_USERNAME, username);
                }
            if (password != NULL)
                {
                    nm_setting_vpn_add_secret (
                        vpn_settings, NM_OPENVPN_KEY_PASSWORD, password);
                }
            if (ca != NULL)
                {
                    nm_setting_vpn_add_data_item (vpn_settings, NM_OPENVPN_KEY_CA, ca);
                }
        }

    nm_connection_normalize (conn, NULL, NULL, NULL);

    NMClient *client = nm_client_new (NULL, NULL);
    if (client == NULL)
        {
            g_clear_object (&conn);
            g_main_loop_unref (loop);
            return NULL;
        }

    nm_client_add_connection_async (
        client, conn, TRUE, NULL, (GAsyncReadyCallback) add_cb, loop);
    g_main_loop_run (loop);

    const char *uuid = nm_connection_get_uuid (conn);
    if (uuid != NULL)
        {
            g_strlcpy (uuid_buffer, uuid, sizeof (uuid_buffer));
        }
    else
        {
            uuid_buffer[0] = '\0';
        }

    g_clear_object (&conn);
    g_clear_object (&client);
    g_main_loop_unref (loop);

    return uuid_buffer[0] != '\0' ? uuid_buffer : NULL;
}

static void
activate_cb (NMClient *client, GAsyncResult *result, GMainLoop *loop)
{
    GError *err = NULL;
    NMActiveConnection *active_conn =
        nm_client_activate_connection_finish (client, result, &err);
    if (err != NULL)
        {
            g_print ("Error: %s\n", err->message);
            g_clear_error (&err);
        }
    else
        {
            g_debug ("[NM] Connection Connected!");
            if (active_conn != NULL)
                g_clear_object (&active_conn);
        }

    g_main_loop_quit (loop);
}

int
activate_connection (char *uuid)
{
    if (uuid == NULL)
        return false;

    GMainLoop *loop = g_main_loop_new (NULL, FALSE);
    NMClient *client = nm_client_new (NULL, NULL);
    if (client == NULL)
        {
            g_main_loop_unref (loop);
            return false;
        }

    const GPtrArray *arr = nm_client_get_connections (client);
    NMConnection *target = NULL;

    if (arr != NULL)
        {
            for (size_t i = 0; i < arr->len; i++)
                {
                    NMConnection *c = NM_CONNECTION (arr->pdata[i]);
                    const char *current_uuid = nm_connection_get_uuid (c);
                    if (current_uuid != NULL && strcmp (uuid, current_uuid) == 0)
                        {
                            target = c;
                            break;
                        }
                }
        }

    if (target == NULL)
        {
            g_warning ("[%s] Connection with UUID %s not found", __FUNCTION__, uuid);
            g_clear_object (&client);
            g_main_loop_unref (loop);
            return false;
        }

    nm_client_activate_connection_async (client,
                                         target,
                                         NULL,
                                         NULL,
                                         NULL,
                                         (GAsyncReadyCallback) activate_cb,
                                         loop);
    g_main_loop_run (loop);

    g_clear_object (&client);
    g_main_loop_unref (loop);
    return true;
}

static void
disconnect_cb (NMClient *client, GAsyncResult *result, GMainLoop *loop)
{
    GError *err = NULL;
    nm_client_deactivate_connection_finish (client, result, &err);
    if (err != NULL)
        {
            g_print ("Error: %s\n", err->message);
            g_clear_error (&err);
        }
    else
        {
            g_debug ("[NM] Connection Disconnected!");
        }
    g_main_loop_quit (loop);
}

int
disconnect (char *uuid)
{
    if (uuid == NULL)
        return false;

    GMainLoop *loop = g_main_loop_new (NULL, FALSE);
    NMClient *client = nm_client_new (NULL, NULL);
    if (client == NULL)
        {
            g_main_loop_unref (loop);
            return false;
        }

    const GPtrArray *arr = nm_client_get_active_connections (client);
    NMActiveConnection *target = NULL;

    if (arr != NULL)
        {
            for (size_t i = 0; i < arr->len; i++)
                {
                    NMActiveConnection *ac = NM_ACTIVE_CONNECTION (arr->pdata[i]);
                    const char *current_uuid = nm_active_connection_get_uuid (ac);

                    g_debug ("connection uuid: %s\n", uuid);

                    if (current_uuid != NULL && strcmp (uuid, current_uuid) == 0)
                        {
                            target = ac;
                            break;
                        }
                }
        }

    if (target == NULL)
        {
            g_warning ("[%s] Active connection with UUID %s not found", __FUNCTION__, uuid);
            g_clear_object (&client);
            g_main_loop_unref (loop);
            return false;
        }

    nm_client_deactivate_connection_async (
        client, target, NULL, (GAsyncReadyCallback) disconnect_cb, loop);
    g_main_loop_run (loop);

    g_clear_object (&client);
    g_main_loop_unref (loop);
    return true;
}

static void
delete_cb (NMRemoteConnection *conn, GAsyncResult *result, GMainLoop *loop)
{
    GError *err = NULL;
    nm_remote_connection_delete_finish (conn, result, &err);
    if (err != NULL)
        {
            g_print ("Error: %s\n", err->message);
            g_clear_error (&err);
        }
    else
        {
            g_debug ("[NM] Connection Deleted!");
        }
    g_main_loop_quit (loop);
}

int
delete_connection (char *uuid)
{
    if (uuid == NULL)
        return false;

    GMainLoop *loop = g_main_loop_new (NULL, FALSE);
    NMClient *client = nm_client_new (NULL, NULL);
    if (client == NULL)
        {
            g_main_loop_unref (loop);
            return false;
        }

    const GPtrArray *arr = nm_client_get_connections (client);
    NMRemoteConnection *target = NULL;

    if (arr != NULL)
        {
            for (size_t i = 0; i < arr->len; i++)
                {
                    NMConnection *c = NM_CONNECTION (arr->pdata[i]);
                    const char *current_uuid = nm_connection_get_uuid (c);
                    if (current_uuid != NULL && strcmp (uuid, current_uuid) == 0)
                        {
                            g_debug ("[%s] uuid match: %s\n", __FUNCTION__, uuid);
                            target = NM_REMOTE_CONNECTION (arr->pdata[i]);
                            break;
                        }
                }
        }

    if (target == NULL)
        {
            g_warning ("[%s] Remote connection with UUID %s not found", __FUNCTION__, uuid);
            g_clear_object (&client);
            g_main_loop_unref (loop);
            return false;
        }

    nm_remote_connection_delete_async (
        target, NULL, (GAsyncReadyCallback) delete_cb, loop);
    g_main_loop_run (loop);

    g_clear_object (&client);
    g_main_loop_unref (loop);
    return true;
}

char *
get_active_vpn_connection_uuid (void)
{
    static char active_uuid[64];
    NMClient *client = nm_client_new (NULL, NULL);
    if (client == NULL)
        return NULL;

    const GPtrArray *arr = nm_client_get_active_connections (client);
    char *result = NULL;

    if (arr != NULL)
        {
            for (size_t i = 0; i < arr->len; i++)
                {
                    NMActiveConnection *ac = NM_ACTIVE_CONNECTION (arr->pdata[i]);
                    const char *conn_type = nm_active_connection_get_connection_type (ac);
                    if (conn_type != NULL && strcmp (conn_type, "vpn") == 0)
                        {
                            const char *uuid = nm_active_connection_get_uuid (ac);
                            if (uuid != NULL)
                                {
                                    g_strlcpy (active_uuid, uuid, sizeof (active_uuid));
                                    result = active_uuid;
                                }
                            break;
                        }
                }
        }

    g_clear_object (&client);
    return result;
}

int
delete_all_vpn_connections (void)
{
    NMClient *client = nm_client_new (NULL, NULL);
    if (client == NULL)
        return false;

    const GPtrArray *arr = nm_client_get_connections (client);
    if (arr == NULL || arr->len == 0)
        {
            g_clear_object (&client);
            return true;
        }

    char **vpn_uuid = g_new0 (char *, arr->len);
    int vpn_uuid_count = 0;

    for (size_t i = 0; i < arr->len; i++)
        {
            NMConnection *conn = NM_CONNECTION (arr->pdata[i]);
            const char *uuid = nm_connection_get_uuid (conn);
            NMSetting *is_vpn = nm_connection_get_setting_by_name (conn, "vpn");
            g_print ("[%s] uuid = %s\n", __FUNCTION__, uuid ? uuid : "(null)");
            if (is_vpn != NULL && uuid != NULL)
                {
                    g_print ("[%s] *VPN = %s\n", __FUNCTION__, uuid);
                    vpn_uuid[vpn_uuid_count++] = g_strdup (uuid);
                }
        }

    g_clear_object (&client);

    for (int i = 0; i < vpn_uuid_count; i++)
        {
            g_print ("Deleting %s\n...", vpn_uuid[i]);
            delete_connection (vpn_uuid[i]);
            g_free (vpn_uuid[i]);
        }
    g_free (vpn_uuid);

    return true;
}

int
is_vpn_running (void)
{
    NMClient *client = nm_client_new (NULL, NULL);
    if (client == NULL)
        return false;

    const GPtrArray *arr = nm_client_get_active_connections (client);
    gboolean running = FALSE;

    if (arr != NULL)
        {
            for (size_t i = 0; i < arr->len; i++)
                {
                    NMActiveConnection *ac = NM_ACTIVE_CONNECTION (arr->pdata[i]);
                    const char *con_type = nm_active_connection_get_connection_type (ac);

                    if (con_type != NULL && strcmp ("vpn", con_type) == 0)
                        {
                            running = TRUE;
                            break;
                        }
                }
        }

    g_clear_object (&client);
    return running;
}

int
is_vpn_activated (char *uuid)
{
    if (uuid == NULL)
        return -1;

    NMClient *client = nm_client_new (NULL, NULL);
    if (client == NULL)
        return -1;

    const GPtrArray *arr = nm_client_get_active_connections (client);
    NMActiveConnection *target = NULL;

    if (arr != NULL)
        {
            for (size_t i = 0; i < arr->len; i++)
                {
                    NMActiveConnection *ac = NM_ACTIVE_CONNECTION (arr->pdata[i]);
                    const char *current_uuid = nm_active_connection_get_uuid (ac);

                    if (current_uuid != NULL && strcmp (uuid, current_uuid) == 0)
                        {
                            target = ac;
                            break;
                        }
                }
        }

    if (target == NULL)
        {
            g_clear_object (&client);
            return -1;
        }

    NMVpnConnectionState state =
        nm_vpn_connection_get_vpn_state (NM_VPN_CONNECTION (target));
    g_clear_object (&client);
    return state;
}

char *
get_version (void)
{
    static char version_buf[64];
    GError *err = NULL;
    NMClient *client = nm_client_new (NULL, &err);
    if (err != NULL)
        {
            g_print ("Error: %s\n", err->message);
            g_clear_error (&err);
            return NULL;
        }

    const char *ver = nm_client_get_version (client);
    if (ver != NULL)
        g_strlcpy (version_buf, ver, sizeof (version_buf));
    else
        version_buf[0] = '\0';

    g_clear_object (&client);
    return version_buf[0] != '\0' ? version_buf : NULL;
}

int
is_openvpn_plugin_available (void)
{
    GSList *plugins = nm_vpn_plugin_info_list_load ();
    GSList *iter;
    gboolean available = FALSE;

    if (plugins == NULL)
        {
            return false;
        }

    for (iter = plugins; iter; iter = iter->next)
        {
            NMVpnPluginInfo *info = NM_VPN_PLUGIN_INFO (iter->data);
            const char *name = nm_vpn_plugin_info_get_name (info);
            if (name != NULL && strcmp ("openvpn", name) == 0)
                {
                    available = TRUE;
                    break;
                }
        }

    g_slist_free_full (plugins, g_object_unref);
    return available;
}