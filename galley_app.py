

import sys
import ctypes
from ctypes import wintypes

# ------------------------------------------------------------------
# SINGLE‑INSTANCE VIA WIN32 NAMED MUTEX
# ------------------------------------------------------------------
mutex_name = "Global\\MyGalleyAppMutex"   # pick a truly unique name
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



from datetime import datetime, date, timedelta, timezone
from zoneinfo import ZoneInfo
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from ttkbootstrap import Style, ttk
from ttkbootstrap.constants import *

# ----------------------------
# Logging Configuration
# ----------------------------



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
import json
from pathlib import Path

def load_db_config(config_file="db_config.json"):
    import json, sys
    from pathlib import Path
    try:
        base = Path(sys.executable).parent if getattr(sys, 'frozen', False) \
               else Path(__file__).resolve().parent
        with open(base / config_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"type": "sqlite"}


# ----------------------------
# Database Manager Class
# ----------------------------
import sys
import sqlite3
import logging
import bcrypt  # if you need bcrypt elsewhere
from pathlib import Path

class DatabaseManager:
    def __init__(self, config):
        """
        config: dict from db_config.json, e.g.
          {"type":"sqlite"}
          or
          {"type":"mysql","host":"...","port":3306,"database":"...","user":"...","password":"..."}
        """
        self.config = config or {"type": "sqlite"}
        self.backend = self.config.get("type", "sqlite")

        if self.backend == "sqlite":
            # local file path
            if getattr(sys, 'frozen', False):
                app_dir = Path(sys.executable).parent
            else:
                app_dir = Path(__file__).resolve().parent
            self.db_path = str(app_dir / "orders.db")
        else:
            # MySQL settings, including dict cursor
            self.mysql_settings = {
                "host": self.config["host"],
                "port": int(self.config["port"]),
                "user": self.config["user"],
                "password": self.config["password"],
                "database": self.config["database"],
                "use_pure": True,
                "auth_plugin": "mysql_native_password",  # optional
            }

    def _param(self):
        return "?" if self.backend == "sqlite" else "%s"

    def get_connection(self):
        if self.backend == "sqlite":
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            return conn
        else:
            import mysql.connector
            conn = mysql.connector.connect(**self.mysql_settings)
            return conn

    def get_venues(self):
        sql = "SELECT id, name FROM venues ORDER BY name"
        conn = self.get_connection()
        if self.backend == "sqlite":
            cur = conn.cursor()
            cur.execute(sql)
            rows = cur.fetchall()
            conn.close()
            return [dict(row) for row in rows]
        else:
            cur = conn.cursor(dictionary=True)
            cur.execute(sql)
            rows = cur.fetchall()
            cur.close()
            conn.close()
            return rows

    def load_current_voyage_from_config(self):
        """
        Load current voyage_id from app_config and cache it on self.
        Returns the voyage_id string (e.g. 'SU542') or None if not set.
        """
        vid = self.get_config_values("current_voyage_id", "")
        self.current_voyage_id = (vid or "").strip() or None
        return self.current_voyage_id

    # Inside DatabaseManager (galley_app.py)

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

    # 🔧 Backward-compat shim (accepts 2 params like your call does)
    def get_config_values(self, key, default=None):
        return self.get_config_value(key, default)

    def update_order(self, order_id, dish, pax, section,
                     standing_order, special_requests,
                     chef_flag, chef_remark):
        if self.backend == "sqlite":
            sql = """
                UPDATE preorders
                SET dish = ?,
                    pax = ?,
                    galley_section = ?,
                    standing_order = ?,
                    special_requests = ?,
                    chef_flag = ?,
                    chef_remark = ?
                WHERE id = ?
            """
        else:
            sql = """
                UPDATE preorders
                SET dish = %s,
                    pax = %s,
                    galley_section = %s,
                    standing_order = %s,
                    special_requests = %s,
                    chef_flag = %s,
                    chef_remark = %s
                WHERE id = %s
            """

        params = (
            dish,
            int(pax),
            section,
            standing_order,
            special_requests,
            chef_flag,
            chef_remark,
            order_id
        )

        conn = self.get_connection()
        cur = conn.cursor()
        try:
            cur.execute(sql, params)
            conn.commit()
        except Exception as e:
            logging.error(f"Error updating order: {e}")
            raise
        finally:
            cur.close()
            conn.close()
    def get_user_by_username_and_role(self, username, role):
        p = self._param()
        sql = f"SELECT * FROM users WHERE username={p} AND role={p} LIMIT 1"
        conn = self.get_connection()

        try:
            if self.backend == "sqlite":
                # For SQLite, use standard cursor and convert to dict
                cur = conn.cursor()
                cur.execute(sql, (username, role))
                row = cur.fetchone()
                if row:
                    # Convert SQLite row to dictionary
                    return {description[0]: value for description, value in zip(cur.description, row)}
                return None
            else:
                # For MySQL, use dictionary cursor
                cur = conn.cursor(dictionary=True)
                cur.execute(sql, (username, role))
                return cur.fetchone()
        finally:
            cur.close()
            conn.close()

    def get_distinct_service_dates(self, venue_id=None):
        """Return service_dates for the *current voyage*."""
        try:
            vid = getattr(self, "current_voyage_id", None)
            if not vid:
                logging.warning("get_distinct_service_dates: no current_voyage_id")
                return []

            p = self._param()
            if venue_id not in (None, "", 0):
                sql = f"""
                    SELECT DISTINCT service_date
                    FROM preorders
                    WHERE voyage_id = {p} AND venue_id = {p}
                    ORDER BY service_date DESC
                """
                params = (vid, venue_id)
            else:
                sql = f"""
                    SELECT DISTINCT service_date
                    FROM preorders
                    WHERE voyage_id = {p}
                    ORDER BY service_date DESC
                """
                params = (vid,)

            with self.get_connection() as conn:
                cur = conn.cursor()
                cur.execute(sql, params)
                rows = cur.fetchall()
                return [r[0] if self.backend == "mysql" else r["service_date"] for r in rows]
        except Exception as e:
            logging.error(f"Error getting distinct service dates: {e}")
            return []

    def get_order_by_id(self, order_id: int):
        p = self._param()
        sql = f"SELECT * FROM preorders WHERE id={p} LIMIT 1"
        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute(sql, (order_id,))
            row = cur.fetchone()
            if not row:
                return None
            if self.backend == "mysql":
                # if not dict cursor, build dict from description
                cols = [d[0] for d in cur.description]
                return dict(zip(cols, row))
            # sqlite Row -> dict
            return dict(row)

    def get_service_dates(self):
        sql = "SELECT DISTINCT service_date FROM preorders ORDER BY service_date DESC"
        conn = self.get_connection()
        cur = conn.cursor()
        cur.execute(sql)
        dates = [row[0] for row in cur.fetchall()]
        cur.close()
        conn.close()
        return dates

    def get_order_by_fields(self, cabin, guest, dish, slot, section, standing):
        p = self._param()
        sql = f"""
            SELECT * FROM preorders
             WHERE cabin_number={p}
               AND guest_name={p}
               AND dish={p}
               AND service_time_slot={p}
               AND galley_section={p}
               AND standing_order={p}
               AND voyage_id={p}
             LIMIT 1
        """
        vid = getattr(self, "current_voyage_id", None)
        params = (cabin, guest, dish, slot, section, standing, vid)
        conn = self.get_connection()
        try:
            if self.backend == "sqlite":
                cur = conn.cursor();
                cur.execute(sql, params)
                row = cur.fetchone()
                if row:
                    col_names = [d[0] for d in cur.description]
                    return dict(zip(col_names, row))
                return None
            else:
                cur = conn.cursor(dictionary=True);
                cur.execute(sql, params)
                return cur.fetchone()
        finally:
            cur.close();
            conn.close()

    def flag_order(self, order_id, flag_type, remark):
        if self.backend == "sqlite":
            sql = "UPDATE preorders SET chef_flag=?, chef_remark=? WHERE id=?"
        else:
            sql = "UPDATE preorders SET chef_flag=%s, chef_remark=%s WHERE id=%s"

        conn = self.get_connection()
        cur = conn.cursor()
        try:
            cur.execute(sql, (flag_type, remark, order_id))
            conn.commit()
        except Exception as e:
            logging.error(f"Error flagging order: {e}")
            raise
        finally:
            cur.close()
            conn.close()

    # In galley_app.py, inside DatabaseManager
    def refresh_service_dates_for_current_voyage(self, init_only: bool = False):
        # If widget is gone, bail
        if not hasattr(self, "date_dropdown") or not self.date_dropdown.winfo_exists():
            return

        # Pull dates (current voyage + selected venue if any)
        dates = self.db_manager.get_distinct_service_dates(self.selected_venue_id)
        if not dates:
            dates = [self.get_today_date()]

        # Always work with strings to match StringVar
        dates = [str(d) for d in dates]

        # Remember previous selection (what the user *sees*), not only self.selected_date
        prev = str(self.date_var.get() or "")

        # Temporarily unbind to avoid spurious ComboboxSelected while we repopulate
        try:
            self.date_dropdown.unbind("<<ComboboxSelected>>")
        except Exception:
            pass

        try:
            # Update values without switching to "normal" (keeps it truly readonly)
            self.date_dropdown['values'] = dates

            if prev and prev in dates:
                # Keep what the user had, if still valid in the new venue
                self.selected_date = prev
                self.date_var.set(prev)
            else:
                # Only auto-select on the very first initialization
                if init_only or not getattr(self, "_date_initialized", False):
                    self.selected_date = dates[0]
                    self.date_var.set(self.selected_date)
                    self._date_initialized = True
                else:
                    # Don’t pick a new date for the user; leave empty so they choose
                    self.selected_date = ""
                    self.date_var.set("")
        finally:
            # Rebind after we finish repopulating
            self.date_dropdown.bind("<<ComboboxSelected>>", self.on_date_selected)
    def get_orders(self, *, venue_id, selected_date, time_slot=None, sections=None):
        vid = getattr(self, "current_voyage_id", None)
        if not vid:
            logging.warning("get_orders: current_voyage_id is not set; returning no rows.")
            return []

        p = self._param()
        params = [selected_date, vid]
        sql = f"""
            SELECT id, manager, cabin_number, guest_name, dish, pax, allergy_notes,
                   special_requests, service_time_slot, galley_section, standing_order,
                   chef_flag, chef_remark
              FROM preorders
             WHERE service_date = {p}
               AND voyage_id    = {p}
        """

        # only add venue filter when not "ALL"
        if venue_id not in (None, "", -1):
            sql += f" AND venue_id = {p}"
            params.append(venue_id)

        # only add time-slot filter when not ALL
        if time_slot and str(time_slot).strip().upper() != "ALL":
            sql += f" AND service_time_slot = {p}"
            params.append(time_slot)

        if sections:
            secs = [s for s in sections if str(s).strip()]
            if secs:
                sql += " AND galley_section IN (" + ",".join([p] * len(secs)) + ")"
                params.extend(secs)

        sql += " ORDER BY id DESC"

        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute(sql, tuple(params))
            rows = cur.fetchall()
            if self.backend == "mysql":
                keys = ["id", "manager", "cabin_number", "guest_name", "dish", "pax", "allergy_notes",
                        "special_requests", "service_time_slot", "galley_section", "standing_order",
                        "chef_flag", "chef_remark"]
                return [dict(zip(keys, r)) for r in rows]
            return [dict(r) for r in rows]


