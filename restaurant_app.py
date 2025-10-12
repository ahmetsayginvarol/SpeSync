import sys
import ctypes
from ctypes import wintypes

# ------------------------------------------------------------------
# SINGLE‑INSTANCE VIA WIN32 NAMED MUTEX
# ------------------------------------------------------------------
mutex_name = "Global\\MyRestaurantAppMutex"   # pick a truly unique name
kernel32    = ctypes.WinDLL('kernel32', use_last_error=True)

# CreateMutexW returns a handle; if it already exists, GetLastError() == ERROR_ALREADY_EXISTS (183)
h_mutex = kernel32.CreateMutexW(
    ctypes.c_void_p(None),       # no security attributes
    wintypes.BOOL(True),         # take initial ownership
    ctypes.c_wchar_p(mutex_name) # name of the mutex
)
ERROR_ALREADY_EXISTS = 183
if ctypes.get_last_error() == ERROR_ALREADY_EXISTS:
    # another instance is running
    import tkinter as tk
    from tkinter import messagebox
    root = tk.Tk()
    root.withdraw()
    messagebox.showwarning(
        "Already Running",
        "Another instance of this application is already running."
    )
    sys.exit(0)





import logging
from ttkbootstrap.icons import Icon
import threading
from tkinter import ttk
class AutocompleteEntry(ttk.Entry):
    """
    A ttk.Entry widget with autocompletion dropdown.
    - Deduplicates suggestions
    - Smart sort: numeric cabins vs alphabetical names
    - Voyage-scoped guest source (optional)
    - Selection-only mode (enforce_pick): only values chosen from the list are accepted
    """

    def __init__(self, parent, suggestions, *args, textvariable=None,
                 guest_name_var=None, galley_callback=None, meal_period_callback=None,
                 db_manager=None, voyage_scoped=False,
                 enforce_pick=False,
                 **kwargs):

        # Bind the entry to a StringVar
        if textvariable is None:
            self.var = tk.StringVar()
            kwargs['textvariable'] = self.var
        else:
            self.var = textvariable
            kwargs['textvariable'] = self.var

        self.guest_name_var = guest_name_var
        self.galley_callback = galley_callback
        self.meal_period_callback = meal_period_callback
        super().__init__(parent, *args, **kwargs)

        # DB + scoping
        self.db_manager = db_manager
        self.voyage_scoped = voyage_scoped

        # Selection-only mode state
        self.enforce_pick = enforce_pick
        self._last_picked_value = None   # full display string chosen from list
        self._picked_flag = False        # True iff last set came from list
        self._cabin_only = ""            # extracted cabin number

        self.listbox = None

        # Seed suggestions
        if self.voyage_scoped and self._can_query_db():
            self._dedupe_and_set(self._query_guests_for_current_voyage())
        else:
            self._dedupe_and_set(suggestions or [])

        # Events
        self.bind("<KeyRelease>", self._on_keyrelease)
        self.bind("<Down>",       self._on_down)
        self.bind("<FocusOut>",   self._on_focus_out)

        if self.enforce_pick:
            # Validate on Enter / keypad Enter / Tab
            self.bind("<Return>",    self._validate_pick_and_forward)
            self.bind("<KP_Enter>",  self._validate_pick_and_forward)
            self.bind("<Tab>",       self._validate_pick_and_forward)

    # ---------- Public helpers ----------

    def reload_from_db(self):
        """
        Rebuild suggestions for the *current* voyage, if voyage_scoped.
        Call this after you switch voyages.
        """
        if not (self.voyage_scoped and self._can_query_db()):
            return
        self._dedupe_and_set(self._query_guests_for_current_voyage())

    def is_valid_pick(self) -> bool:
        """True if current content was selected from the dropdown (not free-typed)."""
        val = (self.var.get() or "").strip()
        return bool(self._picked_flag and self._last_picked_value == val and self._cabin_only)

    def force_clear_pick(self):
        """Clear selection state & text (useful when starting a new occupant)."""
        self._picked_flag = False
        self._last_picked_value = None
        self._cabin_only = ""
        self.var.set("")
        self._hide_listbox()

    # ---------- Internal: data sourcing ----------

    def _can_query_db(self):
        return bool(self.db_manager) and hasattr(self.db_manager, "get_connection")

    def _query_guests_for_current_voyage(self):
        """
        Return a list of display strings 'CABIN - FIRST LAST' for current voyage only.
        """
        out = []
        try:
            vid = getattr(self.db_manager, "current_voyage_id", None)
            if not vid:
                return out
            p = self.db_manager._param()
            sql = f"""
                SELECT cabin_number, first_name, last_name
                  FROM guests
                 WHERE voyage_id = {p}
                 ORDER BY cabin_number, last_name, first_name
            """
            with self.db_manager.get_connection() as conn:
                cur = conn.cursor()
                cur.execute(sql, (vid,))
                rows = cur.fetchall()

            if self.db_manager.backend == "mysql":
                for cabin, first, last in rows:
                    cabin = str(cabin or "").strip()
                    first = str(first or "").strip()
                    last  = str(last  or "").strip()
                    if cabin and (first or last):
                        out.append(f"{cabin} - {first} {last}".strip())
            else:
                for r in rows:
                    cabin = str(r["cabin_number"] or "").strip()
                    first = str(r["first_name"]   or "").strip()
                    last  = str(r["last_name"]    or "").strip()
                    if cabin and (first or last):
                        out.append(f"{cabin} - {first} {last}".strip())
        except Exception as e:
            logging.error(f"Autocomplete reload_from_db failed: {e}", exc_info=True)
        return out

    def _dedupe_and_set(self, items):
        seen = set()
        self.suggestions = []
        for s in items:
            if s not in seen:
                seen.add(s)
                self.suggestions.append(s)

    # ---------- UI: filtering & listbox ----------

    def _on_keyrelease(self, event):
        # Ignore nav keys
        if event.keysym in ("Up", "Down", "Return", "KP_Enter"):
            return

        # free-typing invalidates pick until user selects from list again
        if self.enforce_pick:
            self._picked_flag = False

        text = (self.var.get() or "").strip()
        if len(text) < 3:
            return self._hide_listbox()

        upper_text = text.upper()

        # 1) Filter suggestions containing the typed text
        raw = [s for s in self.suggestions if upper_text in s.upper()]
        if not raw:
            return self._hide_listbox()

        # 2) Sorting: cabin-first if starts with digits, else name-first
        first_two = text[:2]
        if first_two.isdigit():
            def cabin_num(s):
                part = s.split(" - ", 1)[0]
                try:
                    return int(part)
                except ValueError:
                    return float('inf')
            matches = [s for s in raw if s.startswith(text)]
            if not matches:
                matches = raw.copy()
            matches.sort(key=cabin_num)
        else:
            def display_part(s):
                parts = s.split(" - ", 1)
                return parts[1] if len(parts) == 2 else s
            prefix, contains = [], []
            for s in raw:
                disp = display_part(s).upper()
                if disp.startswith(upper_text):
                    prefix.append((s, disp))
                else:
                    contains.append((s, disp))
            prefix.sort(key=lambda x: x[1])
            contains.sort(key=lambda x: x[1])
            matches = [s for s, _ in (prefix + contains)]

        # 3) Show dropdown
        if not self.listbox:
            self.listbox = tk.Listbox(self.master, height=5)
            self.listbox.bind("<<ListboxSelect>>", self._on_listbox_select)
            self.listbox.bind("<Return>",          self._on_listbox_select)
            self.listbox.bind("<KP_Enter>",        self._on_listbox_select)
            self.listbox.bind("<Double-Button-1>", self._on_listbox_select)
            self.listbox.bind("<Up>",              self._on_listbox_nav)
            self.listbox.bind("<Down>",            self._on_listbox_nav)
            self.listbox.bind("<FocusOut>",        lambda e: self._hide_listbox())

        self.listbox.delete(0, tk.END)
        for m in matches:
            self.listbox.insert(tk.END, m)

        self.listbox.place(in_=self, x=0, y=self.winfo_height(), width=self.winfo_width())

    def _on_down(self, event):
        if self.listbox:
            self.listbox.focus_set()
            self.listbox.selection_set(0)
            self.listbox.activate(0)
        return "break"

    def _on_listbox_nav(self, event):
        if not self.listbox:
            return "break"
        idx = self.listbox.curselection()
        i = idx[0] if idx else 0
        if event.keysym == "Down":
            i = min(i + 1, self.listbox.size() - 1)
        elif event.keysym == "Up":
            i = max(i - 1, 0)
        self.listbox.selection_clear(0, tk.END)
        self.listbox.selection_set(i)
        self.listbox.activate(i)
        return "break"

    def _on_listbox_select(self, event):
        if not self.listbox:
            return
        sel = self.listbox.curselection()
        if not sel:
            return

        value = self.listbox.get(sel[0])
        self.var.set(value)

        # Mark as a valid pick
        self._picked_flag = True
        self._last_picked_value = value

        # Split "CABIN - GUEST"
        if self.guest_name_var and " - " in value:
            cabin_part, guest_part = value.split(" - ", 1)
            self._cabin_only = cabin_part.strip()
            self.guest_name_var.set(guest_part.strip())
        else:
            self._cabin_only = value.strip()
            if self.guest_name_var:
                self.guest_name_var.set("")

        # Populate allergy list if we have a guest target
        if self.guest_name_var:
            root = self.winfo_toplevel()
            lab = getattr(root, "selected_allergies_listbox", None)
            if lab:
                lab.delete(0, tk.END)
                guest = self.guest_name_var.get().strip()
                if guest:
                    try:
                        p = root.db_manager._param()
                        sqlite_mode = (root.db_manager.backend == "sqlite")
                        vid = getattr(root.db_manager, "current_voyage_id", None)
                        use_voyage = bool(vid)

                        if sqlite_mode:
                            if use_voyage:
                                sql = f"""
                                    SELECT allergy_notes
                                      FROM preorders
                                     WHERE cabin_number = {p}
                                       AND guest_name   = {p} COLLATE NOCASE
                                       AND voyage_id    = {p}
                                     ORDER BY id DESC
                                     LIMIT 1
                                """
                                params = (self._cabin_only.strip(), guest, vid)
                            else:
                                sql = f"""
                                    SELECT allergy_notes
                                      FROM preorders
                                     WHERE cabin_number = {p}
                                       AND guest_name   = {p} COLLATE NOCASE
                                     ORDER BY id DESC
                                     LIMIT 1
                                """
                                params = (self._cabin_only.strip(), guest)
                        else:
                            if use_voyage:
                                sql = f"""
                                    SELECT allergy_notes
                                      FROM preorders
                                     WHERE cabin_number = {p}
                                       AND guest_name   = {p}
                                       AND voyage_id    = {p}
                                     ORDER BY id DESC
                                     LIMIT 1
                                """
                                params = (self._cabin_only.strip(), guest, vid)
                            else:
                                sql = f"""
                                    SELECT allergy_notes
                                      FROM preorders
                                     WHERE cabin_number = {p}
                                       AND guest_name   = {p}
                                     ORDER BY id DESC
                                     LIMIT 1
                                """
                                params = (self._cabin_only.strip(), guest)

                        with root.db_manager.get_connection() as conn:
                            cur = conn.cursor()
                            cur.execute(sql, params)
                            row = cur.fetchone()

                        notes = (row[0] if row and root.db_manager.backend == "mysql"
                                 else (row["allergy_notes"] if row else None))
                        if notes:
                            for note in str(notes).split(","):
                                n = note.strip()
                                if n:
                                    lab.insert(tk.END, n)
                    except Exception as e:
                        logging.error(f"Error populating allergies: {e}")

        if self.galley_callback:
            self.galley_callback(value.strip())
        if self.meal_period_callback:
            self.meal_period_callback(value.strip())

        self.icursor(tk.END)
        self._hide_listbox()
        self.focus_set()
        self.selection_range(0, tk.END)

    def _on_focus_out(self, event):
        # Delay until focus really moved
        self.after_idle(self._hide_if_focus_outside)
        # Enforce selection-only if enabled
        if self.enforce_pick:
            self.after_idle(self._enforce_pick_validation)

    def _hide_if_focus_outside(self):
        if self.listbox and self.focus_get() == self.listbox:
            return
        self._hide_listbox()

    def _hide_listbox(self):
        if self.listbox:
            self.listbox.destroy()
            self.listbox = None

    def _validate_pick_and_forward(self, event):
        """Validate enforce_pick on Return/Tab before other handlers."""
        if self.enforce_pick:
            self._enforce_pick_validation()
        return None

    def _enforce_pick_validation(self):
        """
        If enforce_pick, ensure the current text is exactly the last picked value.
        Otherwise revert to last picked or clear.
        """
        val = (self.var.get() or "").strip()
        if not val:
            self._picked_flag = False
            self._last_picked_value = None
            self._cabin_only = ""
            return
        if not self._picked_flag or val != (self._last_picked_value or ""):
            # Revert
            if self._last_picked_value:
                self.var.set(self._last_picked_value)
            else:
                self.var.set("")
                self._cabin_only = ""
            try:
                self.bell()
            except Exception:
                pass

    # ---------- External API parity ----------
    def update_suggestions(self, new_list):
        """Replace suggestions list, deduplicated (used if voyage_scoped=False)."""
        seen = set()
        self.suggestions = []
        for s in new_list:
            if s not in seen:
                seen.add(s)
                self.suggestions.append(s)



class ToolTip:

    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tipwin = None
        widget.bind("<Enter>", self.show)
        widget.bind("<Leave>", self.hide)

    def show(self, event=None):
        if self.tipwin or not self.text:
            return
        x = event.x_root + 10
        y = event.y_root + 10
        self.tipwin = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        label = tk.Label(
            tw, text=self.text, justify='left',
            background="#ffffe0", relief='solid', borderwidth=1,
            font=("Helvetica", 10)
        )
        label.pack(ipadx=4, ipady=2)

    def hide(self, event=None):
        if self.tipwin:
            self.tipwin.destroy()
            self.tipwin = None

# If you’re using ttkbootstrap 1.0+

