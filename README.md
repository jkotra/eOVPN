# eOVPN

<div align="center">

<img src="static/connected.png" alt="eOVPN">


</div>

---

`eOVPN` is a application to connect, manage and update(from remote <i>.zip</i>) OpenVPN configurations.

<a href='https://flathub.org/apps/details/com.github.jkotra.eovpn'><img width='240' alt='Download on Flathub' src='https://flathub.org/assets/badges/flathub-badge-en.png'/></a>

---

## Setup

1. Open `Settings` from the menu.
2. Fill in the required details:
    * **Configuration Source**: This refers to a link that contains a zip file with OpenVPN configurations. 
        * Example: [IPVanish](https://www.ipvanish.com/software/configs/configs.zip), [NordVPN](https://downloads.nordcdn.com/configs/archives/servers/ovpn.zip)

        * [`eOVPN` also supports local directory/folder/zip]

    * **Update On Start(*Checkbox*)**: If Checked, configurations are downloaded and updated from `remote` each time you open the app.
    
    * **Requires Authentication**(*Checkbox*): Weather the configuration from remote requires Authentication. check the box and fill `Username` and `Password`

    * **OpenVPN CRT**: OpenVPN CRT/CA file. Will be automatically set on `Update` if such file exists in `remote`.

    * **Connect On Launch(*Checkbox*)**: If Checked, eOVPN will try to connect to the last connected server on application launch.

    * **Notification on 'Connect '& 'Disconnect'**(*Checkbox*): If Checked, eOVPN will send system notifications on connect and disconnect events.


3. click `Save`.
    * If it's for the first time, Configurations are automatically updated else the user needs to click `Update` from the menu to reflect changes.

---

### Debug

either use `--debug [LEVEL]` as a command-line argument or set `EOVPN_DEBUG=[LEVEL]` as an environment variable.

Refer: [Python Logging Levels](https://docs.python.org/3/library/logging.html#levels)

---

## Install

### Dependencies

```
pip install -r requirements.txt
```

eOVPN uses [meson build system](https://mesonbuild.com/), to build the project:

```
meson build -Dprefix=/usr
ninja install -C build
```

To uninstall:
```
ninja uninstall
```

---

* special thanks to [Gabriele Musco](https://gitlab.gnome.org/GabMus) for design suggestions.