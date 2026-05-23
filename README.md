# Osinaldi BluRay MultiBurner

**Osinaldi BluRay MultiBurner** is a Linux GUI application designed to make Blu-ray ISO burning simple, reliable, and practical for multi-writer workflows.

The program was created for users who need to burn multiple Blu-ray discs at the same time, especially when working with BD-R media, anime collections, authored Blu-ray ISO files, and compatibility-focused disc creation. It allows each Blu-ray writer to use its own ISO image, or the same master ISO can be copied to all selected writers when needed.

Unlike generic disc-burning tools, Osinaldi BluRay MultiBurner is focused on one clear purpose: burning Blu-ray ISO images to physical BD-R discs with a simple graphical interface, safe defaults, and a workflow suitable for several drives running in parallel.

## What it does

- Burn Blu-ray ISO images to BD-R discs.
- Use up to six Blu-ray writers in parallel.
- Assign a different ISO file to each writer.
- Copy one master ISO to all selected writers.
- Create an ISO image from a physical disc.
- Save the physical order of writers in the interface.
- Protect active burns from accidental window closure.
- Provide logs for every operation.
- Test writer access from the GUI.
- Use compatibility-focused `growisofs` commands.

## Designed for compatibility

The default writing profile is focused on broad Blu-ray player compatibility, including older or inexpensive Blu-ray players and consoles. The default 4x writing mode is intended for stable BD-R burning workflows, while the `AWS / Max` option is available for automatic or maximum drive speed behavior.

## Built for Linux

Osinaldi BluRay MultiBurner is built for Ubuntu and Linux desktop systems using Python and Tkinter. It integrates with common Linux tools such as `growisofs`, `dd`, `zenity`, `eject`, and standard `/dev/sr*` optical writer devices.

The project includes Debian packaging, AppStream metadata, desktop launcher files, icons, changelog, known issues, and documentation to make future Linux store distribution easier.

## Mirtza Chan

The official mascot and program icon is **Mirtza Chan**.

Mirtza Chan is a cheerful anime-style character created as the visual identity of the program and as a tribute to my beautiful and beloved wife. She appears as the application icon and inside the About window, giving the tool a more personal and friendly identity instead of looking like a generic utility.

## Project information

- Website: https://euroanime.jp.net
- GitHub: https://github.com/Phantasmum/Osinaldi-Bluray-MultiBurner
- Contact: phantasmum@proton.me
- License: MIT
