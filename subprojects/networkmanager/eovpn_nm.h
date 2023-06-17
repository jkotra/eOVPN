char *add_connection (
    char *config_name, char *username, char *password, char *ca, int debug);
int activate_connection (char *uuid);
int disconnect (char *uuid, int debug);
int delete_connection (char *uuid, int debug);
char *get_active_vpn_connection_uuid (void);
char *get_version (void);
int delete_all_vpn_connections (void);
int is_vpn_running (void);
int is_vpn_activated (char *uuid);
int is_openvpn_plugin_available (void);