# “Venue: X | Manager: Y” is typically in a label at (row=0, col=1).
# We'll add a link at (row=0, col=2) or (row=0, col=3) to the right of that label:
# ----------------------------
# Logging Configuration
# ----------------------------
logging.basicConfig(
    filename='restaurant_app.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# ----------------------------
# Constants
# ----------------------------
TIMESLOTS = ["Dinner", "Lunch", "Breakfast"]
GALLEY_SECTIONS = ["Hot", "Cold", "Pastry"]
PASSWORD_MIN_LENGTH = 6  # Example password policy

# ----------------------------
# Utility Function to Determine Database Path
# ----------------------------
def get_database_path():
    """
    Determines the absolute path to the orders.db file.
    - For packaged executables, it points to the executable's directory.
    - For scripts, it points to the parent directory of the script.
    """
    try:
        if getattr(sys, 'frozen', False):
            # Application is running as a bundled executable
            app_dir = Path(sys.executable).parent
        else:
            # Application is running as a script
            app_dir = Path(__file__).resolve().parent.parent

        db_path = app_dir / "orders.db"
        logging.info(f"Database path set to: {db_path}")
        return db_path
    except Exception as e:
        logging.error(f"Error determining database path: {e}")
        raise

logging.basicConfig(
    filename='restaurant_app.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# ----------------------------
# Constants
# ----------------------------
TIMESLOTS = ["Dinner".upper(), "Lunch".upper(), "Breakfast".upper()]
GALLEY_SECTIONS = ["Hot".upper(), "Cold".upper(), "Pastry".upper()]
PASSWORD_MIN_LENGTH = 6

# ----------------------------
# Utility Function to Determine Database Path
# ----------------------------



# ----------------------------
# Database Manager Class
# ----------------------------


import json
import sys
import sqlite3
import logging
from pathlib import Path
from contextlib import contextmanager

# If you need MySQL support, make sure mysql-connector-python is installed:
try:
    import mysql.connector
except ImportError:
    mysql = None

def load_db_config(config_file: str = "db_config.json") -> dict:
    """
    Load database config from JSON next to this file.
    Supports BOM (utf-8-sig) and raises on errors.
    """
    p = Path(__file__).resolve().parent / config_file
    try:
        text = p.read_text(encoding="utf-8-sig")
        return json.loads(text)
    except FileNotFoundError:
        raise RuntimeError(f"Config file not found: {p}")
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Invalid JSON in {p}: {e}")
    except Exception as e:
        raise RuntimeError(f"Failed to load {config_file}: {e}")




import json
import logging
import sqlite3
import sys
from pathlib import Path
from contextlib import contextmanager

import bcrypt

# Try MySQL; if missing, we’ll raise only if you try to use it.
try:
    import mysql.connector as mysql
except Exception:
    mysql = None


class DatabaseManager:
    """
    Hybrid SQLite/MySQL data access for SafeBite.
    You can construct with either:
        DatabaseManager()                          # will look for ./db_config.json
        DatabaseManager("path/to/db_config.json")  # explicit file path
        DatabaseManager({"type":"sqlite", ...})    # direct config dict
    """

    # --------------------------
    # Init & configuration
    # --------------------------
    def __init__(self, config_or_path="db_config.json"):
        self.config = self._load_config(config_or_path)
        self.backend = self.config.get("type", "").lower()
        # Inside class DatabaseManager __init__ (add these safe defaults)
        self.sqlite_busy_timeout_ms = getattr(self, "sqlite_busy_timeout_ms", 15000)  # 15s
        self.sqlite_journal_mode = getattr(self, "sqlite_journal_mode", "WAL")
        self.sqlite_synchronous = getattr(self, "sqlite_synchronous", "NORMAL")  # FULL is safer, slower

        if self.backend == "sqlite":
            # allow override via JSON, else default next to code
            if "sqlite_path" in self.config:
                self.db_path = self.config["sqlite_path"]
            else:
                if getattr(sys, "frozen", False):
                    app_dir = Path(sys.executable).parent
                else:
                    app_dir = Path(__file__).resolve().parent
                # typical layout: admin_app.py next to this file; db one level up ok too
                self.db_path = str((app_dir / "orders.db").resolve())
        elif self.backend == "mysql":
            for key in ("host", "port", "user", "password", "database"):
                if key not in self.config:
                    raise RuntimeError(f"Missing MySQL config key: {key}")
            self.mysql_settings = {
                "host": self.config["host"],
                "port": int(self.config["port"]),
                "user": self.config["user"],
                "password": self.config["password"],
                "database": self.config["database"],
                "use_pure": True,
                "auth_plugin": "mysql_native_password",  # optional
            }

        else:
            raise RuntimeError(f"Unknown database type: {self.config.get('type')}")

        # create core tables used by the admin app
        self._setup_database()

    @staticmethod
    def _load_config(config_or_path):
        if isinstance(config_or_path, dict):
            return config_or_path
        # else treat as path
        cfg_path = Path(config_or_path)
        if not cfg_path.exists():
            # fall back to local defaults
            return {"type": "sqlite"}
        with cfg_path.open("r", encoding="utf-8") as f:
            return json.load(f)

    def _param(self) -> str:
        return "?" if self.backend == "sqlite" else "%s"

    def _get_raw_connection(self):
        if self.backend == "sqlite":
            conn = sqlite3.connect(
                self.db_path,
                timeout=getattr(self, "sqlite_busy_timeout_ms", 15_000) / 1000.0,
                check_same_thread=False
            )
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            try:
                cur.execute("PRAGMA foreign_keys = ON")
                cur.execute(f"PRAGMA busy_timeout = {getattr(self, 'sqlite_busy_timeout_ms', 15000)}")
                cur.execute(f"PRAGMA journal_mode = {getattr(self, 'sqlite_journal_mode', 'WAL')}")
                cur.execute(f"PRAGMA synchronous = {getattr(self, 'sqlite_synchronous', 'NORMAL')}")
                cur.execute("PRAGMA temp_store = MEMORY")
            finally:
                cur.close()
            return conn

        # --- MySQL via mysql-connector only ---
        if mysql is None:
            raise RuntimeError("mysql-connector-python is not installed. pip install mysql-connector-python")

        # IMPORTANT: pass settings only once; do NOT add use_pure again in connect(...)
        return mysql.connect(**self.mysql_settings)

    from contextlib import contextmanager

    @contextmanager
    def get_connection(self):
        conn = self._get_raw_connection()
        try:
            yield conn
            conn.commit()
        except Exception:
            try:
                conn.rollback()
            except Exception:
                pass
            raise
        finally:
            try:
                conn.close()
            except Exception:
                pass

    # --------------------------
    # One-time setup
    # --------------------------
    def _setup_database(self):
        conn = self._get_raw_connection()
        try:
            cur = conn.cursor()

            # Minimal core tables used by admin app.
            # USERS
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username VARCHAR(64) UNIQUE NOT NULL,
                    password_hash VARCHAR(128) NOT NULL,
                    role VARCHAR(32) NOT NULL
                )
            """ if self.backend == "sqlite" else """
                CREATE TABLE IF NOT EXISTS users (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    username VARCHAR(64) UNIQUE NOT NULL,
                    password_hash VARCHAR(128) NOT NULL,
                    role VARCHAR(32) NOT NULL
                )
            """)

            # VENUES
            cur.execute("""
                CREATE TABLE IF NOT EXISTS venues (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name VARCHAR(64) UNIQUE NOT NULL,
                    breakfast_available INTEGER DEFAULT 0,
                    lunch_available INTEGER DEFAULT 0,
                    dinner_available INTEGER DEFAULT 1
                )
            """ if self.backend == "sqlite" else """
                CREATE TABLE IF NOT EXISTS venues (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    name VARCHAR(64) UNIQUE NOT NULL,
                    breakfast_available TINYINT DEFAULT 0,
                    lunch_available TINYINT DEFAULT 0,
                    dinner_available TINYINT DEFAULT 1
                )
            """)

            # ALLERGIES
            cur.execute("""
                CREATE TABLE IF NOT EXISTS allergies (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name VARCHAR(64) UNIQUE NOT NULL
                )
            """ if self.backend == "sqlite" else """
                CREATE TABLE IF NOT EXISTS allergies (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    name VARCHAR(64) UNIQUE NOT NULL
                )
            """)

            # GUESTS
            cur.execute("""
                CREATE TABLE IF NOT EXISTS guests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    cabin_number VARCHAR(16) NOT NULL,
                    first_name VARCHAR(64) NOT NULL,
                    last_name VARCHAR(64) NOT NULL,
                    UNIQUE(cabin_number, first_name, last_name)
                )
            """ if self.backend == "sqlite" else """
                CREATE TABLE IF NOT EXISTS guests (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    cabin_number VARCHAR(16) NOT NULL,
                    first_name VARCHAR(64) NOT NULL,
                    last_name VARCHAR(64) NOT NULL,
                    UNIQUE KEY uniq_guest (cabin_number, first_name, last_name)
                )
            """)

            # PREORDERS (with chef fields present)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS preorders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    manager           VARCHAR(64)  NOT NULL,
                    cabin_number      VARCHAR(16)  NOT NULL,
                    guest_name        VARCHAR(128) NOT NULL,
                    dish              VARCHAR(128) NOT NULL,
                    pax               INT          NOT NULL,
                    allergy_notes     VARCHAR(255),
                    special_requests  VARCHAR(255),
                    service_time_slot VARCHAR(32)  NOT NULL,
                    galley_section    VARCHAR(32)  NOT NULL,
                    standing_order    VARCHAR(32)  NOT NULL,
                    venue_id          INT          NOT NULL,
                    service_date      VARCHAR(16)  NOT NULL,
                    chef_flag         VARCHAR(16)  NOT NULL DEFAULT '',
                    chef_remark       VARCHAR(255) NOT NULL DEFAULT ''
                )
            """ if self.backend == "sqlite" else """
                CREATE TABLE IF NOT EXISTS preorders (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    manager           VARCHAR(64)  NOT NULL,
                    cabin_number      VARCHAR(16)  NOT NULL,
                    guest_name        VARCHAR(128) NOT NULL,
                    dish              VARCHAR(128) NOT NULL,
                    pax               INT          NOT NULL,
                    allergy_notes     VARCHAR(255),
                    special_requests  VARCHAR(255),
                    service_time_slot VARCHAR(32)  NOT NULL,
                    galley_section    VARCHAR(32)  NOT NULL,
                    standing_order    VARCHAR(32)  NOT NULL,
                    venue_id          INT          NOT NULL,
                    service_date      VARCHAR(16)  NOT NULL,
                    chef_flag         VARCHAR(16)  NOT NULL DEFAULT '',
                    chef_remark       VARCHAR(255) NOT NULL DEFAULT ''
                )
            """)
            try:
                cur.execute("ALTER TABLE preorders ADD COLUMN voyage_id " +
                            ("TEXT" if self.backend == "sqlite" else "VARCHAR(64)"))
            except Exception:
                pass

            # app_config
            cur.execute("""
                CREATE TABLE IF NOT EXISTS app_config (
                    `key`   VARCHAR(64) PRIMARY KEY,
                    `value` VARCHAR(255) NOT NULL
                )
            """)

            # import_mappings (avoid CHECK on MySQL)
            if self.backend == "sqlite":
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS import_mappings (
                        id INT PRIMARY KEY CHECK(id = 1),
                        cabin_col      VARCHAR(8) NOT NULL,
                        last_name_col  VARCHAR(8) NOT NULL,
                        first_name_col VARCHAR(8) NOT NULL
                    )
                """)
            else:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS import_mappings (
                        id INT PRIMARY KEY,
                        cabin_col      VARCHAR(8) NOT NULL,
                        last_name_col  VARCHAR(8) NOT NULL,
                        first_name_col VARCHAR(8) NOT NULL
                    )
                """)

            # seed global key
            if self.backend == "sqlite":
                cur.execute("INSERT OR IGNORE INTO app_config (`key`,`value`) VALUES ('last_standing_copy','')")
            else:
                cur.execute("INSERT IGNORE INTO app_config (`key`,`value`) VALUES ('last_standing_copy','')")

            conn.commit()
        except Exception as e:
            logging.error(f"Error in DatabaseManager._setup_database: {e}")
            raise
        finally:
            try:
                cur.close()
            except Exception:
                pass
            try:
                conn.close()
            except Exception:
                pass


    from contextlib import contextmanager
    import sqlite3, os

    @contextmanager
    def get_ro_connection(self):
        if self.backend == "sqlite":
            # Build a read-only URI
            db_path = getattr(self, "db_path")
            uri = f"file:{db_path}?mode=ro"
            conn = sqlite3.connect(
                uri,
                uri=True,
                timeout=getattr(self, "sqlite_busy_timeout_ms", 15000) / 1000.0,
                check_same_thread=False
            )
            try:
                conn.row_factory = sqlite3.Row
                cur = conn.cursor()
                try:
                    cur.execute("PRAGMA query_only = ON")
                    cur.execute("PRAGMA busy_timeout = %d" % getattr(self, "sqlite_busy_timeout_ms", 15000))
                    # WAL readers never block writers, but set this anyway
                    cur.execute("PRAGMA journal_mode = WAL")
                    cur.execute("PRAGMA synchronous = NORMAL")
                    cur.execute("PRAGMA temp_store = MEMORY")
                finally:
                    cur.close()
                yield conn
            finally:
                try:
                    conn.close()
                except Exception:
                    pass
        else:
            # MySQL: normal pooled connection is fine for reads
            with self.get_connection() as conn:
                yield conn

    # --------------------------
    # Users
    # --------------------------
    def add_user(self, username, password, role):
        try:
            with self.get_connection() as conn:
                cur = conn.cursor()
                hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
                p = self._param()
                sql = f"INSERT INTO users (username,password_hash,role) VALUES ({p},{p},{p})"
                cur.execute(sql, (username, hashed, role))
                return True
        except Exception as e:
            if "UNIQUE" in str(e) or "Duplicate" in str(e):
                return False
            logging.error(f"add_user: {e}")
            return False

    def get_user_password_hash(self, username):
        try:
            with self.get_connection() as conn:
                cur = conn.cursor()
                p = self._param()
                cur.execute(f"SELECT password_hash FROM users WHERE username = {p}", (username,))
                row = cur.fetchone()
                if not row:
                    return None
                return row[0] if self.backend == "mysql" else row["password_hash"]
        except Exception as e:
            logging.error(f"Error fetching user '{username}': {e}")
            return None

    def update_user_password(self, username, new_password):
        try:
            with self.get_connection() as conn:
                cur = conn.cursor()
                hashed = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt()).decode()
                p = self._param()
                cur.execute(f"UPDATE users SET password_hash={p} WHERE username={p}", (hashed, username))
                return cur.rowcount == 1
        except Exception as e:
            logging.error(f"update_user_password: {e}")
            return False

    def get_all_users(self):
        try:
            with self.get_connection() as conn:
                cur = conn.cursor()
                cur.execute("SELECT id, username, role FROM users ORDER BY id")
                rows = cur.fetchall()
                if self.backend == "mysql":
                    return [{"id": r[0], "username": r[1], "role": r[2]} for r in rows]
                return [dict(r) for r in rows]
        except Exception as e:
            logging.error(f"get_all_users: {e}")
            return []

    def update_user(self, user_id, new_password, new_role):
        try:
            with self.get_connection() as conn:
                cur = conn.cursor()
                p = self._param()
                if new_password:
                    hashed = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt()).decode()
                    sql = f"UPDATE users SET password_hash={p}, role={p} WHERE id={p}"
                    cur.execute(sql, (hashed, new_role, user_id))
                else:
                    sql = f"UPDATE users SET role={p} WHERE id={p}"
                    cur.execute(sql, (new_role, user_id))
                return True
        except Exception as e:
            logging.error(f"update_user: {e}")
            return False

    def delete_user(self, user_id, _username=None):
        try:
            with self.get_connection() as conn:
                cur = conn.cursor()
                p = self._param()
                cur.execute(f"DELETE FROM users WHERE id={p}", (user_id,))
                return True
        except Exception as e:
            logging.error(f"delete_user: {e}")
            return False

    def verify_user(self, username, password):
        try:
            with self.get_connection() as conn:
                p = self._param()
                sql = f"SELECT password_hash FROM users WHERE username = {p}"
                cur = conn.cursor()
                cur.execute(sql, (username,))
                row = cur.fetchone()
                if row:
                    stored = row[0] if self.backend == "mysql" else row["password_hash"]
                    return bcrypt.checkpw(password.encode('utf-8'), stored.encode('utf-8'))
        except Exception as e:
            logging.error(f"Error verifying user '{username}': {e}")
        return False

    # --------------------------
    # Venues
    # --------------------------
    def add_venue(self, name, bf=0, ln=0, dn=1):
        try:
            with self.get_connection() as conn:
                cur = conn.cursor()
                p = self._param()
                sql = f"""
                    INSERT INTO venues (name,breakfast_available,lunch_available,dinner_available)
                    VALUES ({p},{p},{p},{p})
                """
                cur.execute(sql, (name, bf, ln, dn))
                return True
        except Exception as e:
            if "UNIQUE" in str(e):
                return False
            logging.error(f"add_venue: {e}")
            return False

    def get_config_value(self, key, default=None):
        try:
            with self.get_connection() as conn:
                cur = conn.cursor()
                p = self._param()
                cur.execute(f"SELECT value FROM app_config WHERE `key`={p} LIMIT 1", (key,))
                row = cur.fetchone()
                if not row:
                    return default
                return row[0] if self.backend == "mysql" else row["value"]
        except Exception:
            return default

    def load_current_voyage_from_config(self):
        vid = self.get_config_value("current_voyage_id", "")
        self.current_voyage_id = (vid or "").strip() or None

        return self.current_voyage_id


    def get_all_venues(self):
        try:
            with self.get_connection() as conn:
                cur = conn.cursor()
                cur.execute("SELECT id,name,breakfast_available,lunch_available,dinner_available FROM venues ORDER BY id")
                rows = cur.fetchall()
                if self.backend == "mysql":
                    return [
                        {"id": r[0], "name": r[1], "breakfast_available": r[2],
                         "lunch_available": r[3], "dinner_available": r[4]}
                        for r in rows
                    ]
                return [dict(r) for r in rows]
        except Exception as e:
            logging.error(f"get_all_venues: {e}")
            return []

    def delete_venue(self, vid, vname):
        try:
            with self.get_connection() as conn:
                cur = conn.cursor()
                p = self._param()
                cur.execute(f"SELECT COUNT(*) FROM preorders WHERE venue_id={p}", (vid,))
                cnt = cur.fetchone()[0]
                if cnt > 0:
                    return False, f"Cannot delete venue '{vname}'—it has orders."
                cur.execute(f"DELETE FROM venues WHERE id={p}", (vid,))
                return True, f"Venue '{vname}' deleted."
        except Exception as e:
            logging.error(f"delete_venue: {e}")
            return False, "Error deleting venue"

    def get_venues(self):
        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT id, name FROM venues ORDER BY name")
            rows = cur.fetchall()
        if self.backend == "mysql":
            return [{"id": r[0], "name": r[1]} for r in rows]
        return [dict(r) for r in rows]

    def get_venue_by_id(self, venue_id):
        p = self._param()
        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute(f"""
                SELECT breakfast_available, lunch_available, dinner_available
                FROM venues WHERE id = {p}
            """, (venue_id,))
            row = cur.fetchone()
        if not row:
            return {}
        if self.backend == "mysql":
            return {"breakfast_available": row[0], "lunch_available": row[1], "dinner_available": row[2]}
        return dict(row)

    def get_venue_meal_periods(self, venue_id):
        p = self._param()
        sql = f"""
            SELECT breakfast_available, lunch_available, dinner_available
              FROM venues
             WHERE id = {p}
        """
        try:
            with self.get_connection() as conn:
                cur = conn.cursor()
                cur.execute(sql, (venue_id,))
                row = cur.fetchone()
        except Exception as e:
            logging.error(f"get_venue_meal_periods failed: {e}")
            return {}

        if not row:
            return {}

        if self.backend == "mysql":
            bf, ln, dn = row[0], row[1], row[2]
        else:
            bf = row["breakfast_available"]; ln = row["lunch_available"]; dn = row["dinner_available"]

        periods = {}
        if bf: periods["breakfast"] = "BREAKFAST"
        if ln: periods["lunch"] = "LUNCH"
        if dn: periods["dinner"] = "DINNER"
        return periods

    # --------------------------
    # Allergies
    # --------------------------
    def get_all_allergies(self):
        try:
            with self.get_connection() as conn:
                cur = conn.cursor()
                cur.execute("SELECT id, name FROM allergies ORDER BY id ASC")
                rows = cur.fetchall()
                if self.backend == "mysql":
                    data = [{"id": r[0], "name": r[1]} for r in rows]
                else:
                    data = [dict(r) for r in rows]
        except Exception as e:
            logging.error(f"get_all_allergies: {e}")
            data = []
        return [{"id": 0, "name": "None"}] + data + [{"id": -1, "name": "Other"}]

    def add_allergy(self, name):
        try:
            with self.get_connection() as conn:
                cur = conn.cursor()
                p = self._param()
                cur.execute(f"INSERT INTO allergies (name) VALUES ({p})", (name,))
                return True
        except Exception as e:
            if "UNIQUE" in str(e):
                return False
            logging.error(f"add_allergy: {e}")
            return False

    def delete_allergy(self, aid, aname):
        try:
            with self.get_connection() as conn:
                cur = conn.cursor()
                p = self._param()
                cur.execute(f"SELECT COUNT(*) FROM preorders WHERE allergy_notes LIKE {p}", (f"%{aname}%",))
                cnt = cur.fetchone()[0]
                if cnt > 0:
                    return False, f"Cannot delete allergy '{aname}'—it’s in use."
                cur.execute(f"DELETE FROM allergies WHERE id={p}", (aid,))
                return True, f"Allergy '{aname}' deleted."
        except Exception as e:
            logging.error(f"delete_allergy: {e}")
            return False, "Error deleting allergy"

    def get_allergies(self):
        return self.get_all_allergies()

    def edit_allergy(self, aid, new_name):
        try:
            with self.get_connection() as conn:
                cur = conn.cursor()
                p = self._param()
                cur.execute(f"UPDATE allergies SET name={p} WHERE id={p}", (new_name, aid))
                return True
        except Exception as e:
            logging.error(f"edit_allergy: {e}")
            return False

    def get_users_by_role(self, role):
        with self.get_connection() as conn:
            cur = conn.cursor()
            p = self._param()
            cur.execute(f"""
                SELECT username FROM users WHERE role={p}
            """, (role,))
            return [row[0] for row in cur.fetchall()]

    # --------------------------
    # Guests
    # --------------------------
    def add_guest(self, cab, first, last):
        try:
            with self.get_connection() as conn:
                cur = conn.cursor()
                p = self._param()
                if self.backend == "mysql":
                    sql = f"INSERT IGNORE INTO guests (cabin_number,first_name,last_name) VALUES ({p},{p},{p})"
                else:
                    sql = f"INSERT OR IGNORE INTO guests (cabin_number,first_name,last_name) VALUES ({p},{p},{p})"
                cur.execute(sql, (cab, first, last))
                return True
        except Exception as e:
            logging.error(f"add_guest: {e}")
            return False

    def get_guests_for_cabin(self, cabin_number):
        vid = getattr(self, "current_voyage_id", None)
        if not vid:
            return []
        p = self._param()
        sql = f"""
            SELECT DISTINCT first_name, last_name
              FROM guests
             WHERE cabin_number = {p}
               AND voyage_id    = {p}
             ORDER BY last_name, first_name
        """
        try:
            with self.get_connection() as conn:
                cur = conn.cursor()
                cur.execute(sql, (cabin_number, vid))
                rows = cur.fetchall()
                if self.backend == "mysql":
                    return [{"first_name": r[0], "last_name": r[1]} for r in rows]
                return [dict(r) for r in rows]
        except Exception as e:
            logging.error(f"get_guests_for_cabin: {e}", exc_info=True)
            return []

    def search_guests_by_name(self, needle):
        vid = getattr(self, "current_voyage_id", None)
        if not vid:
            return []
        n = (needle or "").strip()
        if not n:
            return []
        p = self._param()
        like = f"%{n}%"
        if self.backend == "sqlite":
            sql = f"""
                SELECT DISTINCT cabin_number, first_name, last_name
                  FROM guests
                 WHERE voyage_id = {p}
                   AND ((first_name || ' ' || last_name) LIKE {p}
                     OR first_name LIKE {p}
                     OR last_name  LIKE {p})
                 ORDER BY last_name, first_name
            """
            params = (vid, like, like, like)
        else:
            sql = f"""
                SELECT DISTINCT cabin_number, first_name, last_name
                  FROM guests
                 WHERE voyage_id = {p}
                   AND (CONCAT(first_name, ' ', last_name) LIKE {p}
                     OR first_name LIKE {p}
                     OR last_name  LIKE {p})
                 ORDER BY last_name, first_name
            """
            params = (vid, like, like, like)
        try:
            with self.get_connection() as conn:
                cur = conn.cursor()
                cur.execute(sql, params)
                rows = cur.fetchall()
                if self.backend == "mysql":
                    return [{"cabin_number": r[0], "first_name": r[1], "last_name": r[2]} for r in rows]
                return [dict(r) for r in rows]
        except Exception as e:
            logging.error(f"search_guests_by_name: {e}", exc_info=True)
            return []

    def get_guests_by_manager(self, manager):
        vid = getattr(self, "current_voyage_id", None)
        if not vid:
            return []

        p = self._param()
        sql = f"""
            SELECT DISTINCT cabin_number, guest_name 
            FROM preorders 
            WHERE manager = {p} AND voyage_id = {p}
        """
        with self.get_ro_connection() as conn:
            cur = conn.cursor()
            cur.execute(sql, (manager, vid))
            rows = cur.fetchall()
            if self.backend == "mysql":
                return [{"cabin_number": r[0], "guest_name": r[1]} for r in rows]
            return [dict(r) for r in rows]
    def load_guest_cache(self):
        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT cabin_number, first_name, last_name FROM guests")
            self.cached_guests = cur.fetchall()

    # --------------------------
    # Preorders
    # --------------------------
    def insert_preorder(self, preorder):
        try:
            with self.get_connection() as conn:
                cur = conn.cursor()
                p = self._param()
                vid = getattr(self, "current_voyage_id", None)
                if not vid:
                    raise RuntimeError("No current_voyage_id in DatabaseManager; Admin must set voyage.")

                sql = f"""
                    INSERT INTO preorders (
                        cabin_number, guest_name, dish, pax, allergy_notes, special_requests,
                        service_time_slot, galley_section, standing_order, venue_id, service_date, manager,
                        voyage_id
                    ) VALUES (
                        {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}
                    )
                """
                cur.execute(sql, (
                    preorder['cabin_number'],
                    preorder['guest_name'],
                    preorder['dish'],
                    preorder['pax'],
                    preorder['allergy_notes'],
                    preorder['special_requests'],
                    preorder['service_time_slot'],
                    preorder['galley_section'],
                    preorder['standing_order'],
                    preorder['venue_id'],
                    preorder['service_date'],
                    preorder['manager'],
                    vid,  # ← keep as string like 'SU542'
                ))
                return True
        except Exception as e:
            logging.error(f"Error inserting preorder: {e}", exc_info=True)
            return False

    def delete_preorder(self, manager, cabin, guest, dish, pax, allergy, req,
                        ts, galley, stand, venue_id, service_date):
        try:
            with self.get_connection() as conn:
                cur = conn.cursor()
                p = self._param()
                sql = f"""
                    DELETE FROM preorders
                    WHERE manager = {p}
                      AND cabin_number = {p}
                      AND guest_name = {p}
                      AND dish = {p}
                      AND pax = {p}
                      AND allergy_notes = {p}
                      AND special_requests = {p}
                      AND service_time_slot = {p}
                      AND galley_section = {p}
                      AND standing_order = {p}
                      AND venue_id = {p}
                      AND service_date = {p}
                """
                cur.execute(sql, (
                    manager, cabin, guest, dish, pax, allergy, req,
                    ts, galley, stand, venue_id, service_date
                ))
                return cur.rowcount > 0
        except Exception as e:
            logging.error(f"Error deleting preorder: {e}")
            return False

    def update_preorder(self,
                        old_manager, old_cabin, old_guest,
                        old_dish, old_pax, old_allergy, old_requests,
                        old_timeslot, old_galley, old_standing,
                        venue_id, service_date,
                        new_cabin, new_guest, new_dish, new_pax,
                        new_allergy, new_requests,
                        new_timeslot, new_galley, new_standing):
        try:
            with self.get_connection() as conn:
                cur = conn.cursor()
                p = self._param()
                sql = f"""
                    UPDATE preorders
                       SET cabin_number     = {p},
                           guest_name       = {p},
                           dish             = {p},
                           pax              = {p},
                           allergy_notes    = {p},
                           special_requests = {p},
                           service_time_slot= {p},
                           galley_section   = {p},
                           standing_order   = {p}
                     WHERE manager = {p} AND cabin_number = {p} AND guest_name = {p}
                       AND dish    = {p} AND pax = {p} AND allergy_notes = {p}
                       AND special_requests = {p} AND service_time_slot = {p}
                       AND galley_section = {p} AND standing_order = {p}
                       AND venue_id = {p} AND service_date = {p}
                """
                cur.execute(sql, (
                    new_cabin, new_guest, new_dish, new_pax, new_allergy, new_requests,
                    new_timeslot, new_galley, new_standing,
                    old_manager, old_cabin, old_guest, old_dish, old_pax, old_allergy,
                    old_requests, old_timeslot, old_galley, old_standing, venue_id, service_date
                ))
                return cur.rowcount > 0
        except Exception as e:
            logging.error(f"Failed to update preorder: {e}")
            return False

    def get_preorders(self, service_date, venue_id):
        p = self._param()
        vid = getattr(self, "current_voyage_id", None)

        sql = f"""
            SELECT manager, cabin_number, guest_name, dish, pax, allergy_notes, special_requests,
                   service_time_slot, galley_section, standing_order
              FROM preorders
             WHERE service_date = {p}
               AND venue_id      = {p}
        """
        params = [service_date, venue_id]

        if vid:
            sql += f" AND voyage_id = {p}"
            params.append(vid)
        else:
            sql += " AND (voyage_id IS NULL OR voyage_id = '')"

        sql += " ORDER BY id DESC"

        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute(sql, tuple(params))
            return cur.fetchall()

    def get_preorders_by_guest(self, cabin_number, guest_name):
        p = self._param()
        sql = f"""
            SELECT manager, dish, service_time_slot, galley_section, service_date, venue_id,
                   (SELECT name FROM venues WHERE id = preorders.venue_id) AS venue_name,
                   allergy_notes
              FROM preorders
             WHERE cabin_number = {p}
               AND guest_name   = {p}
               AND voyage_id    = {p}
        """
        try:
            with self.get_ro_connection() as conn:  # ← use RO here
                cur = conn.cursor()
                vid = getattr(self, "current_voyage_id", None)
                cur.execute(sql, (cabin_number, guest_name, vid))
                rows = cur.fetchall()
                if self.backend == "mysql":
                    keys = ["manager", "dish", "service_time_slot", "galley_section",
                            "service_date", "venue_id", "venue_name", "allergy_notes"]
                    return [dict(zip(keys, row)) for row in rows]
                return [dict(row) for row in rows]
        except Exception as e:
            logging.error(f"Error fetching guest orders: {e}")
            return []

    def get_galley_for_dish(self, dish, venue_id):
        p = self._param()
        condition = "dish COLLATE NOCASE" if self.backend == "sqlite" else "LOWER(dish)"
        sql = f"""
            SELECT galley_section
              FROM preorders
             WHERE {condition} = {p}
               AND venue_id = {p}
               AND voyage_id = {p}
             ORDER BY service_date DESC, id DESC
             LIMIT 1
        """
        try:
            with self.get_connection() as conn:
                cur = conn.cursor()
                param = dish if self.backend == "sqlite" else dish.lower()
                vid = getattr(self, "current_voyage_id", None)
                cur.execute(sql, (param, venue_id, vid))
                row = cur.fetchone()
                if not row:
                    return None
                return row[0] if self.backend == "mysql" else row["galley_section"]
        except Exception as e:
            logging.error(f"Error fetching galley for dish: {e}")
            return None

    def get_meal_period_for_dish(self, dish, venue_id):
        p = self._param()
        condition = "dish COLLATE NOCASE" if self.backend == "sqlite" else "LOWER(dish)"
        sql = f"""
            SELECT service_time_slot
              FROM preorders
             WHERE {condition} = {p}
               AND venue_id = {p}
               AND voyage_id = {p}
             ORDER BY service_date DESC, id DESC
             LIMIT 1
        """
        try:
            with self.get_connection() as conn:
                cur = conn.cursor()
                param = dish if self.backend == "sqlite" else dish.lower()
                vid = getattr(self, "current_voyage_id", None)  # leave as string like 'SU542'
                cur.execute(sql, (param, venue_id, vid))  # param_or_date → param

                row = cur.fetchone()
                if not row:
                    return None
                return row[0] if self.backend == "mysql" else row["service_time_slot"]
        except Exception as e:
            logging.error(f"Error fetching meal period: {e}")
            return None

    # --------------------------
    # Standing orders & config
    # --------------------------
    def get_last_standing_copy(self):
        try:
            with self.get_connection() as conn:
                cur = conn.cursor()
                cur.execute("SELECT value FROM app_config WHERE `key`='last_standing_copy'")
                row = cur.fetchone()
                return row[0] if row else None
        except Exception as e:
            logging.error(f"Error fetching last_standing_copy: {e}")
            return None

    def get_last_standing_copy_for_venue(self, venue_id):
        p = self._param()
        key_name = f"last_standing_copy_{venue_id}"
        sql = f"SELECT value FROM app_config WHERE `key` = {p}"
        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute(sql, (key_name,))
            row = cur.fetchone()
        return row[0] if row else None

    def set_last_standing_copy_for_venue(self, venue_id, date_str):
        key = f"last_standing_copy_{venue_id}"
        with self.get_connection() as conn:
            cur = conn.cursor()
            if self.backend == "sqlite":
                cur.execute("INSERT OR REPLACE INTO app_config (`key`,`value`) VALUES (?,?)", (key, date_str))
            else:
                cur.execute("""
                    INSERT INTO app_config (`key`,`value`)
                    VALUES (%s, %s)
                    ON DUPLICATE KEY UPDATE `value` = VALUES(`value`)
                """, (key, date_str))

    def get_standing_orders(self, service_date, venue_id):
        p = self._param()
        sql = f"""
            SELECT *
              FROM preorders
             WHERE service_date = {p}
               AND venue_id      = {p}
               AND (standing_order = 'YES' OR standing_order = 1)
        """
        try:
            with self.get_connection() as conn:
                cur = conn.cursor()
                cur.execute(sql, (service_date, venue_id))
                return cur.fetchall()
        except Exception as e:
            logging.error(f"Error fetching standing orders: {e}")
            return []

    def carry_standing_orders(self, today, tomorrow, venue_id, voyage_id=None):
        """
        Copy standing orders for `venue_id` from 'today' to 'tomorrow',
        strictly within a single voyage.

        Backward compatible:
          - if voyage_id is None, uses self.current_voyage_id
        Returns number of rows copied.
        """
        try:
            vid = voyage_id if voyage_id is not None else getattr(self, "current_voyage_id", None)
            if not vid:
                logging.warning("carry_standing_orders: current_voyage_id is not set.")
                return 0

            p = self._param()
            with self.get_connection() as conn:
                cur = conn.cursor()

                # 1) Read today's standing orders for this venue & voyage
                sql_select = f"""
                    SELECT cabin_number, dish, pax, allergy_notes, special_requests,
                           service_time_slot, galley_section, standing_order,
                           venue_id, manager, guest_name
                      FROM preorders
                     WHERE service_date = {p}
                       AND (standing_order = 'YES' OR standing_order = 1)
                       AND venue_id     = {p}
                       AND voyage_id    = {p}
                """
                cur.execute(sql_select, (today, venue_id, vid))
                rows = cur.fetchall()
                if not rows:
                    return 0

                # 2) Insert copies for 'tomorrow' (same voyage)
                placeholders = ",".join([p] * 13)
                sql_insert = f"""
                    INSERT INTO preorders (
                        cabin_number, dish, pax, allergy_notes, special_requests,
                        service_time_slot, galley_section, standing_order,
                        venue_id, service_date, manager, guest_name, voyage_id
                    )
                    VALUES ({placeholders})
                """

                copied = 0
                for r in rows:
                    if self.backend == "mysql":
                        (cabin_number, dish, pax, allergy_notes, special_requests,
                         service_time_slot, galley_section, _standing_order,
                         v_id, manager, guest_name) = r
                    else:
                        cabin_number = r["cabin_number"]
                        dish = r["dish"]
                        pax = r["pax"]
                        allergy_notes = r["allergy_notes"]
                        special_requests = r["special_requests"]
                        service_time_slot = r["service_time_slot"]
                        galley_section = r["galley_section"]
                        v_id = r["venue_id"]
                        manager = r["manager"]
                        guest_name = r["guest_name"]

                    cur.execute(sql_insert, (
                        cabin_number, dish, pax, allergy_notes, special_requests,
                        service_time_slot, galley_section, "YES",
                        v_id, tomorrow, manager, guest_name, vid
                    ))
                    copied += 1

                # 3) Remember we copied for THIS venue+voyage today
                key_for_venue = f"last_standing_copy_{venue_id}_{vid}"
                if self.backend == "sqlite":
                    cur.execute(
                        "INSERT OR REPLACE INTO app_config (`key`,`value`) VALUES (?,?)",
                        (key_for_venue, today)
                    )
                else:
                    cur.execute(
                        "INSERT INTO app_config (`key`,`value`) VALUES (%s,%s) "
                        "ON DUPLICATE KEY UPDATE `value`=VALUES(`value`)",
                        (key_for_venue, today)
                    )

                conn.commit()
                return copied

        except Exception as e:
            logging.error(f"Error carrying standing orders: {e}", exc_info=True)
            return 0

    # --------------------------
    # Import mapping helpers
    # --------------------------
    def save_last_mapping(self, *, cabin_col, last_name_col, first_name_col):
        with self.get_connection() as conn:
            cur = conn.cursor()
            p = self._param()
            if self.backend == "sqlite":
                sql = f"""
                    INSERT OR REPLACE INTO import_mappings (id, cabin_col, last_name_col, first_name_col)
                    VALUES (1, {p}, {p}, {p})
                """
                cur.execute(sql, (cabin_col, last_name_col, first_name_col))
            else:
                sql = f"""
                    INSERT INTO import_mappings (id, cabin_col, last_name_col, first_name_col)
                    VALUES (1, {p}, {p}, {p})
                    ON DUPLICATE KEY UPDATE
                        cabin_col = VALUES(cabin_col),
                        last_name_col = VALUES(last_name_col),
                        first_name_col = VALUES(first_name_col)
                """
                cur.execute(sql, (cabin_col, last_name_col, first_name_col))

    def load_last_mapping(self):
        try:
            with self.get_connection() as conn:
                cur = conn.cursor()
                cur.execute("SELECT cabin_col,last_name_col,first_name_col FROM import_mappings WHERE id=1")
                row = cur.fetchone()
                if not row:
                    return {}
                if self.backend == "mysql":
                    return {"cabin": row[0], "last": row[1], "first": row[2]}
                return {"cabin": row["cabin_col"], "last": row["last_name_col"], "first": row["first_name_col"]}
        except Exception as e:
            logging.error(f"load_last_mapping: {e}")
            return {}

    # --------------------------
    # Reports / resets
    # --------------------------
    def get_all_orders_sorted_by_date(self):
        try:
            with self.get_connection() as conn:
                cur = conn.cursor()
                cur.execute("""
                    SELECT p.id,p.manager,p.cabin_number,p.guest_name,p.dish,p.pax,
                           p.allergy_notes,p.special_requests,p.service_time_slot,
                           p.galley_section,p.standing_order,p.service_date,
                           v.name AS venue_name
                      FROM preorders p
                 LEFT JOIN venues v ON p.venue_id=v.id
                     ORDER BY p.service_date,p.service_time_slot,p.galley_section
                """)
                rows = cur.fetchall()
                if self.backend == "mysql":
                    return [{
                        "id": r[0], "manager": r[1], "cabin_number": r[2], "guest_name": r[3],
                        "dish": r[4], "pax": r[5], "allergy_notes": r[6], "special_requests": r[7],
                        "service_time_slot": r[8], "galley_section": r[9], "standing_order": r[10],
                        "service_date": r[11], "venue_name": r[12]
                    } for r in rows]
                return [dict(r) for r in rows]
        except Exception as e:
            logging.error(f"get_all_orders_sorted_by_date: {e}")
            return []

    def reset_orders(self):
        try:
            with self.get_connection() as conn:
                cur = conn.cursor()
                cur.execute("DELETE FROM preorders")
                cur.execute("DELETE FROM guests")
                return True
        except Exception as e:
            logging.error(f"reset_orders: {e}")
            return False

