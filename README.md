# eOVPN

<div align="center">

<img src="static/connected.png" alt="eOVPN" height='500'>


</div>

---

`eOVPN` is a application to connect, manage and update(from remote <i>.zip</i>) OpenVPN configurations.

<a href='https://flathub.org/apps/details/com.github.jkotra.eovpn'><img height='50' alt='Download on Flathub' src='https://flathub.org/assets/badges/flathub-badge-en.png'/></a>

<a href="https://www.buymeacoffee.com/jkotra"><img src="https://img.buymeacoffee.com/button-api/?text=Buy me a coffee&emoji=&slug=jkotra&button_colour=FFDD00&font_colour=000000&font_family=Lato&outline_colour=000000&coffee_colour=ffffff"></a>

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

to change python dependencies, refer to [flatpak documentation](https://docs.flatpak.org/en/latest/python.html#building-multiple-python-dependencies).


---

* special thanks to [Gabriele Musco](https://gitlab.gnome.org/GabMus) for design suggestions.