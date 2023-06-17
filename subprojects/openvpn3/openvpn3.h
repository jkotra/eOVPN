int get_connection_status ();
void disconnect_all_sessions ();
int get_specific_connection_status (char *session_path);
char *get_version ();
char *import_config (char *name, char *config_str);
char *prepare_tunnel (char *config_object);
void init_unique_session (char *session_object);
void set_dco (char *session_object, int set_to);
void set_receive_log_events (char *session_object, int set_to);
void set_log_forward ();
char *is_ready_to_connect ();
void send_auth (char *session_object, int type, int group, int id, char *value);
void connect_vpn ();
void disconnect_vpn ();
void pause_vpn (char *reason);
void resume_vpn ();
char *p_get_version ();
int p_get_connection_status ();