# ----------------------------
# Main RestaurantApp Class
# ----------------------------
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from ttkbootstrap import Style
from ttkbootstrap.constants import *
import logging
from datetime import datetime, timedelta
from PIL import Image, ImageTk



# Presume these come from your existing code or imports:
# from your_module import get_database_path, DatabaseManager, get_next_day_date


PASSWORD_MIN_LENGTH = 6  # example
import ctypes


from zoneinfo import ZoneInfo
class RestaurantApp(tk.Tk):
    def __init__(self):
        super().__init__()
        hour = datetime.now().hour
        theme = "flatly"
        self.style = Style(theme)
        print(theme)
        self.dish_var = tk.StringVar()  # the textvariable for the dish-combobox
        self.today_dishes = []
        self.cabin_number_var = tk.StringVar()
        self.temp_dishes = []
        self.dish_var = tk.StringVar()
        self.pax_var = tk.StringVar()
        self.special_requests_var = tk.StringVar()
        self.timeslot_var = tk.StringVar()
        self.galley_section_var = tk.StringVar(value=GALLEY_SECTIONS[0].upper())
        self.standing_order_var = tk.BooleanVar()
        self.guest_name_var = tk.StringVar()

        self.tree_expanded = False
        self.show_only_unsaved = False
        # Initialize ttkbootstrap Style



        self.style.configure('Active.TEntry', foreground='black', background='#FFFF99')  # Yellow highlight
        self.style.configure('Active.TCombobox', fieldbackground='#FFFF99', background='white')
        self.programmatic_cabin_set = False
        # New state tracking variables
        self.unsaved_orders_exist = tk.BooleanVar(value=False)
        self.valid_cabin_entered = tk.BooleanVar(value=False)

        # Add these traces
        self.cabin_number_var.trace_add('write', self.validate_buttons)
        self.unsaved_orders_exist.trace_add('write', self.validate_buttons)

        self.title("SpeSync Suite")
        self.geometry("1250x1000")
        self.resizable(True, True)
        self.iconbitmap('icons/icon_app.ico')

        # Initialize DB Manager
        db_path = get_database_path()
        # no db_path passed here:
        self.db_manager = DatabaseManager()
        self.service_date_var = tk.StringVar(value=self._next_service_date())
        self.db_manager = DatabaseManager()
        vid = self.db_manager.load_current_voyage_from_config()
        if not vid:
            # Non-fatal: app can still run, but INSERTs will fail if voyage_id is NOT NULL.
            logging.warning("No current_voyage_id found in app_config. Ask Admin to set Voyage.")

        self.venue_id = None
        self.venue_name = None
        self.manager = None
        # after building right_info_frame / server_time_label:


        # All allergies from the DB
        self.allergies = []
        self.db_manager.load_guest_cache()
        # Guest name radio choice, occupant-level
        self.guest_name_var = tk.StringVar()
        self.cached_guests = []  # ← Memory cache
        # Orders stored as:
        # (manager, cabin, guest_name, dish, pax, allergy, requests, timeslot, galley_section, standing, from_db)
        self.all_orders = []
        self.occupant_locked = False
        self.temp_dishes = []  # Will hold dish-level items for the current occupant

        # Track unsaved data
        self.unsaved_data = False

        # On close event
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

        self.show_login_and_venue_screen()

        self.guest_name_var = tk.StringVar(value="")  # For displaying the guest name
        icon_obj = Icon()  # Instantiate without arguments
        self.db_icon = tk.PhotoImage(file="icons/database.png")
        self.unsaved_icon = tk.PhotoImage(file="icons/edit.png")
        self._treeview_icons = [self.db_icon, self.unsaved_icon]

    def _get_current_venue_id(self):
        """
        Resolve the current venue id from common places in the app.
        Returns an int or str (param-safe) or None if unavailable.
        """
        # Try explicit attribute first
        v = getattr(self, "current_venue_id", None)
        if v not in (None, "", 0):
            return v
        # Try a tk variable you might be using
        try:
            if hasattr(self, "venue_id_var"):
                val = self.venue_id_var.get()
                if str(val).strip():
                    return val
        except Exception:
            pass
        # Try config as last resort
        try:
            val = self.db_manager.get_config_value("current_venue_id", "")
            if str(val).strip():
                return val
        except Exception:
            pass
        return None

    def _get_service_timezone(self) -> str | None:
        """
        MySQL: prefer app_config.server_time_zone, fallback app_config.service_timezone.
        SQLite: return None (use PC clock).
        """
        dbm = getattr(self, "db_manager", None)
        if dbm and getattr(dbm, "backend", "").lower() == "mysql":
            try:
                with dbm.get_connection() as conn:
                    cur = conn.cursor()

                    def _val_from_row(row):
                        if row is None:
                            return None
                        # support dict or tuple rows
                        if isinstance(row, dict):
                            return row.get("value")
                        try:
                            return row[0]
                        except Exception:
                            return None

                    # 1) Preferred key from admin_app
                    cur.execute("SELECT value FROM app_config WHERE `key`='server_time_zone' LIMIT 1")
                    row = cur.fetchone()
                    v = _val_from_row(row)
                    if v:
                        return str(v)

                    # 2) Backward-compat key
                    cur.execute("SELECT value FROM app_config WHERE `key`='service_timezone' LIMIT 1")
                    row = cur.fetchone()
                    v = _val_from_row(row)
                    if v:
                        return str(v)
            except Exception:
                pass
        return None  # → use PC clock

    def _get_cutoff_hour(self) -> int:
        """
        MySQL: read app_config.cutoff_hour if present; fallback 4.
        SQLite: fallback 4.
        """
        default_cutoff = 4
        dbm = getattr(self, "db_manager", None)
        if dbm and getattr(dbm, "backend", "").lower() == "mysql":
            try:
                with dbm.get_connection() as conn:
                    cur = conn.cursor()

                    def _val_from_row(row):
                        if row is None:
                            return None
                        if isinstance(row, dict):
                            return row.get("value")
                        try:
                            return row[0]
                        except Exception:
                            return None

                    cur.execute("SELECT value FROM app_config WHERE `key`='cutoff_hour' LIMIT 1")
                    row = cur.fetchone()
                    v = _val_from_row(row)
                    if v is not None and str(v).strip().isdigit():
                        return int(v)
            except Exception:
                pass
        return default_cutoff

    def _now_local(self) -> datetime:
        """
        If MySQL + service_timezone is set → use that tz.
        Else → use PC local time.
        """
        tz = self._get_service_timezone()
        return datetime.now(ZoneInfo(tz)) if tz else datetime.now()

    def _service_date_for(self, dt: datetime, cutoff_hour: int) -> str:
        target = dt.date() if dt.hour < cutoff_hour else (dt.date() + timedelta(days=1))
        return target.strftime("%Y-%m-%d")

    def _next_service_date(self) -> str:
        """Convenience: compute service date using hybrid clock + cutoff."""
        return self._service_date_for(self._now_local(), self._get_cutoff_hour())

    # ---------------------------- LOGIN ----------------------------


    # Cache DB time for a short period to avoid hammering the DB
    def _db_utc_now(self) -> datetime | None:
        """
        Return authoritative UTC 'now' from MySQL (UTC_TIMESTAMP()).
        Returns None on SQLite or if the query fails.
        """
        from datetime import datetime, timedelta, timezone  # make sure these are imported
        from zoneinfo import ZoneInfo
        dbm = getattr(self, "db_manager", None)
        if not (dbm and getattr(dbm, "backend", "").lower() == "mysql"):
            return None
        try:
            with dbm.get_connection() as conn:
                cur = conn.cursor()
                cur.execute("SELECT UTC_TIMESTAMP()")
                row = cur.fetchone()
            # row can be a tuple or dict
            val = row.get("UTC_TIMESTAMP()") if isinstance(row, dict) else row[0]
            # Ensure timezone-aware UTC
            if isinstance(val, datetime):
                if val.tzinfo is None:
                    return val.replace(tzinfo=timezone.utc)
                return val.astimezone(timezone.utc)
            # Fallback parse (rare)
            return datetime.fromisoformat(str(val)).replace(tzinfo=timezone.utc)
        except Exception:
            return None

    def _now_local(self) -> datetime:
        """
        HYBRID 'now':
        - If MySQL: use DB UTC time (UTC_TIMESTAMP()) and convert to app_config server_time_zone.
        - If SQLite: use PC clock.
        """
        from datetime import datetime, timedelta, timezone  # make sure these are imported
        from zoneinfo import ZoneInfo
        tz = self._get_service_timezone()  # e.g., 'Europe/Athens' or None
        if getattr(self, "db_manager", None) and getattr(self.db_manager, "backend", "").lower() == "mysql":
            db_utc = self._db_utc_now()
            if db_utc is not None:
                return db_utc.astimezone(ZoneInfo(tz)) if tz else db_utc.astimezone()
        # Fallbacks: PC clock -> convert to tz if provided
        now_pc = datetime.now(timezone.utc).astimezone(ZoneInfo(tz)) if tz else datetime.now()
        return now_pc

    def _selected_or_next_service_date(self):
        s = (self.service_date_var.get() or "").strip() if hasattr(self, "service_date_var") else ""
        return s or self.get_next_day_date()

    def on_dropdown_select(self):
        """Set the username entry field with the selected username from the dropdown."""
        selected_user = self.dropdown_var.get()
        if selected_user:
            self.manager_var.set(selected_user)



    def attempt_login(self):
        username = self.manager_var.get().strip()
        pw = self.password_var.get().strip()

        if not username or not pw:
            messagebox.showwarning("Validation Error", "Username and password required.")
            return

        if self.db_manager.verify_user(username, pw):
            self.manager = username
            logging.info(f"Manager '{username}' logged in.")

            self.show_venue_selection()
        else:
            logging.warning(f"Failed login attempt for {username}.")
            messagebox.showerror("Login Failed", "Invalid username or password.")

    def show_login_and_venue_screen(self):
        """
        Single-screen login + venue selection (no banner resizing).
        Uses icons from ./icons:
          - pass_banner.png (500x500)
          - user.png
          - password.png
          - venue.png
          - enter2.png
        """
        import os, logging
        import tkinter as tk
        from tkinter import ttk, messagebox
        from PIL import Image, ImageTk

        try:
            import bcrypt
        except Exception:
            bcrypt = None

        theme = "flatly"

        # Clear existing widgets
        for w in self.winfo_children():
            w.destroy()

        # Theme (ttkbootstrap if available)
        if not getattr(self, "_login_theme_initialized", False):
            try:
                from ttkbootstrap import Style as BootStyle
                self.style = BootStyle(theme)
                self.current_theme = theme
            except Exception:
                self.style = ttk.Style()
                self.current_theme = "default"
            self._login_theme_initialized = True

        # Match bg
        try:
            self.configure(bg=self.style.colors.bg)
        except Exception:
            pass

        self.grid_rowconfigure(0, weight=0)
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # Image loader
        def _load_pil(path):
            img = Image.open(path)
            return ImageTk.PhotoImage(img)

        # Banner
        try:
            self._login_banner_photo = _load_pil(os.path.join("icons", "pass_banner.png"))
        except Exception:
            self._login_banner_photo = ImageTk.PhotoImage(Image.new("RGBA", (10, 10), (0, 0, 0, 0)))

        # Small icons
        def _safe_load(name):
            try:
                return _load_pil(os.path.join("icons", name))
            except Exception:
                return None

        self._img_user = _safe_load("user.png")
        self._img_password = _safe_load("password.png")
        self._img_venue = _safe_load("venue.png")
        self._img_enter = _safe_load("enter2.png")

        # Banner frame
        banner_frame = ttk.Frame(self, padding=(0, 10))
        banner_frame.grid(row=0, column=0, sticky="n")
        ttk.Label(banner_frame, image=self._login_banner_photo).pack()

        # Content
        content = ttk.Frame(self, padding=(20, 10))
        content.grid(row=1, column=0, sticky="n")
        content.grid_columnconfigure(0, weight=1)

        # LOGIN box
        login_box = ttk.Labelframe(content, text="Manager Login", padding=(20, 16))
        login_box.grid(row=0, column=0, sticky="nwe", pady=(0, 14))
        login_box.grid_columnconfigure(1, weight=1)

        ttk.Label(
            login_box, text="Username:", image=self._img_user, compound=tk.LEFT, font=("Helvetica", 12)
        ).grid(row=0, column=0, padx=(0, 8), pady=(2, 10), sticky="e")
        username_var = tk.StringVar(value="")
        username_ent = ttk.Entry(login_box, textvariable=username_var, font=("Helvetica", 12), width=28)
        username_ent.grid(row=0, column=1, pady=(2, 10), sticky="we")
        username_ent.focus()

        ttk.Label(
            login_box, text="Password:", image=self._img_password, compound=tk.LEFT, font=("Helvetica", 12)
        ).grid(row=1, column=0, padx=(0, 8), pady=(0, 8), sticky="e")
        password_var = tk.StringVar(value="")
        password_ent = ttk.Entry(login_box, textvariable=password_var, show="*", font=("Helvetica", 12), width=28)
        password_ent.grid(row=1, column=1, pady=(0, 8), sticky="we")

        show_pw_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            login_box, text="Show password", variable=show_pw_var,
            command=lambda: password_ent.configure(show="" if show_pw_var.get() else "*")
        ).grid(row=2, column=1, sticky="w", pady=(0, 6))

        # VENUE box
        venue_box = ttk.Labelframe(content, text="Venue Selection", padding=(20, 16))
        venue_box.grid(row=1, column=0, sticky="nwe")
        venue_box.grid_columnconfigure(1, weight=1)

        #manager_label_var = tk.StringVar(value="Logged in as: —")
        #ttk.Label(venue_box, textvariable=manager_label_var, font=("Helvetica", 12, "italic")) \
        #   .grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 10))

        ttk.Label(
            venue_box, text="Select Venue:", image=self._img_venue, compound=tk.LEFT, font=("Helvetica", 12)
        ).grid(row=1, column=0, padx=(0, 8), pady=(0, 10), sticky="e")

        try:
            venues = self.db_manager.get_venues() or []
        except Exception:
            venues = []
            logging.exception("get_venues failed")

        venue_names = [r["name"] if isinstance(r, dict) else r[1] for r in venues]
        venue_map = {(r["name"] if isinstance(r, dict) else r[1]): (r["id"] if isinstance(r, dict) else r[0]) for r in
                     venues}
        selected_venue_var = tk.StringVar(value=(venue_names[0] if venue_names else ""))

        venue_cmb = ttk.Combobox(
            venue_box, textvariable=selected_venue_var, values=venue_names,
            state=("readonly" if venue_names else "disabled"),
            width=28, font=("Helvetica", 12)
        )
        venue_cmb.grid(row=1, column=1, pady=(0, 10), sticky="we")

        # Button row
        btns = ttk.Frame(content)
        btns.grid(row=2, column=0, pady=(12, 0))

        login_btn = ttk.Button(btns, text="  LOGIN  ", image=self._img_enter, compound=tk.LEFT)
        login_btn.grid(row=0, column=0, padx=(0, 10))

        # Auth helper
        def _validate_credentials(u, p):
            if not bcrypt:
                messagebox.showerror("Missing dependency", "bcrypt is not installed.")
                return False, None
            if not u or not p:
                messagebox.showwarning("Incomplete", "Please enter both username and password.")
                return False, None
            try:
                with self.db_manager.get_connection() as conn:
                    cur = conn.cursor()
                    q = f"SELECT username, password_hash, role FROM users WHERE username={self.db_manager._param()}"
                    cur.execute(q, (u,))
                    row = cur.fetchone()
            except Exception:
                logging.exception("Login query failed")
                messagebox.showerror("Database Error", "Unable to query users table.")
                return False, None

            if not row:
                messagebox.showerror("Login Failed", "Invalid username or password.")
                return False, None

            if isinstance(row, dict):
                pw_hash = row.get("password_hash") or row.get("password")
                role = row.get("role")
            else:
                pw_hash = row[1]
                role = (row[2] if len(row) > 2 else None)

            try:
                ok = bcrypt.checkpw(p.encode("utf-8"), (pw_hash or "").encode("utf-8"))
            except Exception:
                ok = False

            if not ok:
                messagebox.showerror("Login Failed", "Invalid username or password.")
                return False, None
            return True, role

        def _on_login():
            u = username_var.get().strip()
            p = password_var.get()
            ok, role = _validate_credentials(u, p)
            if not ok:
                return
            self.manager = u
            self.role = role
            #manager_label_var.set(f"Logged in as: {self.manager}" + (f"  ({role})" if role else ""))

            name = selected_venue_var.get()
            if not name:
                messagebox.showwarning("Select venue", "Please select a venue.")
                return
            vid = venue_map.get(name)
            if not vid:
                messagebox.showerror("No Venues", "No venues found in the database.")
                return

            self.selected_venue_var = selected_venue_var
            self.venue_map = venue_map
            self.selected_venue_id = vid

            if hasattr(self, "select_venue") and callable(self.select_venue):
                self.select_venue()
                return

            try:
                self.show_main_screen()
            except Exception:
                logging.exception("Failed to show main screen")
                messagebox.showerror("Navigation Error", "Failed to continue to main screen.")

        # Bindings
        login_btn.configure(command=_on_login)
        username_ent.bind("<Return>", lambda e: password_ent.focus())
        password_ent.bind("<Return>", lambda e: _on_login())
        venue_cmb.bind("<Return>", lambda e: _on_login())

        try:
            self.update_idletasks()
            self.minsize(720, 800)
        except Exception:
            pass

    def show_login_screen(self):
        from datetime import datetime
        import tkinter as tk
        from tkinter import ttk
        from PIL import Image, ImageTk, ImageChops

        # ──────────── Tweak these if you want ────────────
        banner_height_fraction = 0.3  # up to 30% of screen height
        banner_max_height = 500  # hard cap in pixels, None to ignore
        # ────────────────────────────────────────────────

        # 1) Clear existing widgets
        for w in self.winfo_children():
            w.destroy()

        # 2) Pick light or dark based on time
        hour = datetime.now().hour
        theme = "flatly"

        # 3) One‑time bootstrap Style creation
        if not getattr(self, "_login_theme_initialized", False):
            from ttkbootstrap import Style as BootStyle
            self.style = BootStyle(theme)
            self.current_theme = theme
            self._login_theme_initialized = True

        # 4) Paint the root background to match the theme
        self.configure(bg=self.style.colors.bg)

        # 5) Dark‑mode tweaks (re‑applied each redraw)
        if self.current_theme == "darkly":
            self.style.configure(
                "TEntry",
                fieldbackground="#222222",
                foreground="#f8f8f8"
            )

        # 6) Load & auto‑crop banner/logo image
        banner = Image.open("icons/pass_banner.png")
        if self.current_theme == "darkly":
            banner = self.swap_black_white(banner)
        bg = Image.new(banner.mode, banner.size, banner.getpixel((0, 0)))
        diff = ImageChops.difference(banner, bg)
        bbox = diff.getbbox()
        if bbox:
            banner = banner.crop(bbox)
        self.original_banner = banner

        # 7) Configure root grid for proportional resizing
        total = 100
        bw = int(banner_height_fraction * total)
        fw = total - bw
        self.grid_rowconfigure(0, weight=bw)
        self.grid_rowconfigure(1, weight=fw)
        self.grid_columnconfigure(0, weight=1)

        # 8) Banner/logo frame
        banner_frame = ttk.Frame(self)
        banner_frame.grid(row=0, column=0, sticky="nsew")
        banner_frame.grid_columnconfigure(0, weight=1)
        banner_frame.grid_rowconfigure(0, weight=1)
        banner_label = ttk.Label(banner_frame)
        banner_label.grid(row=0, column=0)

        def resize_banner(event=None):
            frame_w = banner_frame.winfo_width()
            frame_h = banner_frame.winfo_height()
            orig_w, orig_h = self.original_banner.size
            aspect = orig_w / orig_h

            # Target: fill up to 80% of width, but not more than 90% of height
            max_w = int(frame_w * 0.8)
            max_h = int(frame_h * 0.9)
            # Also don't exceed banner_max_height
            if banner_max_height is not None:
                max_h = min(max_h, banner_max_height)

            scale = min(max_w / orig_w, max_h / orig_h, 1)
            new_w = max(1, int(orig_w * scale))
            new_h = max(1, int(orig_h * scale))

            img = self.original_banner.resize((new_w, new_h), Image.LANCZOS)
            self.banner_photo = ImageTk.PhotoImage(img)
            banner_label.config(image=self.banner_photo)
            # Center the logo in frame
            banner_label.grid_configure(padx=(frame_w - new_w) // 2, pady=(frame_h - new_h) // 2)

        banner_frame.bind("<Configure>", resize_banner)

        # 9) Load credential icons
        self.user_icon = tk.PhotoImage(file="icons/user.png")
        self.password_icon = tk.PhotoImage(file="icons/password.png")
        self.enter_btn_img = tk.PhotoImage(file="icons/enter2.png")

        # 10) Login form
        login_frame = ttk.Labelframe(self, text="Manager Login", padding=(30, 20))
        login_frame.grid(row=1, column=0, sticky="n")
        login_frame.grid_columnconfigure(0, weight=0)
        login_frame.grid_columnconfigure(1, weight=1)

        # Username row
        ttk.Label(
            login_frame, text="Username:",
            image=self.user_icon, compound=tk.LEFT,
            font=("Helvetica", 12)
        ).grid(row=0, column=0, padx=(0, 10), pady=(0, 10), sticky="e")
        self.manager_var = tk.StringVar()
        manager_entry = ttk.Entry(
            login_frame, textvariable=self.manager_var,
            font=("Helvetica", 12), width=30
        )
        manager_entry.grid(row=0, column=1, pady=(0, 10), sticky="we")
        manager_entry.focus()

        # Password row
        ttk.Label(
            login_frame, text="Password:",
            image=self.password_icon, compound=tk.LEFT,
            font=("Helvetica", 12)
        ).grid(row=1, column=0, padx=(0, 10), pady=(0, 10), sticky="e")
        self.password_var = tk.StringVar()
        password_entry = ttk.Entry(
            login_frame, textvariable=self.password_var,
            show="*", font=("Helvetica", 12), width=30
        )
        password_entry.grid(row=1, column=1, pady=(0, 10), sticky="we")

        # Enter‑key bindings
        manager_entry.bind("<Return>", lambda e: password_entry.focus())
        password_entry.bind("<Return>", lambda e: self.attempt_login())

        # Login button
        login_btn = ttk.Button(
            login_frame, text=" LOGIN ",
            image=self.enter_btn_img, compound=tk.LEFT,
            command=self.attempt_login, bootstyle="primary"
        )
        login_btn.grid(row=2, column=0, columnspan=2, pady=(15, 0))

        # 11) Initial draw
        self.update_idletasks()


    def show_venue_selection(self):
        import tkinter as tk
        from tkinter import ttk, messagebox
        from PIL import Image, ImageTk, ImageChops

        # ───── Layout Settings ─────
        banner_height_fraction = 0.3
        banner_max_height = 500

        # 1) Clear window
        for w in self.winfo_children():
            w.destroy()

        # 2) Paint the root background to match the theme
        self.configure(bg=self.style.colors.bg)

        # 3) Load & auto-crop banner/logo image
        banner = Image.open("icons/pass_banner.png")
        if getattr(self, "current_theme", "flatly") == "darkly":
            banner = self.swap_black_white(banner)
        bg = Image.new(banner.mode, banner.size, banner.getpixel((0, 0)))
        diff = ImageChops.difference(banner, bg)
        bbox = diff.getbbox()
        if bbox:
            banner = banner.crop(bbox)
        self.original_banner = banner

        # 4) Configure root grid
        total = 100
        bw = int(banner_height_fraction * total)
        fw = total - bw
        self.grid_rowconfigure(0, weight=bw)
        self.grid_rowconfigure(1, weight=fw)
        self.grid_columnconfigure(0, weight=1)

        # 5) Banner/logo frame (centered)
        banner_frame = ttk.Frame(self)
        banner_frame.grid(row=0, column=0, sticky="nsew")
        banner_frame.grid_columnconfigure(0, weight=1)
        banner_frame.grid_rowconfigure(0, weight=1)
        banner_label = ttk.Label(banner_frame)
        banner_label.grid(row=0, column=0)

        def resize_banner(event=None):
            frame_w = banner_frame.winfo_width()
            frame_h = banner_frame.winfo_height()
            orig_w, orig_h = self.original_banner.size
            aspect = orig_w / orig_h

            # Target: fill up to 80% of width, not more than 90% of height
            max_w = int(frame_w * 0.8)
            max_h = int(frame_h * 0.9)
            if banner_max_height is not None:
                max_h = min(max_h, banner_max_height)

            scale = min(max_w / orig_w, max_h / orig_h, 1)
            new_w = max(1, int(orig_w * scale))
            new_h = max(1, int(orig_h * scale))

            img = self.original_banner.resize((new_w, new_h), Image.LANCZOS)
            self.banner_photo = ImageTk.PhotoImage(img)
            banner_label.config(image=self.banner_photo)
            # Center logo in frame
            banner_label.grid_configure(padx=(frame_w - new_w) // 2, pady=(frame_h - new_h) // 2)

        banner_frame.bind("<Configure>", resize_banner)

        # 6) Load icons
        self.venue_icon = tk.PhotoImage(file="icons/venue.png")
        self.enter_btn_img = tk.PhotoImage(file="icons/enter2.png")

        # 7) Venue Frame
        frame = ttk.Labelframe(self, text="Venue Selection", padding=(30, 20))
        frame.grid(row=1, column=0, sticky="n")
        frame.grid_columnconfigure(0, weight=0)
        frame.grid_columnconfigure(1, weight=1)

        # Logged in as
        ttk.Label(
            frame, text=f"Logged in as: {self.manager}",
            font=("Helvetica", 13, "italic")
        ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 15))

        # Venue Label + Dropdown
        ttk.Label(
            frame, text="Select Venue:",
            image=self.venue_icon, compound=tk.LEFT,
            font=("Helvetica", 12)
        ).grid(row=1, column=0, padx=(0, 10), pady=(0, 10), sticky="e")

        vs = self.db_manager.get_venues()
        if not vs:
            messagebox.showerror("No Venues", "No venues in DB.")
            self.logout()
            return

        venue_names = [r["name"] for r in vs]
        self.venue_map = {r["name"]: r["id"] for r in vs}

        self.selected_venue_var = tk.StringVar(value=venue_names[0])
        vcombo = ttk.Combobox(
            frame, textvariable=self.selected_venue_var,
            values=venue_names, state="readonly",
            font=("Helvetica", 12), width=30
        )
        vcombo.grid(row=1, column=1, pady=(0, 10), sticky="we")
        vcombo.focus()
        vcombo.bind("<Return>", lambda e: self.select_venue())

        # Select Button
        select_btn = ttk.Button(
            frame, text="  ENTER ".upper(),
            image=self.enter_btn_img, compound=tk.LEFT,
            command=self.select_venue,
            bootstyle="primary"
        )
        select_btn.grid(row=2, column=0, columnspan=2, pady=(10, 0))
        select_btn.bind("<Return>", lambda e: self.select_venue())

        # 8) Force initial layout
        self.update_idletasks()

    def update_entry_width(self, event=None):
        """
        Dynamically updates the width of the dish entry field based on the length of the text.
        Maximum width is capped at 70 characters.
        """
        text_length = len(self.dish_var.get())
        # Calculate the new width, capping at 70
        new_width = min(max(20, text_length + 2), 70)
        self.dish_entry.config(width=new_width)

    def select_venue(self):
        sel = self.selected_venue_var.get()
        self.venue_id = self.venue_map.get(sel)
        self.venue_name = sel
        if not self.venue_id:
            messagebox.showerror("Error", f"Venue ID not found for {sel}.")
            return

        # 1) Copy forward ANY standing orders before we blow away the screen
        self.check_and_carry_standing_orders()

        # 2) Re-draw the main screen (this creates self.timeslot_dropdown, self.allergy_combobox, etc.)
        self.show_main_order_screen()

        # 3) Now that those widgets exist, populate them:
        self.populate_time_slots()
        self.load_allergies()


    def get_current_cabin_number(self):
        val = self.cabin_number_var.get()
        return val.split(" - ")[0].strip() if " - " in val else val.strip()

    # -------------- GUEST SELECTION LOGIC --------------
    def recall_guests_by_cabin(self, cabin_number):
        guests = self.db_manager.get_guests_for_cabin(cabin_number)
        lb = self.guest_listbox  # adjust if your widget name differs
        lb.delete(0, tk.END)
        self.guest_map = {}
        for g in guests:
            display = f"{g['last_name']}, {g['first_name']}"
            lb.insert(tk.END, display)
            # Map back to (cabin, "First Last")
            self.guest_map[display] = (cabin_number, f"{g['first_name']} {g['last_name']}")

    def on_recall_search_change(self, *_):
        term = self.recall_search_var.get()
        try:
            guests = self.db.search_guests_by_name(term)
            lb = getattr(self, "recall_listbox", None) or getattr(self, "lst_recall_guests", None)
            if lb is None:
                return
            lb.delete(0, tk.END)
            for g in guests:
                lb.insert(tk.END, f"{g['cabin_number']} — {g['last_name']}, {g['first_name']}")
            self._recall_map = guests
        except Exception as e:
            logging.error(f"on_recall_search_change: {e}", exc_info=True)

    # ---------------------------- ALLERGIES LOGIC ----------------------------
    def load_allergies(self):
        self.allergies = self.db_manager.get_allergies()
        logging.info(f"Loaded {len(self.allergies)} allergies")

        # Extract allergy names, preserving the order and special entries
        raw = []
        for a in self.allergies:
            name = a["name"]
            # Only include "None" once at the beginning
            if name.lower() == "none" and "None" not in raw:
                raw.append("None")
            # Only include "Other" once at the end
            elif name.lower() == "other" and "Other" not in raw:
                raw.append("Other")
            # Add all other allergies
            elif name.lower() not in ("none", "other"):
                raw.append(name)

        # Ensure "Other" is always last
        if "Other" not in raw:
            raw.append("Other")

        if hasattr(self, 'allergy_combobox') and self.allergy_combobox.winfo_exists():
            self.allergy_combobox['values'] = raw
            logging.info(f"Populated allergy combobox with {len(raw)} items")
            self.allergy_combobox.set("None")


    from datetime import datetime, timedelta

    def check_and_carry_standing_orders(self):
        """
        Carry today's standing orders to tomorrow for THIS venue,
        strictly within the CURRENT voyage only.
        Prevents cross-voyage leakage and double-runs via a per-venue+voyage key.
        """
        # 0) Resolve current voyage
        vid = getattr(self.db_manager, "current_voyage_id", None)
        if not vid:
            messagebox.showwarning("Voyage not set",
                                   "Set the current voyage first (Admin → Start New Voyage).")
            return

        # 1) Compute 'today' and 'tomorrow' using your cutoff rules
        now = self._now_local()
        cutoff_hour = self._get_cutoff_hour()
        if now.hour < cutoff_hour:
            today = (now.date() - timedelta(days=1)).strftime("%Y-%m-%d")
            tomorrow = now.date().strftime("%Y-%m-%d")
        else:
            today = now.date().strftime("%Y-%m-%d")
            tomorrow = (now.date() + timedelta(days=1)).strftime("%Y-%m-%d")

        # 2) Per-venue PER-VOYAGE last-run guard
        last_key = f"last_standing_copy_{self.venue_id}_{vid}"
        last_run = self.db_manager.get_config_value(last_key, None)
        if last_run == today:
            logging.info(f"[StandingCarry] Already carried for venue={self.venue_id}, voyage={vid}, date={today}.")
            return

        # 3) Count standing orders for TODAY, scoped by venue & voyage
        p = self.db_manager._param()
        try:
            with self.db_manager.get_connection() as conn:
                cur = conn.cursor()
                if self.db_manager.backend == "mysql":
                    sql_cnt = f"""
                        SELECT COUNT(*) FROM preorders
                         WHERE service_date = {p}
                           AND venue_id     = {p}
                           AND voyage_id    = {p}
                           AND (standing_order = 'YES' OR standing_order = 1)
                    """
                else:
                    sql_cnt = f"""
                        SELECT COUNT(*) AS c FROM preorders
                         WHERE service_date = {p}
                           AND venue_id     = {p}
                           AND voyage_id    = {p}
                           AND (standing_order = 'YES' OR standing_order = 1)
                    """
                cur.execute(sql_cnt, (today, self.venue_id, vid))
                row = cur.fetchone()
                so_count = (row[0] if self.db_manager.backend == "mysql" else row["c"]) if row else 0
        except Exception as e:
            logging.error(f"[StandingCarry] Count failed: {e}", exc_info=True)
            messagebox.showerror("Error", "Could not check standing orders.")
            return

        if not so_count:
            logging.info(f"[StandingCarry] None to carry for venue={self.venue_id}, voyage={vid}, date={today}.")
            #messagebox.showinfo("Standing Orders", f"No standing orders found for {self.venue_name} on {today}.")
            return

        # 4) Confirm with the user (make voyage explicit)
        if not messagebox.askyesno(
                "Standing Orders",
                f"{so_count} standing order(s) found today in {self.venue_name} "
                f"for voyage {vid}.\nCarry them over to {tomorrow}?"
        ):
            return

        # 5) Perform the carry (DB helper MUST be voyage-scoped)
        try:
            carried = self.db_manager.carry_standing_orders(today, tomorrow, self.venue_id, vid)
        except TypeError:
            # Safety: if your helper is still the old signature, fail rather than cross-voyage carry.
            logging.error("[StandingCarry] carry_standing_orders() needs voyage_id parameter.")
            messagebox.showerror("Error",
                                 "Standing order carry is not configured for voyage scoping. "
                                 "Please update the database helper to accept voyage_id.")
            return
        except Exception as e:
            logging.error(f"[StandingCarry] Carry failed: {e}", exc_info=True)
            messagebox.showerror("Error", "Failed to carry standing orders.")
            return

        if carried > 0:
            # 6) Mark carried for THIS venue+voyage on THIS 'today'
            try:
                self.db_manager.set_config_value(last_key, today)
            except Exception as e:
                logging.warning(f"[StandingCarry] Failed to set last-run key: {e}")
            messagebox.showinfo("Success", f"{carried} standing order(s) carried to {tomorrow} (voyage {vid}).")
        else:
            messagebox.showwarning("No Standing Orders", "No standing orders were carried over.")

    from PIL import Image, ImageTk

    def show_toast(self, message, duration=3000, toast_type="info"):
        """
        Display a toast notification.
        toast_type can be "info" or "warning" (you can extend to "error", etc.).
        """

        # ─── Configuration ──────────────────────────────────────────
        configs = {
            "info":    {"bg":"#4CAF50", "fg":"#ffffff", "gif":"icons/check.gif"},
            "warning": {"bg":"#FFC107", "fg":"#333333", "gif":"icons/alert.gif"},
            # add more types if you like:
            # "error": {"bg":"#F44336", "fg":"#ffffff", "gif":"icons/error.gif"},
        }
        cfg = configs.get(toast_type, configs["info"])

        # ─── Create Toast Window ────────────────────────────────────
        toast = tk.Toplevel(self)
        toast.overrideredirect(True)
        toast.attributes("-topmost", True)
        toast.configure(bg=cfg["bg"])
        toast.attributes("-alpha", 0.0)

        container = tk.Frame(toast, bg=cfg["bg"], padx=10, pady=10)
        container.pack()

        # ─── Load GIF ──────────────────────────────────────────────
        def load_gif_frames(path):
            frames, durations = [], []
            try:
                pil_img = Image.open(path)
                while True:
                    frames.append(ImageTk.PhotoImage(pil_img.copy().convert("RGBA")))
                    durations.append(pil_img.info.get("duration", 80))
                    pil_img.seek(pil_img.tell() + 1)
            except EOFError:
                pass
            except Exception as e:
                print(f"Failed to load GIF {path!r}:", e)
            return frames, durations

        frames, durations = load_gif_frames(cfg["gif"])
        if frames:
            gif_label = tk.Label(container, bg=cfg["bg"])
            gif_label.pack(side="left", padx=(0,10))
            def animate(idx=0):
                gif_label.configure(image=frames[idx])
                next_idx = (idx+1) % len(frames)
                delay = durations[idx] if idx < len(durations) else 80
                gif_label.after(delay, animate, next_idx)
            animate()

        # ─── Message ───────────────────────────────────────────────
        text_label = tk.Label(
            container, text=message,
            bg=cfg["bg"], fg=cfg["fg"],
            font=("Helvetica", 14, "bold")
        )
        text_label.pack(side="left")

        # ─── Position ──────────────────────────────────────────────
        toast.update_idletasks()
        x = self.winfo_rootx() + (self.winfo_width()//2) - (toast.winfo_width()//2)
        y = self.winfo_rooty() + 30
        toast.geometry(f"+{x}+{y}")

        # ─── Fade In / Out ─────────────────────────────────────────
        def fade_in(alpha=0.0):
            alpha += 0.1
            if alpha < 1.0:
                toast.attributes("-alpha", alpha)
                toast.after(30, fade_in, alpha)
            else:
                toast.attributes("-alpha", 1.0)

        def fade_out(alpha=1.0):
            alpha -= 0.1
            if alpha > 0:
                toast.attributes("-alpha", alpha)
                toast.after(30, fade_out, alpha)
            else:
                toast.destroy()

        fade_in()
        toast.after(duration, fade_out)

    def populate_time_slots(self):
        try:
            with self.db_manager.get_connection() as conn:
                cur = conn.cursor()
                # Get correct placeholder for current backend
                p = self.db_manager._param()
                sql = f"""
                    SELECT breakfast_available, lunch_available, dinner_available
                    FROM venues
                    WHERE id = {p}
                """
                cur.execute(sql, (self.venue_id,))
                row = cur.fetchone()
                if not row:
                    return

                # Access by index for MySQL compatibility
                if self.db_manager.backend == "mysql":
                    bf, ln, dn = row[0], row[1], row[2]
                else:
                    bf = row["breakfast_available"]
                    ln = row["lunch_available"]
                    dn = row["dinner_available"]

                slots = []
                if bf: slots.append("BREAKFAST")
                if ln: slots.append("LUNCH")
                if dn: slots.append("DINNER")

                self.timeslot_dropdown['values'] = slots

                # Always select DINNER by default when available
                if dn:
                    self.timeslot_var.set("DINNER")
                elif slots:  # If no dinner but other slots exist
                    self.timeslot_var.set(slots[0])
                else:
                    self.timeslot_var.set("")
        except Exception as e:
            logging.error(f"Error populating time slots: {e}")    # ---------------------------- MAIN ORDER SCREEN ----------------------------

    def prompt_switch_venue(self):
        """
        Prompt the user to handle unsaved orders, then go to the venue selection screen.
        """
        # Check if we have unsent orders (same logic you do on close)
        any_unsaved = any(not order[10] for order in self.all_orders)  # from_db flag is False
        if any_unsaved:
            ans = messagebox.askyesnocancel(
                "Unsaved Data",
                "You have unsaved orders. Do you want to commit them before switching venue?"
            )
            if ans is True:
                # User chose YES => commit to DB
                self.commit_to_db()
                # After commit, proceed to switch
            elif ans is None:
                # User cancelled => do nothing
                return
            else:
                # User chose NO => discard the unsaved
                pass

        # Now we either committed or decided to discard unsaved data, so let's
        # effectively “reset” the main screen and show the venue selection again.
        # We do NOT log out the manager. We just re‐select a venue.

        self.clear_main_screen()  # we’ll define a helper to remove main UI frames
        self.show_venue_selection()  # let them choose a new venue

    def clear_main_screen(self):
        # reset any row/column weights that may have been set
        for i in range(3):  # just pick enough rows/cols
            self.grid_rowconfigure(i, weight=0)
            self.grid_columnconfigure(i, weight=0)

        for w in self.winfo_children():
            w.destroy()

    import tkinter as tk
    from tkinter import ttk


    from ttkbootstrap import Style

    def show_main_order_screen(self):
        from datetime import datetime

        # --- Theme row colors (adjust as you wish) ---
        LIGHT_ODDROW = "#dce2e6"
        LIGHT_EVENROW = "#ffffff"
        # DARK_ODDROW = "#262626"
        # DARK_EVENROW = "#22292f"
        self.tree_expanded = False

        # --- Clear and grid config ---
        for w in self.winfo_children():
            w.destroy()
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)
        # Reset *all* rows to 0, then give row 0 full weight
        for r in range(self.grid_size()[1]):
            self.grid_rowconfigure(r, weight=0)
        self.grid_rowconfigure(0, weight=1)

        # And your single column still gets all the width
        self.grid_columnconfigure(0, weight=1)

        # --- Load Field Icons ---
        self.cabin_icon = tk.PhotoImage(file="icons/cabin.png")
        self.allergy_icon = tk.PhotoImage(file="icons/allergy.png")
        self.meal_icon = tk.PhotoImage(file="icons/meal.png")
        self.galley_icon = tk.PhotoImage(file="icons/galley.png")
        self.reqs_icon = tk.PhotoImage(file="icons/reqs.png")
        self.dish_icon = tk.PhotoImage(file="icons/dish.png")
        self.pax_icon = tk.PhotoImage(file="icons/pax.png")
        self.plus_allergy = tk.PhotoImage(file="icons/plus-square.png")
        self.plus_icon = tk.PhotoImage(file="icons/plus.png")
        self.clipboard_icon = tk.PhotoImage(file="icons/clipboard.png")
        self.cloud_icon = tk.PhotoImage(file="icons/cloud.png")
        self.search_icon = tk.PhotoImage(file="icons/search.png")
        self.standing_icon = tk.PhotoImage(file="icons/standing.png")
        self.recall_icon = tk.PhotoImage(file="icons/recall.png")
        self.logout_icon = tk.PhotoImage(file="icons/logout.png")
        self.my_orders_icon = tk.PhotoImage(file="icons/my_orders.png")

        # --- MENU BAR ---
        menubar = tk.Menu(self, bg="white", fg="black")
        self.config(menu=menubar)
        file_menu = tk.Menu(menubar, tearoff=0, bg="white", fg="black")
        file_menu.add_command(label="Logout", command=self.logout, accelerator="Ctrl+L")
        menubar.add_cascade(label="File", menu=file_menu)
        admin_menu = tk.Menu(menubar, tearoff=0, bg="white", fg="black")
        admin_menu.add_command(label="Today's Orders Preview", command=self.show_todays_orders)
        admin_menu.add_command(label="Settings", command=self.show_settings_window)
        menubar.add_cascade(label="Admin", menu=admin_menu)
        help_menu = tk.Menu(menubar, tearoff=0, bg="white", fg="black")
        help_menu.add_command(label="Contact Info", command=self.show_help_info)
        menubar.add_cascade(label="Help", menu=help_menu)

        paned = ttk.PanedWindow(self, orient=tk.VERTICAL)
        paned.grid(row=0, column=0, sticky="nsew")
        top_frame = ttk.Frame(paned)
        bottom_frame = ttk.Frame(paned)
        paned.add(top_frame, weight=0)
        paned.add(bottom_frame, weight=1)

        # 1) Force an update so the panes lay themselves out.
        self.update_idletasks()

        # 2) Record the *true* collapsed sash position
        self._collapsed_sash = paned.sashpos(0)
        #    (expanded is always “0” because that pushes the sash all the way up)
        self._expanded_sash = 0

        # 3) Immediately collapse back to show the form
        paned.sashpos(0, self._collapsed_sash)

        # 4) Reset your flag
        self.tree_expanded = False

        # --- HEADER (in top_frame) ---
        top_frame.columnconfigure(0, weight=1)
        header_frame = ttk.Frame(top_frame)
        header_frame.grid(row=0, column=0, sticky="ew", pady=(10, 5))
        header_frame.columnconfigure((0, 1, 2), weight=1)

        # Left buttons
        left_button_frame = ttk.Frame(header_frame)
        left_button_frame.grid(row=0, column=0, sticky="w", padx=10)
        btn_change_venue = ttk.Button(
            left_button_frame,
            text=" CHANGE VENUE ",
            command=self.prompt_switch_venue,
            bootstyle="danger.Outline.TButton",
            image=self.logout_icon,
            compound="left"
        )
        btn_change_venue.pack(side="left", padx=(0, 8))
        ToolTip(btn_change_venue, "Switch to another restaurant venue.")

        btn_recall_guest = ttk.Button(
            left_button_frame,
            text=" RECALL GUEST ",
            command=self.recall_guests_by_manager,
            bootstyle="info.Outline.TButton",
            image=self.recall_icon,
            compound="left"
        )
        btn_recall_guest.pack(side="left")
        ToolTip(btn_recall_guest, "Recall a previously entered guest for editing.")

        # Centered logo and info
        center_frame = ttk.Frame(header_frame)
        center_frame.grid(row=0, column=1, sticky="nsew")

        from PIL import Image, ImageTk

        center_frame = ttk.Frame(header_frame)
        center_frame.grid(row=0, column=1, sticky="nsew")

        # Load your *cropped* logo (should have very little whitespace)
        logo_path = "icons/header_logo.png"
        logo_img = Image.open(logo_path)
        # Resize for header: 80–100px tall usually looks pro (adjust as you wish)
        target_height = 100
        aspect = logo_img.width / logo_img.height
        logo_resized = logo_img.resize((int(target_height * aspect), target_height), Image.LANCZOS)
        self.safebite_logo_img = ImageTk.PhotoImage(logo_resized)
        logo_label = ttk.Label(center_frame, image=self.safebite_logo_img)
        logo_label.pack(pady=(0, 2))

        # Subtitle (venue and manager), still centered and close to logo
        subtitle = ttk.Label(center_frame,
                             text=f"Venue: {self.venue_name}   |   Manager: {self.manager}",
                             font=("Helvetica", 13, "italic"))
        subtitle.pack()

        # Right info (date & guest)
        right_info_frame = ttk.Frame(header_frame)
        right_info_frame.grid(row=0, column=2, sticky="e", padx=10)

        date_frame = ttk.Frame(right_info_frame)
        date_frame.pack(anchor="e")
        ttk.Label(date_frame, text="Service Date:", font=("Helvetica", 12)).pack(side="left", padx=(0, 5))
        self.service_date_entry = ttk.Entry(date_frame,
                                            textvariable=self.service_date_var,
                                            width=12, font=("Helvetica", 12))
        self.service_date_entry.pack(side="left")

        guest_frame = ttk.Frame(right_info_frame)
        guest_frame.pack(anchor="e", pady=(5, 0))
        ttk.Label(guest_frame, text="Guest Name:", font=("Helvetica", 12)).pack(side="left")
        self.guest_name_label = ttk.Label(guest_frame,
                                          textvariable=self.guest_name_var,
                                          font=("Helvetica", 12),
                                          foreground="#333")
        self.guest_name_label.pack(side="left", padx=(5, 0))

        # NEW: server time row
        server_frame = ttk.Frame(right_info_frame)
        server_frame.pack(anchor="e", pady=(5, 0))
        self.server_time_label = ttk.Label(
            server_frame,
            text="",  # will be filled by updater
            font=("Helvetica", 10),
            foreground="#555"
        )
        self.server_time_label.pack(side="left")
        self._update_server_time_label()

        # --- FORM (as self.form_frame for access in expand logic) ---
        self.form_frame = ttk.Labelframe(top_frame,
                                         text="Add New Order",
                                         bootstyle="danger",
                                         padding=15)
        self.form_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 10))
        self.form_frame.columnconfigure((1, 3), weight=1)
        form_frame = self.form_frame  # For below

        print("DBG backend=", getattr(self.db_manager, "backend", None),
              "tz=", self._get_service_timezone(),
              "cutoff=", self._get_cutoff_hour())

        def toggle_tree_expand():
            if not self.tree_expanded:
                expand_btn.config(text=" Restore Table",
                                  image= self.collapse_icon,
                                  compound="left",
                                  style="danger.TButton")
                paned.sashpos(0, self._expanded_sash)
            else:
                expand_btn.config(text=" Expand Table",
                                  image= self.expand_icon,
                                  compound="left",
                                  style="primary.Outline.TButton")
                paned.sashpos(0, self._collapsed_sash)
            self.tree_expanded = not self.tree_expanded

        def create_field_label(master, icon, text, font=("Helvetica", 12)):
            frame = ttk.Frame(master)
            ttk.Label(frame, image=icon).grid(row=0, column=0, padx=(5, 10), pady=5, sticky="w")
            ttk.Label(frame, text=text, font=font, width=15, anchor="w") \
                .grid(row=0, column=1, sticky="w")
            return frame

        # Guest/Cabin autocomplete
        # --- Guest autocomplete (voyage-scoped) ---
        # Build the entry without precomputed suggestions; it will pull from DB for current_voyage_id.
        cabin_label_frame = create_field_label(form_frame, self.cabin_icon, "Guest Name/Cabin :")
        cabin_label_frame.grid(row=0, column=0, sticky="e", padx=5, pady=5)

        self.cabin_number_entry = AutocompleteEntry(
            form_frame,
            suggestions=[],
            textvariable=self.cabin_number_var,
            guest_name_var=self.guest_name_var,
            db_manager=self.db_manager,
            voyage_scoped=True,
            enforce_pick=True,  # <— enforce selection-only
            font=("Helvetica", 12),
            width=25
        )
        self.cabin_number_entry.reload_from_db()

        self.cabin_number_entry.grid(row=0, column=1, sticky="w", padx=5, pady=5)
        self.cabin_number_entry.bind("<Return>", lambda e: self.dish_entry.focus())
        ToolTip(self.cabin_number_entry, "Start entering the cabin number or guest name")

        # Immediately load suggestions for the current voyage
        try:
            self.cabin_number_entry.reload_from_db()
        except Exception:
            pass

        # --- Dish autocomplete (unchanged logic) ---
        dish_label_frame = create_field_label(form_frame, self.dish_icon, "Dish:")
        dish_label_frame.grid(row=1, column=0, sticky="e", padx=5, pady=5)
        self.dish_entry = AutocompleteEntry(
            form_frame,
            suggestions=self.today_dishes,
            textvariable=self.dish_var,
            width=35,
            galley_callback=lambda d: self.galley_section_var.set(
                self.db_manager.get_galley_for_dish(
                    d if self.db_manager.backend == "sqlite" else d.lower(),
                    self.venue_id
                ) or GALLEY_SECTIONS[0]
            ),
            meal_period_callback=lambda d: self.timeslot_var.set(
                self.db_manager.get_meal_period_for_dish(
                    d if self.db_manager.backend == "sqlite" else d.lower(),
                    self.venue_id
                ) or TIMESLOTS[0]
            ),
            font=("Helvetica", 12)
        )
        self.dish_entry.grid(row=1, column=1, sticky="w", padx=5, pady=5)

        # Pax size
        pax_label_frame = create_field_label(form_frame, self.pax_icon, "Pax Size:")
        pax_label_frame.grid(row=2, column=0, sticky="e", padx=5, pady=5)
        self.pax_var.set("1")
        self.pax_spinbox = tk.Spinbox(form_frame,
                                      from_=1, to=20,
                                      textvariable=self.pax_var,
                                      font=("Helvetica", 12),
                                      width=5)
        self.pax_spinbox.grid(row=2, column=1, sticky="w", padx=5, pady=5)

        # Allergies
        allergy_label_frame = create_field_label(form_frame, self.allergy_icon, "Allergies:")
        allergy_label_frame.grid(row=3, column=0, sticky="e", padx=5, pady=5)
        allergy_frame = ttk.Frame(form_frame)
        allergy_frame.grid(row=3, column=1, sticky="w", padx=5, pady=5)
        self.allergy_selected_var = tk.StringVar()
        raw = [a["name"] for a in self.allergies]
        if "Other" not in raw: raw.append("Other")
        self.allergy_combobox = ttk.Combobox(
            allergy_frame,
            textvariable=self.allergy_selected_var,
            values=raw,
            state="readonly",
            font=("Helvetica", 12),
            width=20
        )


        self.allergy_combobox.grid(row=0, column=0, padx=(0, 10), sticky="ew")
        self.allergy_combobox.bind("<<ComboboxSelected>>", self.on_allergy_selected)
        self.add_allergy_button = ttk.Button(
            allergy_frame,
            style="danger.TButton",
            image=self.plus_allergy,
            compound=tk.LEFT,
            width=3,
            command=self.add_allergy
        )
        ToolTip(self.allergy_combobox, "Choose an allergy from the list")
        self.add_allergy_button.grid(row=0, column=1)
        self.allergy_combobox.current(0)
        sel_allergy_frame = ttk.Frame(form_frame)
        sel_allergy_frame.grid(row=4, column=1, columnspan=2, sticky="w", padx=5, pady=10)
        ttk.Label(sel_allergy_frame, text="Selected Allergies:", font=("Helvetica", 12)) \
            .grid(row=0, column=0, sticky="w")
        self.selected_allergies_listbox = tk.Listbox(
            sel_allergy_frame, height=5, width=30, font=("Helvetica", 12))
        self.selected_allergies_listbox.grid(row=1, column=0, sticky="w", padx=(0, 10))
        self.selected_allergies_listbox.bind("<<ListboxSelect>>", self.update_remove_button_state)
        self.selected_allergies_listbox.bind("<Delete>", self.remove_selected_allergy)
        self.rem_btn = ttk.Button(sel_allergy_frame, text="Remove",
                                  command=self.remove_selected_allergy)
        self.rem_btn.grid(row=1, column=1, sticky="w")
        self.update_remove_button_state()
        self.on_allergy_selected()

        # Special requests
        reqs_label_frame = create_field_label(form_frame, self.reqs_icon, "Special Requests:")
        reqs_label_frame.grid(row=0, column=2, sticky="e", padx=(30, 5), pady=5)
        self.special_requests_entry = ttk.Entry(
            form_frame,
            textvariable=self.special_requests_var,
            width=30,
            font=("Helvetica", 12)
        )
        self.special_requests_entry.grid(row=0, column=3, sticky="w", padx=5, pady=5)
        ToolTip(self.special_requests_entry, "Enter any details if available")

        # Time slot
        meal_label_frame = create_field_label(form_frame, self.meal_icon, "Time Slot:")
        meal_label_frame.grid(row=1, column=2, sticky="e", padx=(30, 5), pady=5)
        self.timeslot_dropdown = ttk.Combobox(
            form_frame,
            textvariable=self.timeslot_var,
            state="readonly",
            font=("Helvetica", 12)
        )
        self.timeslot_dropdown.grid(row=1, column=3, sticky="w", padx=5, pady=5)
        self.timeslot_dropdown.bind("<Return>", lambda e: self.galley_section_dropdown.focus())
        ToolTip(self.timeslot_dropdown, "Choose the meal period")

        # Galley section
        section_label_frame = create_field_label(form_frame, self.galley_icon, "Galley Section")
        section_label_frame.grid(row=2, column=2, sticky="e", padx=(30, 5), pady=5)
        self.galley_section_dropdown = ttk.Combobox(
            form_frame,
            textvariable=self.galley_section_var,
            values=[s.upper() for s in GALLEY_SECTIONS],
            state="readonly",
            font=("Helvetica", 12)
        )
        self.galley_section_dropdown.grid(row=2, column=3, sticky="w", padx=5, pady=5)
        self.galley_section_dropdown.bind("<Return>", lambda e: self.standing_order_check.focus())
        ToolTip(self.galley_section_dropdown, "Select the galley section")

        # Standing order checkbox
        self.standing_order_check = ttk.Checkbutton(
            form_frame,
            text=" STANDING ORDER ",
            image=self.standing_icon,
            compound=tk.LEFT,
            variable=self.standing_order_var,
            style="danger.Outline.Toolbutton"
        )
        self.standing_order_check.grid(row=3, column=3, padx=5, pady=5, sticky="w")
        ToolTip(self.standing_order_check,
                "Activate if this is a standing order.\nStanding orders will be moved to next day automatically")
        # --- ORDER ACTIONS BAR ---
        actions_frame = ttk.Frame(top_frame)
        actions_frame.grid(row=99, column=0, columnspan=2, sticky="ew", padx=10, pady=(6, 6))

        # Use equal weight for columns
        for i in range(4):
            actions_frame.columnconfigure(i, weight=1)

        self.btn_edit = ttk.Button(actions_frame, text="✏️  Edit", command=self.on_edit_order,
                                   state="disabled", bootstyle="primary.Outline.TButton")
        self.btn_delete = ttk.Button(actions_frame, text="🗑️  Delete", command=self.on_remove_order,
                                     state="disabled", bootstyle="danger.Outline.TButton")
        self.btn_new = ttk.Button(actions_frame, text="➕  Start New Order", command=self.start_new_order,
                                  state="disabled", bootstyle="success.Outline.TButton")
        self.btn_hist = ttk.Button(actions_frame, text="📄  Guest History", command=self.show_guest_history_for_selected,
                                   state="disabled", bootstyle="info.Outline.TButton")

        self.btn_edit.grid(row=0, column=0, padx=5, sticky="ew")
        self.btn_delete.grid(row=0, column=1, padx=5, sticky="ew")
        self.btn_new.grid(row=0, column=2, padx=5, sticky="ew")
        self.btn_hist.grid(row=0, column=3, padx=5, sticky="ew")

        # --- TREEVIEW (in bottom_frame) ---
        bottom_frame.rowconfigure(0, weight=1)
        bottom_frame.columnconfigure(0, weight=1)
        tree_frame = ttk.Frame(bottom_frame)
        tree_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=(0, 5))
        tree_frame.rowconfigure(0, weight=1)
        tree_frame.columnconfigure(0, weight=1)

        cols = ("Manager", "Cabin", "Guest Name", "Dish", "Pax", "Allergy",
                "Requests", "Time Slot", "Galley Section", "Standing")

        self.tree = ttk.Treeview(
            tree_frame,
            columns=cols,
            show="tree headings",  # Show icon/status column!
            selectmode="browse"
        )
        self.tree.heading("#0", text="")  # "S" for Status/Icon
        self.tree.column("#0", width=self.db_icon.width(), stretch=False)
        for col in cols:
            self.tree.heading(col, text=col.upper(), anchor="center")
            self.tree.column(col, anchor="center", stretch=True)

        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        vsb.grid(row=0, column=1, sticky="ns")
        hsb = ttk.Scrollbar(tree_frame, orient="horizontal", command=self.tree.xview)
        hsb.grid(row=1, column=0, sticky="ew", columnspan=2)  # covers tree + vsb

        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        # Theme styling (adjust your colors as you like for dark mode)
        self.style.configure("Treeview", rowheight=30)
        self.style.configure("Treeview.Heading", font=("Helvetica", 11, "bold"))
        self.style.map("Treeview", background=[("selected", "#ab0c24")], foreground=[("selected", "white")])
        self.style.configure("Treeview", borderwidth=1, relief="solid")
        self.tree.tag_configure("oddrow", background=LIGHT_ODDROW)
        self.tree.tag_configure("evenrow", background=LIGHT_EVENROW)

        def populate_treeview(rows):
            for it in self.tree.get_children():
                self.tree.delete(it)
            for idx, row in enumerate(rows):
                icon = self.db_icon if row[10] else self.unsaved_icon
                tag = "evenrow" if idx % 2 == 0 else "oddrow"
                self.tree.insert('', tk.END, image=icon, values=row[:10], tags=(tag,))



        self.populate_treeview = populate_treeview  # Save for use elsewhere
        self.populate_treeview(self.all_orders)

        # ------------------- CONTEXT MENU -------------------
        self.context_menu = tk.Menu(self, tearoff=0)
        self.context_menu.add_command(label="Edit", command=self.on_edit_order)
        self.context_menu.add_command(label="Remove", command=self.on_remove_order)
        self.tree.bind("<Delete>", self.on_remove_order)
        self.tree.bind("<Return>", self.on_double_click)
        self.tree.bind("<Button-3>", self.on_tree_right_click)
        self.tree.bind("<Double-1>", self.on_double_click)
        self.tree.bind("<<TreeviewSelect>>", self._on_tree_selection)

        # --- SEARCH FRAME (in bottom_frame) ---
        search_frame = ttk.Frame(bottom_frame)
        search_frame.grid(row=1, column=0, sticky="ew", padx=5, pady=5)
        search_frame.columnconfigure(1, weight=1)
        search_frame.columnconfigure(2, weight=0)

        # "Search:" label + search icon in same frame
        search_label_frame = ttk.Frame(search_frame)
        search_label_frame.grid(row=0, column=0, padx=(0, 5), pady=5, sticky="w")
        ttk.Label(search_label_frame, text="Search:", font=("Helvetica", 12)).pack(side="left")
        ttk.Label(search_label_frame, image=self.search_icon).pack(side="left", padx=(5, 0))

        # Entry box (no search icon here now)
        entry_frame = ttk.Frame(search_frame)
        entry_frame.grid(row=0, column=1, padx=(0, 10), pady=5, sticky="ew")
        entry_frame.columnconfigure(0, weight=1)
        self.search_var = tk.StringVar()
        self.search_var.trace("w", lambda *args: self.update_treeview())
        s_entry = ttk.Entry(entry_frame,
                            textvariable=self.search_var,
                            width=50,
                            bootstyle="primary",
                            font=("Helvetica", 12))
        s_entry.grid(row=0, column=0, sticky="ew")
        ToolTip(s_entry, "Start typing to search in orders")

        # … right after you create your Search entry (col 1) …

        common_grid_opts = dict(pady=2, ipady=2)

        # 1) “My Orders Only” checkbox in col 2
        self.show_mine_var = tk.BooleanVar(value=False)
        mine_cb = ttk.Checkbutton(
            search_frame,
            text=" My Orders",
            image=self.my_orders_icon,
            compound="left",
            variable=self.show_mine_var,
            command=self.update_treeview,
            bootstyle="danger.Outline.Toolbutton",
            padding=(5, 5)  # uniform internal padding
        )
        mine_cb.grid(row=0, column=2, sticky="w", padx=(10, 5), **common_grid_opts)

        # 2) Expand Table button in col 3
        self.expand_icon = tk.PhotoImage(file="icons/expand.png")
        self.collapse_icon = tk.PhotoImage(file="icons/collapse.png")
        expand_btn = ttk.Button(
            search_frame,
            text=" Expand Table",
            image=self.collapse_icon,
            compound="left",
            style="primary.Outline.TButton",
            command=toggle_tree_expand,
            padding=(5, 5)
        )
        expand_btn.grid(row=0, column=3, sticky="e", padx=(5, 5), **common_grid_opts)

        # 3) Show Unsaved Orders toggle in col 4
        self.toggle_btn = ttk.Button(
            search_frame,
            text=" Show Unsaved Orders",
            image=self.unsaved_icon,
            compound="left",
            command=self._toggle_unsaved_view,
            bootstyle="danger.Outline.TButton",
            padding=(5, 5)
        )
        self.toggle_btn.grid(row=0, column=4, sticky="e", padx=(5, 0), **common_grid_opts)
        ToolTip(self.toggle_btn, "Show only unsaved orders / show all orders")

        # --- BUTTON FRAME (in bottom_frame) ---
        btn_frame = ttk.Frame(bottom_frame)
        btn_frame.grid(row=2, column=0, sticky="ew", padx=5, pady=5)
        for i in range(3):
            btn_frame.columnconfigure(i, weight=1)
        self.add_to_order_btn = ttk.Button(
            btn_frame,
            text="ADD TO ORDER",
            command=self.add_to_order,
            state="disabled",
            image=self.plus_icon,
            style="info.TButton",
            compound="left"
        )
        self.add_to_order_btn.grid(row=0, column=0, padx=5, pady=5, sticky="ew")




        ToolTip(self.add_to_order_btn, "Press to start entering multiple dishes for same guest")

        self.save_button = ttk.Button(
            btn_frame,
            text="FINALIZE ORDER",
            command=self.validate_and_save,
            state="disabled",
            image=self.clipboard_icon,
            style="success.TButton",
            compound="left"
        )
        self.save_button.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        ToolTip(self.save_button, "Press to complete the order")
        self.commit_btn = ttk.Button(
            btn_frame,
            text="SEND TO DATABASE",
            command=self.commit_to_db,
            state="disabled",
            image=self.cloud_icon,
            style="danger.TButton",
            compound="left"
        )
        self.commit_btn.grid(row=0, column=2, padx=5, pady=5, sticky="ew")
        ToolTip(self.commit_btn, "Press to send orders to database")

        self.update_idletasks()
        self._collapsed_sash = paned.sashpos(0)
        self._expanded_sash = 0
        self.tree_expanded = False




        expand_btn.config(command=toggle_tree_expand)
        ToolTip(expand_btn, "Press to Expand/Restore the Orders List")



        # --- Adaptive resizing for Treeview columns ---
        def _resize_cols(event):
            total_w = self.tree.winfo_width() - vsb.winfo_width()
            col_w = max(int(total_w / len(cols)), 50)
            for c in cols:
                self.tree.column(c, width=col_w)

        self.tree.bind("<Configure>", _resize_cols)

        # --- Populate orders ---
        self.refresh_orders()

        # --- Final: Force window layout update and auto-resize ---
        self.after(100, lambda: self.state('zoomed'))

        self.add_allergy_button.config(state='disabled')
    def populate_treeview(self, rows):
        """
        Clear and redraw the order tree with newest‐first unsaved,
        then newest‐first saved rows.
        """
        # clear
        for iid in self.tree.get_children():
            self.tree.delete(iid)

        # split unsaved vs saved
        unsaved = [r for r in rows if not r[10]]  # flag index 10 == from_db
        saved = [r for r in rows if r[10]]

        # newest‐first within each
        unsaved.reverse()
        saved.reverse()

        # insert them
        for idx, row in enumerate(unsaved + saved):
            icon = self.db_icon if row[10] else self.unsaved_icon
            tag = "evenrow" if idx % 2 == 0 else "oddrow"
            self.tree.insert('', 'end', image=icon, values=row[:10], tags=(tag,))

    import threading

    def _on_tree_selection(self, event=None):
        has_sel = bool(self.tree.selection())
        # Actions bar
        self.btn_edit.config(state="normal" if has_sel else "disabled")
        self.btn_delete.config(state="normal" if has_sel else "disabled")
        self.btn_hist.config(state="normal" if has_sel else "disabled")
        # New Order becomes available as soon as a valid cabin is present or a row is selected
        try:
            has_cabin = bool(self.cabin_number_var.get().strip())
        except Exception:
            has_cabin = False
        self.btn_new.config(state="normal" if (has_sel or has_cabin) else "disabled")

    def start_new_order(self):
        """Prefill fields using the selected row and start a fresh order for that same guest."""
        sel = getattr(self, "tree", None).selection() if hasattr(self, "tree") else ()
        if not sel:
            try:
                self.show_toast("Select an order first.", toast_type="warning")
            except Exception:
                messagebox.showwarning("Start New Order", "Please select an order first.")
            return

        # Table columns: MANAGER, CABIN, GUEST NAME, DISH, PAX, ALLERGY, REQUESTS, TIME SLOT, GALLEY SECTION, STANDING
        vals = self.tree.item(sel[0], "values")
        try:
            cabin = str(vals[1]).strip()
            guest = str(vals[2]).strip()  # "FIRST LAST"
            timeslot = str(vals[7]).strip() if len(vals) > 7 else ""
            galley = str(vals[8]).strip() if len(vals) > 8 else ""
            allergy = str(vals[5]).strip() if len(vals) > 5 else ""
        except Exception:
            try:
                self.show_toast("Could not read row values.", toast_type="warning")
            except Exception:
                messagebox.showwarning("Start New Order", "Could not read row values.")
            return

        # Ensure widgets are usable
        try:
            self.occupant_locked = False
            self.cabin_number_entry.config(state='normal')
            self.pax_spinbox.config(state='normal')
            self.timeslot_dropdown.config(state='readonly')
            self.standing_order_check.config(state='normal')
            self.selected_allergies_listbox.config(state='normal')
            self.allergy_combobox.config(state='readonly')
            self.add_allergy_button.config(state='normal')
        except Exception:
            pass

        # --- Key change: set the entry to "[CABIN] - [FIRST LAST]" and mark it as a valid pick
        display_value = f"{cabin} - {guest}" if guest else cabin
        self.cabin_number_var.set(display_value)
        self.guest_name_var.set(guest)

        # If using our AutocompleteEntry, update its internal selection flags so downstream logic treats this as picked
        try:
            ae = self.cabin_number_entry  # AutocompleteEntry
            ae._picked_flag = True
            ae._last_picked_value = display_value
            ae._cabin_only = cabin
        except Exception:
            pass

        # Keep same service context as convenience
        if timeslot:
            self.timeslot_var.set(timeslot.upper())
        if galley:
            self.galley_section_var.set(galley.upper())

        # Start fresh specifics
        self.dish_var.set("")  # new dish
        self.special_requests_var.set("")  # new requests
        self.pax_var.set("1")
        self.standing_order_var.set(False)
        self.show_toast("Guest Selected", 2000, "info")

        # Repopulate "Selected Allergies" from selected row
        try:
            self.selected_allergies_listbox.delete(0, tk.END)
            for note in (allergy or "").split(","):
                n = note.strip()
                if n and n.upper() not in ("None", "NO", "N/A"):
                    self.selected_allergies_listbox.insert(tk.END, n)
        except Exception:
            pass

        # Clear any staged dish rows for previous occupant
        try:
            self.temp_dishes.clear()
        except Exception:
            self.temp_dishes = []

        # Focus where user types next
        try:
            self.dish_entry.focus_set()
            self.dish_entry.icursor(tk.END)
        except Exception:
            pass

        # Keep action-button state consistent
        try:
            self.validate_buttons()
            self._on_tree_selection()
        except Exception:
            pass
    def show_guest_history_for_selected(self):
        sel = self.tree.selection()
        if not sel:
            self.show_toast("Select an order first.", toast_type="warning")
            return

        vals = self.tree.item(sel[0], "values")
        try:
            cabin = vals[1]  # "Cabin"
            guest = vals[2]  # "Guest Name"
        except Exception:
            self.show_toast("Could not read Cabin/Guest from selection.", toast_type="warning")
            return

        rows = self.db_manager.get_preorders_by_guest(cabin, guest)
        if not rows:
            self.show_toast("No history found for this guest.", toast_type="info")
            return

        # Simple history window
        hist = tk.Toplevel(self)
        hist.title(f"History: {guest} (Cabin {cabin})")
        hist.geometry("850x320")
        hist.grab_set()
        hist.iconbitmap('icons/icon_app.ico')

        ttk.Label(hist, text=f"Order History for {guest} - Cabin {cabin}",
                  font=("Helvetica", 14, "bold")).pack(pady=8)

        cols = ("dish", "time", "section", "date", "manager", "venue")
        tv = ttk.Treeview(hist, columns=cols, show="headings")
        for c in cols:
            tv.heading(c, text=c.capitalize())
            tv.column(c, width=120, anchor="center")
        tv.pack(fill="both", expand=True, padx=10, pady=8)

        for r in rows:
            tv.insert("", "end", values=(
                r.get("dish", "N/A"),
                r.get("service_time_slot", "N/A"),
                r.get("galley_section", "N/A"),
                r.get("service_date", "N/A"),
                r.get("manager", "N/A"),
                r.get("venue_name", "N/A"),
            ))

        ttk.Button(hist, text="Close", command=hist.destroy, bootstyle="secondary").pack(pady=(0, 8))

    def recall_guests_by_manager(self):
        import time
        # Show loading window
        loading_win = tk.Toplevel(self)
        loading_win.title("Loading Guests...")
        loading_win.geometry("270x120")
        loading_win.transient(self)
        loading_win.grab_set()
        loading_win.iconbitmap('icons/icon_app.ico')
        ttk.Label(loading_win, text="Fetching data from database...", font=("Helvetica", 12)).pack(pady=(20, 5))
        pb = ttk.Progressbar(loading_win, mode='indeterminate')
        pb.pack(fill="x", padx=30, pady=10)
        pb.start(10)

        def load_guests():
            time.sleep(0.7)
            # Get guests for current manager AND current voyage
            rows = self.db_manager.get_guests_by_manager(self.manager)
            self.after(0, lambda: (loading_win.destroy(),
                                   self._show_recall_popup(rows, self._resolve_current_venue_id())))

        threading.Thread(target=load_guests, daemon=True).start()
    def _update_server_time_label(self):
        if not hasattr(self, "server_time_label"):
            self.after(500, self._update_server_time_label)
            return
        try:
            tz_from_db = self._get_service_timezone()
            tz_label = tz_from_db or "Local Network"
            now = self._now_local()
            cutoff = self._get_cutoff_hour()
            self.server_time_label.config(
                text=f"Server time: {now.strftime('%Y-%m-%d %H:%M:%S')} ({tz_label}) • Cutoff {cutoff:02d}:00"
            )
        except Exception as e:
            self.server_time_label.config(text=f"Server time: n/a ({e})")
        self.after(60000, self._update_server_time_label)

    def _get_current_manager(self):
        # Highest priority: attribute set at login
        mgr = getattr(self, "manager", None)
        if mgr:
            return (mgr or "").strip()

        # Fallbacks used elsewhere in the app
        mgr = getattr(self, "manager_name", None) or getattr(self, "current_manager", None)
        if not mgr:
            try:
                mv = getattr(self, "manager_var", None)
                if mv:
                    mgr = mv.get().strip()
            except Exception:
                pass
        if not mgr:
            try:
                mgr = (self.db_manager.get_config_value("manager_name", "") or "").strip()
            except Exception:
                mgr = ""
        return mgr or ""

    def _current_service_date(self):
        """
        Decide which service_date to use in DB ops.
        Priority:
          1) self.service_date_var (if present & non-empty)
          2) 'tomorrow' if app is in a 'next day' mode flag
          3) today
        """
        from datetime import date, timedelta
        # 1) bound StringVar from UI
        try:
            v = getattr(self, "service_date_var", None)
            if v:
                s = (v.get() or "").strip()
                if s:
                    return s
        except Exception:
            pass

        # 2) optional 'tomorrow mode' flag you might have
        if getattr(self, "use_tomorrow", False):
            return (date.today() + timedelta(days=1)).isoformat()

        # 3) default: today
        return date.today().isoformat()

    def reload_recall_guest_list(self, venue_id=None):
        """
        Build recall list ONLY from PREORDERS, but include rows only if:
          - p.voyage_id == current_voyage_id
          - (optional) p.manager   == current manager
          - (optional) p.venue_id  == venue_id
          - AND guest still exists in GUESTS with SAME voyage_id
        """
        vid = (getattr(self.db_manager, "current_voyage_id", None) or "").strip()
        if not vid:
            self.show_toast("Set Voyage ID first (Admin → Voyage Settings).", toast_type="warning")
            return

        mgr = self._get_current_manager()
        if not mgr:
            self.show_toast("No manager resolved — please log in again.", toast_type="warning")
            return

        p = self.db_manager._param()
        where = [f"p.voyage_id = {p}", f"p.manager = {p}"]
        params = [vid, mgr]

        """if venue_id not in (None, "", 0):
            where.append(f"p.venue_id = {p}")
            params.append(venue_id)"""

        if self.db_manager.backend == "sqlite":
            sql = f"""
                SELECT DISTINCT p.cabin_number, p.guest_name
                  FROM preorders p
                  JOIN guests g
                    ON g.cabin_number = p.cabin_number
                   AND LOWER(g.first_name || ' ' || g.last_name) = LOWER(p.guest_name)
                   AND g.voyage_id = p.voyage_id
                 WHERE {" AND ".join(where)}
                 ORDER BY p.cabin_number, p.guest_name
            """
        else:
            sql = f"""
                SELECT DISTINCT p.cabin_number, p.guest_name
                  FROM preorders p
                  JOIN guests g
                    ON g.cabin_number = p.cabin_number
                   AND LOWER(CONCAT(g.first_name, ' ', g.last_name)) = LOWER(p.guest_name)
                   AND g.voyage_id = p.voyage_id
                 WHERE {" AND ".join(where)}
                 ORDER BY p.cabin_number, p.guest_name
            """

        try:
            with self.db_manager.get_ro_connection() as conn:
                cur = conn.cursor()
                cur.execute(sql, tuple(params))
                rows = cur.fetchall()
        except Exception as e:
            logging.error(f"reload_recall_guest_list failed: {e}", exc_info=True)
            self.show_toast("Failed to load guests.", toast_type="error")
            return

        # Populate UI
        self.guest_listbox.delete(0, tk.END)
        self.guest_map = {}

        for r in rows:
            if self.db_manager.backend == "mysql":
                cabin, guest = r
            else:
                cabin, guest = r["cabin_number"], r["guest_name"]
            display = f"{cabin} - {guest}"
            self.guest_listbox.insert(tk.END, display)
            self.guest_map[display] = (cabin, guest)

        if not rows:
            info = []
            if mgr: info.append(f"manager: {mgr}")
            if venue_id not in (None, "", 0): info.append(f"venue: {venue_id}")
            suffix = " (" + ", ".join(info) + ")" if info else ""
            self.show_toast(f"You have no guests to recall for this voyage yet!", toast_type="warning")





    def _resolve_current_venue_id(self):
        # Try common attributes first
        for attr in ("venue_id", "current_venue_id", "selected_venue_id"):
            v = getattr(self, attr, None)
            if v not in (None, "", 0):
                return v
        # Try UI variable → DB lookup
        try:
            name = getattr(self, "venue_var", None)
            name = name.get().strip() if name else ""
            if name:
                p = self.db_manager._param()
                with self.db_manager.get_connection() as conn:
                    cur = conn.cursor()
                    cur.execute(f"SELECT id FROM venues WHERE name = {p} LIMIT 1", (name,))
                    r = cur.fetchone()
                    if r:
                        return r[0] if self.db_manager.backend == "mysql" else r["id"]
        except Exception as e:
            logging.warning(f"_resolve_current_venue_id: {e}")
        # Try app_config as a last resort
        try:
            v = self.db_manager.get_config_value("current_venue_id", None)
            if v not in (None, "", 0):
                return v
        except Exception:
            pass
        return None

    def _show_recall_popup(self, rows, venue_id=None):
        if venue_id is None:
            venue_id = self._resolve_current_venue_id()
        if venue_id is None:
            self.show_toast("Couldn't determine the current venue.", toast_type="warning")
            return

        # ... your existing popup UI creation code (Toplevel, frames, listbox, buttons) ...

        # After creating self.guest_listbox and self.guest_map, load data:


        popup = tk.Toplevel(self)
        popup.title("Recall Guest")
        popup.geometry("550x500")
        popup.grab_set()
        popup.iconbitmap('icons/icon_app.ico')
        popup.protocol("WM_DELETE_WINDOW", lambda: (popup.grab_release(), popup.destroy()))

        ttk.Label(popup, text="Recall Guest from History", font=("Helvetica", 16, "bold")).pack(pady=(15, 5))
        ttk.Label(popup, text="Search and select a guest:", font=("Helvetica", 12)).pack()

        # Search Frame
        search_frame = ttk.Frame(popup)
        search_frame.pack(fill="x", padx=15, pady=(5, 10))

        search_icon = tk.PhotoImage(file="icons/search.png")
        search_label = ttk.Label(search_frame, image=search_icon)
        search_label.image = search_icon
        search_label.pack(side="left", padx=(0, 5))

        search_var = tk.StringVar()
        search_entry = ttk.Entry(search_frame, textvariable=search_var, font=("Helvetica", 12))
        search_entry.pack(side="left", fill="x", expand=True)
        search_entry.focus()

        # List Frame
        list_frame = ttk.Labelframe(popup, text="Guests with History", padding=10)
        list_frame.pack(fill="both", expand=True, padx=15, pady=(0, 10))

        self.guest_listbox = tk.Listbox(
            list_frame,
            height=14,
            font=("Consolas", 12),
            selectmode=tk.SINGLE,
            activestyle="dotbox"
        )
        self.guest_listbox.pack(side="left", fill="both", expand=True, padx=(0, 5))

        scrollbar = ttk.Scrollbar(list_frame, command=self.guest_listbox.yview)
        scrollbar.pack(side="right", fill="y")
        self.guest_listbox.config(yscrollcommand=scrollbar.set)

        self.guest_map = {}
        self.displayed_items = []

        for row in rows:
            cabin, guest = row["cabin_number"], row["guest_name"]
            display_text = f"Cabin {cabin}: {guest}"
            self.guest_map[display_text] = (cabin, guest)
            self.displayed_items.append(display_text)

        def update_list(*args):
            query = search_var.get().strip().lower()
            self.guest_listbox.delete(0, tk.END)
            for item in self.displayed_items:
                if query in item.lower():
                    self.guest_listbox.insert(tk.END, item)
            if self.guest_listbox.size() > 0:
                self.guest_listbox.select_set(0)
                self.guest_listbox.activate(0)

        def move_up(event=None):
            if self.guest_listbox.size() == 0:
                return
            index = self.guest_listbox.curselection()
            if index and index[0] > 0:
                self.guest_listbox.select_clear(0, tk.END)
                self.guest_listbox.select_set(index[0] - 1)
                self.guest_listbox.activate(index[0] - 1)

        def move_down(event=None):
            if self.guest_listbox.size() == 0:
                return
            index = self.guest_listbox.curselection()
            if not index:
                self.guest_listbox.select_set(0)
                return
            if index[0] < self.guest_listbox.size() - 1:
                self.guest_listbox.select_clear(0, tk.END)
                self.guest_listbox.select_set(index[0] + 1)
                self.guest_listbox.activate(index[0] + 1)

        def handle_return(event=None):
            self.select_recalled_guest(popup)

        # Key Bindings
        search_entry.bind("<Down>", move_down)
        search_entry.bind("<Up>", move_up)
        search_entry.bind("<Return>", handle_return)
        self.guest_listbox.bind("<Return>", handle_return)
        self.guest_listbox.bind("<Double-Button-1>", handle_return)

        search_var.trace_add("write", update_list)
        update_list()

        # Button Frame
        btn_frame = ttk.Frame(popup)
        btn_frame.pack(fill="x", pady=(10, 15), padx=20)
        # Left-aligned View History button (neutral)
        ttk.Button(
            btn_frame,
            text="📄 View History".upper(),
            command=self.view_selected_guest_history,
            bootstyle="information"
        ).pack(side="left", padx=(0, 10))

        # Right-aligned Select and Cancel buttons (colored)
        ttk.Button(
            btn_frame,
            text="✅ Select Guest".upper(),
            command=lambda: self.select_recalled_guest(popup),
            bootstyle="success"
        ).pack(side="right", padx=(10, 0))

        ttk.Button(
            btn_frame,
            text="❌ Cancel".upper(),
            command=popup.destroy,
            bootstyle="danger"
        ).pack(side="right", padx=(0, 10))
        self.reload_recall_guest_list(venue_id)
    def _toggle_unsaved_view(self):
        # flip the flag
        self.show_only_unsaved = not self.show_only_unsaved

        if self.show_only_unsaved:
            # Active: solid warning button
            self.toggle_btn.config(
                text="Show All Orders",
                bootstyle="danger.TButton",
                image=self.db_icon,
                compound="left"
            )
            rows = [r for r in self.all_orders if not r[10]]
        else:
            # Inactive: outlined warning button
            self.toggle_btn.config(
                text="Show Unsaved Only",
                bootstyle="primary.Outline.TButton",
                image=self.unsaved_icon,
                compound="left"
            )
            rows = self.all_orders

        # re‑populate the tree
        self.populate_treeview(rows)

    def get_next_day_date(self):
        now = self._now_local()
        if now.hour < self._get_cutoff_hour():
            target_date = now.date()
        else:
            target_date = now.date() + timedelta(days=1)
        return target_date.strftime("%Y-%m-%d")

    def show_settings_window(self):
        win = tk.Toplevel(self)
        win.title("User Settings")
        win.geometry("400x300")
        win.grab_set()  # modal
        win.iconbitmap('icons/icon_app.ico')  # Added icon for consistency

        # Password Section
        ttk.Separator(win).pack(fill="x", padx=20, pady=10)

        ttk.Label(win, text="Change Password:", font=("Helvetica", 12, "bold")) \
            .pack(anchor="w", padx=20, pady=(10, 5))

        frm = ttk.Frame(win)
        frm.pack(fill="x", padx=20)

        ttk.Label(frm, text="Current:").grid(row=0, column=0, sticky="e", pady=2)
        curr_pw = ttk.Entry(frm, show="*")
        curr_pw.grid(row=0, column=1, sticky="we", pady=2)
        ttk.Label(frm, text="New:").grid(row=1, column=0, sticky="e", pady=2)
        new_pw = ttk.Entry(frm, show="*")
        new_pw.grid(row=1, column=1, sticky="we", pady=2)
        ttk.Label(frm, text="Confirm:").grid(row=2, column=0, sticky="e", pady=2)
        confirm_pw = ttk.Entry(frm, show="*")
        confirm_pw.grid(row=2, column=1, sticky="we", pady=2)
        frm.columnconfigure(1, weight=1)  # Ensure entry fields expand

        def apply_password():
            old = curr_pw.get().strip()
            pw1 = new_pw.get().strip()
            pw2 = confirm_pw.get().strip()
            if not old or not pw1 or not pw2:
                messagebox.showwarning("Settings", "Fill in all password fields.")
                return
            if pw1 != pw2:
                messagebox.showerror("Settings", "New passwords do not match.")
                return
            if not self.db_manager.verify_user(self.manager, old):
                messagebox.showerror("Settings", "Current password is incorrect.")
                return
            if self.db_manager.update_user_password(self.manager, pw1):
                messagebox.showinfo("Settings", "Password updated successfully!")
                win.destroy()
            else:
                messagebox.showerror("Settings", "Failed to update password.")

        btn_frame = ttk.Frame(win)
        btn_frame.pack(fill="x", padx=20, pady=(0, 20))

        ttk.Button(btn_frame, text="Change Password",
                   command=apply_password, bootstyle="success") \
            .pack(side="right", padx=5)

        ttk.Button(btn_frame, text="Cancel",
                   command=win.destroy, bootstyle="danger") \
            .pack(side="right", padx=5)

        # Focus on current password field
        curr_pw.focus_set()

        # Bind Enter key to trigger password change
        win.bind("<Return>", lambda e: apply_password())
    def view_selected_guest_history(self):
        selection = self.guest_listbox.curselection()
        if not selection:
            self.show_toast("Please select a guest first.", toast_type="warning")
            return

        selected_text = self.guest_listbox.get(selection[0])
        cabin, guest = self.guest_map[selected_text]

        # Fetch orders for the selected guest
        orders = self.db_manager.get_preorders_by_guest(cabin, guest)

        if not orders:
            self.show_toast("No order history found for this guest.", toast_type="warning")
            return

        # Create window to show history
        hist_win = tk.Toplevel(self)
        hist_win.title(f"Order History for {guest}")
        hist_win.geometry("850x300")
        hist_win.grab_set()
        hist_win.iconbitmap('icons/icon_app.ico')

        ttk.Label(
            hist_win,
            text=f"Order History for {guest} - Cabin {cabin}",
            font=("Helvetica", 14, "bold")
        ).pack(pady=10)

        cols = ("dish", "time", "section", "date", "manager", "venue")
        tree = ttk.Treeview(hist_win, columns=cols, show="headings")
        tree.pack(fill="both", expand=True, padx=10, pady=10)

        for col in cols:
            tree.heading(col, text=col.capitalize())
            tree.column(col, width=100)

        style = ttk.Style()
        style.configure("Treeview", rowheight=25)
        style.configure("Treeview.Heading", font=("Helvetica", 11, "bold"))
        style.map('Treeview', background=[('selected', '#ab0c24')])
        style.configure("Treeview", borderwidth=1, relief="solid")

        for row in orders:
            tree.insert("", tk.END, values=(
                row.get("dish", "N/A"),
                row.get("service_time_slot", "N/A"),
                row.get("galley_section", "N/A"),
                row.get("service_date", "N/A"),
                row.get("manager", "N/A"),
                row.get("venue_name", "N/A")
            ))

        ttk.Button(hist_win, text="Close", command=hist_win.destroy).pack(pady=5)

    def select_recalled_guest(self, popup):
        selection = self.guest_listbox.curselection()
        if not selection:
            self.show_toast("Please select a guest.", toast_type="warning")
            return

        selected_text = self.guest_listbox.get(selection[0])
        cabin, guest = self.guest_map[selected_text]

        # ----- NEW: verify guest still exists in GUESTS for current voyage -----
        vid = getattr(self.db_manager, "current_voyage_id", None)
        if not vid:
            self.show_toast("Set Voyage ID first (Admin → Voyage Settings).", toast_type="warning")
            return

        try:
            p = self.db_manager._param()
            if self.db_manager.backend == "sqlite":
                sql_check = f"""
                    SELECT 1
                      FROM guests
                     WHERE cabin_number = {p}
                       AND LOWER(first_name || ' ' || last_name) = LOWER({p})
                       AND voyage_id = {p}
                     LIMIT 1
                """
            else:
                sql_check = f"""
                    SELECT 1
                      FROM guests
                     WHERE cabin_number = {p}
                       AND LOWER(CONCAT(first_name, ' ', last_name)) = LOWER({p})
                       AND voyage_id = {p}
                     LIMIT 1
                """
            with self.db_manager.get_ro_connection() as conn:
                cur = conn.cursor()
                cur.execute(sql_check, (cabin, guest, vid))
                exists = cur.fetchone() is not None

            if not exists:
                # Remove obsolete entry from UI and map; stop here.
                self.guest_listbox.delete(selection[0])
                try:
                    del self.guest_map[selected_text]
                except KeyError:
                    pass
                self.show_toast("This guest is no longer on the manifest for this voyage.", toast_type="info")
                return
        except Exception as e:
            logging.error(f"Guest existence check failed: {e}", exc_info=True)
            # If check fails, fail-safe: don't proceed with recall
            return
        # ----- END NEW GUARD -----

        # Prevent automatic guest selection while we update fields
        self.programmatic_cabin_set = True

        # Set cabin and guest in main form
        self.cabin_number_var.set(f"{cabin} - {guest}")
        self.guest_name_var.set(guest)
        if hasattr(self, "cabin_number_entry"):
            self.cabin_number_entry._cabin_only = cabin

        # Clear allergies listbox
        self.selected_allergies_listbox.delete(0, tk.END)

        # Debug logs
        logging.debug(f"Fetching orders for cabin: {cabin}, guest: {guest}")

        # 1) Fetch orders (voyage-scoped in DB helper)
        try:
            orders = self.db_manager.get_preorders_by_guest(cabin, guest)
        except Exception as e:
            logging.error(f"Error fetching orders: {e}", exc_info=True)
            orders = []

        logging.debug(f"Received {len(orders)} orders for allergy processing")

        # 2) Build allergy set from orders
        allergies_set = set()
        for idx, row in enumerate(orders):
            logging.debug(f"Processing order #{idx + 1}: {row}")
            try:
                if isinstance(row, dict):
                    notes = row.get("allergy_notes", "") or ""
                elif isinstance(row, (tuple, list)) and len(row) > 5:
                    notes = row[7] if len(row) > 7 else (row[5] or "")
                else:
                    notes = ""
            except Exception as e:
                logging.error(f"Error accessing allergy_notes: {e}")
                notes = ""

            if not notes or str(notes).strip().upper() == "None":
                continue

            cleaned = str(notes).replace(";", ",").replace("\n", ",")
            for token in cleaned.split(","):
                token = token.strip()
                if token:
                    allergies_set.add(token.upper())

        # 3) Fallback: latest allergy_notes from preorders (voyage-scoped)
        if not allergies_set:
            try:
                p = self.db_manager._param()
                sql = f"""
                    SELECT allergy_notes
                      FROM preorders
                     WHERE cabin_number = {p}
                       AND guest_name    = {p}
                       AND voyage_id     = {p}
                       AND allergy_notes IS NOT NULL
                       AND TRIM(allergy_notes) <> ''
                     ORDER BY service_date DESC, id DESC
                     LIMIT 1
                """
                with self.db_manager.get_connection() as conn:
                    cur = conn.cursor()
                    cur.execute(sql, (cabin, guest, vid))
                    row = cur.fetchone()
                    if row:
                        notes = row[0] if self.db_manager.backend == "mysql" else row["allergy_notes"]
                        cleaned = str(notes).replace(";", ",").replace("\n", ",")
                        for token in cleaned.split(","):
                            token = token.strip()
                            if token:
                                allergies_set.add(token.upper())
            except Exception as e:
                logging.error(f"Fallback allergy fetch failed: {e}", exc_info=True)

        # Populate allergies listbox
        self.selected_allergies_listbox.delete(0, tk.END)
        for allergy in sorted(allergies_set):
            self.selected_allergies_listbox.insert(tk.END, allergy)

        # Enable controls to add new allergies
        self.allergy_combobox.config(state='readonly')
        self.add_allergy_button.config(state='normal')

        # Default selection if none found
        if not allergies_set:
            try:
                self.allergy_combobox.set("None")
            except Exception:
                self.allergy_combobox.set("")

        # Update UI state
        self.update_remove_button_state()

        # Clear the guard flag
        self.programmatic_cabin_set = False

        # Close popup and focus dish entry
        popup.destroy()
        self.dish_entry.focus_set()

    def update_remove_button_state(self, event=None):
        """Update the visibility and state of the Remove button based on listbox content."""
        if self.selected_allergies_listbox.size() == 0:
            self.rem_btn.grid_remove()  # Hide the Remove button
        else:
            self.rem_btn.grid()  # Show the Remove button
            selected = self.selected_allergies_listbox.curselection()
            self.rem_btn["state"] = "normal" if selected else "disabled"

    def add_to_order(self):
        newly_locked = False  # Track if we locked fields in this call
        self.dish_entry.focus_set()
        # 1. Validate occupant-level fields if not locked
        if not self.occupant_locked:
            self.get_current_cabin_number()
            guest = self.guest_name_var.get()
            cabin = self.get_current_cabin_number()

            px = self.pax_var.get().strip()
            ts = self.timeslot_var.get().strip().upper()

            # Validate occupant fields
            valid = True
            if not cabin:
                self.show_toast("Cabin # required before adding a dish.", toast_type="warning")
                valid = False
            elif not px.isdigit() or int(px) < 1:
                self.show_toast("Pax must be a positive integer before adding a dish.", toast_type="warning")
                valid = False
            elif not ts:
                self.show_toast( "Time slot required before adding a dish.", toast_type="warning")
                valid = False

            if not valid:
                return  # Exit without locking fields

            # Lock fields if validation passed
            self.occupant_locked = True
            newly_locked = True
            self.cabin_number_entry.config(state='disabled')
            self.pax_spinbox.config(state='disabled')
            self.timeslot_dropdown.config(state='disabled')
            self.standing_order_check.config(state='disabled')
            self.selected_allergies_listbox.config(state='disabled')
            self.allergy_combobox.config(state='disabled')
            self.add_allergy_button.config(state='disabled')
            self.btn_edit.config(state="disabled")
            self.btn_delete.config(state="disabled")
            self.btn_new.config(state="disabled")
            self.btn_hist.config(state="disabled")


        # 2. Validate dish-level fields
        dish = self.dish_var.get().strip().upper()
        reqs = self.special_requests_var.get().strip().upper()
        galley = self.galley_section_var.get().strip().upper()

        if not dish:
            self.show_toast("Dish is required before adding.", toast_type="warning")

            # Unlock occupant fields if we locked them in this operation
            if newly_locked:
                self.occupant_locked = False
                self.cabin_number_entry.config(state='normal')
                self.pax_spinbox.config(state='normal')
                self.timeslot_dropdown.config(state='readonly')
                self.standing_order_check.config(state='normal')
                self.selected_allergies_listbox.config(state='normal')
                self.allergy_combobox.config(state='readonly')
                self.add_allergy_button.config(state='normal')
                self._on_tree_selection()

            return

        # 3. Add valid dish to temp list
        self.temp_dishes.append((dish, reqs, galley))

        # 4. Clear dish fields
        self.dish_var.set("")
        self.special_requests_var.set("")
        self.galley_section_var.set(GALLEY_SECTIONS[0])

        self.show_toast(f"{dish} has been added successfully!\nPlease add new dish or click Finalize Order", toast_type="info")

        self.validate_buttons()



    def on_allergy_selected(self, event=None):
        choice = self.allergy_selected_var.get()
        if choice == "None":
            self.add_allergy_button.config(state='disabled')
        else:
            self.add_allergy_button.config(state='normal')
        self.selected_allergies_listbox.config(state='normal')
        self.update_remove_button_state()  # So "Remove" button state updates

    def on_cabin_change(self):
        if getattr(self, 'programmatic_cabin_set', False):
            self.programmatic_cabin_set = False  # Reset the flag
            return

        cabin = getattr(self.cabin_number_entry, "_cabin_only",
                        self.cabin_number_var.get())
        guest = self.guest_name_var.get()



        if not cabin:
            self.guest_name_var.set("")  # Clear guest name if cabin is empty
            return

        try:
            guests = self.db_manager.get_guests_for_cabin(cabin)
            logging.debug(f"Guests fetched: {guests}")  # Log fetched guests
            if not guests:
                self.guest_name_var.set("No guests found")  # Display message if no guests
            elif len(guests) == 1:
                # Auto-select if only one guest
                guest_name = f"{guests[0]['first_name']} {guests[0]['last_name']}".strip()
                self.guest_name_var.set(guest_name)
            else:
                # Multiple guests: prompt user to select
                self.popup_guest_selection(guests)
        except Exception as e:
            self.guest_name_var.set("Error fetching guest")
            logging.error(f"Error in on_cabin_change: {e}")

    # ---------------------------- ALLERGY HANDLERS ----------------------------

    def recall_allergies(self):
        """
        Recall occupant-level allergies based on cabin and guest information.
        Fetches allergies from the database and populates the listbox.
        """
        cabin = getattr(self.cabin_number_entry, "_cabin_only",
                        self.cabin_number_var.get())
        guest = self.guest_name_var.get().strip()

        if not cabin or not guest:
            # Clear the listbox and disable combobox if inputs are invalid
            self.selected_allergies_listbox.delete(0, tk.END)
            self.allergy_combobox.config(state='disabled')
            self.add_allergy_button.config(state='disabled')
            self.unsaved_data = False
            return

        try:
            # Fetch allergies from the database
            occupant_preorders = self.db_manager.get_preorders_by_guest(cabin, guest)
            logging.debug(f"Fetched allergies for cabin {cabin}, guest {guest}: {occupant_preorders}")

            # Process and deduplicate allergy strings
            allergy_strings = set()
            for row in occupant_preorders:
                notes = row.get("allergy_notes", "").strip()
                if notes:
                    for note in notes.split(","):
                        if note.strip().lower() != "None":
                            allergy_strings.add(note.strip())

            # Update the listbox with allergies
            self.selected_allergies_listbox.delete(0, tk.END)
            if allergy_strings:
                for allergy in sorted(allergy_strings):
                    self.selected_allergies_listbox.insert(tk.END, allergy)
                self.allergy_combobox.config(state='readonly')
                self.add_allergy_button.config(state='normal')
            else:
                self.allergy_combobox.config(state='disabled')
                self.add_allergy_button.config(state='disabled')

            self.unsaved_data = True

        except Exception as e:
            logging.error(f"Error recalling allergies for cabin {cabin}, guest {guest}: {e}")
            self.selected_allergies_listbox.delete(0, tk.END)
            self.allergy_combobox.config(state='disabled')
            self.add_allergy_button.config(state='disabled')
            self.unsaved_data = False

    def add_allergy(self):
        sel = self.allergy_selected_var.get()
        if not sel:
            messagebox.showwarning("Selection Error", "Select an allergy first.")
            return


        # If "Other" is selected, prompt for custom input
        if sel.lower() == "other":
            custom_allergy = simpledialog.askstring(
                "Custom Allergy",
                "Please enter the unique allergy:",
                parent=self
            )
            if custom_allergy:
                # Check if the custom allergy already exists
                existing = self.selected_allergies_listbox.get(0, tk.END)
                if custom_allergy in existing:
                    messagebox.showwarning("Duplicate", f"'{custom_allergy}' already in list.")
                    return
                self.selected_allergies_listbox.insert(tk.END, custom_allergy)
            else:
                return  # User cancelled input
        else:
            # Add selected allergy to the listbox
            existing = self.selected_allergies_listbox.get(0, tk.END)
            if sel in existing:
                messagebox.showwarning("Duplicate", f"'{sel}' already in list.")
                return
            self.selected_allergies_listbox.insert(tk.END, sel)


        # Clear the combobox selection
        self.allergy_combobox.set("")
        self.unsaved_data = True

    def validate_buttons(self, *args):
        """Update button states based on current conditions"""
        # Cabin number validation
        has_cabin = bool(self.cabin_number_var.get().strip())
        self.valid_cabin_entered.set(has_cabin)

        # Add to Order/Save to Sheet buttons
        self.add_to_order_btn['state'] = 'normal' if has_cabin else 'disabled'
        self.save_button['state'] = 'normal' if has_cabin else 'disabled'

        # Database button
        any_unsaved = any(not order[10] for order in self.all_orders)  # Check from_db flag
        self.commit_btn['state'] = 'normal' if any_unsaved else 'disabled'

    def remove_selected_allergy(self, event=None):
        idxs = self.selected_allergies_listbox.curselection()
        if not idxs:
            return
        for i in reversed(idxs):
            self.selected_allergies_listbox.delete(i)
        self.unsaved_data = True

    def show_help_info(self):
        """
        Opens a small Toplevel window with contact info and a help GIF.
        """
        help_win = tk.Toplevel(self)
        help_win.title("Contact Info")
        help_win.geometry("460x460")
        help_win.resizable(False, False)
        help_win.iconbitmap('icons/icon_app.ico')

        # Center the window on the screen
        help_win.update_idletasks()
        x = (help_win.winfo_screenwidth() - help_win.winfo_reqwidth()) // 2
        y = (help_win.winfo_screenheight() - help_win.winfo_reqheight()) // 2
        help_win.geometry(f"+{x}+{y}")



        # Label with your contact details
        info_label = ttk.Label(
            help_win,
            text=(
                "Please contact for suggestions or help:\n\n"
                "Email: asayginvarol@live.com\n"
                "WhatsApp: +905433520378\n\n"
                "Created by Ahmet Saygin VAROL for Princess Cruises.\n"
                "All rights reserved ® 2025"
            ),
            font=("Helvetica", 12),
            justify="center",
            padding=20
        )
        info_label.pack(expand=True, fill="both")

    # ---------------------------- VALIDATE & SAVE (Send to Tree) ----------------------------

    from uuid import uuid4

    def validate_and_save(self):
        # --- guard: suspend any auto-refreshes while we manipulate form vars ---
        was_suspended = getattr(self, "_suspend_order_refresh", False)
        self._suspend_order_refresh = True
        try:
            dish = self.dish_var.get().strip().upper()
            reqs = self.special_requests_var.get().strip().upper()
            galley = self.galley_section_var.get().strip().upper()

            # (unchanged) multi-dish staging block...
            if dish:
                cabin = self.get_current_cabin_number()
                px = self.pax_var.get().strip()
                ts = self.timeslot_var.get().strip().upper()
                if not cabin:
                    messagebox.showwarning("Validation", "Cabin # required before saving.")
                    return
                if not px.isdigit() or int(px) < 1:
                    messagebox.showwarning("Validation", "Pax must be a positive integer before saving.")
                    return
                if not ts:
                    messagebox.showwarning("Validation", "Time slot required before saving.")
                    return

                if not self.occupant_locked:
                    self.occupant_locked = True
                    self.cabin_number_entry.config(state='disabled')
                    self.pax_spinbox.config(state='disabled')
                    self.timeslot_dropdown.config(state='disabled')
                    self.standing_order_check.config(state='disabled')
                    self.selected_allergies_listbox.config(state='disabled')
                    self.allergy_combobox.config(state='disabled')
                    self.add_allergy_button.config(state='disabled')

                self.temp_dishes.append((dish, reqs, galley))
                self.dish_var.set("")
                self.special_requests_var.set("")
                self.galley_section_var.set(GALLEY_SECTIONS[0])

            if self.occupant_locked and self.temp_dishes:
                self.multi_dish_finalize()
                return

            # SINGLE-DISH path
            cabin = getattr(self.cabin_number_entry, "_cabin_only", self.cabin_number_var.get())
            px = self.pax_var.get().strip()
            ts = self.timeslot_var.get().strip().upper()
            stand = "YES" if self.standing_order_var.get() else "NO"
            arr = self.selected_allergies_listbox.get(0, tk.END)
            allergy = ", ".join(arr).upper() if arr else "None"
            guest = self.guest_name_var.get().strip()

            if not cabin:
                messagebox.showwarning("Validation", "Cabin number required.")
                return
            if not dish:
                messagebox.showwarning("Validation", "Dish required.")
                return
            if not px.isdigit() or int(px) < 1:
                messagebox.showwarning("Validation", "Pax must be a positive value.")
                return
            if not ts:
                messagebox.showwarning("Validation", "Time slot required.")
                return

            # Build order tuple (keep your structure)
            order = (self.manager, cabin, guest, dish, px, allergy, reqs, ts, galley, stand, False)
            self.all_orders.append(order)

            # --- ensure pending store & unique iid ---
            if not hasattr(self, "pending_orders"):
                self.pending_orders = {}
            pid = f"pending-{uuid4().hex}"
            self.pending_orders[pid] = {"values": order[:10]}

            # Insert with a stable iid and a 'pending' tag
            try:
                self.tree.tag_configure("pending", font=("Helvetica", 10, "italic"))
            except Exception:
                pass
            self.tree.insert('', tk.END, iid=pid, image=self.unsaved_icon, values=order[:10], tags=("pending",))

            self.show_toast(f"{dish} has been added for Cabin {cabin}.", toast_type="info")
            self.unsaved_data = True

            # Unlock & reset form (guard still on to avoid triggering reload handlers)
            self.occupant_locked = False
            self.cabin_number_entry.config(state="normal")
            self.pax_spinbox.config(state="normal")
            self.timeslot_dropdown.config(state="readonly")
            self.standing_order_check.config(state="normal")
            self.selected_allergies_listbox.config(state="normal")
            self.allergy_combobox.config(state="readonly")
            self.add_allergy_button.config(state="normal")

            self.cabin_number_var.set("")
            self.guest_name_var.set("")
            self.pax_var.set("1")
            self.timeslot_var.set("DINNER")
            self.standing_order_var.set(False)
            self.selected_allergies_listbox.delete(0, tk.END)
            self.allergy_combobox.set("None")

            self.dish_var.set("")
            self.special_requests_var.set("")
            self.galley_section_var.set(GALLEY_SECTIONS[0])

            self.validate_buttons()

        finally:
            # release guard; if a refresh was requested while suspended, run one now
            self._suspend_order_refresh = was_suspended
            if not self._suspend_order_refresh and getattr(self, "_refresh_requested_during_suspend", False):
                self._refresh_requested_during_suspend = False
                try:
                    self.reload_orders_from_db_merge_pending()
                except Exception:
                    pass

    def reload_orders_from_db_merge_pending(self):
        """
        Reload committed orders from DB, then reinsert any pending rows.
        """
        # 1) If a refresh is currently suspended, just mark and bail
        if getattr(self, "_suspend_order_refresh", False):
            self._refresh_requested_during_suspend = True
            return

        # 2) Clear and repopulate committed rows from DB (your existing logic)
        self.tree.delete(*self.tree.get_children())
        committed_rows = self.db_manager.get_orders_by_date(self.current_service_date, self.venue_id)  # your function
        for r in committed_rows:
            iid = f"db-{r['id']}" if isinstance(r, dict) else f"db-{r[0]}"
            self.tree.insert('', 'end', iid=iid, values=(...))  # your mapping

        # 3) Reinsert pending rows
        for pid, obj in getattr(self, "pending_orders", {}).items():
            self.tree.insert('', 'end', iid=pid, values=obj["values"], tags=("pending",))

    def multi_dish_finalize(self):
        cabin = getattr(self.cabin_number_entry, "_cabin_only",
                        self.cabin_number_var.get())
        px = self.pax_var.get().strip()
        guest = self.guest_name_var.get().strip()
        ts = self.timeslot_var.get().strip().upper()
        stand = "YES" if self.standing_order_var.get() else "NO"

        # allergies
        arr = self.selected_allergies_listbox.get(0, tk.END)
        allergy = ", ".join(arr).upper() if arr else "None"

        # Basic occupant validation
        if not cabin:
            messagebox.showwarning("Validation", "Cabin number is missing.")
            return
        if not px.isdigit() or int(px) < 1:
            messagebox.showwarning("Validation", "Pax must be a positive value.")
            return
        if not ts:
            messagebox.showwarning("Validation", "Time slot required.")
            return

        # Insert each dish from temp_dishes into the tree
        inserted_count = 0
        for (dish, reqs, gal) in self.temp_dishes:
            order = (
                self.manager,  # who is manager
                cabin,  # occupant-level cabin
                guest,  # occupant-level guest
                dish,
                px,
                allergy,
                reqs,
                ts,
                gal,
                stand,
                False  # from_db = False
            )
            self.all_orders.append(order)
            self.tree.insert('', tk.END, image=self.unsaved_icon, values=order[:10])

            inserted_count += 1

        # Show a summary message
        self.show_toast(
            f"{inserted_count} dish(es) added for Cabin {cabin}.",toast_type="info"
        )
        self.unsaved_data = True

        # ---------------------------------------------------------
        # 1) UNLOCK occupant-level fields for the *next* occupant
        # ---------------------------------------------------------
        self.occupant_locked = False  # occupant is no longer locked
        self.cabin_number_entry.config(state='normal')
        self.pax_spinbox.config(state='normal')
        self.standing_order_check.config(state='normal')
        self.selected_allergies_listbox.config(state='normal')
        self.allergy_combobox.config(state='readonly')
        self.add_allergy_button.config(state='normal')

        # ---------------------------------------------------------
        # 2) Also keep Dish, Special Requests, Time Slot enabled
        # (which is already 'normal' or 'readonly' from your code)
        # ---------------------------------------------------------
        self.dish_entry.config(state='normal')
        self.special_requests_entry.config(state='normal')
        self.timeslot_dropdown.config(state='readonly')  # or "normal"

        # ---------------------------------------------------------
        # 3) CLEAR occupant-level fields
        # ---------------------------------------------------------
        self.cabin_number_var.set("")
        self.guest_name_var.set("")
        self.pax_var.set("1")
        self.timeslot_var.set("DINNER")
        self.standing_order_var.set(False)
        self.selected_allergies_listbox.delete(0, tk.END)
        self.allergy_combobox.set("None")

        # Clear the multi-dish data
        self.temp_dishes.clear()

        # ---------------------------------------------------------
        # 4) CLEAR Dish & Special Requests fields
        # ---------------------------------------------------------
        self.dish_var.set("")
        self.special_requests_var.set("")
        self.galley_section_var.set(GALLEY_SECTIONS[0])
        self.timeslot_var.set("DINNER")

        # ---------------------------------------------------------
        # 5) Focus on Dish, and let Enter move to Special Requests
        # ---------------------------------------------------------
        self.cabin_number_entry.focus
        self.dish_entry.bind("<Return>", lambda e: self.special_requests_entry.focus())
        self.special_requests_entry.bind("<Return>", lambda e: self.timeslot_dropdown.focus())

    # ---------------------------- REFRESH ----------------------------
    def refresh_orders(self):
        # Always use tomorrow's date for preorders
        sd = self._next_service_date()
        self.service_date_var.set(sd)
        rows = self.db_manager.get_preorders(sd, self.venue_id)

        # Fetch orders for tomorrow
        rows = self.db_manager.get_preorders(sd, self.venue_id)

        # Rest of the method remains the same...
        self.today_dishes = []
        for r in rows:
            dish_value = r[3] if self.db_manager.backend == "mysql" else r["dish"]
            if dish_value:
                self.today_dishes.append(dish_value.upper())

        self.all_orders.clear()
        for r in rows:
            if self.db_manager.backend == "mysql":
                # Tuple access
                manager = r[0] or ""
                cabin = r[1] or ""
                guest = r[2] or ""
                dish = r[3] or ""
                pax = str(r[4] or "1")
                al = r[5] or "None"
                req = r[6] or ""
                ts = r[7] or ""
                gal = r[8] or ""
                st = r[9] or "NO"
            else:
                # Dictionary access
                manager = r["manager"] or ""
                cabin = r["cabin_number"] or ""
                guest = (r["guest_name"] if "guest_name" in r.keys() else "") or ""
                dish = r["dish"] or ""
                pax = str(r["pax"] or "1")
                al = r["allergy_notes"] or "None"
                req = r["special_requests"] or ""
                ts = r["service_time_slot"] or ""
                gal = r["galley_section"] or ""
                st = r["standing_order"] or "NO"

            tup = (manager, cabin, guest, dish, pax, al, req, ts, gal, st, True)
            self.all_orders.append(tup)

        self.populate_treeview(self.all_orders)
        if hasattr(self, 'dish_entry'):
            self.dish_entry.update_suggestions(self.today_dishes)    # ---------------------------- COMMIT TO DB ----------------------------
    def commit_to_db(self):
        if not self.tree.get_children():
            messagebox.showinfo("No Data", "No orders in the tree.")
            return

        sd = self._selected_or_next_service_date()
        committed = 0
        new_list = []

        for o in self.all_orders:
            # o = (manager, cabin, guest, dish, px, al, rq, ts, gal, st, from_db)
            from_db = o[10]
            if not from_db:
                manager, cabin, guest, dish, px, al, rq, tslot, gsect, st = o[:10]
                if not cabin:
                    continue

                pre = {
                    'manager': manager,
                    'cabin_number': cabin,
                    'guest_name': guest,
                    'dish': dish,
                    'pax': int(px),
                    'allergy_notes': al,
                    'special_requests': rq,
                    'service_time_slot': tslot,
                    'galley_section': gsect,
                    'standing_order': st,
                    'venue_id': self.venue_id,
                    'service_date': sd
                }

                ok = self.db_manager.insert_preorder(pre)
                if ok:
                    committed += 1
                    # now that it's in DB, mark from_db=True
                    new_list.append((manager, cabin, guest, dish, px, al, rq, tslot, gsect, st, True))
                else:
                    new_list.append(o)
            else:
                # already in DB, keep as-is
                new_list.append(o)

        if committed >= 1:
            self.commit_btn.config(state="disabled")
            if committed == 1:
                self.show_toast(f"{committed} order has been sent to the database.", toast_type="info")
            else:
                self.show_toast(f"{committed} orders have been sent to the database", toast_type="info")

            # Refresh the tree with updated icons (always, for both cases)
            for it in self.tree.get_children():
                self.tree.delete(it)
            self.all_orders = new_list
            for nt in new_list:
                icon = self.db_icon if nt[10] else self.unsaved_icon
                self.tree.insert('', tk.END,
                                 image=icon,
                                 values=nt[:10])
            self.unsaved_data = False
        else:
            messagebox.showerror("Commit Failed", "No new orders committed.")

        self.validate_buttons()
        self.refresh_orders()


    # ---------------------------- SEARCH / UPDATE TREEVIEW ----------------------------
    def update_treeview(self):
        # base list of orders (probably self.all_orders or similar)
        rows = list(self.all_orders)

        # filter “My Orders Only”
        if self.show_mine_var.get():
            rows = [r for r in rows if r[0] == self.manager]

        # your existing search‐text filtering
        q = self.search_var.get().strip().lower()
        if q:
            rows = [
                r for r in rows
                if any(q in str(field).lower() for field in r)
            ]

        # then re‑insert into the tree exactly as you already do:
        for iid in self.tree.get_children():
            self.tree.delete(iid)
        for idx, r in enumerate(rows):
            icon = self.db_icon if r[10] else self.unsaved_icon
            tag = "evenrow" if idx % 2 == 0 else "oddrow"
            self.tree.insert('', 'end', image=icon, values=r[:10], tags=(tag,))

    # ---------------------------- CONTEXT MENU HANDLERS ----------------------------
    def on_tree_right_click(self, event):
        row_id = self.tree.identify_row(event.y)
        if not row_id:
            return
        self.tree.selection_set(row_id)
        self.context_menu.post(event.x_root, event.y_root)

    def on_edit_order(self):
        """
        Let user edit the selected order's fields.
        If the order is from_db=True, ask for the manager's password to proceed.
        """
        selected = self.tree.selection()
        if not selected:
            return

        item_id = selected[0]
        # The Treeview has 10 columns in .item(..., "values")
        # => (manager, cabin, guest, dish, pax, allergy, requests, timeslot, galley, standing)
        tree_values = self.tree.item(item_id, "values")

        # Find matching order in self.all_orders
        matched_idx = None
        for i, order_tuple in enumerate(self.all_orders):
            # order_tuple[:10] are the first 10 fields that match the Treeview
            if order_tuple[:10] == tree_values:
                matched_idx = i
                break

        if matched_idx is None:
            messagebox.showerror("Error", "Could not locate the order in memory.")
            return

        # Found the order tuple
        order = self.all_orders[matched_idx]
        # order = (manager, cabin, guest, dish, pax, allergy, req, timeslot, galley, stand, from_db)
        from_db = order[10]
        manager_for_order = order[0]

        # If from_db, verify manager's password
        if from_db:
            pw = simpledialog.askstring(
                "Manager Password",
                f"Order belongs to '{manager_for_order}' in DB.\n"
                f"Enter manager password:",
                show='*'
            )
            if not pw:
                return
            # check password
            if not self.db_manager.verify_user(manager_for_order, pw):
                messagebox.showerror("Access Denied", "Incorrect password.")
                return

        # Show popup to edit
        self.edit_popup(order, matched_idx)

    def edit_popup(self, order, idx):
        """
        A Toplevel to let user edit the fields of an existing order in two columns.
        order = (
            manager, cabin, guest, dish, pax, allergy, requests,
            timeslot, galley, stand, from_db
        )
        """
        popup = tk.Toplevel(self)
        popup.title("Edit Order")
        popup.geometry("600x320")
        popup.resizable(False, False)
        popup.iconbitmap('icons/icon_app.ico')

        manager, cabin, guest, dish, pax, allergy, req, timeslot, galley, stand, from_db = order

        # Main frame (grid-based layout, 5 rows x 4 columns)
        main_frame = ttk.Frame(popup, padding=10)
        main_frame.grid(sticky="nsew")
        for r in range(6):
            main_frame.grid_rowconfigure(r, weight=1)
        for c in range(4):
            main_frame.grid_columnconfigure(c, weight=1)

        # ------------------------------------------------------------
        # Row 0: Cabin Number (left), Guest Name (right)
        # ------------------------------------------------------------
        cabin_var = tk.StringVar(value=cabin)
        ttk.Label(main_frame, text="Cabin Number:", font=("Helvetica", 12)).grid(
            row=0, column=0, sticky='e', padx=(0, 5), pady=5
        )
        cabin_entry = ttk.Entry(main_frame, textvariable=cabin_var, state="readonly", width=20)
        cabin_entry.grid(row=0, column=1, sticky='w', pady=5)

        guest_var = tk.StringVar(value=guest)
        ttk.Label(main_frame, text="Guest Name:",  font=("Helvetica", 12)).grid(
            row=0, column=2, sticky='e', padx=(10, 5), pady=5
        )
        guest_entry = ttk.Entry(main_frame, textvariable=guest_var, state="readonly", width=20)
        guest_entry.grid(row=0, column=3, sticky='w', pady=5)

        # ------------------------------------------------------------
        # Row 1: Dish (left), Pax (right)
        # ------------------------------------------------------------
        dish_var = tk.StringVar(value=dish)
        ttk.Label(main_frame, text="Dish:", font=("Helvetica", 12)).grid(
            row=1, column=0, sticky='e', padx=(0, 5), pady=5
        )
        dish_entry = ttk.Entry(main_frame, textvariable=dish_var, width=20)
        dish_entry.grid(row=1, column=1, sticky='w', pady=5)

        pax_var = tk.StringVar(value=pax)
        ttk.Label(main_frame, text="Pax:", font=("Helvetica", 12)).grid(
            row=1, column=2, sticky='e', padx=(10, 5), pady=5
        )
        pax_entry = ttk.Entry(main_frame, textvariable=pax_var, width=6)
        pax_entry.grid(row=1, column=3, sticky='w', pady=5)

        # ------------------------------------------------------------
        # Row 2: Requests (left), Time Slot (right)
        # ------------------------------------------------------------
        req_var = tk.StringVar(value=req)
        ttk.Label(main_frame, text="Special Requests:",  font=("Helvetica", 12)).grid(
            row=2, column=0, sticky='e', padx=(0, 5), pady=5
        )
        req_entry = ttk.Entry(main_frame, textvariable=req_var, width=20)
        req_entry.grid(row=2, column=1, sticky='w', pady=5)

        ttk.Label(main_frame, text="Time Slot:", font=("Helvetica", 12)).grid(
            row=2, column=2, sticky='e', padx=(10, 5), pady=5
        )
        timeslot_var = tk.StringVar(value=timeslot)
        timeslot_combo = ttk.Combobox(
            main_frame, textvariable=timeslot_var,
            values=TIMESLOTS, state="readonly", width=18
        )
        timeslot_combo.grid(row=2, column=3, sticky='w', pady=5)

        # ------------------------------------------------------------
        # Row 3: Galley Section (left), Standing Order (right)
        # ------------------------------------------------------------
        ttk.Label(main_frame, text="Galley Section:", font=("Helvetica", 12)).grid(
            row=3, column=0, sticky='e', padx=(0, 5), pady=5
        )
        galley_var = tk.StringVar(value=galley)
        galley_combo = ttk.Combobox(
            main_frame, textvariable=galley_var,
            values=[s.upper() for s in GALLEY_SECTIONS], state="readonly", width=18
        )
        galley_combo.grid(row=3, column=1, sticky='w', pady=5)

        stand_var = tk.BooleanVar(value=(stand.upper() == "YES"))
        stand_chk = ttk.Checkbutton(
            main_frame, text="Standing Order", variable=stand_var
        )
        stand_chk.grid(row=3, column=2, sticky='e', pady=5, padx=(10, 5))

        # ------------------------------------------------------------
        # Row 4: Allergies (across columns 0..1), Entry (across columns 2..3)
        # ------------------------------------------------------------
        ttk.Label(main_frame, text="Allergies:", font=("Helvetica", 12)).grid(
            row=4, column=0, sticky='e', padx=(0, 5), pady=5
        )
        allergy_var = tk.StringVar(value=allergy)
        allergy_entry = ttk.Entry(main_frame, textvariable=allergy_var, width=47)
        allergy_entry.grid(row=4, column=1, columnspan=3, sticky='w', pady=5)

        # ------------------------------------------------------------
        # Row 5: Save button (span all columns)
        # ------------------------------------------------------------
        def save_edits():
            new_cabin = cabin_var.get().strip().upper()
            new_guest = guest_var.get().strip()
            new_dish = dish_var.get().strip().upper()
            new_pax = pax_var.get().strip()
            new_req = req_var.get().strip().upper()
            new_time = timeslot_var.get().strip().upper()
            new_galley = galley_var.get().strip().upper()
            new_stand = "YES" if stand_var.get() else "NO"
            new_allergy = allergy_var.get().strip().upper()

            # Minimal validation
            if not new_cabin:
                messagebox.showwarning("Validation Error", "Cabin number cannot be empty.")
                popup.focus_set()
                return
            if not new_dish:
                messagebox.showwarning("Validation Error", "Dish cannot be empty.")
                popup.focus_set()
                return
            if not new_pax.isdigit() or int(new_pax) < 1:
                messagebox.showwarning("Validation Error", "Pax must be a positive integer.")
                popup.focus_set()
                return
            if not new_time:
                messagebox.showwarning("Validation Error", "Time slot is required.")
                popup.focus_set()
                return
            if not new_galley:
                messagebox.showwarning("Validation Error", "Galley section is required.")
                popup.focus_set()
                return

            # Rebuild the edited tuple
            manager_original = order[0]  # Manager remains unchanged
            from_db_flag = order[10]

            new_order = (
                manager_original,  # 0
                new_cabin,  # 1
                new_guest,  # 2
                new_dish,  # 3
                new_pax,  # 4
                new_allergy,  # 5
                new_req,  # 6
                new_time,  # 7
                new_galley,  # 8
                new_stand,  # 9
                from_db_flag  # 10
            )

            # If this order was originally loaded from DB, push changes back to the DB
            if from_db_flag:
                old_manager = order[0]
                old_cabin = order[1]
                old_guest = order[2]
                old_dish = order[3]
                old_pax = order[4]
                old_allergy = order[5]
                old_req = order[6]
                old_time = order[7]
                old_galley = order[8]
                old_stand = order[9]

                # Your existing service_date logic, e.g.:
                service_date_str = self.service_date_var.get().strip() or get_next_day_date()

                success = self.db_manager.update_preorder(
                    old_manager=old_manager,
                    old_cabin=old_cabin,
                    old_guest=old_guest,
                    old_dish=old_dish,
                    old_pax=old_pax,
                    old_allergy=old_allergy,
                    old_requests=old_req,
                    old_timeslot=old_time,
                    old_galley=old_galley,
                    old_standing=old_stand,
                    venue_id=self.venue_id,
                    service_date=service_date_str,
                    new_cabin=new_cabin,
                    new_guest=new_guest,
                    new_dish=new_dish,
                    new_pax=new_pax,
                    new_allergy=new_allergy,
                    new_requests=new_req,
                    new_timeslot=new_time,
                    new_galley=new_galley,
                    new_standing=new_stand
                )
                if not success:
                    messagebox.showerror("Update Error", "Failed to update preorder in DB.")
                    return

            # Update self.all_orders (in-memory list)
            self.all_orders[idx] = new_order

            # Update the Treeview item
            old_values = order[:10]
            new_values = new_order[:10]
            for it in self.tree.get_children():
                vals = self.tree.item(it, "values")
                if vals == old_values:
                    self.tree.item(it, values=new_values)
                    break

            self.unsaved_data = True
            popup.destroy()

        ttk.Button(main_frame, text="Save", command=save_edits, bootstyle=SUCCESS).grid(
            row=5, column=0, columnspan=4, pady=10
        )

    def on_remove_order(self, event=None):
        """
        Remove the selected order from the tree (and from self.all_orders).
        If from_db=True, ask for manager password before removing from DB.
        """
        selected = self.tree.selection()
        if not selected:
            return

        item_id = selected[0]
        # Treeview has 10 columns => manager..standing_order
        vals = self.tree.item(item_id, "values")

        # Find the matching order in self.all_orders
        # Each self.all_orders item is an 11-field tuple (index 10 is from_db).
        matching_index = None
        for i, order_tuple in enumerate(self.all_orders):
            # Compare the first 10 fields (manager..standing_order) to the Treeview's values
            if order_tuple[:10] == vals:
                matching_index = i
                break

        if matching_index is None:
            messagebox.showerror("Error", "Order not found in memory.")
            return

        order = self.all_orders[matching_index]
        # order = (manager, cabin, guest, dish, pax, allergy, requests, timeslot, galley, stand, from_db)
        manager_for_order = order[0]
        cabin_number_for_order = order[1]
        guest_name_for_order = order[2]
        dish_for_order = order[3]
        pax_for_order = order[4]
        allergy_for_order = order[5]
        requests_for_order = order[6]
        timeslot_for_order = order[7]
        galley_for_order = order[8]
        standing_for_order = order[9]
        from_db_flag = order[10]

        if from_db_flag:
            # Ask manager password
            pw = simpledialog.askstring(
                "Manager Password",
                f"Order belongs to '{manager_for_order}' in DB.\nEnter manager password to remove:",
                show='*'
            )
            if not pw:
                return
            # Verify password
            if not self.db_manager.verify_user(manager_for_order, pw):
                messagebox.showerror("Access Denied", "Incorrect password.")
                return

            # If password OK => remove from DB
            service_date = self._selected_or_next_service_date()
            success = self.db_manager.delete_preorder(
                manager_for_order,
                cabin_number_for_order,
                guest_name_for_order,  # NEW => pass the guest name
                dish_for_order,
                pax_for_order,
                allergy_for_order,
                requests_for_order,
                timeslot_for_order,
                galley_for_order,
                standing_for_order,
                self.venue_id,
                service_date
            )
            if not success:
                messagebox.showerror("Error", "DB remove failed or no matching record.")
                return
            else:
                logging.info(
                    f"Order from DB removed for Cabin '{cabin_number_for_order}', "
                    f"Guest '{guest_name_for_order}' by Manager '{manager_for_order}'."
                )



        # Remove from memory
        del self.all_orders[matching_index]

        # Remove from tree
        self.tree.delete(item_id)

        self.unsaved_data = True
        self.show_toast(

            f"Order for Cabin '{cabin_number_for_order}', Guest '{guest_name_for_order}' removed.", toast_type="info"
        )
        self.validate_buttons()


    def sort_column(self, col, reverse):
        """
        Sorts the Treeview rows by the specified column 'col'.
        'reverse' toggles ascending/descending.
        """
        # Gather all rows from the Treeview
        data_list = []
        for item_id in self.tree.get_children(''):
            cell_value = self.tree.set(item_id, col)

            # Optional numeric sort if col == 'Pax'
            if col == "Pax":
                try:
                    cell_value = int(cell_value)
                except ValueError:
                    pass  # fallback to string compare if not an integer

            data_list.append((cell_value, item_id))

        # Sort data_list
        data_list.sort(key=lambda x: x[0], reverse=reverse)

        # Reorder Treeview items
        for idx, (val, item_id) in enumerate(data_list):
            self.tree.move(item_id, '', idx)

        # Update the heading so next click toggles the sort
        self.tree.heading(col,
                          command=lambda: self.sort_column(col, not reverse)
                          )

    # ---------------------------- ON DOUBLE-CLICK ----------------------------
    def on_double_click(self, event):
        row_id = self.tree.focus()
        if not row_id:
            return
        vals = self.tree.item(row_id, 'values')
        if not vals:
            return
        self.show_order_details(vals)


    def show_order_details(self, vals):
        fields = ["Manager", "Cabin", "Guest Name", "Dish", "Pax", "Allergies",
                  "Requests", "Time Slot", "Galley Section", "Standing Order"]

        pop = tk.Toplevel(self)
        pop.title(f"Order Details - Cabin {vals[1]}")
        pop.geometry("600x400")
        pop.resizable(True, True)
        try:
            pop.iconbitmap('icons/icon_app.ico')
        except Exception:
            pass

        # ------------------- HEADER -------------------
        # A header frame with a dark background and white text.
        header_frame = tk.Frame(pop, bg="#2c3e50", padx=10, pady=10)
        header_frame.pack(fill="x")
        header_label = tk.Label(header_frame,
                                text=f"Order Details for Cabin {vals[1]}",
                                bg="#2c3e50", fg="white",
                                font=("Helvetica", 18, "bold"))
        header_label.pack()

        # ------------------- CONTENT (SCROLLABLE) -------------------
        content_frame = tk.Frame(pop, bg="white")
        content_frame.pack(fill="both", expand=True, padx=10, pady=10)

        canvas = tk.Canvas(content_frame, bg="white", highlightthickness=0)
        canvas.pack(side="left", fill="both", expand=True)

        vsb = ttk.Scrollbar(content_frame, orient="vertical", command=canvas.yview)
        vsb.pack(side="right", fill="y")
        canvas.configure(yscrollcommand=vsb.set)

        # Create an inner frame to hold the order fields
        inner_frame = tk.Frame(canvas, bg="white")
        inner_window = canvas.create_window((0, 0), window=inner_frame, anchor="nw")

        def on_inner_configure(event):
            canvas.configure(scrollregion=canvas.bbox("all"))

        inner_frame.bind("<Configure>", on_inner_configure)

        # Optional: bind canvas width to inner_frame width
        def on_canvas_configure(event):
            canvas.itemconfig(inner_window, width=event.width)

        canvas.bind("<Configure>", on_canvas_configure)

        # ------------------- FIELD DETAILS -------------------
        # Define styles for headers and values.
        header_font = ("Helvetica", 12, "bold")
        value_font = ("Helvetica", 12)
        header_fg = "#34495e"
        value_fg = "#2c3e50"

        txtacc = ""
        # Use a fixed width for field name labels (e.g., 15 characters)
        for i, (field, value) in enumerate(zip(fields, vals)):
            lbl = tk.Label(inner_frame, text=f"{field}:", font=header_font,
                           fg=header_fg, bg="white", anchor="e", width=15)
            lbl.grid(row=i, column=0, sticky="e", padx=(5, 10), pady=4)
            val_lbl = tk.Label(inner_frame, text=str(value), font=value_font,
                               fg=value_fg, bg="white", anchor="w",
                               wraplength=350, justify="left")
            val_lbl.grid(row=i, column=1, sticky="w", padx=5, pady=4)
            txtacc += f"{field}: {value}\n"

        # ------------------- BUTTON FRAME -------------------
        btn_frame = tk.Frame(pop, bg="white", pady=10)
        btn_frame.pack(fill="x", padx=10)
        close_btn = ttk.Button(btn_frame, text="Close", command=pop.destroy)
        close_btn.pack(side="left", padx=10)
        copy_btn = ttk.Button(btn_frame, text="Copy to Clipboard",
                              command=lambda: self.copy_order_to_clipboard(txtacc))
        copy_btn.pack(side="right", padx=10)

    def copy_order_to_clipboard(self, text):
        self.clipboard_clear()
        self.clipboard_append(text)
        self.show_toast( "Order details copied to clipboard.", toast_type="info")



    # ---------------------------- LOGOUT ----------------------------
    def logout(self):
        self.manager = None
        self.venue_id = None
        self.venue_name = None
        self.allergies.clear()
        self.all_orders.clear()
        self.unsaved_data = False
        logging.info("Manager logged out.")
        self.show_login_and_venue_screen()

    # ---------------------------- SHOW TODAY'S ORDERS ----------------------------
    import sqlite3

    def finalize_sqlite(db_path):
        with sqlite3.connect(db_path) as conn:
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")

    # inside your App class (RestaurantApp/AdminApp)
    def on_close(self):
        try:
            if getattr(self.db_manager, "backend", "") == "sqlite":
                db_path = getattr(self.db_manager, "db_path", None)
                if db_path:
                    finalize_sqlite(db_path)
        except Exception as e:
            print("Failed to finalize SQLite:", e)
        finally:
            # make sure Tkinter really closes
            self.destroy()
    def show_todays_orders(self):
        import os, subprocess, platform, getpass
        from datetime import datetime, timedelta
        import tkinter as tk
        from tkinter import ttk, messagebox, filedialog
        from PIL import Image, ImageTk
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
        from reportlab.lib.pagesizes import landscape, letter
        from reportlab.lib import colors
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.enums import TA_CENTER

        # ─── Preview window ─────────────────────────────────────
        preview = tk.Toplevel(self)
        preview.title("Today's Orders Preview")
        preview.geometry("1100x600")
        preview.resizable(True, True)
        preview.iconbitmap(os.path.join("icons", "icon_app.ico"))

        preview._remark_map = {}
        preview._tooltip = None
        preview._prev_iid = None

        # ─── Preload venues/managers for filters ────────────────
        venues = self.db_manager.get_venues()  # list of dicts {id,name}
        venue_names = ["All Venues"] + [v["name"] for v in venues]
        # Build a stable map once; store on preview and keep a local ref too
        preview.venue_map = {v["name"]: v["id"] for v in venues}
        venue_map = preview.venue_map

        managers_all = ["All Managers"] + self.db_manager.get_users_by_role("restaurant")

        # ─── Main Layout ────────────────────────────────
        main = ttk.Frame(preview, padding=12)
        main.pack(fill="both", expand=True)
        main.rowconfigure(1, weight=1)
        main.columnconfigure(0, weight=1)

        # ─── Filter & Search Section ─────────────────────
        ff = ttk.Labelframe(main, text="Filter and Search", padding=12, bootstyle="info")
        ff.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        for i in range(6):
            ff.columnconfigure(i, weight=1)

        # Venue Selector
        ttk.Label(ff, text="Venue:", font=("Helvetica", 11, "bold")).grid(row=0, column=0, sticky="e", padx=(0, 6))
        selected_venue_var = tk.StringVar(value=venue_names[0])
        venue_cb = ttk.Combobox(ff, textvariable=selected_venue_var, values=venue_names, state="readonly", width=25)
        venue_cb.grid(row=0, column=1, sticky="w", padx=(0, 15))

        # Manager Selector
        ttk.Label(ff, text="Manager:", font=("Helvetica", 11, "bold")).grid(row=0, column=2, sticky="e", padx=(0, 6))
        selected_manager_var = tk.StringVar(value=managers_all[0])
        manager_cb = ttk.Combobox(ff, textvariable=selected_manager_var, values=managers_all, state="readonly",
                                  width=25)
        manager_cb.grid(row=0, column=3, sticky="w", padx=(0, 15))

        # Search Entry
        ttk.Label(ff, text="Search:", font=("Helvetica", 11, "bold")).grid(row=0, column=4, sticky="e", padx=(0, 6))
        search_var = tk.StringVar()
        search_entry = ttk.Entry(ff, textvariable=search_var, width=30)
        search_entry.grid(row=0, column=5, sticky="ew")

        # Meal Type Filter (Radio buttons)
        meal_var = tk.StringVar(value="all")
        radio_frame = ttk.Frame(ff)
        radio_frame.grid(row=1, column=0, columnspan=6, sticky="w", pady=(10, 0))

        # ─── Orders Table ────────────────────────────────
        tf = ttk.Labelframe(main, text="Today's Orders", padding=12, bootstyle="primary")
        tf.grid(row=1, column=0, sticky="nsew")
        tf.rowconfigure(0, weight=1)
        tf.columnconfigure(0, weight=1)

        self.icon_confirmed = ImageTk.PhotoImage(Image.open(os.path.join("icons", "confirmed.png")).resize((24, 24)))
        self.icon_edited = ImageTk.PhotoImage(Image.open(os.path.join("icons", "edited.png")).resize((24, 24)))
        self.icon_vetoed = ImageTk.PhotoImage(Image.open(os.path.join("icons", "vetoed.png")).resize((24, 24)))

        cols = ("Manager", "Cabin", "Guest", "Dish", "Pax", "Allergy",
                "Requests", "Time Slot", "Galley Section", "Standing Order")
        tree = ttk.Treeview(tf, columns=cols, show="tree headings", selectmode="browse")
        tree.heading("#0", text="Status", anchor="center")
        tree.column("#0", width=36, anchor="center", stretch=False)
        for c in cols:
            tree.heading(c, text=c)
            tree.column(c, width=110, anchor="center")

        tree.grid(row=0, column=0, sticky="nsew")
        vsb = ttk.Scrollbar(tf, orient="vertical", command=tree.yview)
        vsb.grid(row=0, column=1, sticky="ns")
        tree.configure(yscrollcommand=vsb.set)

        hsb = ttk.Scrollbar(tf, orient="horizontal", command=tree.xview)
        hsb.grid(row=1, column=0, sticky="ew")
        tree.configure(xscrollcommand=hsb.set)

        tree.tag_configure("edited", background="#fff7d1")
        tree.tag_configure("vetoed", background="#ffd5d6")

        # ─── Data fetcher (RO connection; venue-aware) ───────────
        def get_orders_for_date(date_str, venue_id=None):
            # Use read-only connection (prevents sqlite locks; no writes here)
            with self.db_manager.get_ro_connection() as conn:
                cur = conn.cursor()
                p = self.db_manager._param()
                if venue_id:
                    cur.execute(f"""
                        SELECT manager, cabin_number, guest_name, dish, pax,
                               allergy_notes, special_requests, service_time_slot,
                               galley_section, standing_order, chef_flag, chef_remark
                          FROM preorders
                         WHERE service_date={p} AND venue_id={p}
                         ORDER BY service_time_slot, galley_section
                    """, (date_str, venue_id))
                else:
                    cur.execute(f"""
                        SELECT manager, cabin_number, guest_name, dish, pax,
                               allergy_notes, special_requests, service_time_slot,
                               galley_section, standing_order, chef_flag, chef_remark
                          FROM preorders
                         WHERE service_date={p}
                         ORDER BY venue_id, service_time_slot, galley_section
                    """, (date_str,))
                rows = cur.fetchall()
                cols_desc = [col[0] for col in cur.description]
                return [dict(zip(cols_desc, row)) for row in rows]

        # ─── Meal-period radios builder ───────────────────────────
        def rebuild_meal_radios(*_):
            for w in radio_frame.winfo_children():
                w.destroy()

            # default “All”
            choices = [("All", "all")]

            # Per-venue mapping if available; fallback to B/L/D
            vname = selected_venue_var.get()
            vid = venue_map.get(vname) if vname != "All Venues" else None
            if vid:
                mapping = self.db_manager.get_venue_meal_periods(vid) or {}
            else:
                mapping = {"breakfast": "Breakfast", "lunch": "Lunch", "dinner": "Dinner"}

            # mapping is {"breakfast":"Breakfast", ...}
            for key, label in mapping.items():
                if label:
                    choices.append((label, key))

            for i, (lbl, val) in enumerate(choices):
                ttk.Radiobutton(
                    radio_frame, text=lbl, variable=meal_var, value=val,
                    command=load_todays_orders
                ).grid(row=0, column=i, padx=(0, 10))

        # ─── Loader (applies all filters) ────────────────────────
        def load_todays_orders(*_):
            tree.delete(*tree.get_children())
            preview._remark_map.clear()

            # Compute "today" with cutoff
            now = self._now_local()
            cutoff_hour = self._get_cutoff_hour()
            if now.hour < cutoff_hour:
                today = (now.date() - timedelta(days=1)).strftime("%Y-%m-%d")
            else:
                today = now.date().strftime("%Y-%m-%d")

            # Venue filter at fetch-time
            vname = selected_venue_var.get()
            vid = venue_map.get(vname) if vname != "All Venues" else None
            rows = get_orders_for_date(today, vid)

            # Normalize once
            def norm(s):
                return (s or "").casefold()

            # Meal-period filter (string contains check, case-insensitive)
            period = norm(meal_var.get())
            if period and period not in ("all", "-", "any"):
                rows = [r for r in rows if period in norm(r.get("service_time_slot"))]

            # Manager filter (exact, case-insensitive)
            mgr_filter = selected_manager_var.get()
            if mgr_filter != "All Managers":
                mf = norm(mgr_filter)
                rows = [r for r in rows if norm(r.get("manager")) == mf]

            # Search filter (matches any of these fields)
            q = norm(search_var.get().strip())
            if q:
                keys = ("manager", "cabin_number", "guest_name", "dish", "allergy_notes", "special_requests")
                rows = [r for r in rows if any(q in norm(r.get(k)) for k in keys)]

            # Insert rows + collect remarks
            for r in rows:
                flag = (r.get("chef_flag") or "").upper()
                if flag == "DISREGARD":
                    icon, tag = self.icon_vetoed, "vetoed"
                elif flag == "EDITED":
                    icon, tag = self.icon_edited, "edited"
                else:
                    icon, tag = self.icon_confirmed, ""

                vals = (
                    r.get("manager"), r.get("cabin_number"), r.get("guest_name"), r.get("dish"),
                    r.get("pax"), r.get("allergy_notes"), r.get("special_requests"),
                    r.get("service_time_slot"), r.get("galley_section"), r.get("standing_order")
                )
                iid = tree.insert("", "end", image=icon, values=vals, tags=(tag,))
                remark = r.get("chef_remark") or ""
                # Only show a tooltip sentence if vetoed; keep generic text if you prefer
                if tag == "vetoed" and remark:
                    preview._remark_map[iid] = f"Reason for cancellation: {remark}"
                elif tag == "edited" and remark:
                    preview._remark_map[iid] = f"Chef edited: {remark}"

        # ─── Tooltip logic ─────────────────────────────────────
        def on_tree_motion(event):
            iid = tree.identify_row(event.y)
            if iid != preview._prev_iid:
                if preview._tooltip:
                    preview._tooltip.destroy()
                    preview._tooltip = None
                preview._prev_iid = iid
                if iid and tree.item(iid, "tags"):
                    remark = preview._remark_map.get(iid, "")
                    if remark:
                        preview._tooltip = tk.Toplevel(tree)
                        preview._tooltip.wm_overrideredirect(True)
                        lbl = ttk.Label(preview._tooltip, text=remark,
                                        background="#fffdd0", relief="solid",
                                        borderwidth=1, padding=(4, 2))
                        lbl.pack()
                        x = event.x_root + 20
                        y = event.y_root + 10
                        preview._tooltip.wm_geometry(f"+{x}+{y}")

        def on_tree_leave(event):
            if preview._tooltip:
                preview._tooltip.destroy()
                preview._tooltip = None
            preview._prev_iid = None

        tree.bind("<Motion>", on_tree_motion)
        tree.bind("<Leave>", on_tree_leave)
        manager_cb.bind("<<ComboboxSelected>>", lambda e: load_todays_orders())

        # ─── PDF Export (unchanged content logic; excluded vetoed) ───────────────
        def export_pdf():
            items_all = tree.get_children()
            if not items_all:
                messagebox.showinfo("No Data", "Nothing to export.")
                return

            # Exclude removed/vetoed rows from export
            items = [iid for iid in items_all if "vetoed" not in tree.item(iid, "tags")]
            if not items:
                messagebox.showinfo("No Data", "No non-cancelled orders to export.")
                return

            today_str = datetime.now().strftime("%Y-%m-%d")

            # Meal period line (only show if filtered)
            try:
                meal_period = (meal_var.get() or "").strip()
            except Exception:
                meal_period = ""
            show_meal = bool(meal_period) and meal_period.lower() not in ("all", "any", "-")

            vname_display = selected_venue_var.get()
            vname_file = vname_display.replace(" ", "_")
            default = f"{vname_file}_{today_str}.pdf"
            path = filedialog.asksaveasfilename(
                title="Save as PDF", initialfile=default,
                defaultextension=".pdf", filetypes=[("PDF files", "*.pdf")]
            )
            if not path:
                return

            # --- PDF doc + styles ---
            doc = SimpleDocTemplate(
                path, pagesize=landscape(letter),
                leftMargin=40, rightMargin=40, topMargin=80, bottomMargin=40
            )
            styles = getSampleStyleSheet()
            hdr = ParagraphStyle("Hdr", parent=styles["Title"], alignment=TA_CENTER)
            cell = ParagraphStyle("Cell", parent=styles["Normal"], fontName="Helvetica",
                                  fontSize=8, leading=9, alignment=TA_CENTER)

            venue_line = f"Venue: {vname_display}" + (f"   -|- Meal period: {meal_period.upper()}" if show_meal else "")
            elems = [Paragraph(f"Today's Orders — {today_str}", hdr),
                     Paragraph(venue_line, styles["Heading2"]),
                     Spacer(1, 12)]

            data = [["Manager", "Cabin", "Guest", "Dish", "Pax", "Allergy",
                     "Requests", "Time Slot", "Galley Section", "STD"]]
            for iid in items:
                vals = tree.item(iid, "values")
                data.append([Paragraph(str(v), cell) for v in vals])

            total_w = landscape(letter)[0] - 80
            col_ws = [total_w * 0.09, total_w * 0.07, total_w * 0.12,
                      total_w * 0.15, total_w * 0.05, total_w * 0.12,
                      total_w * 0.15, total_w * 0.09, total_w * 0.08,
                      total_w * 0.05]
            tbl = Table(data, colWidths=col_ws, repeatRows=1)
            tbl.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#343a40")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 10),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.whitesmoke, colors.lightgrey]),
                ("GRID", (0, 0), (-1, -1), 0.3, colors.grey),
            ]))
            elems.append(tbl)

            def _footer(c, d):
                c.saveState()
                text = f"Printed by {getpass.getuser()} on {datetime.now():%Y-%m-%d %H:%M}"
                c.setFont("Helvetica-Oblique", 7)
                c.drawString(40, 28, text)
                c.restoreState()

            doc.build(elems, onFirstPage=_footer, onLaterPages=_footer)
            messagebox.showinfo("Exported", f"PDF saved to:\n{path}")
            if messagebox.askyesno("Open PDF?", "Open now?"):
                if platform.system() == "Windows":
                    os.startfile(path)
                elif platform.system() == "Darwin":
                    subprocess.run(["open", path], check=True)
                else:
                    subprocess.run(["xdg-open", path], check=True)

        # ─── Bindings & Initial Load ──────────────────────────
        venue_cb.bind("<<ComboboxSelected>>", lambda e: (rebuild_meal_radios(), load_todays_orders()))
        manager_cb.bind("<<ComboboxSelected>>", lambda e: load_todays_orders())
        search_var.trace_add("write", lambda *a: load_todays_orders())

        rebuild_meal_radios()
        load_todays_orders()

        preview.lift()
        preview.focus()

        # ─── Row detail window ─────────────────────────────────
        def on_double_click(event):
            item = tree.identify_row(event.y)
            if not item:
                return
            values = tree.item(item, "values")
            tags = tree.item(item, "tags")
            remark = preview._remark_map.get(item, "")
            cols_full = ("Manager", "Cabin", "Guest", "Dish", "Pax", "Allergy",
                         "Requests", "Time Slot", "Galley Section", "Standing Order")

            detail_win = tk.Toplevel(preview)
            detail_win.title("Order Details")
            detail_win.geometry("620x600")
            detail_win.resizable(False, False)
            detail_win.iconbitmap(os.path.join("icons", "icon_app.ico"))

            outer = ttk.Frame(detail_win, padding=20)
            outer.pack(fill="both", expand=True)

            ttk.Label(outer, text="ORDER DETAILS", font=("Segoe UI", 14, "bold")).pack(pady=(0, 12))

            info_frame = ttk.LabelFrame(outer, text="General Info", padding=12)
            info_frame.pack(fill="both", expand=True)

            for i, (label, val) in enumerate(zip(cols_full, values)):
                font_val = ("Segoe UI", 10, "bold") if label in ("Cabin", "Guest", "Dish") else ("Segoe UI", 10)
                wrap = 50 if label in ("Allergy", "Requests") else 0
                anchor = "w" if wrap else "center"
                ttk.Label(info_frame, text=label + ":", font=("Segoe UI", 10, "bold")) \
                    .grid(row=i, column=0, sticky="e", padx=(0, 10), pady=6)
                content = ttk.Label(info_frame, text=val or "-", font=font_val, anchor=anchor,
                                    wraplength=wrap * 8 if wrap else 0, justify="left")
                content.grid(row=i, column=1, sticky="w" if wrap else "n", pady=6)

            # Show remark only if flagged and present
            if ("vetoed" in tags or "edited" in tags) and remark:
                remark_frame = ttk.LabelFrame(outer, text="Chef Remark", padding=12, bootstyle="warning")
                remark_frame.pack(fill="x", expand=False, pady=(12, 0))
                ttk.Label(remark_frame, text=remark, font=("Segoe UI", 10), wraplength=520, justify="left").pack(
                    anchor="w")

            ttk.Button(outer, text="Close", command=detail_win.destroy, bootstyle="danger").pack(pady=(15, 0))

        tree.bind("<Double-1>", on_double_click)

    # ---------------------------- ON CLOSE ----------------------------
    def on_closing(self):
        if self.unsaved_data:
            ans = messagebox.askyesnocancel("Unsaved Data", "You have unsaved orders. Save before exiting?")
            if ans is True:
                self.commit_to_db()
                self.destroy()
            elif ans is False:
                self.destroy()
            else:
                return
        else:
            self.destroy()


