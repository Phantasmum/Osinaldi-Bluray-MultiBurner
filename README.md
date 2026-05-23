# Osinaldi BluRay MultiBurner

<p align="center">
  <img src="assets/mirtza_chan_icon_master.png" alt="Mirtza Chan - Osinaldi BluRay MultiBurner mascot" width="220">
</p>

<h3 align="center">Osinaldi BluRay MultiBurner 1.0.24 — May 2026</h3>

<p align="center">
  Linux GUI application for burning Blu-ray ISO images to multiple BD-R writers in parallel and creating ISO images from physical discs.
</p>

<p align="center">
  <strong>Mirtza Chan</strong> is the official program mascot and application icon:<br>
  <em>a tribute to my beautiful and beloved wife.</em>
</p>

<p align="center">
  <a href="https://euroanime.jp.net">Website</a> ·
  <a href="https://github.com/Phantasmum/Osinaldi-Bluray-MultiBurner">GitHub</a> ·
  <a href="mailto:phantasmum@proton.me">Contact</a>
</p>

<p align="center">
  <img src="screenshots/main-window.png" alt="Osinaldi BluRay MultiBurner main window" width="850">
</p>

<p align="center">
  <img src="screenshots/confirmation-dialog.png" alt="Osinaldi BluRay MultiBurner confirmation dialog" width="520">
</p>

---

**Osinaldi BluRay MultiBurner** is a Linux GUI application designed to make Blu-ray ISO burning simple, reliable, and practical for multi-writer workflows.

The program was created for users who need to burn multiple Blu-ray discs at the same time, especially when working with BD-R media, authored Blu-ray ISO files, anime collections, and compatibility-focused disc creation. It allows each Blu-ray writer to use its own ISO image, or the same master ISO can be copied to all selected writers when needed.

Unlike generic disc-burning tools, Osinaldi BluRay MultiBurner is focused on one clear purpose: burning Blu-ray ISO images to physical BD-R discs with a simple graphical interface, safe defaults, logs, and a workflow suitable for several drives running in parallel.

- Website: [https://euroanime.jp.net](https://euroanime.jp.net)
- GitHub: [https://github.com/Phantasmum/Osinaldi-Bluray-MultiBurner](https://github.com/Phantasmum/Osinaldi-Bluray-MultiBurner)
- Contact: [phantasmum@proton.me](mailto:phantasmum@proton.me)
- License: MIT
- Application ID: `io.github.osinaldi.bluraymultiburner`
- Debian package: `osinaldi-bluray-multiburner`

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
