# eOVPN

<div align="center">

<img src="static/connected.png" alt="eOVPN" height='500'>


</div>

---

`eOVPN` is a application to connect, manage and update(from remote <i>.zip</i>) OpenVPN configurations.

<a href='https://flathub.org/apps/details/com.github.jkotra.eovpn'><img height='50' alt='Download on Flathub' src='https://flathub.org/assets/badges/flathub-badge-en.png'/></a>

<a href='https://ko-fi.com/X7X83SJSN' target='_blank'><img height='36' style='border:0px;height:36px;' src='https://cdn.ko-fi.com/cdn/kofi5.png?v=2' border='0' alt='Buy Me a Coffee at ko-fi.com' /></a>

---

## Setup

1. Open `Settings` from the menu.
2. Fill in the required details:
    * **Configuration Source**: This refers to a link that contains a zip file with OpenVPN configurations. 
        * Example: [IPVanish](https://www.ipvanish.com/software/configs/configs.zip), [NordVPN](https://downloads.nordcdn.com/configs/archives/servers/ovpn.zip)

        * [`eOVPN` also supports local directory/folder/zip]

3. click `Save`.
    * If it's for the first time, Configurations are automatically updated else the user needs to click `Update` from the menu to reflect changes.

---

### Debug

either use `--debug [LEVEL]` as a command-line argument or set `EOVPN_DEBUG=[LEVEL]` as an environment variable.

Refer: [Python Logging Levels](https://docs.python.org/3/library/logging.html#levels)

---

# Install

### Flatpak (**Recommended**)


<a href='https://flathub.org/apps/details/com.github.jkotra.eovpn'><img height='50' alt='Download on Flathub' src='https://flathub.org/assets/badges/flathub-badge-en.png'/></a>

---


### Native (For Developers)

### Build Flags

```
-Dnm=[true(default)|false]  Include support for NetworkManager(libnm).
```

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
sudo ninja uninstall -C build
```

# Build Flatpak


```
flatpak-builder --user --install build-dir dist/flatpak/com.github.jkotra.eovpn.yml --force-clean
```

to build from local directory, use:
```
flatpak-builder --user --install build-dir dist/flatpak/com.github.jkotra.eovpn_local_build.yml --force-clean
```

to change python dependencies, refer to [flatpak documentation](https://docs.flatpak.org/en/latest/python.html#building-multiple-python-dependencies).


---

* special thanks to [Gabriele Musco](https://gitlab.gnome.org/GabMus) for design suggestions.