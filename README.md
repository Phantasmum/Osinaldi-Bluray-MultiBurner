# Osinaldi BluRay MultiBurner

**Osinaldi BluRay MultiBurner 1.0.24 — May 2026** is a Linux GUI application for burning Blu-ray ISO images to multiple BD-R writers in parallel and creating ISO images from physical discs.

Mirtza Chan is the program mascot and application icon: **a tribute to my beautiful and beloved wife**.

- Website: [https://euroanime.jp.net](https://euroanime.jp.net)
- GitHub: [https://github.com/Phantasmum/Osinaldi-Bluray-MultiBurner](https://github.com/Phantasmum/Osinaldi-Bluray-MultiBurner)
- Contact: [phantasmum@proton.me](mailto:phantasmum@proton.me)
- License: MIT
- Application ID: `io.github.osinaldi.bluraymultiburner`
- Debian package: `osinaldi-bluray-multiburner`

![Main window](screenshots/main-window.png)

## Features

- Burn up to six Blu-ray ISO images in parallel.
- Assign a different ISO to every Blu-ray writer.
- Copy one master ISO to all selected writers.
- Create ISO images from physical discs.
- Reorder writers in the GUI to match a physical stacked drive layout.
- Automatically save writer order between sessions.
- Source Disk Lock enabled internally with a fixed limit of 3 readers per source disk.
- Safe close protection while burning or reading.
- Strong stop confirmation to avoid accidental disc loss.
- Open logs button.
- Writer access test button.
- Native Ubuntu/Linux file picker through `zenity`.
- Compatibility-focused `growisofs` command line.

## Default writing profile

The default speed mode is 4x compatibility mode.

Typical command:

```bash
growisofs -dvd-compat -speed=4 -Z '/dev/sr0=/path/movie.iso'
```

The maximum/automatic speed option is shown in the GUI as:

```text
AWS / Max
```

## Requirements

Runtime dependencies:

- Python 3
- Tkinter
- dvd+rw-tools
- util-linux
- eject
- zenity
- coreutils

On Ubuntu/Debian these are installed automatically by the `.deb` package.

## Recommended permissions

For reliable optical writer access, add your user to the `cdrom` group:

```bash
sudo usermod -aG cdrom "$USER"
```

Then log out and log back in.

## Installation from DEB

```bash
sudo apt install ./osinaldi-bluray-multiburner_1.0.24_all.deb
```

Launch from the app menu:

```text
Osinaldi BluRay MultiBurner
```

Or from terminal:

```bash
osinaldi-bluray-multiburner
```

## Creating an ISO from a physical disc

Click:

```text
Create ISO from disc...
```

Select the source writer/reader, review the inserted disc information, choose the destination `.iso` file, and confirm.

The app uses `dd` internally with progress reporting.

## Logs

Logs are stored in:

```bash
~/OsinaldiBurnLogs/
```

## Configuration

Writer order is saved in:

```bash
~/.config/osinaldi-bluray-multiburner/settings.json
```

## Safety notes

Stopping an active optical burn can make discs unusable. The app requires typing:

```text
STOP BURN
```

before stopping active or queued operations.

## Linux store preparation

This repository includes:

- `.desktop` launcher
- AppStream metadata
- hicolor icons
- MIT license
- changelog
- known issues page
- Debian package

Keep the application ID stable:

```text
io.github.osinaldi.bluraymultiburner
```

## License

MIT License. See [LICENSE](LICENSE).


## 1.0.24 — May 2026 GitHub repository update

The official GitHub repository is:

```text
https://github.com/Phantasmum/Osinaldi-Bluray-MultiBurner
```