# ----------------------------
# Utility
# ----------------------------
from datetime import datetime, timedelta, time

def get_next_day_date(self):
    now = self._now_local()
    if now.hour < self._get_cutoff_hour():
        target_date = now.date()
    else:
        target_date = now.date() + timedelta(days=1)
    return target_date.strftime("%Y-%m-%d")



# ----------------------------
# init_db
# ----------------------------
def init_db():
    db_path = get_database_path()
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        # users table
        cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('admin', 'restaurant', 'galley'))
        );
        """)
        # venues
        cur.execute("""
        CREATE TABLE IF NOT EXISTS venues (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL
        );
        """)
        # allergies
        cur.execute("""
        CREATE TABLE IF NOT EXISTS allergies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL
        );
        """)
        # preorders
        cur.execute("""
        CREATE TABLE IF NOT EXISTS preorders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cabin_number TEXT,
            dish TEXT,
            pax INTEGER,
            allergy_notes TEXT,
            special_requests TEXT,
            service_time_slot TEXT NOT NULL,
            galley_section TEXT,
            standing_order TEXT,
            venue_id INTEGER NOT NULL,
            service_date TEXT NOT NULL,
            manager TEXT,
            FOREIGN KEY (venue_id) REFERENCES venues(id) ON DELETE CASCADE
        );
        """)
        # app_config
        cur.execute("""
        CREATE TABLE IF NOT EXISTS app_config (
            key TEXT PRIMARY KEY,
            value TEXT
        );
        """)






        cur.execute("SELECT COUNT(*) FROM allergies")
        if cur.fetchone()[0] == 0:
            base_allergies = ["PEANUTS", "GLUTEN", "SHELLFISH", "SOY", "DAIRY", "EGG", "TREE NUTS"]
            for al in base_allergies:
                cur.execute("INSERT INTO allergies (name) VALUES (?)", (al,))
            logging.info("Inserted sample allergies.")

        cur.execute("SELECT COUNT(*) FROM preorders")

        conn.commit()
        logging.info("DB init done.")
    except sqlite3.Error as e:
        logging.error(f"Error init DB: {e}")
    finally:
        conn.close()

# ----------------------------
# main
# ----------------------------
def main():
    init_db()
    app = RestaurantApp()
    app.mainloop()

if __name__ == "__main__":
    main()
