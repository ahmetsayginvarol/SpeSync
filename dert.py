import sys
from pathlib import Path
import sqlite3
import bcrypt
import logging
from contextlib import contextmanager
import tkinter as tk
from tkinter import messagebox, filedialog, simpledialog
from ttkbootstrap import Style, ttk
from ttkbootstrap.constants import *
from datetime import datetime, timedelta
import pandas as pd  # For exporting to Excel
from tkcalendar import DateEntry
from datetime import datetime, timedelta
from tkinter import PhotoImage
from ttkbootstrap.icons import Icon
# Suppose in show_main_order_screen, after creating header_frame:

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

# ----------------------------
# Database Manager Class
# ----------------------------

# ----------------------------
# Restaurant Application Class
# ----------------------------
 #----------------------------
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
PASSWORD_MIN_LENGTH = 6

# ----------------------------
# Utility Function to Determine Database Path
# ----------------------------
def get_database_path():
    """
    Determines the absolute path to the orders.db file.
    """
    try:
        if getattr(sys, 'frozen', False):
            app_dir = Path(sys.executable).parent  # PyInstaller bundle
        else:
            app_dir = Path(__file__).resolve().parent.parent

        db_path = app_dir / "orders.db"
        logging.info(f"Database path set to: {db_path}")
        return db_path
    except Exception as e:
        logging.error(f"Error determining database path: {e}")
        raise

