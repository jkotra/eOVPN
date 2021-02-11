# eOVPN

---

eOVPN is a application to connect, manage and update(from remote <i>.zip</i>) OpenVPN configurations.

## Usage / Setup

1. Open 'Settings' from the menu.
2. Fill in the details, click 'Save' on completion.
3. Click 'Update' from the menu.

---

## Install

```
meson build
cd build
ninja install
```

To uninstall:
```
ninja uninstall
```

### Flatpak

```
flatpak-builder --user --install build-dir dist/flatpak/com.github.jkotra.eovpn.yml  --force-clean
```

---

* special thanks to [Gabriele Musco](https://gitlab.gnome.org/GabMus) for design suggestions.