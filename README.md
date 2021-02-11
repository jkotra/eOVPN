# eOVPN

---

eOVPN is a application to connect, manage and update(from remote <i>.zip</i>) OpenVPN configurations.

## Usage / Setup

1. Open 'Settings' from menu.
2. Fill in the details, click 'Save' on completion.
3. Click 'Update' from menu.

---

## Install

```
meson build
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