# ----------------------------
# Database Manager Class
# ----------------------------
class DatabaseManager:
    def __init__(self, db_path):
        self.db_path = db_path

    @contextmanager
    def get_connection(self):
        conn = None
        try:
            conn = sqlite3.connect(self.db_path)
            conn.execute("PRAGMA foreign_keys = ON")
            conn.row_factory = sqlite3.Row
            yield conn
            conn.commit()
        except sqlite3.Error as e:
            logging.error(f"SQLite error: {e}")
            if conn:
                conn.rollback()
            raise e
        finally:
            if conn:
                conn.close()

    def verify_user(self, username, password):
        try:
            with self.get_connection() as conn:
                cur = conn.cursor()
                cur.execute("SELECT password_hash FROM users WHERE username = ?", (username,))
                row = cur.fetchone()
                if row:
                    stored_hash = row["password_hash"] or ""
                    return bcrypt.checkpw(password.encode('utf-8'), stored_hash.encode('utf-8'))
        except Exception as e:
            logging.error(f"Error verifying user '{username}': {e}")
        return False

    def get_last_standing_copy_for_venue(self, venue_id):
        with self.get_connection() as conn:
            cur = conn.cursor()
            key_name = f"last_standing_copy_{venue_id}"
            cur.execute("SELECT value FROM app_config WHERE key=?", (key_name,))
            row = cur.fetchone()
            return row["value"] if row else None

    def set_last_standing_copy_for_venue(self, venue_id, date_str):
        with self.get_connection() as conn:
            cur = conn.cursor()
            key_name = f"last_standing_copy_{venue_id}"
            cur.execute(
                "INSERT OR REPLACE INTO app_config (key, value) VALUES (?,?)",
                (key_name, date_str)
            )

    def get_venues(self):
        try:
            with self.get_connection() as conn:
                cur = conn.cursor()
                cur.execute("SELECT id, name FROM venues ORDER BY name")
                return cur.fetchall()
        except sqlite3.Error as e:
            logging.error(f"Error fetching venues: {e}")
            return []

    def update_preorder(self,
                        old_manager,
                        old_cabin,
                        old_guest,
                        old_dish,
                        old_pax,
                        old_allergy,
                        old_requests,
                        old_timeslot,
                        old_galley,
                        old_standing,
                        venue_id,
                        service_date,
                        new_cabin,
                        new_guest,
                        new_dish,
                        new_pax,
                        new_allergy,
                        new_requests,
                        new_timeslot,
                        new_galley,
                        new_standing):
        """
        Updates an existing preorder row that matches the 'old_*' fields,
        and sets them to the 'new_*' fields. The 'venue_id' + 'service_date'
        remain the same, as in your delete_preorder method.
        """
        try:
            with self.get_connection() as conn:
                cur = conn.cursor()
                cur.execute("""
                    UPDATE preorders
                    SET cabin_number = ?,
                        guest_name = ?,
                        dish = ?,
                        pax = ?,
                        allergy_notes = ?,
                        special_requests = ?,
                        service_time_slot = ?,
                        galley_section = ?,
                        standing_order = ?
                    WHERE manager = ?
                      AND cabin_number = ?
                      AND guest_name = ?
                      AND dish = ?
                      AND pax = ?
                      AND allergy_notes = ?
                      AND special_requests = ?
                      AND service_time_slot = ?
                      AND galley_section = ?
                      AND standing_order = ?
                      AND venue_id = ?
                      AND service_date = ?
                """, (
                    new_cabin,
                    new_guest,
                    new_dish,
                    new_pax,
                    new_allergy,
                    new_requests,
                    new_timeslot,
                    new_galley,
                    new_standing,

                    old_manager,
                    old_cabin,
                    old_guest,
                    old_dish,
                    old_pax,
                    old_allergy,
                    old_requests,
                    old_timeslot,
                    old_galley,
                    old_standing,
                    venue_id,
                    service_date
                ))
                return cur.rowcount > 0
        except Exception as e:
            logging.error(f"Failed to update preorder: {e}")
            return False

    def add_allergy(self):
        sel = self.allergy_selected_var.get()
        if not sel:
            messagebox.showwarning("Selection Error", "Select an allergy first.")
            return


        if sel == "Other":
            # Prompt user to enter a custom allergy
            custom_allergy = simpledialog.askstring("Enter Allergy", "Enter the custom allergy:")
            if not custom_allergy:
                messagebox.showinfo("Info", "Custom allergy entry canceled.")
                return
            sel = custom_allergy.strip()

        existing = self.selected_allergies_listbox.get(0, tk.END)
        if sel in existing:
            messagebox.showwarning("Duplicate", f"'{sel}' is already in the list.")
            return

        # Add the selected or custom allergy to the list
        self.selected_allergies_listbox.insert(tk.END, sel)
        self.allergy_combobox.set("")
        self.unsaved_data = True

    def get_allergies(self):
        try:
            with self.get_connection() as conn:
                cur = conn.cursor()
                cur.execute("SELECT id, name FROM allergies ORDER BY name")
                rows = cur.fetchall()
                # Add "None" at the beginning and "Other" at the end
                return [{"id": 0, "name": "None"}] + [dict(r) for r in rows] + [{"id": -1, "name": "Other"}]
        except Exception as e:
            logging.error(f"Error fetching allergies: {e}")
            return [{"id": 0, "name": "None"}, {"id": -1, "name": "Other"}]

    def get_last_standing_copy(self):
        try:
            with self.get_connection() as conn:
                cur = conn.cursor()
                cur.execute("SELECT value FROM app_config WHERE key='last_standing_copy'")
                row = cur.fetchone()
                return row["value"] if row else None
        except sqlite3.Error as e:
            logging.error(f"Error fetching last_standing_copy: {e}")
            return None

    def get_standing_orders(self, service_date, venue_id):
        try:
            with self.get_connection() as conn:
                cur = conn.cursor()
                cur.execute("""
                    SELECT * FROM preorders
                    WHERE service_date=? AND standing_order='YES' AND venue_id=?
                """, (service_date, venue_id))
                return cur.fetchall()
        except sqlite3.Error as e:
            logging.error(f"Error fetching standing orders: {e}")
            return []

    def carry_standing_orders(self, today, tomorrow, venue_id):
        """
        Carry over all standing orders for the given venue_id from 'today' to 'tomorrow'.
        Updates a per-venue key in app_config: 'last_standing_copy_{venue_id}'.
        Returns the number of rows that were copied.
        """
        try:
            with self.get_connection() as conn:
                cur = conn.cursor()
                # Fetch all necessary fields, including guest_name
                cur.execute("""
                    SELECT cabin_number, dish, pax, allergy_notes, special_requests,
                           service_time_slot, galley_section, standing_order,
                           venue_id, manager, guest_name
                    FROM preorders
                    WHERE service_date=? AND standing_order='YES' AND venue_id=?
                """, (today, venue_id))
                rows = cur.fetchall()
                if not rows:
                    return 0

                # Insert rows into the next day's standing orders
                for r in rows:
                    cur.execute("""
                        INSERT INTO preorders (
                            cabin_number, dish, pax, allergy_notes, special_requests,
                            service_time_slot, galley_section, standing_order,
                            venue_id, service_date, manager, guest_name
                        )
                        VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                    """, (
                        r["cabin_number"],
                        r["dish"],
                        r["pax"],
                        r["allergy_notes"],
                        r["special_requests"],
                        r["service_time_slot"],
                        r["galley_section"],
                        r["standing_order"],
                        r["venue_id"],
                        tomorrow,
                        r["manager"],
                        r["guest_name"]
                    ))

                # Use a venue-specific key for last standing copy
                key_for_venue = f"last_standing_copy_{venue_id}"
                cur.execute(
                    "INSERT OR REPLACE INTO app_config (key, value) VALUES (?, ?)",
                    (key_for_venue, today)
                )
                return len(rows)
        except sqlite3.Error as e:
            logging.error(f"Error carrying standing orders: {e}")
            return 0

    def get_all_users(self):
        try:
            with self.get_connection() as conn:
                cur = conn.cursor()
                cur.execute("SELECT username FROM users")  # Adjust the table/column name as needed
                rows = cur.fetchall()
                return [{"username": row["username"]} for row in rows]
        except sqlite3.Error as e:
            logging.error(f"Error fetching users: {e}")
            return []

    def get_preorders_by_guest(self, cabin_number, guest_name):
        """
        Fetch all preorders (for any venue) matching cabin_number + guest_name
        that contain non-empty allergy_notes.
        """
        try:
            with self.get_connection() as conn:
                cur = conn.cursor()
                cur.execute("""
                    SELECT allergy_notes
                    FROM preorders
                    WHERE cabin_number = ?
                      AND guest_name = ?
                      AND allergy_notes IS NOT NULL
                      AND allergy_notes != ''
                """, (cabin_number, guest_name))
                rows = cur.fetchall()
                return [dict(row) for row in rows]
        except sqlite3.Error as e:
            logging.error(f"Error get_preorders_by_guest: {e}")
            return []

    def get_preorders(self, service_date, venue_id):
        try:
            with self.get_connection() as conn:
                cur = conn.cursor()
                cur.execute("""
                    SELECT manager,
                           cabin_number,
                           guest_name,           -- <-- ADD THIS COLUMN HERE
                           dish,
                           pax,
                           allergy_notes,
                           special_requests,
                           service_time_slot,
                           galley_section,
                           standing_order
                    FROM preorders
                    WHERE service_date = ?
                      AND venue_id = ?
                """, (service_date, venue_id))
                return cur.fetchall()
        except sqlite3.Error as e:
            logging.error(f"Error get_preorders: {e}")
            return []

    def insert_preorder(self, preorder):
        try:
            with self.get_connection() as conn:
                cur = conn.cursor()
                cur.execute("""
                    INSERT INTO preorders (
                        cabin_number, guest_name, dish, pax, allergy_notes, special_requests,
                        service_time_slot, galley_section, standing_order, venue_id, service_date, manager
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    preorder['cabin_number'],
                    preorder['guest_name'],  # Add guest name here
                    preorder['dish'],
                    preorder['pax'],
                    preorder['allergy_notes'],
                    preorder['special_requests'],
                    preorder['service_time_slot'],
                    preorder['galley_section'],
                    preorder['standing_order'],
                    preorder['venue_id'],
                    preorder['service_date'],
                    preorder['manager']
                ))
                logging.info(
                    f"Preorder added for Guest '{preorder['guest_name']}' in Cabin '{preorder['cabin_number']}'.")
                return True
        except sqlite3.Error as e:
            logging.error(f"Error inserting preorder: {e}")
            return False

    def delete_preorder(self, manager, cabin, guest, dish, pax, allergy, req,
                        ts, galley, stand, venue_id, service_date):
        try:
            with self.get_connection() as conn:
                cur = conn.cursor()
                cur.execute("""
                    DELETE FROM preorders
                    WHERE manager = ?
                      AND cabin_number = ?
                      AND guest_name = ?
                      AND dish = ?
                      AND pax = ?
                      AND allergy_notes = ?
                      AND special_requests = ?
                      AND service_time_slot = ?
                      AND galley_section = ?
                      AND standing_order = ?
                      AND venue_id = ?
                      AND service_date = ?
                """, (
                    manager, cabin, guest, dish, pax, allergy, req,
                    ts, galley, stand, venue_id, service_date
                ))
                if cur.rowcount > 0:
                    logging.info(f"Removed preorder for cabin {cabin}, guest '{guest}'.")
                    return True
                else:
                    return False
        except sqlite3.Error as e:
            logging.error(f"Error deleting preorder: {e}")
            return False

    # (Optional) for the guest recall
    def get_guests_for_cabin(self, cabin_number):
        try:
            with self.get_connection() as conn:
                cur = conn.cursor()
                cur.execute("""
                    SELECT g.first_name,
                           g.last_name,
                           GROUP_CONCAT(DISTINCT p.allergy_notes) AS allergies
                      FROM guests g
                 LEFT JOIN preorders p 
                        ON g.cabin_number = p.cabin_number
                       AND p.guest_name = (g.first_name || ' ' || g.last_name)
                     WHERE g.cabin_number = ?
                  GROUP BY g.first_name, g.last_name
                """, (cabin_number,))
                rows = cur.fetchall()
                logging.debug(f"Guests for cabin {cabin_number}: {rows}")
                return [dict(r) for r in rows]
        except sqlite3.Error as e:
            logging.error(f"Error getting guests for cabin {cabin_number}: {e}")
            return []


# ----------------------------
# Main RestaurantApp Class
# ----------------------------
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from ttkbootstrap import Style
from ttkbootstrap.constants import *
import logging
from datetime import datetime, timedelta

# Presume these come from your existing code or imports:
# from your_module import get_database_path, DatabaseManager, get_next_day_date

GALLEY_SECTIONS = ["Hot", "Cold", "Pastry"]  # example
PASSWORD_MIN_LENGTH = 6  # example

class RestaurantApp(tk.Tk):
    def __init__(self):
        super().__init__()

        self.cabin_number_var = tk.StringVar()
        self.temp_dishes = []
        self.dish_var = tk.StringVar()
        self.pax_var = tk.StringVar()
        self.special_requests_var = tk.StringVar()
        self.timeslot_var = tk.StringVar()
        self.galley_section_var = tk.StringVar(value=GALLEY_SECTIONS[0])
        self.standing_order_var = tk.BooleanVar()
        self.guest_name_var = tk.StringVar()
        self.service_date_var = tk.StringVar(value=get_next_day_date())
        # Initialize ttkbootstrap Style
        self.style = Style(theme='united')
        self.style.configure('Active.TEntry', foreground='black', background='#FFFF99')  # Yellow highlight
        self.style.configure('Active.TCombobox', fieldbackground='#FFFF99', background='white')

        # New state tracking variables
        self.unsaved_orders_exist = tk.BooleanVar(value=False)
        self.valid_cabin_entered = tk.BooleanVar(value=False)

        # Add these traces
        self.cabin_number_var.trace_add('write', self.validate_buttons)
        self.unsaved_orders_exist.trace_add('write', self.validate_buttons)

        self.title("Restaurant Pre-Order System")
        self.geometry("1250x900")
        self.resizable(True, True)
        self.iconbitmap('icons/icon_app.ico')

        # Initialize DB Manager
        db_path = get_database_path()
        self.db_manager = DatabaseManager(db_path)

        self.venue_id = None
        self.venue_name = None
        self.manager = None

        # All allergies from the DB
        self.allergies = []

        # Guest name radio choice, occupant-level
        self.guest_name_var = tk.StringVar()

        # Orders stored as:
        # (manager, cabin, guest_name, dish, pax, allergy, requests, timeslot, galley_section, standing, from_db)
        self.all_orders = []
        self.occupant_locked = False
        self.temp_dishes = []  # Will hold dish-level items for the current occupant

        # Track unsaved data
        self.unsaved_data = False

        # On close event
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

        self.show_login_screen()

        self.guest_name_var = tk.StringVar(value="")  # For displaying the guest name
        icon_obj = Icon()  # Instantiate without arguments



    # ---------------------------- LOGIN ----------------------------
    def show_login_screen(self):
        for w in self.winfo_children():
            w.destroy()

        # Load icons (ensure these files exist in the icons folder)
        self.user_icon = tk.PhotoImage(file="icons/user.png")
        self.password_icon = tk.PhotoImage(file="icons/password.png")
        self.enter_btn_img = tk.PhotoImage(file="icons/enter.png")

        frame = ttk.Frame(self, padding=20)
        frame.grid(sticky='nsew')
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        title_label = ttk.Label(frame, text="Manager Login", font=("Helvetica", 20, "bold"))
        title_label.grid(row=0, column=0, columnspan=2, pady=(0, 20))

        # Username Label with icon
        ttk.Label(frame,
                  text="Username:",
                  image=self.user_icon,
                  compound=LEFT,
                  font=("Helvetica", 12)
                  ).grid(row=1, column=0, pady=10, sticky='e')
        self.manager_var = tk.StringVar()
        manager_entry = ttk.Entry(frame, textvariable=self.manager_var, width=30, font=("Helvetica", 12))
        manager_entry.grid(row=1, column=1, pady=10, sticky='w')
        manager_entry.focus()

        # Password Label with icon
        ttk.Label(frame,
                  text="Password:",
                  image=self.password_icon,
                  compound=LEFT,
                  font=("Helvetica", 12)
                  ).grid(row=2, column=0, pady=10, sticky='e')
        self.password_var = tk.StringVar()
        password_entry = ttk.Entry(frame, textvariable=self.password_var, width=30, show='*', font=("Helvetica", 12))
        password_entry.grid(row=2, column=1, pady=10, sticky='w')

        # Key bindings
        manager_entry.bind("<Return>", lambda e: password_entry.focus())
        password_entry.bind("<Return>", lambda e: self.attempt_login())

        login_btn = ttk.Button(frame, text="Login", command=self.attempt_login, image=self.enter_btn_img, compound=LEFT, bootstyle=DANGER)
        login_btn.grid(row=3, column=0, columnspan=2, pady=20)
        login_btn.bind("<Return>", lambda e: self.attempt_login())

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
            messagebox.showinfo("Success", f"Welcome, {username}!")
            self.show_venue_selection()
        else:
            logging.warning(f"Failed login attempt for {username}.")
            messagebox.showerror("Login Failed", "Invalid username or password.")

    # ---------------------------- VENUE SELECTION ----------------------------
    def show_venue_selection(self):
        for w in self.winfo_children():
            w.destroy()

        frame = ttk.Frame(self, padding=20)
        frame.grid(sticky='nsew')
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        lbl = ttk.Label(frame, text=f"Logged in as: {self.manager}", font=("Helvetica", 14))
        lbl.pack(anchor='w', pady=(0, 10))

        lbl2 = ttk.Label(frame, text="Select Venue:", font=("Helvetica", 14))
        lbl2.pack(anchor='w', pady=(0, 10))

        vs = self.db_manager.get_venues()
        if not vs:
            messagebox.showerror("No Venues", "No venues in DB.")
            self.logout()
            return

        venue_names = [r["name"] for r in vs]
        self.venue_map = {r["name"]: r["id"] for r in vs}

        self.selected_venue_var = tk.StringVar(value=venue_names[0])
        vcombo = ttk.Combobox(frame, textvariable=self.selected_venue_var,
                              values=venue_names, state="readonly",
                              font=("Helvetica", 12))
        vcombo.pack(pady=5, ipadx=10, ipady=5)
        vcombo.focus()
        vcombo.bind("<Return>", lambda e: self.select_venue())

        btn = ttk.Button(frame, text="Select", command=self.select_venue, bootstyle=PRIMARY)
        btn.pack(pady=10)
        btn.bind("<Return>", lambda e: self.select_venue())



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
        self.venue_id = self.venue_map.get(sel, None)
        self.venue_name = sel
        if not self.venue_id:
            messagebox.showerror("Error", f"Venue ID not found for {sel}.")
            return

        self.load_allergies()
        self.check_and_carry_standing_orders()
        self.show_main_order_screen()
        self.populate_time_slots()

    # -------------- GUEST SELECTION LOGIC --------------
    def recall_guests_for_cabin(self, cabin_number):
        """
        Query DB for all guests in 'guests' table matching cabin_number.
        If multiple, show radio-button popup. If one, auto select. If none, clear.
        """
        if not cabin_number:
            self.guest_name_var.set("")
            return

        rows = self.db_manager.get_guests_for_cabin(cabin_number)
        if not rows:
            # no occupant found
            self.guest_name_var.set("")
            return
        if len(rows) == 1:
            f = rows[0].get("first_name", "").strip()
            l = rows[0].get("last_name", "").strip()
            self.guest_name_var.set(f"{f} {l}".strip())
        else:
            # multiple occupants
            self.popup_guest_selection(rows)





    def popup_guest_selection(self, guests):
        """
        Display a popup for selecting a guest if multiple guests are associated with a cabin.
        Fetch and display allergies dynamically based on the selected guest.
        """
        popup = tk.Toplevel(self)
        popup.title("Select Guest")
        popup.geometry("400x300")
        popup.grab_set()
        self.guest_selected = False
        popup.iconbitmap('icons/icon_app.ico')

        def on_popup_close():
            if not self.guest_selected:
                # No guest was actually selected
                self.cabin_number_var.set("")
                self.cabin_number_entry.focus()
            popup.destroy()

        popup.protocol("WM_DELETE_WINDOW", on_popup_close)

        # Label
        tk.Label(popup, text="Select a guest:", font=("Helvetica", 12)).pack(pady=10)

        # Frame for radio buttons and guest details
        selection_frame = ttk.Frame(popup, padding=10)
        selection_frame.pack(fill="both", expand=True)

        selected_index_var = tk.IntVar(value=-1)

        # Guest details display
        details_frame = ttk.LabelFrame(popup, text="Guest Details", padding=10)
        details_frame.pack(fill="both", expand=True, padx=10, pady=10)

        allergy_label = tk.Label(details_frame, text="Allergies: None",
                                 font=("Helvetica", 12), anchor="w", justify="left")
        allergy_label.pack(fill="x", pady=5)

        def display_guest_details(selected_index):
            if selected_index != -1:
                g = guests[selected_index]
                guest_name = f"{g['first_name']} {g['last_name']}".strip()
                # Just show combined allergies in the label:
                allergy_label.config(text=f"Allergies: {g.get('allergies', 'None')}")

        # Radio buttons for guests
        for i, g in enumerate(guests):
            guest_name = f"{g['first_name']} {g['last_name']}".strip()
            ttk.Radiobutton(
                selection_frame,
                text=guest_name,
                variable=selected_index_var,
                value=i,
                command=lambda: display_guest_details(selected_index_var.get())
            ).pack(anchor="w", pady=2)

        def select_guest():
            idx = selected_index_var.get()
            if idx == -1:
                messagebox.showwarning("Selection Error", "Please select a guest.")
                return

            chosen = guests[idx]
            full_name = f"{chosen['first_name']} {chosen['last_name']}".strip()

            # Update main GUI
            self.guest_name_var.set(full_name)
            self.guest_selected = True

            # -- Now recall occupant‐level allergies into main listbox --
            cabin_up = self.cabin_number_var.get().strip().upper()
            occupant_preorders = self.db_manager.get_preorders_by_guest(cabin_up, full_name)

            self.selected_allergies_listbox.delete(0, tk.END)
            occupant_allergies = set()

            for row in occupant_preorders:
                notes = (row.get("allergy_notes") or "").strip()
                if notes and notes.lower() != "none":
                    for a in notes.split(','):
                        occupant_allergies.add(a.strip())

            if occupant_allergies:
                for a in sorted(occupant_allergies):
                    self.selected_allergies_listbox.insert(tk.END, a)

                self.allergy_combobox.config(state='readonly')
                self.add_allergy_button.config(state='normal')
            else:
                self.allergy_selected_var.set("None")
                self.on_allergy_selected(None)



            popup.destroy()

        # Buttons
        button_frame = ttk.Frame(popup)
        button_frame.pack(fill="x", pady=10)

        ttk.Button(button_frame, text="Select", command=select_guest).pack(side="right", padx=5)
        ttk.Button(button_frame, text="Cancel", command=on_popup_close).pack(side="right", padx=5)

    # ---------------------------- ALLERGIES LOGIC ----------------------------
    def load_allergies(self):
        self.allergies = self.db_manager.get_allergies()
        logging.info("Allergies loaded.")

        # Safely update allergy_combobox if it exists
        if hasattr(self, 'allergy_combobox') and self.allergy_combobox.winfo_exists():
            raw = [a["name"] for a in self.allergies if a["name"].lower() != "none"]
            raw.append("Other")  # Add "Other" option
            self.allergy_combobox['values'] = raw



    def check_and_carry_standing_orders(self):
        today = datetime.now().strftime("%Y-%m-%d")
        tomorrow = (datetime.now().date() + timedelta(days=1)).strftime("%Y-%m-%d")

        # 1) GET the last copy date for *this* venue
        last_run = self.db_manager.get_last_standing_copy_for_venue(self.venue_id)
        if last_run == today:
            logging.info(f"Venue {self.venue_name} already carried standing orders today.")
            return

        # 2) If not carried yet, get the standing orders
        standing_orders = self.db_manager.get_standing_orders(today, self.venue_id)
        if not standing_orders:
            logging.info(f"No standing orders for {self.venue_name} on {today}. Nothing to carry.")
            return

        # 3) Confirm with user
        if not messagebox.askyesno(
                "Standing Orders",
                f"{len(standing_orders)} standing orders found for today in {self.venue_name}.\n"
                "Carry them over to tomorrow?"
        ):
            return

        # 4) Actually carry them forward
        carried_count = self.db_manager.carry_standing_orders(today, tomorrow, self.venue_id)
        if carried_count > 0:
            # Update the per-venue last copy date
            self.db_manager.set_last_standing_copy_for_venue(self.venue_id, today)
            messagebox.showinfo("Success", f"{carried_count} standing order(s) carried to {tomorrow}.")
        else:
            messagebox.showwarning("No Standing Orders", "No standing orders were carried over.")

    def populate_time_slots(self):
        try:
            with self.db_manager.get_connection() as conn:
                cur = conn.cursor()
                cur.execute("""
                    SELECT breakfast_available, lunch_available, dinner_available
                    FROM venues
                    WHERE id=?
                """, (self.venue_id,))
                row = cur.fetchone()
                if not row:
                    return
                slots = []
                if row["breakfast_available"]:
                    slots.append("BREAKFAST")
                if row["lunch_available"]:
                    slots.append("LUNCH")
                if row["dinner_available"]:
                    slots.append("DINNER")

                self.timeslot_dropdown['values'] = slots
                # Set "Dinner" as default if available, otherwise use the first slot
                if "DINNER" in slots:
                    self.timeslot_var.set("DINNER")
                elif slots:
                    self.timeslot_var.set(slots[0])
                else:
                    self.timeslot_var.set("")
        except Exception as e:
            logging.error(f"Error populating time slots: {e}")

    # ---------------------------- MAIN ORDER SCREEN ----------------------------

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
        # Remove all widgets from the main ordering screen
        for w in self.winfo_children():
            w.destroy()
        # Or specifically remove frames if you used them in a certain structure

        # If you want to reset certain variables:
        self.all_orders.clear()
        self.temp_dishes.clear()
        self.unsaved_data = False
        # but do NOT reset self.manager, because we stay logged in.
        # do NOT reset self.db_manager, etc.

    import tkinter as tk
    from tkinter import ttk





    def show_main_order_screen(self):
        # Clear existing widgets
        for w in self.winfo_children():
            w.destroy()

        # Set a minimalist white background
        self.configure(bg="white")

        # ------------------- Load Field Icons -------------------
        # Load and store icons so they are not garbage-collected.
        self.cabin_icon = tk.PhotoImage(file="icons/cabin.png")
        self.allergy_icon = tk.PhotoImage(file="icons/allergy.png")
        self.meal_icon = tk.PhotoImage(file="icons/meal.png")
        self.galley_icon = tk.PhotoImage(file="icons/galley.png")
        self.reqs_icon = tk.PhotoImage(file="icons/reqs.png")
        self.dish_icon = tk.PhotoImage(file="icons/dish.png")
        self.pax_icon = tk.PhotoImage(file="icons/pax.png")
        self.plus_allergy = tk.PhotoImage(file="icons/plus-square.png")
        # Other icons for buttons (if any) are loaded later

        # ------------------- MENU BAR and MAIN FRAME -------------------
        # (Menu bar and header code remains unchanged...)
        menubar = tk.Menu(self, bg="white", fg="black")
        self.config(menu=menubar)
        file_menu = tk.Menu(menubar, tearoff=0, bg="white", fg="black")
        file_menu.add_command(label="Logout", command=self.logout, accelerator="Ctrl+L")
        menubar.add_cascade(label="File", menu=file_menu)
        admin_menu = tk.Menu(menubar, tearoff=0, bg="white", fg="black")
        admin_menu.add_command(label="Today's Orders Preview", command=self.show_todays_orders)
        menubar.add_cascade(label="Admin", menu=admin_menu)
        help_menu = tk.Menu(menubar, tearoff=0, bg="white", fg="black")
        help_menu.add_command(label="Contact Info", command=self.show_help_info)
        menubar.add_cascade(label="Help", menu=help_menu)

        main_frame = ttk.Frame(self, padding=20)
        main_frame.grid(row=0, column=0, sticky="nsew")
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)
        main_frame.grid_rowconfigure(4, weight=1)
        main_frame.grid_columnconfigure(0, weight=1)

        # ------------------- HEADER (TOP FRAME) -------------------
        header_frame = ttk.Frame(main_frame)
        header_frame.grid(row=0, column=0, sticky="ew", pady=(0, 20))
        header_frame.grid_columnconfigure(1, weight=1)  # Center label expands

        # Center: Venue & Manager info
        header_label = ttk.Label(header_frame,
                                 text=f"Venue: {self.venue_name}   |   Manager: {self.manager}",
                                 font=("Helvetica", 16, "bold"))
        header_label.grid(row=0, column=1, sticky="ew")
        # Instead of Link, just do:
        switch_venue_button = ttk.Button(
            header_frame,
            text="Change Venue",
            command=self.prompt_switch_venue,
            bootstyle="danger.Outline.TButton"  # optional: this gives you a "link-style" button; you can omit or change
            # font=("Helvetica", 12, "underline")  # optional, if you still want it underlined
        )
        switch_venue_button.grid(row=0, column=0, pady=10, padx=10, sticky='w')

        # Right: Date & Guest Name
        right_frame = ttk.Frame(header_frame)
        right_frame.grid(row=0, column=2, sticky="e")
        # Date Frame
        date_frame = ttk.Frame(right_frame)
        date_frame.pack(side="top", anchor="e")
        ttk.Label(date_frame, text="Service Date:", font=("Helvetica", 12)).pack(side="left", padx=(0, 5))
        self.service_date_entry = ttk.Entry(date_frame, textvariable=self.service_date_var,
                                            width=12, font=("Helvetica", 12))
        self.service_date_entry.pack(side="left", fill="x")
        # Guest Name Frame
        guest_frame = ttk.Frame(right_frame)
        guest_frame.pack(side="top", anchor="e", pady=(5, 0))
        ttk.Label(guest_frame, text="Guest Name:", font=("Helvetica", 12)).pack(side="left")
        self.guest_name_label = ttk.Label(guest_frame, textvariable=self.guest_name_var,
                                          font=("Helvetica", 12), foreground="#333")
        self.guest_name_label.pack(side="left", padx=(5, 0))
        # ------------------- FORM FRAME -------------------
        form_frame = ttk.Labelframe(main_frame, text="Add New Order", bootstyle="danger", padding=15)
        form_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=10)
        form_frame.columnconfigure(1, weight=1)
        form_frame.columnconfigure(3, weight=1)

        # Helper function to create a label frame with fixed icon column:
        def create_field_label(master, icon, text, font=("Helvetica", 12)):
            frame = ttk.Frame(master)

            # Set uniform width for icons to maintain alignment
            icon_label = ttk.Label(frame, image=icon)
            icon_label.grid(row=0, column=0, padx=(5, 10), pady=5, sticky="w")

            # Use a fixed width for labels to ensure they align correctly
            text_label = ttk.Label(frame, text=text, font=font, width=15, anchor="w")
            text_label.grid(row=0, column=1, sticky="w")

            return frame

        # Row 0: Cabin Number
        cabin_label_frame = create_field_label(form_frame, self.cabin_icon, "Cabin Number:")
        cabin_label_frame.grid(row=0, column=0, sticky="e", padx=5, pady=5)
        self.cabin_number_entry = ttk.Entry(form_frame, textvariable=self.cabin_number_var,
                                            width=7, font=("Helvetica", 12))
        self.cabin_number_entry.grid(row=0, column=1, sticky="w", padx=5, pady=5)
        self.cabin_number_entry.bind("<FocusOut>", lambda e: self.on_cabin_change())
        self.cabin_number_entry.bind("<Return>", lambda e: self.dish_entry.focus())

        # Row 1: Dish
        dish_label_frame = create_field_label(form_frame, self.dish_icon, "Dish:")
        dish_label_frame.grid(row=1, column=0, sticky="e", padx=5, pady=5)
        self.dish_entry = ttk.Entry(form_frame,textvariable=self.dish_var,
                                    width=20, font=("Helvetica", 12))
        self.dish_entry.grid(row=1, column=1, sticky="w", padx=5, pady=5)
        self.dish_entry.bind("<KeyRelease>", self.update_entry_width)
        self.dish_entry.bind("<Return>", lambda e: self.pax_spinbox.focus())

        # Row 2: Pax Size (with pax.png icon)
        pax_label_frame = create_field_label(form_frame, self.pax_icon, "Pax Size:")
        pax_label_frame.grid(row=2, column=0, sticky="e", padx=5, pady=5)
        self.pax_var.set("1")
        self.pax_spinbox = tk.Spinbox(form_frame, from_=1, to=20,
                                      textvariable=self.pax_var, font=("Helvetica", 12),
                                      width=5)
        self.pax_spinbox.grid(row=2, column=1, sticky="w", padx=5, pady=5)

        # Row 3: Allergies
        allergy_label_frame = create_field_label(form_frame, self.allergy_icon, "Allergies:")
        allergy_label_frame.grid(row=3, column=0, sticky="e", padx=5, pady=5)
        allergy_frame = ttk.Frame(form_frame)
        allergy_frame.grid(row=3, column=1, sticky="w", padx=5, pady=5)
        self.allergy_selected_var = tk.StringVar()
        self.add_allergy_button_img = tk.PhotoImage(file="icons/plus-square.png")
        raw = [a["name"] for a in self.allergies]
        #if "None" not in (x.upper() for x in raw):
            #raw.insert(0, "None") ##Deleted due to mutiple calls (def on_allergy_selected)
        if "Other" not in raw:
            raw.append("Other")
        self.allergy_combobox = ttk.Combobox(allergy_frame, textvariable=self.allergy_selected_var,
                                             values=raw, state="readonly", font=("Helvetica", 12), width=20)


        self.allergy_combobox.grid(row=0, column=0, padx=(0, 10), sticky="ew")
        self.allergy_combobox.bind("<<ComboboxSelected>>", self.on_allergy_selected)
        self.add_allergy_button = ttk.Button(allergy_frame, style="danger.TButton",
                                             image=self.add_allergy_button_img, compound=LEFT, width=3,
                                             command=self.add_allergy)
        self.add_allergy_button.grid(row=0, column=1)
        self.allergy_combobox.current(0)





        # Row 4: Selected Allergies (unchanged)
        sel_allergy_frame = ttk.Frame(form_frame)
        sel_allergy_frame.grid(row=4, column=1, columnspan=2, sticky="w", padx=5, pady=10)
        ttk.Label(sel_allergy_frame, text="Selected Allergies:", font=("Helvetica", 12)).grid(row=0, column=0,
                                                                                              sticky="w")
        self.selected_allergies_listbox = tk.Listbox(sel_allergy_frame, height=5, width=30,
                                                     font=("Helvetica", 12))
        self.selected_allergies_listbox.grid(row=1, column=0, sticky="w", padx=(0, 10))
        self.selected_allergies_listbox.bind("<<ListboxSelect>>", self.update_remove_button_state)
        self.rem_btn = ttk.Button(sel_allergy_frame, text="Remove", command=self.remove_selected_allergy)
        self.rem_btn.grid(row=1, column=1, sticky="w")
        self.update_remove_button_state()
        self.selected_allergies_listbox.bind("<Delete>", self.remove_selected_allergy)
        self.on_allergy_selected()

        # Column 2-3: Special Requests, Time Slot, Galley Section, Standing Order
        reqs_label_frame = create_field_label(form_frame, self.reqs_icon, "Special Requests:")
        reqs_label_frame.grid(row=0, column=2, sticky="e", padx=(30, 5), pady=5)
        self.special_requests_entry = ttk.Entry(form_frame, textvariable=self.special_requests_var,
                                                width=30, font=("Helvetica", 12))
        self.special_requests_entry.grid(row=0, column=3, sticky="w", padx=5, pady=5)
        self.special_requests_entry.bind("<Return>", lambda e: self.timeslot_dropdown.focus())

        meal_label_frame = create_field_label(form_frame, self.meal_icon, "Time Slot:")
        meal_label_frame.grid(row=1, column=2, sticky="e", padx=(30, 5), pady=5)
        self.timeslot_dropdown = ttk.Combobox(form_frame, textvariable=self.timeslot_var,
                                              state="readonly", font=("Helvetica", 12))
        self.timeslot_dropdown.grid(row=1, column=3, sticky="w", padx=5, pady=5)
        self.timeslot_dropdown.bind("<Return>", lambda e: self.galley_section_dropdown.focus())

        galley_label_frame = create_field_label(form_frame, self.galley_icon, "Galley Section:")
        galley_label_frame.grid(row=2, column=2, sticky="e", padx=(30, 5), pady=5)
        self.galley_section_dropdown = ttk.Combobox(form_frame, textvariable=self.galley_section_var,
                                                    values=GALLEY_SECTIONS, state="readonly",
                                                    font=("Helvetica", 12))
        self.galley_section_dropdown.grid(row=2, column=3, sticky="w", padx=5, pady=5)
        self.galley_section_dropdown.bind("<Return>", lambda e: self.standing_order_check.focus())

        self.standing_order_check = ttk.Checkbutton(form_frame, text="Standing Order",
                                                    variable=self.standing_order_var,
                                                    style="danger.Outline.Toolbutton")
        self.standing_order_check.grid(row=3, column=3, padx=5, pady=5, sticky="w")
        self.standing_order_check.bind("<Return>", lambda e: self.validate_and_save())

        # ------------------- BUTTON FRAME -------------------
        btn_frame = ttk.Frame(main_frame)
        btn_frame.grid(row=2, column=0, sticky="ew", padx=5, pady=10)
        for i in range(3):
            btn_frame.grid_columnconfigure(i, weight=1)

        self.plus_icon = tk.PhotoImage(file="icons/plus.png")
        self.clipboard_icon = tk.PhotoImage(file="icons/clipboard.png")
        self.cloud_icon = tk.PhotoImage(file="icons/cloud.png")

        self.add_to_order_btn = ttk.Button(btn_frame, text="Add to Order".upper(),
                                           command=self.add_to_order,
                                           state="disabled", image=self.plus_icon, style='info.TButton',
                                           compound=LEFT)
        self.add_to_order_btn.grid(row=0, column=0, padx=5, pady=5, sticky="ew")

        self.save_button = ttk.Button(btn_frame, text="Finalize Order".upper(),
                                      command=self.validate_and_save, style='success.TButton',
                                      state="disabled", image=self.clipboard_icon,
                                      compound=LEFT)
        self.save_button.grid(row=0, column=1, padx=5, pady=5, sticky="ew")

        self.commit_btn = ttk.Button(btn_frame, text="Send to Database".upper(),
                                     command=self.commit_to_db,
                                     state="disabled", image=self.cloud_icon, style='danger.TButton',
                                     compound=LEFT)
        self.commit_btn.grid(row=0, column=2, padx=5, pady=5, sticky="ew")

        # ------------------- SEARCH FRAME -------------------
        search_frame = ttk.Frame(main_frame)
        search_frame.grid(row=3, column=0, sticky="ew", padx=5, pady=10)
        search_frame.grid_columnconfigure(1, weight=1)

        # Label for "Search:" remains as is.
        ttk.Label(search_frame, text="Search:", font=("Helvetica", 12)).grid(
            row=0, column=0, padx=(0, 5), pady=5, sticky="w"
        )

        # Create a container frame to hold both the Entry and the magnifier icon.
        entry_frame = ttk.Frame(search_frame)
        entry_frame.grid(row=0, column=1, padx=(0, 10), pady=5, sticky="ew")
        entry_frame.columnconfigure(0, weight=1)  # Let the Entry expand

        self.search_var = tk.StringVar()
        self.search_var.trace("w", lambda *args: self.update_treeview())

        # Create the search Entry inside the container frame.
        s_entry = ttk.Entry(entry_frame, textvariable=self.search_var,
                            width=50, bootstyle="primary", font=("Helvetica", 12))
        s_entry.grid(row=0, column=0, sticky="ew")

        # Load the magnifier icon (ensure the file exists in the icons folder)
        self.search_icon = tk.PhotoImage(file="icons/search.png")
        # Create a label to hold the magnifier icon and place it to the right of the entry.
        icon_label = ttk.Label(entry_frame, image=self.search_icon)
        icon_label.image = self.search_icon  # Keep a reference to prevent GC.
        icon_label.grid(row=0, column=1, padx=(5, 0))

        # ------------------- TREE FRAME -------------------
        tree_frame = ttk.Frame(main_frame)
        tree_frame.grid(row=4, column=0, sticky="nsew", padx=5, pady=10)
        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)
        cols = ("Manager", "Cabin", "Guest Name", "Dish", "Pax", "Allergy",
                "Requests", "Time Slot", "Galley Section", "Standing Order")
        self.tree = ttk.Treeview(tree_frame, columns=cols, show="headings",
                                 selectmode="browse", style="primary")
        self.tree.grid(row=0, column=0, sticky="nsew")
        for col in cols:
            self.tree.heading(col, text=col.upper(), command=lambda c=col: self.sort_column(c, True))
            self.tree.column(col, anchor="center", width=120)
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        vsb.grid(row=0, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=vsb.set)
        hsb = ttk.Scrollbar(tree_frame, orient="horizontal", command=self.tree.xview)
        hsb.grid(row=1, column=0, sticky="ew")
        self.tree.configure(xscrollcommand=hsb.set)

        # ------------------- CONTEXT MENU -------------------
        self.context_menu = tk.Menu(self, tearoff=0)
        self.context_menu.add_command(label="Edit", command=self.on_edit_order)
        self.context_menu.add_command(label="Remove", command=self.on_remove_order)
        self.tree.bind("<Delete>", self.on_remove_order)
        self.tree.bind("<Return>", self.on_double_click)
        self.tree.bind("<Button-3>", self.on_tree_right_click)
        self.tree.bind("<Double-1>", self.on_double_click)

        # Load data
        self.refresh_orders()

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

        # 1. Validate occupant-level fields if not locked
        if not self.occupant_locked:
            cabin = self.cabin_number_var.get().strip().upper()
            px = self.pax_var.get().strip()
            ts = self.timeslot_var.get().strip().upper()

            # Validate occupant fields
            valid = True
            if not cabin:
                messagebox.showwarning("Validation", "Cabin # required before adding a dish.")
                valid = False
            elif not px.isdigit() or int(px) < 1:
                messagebox.showwarning("Validation", "Pax must be a positive integer before adding a dish.")
                valid = False
            elif not ts:
                messagebox.showwarning("Validation", "Time slot required before adding a dish.")
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

        # 2. Validate dish-level fields
        dish = self.dish_var.get().strip().upper()
        reqs = self.special_requests_var.get().strip().upper()
        galley = self.galley_section_var.get().strip().upper()

        if not dish:
            messagebox.showwarning("Validation", "Dish is required before adding.")

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
            return

        # 3. Add valid dish to temp list
        self.temp_dishes.append((dish, reqs, galley))

        # 4. Clear dish fields
        self.dish_var.set("")
        self.special_requests_var.set("")
        self.galley_section_var.set(GALLEY_SECTIONS[0])

        messagebox.showinfo(
            "Dish Added",
            f"Dish '{dish}' has been added. You can enter another dish, or click 'Save to Sheet' to finish."
        )
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
        cabin = self.cabin_number_var.get().strip().upper()  # Ensure proper format
        logging.debug(f"Checking cabin: {cabin}")  # Log cabin number for debugging

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
        cabin = self.cabin_number_var.get().strip().upper()
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
                        if note.strip().lower() != "none":
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

    def validate_and_save(self):
        # Check if there is a new unsaved dish in the entry fields
        dish = self.dish_var.get().strip().upper()
        reqs = self.special_requests_var.get().strip().upper()
        galley = self.galley_section_var.get().strip().upper()


        if dish:
            # If a new dish exists but wasn't added, add it to temp_dishes
            cabin = self.cabin_number_var.get().strip().upper()
            px = self.pax_var.get().strip()
            ts = self.timeslot_var.get().strip().upper()

            # Minimal occupant-level checks
            if not cabin:
                messagebox.showwarning("Validation", "Cabin # required before saving.")
                return
            if not px.isdigit() or int(px) < 1:
                messagebox.showwarning("Validation", "Pax must be a positive integer before saving.")
                return
            if not ts:
                messagebox.showwarning("Validation", "Time slot required before saving.")
                return

            # Lock the occupant-level fields if not already locked
            if not self.occupant_locked:
                self.occupant_locked = True
                self.cabin_number_entry.config(state='disabled')
                self.pax_spinbox.config(state='disabled')
                self.timeslot_dropdown.config(state='disabled')
                self.standing_order_check.config(state='disabled')
                self.selected_allergies_listbox.config(state='disabled')
                self.allergy_combobox.config(state='disabled')
                self.add_allergy_button.config(state='disabled')

            # Add the current dish to the temp_dishes list
            self.temp_dishes.append((dish, reqs, galley))
            self.dish_var.set("")
            self.special_requests_var.set("")
            # If you prefer “DINNER” or the first item:
            # self.galley_section_var.set("DINNER")
            self.galley_section_var.set(GALLEY_SECTIONS[0])

        # If occupant is locked and we have multiple dishes, finalize all dishes
        if self.occupant_locked and self.temp_dishes:
            self.multi_dish_finalize()
            return

        # SINGLE-DISH logic (if no temp_dishes exist):
        cabin = self.cabin_number_var.get().strip().upper()
        px = self.pax_var.get().strip()
        ts = self.timeslot_var.get().strip().upper()
        stand = "YES" if self.standing_order_var.get() else "NO"

        # allergies
        arr = self.selected_allergies_listbox.get(0, tk.END)
        allergy = ", ".join(arr).upper() if arr else "NONE"

        guest = self.guest_name_var.get().strip()

        # Minimal validation for single-dish fields
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

        # Add the single dish to the tree
        order = (self.manager, cabin, guest, dish, px, allergy, reqs, ts, galley, stand, False)
        self.all_orders.append(order)
        self.tree.insert('', tk.END, values=order[:10])

        messagebox.showinfo("Order Added", f"Single-dish order for Cabin {cabin} added.")
        self.unsaved_data = True

        # -------------------------------------------------
        # Now UNLOCK occupant-level fields for a new occupant
        # -------------------------------------------------
        self.occupant_locked = False
        self.cabin_number_entry.config(state="normal")
        self.pax_spinbox.config(state="normal")
        self.timeslot_dropdown.config(state="readonly")
        self.standing_order_check.config(state="normal")
        self.selected_allergies_listbox.config(state="normal")
        self.allergy_combobox.config(state="readonly")
        self.add_allergy_button.config(state="normal")

        # Clear occupant-level fields
        self.cabin_number_var.set("")
        self.guest_name_var.set("")
        self.pax_var.set("1")
        self.timeslot_var.set("DINNER")
        self.standing_order_var.set(False)
        self.selected_allergies_listbox.delete(0, tk.END)
        self.allergy_combobox.set("None")


        # Clear dish fields
        self.dish_var.set("")
        self.special_requests_var.set("")
        self.galley_section_var.set(GALLEY_SECTIONS[0])


        #
        # IMPORTANT: REMOVE/COMMENT the call to `self.clear_order_fields()`
        # because it might RE-DISABLE occupant fields again.
        #
        # self.clear_order_fields()  # <--- comment this out or remove it
        self.validate_buttons()


    def multi_dish_finalize(self):
        cabin = self.cabin_number_var.get().strip().upper()
        px = self.pax_var.get().strip()
        guest = self.guest_name_var.get().strip()
        ts = self.timeslot_var.get().strip().upper()
        stand = "YES" if self.standing_order_var.get() else "NO"

        # allergies
        arr = self.selected_allergies_listbox.get(0, tk.END)
        allergy = ", ".join(arr).upper() if arr else "NONE"

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
            self.tree.insert('', tk.END, values=order[:10])
            inserted_count += 1

        # Show a summary message
        messagebox.showinfo(
            "Multi-dish Order Added",
            f"{inserted_count} dish(es) added for Cabin {cabin}."
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
        sd = get_next_day_date()
        rows = self.db_manager.get_preorders(sd, self.venue_id)

        # Clear old tree
        for it in self.tree.get_children():
            self.tree.delete(it)
        self.all_orders.clear()

        for r in rows:
            manager = r["manager"] or ""
            cabin = r["cabin_number"] or ""
            dish = r["dish"] or ""
            px = str(r["pax"] or "1")
            al = r["allergy_notes"] or "NONE"
            req = r["special_requests"] or ""
            ts = r["service_time_slot"] or ""
            gal = r["galley_section"] or ""
            st = r["standing_order"] or "NO"
            # occupant-level
            guest = r["guest_name"] if "guest_name" in r.keys() else ""

            # from_db=True
            tup = (manager, cabin, guest, dish, px, al, req, ts, gal, st, True)
            self.all_orders.append(tup)
            self.tree.insert('', tk.END, values=tup[:10])

        messagebox.showinfo("Refreshed", f"Loaded orders for {sd} from DB.")
        self.unsaved_data = False

    # ---------------------------- COMMIT TO DB ----------------------------
    def commit_to_db(self):
        if not self.tree.get_children():
            messagebox.showinfo("No Data", "No orders in the tree.")
            return

        sd = self.service_date_var.get().strip() or get_next_day_date()
        committed = 0
        new_list = []

        for o in self.all_orders:
            # (manager, cabin, guest, dish, px, al, rq, ts, gal, st, from_db)
            from_db = o[10]
            if not from_db:
                manager, cabin, guest, dish, px, al, rq, tslot, gsect, st = o[:10]
                if not cabin:
                    continue

                # IMPORTANT: include 'guest_name'
                pre = {
                    'manager': manager,
                    'cabin_number': cabin,
                    'guest_name': guest,   # occupant-level field
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
                    new_list.append((manager, cabin, guest, dish, px, al,
                                     rq, tslot, gsect, st, True))
                else:
                    new_list.append(o)
            else:
                new_list.append(o)

        if committed > 0:
            messagebox.showinfo("Success", f"{committed} orders committed to DB.")
            # Clear tree
            for it in self.tree.get_children():
                self.tree.delete(it)
            self.all_orders = new_list
            for nt in new_list:
                self.tree.insert('', tk.END, values=nt[:10])
            self.unsaved_data = False
        else:
            messagebox.showerror("Commit Failed", "No new orders committed.")
        self.validate_buttons()


    # ---------------------------- SEARCH / UPDATE TREEVIEW ----------------------------
    def update_treeview(self, *args):
        q = self.search_var.get().lower()
        for it in self.tree.get_children():
            self.tree.delete(it)

        if not q:
            for o in self.all_orders:
                self.tree.insert('', tk.END, values=o[:10])
            return

        filtered = []
        for o in self.all_orders:
            # check first 10 fields
            if any(q in str(f).lower() for f in o[:10]):
                filtered.append(o)

        for t in filtered:
            self.tree.insert('', tk.END, values=t[:10])

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
            values=GALLEY_SECTIONS, state="readonly", width=18
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
                return
            if not new_dish:
                messagebox.showwarning("Validation Error", "Dish cannot be empty.")
                return
            if not new_pax.isdigit() or int(new_pax) < 1:
                messagebox.showwarning("Validation Error", "Pax must be a positive integer.")
                return
            if not new_time:
                messagebox.showwarning("Validation Error", "Time slot is required.")
                return
            if not new_galley:
                messagebox.showwarning("Validation Error", "Galley section is required.")
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
            service_date = get_next_day_date()  # or your actual date logic
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
        messagebox.showinfo(
            "Removed",
            f"Order for Cabin '{cabin_number_for_order}', Guest '{guest_name_for_order}' removed."
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

    def show_order_details_bck(self, vals):
        fields = ["Manager","Cabin","Guest Name","Dish","Pax","Allergies",
                  "Requests","Time Slot","Galley Section","Standing Order"]
        pop = tk.Toplevel(self)
        pop.title(f"Order Details - Cabin {vals[1]}")
        pop.geometry("500x600")
        pop.resizable(True, True)
        pop.iconbitmap('icons/icon_app.ico')


        c = tk.Canvas(pop)
        vsb = ttk.Scrollbar(pop, orient="vertical", command=c.yview)
        frm = ttk.Frame(c, padding=20)
        frm.bind("<Configure>", lambda e: c.configure(scrollregion=c.bbox("all")))
        c.create_window((0,0), window=frm, anchor='nw')
        c.configure(yscrollcommand=vsb.set)
        c.pack(side='left', fill='both', expand=True)
        vsb.pack(side='right', fill='y')


        ttk.Label(frm, text=f"Order Details for Cabin {vals[1]}",
                  font=("Helvetica",16,"bold")).pack(pady=(0,20))

        txtacc = ""
        for f,v in zip(fields, vals):
            lbl = ttk.Label(frm, text=f"{f}: {v}", font=("Helvetica",12),
                            wraplength=450, justify='left')
            lbl.pack(anchor='w', pady=2)
            txtacc += f"{f}: {v}\n"

        closeb = ttk.Button(frm, text="Close", command=pop.destroy, bootstyle=DANGER)
        closeb.pack(pady=10)

        copyb = ttk.Button(frm, text="Copy to Clipboard",
                           command=lambda: self.copy_order_to_clipboard(txtacc),
                           bootstyle=INFO)
        copyb.pack()

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
        messagebox.showinfo("Copied", "Order details copied to clipboard.")



    # ---------------------------- LOGOUT ----------------------------
    def logout(self):
        self.manager = None
        self.venue_id = None
        self.venue_name = None
        self.allergies.clear()
        self.all_orders.clear()
        self.unsaved_data = False
        logging.info("Manager logged out.")
        self.show_login_screen()

    # ---------------------------- SHOW TODAY'S ORDERS ----------------------------
    def show_todays_orders(self):
        """
        Open a new Toplevel window that shows today's orders in a read-only preview.
        The user can filter by venue and do a dynamic search.
        Double-click on an order to see its details in a popup with bold labels.
        """
        # 1) Create a Toplevel window
        preview_window = tk.Toplevel(self)
        preview_window.title("Today's Orders Preview")
        preview_window.geometry("1100x600")
        preview_window.resizable(True, True)
        preview_window.iconbitmap('icons/icon_app.ico')

        main_frame = ttk.Frame(preview_window, padding=10)
        main_frame.pack(fill="both", expand=True)

        # Configure row/column expansion
        main_frame.rowconfigure(1, weight=1)  # The Treeview row expands
        main_frame.columnconfigure(0, weight=1)

        # ----------------------------- FILTER FRAME -----------------------------
        filter_frame = ttk.Labelframe(main_frame, text="Filter and Search", padding=10, bootstyle="info")
        filter_frame.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        filter_frame.columnconfigure(1, weight=1)

        # Venue label
        ttk.Label(filter_frame, text="Venue:", font=("Helvetica", 12, "bold")).grid(
            row=0, column=0, padx=(0, 5), sticky="e"
        )

        # Get all venues + an "All Venues" option
        venues = self.db_manager.get_venues()  # returns list of rows with ["id"] and ["name"]
        venue_map = {v["name"]: v["id"] for v in venues}
        venue_names = ["All Venues"] + [v["name"] for v in venues]

        selected_venue_var = tk.StringVar(value=venue_names[0])
        venue_combo = ttk.Combobox(
            filter_frame,
            textvariable=selected_venue_var,
            values=venue_names,
            state="readonly",
            width=25
        )
        venue_combo.grid(row=0, column=1, padx=(0, 20), sticky="w")

        # Search label
        search_label = ttk.Label(filter_frame, text="Search:", font=("Helvetica", 12, "bold"))
        search_label.grid(row=0, column=2, padx=(0, 5), sticky="e")

        search_var = tk.StringVar()
        search_box = ttk.Entry(filter_frame, textvariable=search_var, width=30)
        search_box.grid(row=0, column=3, padx=(0, 5), sticky="ew")

        # ----------------------------- TREE FRAME -----------------------------
        tree_frame = ttk.Labelframe(main_frame, text="Today's Orders", padding=10, bootstyle="primary")
        tree_frame.grid(row=1, column=0, sticky="nsew")
        tree_frame.rowconfigure(0, weight=1)
        tree_frame.columnconfigure(0, weight=1)

        columns = (
            "Manager",
            "Cabin",
            "Guest Name",
            "Dish",
            "Pax",
            "Allergy",
            "Requests",
            "Time Slot",
            "Galley Section",
            "Standing Order"
        )
        preview_tree = ttk.Treeview(
            tree_frame, columns=columns, show="headings", selectmode="none"
        )
        preview_tree.grid(row=0, column=0, sticky="nsew")

        # Define headings & columns
        for col in columns:
            preview_tree.heading(col, text=col)
            preview_tree.column(col, anchor="center", width=110)

        # Scrollbars
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=preview_tree.yview)
        vsb.grid(row=0, column=1, sticky="ns")
        preview_tree.configure(yscrollcommand=vsb.set)

        hsb = ttk.Scrollbar(tree_frame, orient="horizontal", command=preview_tree.xview)
        hsb.grid(row=1, column=0, sticky="ew")
        preview_tree.configure(xscrollcommand=hsb.set)

        # ----------------------------- BUTTON FRAME -----------------------------
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=2, column=0, sticky="ew", pady=(10, 0))

        print_btn = ttk.Button(button_frame, text="Print", command=lambda: print_orders(), bootstyle="secondary")
        print_btn.pack(side="left", padx=5)

        close_btn = ttk.Button(button_frame, text="Close", command=preview_window.destroy, bootstyle="danger")
        close_btn.pack(side="right", padx=5)

        # ----------------------------- DB LOADING FUNCTIONS -----------------------------
        def load_todays_orders():
            """
            Load today's orders from DB based on selected venue (or all).
            Then apply search filter.
            """
            # Clear the treeview
            for item in preview_tree.get_children():
                preview_tree.delete(item)

            today_str = datetime.now().strftime("%Y-%m-%d")
            selected_venue_name = selected_venue_var.get()

            with self.db_manager.get_connection() as conn:
                cur = conn.cursor()
                if selected_venue_name == "All Venues":
                    cur.execute("""
                        SELECT manager,
                               cabin_number,
                               guest_name,
                               dish,
                               pax,
                               allergy_notes,
                               special_requests,
                               service_time_slot,
                               galley_section,
                               standing_order
                        FROM preorders
                        WHERE service_date = ?
                        ORDER BY service_time_slot, galley_section
                    """, (today_str,))
                else:
                    venue_id = venue_map[selected_venue_name]
                    cur.execute("""
                        SELECT manager,
                               cabin_number,
                               guest_name,
                               dish,
                               pax,
                               allergy_notes,
                               special_requests,
                               service_time_slot,
                               galley_section,
                               standing_order
                        FROM preorders
                        WHERE service_date = ?
                          AND venue_id = ?
                        ORDER BY service_time_slot, galley_section
                    """, (today_str, venue_id))
                rows = cur.fetchall()

            # Turn rows into a list of tuples
            data_list = []
            for row in rows:
                manager = row["manager"] or ""
                cabin = row["cabin_number"] or ""
                guest = row["guest_name"] or ""
                dish = row["dish"] or ""
                pax = str(row["pax"]) if row["pax"] else "1"
                allergy = row["allergy_notes"] or "None"
                reqs = row["special_requests"] or ""
                timeslot = row["service_time_slot"] or ""
                galley = row["galley_section"] or ""
                stand = row["standing_order"] or "NO"
                data_list.append((manager, cabin, guest, dish, pax, allergy, reqs, timeslot, galley, stand))

            # Apply search filter
            query = search_var.get().strip().lower()
            if query:
                filtered = []
                for item_tuple in data_list:
                    if any(query in str(field).lower() for field in item_tuple):
                        filtered.append(item_tuple)
                data_list = filtered

            # Insert into preview_tree
            for row_data in data_list:
                preview_tree.insert("", "end", values=row_data)

        def on_venue_changed(event=None):
            load_todays_orders()

        def on_search_changed(*args):
            load_todays_orders()

        venue_combo.bind("<<ComboboxSelected>>", on_venue_changed)
        search_var.trace_add("write", on_search_changed)

        # ----------------------------- PRINT FUNCTION -----------------------------
        def print_orders():
            """
            Opens a preview window showing today's orders in a formatted,
            column-aligned layout. The user can then confirm to print or cancel.
            """

            # 1) Collect orders from preview_tree
            items = preview_tree.get_children()
            if not items:
                messagebox.showinfo("No Data", "No orders to print.")
                return

            # 2) Build a list of lines, using alignment or spacing for columns
            #    We'll define some columns: (title, width)
            columns = [
                ("Manager", 12),
                ("Cabin", 8),
                ("Guest", 18),
                ("Dish", 18),
                ("Pax", 3),
                ("Allergy", 12),
                ("Requests", 12),
                ("Time Slot", 10),
                ("Galley", 8),
                ("Stand", 5),
            ]

            # Prepare the lines
            lines = []
            today_str = datetime.now().strftime('%Y-%m-%d')
            lines.append(f"Today's Orders - {today_str} (Venue: {selected_venue_var.get()})")
            lines.append("=" * 100)

            # 2a) Header row (column titles)
            header_row = []
            for (title, width) in columns:
                # Left-align, truncate if necessary
                # e.g. f"{title:<{width}}"
                header_row.append(f"{title:<{width}}")
            lines.append(" ".join(header_row))

            lines.append("-" * 100)

            # 2b) Data rows
            for item_id in items:
                vals = preview_tree.item(item_id, "values")
                # Suppose the order of columns in 'vals' matches your columns above:
                # Manager=vals[0], Cabin=vals[1], Guest=vals[2], Dish=vals[3], ...
                row_str_parts = []
                for (col_val, (col_title, width)) in zip(vals, columns):
                    text_val = str(col_val)[:width]  # truncate if needed
                    row_str_parts.append(f"{text_val:<{width}}")
                lines.append(" ".join(row_str_parts))

            lines.append("=" * 100)
            final_text = "\n".join(lines)

            # 3) Show a Toplevel window with a Text widget for preview
            preview_win = tk.Toplevel(preview_window)  # or self, if you prefer
            preview_win.title("Print Preview")
            preview_win.geometry("800x500")
            preview_win.resizable(True, True)

            # A text widget to display the preview
            text_widget = tk.Text(preview_win, wrap="none", font=("Courier New", 10))
            text_widget.pack(fill="both", expand=True)

            # Insert the lines into the text widget
            text_widget.insert("1.0", final_text)
            text_widget.configure(state="disabled")  # make read-only

            # Scrollbars
            x_scroll = ttk.Scrollbar(preview_win, orient="horizontal", command=text_widget.xview)
            x_scroll.pack(side="bottom", fill="x")
            y_scroll = ttk.Scrollbar(preview_win, orient="vertical", command=text_widget.yview)
            y_scroll.pack(side="right", fill="y")
            text_widget.configure(xscrollcommand=x_scroll.set, yscrollcommand=y_scroll.set)

            # 4) Frame with "Print" and "Cancel" buttons
            btn_frame = ttk.Frame(preview_win)
            btn_frame.pack(fill="x", pady=5)

            def confirm_print():
                """
                If the user is happy with the preview, send the job to the printer.
                We reuse the same lines to generate a temp file and print.
                """
                import tempfile, os

                # Write lines to temp file
                with tempfile.NamedTemporaryFile("w", delete=False, suffix=".txt") as tf:
                    tf_name = tf.name
                    tf.write(final_text)

                # Attempt to print
                try:
                    if os.name == "nt":  # Windows
                        os.startfile(tf_name, "print")
                    else:  # Linux/Mac -> lpr
                        os.system(f"lpr '{tf_name}'")

                    messagebox.showinfo("Printing", "Printing command sent to default printer.", parent=preview_win)
                except Exception as e:
                    messagebox.showerror("Print Error", f"Could not print the file:\n{e}", parent=preview_win)

            # Buttons
            print_btn = ttk.Button(btn_frame, text="Print", bootstyle="success", command=confirm_print)
            print_btn.pack(side="left", padx=10)

            close_btn = ttk.Button(btn_frame, text="Close Preview", bootstyle="danger", command=preview_win.destroy)
            close_btn.pack(side="right", padx=10)

        # ----------------------------- DOUBLE-CLICK EVENT -----------------------------
        def on_preview_double_click(event):
            row_id = preview_tree.identify_row(event.y)
            if not row_id:
                return
            vals = preview_tree.item(row_id, "values")
            if not vals:
                return
            show_preview_order_details(vals)

        preview_tree.bind("<Double-1>", on_preview_double_click)

        # ----------------------------- ORDER DETAILS POPUP -----------------------------
        def show_preview_order_details(vals):
            """
            Display a popup window with the order details in two columns.
            The left column has larger, bold text (title), and the right column
            has slightly smaller text (value). All styling is done inline.

            vals is a tuple of 10 fields in the order:
              (Manager, Cabin, Guest Name, Dish, Pax, Allergy,
               Requests, Time Slot, Galley, Standing Order)
            """
            # Create the Toplevel window
            detail_win = tk.Toplevel(preview_window)
            detail_win.title(f"Order Details - Cabin {vals[1]}")
            detail_win.geometry("520x600")
            detail_win.resizable(True, True)

            # Set a white background for the entire popup
            detail_win.configure(bg="#ffffff")

            # A title header label at the top of the window
            header_label = tk.Label(
                detail_win,
                text="Order Information",
                font=("Helvetica", 16, "bold"),
                fg="#2c3e50",
                bg="#ffffff"  # match window bg
            )
            header_label.pack(pady=(15, 10))

            # A container frame for the details, with a slight border or relief
            # so it stands out against the background
            info_frame = tk.LabelFrame(
                detail_win,
                text="Detailed Information",
                bg="#ffffff",
                fg="#2c3e50",  # color for the labelframe title
                bd=2,
                font=("Helvetica", 12, "bold"),
                relief="groove",
                padx=20,
                pady=15
            )
            info_frame.pack(fill="both", expand=True, padx=20, pady=10)

            fields = [
                "Manager", "Cabin", "Guest Name", "Dish", "Pax",
                "Allergy", "Requests", "Time Slot", "Galley", "Standing Order"
            ]

            # Build a string for copy-to-clipboard
            accumulated_text = ""
            for field, value in zip(fields, vals):
                accumulated_text += f"{field}: {value}\n"

            # Use a grid inside info_frame for field/value pairs
            for i, (field, value) in enumerate(zip(fields, vals)):
                # Left label (field name) in a bigger/bold font
                title_label = tk.Label(
                    info_frame,
                    text=f"{field}:",
                    font=("Helvetica", 12, "bold"),
                    fg="#0d6efd",  # a distinct color for field names (blue-ish)
                    bg="#ffffff",
                    anchor="e"
                )
                title_label.grid(row=i, column=0, sticky="e", padx=(5, 10), pady=8)

                # Right label (field value) in a normal font, slightly smaller
                value_label = tk.Label(
                    info_frame,
                    text=str(value),
                    font=("Helvetica", 12),
                    fg="#495057",
                    bg="#ffffff",
                    wraplength=280,  # wrap text if it’s long
                    justify="left"
                )
                value_label.grid(row=i, column=1, sticky="w", padx=(0, 5), pady=8)

            # Button frame at the bottom for "Copy" and "Close"
            btn_frame = ttk.Frame(detail_win, padding=(10, 10))
            btn_frame.pack(fill="x", pady=(0, 10))

            def copy_details():
                detail_win.clipboard_clear()
                detail_win.clipboard_append(accumulated_text)
                messagebox.showinfo("Copied", "Order details copied to clipboard.", parent=detail_win)

            # "Copy to Clipboard" button
            copy_btn = ttk.Button(
                btn_frame,
                text="Copy to Clipboard",
                command=copy_details,
                bootstyle="secondary"
            )
            copy_btn.pack(side="left", padx=10)

            # "Close" button
            close_btn = ttk.Button(
                btn_frame,
                text="Close",
                command=detail_win.destroy,
                bootstyle="danger"
            )
            close_btn.pack(side="right", padx=10)

        # 8) Initial load
        load_todays_orders()

        # Focus the window
        preview_window.lift()
        preview_window.focus()

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
def get_next_day_date():
    tomorrow = datetime.now().date() + timedelta(days=1)
    return tomorrow.strftime("%Y-%m-%d")


# ----------------------------
# get_next_day_date
# ----------------------------


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

        # Insert sample data if not exist
        cur.execute("SELECT COUNT(*) FROM users")
        if cur.fetchone()[0] == 0:
            # create a sample user
            sample_pw = bcrypt.hashpw("password123".encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            cur.execute("INSERT INTO users (username, password_hash, role) VALUES (?,?,?)",
                        ("manager1", sample_pw, "restaurant"))
            logging.info("Inserted sample user manager1 with password 'password123'.")

        cur.execute("SELECT COUNT(*) FROM venues")


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