# Galley Application Class
# ----------------------------
class GalleyApp(tk.Tk):
    def __init__(self):
        super().__init__()
        cfg = load_db_config()
        self.db_manager = DatabaseManager(cfg)
        vid = self.db_manager.load_current_voyage_from_config()
        if not vid:
            logging.warning("No current_voyage_id set. Ask Admin to set Voyage.")

        # Use a ttkbootstrap style for a modern look
        self.style = Style(theme='flatly')  # try 'flatly', 'cosmo', 'superhero', etc.

        self.title("SpeSync Galley Suite")
        self.geometry("1300x800")
        self.resizable(True, True)
        self.iconbitmap('icons/icon_app.ico')

        self.service_tz, self.cutoff_hour = self._load_time_config()
        self.selected_venue_id = None
        self.selected_venue_name = ""
        self.selected_time_slot = "ALL"  # default
        self.selected_date = self.get_today_date()
        self.show_login_panel()
        self._tree_item_to_order_id = {}

    from zoneinfo import ZoneInfo
    from datetime import datetime, timedelta, timezone
    def _load_time_config(self):
        """
        Read time settings from app_config with safe fallbacks.
        Returns: (service_tz: Optional[str], cutoff_hour: int)
        """
        # Prefer new key; fall back to old ones
        tz = self.db_manager.get_config_value("server_time_zone", None)
        if not tz:
            tz = self.db_manager.get_config_value("SERVICE_TZ", None)  # legacy

        cutoff_raw = self.db_manager.get_config_value("cutoff_hour", None)
        try:
            cutoff = int(cutoff_raw) if (cutoff_raw is not None and str(cutoff_raw).strip().isdigit()) else 4
        except Exception:
            cutoff = 4  # hard default

        return tz, cutoff

    def _db_utc_now(self):
        """Authoritative UTC time from MySQL. None if SQLite or on error."""
        if getattr(self.db_manager, "backend", "").lower() != "mysql":
            return None
        try:
            with self.db_manager.get_connection() as conn:
                cur = conn.cursor()
                cur.execute("SELECT UTC_TIMESTAMP()")
                row = cur.fetchone()
            # tuple or dict
            val = row.get("UTC_TIMESTAMP()") if isinstance(row, dict) else row[0]
            if isinstance(val, datetime):
                return val.replace(tzinfo=timezone.utc) if val.tzinfo is None else val.astimezone(timezone.utc)
            return datetime.fromisoformat(str(val)).replace(tzinfo=timezone.utc)
        except Exception:
            return None

    def _now_local(self):
        """
        HYBRID 'now':
        - MySQL → DB UTC then convert to service_tz if set
        - SQLite → PC time (convert to service_tz if set, but service_tz is None in SQLite mode)
        """
        if getattr(self.db_manager, "backend", "").lower() == "mysql":
            db_utc = self._db_utc_now()
            if db_utc is not None:
                return db_utc.astimezone(ZoneInfo(self.service_tz)) if self.service_tz else db_utc.astimezone()
        # fallback: PC
        if self.service_tz:
            return datetime.now(timezone.utc).astimezone(ZoneInfo(self.service_tz))
        return datetime.now()

    def _service_date_for(self, dt: datetime, cutoff_hour: int) -> str:
        target = dt.date() if dt.hour < cutoff_hour else (dt.date() + timedelta(days=1))
        return target.strftime("%Y-%m-%d")

    def _cancel_server_time_timer(self):
        job = getattr(self, "_server_time_job", None)
        if job:
            try:
                self.after_cancel(job)
            except Exception:
                pass
        self._server_time_job = None

    def get_today_date(self):
        """Current service date via hybrid clock."""
        return self._service_date_for(self._now_local(), getattr(self, "cutoff_hour", 4))

    def show_login_panel(self):
        # Clear the window (remove any widgets)
        for widget in self.winfo_children():
            widget.destroy()

        # Create a centered frame for the login
        login_frame = ttk.Frame(self, padding=32)
        login_frame.place(relx=0.5, rely=0.4, anchor="center")

        ttk.Label(login_frame, text="Galley Chef Login", font=("Helvetica", 22, "bold")).grid(row=0, column=0,
                                                                                              columnspan=2,
                                                                                              pady=(0, 22))

        ttk.Label(login_frame, text="Username:", font=("Helvetica", 13)).grid(row=1, column=0, sticky='e', padx=(0, 8),
                                                                              pady=(0, 8))
        username_entry = ttk.Entry(login_frame, width=22, font=("Helvetica", 13))
        username_entry.grid(row=1, column=1, pady=(0, 8))
        username_entry.insert(0, "CHEF")
        username_entry.configure(state="readonly")

        ttk.Label(login_frame, text="Password:", font=("Helvetica", 13)).grid(row=2, column=0, sticky='e', padx=(0, 8),
                                                                              pady=(0, 8))
        password_var = tk.StringVar()
        password_entry = ttk.Entry(login_frame, show="*", textvariable=password_var, width=22, font=("Helvetica", 13))
        password_entry.grid(row=2, column=1, pady=(0, 8))

        error_lbl = ttk.Label(login_frame, text="", foreground="red", font=("Helvetica", 10, "bold"))
        error_lbl.grid(row=3, column=0, columnspan=2, pady=(8, 0))

        def attempt_login(event=None):
            entered_password = password_var.get()
            row = self.db_manager.get_user_by_username_and_role("CHEF", "galley")
            if not row:
                error_lbl.config(text="Chef account not found.")
                return
            import bcrypt
            stored_hash = row["password_hash"]
            if bcrypt.checkpw(entered_password.encode("utf-8"), stored_hash.encode("utf-8")):
                # Success! Remove login panel and show real app UI
                for widget in self.winfo_children():
                    widget.destroy()
                self.create_widgets()
            else:
                error_lbl.config(text="Incorrect password.")
                password_var.set("")
                password_entry.focus_set()

        password_entry.bind("<Return>", attempt_login)
        ttk.Button(login_frame, text="Login", command=attempt_login, width=20).grid(row=4, column=0, columnspan=2,
                                                                                    pady=(16, 0))

        password_entry.focus_set()

    def create_widgets(self):
        from PIL import Image, ImageTk
        self._cancel_server_time_timer()
        # --- Main Frame ---
        main_frame = ttk.Frame(self, padding=20)
        main_frame.pack(fill='both', expand=True)

        # --- HEADER LOGO (centered, fail-safe) ---
        self.safebite_logo_main = None
        logo_path = "icons/header_logo.png"
        try:
            logo_img = Image.open(logo_path)
            target_height = 140
            aspect = logo_img.width / logo_img.height if logo_img.height else 1
            logo_resized = logo_img.resize((int(target_height * aspect), target_height), Image.LANCZOS)
            self.safebite_logo_main = ImageTk.PhotoImage(logo_resized)
        except Exception as e:
            # Don't crash if icon missing; just skip image
            logging.warning(f"Header logo not loaded: {e}")
            self.safebite_logo_main = None

        if self.safebite_logo_main:
            logo_label = ttk.Label(main_frame, image=self.safebite_logo_main)
            logo_label.pack(anchor='center', pady=(0, 12))

        # --- Title ---
        title_label = ttk.Label(main_frame, text="Galley Order Viewer", font=("Helvetica", 24, "bold"))
        title_label.pack(anchor='center', pady=(0, 5))

        # --- Server Time (CENTERED under title) ---
        self.server_time_label = ttk.Label(main_frame, text="", font=("Helvetica", 10), foreground="#555")
        self.server_time_label.pack(anchor='center', pady=(0, 15))

        # --- Selection Frame (Filters) ---
        self.selection_frame = ttk.Labelframe(main_frame, text="Filters & Options", padding=20, bootstyle=PRIMARY)
        self.selection_frame.pack(fill='x', pady=(0, 20))

        # Venue
        lbl_venue = ttk.Label(self.selection_frame, text="Select Venue:", font=("Helvetica", 14))
        lbl_venue.grid(row=0, column=0, padx=5, pady=5, sticky='w')

        self.venue_var = tk.StringVar()
        self.venue_dropdown = ttk.Combobox(
            self.selection_frame, textvariable=self.venue_var, state="readonly", width=30, font=("Helvetica", 12)
        )
        self.venue_dropdown.grid(row=0, column=1, padx=(0, 20), pady=5, sticky='w')
        self.venue_dropdown.bind("<<ComboboxSelected>>", self.on_venue_selected)

        # Time Slot
        lbl_timeslot = ttk.Label(self.selection_frame, text="Select Time Slot:", font=("Helvetica", 14))
        lbl_timeslot.grid(row=0, column=2, padx=5, pady=5, sticky='w')

        self.time_slot_var = tk.StringVar()
        self.time_slot_dropdown = ttk.Combobox(
            self.selection_frame, textvariable=self.time_slot_var, state="readonly", width=20, font=("Helvetica", 12)
        )
        self.time_slot_dropdown['values'] = ["ALL", "BREAKFAST", "LUNCH", "DINNER"]
        self.time_slot_dropdown.current(0)
        self.time_slot_dropdown.grid(row=0, column=3, padx=(0, 20), pady=5, sticky='w')
        self.time_slot_dropdown.bind("<<ComboboxSelected>>", self.on_time_slot_selected)

        # Date
        lbl_date = ttk.Label(self.selection_frame, text="Select Date:", font=("Helvetica", 14))
        lbl_date.grid(row=0, column=4, padx=5, pady=5, sticky='w')

        self.date_var = tk.StringVar()
        self.date_dropdown = ttk.Combobox(
            self.selection_frame, textvariable=self.date_var, state="readonly", width=20, font=("Helvetica", 12)
        )
        self.date_dropdown.grid(row=0, column=5, padx=(0, 20), pady=5, sticky='w')
        self.date_dropdown.bind("<<ComboboxSelected>>", self.on_date_selected)

        # Sections
        self.section_mapping = {"Hot Section": "HOT", "Cold Section": "COLD", "Dessert": "PASTRY"}
        self.sections = ["Hot Section", "Cold Section", "Dessert", "All"]
        self.section_vars = {s: tk.BooleanVar(value=False) for s in self.sections}

        for i, s in enumerate(self.sections):
            cb = ttk.Checkbutton(
                self.selection_frame, text=s, variable=self.section_vars[s],
                command=self.on_filter_change, bootstyle=INFO
            )
            cb.grid(row=1, column=i, padx=3, pady=3, sticky='w')

        # Export
        self.export_button = ttk.Button(
            self.selection_frame, text="Export to PDF", command=self.export_to_pdf, bootstyle=SUCCESS
        )
        self.export_button.grid(row=1, column=len(self.sections), padx=20, pady=5, sticky='e')

        # --- Orders Frame ---
        self.sheet_frame = ttk.Labelframe(main_frame, text="Orders", padding=10, bootstyle=PRIMARY)
        self.sheet_frame.pack(fill='both', expand=True)
        self.sheet_frame.rowconfigure(0, weight=1)
        self.sheet_frame.columnconfigure(0, weight=1)

        # Style
        try:
            style = Style()
            style.configure('Treeview', rowheight=28)
            style.configure('Treeview.Heading', font=('Helvetica', 12, 'bold'))
        except Exception as e:
            logging.debug(f"Style configuration skipped: {e}")

        columns = ["manager", "cabin", "guest", "dish", "pax", "allergy", "reqs", "time", "section", "standing"]
        self.tree = ttk.Treeview(self.sheet_frame, columns=columns, show="headings", selectmode="browse")
        for col in columns:
            self.tree.heading(col, text=col.upper())
            self.tree.column(col, width=120, anchor="center")

        self.tree.grid(row=0, column=0, sticky='nsew')
        vs = ttk.Scrollbar(self.sheet_frame, orient='vertical', command=self.tree.yview)
        vs.grid(row=0, column=1, sticky='ns')
        self.tree.configure(yscrollcommand=vs.set)
        hs = ttk.Scrollbar(self.sheet_frame, orient='horizontal', command=self.tree.xview)
        hs.grid(row=1, column=0, sticky='ew')
        self.tree.configure(xscrollcommand=hs.set)

        self.tree_menu = tk.Menu(self, tearoff=0)
        self.tree_menu.add_command(label="Edit/Disregard Order", command=self.popup_flag_order)

        def on_tree_right_click(event):
            row_id = self.tree.identify_row(event.y)
            if row_id:
                self.tree.selection_set(row_id)
                self.tree_menu.tk_popup(event.x_root, event.y_root)

        self.tree.bind("<Button-3>", on_tree_right_click)
        self.tree.bind("<Double-1>", self.on_order_double_click)
        self.tree.tag_configure("flagged", background="#ffe2b0")
        self.tree.tag_configure("disregard", background="#ffb1b1")

        # --- Load data & start time updates ---
        # IMPORTANT: Load venues (this sets map+default and calls on_venue_selected in your flow)




        ok = self.load_venues()
        if ok and hasattr(self, "refresh_service_dates_for_current_voyage"):
            # Only schedule the date refresh if venues exist and widget is alive
            self.after_idle(lambda: (
                    hasattr(self, "date_dropdown")
                    and self.date_dropdown.winfo_exists()
                    and self.refresh_service_dates_for_current_voyage()
            ))

        # Start server time updates (schedule once; updater guards itself)
        self.after_idle(self._update_server_time_label)

        # If there were no venues, avoid scheduling more UI work that depends on them
        if not ok:
            logging.warning("No venues available; controls disabled. Waiting for admin to add venues.")
            return
    def _update_server_time_label(self):
        # If label no longer exists, stop rescheduling
        if not hasattr(self,
                       "server_time_label") or not self.server_time_label or not self.server_time_label.winfo_exists():
            self._cancel_server_time_timer()
            return

        # Build the text (use DB server time if available, otherwise local)
        try:
            # If you have a DB-side time function, wrap it here; else fallback to local
            ts = None
            try:
                if hasattr(self, "db_manager") and self.db_manager:
                    ts = self.db_manager.get_server_time()  # should return a datetime or string; OK if raises
            except Exception:
                ts = None

            if ts:
                try:
                    # if it's a datetime
                    text = f"Server time: {ts:%Y-%m-%d %H:%M:%S}"
                except Exception:
                    # if it's already a string
                    text = f"Server time: {ts}"
            else:
                import datetime as _dt
                text = f"Local time: {_dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"

            # Update the label only if still alive
            if self.server_time_label.winfo_exists():
                self.server_time_label.config(text=text)
        except tk.TclError:
            # Widget died between checks; stop
            self._cancel_server_time_timer()
            return

        # Reschedule safely
        self._server_time_job = self.after(1000, self._update_server_time_label)

    def load_venues(self) -> bool:
        """
        Populate self.venue_dropdown and self.venue_map.
        Returns True if venues were loaded, False if none found.
        """
        try:
            rows = self.db_manager.get_venues()  # or your existing fetch fn
            # rows expected like [(id, name), ...] or [{"id":..,"name":..}, ...]
        except Exception as e:
            logging.error(f"Failed to load venues: {e}")
            rows = []

        if not rows:
            # No venues: don't destroy the app here. Just inform & disable inputs.
            from tkinter import messagebox
            messagebox.showwarning("No Venues", "No venues in DB. Please contact administrator.")

            self.venue_map = {"ALL": None}
            try:
                self.venue_dropdown.configure(state="disabled")
                self.time_slot_dropdown.configure(state="disabled")
                self.date_dropdown.configure(state="disabled")
                self.export_button.configure(state="disabled")
            except Exception:
                pass

            # Still set a minimal value list so combobox is well-formed
            try:
                self.venue_dropdown['values'] = ["ALL"]
                self.venue_var.set("ALL")
            except Exception:
                pass

            return False

        # Normalize to tuples (id, name)
        normalized = []
        first_id = None
        for r in rows:
            if isinstance(r, dict):
                vid, vname = r.get("id"), r.get("name")
            else:
                # (id, name) or (name, id); adapt if needed
                vid, vname = r[0], r[1]
            normalized.append((vid, vname))
            if first_id is None:
                first_id = vid

        # Build map and populate dropdown
        self.venue_map = {"ALL": None}
        for vid, vname in normalized:
            self.venue_map[vname] = vid

        names = ["ALL"] + [vname for _, vname in normalized]
        self.venue_dropdown['values'] = names
        # default to ALL
        self.venue_dropdown.current(0)
        self.venue_var.set("ALL")

        # Trigger initial load once (safe)
        try:
            self.on_venue_selected()  # this should NOT destroy the window
        except Exception as e:
            logging.error(f"on_venue_selected failed: {e}")

        return True

    def load_orders(self):
        # Fetch data
        sc = self.get_selected_sections()
        data = self.db_manager.get_orders(
            venue_id=self.selected_venue_id,
            selected_date=self.selected_date,
            time_slot=self.selected_time_slot,
            sections=sc
        )

        # Clear previous rows & id map
        self._tree_item_to_order_id.clear()
        for row in self.tree.get_children():
            self.tree.delete(row)

        # Insert new rows, tagging flagged/disregard
        for row in data:
            order_tuple = (
                row.get("manager", ""),
                row.get("cabin_number", ""),
                row.get("guest_name", ""),
                row.get("dish", ""),
                str(row.get("pax", "")),
                row.get("allergy_notes", ""),
                row.get("special_requests", ""),
                row.get("service_time_slot", ""),
                row.get("galley_section", ""),
                row.get("standing_order", "")
            )
            tag = ""
            if (row.get("chef_flag") or "").upper() == "DISREGARD":
                tag = "disregard"
            elif row.get("chef_flag"):
                tag = "flagged"

            iid = self.tree.insert("", "end", values=order_tuple, tags=(tag,))
            # Keep the DB id so popup_flag_order can resolve correctly
            self._tree_item_to_order_id[iid] = row["id"]

        logging.info(
            f"Loaded {len(data)} orders for venue '{self.selected_venue_name}' "
            f"on date '{self.selected_date}' with timeslot '{self.selected_time_slot}' "
            f"and sections {sc if sc else 'All'}."
        )

    def load_service_dates(self):
        """Populate date dropdown with DISTINCT dates for the *current voyage* (and selected venue)."""
        dates = self.db_manager.get_distinct_service_dates(self.selected_venue_id)
        if not dates:
            # fall back to today's service date
            dates = [self.get_today_date()]

        self.date_dropdown['values'] = dates
        # keep current selection if still valid; else choose newest
        cur = getattr(self, "selected_date", None)
        self.selected_date = cur if cur in dates else dates[0]
        self.date_var.set(self.selected_date)

    def on_venue_selected(self, event=None):
        sel = self.venue_var.get()
        self.selected_venue_id = self.venue_map.get(sel, None)
        self.selected_venue_name = sel

        # Refresh the dates first (non-destructive)
        self.refresh_service_dates_for_current_voyage()

        # Only load if a date is chosen
        if getattr(self, "selected_date", ""):
            self.load_orders()

    def refresh_service_dates_for_current_voyage(self):
        if not hasattr(self, "date_dropdown") or not self.date_dropdown.winfo_exists():
            return

        dates = self.db_manager.get_distinct_service_dates(self.selected_venue_id)
        if not dates:
            dates = [self.get_today_date()]

        # Convert dates to strings for consistency
        dates = [str(d) for d in dates]

        try:
            old_state = self.date_dropdown.cget("state")
            self.date_dropdown.configure(state="normal")
            self.date_dropdown['values'] = dates

            current_date = getattr(self, "selected_date", None)

            # Always try to maintain the current date if it exists in the new list
            if current_date and current_date in dates:
                self.selected_date = current_date
                self.date_var.set(self.selected_date)
            elif dates:  # If current date not available, select the first date
                self.selected_date = dates[0]
                self.date_var.set(self.selected_date)
            else:  # Fallback to today if no dates available
                self.selected_date = self.get_today_date()
                self.date_var.set(self.selected_date)

            self.date_dropdown.configure(state=old_state)
        except tk.TclError:
            # Widget might have been destroyed, try again later
            self.after_idle(self.refresh_service_dates_for_current_voyage)
    def popup_flag_order(self):
        selected = self.tree.selection()
        if not selected:
            return
        iid = selected[0]
        order_id = self._tree_item_to_order_id.get(iid)
        if not order_id:
            messagebox.showerror("Error", "Could not resolve the selected order ID.")
            return

        order = self.db_manager.get_order_by_id(order_id)
        if not order:
            messagebox.showerror("Error", "Order no longer exists.")
            return

        win = tk.Toplevel(self)
        win.title("Edit or Veto Order")
        win.geometry("470x580")
        win.resizable(False, False)
        win.transient(self)
        win.grab_set()

        # --- Styles & fonts ---
        label_font = ('Helvetica', 10, 'bold')
        entry_font = ('Helvetica', 11)

        # main container
        mainframe = ttk.Frame(win, padding=(18, 14, 18, 14))
        mainframe.pack(fill='both', expand=True)
        mainframe.grid_columnconfigure(0, weight=1)
        mainframe.grid_columnconfigure(1, weight=2)

        # --- Uneditable fields ---
        def add_ro(label, value, row):
            ttk.Label(mainframe, text=label, font=label_font, foreground="#5a6c85") \
                .grid(row=row, column=0, sticky="e", pady=2, padx=(0, 8))
            e = ttk.Entry(mainframe, width=30, font=entry_font)
            e.insert(0, value)
            e.grid(row=row, column=1, sticky="w", pady=2)
            e.configure(state="readonly")
            return e

        ro_fields = [
            ("Cabin", order['cabin_number']),
            ("Guest", order['guest_name']),
            ("Manager", order['manager']),
            ("Meal Period", order['service_time_slot']),
            ("Allergies", order['allergy_notes'] or "")
        ]
        rownum = 0
        ttk.Label(mainframe, text="Order Details", font=("Helvetica", 12, "bold")) \
            .grid(row=rownum, column=0, columnspan=2, pady=(0, 8))
        rownum += 1
        for lbl, val in ro_fields:
            add_ro(lbl, val, rownum)
            rownum += 1

        # --- Spacer ---
        sep1 = ttk.Separator(mainframe, orient="horizontal")
        sep1.grid(row=rownum, column=0, columnspan=2, sticky="ew", pady=(14, 8))
        rownum += 1

        # --- Editable fields ---
        editable_lbl_style = {'font': label_font, 'foreground': "#1c2840"}
        editable_entry_style = {'font': entry_font}

        # Dish
        ttk.Label(mainframe, text="Dish", **editable_lbl_style) \
            .grid(row=rownum, column=0, sticky="e", pady=2, padx=(0, 8))
        dish_var = tk.StringVar(value=order['dish'])
        dish_box = ttk.Entry(mainframe, textvariable=dish_var, width=30, **editable_entry_style)
        dish_box.grid(row=rownum, column=1, sticky="w", pady=2)
        rownum += 1

        # Pax (numeric only)
        def validate_pax(char):
            return char.isdigit() or char == ""

        vcmd = (win.register(validate_pax), '%P')
        ttk.Label(mainframe, text="Pax", **editable_lbl_style) \
            .grid(row=rownum, column=0, sticky="e", pady=2, padx=(0, 8))
        pax_var = tk.StringVar(value=str(order['pax']))
        pax_box = ttk.Entry(mainframe, textvariable=pax_var, width=30,
                            validate="key", validatecommand=vcmd,
                            **editable_entry_style)
        pax_box.grid(row=rownum, column=1, sticky="w", pady=2)
        rownum += 1

        # Section
        ttk.Label(mainframe, text="Section", **editable_lbl_style) \
            .grid(row=rownum, column=0, sticky="e", pady=2, padx=(0, 8))
        section_var = tk.StringVar(value=order['galley_section'])
        section_box = ttk.Combobox(mainframe, textvariable=section_var, width=30, values=["HOT", "COLD", "PASTRY"])
        section_box.grid(row=rownum, column=1, sticky="w", pady=2)
        rownum += 1

        # Standing Order (Yes/No)
        ttk.Label(mainframe, text="Standing Order", **editable_lbl_style) \
            .grid(row=rownum, column=0, sticky="e", pady=2, padx=(0, 8))
        standing_var = tk.StringVar(
            value=order['standing_order'] if order['standing_order'] in ("YES", "NO") else "NO"
        )
        standing_box = ttk.Combobox(
            mainframe, textvariable=standing_var,
            values=["YES", "NO"], width=28,
            state="readonly", font=entry_font
        )
        standing_box.grid(row=rownum, column=1, sticky="w", pady=2)
        rownum += 1

        # Special Requests
        ttk.Label(mainframe, text="Special Requests", **editable_lbl_style) \
            .grid(row=rownum, column=0, sticky="e", pady=2, padx=(0, 8))
        reqs_var = tk.StringVar(value=order['special_requests'] or "")
        reqs_box = ttk.Entry(mainframe, textvariable=reqs_var, width=30, **editable_entry_style)
        reqs_box.grid(row=rownum, column=1, sticky="w", pady=2)
        rownum += 1

        editable_widgets = [dish_box, pax_box, section_box, standing_box, reqs_box]

        # --- Spacer before veto ---
        sep2 = ttk.Separator(mainframe, orient="horizontal")
        sep2.grid(row=rownum, column=0, columnspan=2, sticky="ew", pady=(16, 4))
        rownum += 1

        # --- Veto section ---
        veto_frame = ttk.Frame(mainframe, padding=(6, 8, 6, 8))
        veto_frame.grid(row=rownum, column=0, columnspan=2, sticky="ew", pady=(0, 8))
        veto_frame.grid_columnconfigure(1, weight=1)

        # initialize veto checkbox from order['chef_flag']
        is_vetoed = (order.get('chef_flag') or "").upper() == "DISREGARD"
        veto_var = tk.BooleanVar(value=is_vetoed)
        veto_check = ttk.Checkbutton(
            veto_frame, text=" Veto (Remove) Order",
            variable=veto_var,
            bootstyle="danger" if hasattr(ttk.Checkbutton, 'bootstyle') else ""
        )
        veto_check.grid(row=0, column=0, sticky="w")

        # only pre-fill reason if the order was vetoed
        # only pre-fill reason if the order was vetoed
        veto_reason_initial = order.get('chef_remark', '') if is_vetoed else ""
        veto_reason_var = tk.StringVar(value=veto_reason_initial)

        veto_reason_box = ttk.Entry(
            veto_frame, textvariable=veto_reason_var,
            width=30, font=entry_font
        )

        ttk.Label(
            veto_frame, text="Reason for cancellation:",
            font=label_font, foreground="#a12323"
        ).grid(row=1, column=0, sticky="e", padx=(0, 6))
        veto_reason_box.grid(row=1, column=1, sticky="ew", pady=(8, 2), padx=(0, 2))

        # ensure spacing
        veto_frame.grid_rowconfigure(2, minsize=8)

        # function to enable/disable fields when toggling veto
        def apply_veto_state():
            if veto_var.get():
                # veto ON: disable all editors, enable reason
                for w in editable_widgets:
                    w.state(['disabled'])
                veto_reason_box.state(['!disabled'])
            else:
                # veto OFF: enable all editors, disable reason
                for w in editable_widgets:
                    w.state(['!disabled'])
                veto_reason_box.state(['disabled'])

        # bind + initialize
        veto_var.trace_add('write', lambda *_: apply_veto_state())
        apply_veto_state()

        # --- Button bar ---
        btn_bar = ttk.Frame(win, padding=(10, 0, 10, 12))
        btn_bar.pack(fill="x", side="bottom")
        btn_bar.grid_columnconfigure(0, weight=1)
        btn_bar.grid_columnconfigure(1, weight=1)

        save_btn = ttk.Button(btn_bar, text="💾 Save", width=12,
                              style="success.TButton" if "success.TButton" in ttk.Style().theme_names() else "")
        cancel_btn = ttk.Button(btn_bar, text="Cancel", width=8,
                                style="secondary.TButton" if "secondary.TButton" in ttk.Style().theme_names() else "")
        save_btn.grid(row=0, column=0, padx=12, pady=(6, 2), sticky="e")
        cancel_btn.grid(row=0, column=1, padx=8, pady=(6, 2), sticky="w")

        # --- Save logic ---
        def on_save():
            orig_flag = (order.get('chef_flag') or "").upper()

            # --- 1) Vetoing the order (checkbox checked) ---
            if veto_var.get():
                if not veto_reason_var.get().strip():
                    messagebox.showwarning(
                        "Veto Reason Required",
                        "Please enter a reason for disregarding the order."
                    )
                    return
                new_flag = "DISREGARD"
                new_remark = veto_reason_var.get().strip()

            # --- 2) Un-vetoing a previously vetoed order ---
            elif orig_flag == "DISREGARD":
                # unchecking the veto = clearing the flag
                new_flag = ""
                new_remark = ""

            # --- 3) Editing fields on a non-vetoed order ---
            else:
                edited = (
                        dish_var.get() != order['dish'] or
                        pax_var.get() != str(order['pax']) or
                        section_var.get() != order['galley_section'] or
                        standing_var.get() != order['standing_order'] or
                        reqs_var.get() != (order['special_requests'] or "")
                )
                if not edited:
                    messagebox.showinfo("No Change", "No fields were changed. Nothing to save.")
                    return
                new_flag = "EDITED"
                new_remark = ""  # <--- IMPORTANT: keep empty so veto reason stays clean

            # --- 4) Persist changes ---
            try:
                if new_flag == "EDITED":
                    # update all the editable columns + flag/remark
                    self.db_manager.update_order(
                        order_id=order['id'],
                        dish=dish_var.get().strip(),
                        pax=pax_var.get().strip(),
                        section=section_var.get().strip(),
                        standing_order=standing_var.get(),
                        special_requests=reqs_var.get().strip(),
                        chef_flag=new_flag,
                        chef_remark=new_remark
                    )
                else:
                    # either DISREGARD or clearing a veto
                    self.db_manager.flag_order(order['id'], new_flag, new_remark)
            except Exception as e:
                messagebox.showerror("Error", f"Could not save changes:\n{e}")
                return

            win.destroy()
            self.load_orders()

        save_btn.config(command=on_save)
        cancel_btn.config(command=win.destroy)

        # focus on first editable widget
        dish_box.focus_set()

    def on_time_slot_selected(self, event=None):
        ts = self.time_slot_var.get()
        self.selected_time_slot = ts.strip().upper()
        self.load_orders()

    def on_order_double_click(self, event):
        """
        Pop up a read-only window showing all order fields
        when the user double-clicks a row.
        """
        iid = self.tree.identify_row(event.y)
        if not iid:
            return

        vals = self.tree.item(iid, "values")
        cols = ["Manager", "Cabin", "Guest", "Dish", "Pax",
                "Allergy", "Requests", "Time Slot", "Section", "Standing"]

        # build popup
        win = tk.Toplevel(self)
        win.title("Order Details")
        win.geometry("400x400")
        win.transient(self)
        win.grab_set()

        frm = ttk.Frame(win, padding=10)
        frm.pack(fill='both', expand=True)
        frm.columnconfigure(1, weight=1)

        # show each field
        for row, (col_name, val) in enumerate(zip(cols, vals)):
            ttk.Label(frm, text=col_name + ":", font=("Helvetica", 10, "bold")) \
                .grid(row=row, column=0, sticky="e", pady=4, padx=(0, 8))
            # wrap long text
            lbl = ttk.Label(frm, text=val or "", wraplength=250, justify="left")
            lbl.grid(row=row, column=1, sticky="w", pady=4)

        # close button
        btn = ttk.Button(frm, text="Close", command=win.destroy)
        btn.grid(row=len(cols), column=0, columnspan=2, pady=(12, 0))

    def on_date_selected(self, event=None):
        dt = self.date_var.get()
        self.selected_date = dt
        self.load_orders()

    def on_filter_change(self):
        if self.section_vars["All"].get():
            for s in ["Hot Section", "Cold Section", "Dessert"]:
                self.section_vars[s].set(False)
        else:
            self.section_vars["All"].set(False)
        self.load_orders()

    def get_selected_sections(self):
        if self.section_vars["All"].get():
            return None
        labs = [s for s in self.sections if self.section_vars[s].get()]
        mapped = [self.section_mapping.get(x, x) for x in labs]
        return mapped if mapped else None  # None = treat as "All"


    def _add_header(self, canvas, doc, venue_name, export_date):
        from reportlab.lib.pagesizes import letter, landscape
        import os
        page_width = landscape(letter)[0]
        banner_path = os.path.join("icons", "pass_banner_pdf.png")
        logo_height = 110
        logo_width = 150
        logo_top_space = 15

        # Where to start drawing (top Y)
        top_y = doc.pagesize[1] - logo_top_space  # Near page top

        # Get page dimensions
        page_width = doc.pagesize[0]

        # Calculate the centered x-coordinate for the logo
        logo_x = (page_width - logo_width) / 2

        # Draw logo centered at the top
        if os.path.exists(banner_path):
            canvas.drawImage(banner_path, logo_x, top_y - logo_height,
                             width=logo_width, height=logo_height, mask='auto')

        # Calculate line position: always just below logo, even for tall logos
        divider_y = top_y - logo_height - 14  # -8 gives a little air below logo

        # HEADER TEXT: centered, just above the divider
        canvas.setFont("Times-Bold", 18)
        header_text = f"PRE-ORDERS FOR {venue_name}"
        header_width = canvas.stringWidth(header_text, "Times-Bold", 16)
        header_x = (page_width - header_width) / 2
        header_y = divider_y + 8  # 8 points above the line
        canvas.drawString(header_x, header_y, header_text)

        # DATE/TIMESTAMP: right top, aligns with header text baseline
        canvas.setFont("Helvetica-Bold", 8)
        timestamp_text = f"Date: {export_date}    Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        canvas.drawRightString(page_width - 40, header_y, timestamp_text)

        # BLUE DIVIDER LINE just under header text (and logo)
        canvas.saveState()
        canvas.setFillColorRGB(0.2, 0.4, 0.6)
        canvas.rect(40, divider_y, page_width - 80, 2, stroke=0, fill=1)
        canvas.restoreState()

        # Page number (right, under line)
        canvas.setFont("Helvetica", 8)
        canvas.drawRightString(page_width - 40, divider_y - 10, f"Page {canvas.getPageNumber()}")
    from reportlab.lib.enums import TA_CENTER
    # ========== ADDED/CHANGED ==========
    def export_to_pdf(self):
        """
        If "ALL" is selected in the Venue combo, export a combined PDF
        sorted by each venue and separated by sections on different pages.
        Otherwise, export only the current venue’s data as a single table.
        """
        if self.selected_venue_name == "ALL":
            self.export_all_venues_to_pdf()
        else:
            self.export_single_venue_to_pdf()

    # ========== ADDED/CHANGED ==========

    def export_single_venue_to_pdf(self):
        """
        Export the current venue's orders; each galley section (Hot/Cold/Pastry)
        gets its own page. Vetoed orders (chef_flag == 'DISREGARD') are excluded.
        Voyage-aware: filenames/headers include the current voyage; any per-row
        re-lookups include venue_id, service_date, and voyage_id.
        """
        import os, platform, subprocess, getpass
        from collections import defaultdict
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
        from reportlab.lib.pagesizes import letter, landscape
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.enums import TA_CENTER
        from reportlab.lib import colors

        vid = getattr(self.db_manager, "current_voyage_id", None)
        sc = self.get_selected_sections()

        # 1) Pull exactly what the UI shows (already voyage-scoped in get_orders)
        data = self.db_manager.get_orders(
            venue_id=self.selected_venue_id,
            selected_date=self.selected_date,
            time_slot=self.selected_time_slot,
            sections=sc
        )

        # 1b) Ensure chef_flag/remark exist (older rows / legacy fetch)
        rows = []
        for d in data:
            d = dict(d)  # copy
            if "chef_flag" not in d or "chef_remark" not in d:
                p = self.db_manager._param()
                sql = f"""
                    SELECT chef_flag, chef_remark
                      FROM preorders
                     WHERE cabin_number      = {p}
                       AND guest_name        = {p}
                       AND dish              = {p}
                       AND service_time_slot = {p}
                       AND galley_section    = {p}
                       AND standing_order    = {p}
                       AND venue_id          = {p}
                       AND service_date      = {p}
                       AND voyage_id         = {p}
                     ORDER BY id DESC
                     LIMIT 1
                """
                params = (
                    d.get("cabin_number"), d.get("guest_name"), d.get("dish"),
                    d.get("service_time_slot"), d.get("galley_section"), d.get("standing_order"),
                    self.selected_venue_id, self.selected_date, vid
                )
                with self.db_manager.get_connection() as conn:
                    if self.db_manager.backend == "mysql":
                        cur = conn.cursor(dictionary=True)
                    else:
                        cur = conn.cursor()
                    cur.execute(sql, params)
                    row = cur.fetchone()
                    cur.close()
                if row:
                    if isinstance(row, tuple):
                        d["chef_flag"], d["chef_remark"] = row[0], row[1]
                    else:
                        d["chef_flag"] = row.get("chef_flag", "")
                        d["chef_remark"] = row.get("chef_remark", "")
                else:
                    d["chef_flag"] = ""
                    d["chef_remark"] = ""
            rows.append(d)

        # 2) Exclude vetoed
        filtered = [r for r in rows if (r.get("chef_flag") or "").upper() != "DISREGARD"]
        if not filtered:
            messagebox.showinfo("No Data", "No orders to export.")
            return

        # 3) Save dialog (stamp voyage)
        default = f"{self.selected_venue_name}_{self.selected_date}_{vid or 'NOVOY'}.pdf"
        path = filedialog.asksaveasfilename(
            initialfile=default, defaultextension=".pdf",
            filetypes=[("PDF files", "*.pdf")],
            title="Save Galley Orders as PDF"
        )
        if not path:
            return

        try:
            # Group by galley_section
            section_map = defaultdict(list)
            for r in filtered:
                section_map[r.get("galley_section")].append(r)
            sorted_secs = sorted(section_map.keys(), key=lambda x: (x is None, x))

            # Styles
            styles = getSampleStyleSheet()
            cell_style = ParagraphStyle(
                "CellStyle", parent=styles["Normal"],
                fontName="Helvetica", fontSize=7.7, leading=8.8, alignment=TA_CENTER
            )
            header_style = ParagraphStyle(
                "HeaderStyle", parent=styles["Normal"],
                fontName="Helvetica-Bold", fontSize=9.5,
                textColor=colors.white, alignment=TA_CENTER, leading=11
            )
            section_style = ParagraphStyle(
                "SectionHeader", parent=styles["Normal"],
                fontName="Helvetica-Bold", fontSize=12,
                textColor=colors.black, alignment=TA_CENTER,
                spaceBefore=12, spaceAfter=7
            )
            summary_style = ParagraphStyle("SummaryStyle", parent=styles["Normal"], fontSize=7, leftIndent=10,
                                           spaceBefore=3)

            def make_sec_header(sec):
                txt = (f"PRE-ORDERS FOR: {self.selected_venue_name.upper()} - "
                       f"SECTION: {str(sec or 'UNKNOWN').upper()} - VOYAGE: {vid or 'N/A'}")
                return Paragraph(txt, section_style)

            table_header = [
                Paragraph("CABIN & GUEST", header_style),
                Paragraph("DISH", header_style),
                Paragraph("PAX", header_style),
                Paragraph("ALLERGIES", header_style),
                Paragraph("REQUESTS", header_style),
                Paragraph("TIME SLOT", header_style),
                Paragraph("SECTION", header_style),
                Paragraph("MNGR", header_style),
                Paragraph("STD?", header_style),
            ]
            ratios = [1.4, 2.0, 0.56, 1.5, 1.5, 0.8, 0.7, 0.6, 0.45]
            total_w = landscape(letter)[0] - 80
            col_widths = [(r / sum(ratios)) * total_w for r in ratios]

            # Build PDF
            doc = SimpleDocTemplate(path, pagesize=landscape(letter),
                                    leftMargin=40, rightMargin=40, topMargin=110, bottomMargin=36)
            elems = []
            first = True

            for sec in sorted_secs:
                if not first:
                    elems.append(PageBreak())
                first = False
                elems.append(Spacer(1, 14))
                elems.append(make_sec_header(sec))

                data = [table_header]
                for r in section_map[sec]:
                    merged = f"{r.get('cabin_number', '')} / {r.get('guest_name', '')}"
                    data.append([
                        Paragraph(merged, cell_style),
                        Paragraph(r.get("dish", ""), cell_style),
                        Paragraph(str(r.get("pax", "")), cell_style),
                        Paragraph(r.get("allergy_notes", "") or "", cell_style),
                        Paragraph(r.get("special_requests", "") or "", cell_style),
                        Paragraph(r.get("service_time_slot", ""), cell_style),
                        Paragraph(r.get("galley_section", ""), cell_style),
                        Paragraph(r.get("manager", ""), cell_style),
                        Paragraph(r.get("standing_order", ""), cell_style),
                    ])

                if len(data) == 1:
                    data.append([Paragraph("No orders for this section", cell_style)] + [""] * (len(table_header) - 1))

                table = Table(data, colWidths=col_widths, repeatRows=1)
                table.setStyle(TableStyle([
                    ("BACKGROUND", (0, 0), (-1, 0), colors.darkblue),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, 0), 10),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.whitesmoke, colors.lightgrey]),
                    ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
                    ("LEFTPADDING", (0, 0), (-1, -1), 2),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 2),
                    ("TOPPADDING", (0, 0), (-1, -1), 1),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
                ]))

                # allergy highlight
                for idx, row in enumerate(data[1:], start=1):
                    av = row[3].getPlainText() if hasattr(row[3], "getPlainText") else str(row[3])
                    if av.strip() not in ("", "-", "None", "N/A"):
                        table.setStyle([
                            ("BACKGROUND", (3, idx), (3, idx), colors.pink),
                            ("TEXTCOLOR", (3, idx), (3, idx), colors.red),
                            ("FONTNAME", (3, idx), (3, idx), "Helvetica-Bold"),
                        ])

                elems.append(table)
                total_orders = len(section_map[sec])
                total_pax = sum(int(r.get("pax") or 0) for r in section_map[sec] if str(r.get("pax")).isdigit())
                summary = Paragraph(f"<b>Total Orders:</b> {total_orders}   <b>Total Pax:</b> {total_pax}",
                                    summary_style)
                elems.extend([Spacer(1, 4), summary])

            # header/footer
            def _header(canvas, doc):
                self._add_header(canvas, doc, f"{self.selected_venue_name}",
                                 self.selected_date)
                canvas.setFont("Helvetica-Oblique", 7)
                user = getpass.getuser() if hasattr(getpass, 'getuser') else "Unknown"
                ts = datetime.now().strftime("%Y-%m-%d %H:%M")
                canvas.drawString(40, 28, f"Printed by: {user} on {ts}")

            doc.build(elems, onFirstPage=_header, onLaterPages=_header)
            messagebox.showinfo("Success", f"Orders exported to PDF:\n{path}")

            if messagebox.askyesno("Open File", "Open the exported PDF now?"):
                try:
                    if platform.system() == "Windows":
                        os.startfile(path)
                    elif platform.system() == "Darwin":
                        subprocess.run(["open", path], check=True)
                    else:
                        subprocess.run(["xdg-open", path], check=True)
                except Exception as e:
                    messagebox.showerror("Error", f"Could not open file:\n{e}")

        except Exception as e:
            logging.error(f"Error exporting to PDF: {e}", exc_info=True)
            messagebox.showerror("Export Failed", f"An error occurred:\n{e}")

    def export_all_venues_to_pdf(self):
        """
        Export a master PDF for ALL venues; each Venue is grouped, and each
        galley section is on its own page. Excludes DISREGARD rows.
        Voyage-aware: uses voyage-scoped get_orders; stamps voyage in filename/header.
        """
        import os, platform, subprocess, getpass
        from collections import defaultdict
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
        from reportlab.lib.pagesizes import letter, landscape
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.enums import TA_CENTER
        from reportlab.lib import colors

        vid = getattr(self.db_manager, "current_voyage_id", None)
        sc = self.get_selected_sections()

        # 1) Gather filtered orders per venue (get_orders is voyage-scoped)
        venues = self.db_manager.get_venues()
        all_orders = []
        for venue in venues:
            filtered = self.db_manager.get_orders(
                venue_id=venue["id"],
                selected_date=self.selected_date,
                time_slot=self.selected_time_slot,
                sections=sc
            )
            for o in filtered:
                oo = dict(o)
                oo["venue_name"] = venue["name"]
                all_orders.append(oo)

        kept = [r for r in all_orders if (r.get("chef_flag", "") or "").upper() != "DISREGARD"]
        if not kept:
            messagebox.showinfo("No Data", "No   orders for ALL venues.")
            return

        # 2) Save dialog (stamp voyage)
        default = f"ALL_Venues_{self.selected_date}_{vid or 'NOVOY'}.pdf"
        path = filedialog.asksaveasfilename(
            initialfile=default, defaultextension=".pdf",
            filetypes=[("PDF files", "*.pdf")],
            title="Save ALL Venues Galley Orders as PDF"
        )
        if not path:
            return

        try:
            # Group by venue → section
            grouped = defaultdict(lambda: defaultdict(list))
            for r in kept:
                grouped[r["venue_name"]][r.get("galley_section")].append(r)

            # Styles
            styles = getSampleStyleSheet()
            cell_style = ParagraphStyle(
                "CellStyle", parent=styles["Normal"],
                fontName="Helvetica", fontSize=7.7, leading=8.8, alignment=TA_CENTER
            )
            header_style = ParagraphStyle(
                "HeaderStyle", parent=styles["Normal"],
                fontName="Helvetica-Bold", fontSize=9.5,
                textColor=colors.white, alignment=TA_CENTER, leading=11
            )
            section_style = ParagraphStyle(
                "SectionHeader", parent=styles["Normal"],
                fontName="Helvetica-Bold", fontSize=12,
                textColor=colors.black, alignment=TA_CENTER,
                spaceBefore=12, spaceAfter=7
            )
            summary_style = ParagraphStyle("SummaryStyle", parent=styles["Normal"], fontSize=7, leftIndent=10,
                                           spaceBefore=3)

            def make_header(venue, section):
                txt = f"PRE-ORDERS FOR: {venue.upper()} — SECTION: {str(section or 'UNKNOWN').upper()} - (VOYAGE: {vid or 'N/A'})"
                return Paragraph(txt, section_style)

            table_header = [
                Paragraph("CABIN & GUEST", header_style),
                Paragraph("DISH", header_style),
                Paragraph("PAX", header_style),
                Paragraph("ALLERGIES", header_style),
                Paragraph("REQUESTS", header_style),
                Paragraph("TIME SLOT", header_style),
                Paragraph("SECTION", header_style),
                Paragraph("MNGR", header_style),
                Paragraph("STD?", header_style),
            ]
            ratios = [1.4, 2.0, 0.56, 1.5, 1.5, 0.8, 0.7, 0.6, 0.45]
            total_w = landscape(letter)[0] - 80
            col_widths = [(r / sum(ratios)) * total_w for r in ratios]

            doc = SimpleDocTemplate(path, pagesize=landscape(letter),
                                    leftMargin=40, rightMargin=40, topMargin=110, bottomMargin=36)
            elements = []
            first = True

            for venue in sorted(grouped.keys(), key=str.lower):
                for section in sorted(grouped[venue].keys(), key=lambda x: (x is None, x)):
                    if not first:
                        elements.append(PageBreak())
                    first = False
                    elements.append(Spacer(1, 14))
                    elements.append(make_header(venue, section))

                    data = [table_header]
                    orders = grouped[venue][section]

                    if orders:
                        for o in orders:
                            cg = f"{o.get('cabin_number', '')} / {o.get('guest_name', '')}"
                            data.append([
                                Paragraph(cg, cell_style),
                                Paragraph(o.get("dish", ""), cell_style),
                                Paragraph(str(o.get("pax", "")), cell_style),
                                Paragraph(o.get("allergy_notes", "") or "", cell_style),
                                Paragraph(o.get("special_requests", "") or "", cell_style),
                                Paragraph(o.get("service_time_slot", ""), cell_style),
                                Paragraph(o.get("galley_section", ""), cell_style),
                                Paragraph(o.get("manager", ""), cell_style),
                                Paragraph(o.get("standing_order", ""), cell_style),
                            ])
                    else:
                        data.append(
                            [Paragraph("No orders for this section", cell_style)] + [""] * (len(table_header) - 1))

                    tbl = Table(data, colWidths=col_widths, repeatRows=1)
                    tbl.setStyle(TableStyle([
                        ("BACKGROUND", (0, 0), (-1, 0), colors.darkblue),
                        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                        ("FONTSIZE", (0, 0), (-1, 0), 10),
                        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.whitesmoke, colors.lightgrey]),
                        ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
                        ("LEFTPADDING", (0, 0), (-1, -1), 2),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 2),
                        ("TOPPADDING", (0, 0), (-1, -1), 1),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
                    ]))

                    # allergy highlight
                    for idx, row in enumerate(data[1:], start=1):
                        av = row[3].getPlainText() if hasattr(row[3], "getPlainText") else str(row[3])
                        if av.strip() not in ("", "-", "None", "N/A"):
                            tbl.setStyle([
                                ("BACKGROUND", (3, idx), (3, idx), colors.pink),
                                ("TEXTCOLOR", (3, idx), (3, idx), colors.red),
                                ("FONTNAME", (3, idx), (3, idx), "Helvetica-Bold"),
                            ])

                    elements.append(tbl)
                    total_orders = len(orders)
                    total_pax = sum(int(o.get("pax") or 0) for o in orders if str(o.get("pax")).isdigit())
                    summ = Paragraph(f"<b>Total Orders:</b> {total_orders}   <b>Total Pax:</b> {total_pax}",
                                     summary_style)
                    elements.append(Spacer(1, 4))
                    elements.append(summ)

            def _header(canvas, doc):
                self._add_header(canvas, doc, f"ALL VENUES ", self.selected_date)
                canvas.setFont("Helvetica-Oblique", 7)
                user = getpass.getuser() if hasattr(getpass, 'getuser') else "Unknown"
                text = f"Printed by: {user} on {datetime.now():%Y-%m-%d %H:%M}"
                canvas.drawString(40, 28, text)

            doc.build(elements, onFirstPage=_header, onLaterPages=_header)
            messagebox.showinfo("Success", f"ALL Venues orders exported to PDF:\n{path}")

            if messagebox.askyesno("Open File", "Open the exported PDF now?"):
                try:
                    if platform.system() == "Windows":
                        os.startfile(path)
                    elif platform.system() == "Darwin":
                        subprocess.run(["open", path], check=True)
                    else:
                        subprocess.run(["xdg-open", path], check=True)
                except Exception as e:
                    messagebox.showerror("Error", f"Could not open file:\n{e}")

        except Exception as e:
            logging.error(f"Error exporting ALL Venues to PDF: {e}", exc_info=True)
            messagebox.showerror("Export Failed", f"An error occurred:\n{e}")

    # ========== ADDED/CHANGED ==========


# ----------------------------
# Main Execution
# ----------------------------
def main():
    app = GalleyApp()
    app.mainloop()


if __name__ == "__main__":
    main()
