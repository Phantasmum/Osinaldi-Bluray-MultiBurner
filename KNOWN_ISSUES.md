# Known Issues

## Optical writer permissions

Some Linux systems require the user to be in the `cdrom` group before optical writers can be accessed reliably.

Recommended fix:

```bash
sudo usermod -aG cdrom "$USER"
```

Then log out and log back in.

## Drive speed may differ from Windows

Linux `growisofs` and Windows burning tools may report or negotiate write speed differently. The default mode requests 4x compatibility mode.

## App Center local DEB preview icon

Some Ubuntu App Center versions may not show custom icons for local `.deb` files before installation. After installation, the application menu should show the Mirtza Chan icon.

## BD-R media detection

Some drives may take several seconds to recognize newly inserted BD-R media. Wait briefly after closing the tray before starting a burn.

## Sandboxed formats

Flatpak/Snap publication may require additional device permissions for `/dev/sr*` optical writers and mounted external drives.

## Do not close or power off during burning

The app blocks accidental window closure during active operations, but users should still avoid shutting down, unplugging drives, or disconnecting source disks while burning or reading.
