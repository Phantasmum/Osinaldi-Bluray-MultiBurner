#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Osinaldi BluRay MultiBurner for Linux 1.0.24

Purpose:
- Burn Blu-ray ISO images to one or multiple Blu-ray writers in parallel.
- BD-R workflow: BD-R only, BD-R HTL recommended.
- Designed for maximum playback compatibility with old/cheap Blu-ray players,
  PS3, PS4, PS5 and modern Blu-ray players.
- Linux GUI, optimized for Ubuntu and similar distributions.

Compatibility burn profile:
- BD-R only for BD-R workflow.
- BD-R HTL profile text.
- Windows-like speed mode by default: no explicit -speed flag, so the burner firmware negotiates speed.
- Optional fixed 4x request available.
- growisofs with -dvd-compat to finalize/close the disc.
- No multisession.
- No experimental flags.
- Direct ISO-to-disc writing.
- Native Ubuntu/Linux file picker only.
- macOS-like light GUI with traffic-light dots and per-drive progress bars.

Important:
Default speed mode does not pass -speed to growisofs. This is closer to Windows/ImgBurn
"automatic" behavior, letting the burner firmware choose the best real write strategy.
A fixed 4x request is still available if needed, but some Linux/growisofs/drive
combinations may turn -speed=4 into a much slower real speed such as about 1.7x.
"""

import os
import json
import re
import shlex
import shutil
import signal
import subprocess
import threading
import webbrowser
import tkinter as tk
from pathlib import Path
from tkinter import ttk, messagebox, simpledialog


APP_NAME = "Osinaldi BluRay MultiBurner 1.0.24 — May 2026"
APP_VERSION = "1.0.24"
APP_LAST_MODIFIED = "May 2026"
APP_VERSION_DISPLAY = "1.0.24 — May 2026"
APP_ID = "io.github.osinaldi.bluraymultiburner"
APP_GITHUB_URL = "https://github.com/Phantasmum/Osinaldi-Bluray-MultiBurner"
APP_HOMEPAGE = "https://euroanime.jp.net"
APP_CONTACT_EMAIL = "phantasmum@proton.me"


def which(cmd):
    return shutil.which(cmd)


def run_command(args, timeout=20):
    try:
        p = subprocess.run(
            args,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
        return p.returncode, p.stdout.strip()
    except subprocess.TimeoutExpired:
        return 124, "Timeout while running: " + " ".join(args)
    except Exception as e:
        return 999, str(e)


def human_size(num_bytes):
    gib = num_bytes / (1024 ** 3)
    if gib < 1:
        return f"{num_bytes / (1024 ** 2):.1f} MB"
    return f"{gib:.2f} GB"


def iso_capacity_hint(path):
    try:
        size = os.path.getsize(path)
    except Exception:
        return "Could not read the Blu-ray ISO size."

    gib = size / (1024 ** 3)
    if gib <= 25:
        disc = "BD-25 BD-R HTL"
    elif gib <= 50:
        disc = "BD-50 BD-R HTL"
    elif gib <= 100:
        disc = "BD-100 HTL, if supported by your burner/player target"
    elif gib <= 128:
        disc = "BD-128 HTL, if supported by your burner/player target"
    else:
        disc = "higher-capacity Blu-ray media, if your writer supports it"

    return f"Blu-ray ISO size: {human_size(size)}. Recommended client media: {disc}."


def pick_iso_with_native_linux_dialog():
    """
    Opens the native GTK file picker through zenity.
    This usually shows mounted NTFS/external drives in the sidebar,
    like the Ubuntu Files app.
    """
    if not which("zenity"):
        return None, "zenity_missing"

    cmd = [
        "zenity",
        "--file-selection",
        "--title=Select Blu-ray ISO",
        "--filename=" + str(Path.home()) + "/",
        "--file-filter=All files | *",
        "--file-filter=ISO lowercase | *.iso",
        "--file-filter=ISO uppercase | *.ISO",
        "--file-filter=ISO mixed case | *.[iI][sS][oO]",
    ]

    try:
        p = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if p.returncode == 0:
            path = p.stdout.strip()
            if path:
                return path, None
        return None, "cancelled"
    except Exception as e:
        return None, str(e)


def save_iso_with_native_linux_dialog():
    """
    Opens the native GTK save dialog through zenity.
    Used for creating an ISO from a physical disc.
    """
    if not which("zenity"):
        return None, "zenity_missing"

    default_name = str(Path.home() / "disc_image.iso")
    cmd = [
        "zenity",
        "--file-selection",
        "--save",
        "--confirm-overwrite",
        "--title=Save ISO image as",
        "--filename=" + default_name,
        "--file-filter=ISO image | *.iso",
        "--file-filter=All files | *",
    ]

    try:
        p = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if p.returncode == 0:
            path = p.stdout.strip()
            if path:
                if not path.lower().endswith(".iso"):
                    path += ".iso"
                return path, None
        return None, "cancelled"
    except Exception as e:
        return None, str(e)


def get_device_description(dev):
    rc, out = run_command(["lsblk", "-ndo", "VENDOR,MODEL,TYPE", dev])
    if rc == 0 and out:
        return re.sub(r"\s+", " ", out).strip()

    if which("udevadm"):
        rc, out = run_command(["udevadm", "info", "--query=property", "--name", dev])
        vendor = ""
        model = ""
        for line in out.splitlines():
            if line.startswith("ID_VENDOR="):
                vendor = line.split("=", 1)[1].replace("_", " ")
            elif line.startswith("ID_MODEL="):
                model = line.split("=", 1)[1].replace("_", " ")
        desc = f"{vendor} {model}".strip()
        if desc:
            return desc

    return Path(dev).name


def natural_sr_key(dev):
    m = re.search(r"/dev/sr(\d+)$", dev)
    return int(m.group(1)) if m else 9999


def detect_bluray_drives():
    devices = []

    rc, out = run_command(["lsblk", "-ndo", "NAME,TYPE"])
    if rc == 0:
        for line in out.splitlines():
            parts = line.split()
            if len(parts) >= 2:
                name, typ = parts[0], parts[1]
                if typ == "rom" and name.startswith("sr"):
                    dev = f"/dev/{name}"
                    if os.path.exists(dev):
                        devices.append((dev, get_device_description(dev)))

    known = {d[0] for d in devices}
    for p in sorted(Path("/dev").glob("sr*")):
        dev = str(p)
        if dev not in known:
            devices.append((dev, get_device_description(dev)))

    return sorted(devices, key=lambda item: natural_sr_key(item[0]))


def has_rw_access(dev):
    return os.access(dev, os.R_OK | os.W_OK)


def parse_growisofs_progress(line):
    patterns = [
        r"\(\s*(\d+(?:\.\d+)?)%\s*\)",
        r"(\d+(?:\.\d+)?)%\s*done",
        r"\s(\d+(?:\.\d+)?)%\s",
    ]
    for pat in patterns:
        m = re.search(pat, line, re.IGNORECASE)
        if m:
            try:
                val = float(m.group(1))
                if 0 <= val <= 100:
                    return val
            except ValueError:
                pass
    return None


def parse_burn_speed(line):
    """
    Attempts to extract the real speed reported by growisofs, such as @1.7x.
    """
    m = re.search(r"@\s*(\d+(?:\.\d+)?)x", line, re.IGNORECASE)
    if not m:
        return None
    try:
        return float(m.group(1))
    except ValueError:
        return None


def parse_dd_progress_bytes(line):
    """
    Parses GNU dd status=progress output, usually:
    123456789 bytes (123 MB, 117 MiB) copied, ...
    """
    m = re.search(r"^\s*(\d+)\s+bytes", line)
    if not m:
        return None
    try:
        return int(m.group(1))
    except ValueError:
        return None


class MultiBurnerApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_NAME)
        self.geometry("1220x840")
        self.minsize(1080, 740)
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.load_app_icon()

        # Prevent accidental terminal Ctrl+C or termination while burning.
        # Also ignore SIGHUP so closing the launching terminal does not close the GUI.
        try:
            signal.signal(signal.SIGINT, self.handle_sigint)
            signal.signal(signal.SIGTERM, self.handle_sigterm)
            if hasattr(signal, "SIGHUP"):
                signal.signal(signal.SIGHUP, signal.SIG_IGN)
        except Exception:
            pass

        self.iso_path = tk.StringVar()
        self.speed_mode = tk.StringVar(value="Request 4x compatibility")
        self.eject_after = tk.BooleanVar(value=True)
        self.use_sudo = tk.BooleanVar(value=False)  # hidden default: normal user access, no pkexec
        self.source_lock_enabled = tk.BooleanVar(value=True)  # hidden default
        self.source_lock_limit = tk.StringVar(value="3")  # hidden default
        self.pending_devices = []
        self.source_active_counts = {}
        self.device_source_keys = {}
        self.iso_creation_active = False

        self.device_vars = {}
        self.device_order = []
        self.device_names = {}
        self.device_status = {}
        self.device_progress = {}
        self.device_progress_text = {}
        self.device_iso_vars = {}
        self.device_iso_labels = {}
        self.device_iso_buttons = {}
        self.running = {}
        self.active_devices = set()
        self.lock = threading.RLock()
        self.is_burning = False
        self.stopping = False
        self.close_blocked_count = 0
        self.config_dir = Path.home() / ".config" / "osinaldi-bluray-multiburner"
        self.config_file = self.config_dir / "settings.json"
        self.saved_writer_order = self.load_saved_writer_order()
        self._after_ids = set()

        self.setup_styles()
        self.build_ui()
        self.check_dependencies()
        self.refresh_devices()


    def maximize_startup_window(self):
        """
        Opens the window expanded so the writer list and log are visible.
        Works across common Linux/Tk window managers with safe fallbacks.
        """
        try:
            self.state("zoomed")
            return
        except Exception:
            pass

        try:
            self.attributes("-zoomed", True)
            return
        except Exception:
            pass

        try:
            width = self.winfo_screenwidth()
            height = self.winfo_screenheight()
            self.geometry(f"{max(1180, width - 80)}x{max(780, height - 100)}+20+20")
        except Exception:
            pass


    def asset_path(self, name):
        return Path(__file__).resolve().parent / "assets" / name

    def load_app_icon(self):
        """
        Load Mirtza Chan as the real application icon for the window.
        """
        try:
            icon_path = self.asset_path("osinaldi-bluray-multiburner.png")
            if icon_path.exists():
                self.app_icon_image = tk.PhotoImage(file=str(icon_path))
                self.iconphoto(True, self.app_icon_image)
        except Exception:
            pass

    def setup_styles(self):
        self.configure(bg="#e5e7eb")

        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except Exception:
            pass

        style.configure(".", font=("Ubuntu", 10))
        style.configure("TFrame", background="#e5e7eb")
        style.configure("TLabel", background="#e5e7eb", foreground="#1f2937")
        style.configure("Header.TLabel", background="#e5e7eb", foreground="#111827", font=("Ubuntu", 18, "bold"))
        style.configure("SubHeader.TLabel", background="#e5e7eb", foreground="#4b5563")
        style.configure("TLabelframe", background="#e5e7eb", borderwidth=1, relief="solid")
        style.configure("TLabelframe.Label", background="#e5e7eb", foreground="#111827", font=("Ubuntu", 10, "bold"))

        style.configure(
            "TEntry",
            fieldbackground="#ffffff",
            foreground="#111827",
            bordercolor="#d1d5db",
            lightcolor="#d1d5db",
            darkcolor="#d1d5db",
            padding=6,
        )
        style.map(
            "TEntry",
            bordercolor=[("focus", "#6aa9ff")],
            lightcolor=[("focus", "#6aa9ff")],
            darkcolor=[("focus", "#6aa9ff")],
        )

        style.configure(
            "TCombobox",
            fieldbackground="#ffffff",
            background="#ffffff",
            foreground="#111827",
            bordercolor="#d1d5db",
            lightcolor="#d1d5db",
            darkcolor="#d1d5db",
            arrowsize=14,
            padding=5,
        )

        style.configure(
            "TButton",
            background="#ffffff",
            foreground="#111827",
            borderwidth=0,
            focusthickness=0,
            padding=(12, 8),
            relief="flat",
        )
        style.map(
            "TButton",
            background=[("active", "#f3f4f6"), ("disabled", "#e5e7eb")],
            foreground=[("disabled", "#9ca3af")],
        )

        style.configure("Primary.TButton", background="#e8f2ff", foreground="#0f172a", padding=(14, 9), borderwidth=0, relief="flat")
        style.map("Primary.TButton", background=[("active", "#dbeafe"), ("disabled", "#e5e7eb")])

        style.configure("Green.TButton", background="#34c759", foreground="#ffffff", padding=(14, 9), borderwidth=0, relief="flat")
        style.map("Green.TButton", background=[("active", "#2fb44f"), ("disabled", "#b7e4c1")], foreground=[("disabled", "#ffffff")])

        style.configure("Red.TButton", background="#ff5f57", foreground="#ffffff", padding=(14, 9), borderwidth=0, relief="flat")
        style.map("Red.TButton", background=[("active", "#eb554d"), ("disabled", "#f3b4b0")], foreground=[("disabled", "#ffffff")])

        style.configure("SoftGreen.TButton", background="#dff7e7", foreground="#166534", padding=(12, 8), borderwidth=0, relief="flat")
        style.map("SoftGreen.TButton", background=[("active", "#cff0da"), ("disabled", "#ebf7ef")])

        style.configure("SoftRed.TButton", background="#ffe3e1", foreground="#991b1b", padding=(12, 8), borderwidth=0, relief="flat")
        style.map("SoftRed.TButton", background=[("active", "#ffd2cf"), ("disabled", "#faeceb")])

        style.configure("TCheckbutton", background="#e5e7eb", foreground="#1f2937")

        style.configure(
            "Mac.Horizontal.TProgressbar",
            troughcolor="#e5e7eb",
            background="#34c759",
            bordercolor="#e5e7eb",
            lightcolor="#34c759",
            darkcolor="#34c759",
            thickness=12,
        )

    def safe_after(self, delay_ms, callback, *args):
        if not self.winfo_exists():
            return None
        holder = {"id": None}

        def wrapped():
            self._after_ids.discard(holder["id"])
            try:
                if self.winfo_exists():
                    callback(*args)
            except tk.TclError:
                pass

        try:
            aid = self.after(delay_ms, wrapped)
            holder["id"] = aid
            self._after_ids.add(aid)
            return aid
        except tk.TclError:
            return None


    def handle_sigint(self, signum, frame):
        if self.is_burning or self.running or self.pending_devices or self.active_devices:
            self.log_msg("Close/interrupt ignored: active burn is protected.")
            try:
                self.bell()
            except Exception:
                pass
            return
        self.on_close()

    def handle_sigterm(self, signum, frame):
        if self.is_burning or self.running or self.pending_devices or self.active_devices:
            self.log_msg("Terminate signal ignored: active burn is protected.")
            try:
                self.bell()
            except Exception:
                pass
            return
        self.on_close()

    def show_burn_lock_warning(self):
        self.close_blocked_count += 1
        try:
            self.bell()
        except Exception:
            pass

        messagebox.showwarning(
            APP_NAME,
            "Burn protection is active.\n\n"
            "The window cannot be closed while discs are burning, reading, or queued.\n\n"
            "Wait until every writer/reader operation finishes.\n"
            "This prevents accidental disc or ISO operation interruption."
        )
        self.log_msg(f"Close attempt blocked while burning/queued. Count: {self.close_blocked_count}")

    def get_source_key_for_iso(self, iso_path):
        """
        Groups ISO files by source filesystem. This is the practical cache/source lock:
        max N simultaneous readers from the same HDD/SSD/mount.
        """
        try:
            return str(os.stat(iso_path).st_dev)
        except Exception:
            return "unknown"

    def get_source_label_for_iso(self, iso_path):
        if which("findmnt"):
            rc, out = run_command(["findmnt", "-T", iso_path, "-no", "TARGET,SOURCE,FSTYPE"], timeout=10)
            if rc == 0 and out.strip():
                return re.sub(r"\s+", " ", out.strip())
        try:
            return str(Path(iso_path).anchor or Path(iso_path).parents[-1])
        except Exception:
            return "unknown"

    def get_source_limit(self):
        try:
            value = int(self.source_lock_limit.get().strip())
            return max(1, min(6, value))
        except Exception:
            return 3


    def open_logs_folder(self):
        log_dir = Path.home() / "OsinaldiBurnLogs"
        log_dir.mkdir(parents=True, exist_ok=True)
        try:
            if which("xdg-open"):
                subprocess.Popen(["xdg-open", str(log_dir)])
            else:
                messagebox.showinfo(APP_NAME, f"Logs folder:\n{log_dir}")
        except Exception as e:
            messagebox.showerror(APP_NAME, f"Could not open logs folder:\n{e}")

    def show_about(self):
        about = tk.Toplevel(self)
        about.title("About")
        about.transient(self)
        about.resizable(False, False)
        about.configure(bg="#e5e7eb")

        try:
            if hasattr(self, "app_icon_image"):
                about.iconphoto(True, self.app_icon_image)
        except Exception:
            pass

        frame = ttk.Frame(about, padding=16)
        frame.pack(fill="both", expand=True)

        icon_holder = ttk.Frame(frame)
        icon_holder.pack(fill="x")

        try:
            about_icon_path = self.asset_path("osinaldi-bluray-multiburner-128.png")
            self.about_icon_image = tk.PhotoImage(file=str(about_icon_path))
            icon_label = ttk.Label(icon_holder, image=self.about_icon_image)
            icon_label.pack(pady=(0, 10))
        except Exception:
            pass

        ttk.Label(
            frame,
            text="Osinaldi BluRay MultiBurner 1.0.24 — May 2026",
            style="Header.TLabel",
        ).pack(anchor="center")

        ttk.Label(
            frame,
            text="Mascot / Program icon: Mirtza Chan (A tribute to my beautiful and beloved wife)",
        ).pack(anchor="center", pady=(6, 4))

        ttk.Label(
            frame,
            text=(
                "A Linux GUI tool for burning multiple Blu-ray ISO images to multiple BD-R writers in parallel.\n\n"
                "Features:\n"
                "- Per-writer ISO assignment\n"
                "- Create ISO images from physical discs\n"
                "- Source Disk Lock\n"
                "- Writer order saving\n"
                "- Safe close protection\n"
                "- growisofs compatibility-focused burning\n\n"
                "Website: https://euroanime.jp.net\n"
                "GitHub: https://github.com/Phantasmum/Osinaldi-Bluray-MultiBurner\n"
                "Contact: phantasmum@proton.me\n"
                "License: MIT\n"
                "Package ID: io.github.osinaldi.bluraymultiburner"
            ),
            justify="center",
            wraplength=560,
        ).pack(anchor="center", pady=(4, 10))

        ttk.Button(frame, text="Close", command=about.destroy, style="Primary.TButton").pack(pady=(2, 0))

        about.update_idletasks()
        w = about.winfo_width()
        h = about.winfo_height()
        x = self.winfo_rootx() + max(20, (self.winfo_width() - w) // 2)
        y = self.winfo_rooty() + max(20, (self.winfo_height() - h) // 2)
        about.geometry(f"+{x}+{y}")
        about.grab_set()

    def test_writer_access(self):
        devices = self.selected_devices()
        if not devices:
            devices = list(self.device_order)

        if not devices:
            messagebox.showerror(APP_NAME, "No Blu-ray writers detected.")
            return

        lines = []
        for dev in devices:
            exists = os.path.exists(dev)
            rw = has_rw_access(dev) if exists else False
            info = "not tested"
            if which("dvd+rw-mediainfo") and exists:
                rc, out = run_command(["dvd+rw-mediainfo", dev], timeout=25)
                if rc == 0 and out.strip():
                    first = out.splitlines()[0] if out.splitlines() else "media info available"
                    info = f"media info OK: {first}"
                else:
                    info = "no media info / no disc / not ready"
            status = "OK" if exists and rw else "NO ACCESS"
            lines.append(f"{dev}: {status} — {info}")

        messagebox.showinfo(APP_NAME, "Writer access test:\n\n" + "\n".join(lines))

    def build_ui(self):
        main = ttk.Frame(self, padding=10)
        main.pack(fill="both", expand=True)

        iso_box = ttk.LabelFrame(main, text="Master ISO / optional copy to all writers")
        iso_box.pack(fill="x", pady=6)

        iso_row = ttk.Frame(iso_box, padding=8)
        iso_row.pack(fill="x")

        self.master_iso_display = ttk.Label(iso_row, text="No master ISO selected", width=54)
        self.master_iso_display.pack(side="left", fill="x", expand=True)
        ttk.Button(
            iso_row,
            text="Select master ISO...",
            command=self.pick_master_iso,
            style="Green.TButton",
        ).pack(side="left", padx=(8, 0))
        ttk.Button(
            iso_row,
            text="Copy master ISO to selected writers",
            command=self.copy_master_iso_to_selected,
            style="Primary.TButton",
        ).pack(side="left", padx=(8, 0))
        ttk.Button(
            iso_row,
            text="Create ISO from disc...",
            command=self.create_iso_from_selected_writer,
            style="Primary.TButton",
        ).pack(side="left", padx=(8, 0))

        self.iso_label = ttk.Label(iso_box, text="")
        self.iso_label.pack_forget()

        drives_box = ttk.LabelFrame(main, text="Detected Blu-ray writers")
        drives_box.pack(fill="both", expand=True, pady=6)

        drive_buttons = ttk.Frame(drives_box, padding=(8, 8, 8, 0))
        drive_buttons.pack(fill="x")

        self.refresh_btn = ttk.Button(drive_buttons, text="Refresh writers", command=self.refresh_devices, style="Primary.TButton")
        self.refresh_btn.pack(side="left")
        self.select_all_btn = ttk.Button(drive_buttons, text="Select all", command=self.select_all, style="SoftGreen.TButton")
        self.select_all_btn.pack(side="left", padx=(8, 0))
        self.select_none_btn = ttk.Button(drive_buttons, text="Select none", command=self.select_none, style="SoftRed.TButton")
        self.select_none_btn.pack(side="left", padx=(8, 0))
        self.check_media_btn = ttk.Button(drive_buttons, text="Check inserted BD-R media", command=self.check_all_media, style="Primary.TButton")
        self.check_media_btn.pack(side="left", padx=(8, 0))

        ttk.Label(
            drive_buttons,
            text="   ▲/▼ = reorder physical stack   ·   Green dot = selected   ·   Red dot = not selected",
            style="SubHeader.TLabel",
        ).pack(side="left", padx=(18, 0))

        self.drives_frame = ttk.Frame(drives_box, padding=8)
        self.drives_frame.pack(fill="both", expand=True)

        header = ttk.Frame(self.drives_frame)
        header.pack(fill="x", pady=(0, 4))
        ttk.Label(header, text="Order", width=8).grid(row=0, column=0, sticky="w")
        ttk.Label(header, text="Select", width=7).grid(row=0, column=1, sticky="w")
        ttk.Label(header, text="Device", width=11).grid(row=0, column=2, sticky="w")
        ttk.Label(header, text="Writer", width=30).grid(row=0, column=3, sticky="w")
        ttk.Label(header, text="Access", width=10).grid(row=0, column=4, sticky="w")
        ttk.Label(header, text="Status", width=16).grid(row=0, column=5, sticky="w")
        ttk.Label(header, text="ISO", width=34).grid(row=0, column=6, sticky="w")
        ttk.Label(header, text="Progress", width=24).grid(row=0, column=7, sticky="w")

        self.drive_list = ttk.Frame(self.drives_frame)
        self.drive_list.pack(fill="both", expand=True)

        opt_box = ttk.LabelFrame(main, text="Writing settings")
        opt_box.pack(fill="x", pady=6)

        opt = ttk.Frame(opt_box, padding=8)
        opt.pack(fill="x")

        ttk.Label(opt, text="Speed mode:").grid(row=0, column=0, sticky="w", padx=(0, 6), pady=4)
        ttk.Combobox(
            opt,
            textvariable=self.speed_mode,
            state="readonly",
            width=28,
            values=[
                "AWS / Max",
                "Request 4x compatibility",
                "Request 2x",
                "Request 6x",
                "Request 8x",
            ],
        ).grid(row=0, column=1, sticky="w", pady=4)

        ttk.Checkbutton(opt, text="Eject when finished", variable=self.eject_after).grid(row=0, column=2, sticky="w", padx=18)


        action = ttk.Frame(main)
        action.pack(fill="x", pady=(12, 8))

        self.start_btn = ttk.Button(action, text="BURN BD-R ON SELECTED WRITERS", command=self.start_selected, style="Green.TButton")
        self.start_btn.pack(side="left")

        self.show_cmd_btn = ttk.Button(action, text="Show commands", command=self.show_commands, style="Primary.TButton")
        self.show_cmd_btn.pack(side="left", padx=(8, 0))

        self.test_access_btn = ttk.Button(action, text="Test writer access", command=self.test_writer_access, style="Primary.TButton")
        self.test_access_btn.pack(side="left", padx=(8, 0))

        self.stop_btn = ttk.Button(action, text="Stop", command=self.stop_all, state="disabled", style="Red.TButton")
        self.stop_btn.pack(side="left", padx=(8, 0))

        right_actions = ttk.Frame(action)
        right_actions.pack(side="right")

        ttk.Button(
            right_actions,
            text="Open logs",
            command=self.open_logs_folder,
            style="Primary.TButton",
        ).pack(side="left", padx=(0, 8))

        try:
            about_icon_path = self.asset_path("osinaldi-bluray-multiburner-48.png")
            if about_icon_path.exists():
                self.about_icon_button_image = tk.PhotoImage(file=str(about_icon_path))
                self.about_icon_button = tk.Label(
                    right_actions,
                    image=self.about_icon_button_image,
                    bd=0,
                    highlightthickness=0,
                    relief="flat",
                    cursor="hand2",
                    bg="#e5e7eb",
                    activebackground="#e5e7eb",
                )
                self.about_icon_button.pack(side="left")
                self.about_icon_button.bind("<Button-1>", lambda _e: self.show_about())
            else:
                ttk.Button(
                    right_actions,
                    text="About",
                    command=self.show_about,
                    style="Primary.TButton",
                ).pack(side="left")
        except Exception:
            ttk.Button(
                right_actions,
                text="About",
                command=self.show_about,
                style="Primary.TButton",
            ).pack(side="left")

        log_box = ttk.LabelFrame(main, text="General log")
        log_box.pack(fill="both", expand=True, pady=6)

        self.log = tk.Text(
            log_box,
            height=16,
            wrap="word",
            bg="#ffffff",
            fg="#111827",
            insertbackground="#111827",
            relief="flat",
            padx=8,
            pady=8,
        )
        self.log.pack(side="left", fill="both", expand=True, padx=(8, 0), pady=8)
        scroll = ttk.Scrollbar(log_box, orient="vertical", command=self.log.yview)
        scroll.pack(side="right", fill="y", padx=(0, 8), pady=8)
        self.log.configure(yscrollcommand=scroll.set)

    def log_msg(self, text):
        self.safe_after(0, self._append_log, str(text))

    def _append_log(self, text):
        try:
            self.log.insert("end", text + "\n")
            self.log.see("end")
        except tk.TclError:
            pass

    def set_status(self, dev, text):
        def apply():
            label = self.device_status.get(dev)
            if label:
                label.config(text=text)
        self.safe_after(0, apply)

    def set_progress(self, dev, value=None, text=None, indeterminate=False, stop_indeterminate=False):
        def apply():
            bar = self.device_progress.get(dev)
            label = self.device_progress_text.get(dev)
            if not bar:
                return

            if stop_indeterminate:
                try:
                    bar.stop()
                except Exception:
                    pass
                bar.configure(mode="determinate")

            if indeterminate:
                bar.configure(mode="indeterminate")
                try:
                    bar.start(12)
                except Exception:
                    pass
            elif value is not None:
                try:
                    bar.stop()
                except Exception:
                    pass
                bar.configure(mode="determinate")
                bar["value"] = max(0, min(100, float(value)))

            if label and text is not None:
                label.config(text=text)

        self.safe_after(0, apply)

    def set_master_iso_path(self, path):
        if path:
            self.iso_path.set(path)
            if hasattr(self, "master_iso_display"):
                self.master_iso_display.config(text=Path(path).name)
            self.log_msg(f"Selected master ISO: {path}")

    def set_device_iso_path(self, dev, path):
        if not path:
            return
        var = self.device_iso_vars.get(dev)
        label = self.device_iso_labels.get(dev)
        if var:
            var.set(path)
        if label:
            label.config(text=Path(path).name)
        self.log_msg(f"[{dev}] ISO assigned: {path}")

    def pick_iso_dialog(self):
        path, err = pick_iso_with_native_linux_dialog()
        if path:
            return path

        if err == "zenity_missing":
            messagebox.showerror(
                APP_NAME,
                "zenity is missing.\n\nInstall it with:\n\nsudo apt install zenity"
            )
        elif err == "cancelled":
            return None
        else:
            messagebox.showerror(APP_NAME, f"Could not open the Ubuntu/Linux file picker:\n{err}")
        return None

    def pick_master_iso(self):
        path = self.pick_iso_dialog()
        if path:
            self.set_master_iso_path(path)

    def pick_iso_for_device(self, dev):
        if self.is_burning:
            return
        path = self.pick_iso_dialog()
        if path:
            self.set_device_iso_path(dev, path)

    def copy_master_iso_to_selected(self):
        if self.is_burning:
            return
        path = self.iso_path.get().strip()
        if not path:
            messagebox.showerror(APP_NAME, "Select a master ISO first.")
            return
        if not os.path.isfile(path):
            messagebox.showerror(APP_NAME, "The master ISO does not exist.")
            return
        devices = self.selected_devices()
        if not devices:
            messagebox.showerror(APP_NAME, "Select at least one writer.")
            return
        for dev in devices:
            self.set_device_iso_path(dev, path)
        self.log_msg(f"Master ISO copied to {len(devices)} selected writer(s).")

    def get_iso_for_device(self, dev):
        var = self.device_iso_vars.get(dev)
        return var.get().strip() if var else ""

    def set_busy_state(self, busy):
        self.is_burning = busy
        state_busy = "disabled" if busy else "normal"
        self.start_btn.config(state=state_busy)
        self.refresh_btn.config(state=state_busy)
        self.select_all_btn.config(state=state_busy)
        self.select_none_btn.config(state=state_busy)
        self.check_media_btn.config(state=state_busy)
        self.show_cmd_btn.config(state=state_busy)
        if hasattr(self, "test_access_btn"):
            self.test_access_btn.config(state=state_busy)
        self.stop_btn.config(state="normal" if busy else "disabled")
        for btn in self.device_iso_buttons.values():
            btn.config(state=state_busy)

        if busy:
            self.title(APP_NAME + " — BURNING, CLOSE LOCKED")
            self.log_msg("Burn lock enabled: window close is blocked until all writers finish.")
        else:
            self.title(APP_NAME)
            self.log_msg("Burn lock disabled: all writers finished.")


    def get_permission_help_text(self):
        return (
            "Optical writer access is not available for the current user.\n\n"
            "Recommended one-time fix:\n"
            "sudo usermod -aG cdrom \"$USER\"\n\n"
            "Then log out and log back in.\n\n"
            "This app does not use pkexec by default because pkexec/root can make "
            "some Linux optical-drive/media detection paths behave differently."
        )

    def check_dependencies(self):
        missing = [cmd for cmd in ["growisofs", "lsblk", "eject", "zenity"] if not which(cmd)]
        if missing:
            self.log_msg("MISSING dependencies: " + ", ".join(missing))
            self.log_msg("Install with:")
            self.log_msg("sudo apt update && sudo apt install python3-tk dvd+rw-tools util-linux eject zenity")
        else:
            self.log_msg("Basic dependencies OK.")
        self.log_msg("Terminal-close protection enabled: launcher detaches GUI and app ignores SIGHUP.")
        self.log_msg("Normal-user burn mode enabled.")

        self.log_msg("Client compatibility burn profile loaded:")
        self.log_msg("  BD-R workflow profile, drive-default speed, -dvd-compat finalization.")
        self.log_msg("  Direct ISO writing, simplified BD-R workflow.")
        self.log_msg("  1.0.24 does not force -speed by default, to behave closer to Windows automatic speed selection.")

        if not which("dvd+rw-mediainfo"):
            self.log_msg("Warning: dvd+rw-mediainfo is missing. Install dvd+rw-tools.")
        self.log_msg("If a writer shows No access, add your user to the cdrom group instead of using pkexec.")


    def create_dot_selector(self, parent, dev, variable):
        """
        macOS-style circular selector:
        green = selected
        red = not selected
        """
        canvas = tk.Canvas(parent, width=24, height=24, bg="#e5e7eb", highlightthickness=0, bd=0)
        oval_id = canvas.create_oval(4, 4, 20, 20, fill="#28c840", outline="#1dad2b", width=1)

        def redraw(*_):
            if variable.get():
                canvas.itemconfig(oval_id, fill="#28c840", outline="#1dad2b")
            else:
                canvas.itemconfig(oval_id, fill="#ff5f57", outline="#e0443e")

        def toggle(_event=None):
            if self.is_burning:
                return
            variable.set(not variable.get())
            redraw()

        canvas.bind("<Button-1>", toggle)
        canvas.bind("<space>", toggle)
        canvas.configure(cursor="hand2")
        variable.trace_add("write", redraw)
        redraw()
        return canvas


    def load_saved_writer_order(self):
        try:
            if self.config_file.exists():
                data = json.loads(self.config_file.read_text(encoding="utf-8"))
                order = data.get("writer_order", [])
                if isinstance(order, list):
                    return [str(x) for x in order]
        except Exception as e:
            # Log is not ready yet during __init__, so fail silently.
            pass
        return []

    def save_writer_order(self):
        try:
            self.config_dir.mkdir(parents=True, exist_ok=True)
            data = {}
            if self.config_file.exists():
                try:
                    data = json.loads(self.config_file.read_text(encoding="utf-8"))
                    if not isinstance(data, dict):
                        data = {}
                except Exception:
                    data = {}

            data["writer_order"] = list(self.device_order)
            self.config_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
            self.saved_writer_order = list(self.device_order)
            self.log_msg("Writer order saved.")
        except Exception as e:
            self.log_msg(f"Could not save writer order: {e}")

    def apply_saved_writer_order(self, devices):
        """
        Applies the saved order to currently detected devices.

        Matching is primarily by /dev/srX because that is what the app uses.
        New or missing writers are handled safely:
        - saved devices found now keep their saved order
        - newly detected devices are appended at the end
        """
        device_map = {dev: desc for dev, desc in devices}
        ordered = []

        for dev in self.saved_writer_order:
            if dev in device_map and dev not in ordered:
                ordered.append(dev)

        for dev, _desc in devices:
            if dev not in ordered:
                ordered.append(dev)

        return [(dev, device_map[dev]) for dev in ordered if dev in device_map]

    def move_device_up(self, dev):
        if self.is_burning:
            return
        if dev not in self.device_order:
            return
        idx = self.device_order.index(dev)
        if idx <= 0:
            return
        self.device_order[idx - 1], self.device_order[idx] = self.device_order[idx], self.device_order[idx - 1]
        self.rebuild_drive_rows_from_order()
        self.save_writer_order()
        self.log_msg(f"Writer order changed: {dev} moved up.")

    def move_device_down(self, dev):
        if self.is_burning:
            return
        if dev not in self.device_order:
            return
        idx = self.device_order.index(dev)
        if idx >= len(self.device_order) - 1:
            return
        self.device_order[idx + 1], self.device_order[idx] = self.device_order[idx], self.device_order[idx + 1]
        self.rebuild_drive_rows_from_order()
        self.save_writer_order()
        self.log_msg(f"Writer order changed: {dev} moved down.")

    def rebuild_drive_rows_from_order(self):
        """
        Rebuilds the visual writer list using self.device_order while preserving:
        - selected/unselected state
        - assigned ISO per writer
        - progress/status widgets reset visually
        """
        saved_selected = {dev: var.get() for dev, var in self.device_vars.items()}
        saved_iso = {dev: var.get() for dev, var in self.device_iso_vars.items()}

        for child in self.drive_list.winfo_children():
            child.destroy()

        old_names = dict(self.device_names)

        self.device_vars.clear()
        self.device_status.clear()
        self.device_progress.clear()
        self.device_progress_text.clear()
        self.device_iso_vars.clear()
        self.device_iso_labels.clear()
        self.device_iso_buttons.clear()

        for dev in list(self.device_order):
            if not os.path.exists(dev):
                continue
            desc = old_names.get(dev, get_device_description(dev))
            self.add_drive_row(dev, desc, saved_selected.get(dev, True), saved_iso.get(dev, ""))

    def clear_drive_rows(self):
        for child in self.drive_list.winfo_children():
            child.destroy()
        self.device_vars.clear()
        self.device_order.clear()
        self.device_names.clear()
        self.device_status.clear()
        self.device_progress.clear()
        self.device_progress_text.clear()
        self.device_iso_vars.clear()
        self.device_iso_labels.clear()
        self.device_iso_buttons.clear()


    def add_drive_row(self, dev, desc, selected=True, iso_path=""):
        self.device_names[dev] = desc

        var = tk.BooleanVar(value=selected)
        self.device_vars[dev] = var

        row = ttk.Frame(self.drive_list)
        row.pack(fill="x", pady=3)

        access = "OK" if has_rw_access(dev) else "No access"

        # Mouse controls to match the physical vertical order of stacked writers.
        order_frame = ttk.Frame(row)
        order_frame.grid(row=0, column=0, sticky="w", padx=(0, 6))
        ttk.Button(
            order_frame,
            text="▲",
            width=2,
            command=lambda d=dev: self.move_device_up(d),
            style="Primary.TButton",
        ).pack(side="left", padx=(0, 2))
        ttk.Button(
            order_frame,
            text="▼",
            width=2,
            command=lambda d=dev: self.move_device_down(d),
            style="Primary.TButton",
        ).pack(side="left", padx=(0, 4))

        self.create_dot_selector(row, dev, var).grid(row=0, column=1, sticky="w", padx=(0, 8))
        ttk.Label(row, text=dev, width=11).grid(row=0, column=2, sticky="w")
        ttk.Label(row, text=desc, width=30).grid(row=0, column=3, sticky="w")
        ttk.Label(row, text=access, width=10).grid(row=0, column=4, sticky="w")

        st = ttk.Label(row, text="Ready", width=16)
        st.grid(row=0, column=5, sticky="w")
        self.device_status[dev] = st

        iso_frame = ttk.Frame(row)
        iso_frame.grid(row=0, column=6, sticky="w", padx=(4, 4))
        iso_var = tk.StringVar(value=iso_path or "")
        iso_label_text = Path(iso_path).name if iso_path else "No ISO"
        iso_label = ttk.Label(iso_frame, text=iso_label_text, width=22)
        iso_label.pack(side="left", padx=(0, 5))
        iso_btn = ttk.Button(
            iso_frame,
            text="Select ISO",
            command=lambda d=dev: self.pick_iso_for_device(d),
            style="Primary.TButton",
        )
        iso_btn.pack(side="left")

        self.device_iso_vars[dev] = iso_var
        self.device_iso_labels[dev] = iso_label
        self.device_iso_buttons[dev] = iso_btn

        prog_frame = ttk.Frame(row)
        prog_frame.grid(row=0, column=7, sticky="ew", padx=(4, 0))
        bar = ttk.Progressbar(
            prog_frame,
            orient="horizontal",
            length=140,
            mode="determinate",
            maximum=100,
            style="Mac.Horizontal.TProgressbar",
        )
        bar.pack(side="left", padx=(0, 6))
        label = ttk.Label(prog_frame, text="0%", width=8)
        label.pack(side="left")

        self.device_progress[dev] = bar
        self.device_progress_text[dev] = label

    def refresh_devices(self):
        if self.is_burning:
            messagebox.showwarning(APP_NAME, "Do not refresh writers while burns are active.")
            return

        self.clear_drive_rows()
        devices = detect_bluray_drives()

        if not devices:
            ttk.Label(self.drive_list, text="No Blu-ray writer /dev/sr* was detected.").pack(anchor="w")
            self.log_msg("No writers detected. Connect the Blu-ray writers and press Refresh.")
            return

        devices = self.apply_saved_writer_order(devices)
        self.device_order = [dev for dev, _desc in devices]

        for dev, desc in devices:
            self.add_drive_row(dev, desc, selected=True, iso_path="")

        self.log_msg(f"Writers detected: {len(devices)}")
        self.log_msg("Use the ▲ / ▼ buttons to match the GUI order with your physical stacked writers.")
        self.log_msg(f"Writer order settings file: {self.config_file}")


    def select_all(self):
        if self.is_burning:
            return
        for var in self.device_vars.values():
            var.set(True)

    def select_none(self):
        if self.is_burning:
            return
        for var in self.device_vars.values():
            var.set(False)

    def selected_devices(self):
        return [dev for dev in self.device_order if dev in self.device_vars and self.device_vars[dev].get()]

    def validate(self):
        devices = self.selected_devices()

        if not devices:
            messagebox.showerror(APP_NAME, "Select at least one Blu-ray writer.")
            return False

        missing_iso = []
        bad_iso = []
        empty_iso = []

        for dev in devices:
            iso = self.get_iso_for_device(dev)
            if not iso:
                missing_iso.append(dev)
                continue
            if not os.path.isfile(iso):
                bad_iso.append(f"{dev}: {iso}")
                continue
            try:
                if os.path.getsize(iso) <= 0:
                    empty_iso.append(f"{dev}: {iso}")
            except OSError:
                bad_iso.append(f"{dev}: {iso}")

        if missing_iso:
            messagebox.showerror(APP_NAME, "These selected writers have no ISO assigned:\n" + "\n".join(missing_iso))
            return False

        if bad_iso:
            messagebox.showerror(APP_NAME, "These assigned ISO files are invalid or missing:\n" + "\n".join(bad_iso))
            return False

        if empty_iso:
            messagebox.showerror(APP_NAME, "These assigned ISO files are empty:\n" + "\n".join(empty_iso))
            return False

        missing_devices = [d for d in devices if not os.path.exists(d)]
        if missing_devices:
            messagebox.showerror(APP_NAME, "These writers no longer exist:\n" + "\n".join(missing_devices))
            return False

        if not which("growisofs"):
            messagebox.showerror(APP_NAME, "growisofs is missing. Install with: sudo apt install dvd+rw-tools")
            return False

        non_iso = []
        for dev in devices:
            iso = self.get_iso_for_device(dev)
            if iso and not iso.lower().endswith(".iso"):
                non_iso.append(f"{dev}: {iso}")

        if non_iso:
            if not messagebox.askyesno(
                APP_NAME,
                "Some assigned files do not end in .iso. Continue anyway?\n\n" + "\n".join(non_iso)
            ):
                return False

        return True

    def sudo_prefix(self):
        if not self.use_sudo.get():
            return []
        if which("pkexec"):
            return ["pkexec"]
        return ["sudo"]

    def build_burn_command(self, dev):
        iso = self.get_iso_for_device(dev)

        # Locked client compatibility profile:
        # - BD-R workflow only
        # - BD-R HTL BD-R workflow
        # - -dvd-compat finalizes/closes the disc
        # - direct ISO writing preserves authored Blu-ray structure
        # - no multisession, direct burning, no test mode
        cmd = ["growisofs", "-dvd-compat"]

        mode = self.speed_mode.get().strip()

        # Default: do not pass -speed.
        # This lets the burner firmware/media strategy choose the speed, closer to Windows/ImgBurn auto mode.
        if mode == "Request 4x compatibility":
            cmd.append("-speed=4")
        elif mode == "Request 2x":
            cmd.append("-speed=2")
        elif mode == "Request 6x":
            cmd.append("-speed=6")
        elif mode == "Request 8x":
            cmd.append("-speed=8")

        cmd += ["-Z", f"{dev}={iso}"]
        return self.sudo_prefix() + cmd

    def build_eject_command(self, dev):
        return self.sudo_prefix() + ["eject", dev]

    def cmd_text(self, cmd):
        return " ".join(shlex.quote(x) for x in cmd)

    def show_commands(self):
        if not self.validate():
            return
        commands = [self.cmd_text(self.build_burn_command(dev)) for dev in self.selected_devices()]
        messagebox.showinfo(APP_NAME, "\n\n".join(commands))

    def reset_progress_for_devices(self, devices):
        for dev in devices:
            self.set_progress(dev, value=0, text="0%", stop_indeterminate=True)


    def check_blank_bdr_media(self, dev):
        """
        Preflight check before starting growisofs.
        1.0.24 runs this as the normal user, not pkexec/root.
        """
        if not which("dvd+rw-mediainfo"):
            return True, "dvd+rw-mediainfo missing; skipping media preflight."

        cmd = ["dvd+rw-mediainfo", dev]
        rc, out = run_command(cmd, timeout=70)
        text = out or ""
        lower = text.lower()

        self.log_msg(f"[{dev}] dvd+rw-mediainfo return code: {rc}")
        if text.strip():
            for line in text.splitlines()[:18]:
                self.log_msg(f"[{dev}] media-info: {line}")

        if rc != 0 or not text.strip():
            return False, f"{dev}: the drive did not report usable media. Check tray, blank BD-R, and permissions."

        if "no media" in lower or "not present" in lower:
            return False, f"{dev}: no disc detected."

        if ("mounted media:" in lower and "dvd" in lower and "bd" not in lower) or ("mounted media:" in lower and "cd" in lower and "bd" not in lower):
            return False, f"{dev}: inserted media is not BD-R/Blu-ray."

        if ("bd-r" in lower) or ("bd-r sequential" in lower) or ("blu-ray" in lower) or ("mounted media:" in lower and "bd" in lower):
            used_markers = [
                "disc status: complete",
                "disc status: appendable",
                "remaining writable size: 0",
            ]
            if any(marker in lower for marker in used_markers):
                return False, f"{dev}: Blu-ray media is not blank/writable."
            return True, f"{dev}: blank/writable Blu-ray media detected."

        if "mounted media:" in lower or "media id:" in lower or "current write speed" in lower:
            return True, f"{dev}: media info detected; allowing burn."

        return False, f"{dev}: media is not recognized as blank BD-R/Blu-ray."

    def preflight_selected_media(self, devices):
        errors = []
        notes = []
        for dev in devices:
            self.set_status(dev, "Checking media...")
            ok, msg = self.check_blank_bdr_media(dev)
            notes.append(msg)
            self.log_msg(msg)
            if not ok:
                errors.append(msg)
                self.set_status(dev, "No BD-R detected")
            else:
                self.set_status(dev, "Media OK")

        if errors:
            messagebox.showerror(
                APP_NAME,
                "Burn was not started because some writers do not have recognized blank BD-R media:\n\n"
                + "\n".join(errors)
                + "\n\nInsert blank BD-R discs, close the trays, wait a few seconds, then try again."
            )
            return False

        return True


    def get_disc_label_for_device(self, dev):
        """
        Attempts to detect a user-friendly inserted disc label/title.
        It uses blkid first and then dvd+rw-mediainfo as a fallback.
        """
        labels = []

        if which("blkid"):
            rc, out = run_command(["blkid", "-o", "export", dev], timeout=20)
            if rc == 0 and out.strip():
                info = {}
                for line in out.splitlines():
                    if "=" in line:
                        k, v = line.split("=", 1)
                        info[k.strip()] = v.strip()
                for key in ["LABEL", "UUID", "TYPE"]:
                    if info.get(key):
                        labels.append(f"{key}: {info[key]}")

        if which("dvd+rw-mediainfo"):
            rc, out = run_command(["dvd+rw-mediainfo", dev], timeout=40)
            if rc == 0 and out.strip():
                for line in out.splitlines():
                    clean = line.strip()
                    low = clean.lower()
                    if (
                        "mounted media:" in low
                        or "media id:" in low
                        or "disc status:" in low
                        or "current write speed:" in low
                        or "read speed" in low
                    ):
                        labels.append(clean)

        if labels:
            return " | ".join(labels[:4])

        return "No disc label detected / drive may be empty or not ready"

    def refresh_create_iso_disc_info(self, combo, info_var):
        dev = combo.get().split(" ", 1)[0].strip()
        if not dev:
            info_var.set("Select a writer/reader.")
            return
        info_var.set("Checking inserted disc...")
        def worker():
            label = self.get_disc_label_for_device(dev)
            self.safe_after(0, lambda: info_var.set(label))
        threading.Thread(target=worker, daemon=True).start()

    def get_disc_size_bytes(self, dev):
        """
        Returns media size in bytes if Linux exposes it.
        Used only for ISO creation progress estimation.
        """
        if which("blockdev"):
            rc, out = run_command(["blockdev", "--getsize64", dev], timeout=20)
            if rc == 0 and out.strip().isdigit():
                return int(out.strip())

        # Fallback: /sys/block/srX/size is in 512-byte sectors.
        try:
            name = Path(dev).name
            size_file = Path("/sys/block") / name / "size"
            if size_file.exists():
                sectors = int(size_file.read_text().strip())
                return sectors * 512
        except Exception:
            pass

        return None

    def pick_iso_output_path(self):
        path, err = save_iso_with_native_linux_dialog()
        if path:
            return path

        if err == "zenity_missing":
            messagebox.showerror(
                APP_NAME,
                "zenity is missing.\n\nInstall it with:\n\nsudo apt install zenity"
            )
        elif err == "cancelled":
            return None
        else:
            messagebox.showerror(APP_NAME, f"Could not open the save dialog:\n{err}")
        return None

    def create_iso_from_selected_writer(self):
        """
        Opens a small dialog for selecting the reader/writer and shows inserted
        disc information before creating an ISO image.
        """
        if self.is_burning or self.running or self.pending_devices:
            messagebox.showwarning(APP_NAME, "A burn or disc operation is already running.")
            return

        available = []
        for dev in self.device_order:
            if dev in self.device_names and os.path.exists(dev):
                available.append((dev, self.device_names.get(dev, "Unknown writer")))

        if not available:
            messagebox.showerror(APP_NAME, "No writer/reader detected.")
            return

        dialog = tk.Toplevel(self)
        dialog.title("Create ISO from physical disc")
        dialog.transient(self)
        dialog.grab_set()
        dialog.resizable(False, False)
        dialog.configure(bg="#e5e7eb")

        frame = ttk.Frame(dialog, padding=14)
        frame.pack(fill="both", expand=True)

        ttk.Label(frame, text="Select source writer/reader:").grid(row=0, column=0, sticky="w", pady=(0, 6))

        combo_values = [f"{dev} — {name}" for dev, name in available]
        source_var = tk.StringVar(value=combo_values[0])
        combo = ttk.Combobox(frame, textvariable=source_var, values=combo_values, state="readonly", width=68)
        combo.grid(row=1, column=0, columnspan=3, sticky="ew", pady=(0, 10))

        ttk.Label(frame, text="Inserted disc:").grid(row=2, column=0, sticky="w", pady=(0, 4))
        info_var = tk.StringVar(value="Checking inserted disc...")
        info_label = ttk.Label(frame, textvariable=info_var, wraplength=560)
        info_label.grid(row=3, column=0, columnspan=3, sticky="ew", pady=(0, 10))

        def refresh_info(_event=None):
            self.refresh_create_iso_disc_info(combo, info_var)

        combo.bind("<<ComboboxSelected>>", refresh_info)

        def cancel():
            dialog.grab_release()
            dialog.destroy()

        def continue_create():
            dev = combo.get().split(" ", 1)[0].strip()
            if not dev:
                messagebox.showerror(APP_NAME, "Select a writer/reader.")
                return

            if not os.path.exists(dev):
                messagebox.showerror(APP_NAME, f"{dev} does not exist.")
                return

            if not os.access(dev, os.R_OK):
                messagebox.showerror(
                    APP_NAME,
                    f"No read access to {dev}.\n\n"
                    "Recommended fix:\n"
                    "sudo usermod -aG cdrom \"$USER\"\n\n"
                    "Then log out and log back in."
                )
                return

            out_path = self.pick_iso_output_path()
            if not out_path:
                return

            writer_name = self.device_names.get(dev, "Unknown writer")
            disc_info = info_var.get()

            msg = (
                f"Source writer/reader:\n{dev} - {writer_name}\n\n"
                f"Inserted disc:\n{disc_info}\n\n"
                f"Output ISO:\n{out_path}\n\n"
                "This can take a while. Closing the window will be blocked while reading.\n\n"
                "Confirm?"
            )

            if not messagebox.askyesno(APP_NAME, msg):
                return

            dialog.grab_release()
            dialog.destroy()

            self.reset_progress_for_devices([dev])

            with self.lock:
                self.active_devices = {dev}
                self.pending_devices = []
                self.running.clear()
                self.stopping = False
                self.iso_creation_active = True

            self.set_busy_state(True)
            self.set_status(dev, "Creating ISO...")
            t = threading.Thread(target=self.create_iso_worker, args=(dev, out_path), daemon=True)
            t.start()

        btns = ttk.Frame(frame)
        btns.grid(row=4, column=0, columnspan=3, sticky="e", pady=(8, 0))
        ttk.Button(btns, text="Refresh disc info", command=refresh_info, style="Primary.TButton").pack(side="left", padx=(0, 8))
        ttk.Button(btns, text="Cancel", command=cancel, style="SoftRed.TButton").pack(side="left", padx=(0, 8))
        ttk.Button(btns, text="Create ISO", command=continue_create, style="Green.TButton").pack(side="left")

        self.safe_after(100, refresh_info)

    def build_create_iso_command(self, dev, out_path):
        # status=progress is supported by GNU coreutils dd on Ubuntu.
        # conv=noerror,sync helps keep reading when minor read errors occur, but users
        # should treat any read-error ISO as suspicious.
        return [
            "dd",
            f"if={dev}",
            f"of={out_path}",
            "bs=4M",
            "status=progress",
            "conv=noerror,sync",
        ]

    def create_iso_worker(self, dev, out_path):
        total_size = self.get_disc_size_bytes(dev)
        cmd = self.build_create_iso_command(dev, out_path)
        self.log_msg(f"[{dev}] $ {self.cmd_text(cmd)}")

        try:
            p = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                start_new_session=True,
            )

            with self.lock:
                self.running[dev] = p

            self.set_progress(dev, indeterminate=True, text="Reading")

            if p.stdout is not None:
                for line in p.stdout:
                    clean = line.rstrip()
                    if clean:
                        self.log_msg(f"[{dev}] {clean}")

                    copied = parse_dd_progress_bytes(clean)
                    if copied is not None and total_size and total_size > 0:
                        pct = min(100.0, copied * 100.0 / total_size)
                        self.set_progress(dev, value=pct, text=f"{pct:.0f}%", stop_indeterminate=True)

            rc = p.wait()

            with self.lock:
                stopping_now = self.stopping

            if stopping_now:
                self.set_status(dev, "Stopped")
                self.set_progress(dev, value=0, text="Stopped", stop_indeterminate=True)
                self.log_msg(f"[{dev}] ISO creation stopped.")
                return

            if rc == 0:
                self.set_status(dev, "ISO created")
                self.set_progress(dev, value=100, text="100%", stop_indeterminate=True)
                self.log_msg(f"[{dev}] ISO created successfully: {out_path}")
                messagebox.showinfo(APP_NAME, f"ISO created successfully:\n\n{out_path}")
            else:
                self.set_status(dev, f"Read error {rc}")
                self.set_progress(dev, value=0, text="Error", stop_indeterminate=True)
                self.log_msg(f"[{dev}] ISO creation ended with error. Code: {rc}")
                messagebox.showerror(APP_NAME, f"ISO creation failed for {dev}.\n\nExit code: {rc}")

        except FileNotFoundError:
            self.set_status(dev, "dd missing")
            self.log_msg(f"[{dev}] ERROR: dd command not found.")
            messagebox.showerror(APP_NAME, "dd command not found.")
        except Exception as e:
            self.set_status(dev, "ISO error")
            self.set_progress(dev, value=0, text="Error", stop_indeterminate=True)
            self.log_msg(f"[{dev}] ISO creation error: {e}")
            messagebox.showerror(APP_NAME, f"ISO creation error:\n{e}")
        finally:
            with self.lock:
                self.running.pop(dev, None)
                self.active_devices.discard(dev)
                self.iso_creation_active = False
            self.safe_after(0, self.check_all_finished)

    def start_selected(self):
        if self.is_burning:
            messagebox.showwarning(APP_NAME, "A burn is already running.")
            return

        if not self.validate():
            return

        devices = self.selected_devices()

        no_access = [d for d in devices if not has_rw_access(d)]
        access_note = ""
        if no_access and not self.use_sudo.get():
            messagebox.showerror(
                APP_NAME,
                "These writers have no normal-user write access:\n"
                + "\n".join(no_access)
                + "\n\n"
                + self.get_permission_help_text()
            )
            return

        assignment_lines = []
        source_lines = []
        for dev in devices:
            iso = self.get_iso_for_device(dev)
            writer_name = self.device_names.get(dev, "Unknown writer")
            iso_name = Path(iso).name
            source_label = self.get_source_label_for_iso(iso)
            assignment_lines.append(
                f"The writer ({dev} - {writer_name}) will burn ISO ({iso_name})"
            )
            source_lines.append(f"{dev}: {source_label}")

        # Source Disk Lock is enabled internally with a fixed limit of 3.
        source_note = ""

        msg = (
            "\n\n".join(assignment_lines)
            + source_note
            + access_note
            + "\n\nConfirm?"
        )

        if not messagebox.askyesno(APP_NAME, msg):
            return

        if not self.preflight_selected_media(devices):
            return

        self.reset_progress_for_devices(devices)

        with self.lock:
            self.active_devices = set(devices)
            self.running.clear()
            self.stopping = False
            self.pending_devices = list(devices)
            self.source_active_counts = {}
            self.device_source_keys = {
                dev: self.get_source_key_for_iso(self.get_iso_for_device(dev))
                for dev in devices
            }

        self.set_busy_state(True)
        self.log_msg("Burn scheduler started.")
        self.schedule_pending_burns()

    def schedule_pending_burns(self):
        with self.lock:
            if self.stopping or not self.pending_devices:
                return

            limit = self.get_source_limit()
            started = []

            for dev in list(self.pending_devices):
                source_key = self.device_source_keys.get(dev, "unknown")
                active_for_source = self.source_active_counts.get(source_key, 0)

                if self.source_lock_enabled.get() and active_for_source >= limit:
                    self.set_status(dev, f"Queued: source limit {limit}")
                    continue

                self.pending_devices.remove(dev)
                self.source_active_counts[source_key] = active_for_source + 1
                started.append(dev)

        for dev in started:
            self.set_status(dev, "Waiting...")
            self.log_msg(f"[{dev}] Started by burn scheduler.")
            t = threading.Thread(target=self.burn_worker, args=(dev,), daemon=True)
            t.start()

    def run_streaming(self, dev, cmd, progress_enabled=True):
        self.log_msg(f"[{dev}] $ {self.cmd_text(cmd)}")

        try:
            p = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                start_new_session=True,
            )

            with self.lock:
                self.running[dev] = p

            if progress_enabled:
                self.set_progress(dev, indeterminate=True, text="Starting")

            last_speed = None

            if p.stdout is not None:
                for line in p.stdout:
                    clean = line.rstrip()
                    self.log_msg(f"[{dev}] {clean}")

                    speed = parse_burn_speed(clean)
                    if speed is not None:
                        last_speed = speed

                    if progress_enabled:
                        pct = parse_growisofs_progress(clean)
                        if pct is not None:
                            label = f"{pct:.0f}%"
                            if last_speed is not None:
                                label += f" {last_speed:.1f}x"
                            self.set_progress(dev, value=pct, text=label, stop_indeterminate=True)

            return p.wait()

        except FileNotFoundError as e:
            self.log_msg(f"[{dev}] ERROR: command not found: {e}")
            return 127
        except PermissionError as e:
            self.log_msg(f"[{dev}] PERMISSION ERROR: {e}")
            return 126
        except Exception as e:
            self.log_msg(f"[{dev}] ERROR: {e}")
            return 999
        finally:
            with self.lock:
                self.running.pop(dev, None)

    def burn_worker(self, dev):
        try:
            with self.lock:
                if self.stopping:
                    self.set_status(dev, "Cancelled")
                    self.set_progress(dev, value=0, text="Cancelled", stop_indeterminate=True)
                    return

            self.set_status(dev, "Burning BD-R...")
            rc = self.run_streaming(dev, self.build_burn_command(dev), progress_enabled=True)

            with self.lock:
                stopping_now = self.stopping

            if stopping_now:
                self.set_status(dev, "Stopped")
                self.set_progress(dev, value=0, text="Stopped", stop_indeterminate=True)
                self.log_msg(f"[{dev}] Burn stopped.")
                return

            if rc == 0:
                self.set_status(dev, "BD-R OK")
                self.set_progress(dev, value=100, text="100%", stop_indeterminate=True)
                self.log_msg(f"[{dev}] BD-R burned successfully.")
            elif rc == 126:
                self.set_status(dev, "Access error")
                self.set_progress(dev, value=0, text="Access", stop_indeterminate=True)
                self.log_msg(f"[{dev}] Access error. Enable sudo/pkexec or add your user to the cdrom group.")
                return
            elif rc == 127:
                self.set_status(dev, "Command missing")
                self.set_progress(dev, value=0, text="Missing", stop_indeterminate=True)
                self.log_msg(f"[{dev}] Required command was not found.")
                return
            else:
                self.set_status(dev, f"Error {rc}")
                self.set_progress(dev, value=0, text="Error", stop_indeterminate=True)
                self.log_msg(f"[{dev}] BD-R burn ended with error. Code: {rc}")
                if rc == 252:
                    self.log_msg(f"[{dev}] Hint: growisofs did not recognize a blank recordable Blu-ray disc in this writer.")
                return

            if self.eject_after.get():
                self.set_status(dev, "Ejecting...")
                erc, out = run_command(self.build_eject_command(dev), timeout=40)
                if out:
                    self.log_msg(f"[{dev}] {out}")
                if erc == 0:
                    self.set_status(dev, "Finished / ejected")
                else:
                    self.set_status(dev, "Finished, not ejected")
                    self.log_msg(f"[{dev}] Could not eject. Code: {erc}")

        finally:
            with self.lock:
                self.active_devices.discard(dev)
                source_key = self.device_source_keys.get(dev)
                if source_key is not None:
                    self.source_active_counts[source_key] = max(
                        0,
                        self.source_active_counts.get(source_key, 0) - 1
                    )
                remaining = len(self.active_devices)

            self.log_msg(f"[{dev}] Process finished. Remaining: {remaining}")
            self.safe_after(0, self.schedule_pending_burns)
            self.safe_after(0, self.check_all_finished)

    def check_all_finished(self):
        with self.lock:
            finished = self.is_burning and not self.active_devices and not self.pending_devices

        if finished:
            with self.lock:
                self.stopping = False
                self.source_active_counts.clear()
                self.device_source_keys.clear()
                self.iso_creation_active = False
            self.set_busy_state(False)
            self.log_msg("All BD-R burns have finished.")

    def stop_all(self):
        with self.lock:
            running_items = list(self.running.items())
            queued_items = list(self.pending_devices)

        if not running_items and not queued_items:
            self.log_msg("No active or queued process to stop.")
            self.check_all_finished()
            return

        messagebox.showwarning(
            APP_NAME,
            "Stopping an active burn/read operation can destroy discs or cancel jobs.\n\n"
            "Only continue if you are absolutely sure."
        )
        typed = simpledialog.askstring(
            APP_NAME,
            "Type exactly STOP BURN to stop all active or queued operations:"
        )

        if typed != "STOP BURN":
            self.log_msg("Stop request cancelled: confirmation text did not match.")
            return

        with self.lock:
            self.stopping = True
            for dev in list(self.pending_devices):
                self.active_devices.discard(dev)
                self.set_status(dev, "Cancelled")
                self.set_progress(dev, value=0, text="Cancelled", stop_indeterminate=True)
            self.pending_devices.clear()

        if not running_items:
            self.log_msg("Queued burns cancelled. No active process to stop.")
            self.check_all_finished()
            return

        self.stop_btn.config(state="disabled")

        for dev, proc in running_items:
            try:
                self.set_status(dev, "Stopping...")
                self.set_progress(dev, indeterminate=True, text="Stopping")
                try:
                    os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
                except Exception:
                    proc.terminate()
                self.log_msg(f"[{dev}] Stop signal sent.")
            except Exception as e:
                self.log_msg(f"[{dev}] Could not stop: {e}")

    def check_all_media(self):
        if self.is_burning:
            messagebox.showwarning(APP_NAME, "Do not check media while burns are active.")
            return

        devices = self.selected_devices()
        if not devices:
            messagebox.showerror(APP_NAME, "Select at least one Blu-ray writer.")
            return

        if not which("dvd+rw-mediainfo"):
            messagebox.showerror(APP_NAME, "dvd+rw-mediainfo is missing. Install dvd+rw-tools.")
            return

        self.check_media_btn.config(state="disabled")
        for dev in devices:
            threading.Thread(target=self.media_info_worker, args=(dev,), daemon=True).start()

        self.safe_after(2500, lambda: self.check_media_btn.config(state="normal"))

    def media_info_worker(self, dev):
        self.set_status(dev, "Checking BD-R...")
        self.set_progress(dev, indeterminate=True, text="Check")
        cmd = ["dvd+rw-mediainfo", dev]
        rc, out = run_command(cmd, timeout=70)
        self.log_msg(f"---- Blu-ray media in {dev} ----")
        self.log_msg(out if out else f"No output. Code: {rc}")
        self.log_msg("-------------------------------")
        self.set_status(dev, "Ready")
        self.set_progress(dev, value=0, text="0%", stop_indeterminate=True)

    def on_close(self):
        with self.lock:
            has_active_or_queued = bool(self.running) or bool(self.pending_devices) or bool(self.active_devices) or self.is_burning

        if has_active_or_queued:
            self.show_burn_lock_warning()
            return

        self.save_writer_order()

        for aid in list(self._after_ids):
            try:
                self.after_cancel(aid)
            except Exception:
                pass
        self._after_ids.clear()
        self.destroy()


if __name__ == "__main__":
    app = MultiBurnerApp()
    app.mainloop()
