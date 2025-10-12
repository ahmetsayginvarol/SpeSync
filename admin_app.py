import logging
import time
from openpyxl import Workbook
from openpyxl.styles import PatternFill, Font, Alignment
from tkinter import messagebox



def load_db_config(config_file="db_config.json"):
    import json, os, sys
    if getattr(sys, "frozen", False):  # running as PyInstaller EXE
        base_dir = os.path.dirname(sys.executable)
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(base_dir, config_file)

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"type": "sqlite"}  # sensible default
# ----------------------------
# Logging Configuration
# ----------------------------
logging.basicConfig(
    filename='admin_app.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# ----------------------------
# Constants
# ----------------------------
ROLES = ["admin", "restaurant", "galley"]
PASSWORD_MIN_LENGTH = 6  # Example password policy
DEFAULT_ADMIN_USERNAME = "ADMIN"
DEFAULT_ADMIN_PASSWORD = "123456"

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
            app_dir = Path(sys.executable).parent.parent
        else:
            # Application is running as a script
            app_dir = Path(__file__).resolve().parent

        db_path = app_dir / "orders.db"
        logging.info(f"Database path set to: {db_path}")
        return db_path
    except Exception as e:
        logging.error(f"Error determining database path: {e}")
        raise

# ----------------------------
# Database Manager Class
# ----------------------------
import tkinter as tk
from tkinter import ttk



#


# ----------------------------
# AdminLoginFrame: Prompt for Admin Password
# ----------------------------
import sys
from pathlib import Path
import sqlite3
import logging
import bcrypt

class DatabaseManager:
    def __init__(self, config):
        """
        config: dict loaded from db_config.json, e.g.
          {"type":"sqlite"}
          or
          {"type":"mysql","host":"...","port":3306,"database":"...","user":"...","password":"..."}
        """

        self.config = config or {"type": "sqlite"}
        self.backend = self.config.get("type", "sqlite")
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

    def _get_sqlite_db_path(self):
        if getattr(sys, 'frozen', False):
            app_dir = Path(sys.executable).parent
        else:
            app_dir = Path(__file__).resolve().parent.parent
        return str(app_dir / "orders.db")

    def _param(self):
        return "?" if self.backend == "sqlite" else "%s"

    def _pk(self):
        # Primary key syntax
        return "INTEGER PRIMARY KEY AUTOINCREMENT" if self.backend == "sqlite" else "INT AUTO_INCREMENT PRIMARY KEY"

    # DatabaseManager.get_connection()
    def get_connection(self):
        if self.backend == "sqlite":
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            return conn
        else:
            try:
                import pymysql
                return pymysql.connect(
                    host=self.mysql_settings["host"],
                    port=self.mysql_settings["port"],
                    user=self.mysql_settings["user"],
                    password=self.mysql_settings["password"],
                    database=self.mysql_settings["database"],
                    charset="utf8mb4",
                    autocommit=True,
                    cursorclass=pymysql.cursors.Cursor,
                )
            except Exception:
                # fallback to mysql.connector (pure mode)
                import mysql.connector
                return mysql.connector.connect(
                    **self.mysql_settings,
                    use_pure=True,  # avoid C extension issues
                    auth_plugin='mysql_native_password'  # helpful on some servers
                )

    def setup_database(self):
        """
        Ensures the database contains all necessary tables.
        Adds voyage support: voyages table, preorders.voyage_id, app_config keys.
        """
        from datetime import datetime

        conn = None
        cur = None
        try:
            conn = self.get_connection()
            if conn is None:
                return

            cur = conn.cursor()

            pk = (
                "INTEGER PRIMARY KEY AUTOINCREMENT"
                if self.backend == "sqlite"
                else "INT AUTO_INCREMENT PRIMARY KEY"
            )

            # USERS
            cur.execute(f"""
                CREATE TABLE IF NOT EXISTS users (
                    id {pk},
                    username VARCHAR(64) UNIQUE NOT NULL,
                    password_hash VARCHAR(128) NOT NULL,
                    role VARCHAR(32) NOT NULL
                )
            """)

            # VENUES
            cur.execute(f"""
                CREATE TABLE IF NOT EXISTS venues (
                    id {pk},
                    name VARCHAR(64) UNIQUE NOT NULL,
                    breakfast_available TINYINT DEFAULT 0,
                    lunch_available TINYINT DEFAULT 0,
                    dinner_available TINYINT DEFAULT 1
                )
            """)

            # ALLERGIES
            cur.execute(f"""
                CREATE TABLE IF NOT EXISTS allergies (
                    id {pk},
                    name VARCHAR(64) UNIQUE NOT NULL
                )
            """)

            # --- Seed base allergies (ALL CAPS) ---
            base_allergies = [
                "GLUTEN",
                "DAIRY",
                "TREE NUTS",
                "PEANUTS",
                "EGGS",
                "SHELLFISH",
                "SOY",
                "LACTOSE"
            ]

            # Param style: ? for SQLite, %s for MySQL
            p = "?" if self.backend == "sqlite" else "%s"

            # Build placeholders for multi-row insert
            placeholders = ", ".join([f"({p})" for _ in base_allergies])

            # Choose dialect-specific insert
            if self.backend == "sqlite":
                cur.execute(
                    f"INSERT OR IGNORE INTO allergies (name) VALUES {placeholders}",
                    base_allergies
                )
            else:  # MySQL
                cur.execute(
                    f"INSERT IGNORE INTO allergies (name) VALUES {placeholders}",
                    base_allergies
                )

            # GUESTS
            cur.execute(f"""
                CREATE TABLE IF NOT EXISTS guests (
                    id {pk},
                    cabin_number VARCHAR(16) NOT NULL,
                    first_name VARCHAR(64) NOT NULL,
                    last_name  VARCHAR(64) NOT NULL,
                    voyage_id VARCHAR(64) NOT NULL,
                    UNIQUE(cabin_number, first_name, last_name, voyage_id)
                )
            """)

            # PREORDERS (base)
            cur.execute(f"""
                CREATE TABLE IF NOT EXISTS preorders (
                    id {pk},
                    manager           VARCHAR(64)  NOT NULL,
                    cabin_number      VARCHAR(16)  NOT NULL,
                    guest_name        VARCHAR(64)  NOT NULL,
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
                    chef_remark       VARCHAR(255) NOT NULL DEFAULT '',
                    FOREIGN KEY(venue_id) REFERENCES venues(id)
                )
            """)

            # APP_CONFIG (key-value)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS app_config (
                    `key`   VARCHAR(64) PRIMARY KEY,
                    `value` VARCHAR(255) NOT NULL
                )
            """)

            # Default server timezone
            if self.backend == "sqlite":
                cur.execute("""
                    INSERT OR IGNORE INTO app_config (`key`, `value`)
                    VALUES ('server_time_zone', 'UTC')
                """)
            else:
                cur.execute("""
                    INSERT IGNORE INTO app_config (`key`, `value`)
                    VALUES ('server_time_zone', 'UTC')
                """)

            # IMPORT_MAPPINGS
            if self.backend == "sqlite":
                cur.execute(f"""
                    CREATE TABLE IF NOT EXISTS import_mappings (
                        id             INT PRIMARY KEY CHECK (id = 1),
                        cabin_col      VARCHAR(8) NOT NULL,
                        last_name_col  VARCHAR(8) NOT NULL,
                        first_name_col VARCHAR(8) NOT NULL
                    )
                """)
            else:
                cur.execute(f"""
                    CREATE TABLE IF NOT EXISTS import_mappings (
                        id             INT PRIMARY KEY,
                        cabin_col      VARCHAR(8) NOT NULL,
                        last_name_col  VARCHAR(8) NOT NULL,
                        first_name_col VARCHAR(8) NOT NULL
                    )
                """)

            # Default row example they used earlier (keep behavior)
            if self.backend == "sqlite":
                cur.execute("""
                    INSERT OR IGNORE INTO app_config (`key`, `value`)
                    VALUES ('last_standing_copy', '')
                """)
            else:
                cur.execute("""
                    INSERT IGNORE INTO app_config (`key`, `value`)
                    VALUES ('last_standing_copy', '')
                """)

            # ───────────────────────────────
            # VOYAGE SUPPORT (NEW)
            # ───────────────────────────────

            # 1) VOYAGES table
            cur.execute(f"""
                CREATE TABLE IF NOT EXISTS voyages (
                    id {pk},
                    code VARCHAR(32) UNIQUE NOT NULL,
                    start_date VARCHAR(16),
                    end_date   VARCHAR(16),
                    notes      VARCHAR(255)
                )
            """)

            # 2) Add voyage_id to preorders (if missing)
            try:
                cur.execute("ALTER TABLE preorders ADD COLUMN voyage_id INT")
            except Exception:
                # column already exists or backend-specific no-op
                pass

            # 3) Seed config keys for current voyage
            if self.backend == "sqlite":
                cur.execute("""
                    INSERT OR IGNORE INTO app_config (`key`,`value`) VALUES ('current_voyage_code','BOOTSTRAP')
                """)
                cur.execute("""
                    INSERT OR IGNORE INTO app_config (`key`,`value`) VALUES ('current_voyage_id','')
                """)
            else:
                cur.execute("""
                    INSERT IGNORE INTO app_config (`key`,`value`) VALUES ('current_voyage_code','BOOTSTRAP')
                """)
                cur.execute("""
                    INSERT IGNORE INTO app_config (`key`,`value`) VALUES ('current_voyage_id','')
                """)

            # 4) Ensure BOOTSTRAP voyage exists and get its id
            if self.backend == "sqlite":
                cur.execute("INSERT OR IGNORE INTO voyages (code, start_date) VALUES ('BOOTSTRAP', ?)",
                            (datetime.now().date().isoformat(),))
                cur.execute("SELECT id FROM voyages WHERE code='BOOTSTRAP'")
            else:
                cur.execute("INSERT IGNORE INTO voyages (code, start_date) VALUES ('BOOTSTRAP', %s)",
                            (datetime.now().date().isoformat(),))
                cur.execute("SELECT id FROM voyages WHERE code=%s", ('BOOTSTRAP',))
            row = cur.fetchone()
            bootstrap_voyage_id = row[0] if row else None

            # 5) Backfill existing preorder rows without voyage_id
            if bootstrap_voyage_id is not None:
                try:
                    # Works in both backends: NULL or 0 → set to bootstrap
                    cur.execute(
                        "UPDATE preorders SET voyage_id = %s WHERE voyage_id IS NULL OR voyage_id = 0"
                        if self.backend != "sqlite"
                        else "UPDATE preorders SET voyage_id = ? WHERE voyage_id IS NULL OR voyage_id = 0",
                        (bootstrap_voyage_id,)
                    )
                except Exception:
                    pass

                # Ensure app_config current_voyage_id populated if empty
                if self.backend == "sqlite":
                    cur.execute("SELECT `value` FROM app_config WHERE `key`='current_voyage_id'")
                else:
                    cur.execute("SELECT `value` FROM app_config WHERE `key`=%s", ('current_voyage_id',))
                vrow = cur.fetchone()
                needs_set = (not vrow) or (not (vrow[0] or "").strip())
                if needs_set:
                    if self.backend == "sqlite":
                        cur.execute("UPDATE app_config SET `value`=? WHERE `key`='current_voyage_id'",
                                    (str(bootstrap_voyage_id),))
                    else:
                        cur.execute("UPDATE app_config SET `value`=%s WHERE `key`=%s",
                                    (str(bootstrap_voyage_id), 'current_voyage_id'))

            # 6) Indexes to speed common filters
            # (IF NOT EXISTS is supported by SQLite; MySQL 8+ supports it—otherwise ignore errors)
            try:
                cur.execute(
                    "CREATE INDEX IF NOT EXISTS idx_preorders_voyage_date ON preorders(voyage_id, service_date)")
            except Exception:
                try:
                    cur.execute("CREATE INDEX idx_preorders_voyage_date ON preorders(voyage_id, service_date)")
                except Exception:
                    pass
            try:
                cur.execute("CREATE INDEX IF NOT EXISTS idx_preorders_voyage_venue ON preorders(voyage_id, venue_id)")
            except Exception:
                try:
                    cur.execute("CREATE INDEX idx_preorders_voyage_venue ON preorders(voyage_id, venue_id)")
                except Exception:
                    pass

            conn.commit()

        except Exception as e:
            logging.error(f"Error setting up the database: {e}", exc_info=True)
        finally:
            if cur:
                try:
                    cur.close()
                except:
                    pass
            if conn:
                try:
                    conn.close()
                except:
                    pass


    def _alter_column_type_if_exists(self, table, column, new_type):
        conn = self.get_connection()
        cur = conn.cursor()
        try:
            if self.backend == "sqlite":
                # SQLite lacks easy ALTER TYPE; do best-effort copy if needed.
                cur.execute(f"PRAGMA table_info({table})")
                cols = [r[1] for r in cur.fetchall()]
                if column not in cols:
                    cur.execute(f"ALTER TABLE {table} ADD COLUMN {column} {new_type}")
                # Optional: migration of data types is skipped since SQLite is permissive with types.
            else:
                # MySQL: convert type in-place if column exists and differs
                cur.execute("""
                    SELECT DATA_TYPE, CHARACTER_MAXIMUM_LENGTH
                    FROM information_schema.COLUMNS
                    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME=%s AND COLUMN_NAME=%s
                """, (table, column))
                row = cur.fetchone()
                if row:
                    cur.execute(f"ALTER TABLE `{table}` MODIFY `{column}` {new_type}")
            conn.commit()
        finally:
            try:
                cur.close()
            except:
                pass
            try:
                conn.close()
            except:
                pass

    def _add_column_if_not_exists(self, _cur_unused, table, column, col_type):
        """
        Add a column to `table` if it doesn't already exist.
        Works for both SQLite and MySQL.
        Uses a fresh cursor/connection to avoid 'Cursor closed' issues.
        """
        conn = None
        cur = None
        try:
            conn = self.get_connection()
            cur = conn.cursor()

            if self.backend == "sqlite":
                # PRAGMA returns: cid, name, type, notnull, dflt_value, pk
                cur.execute(f"PRAGMA table_info({table})")
                existing = [row[1] for row in cur.fetchall()]
                if column not in existing:
                    cur.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")
            else:
                # MySQL: check via information_schema (sağlam ve parametrik)
                cur.execute(
                    "SELECT COUNT(*) "
                    "FROM information_schema.COLUMNS "
                    "WHERE TABLE_SCHEMA = DATABASE() "
                    "  AND TABLE_NAME = %s "
                    "  AND COLUMN_NAME = %s",
                    (table, column)
                )
                exists = (cur.fetchone()[0] or 0) > 0
                if not exists:
                    cur.execute(f"ALTER TABLE `{table}` ADD COLUMN `{column}` {col_type}")

            conn.commit()
        except Exception as e:
            logging.error(f"_add_column_if_not_exists({table}.{column}): {e}", exc_info=True)
            raise
        finally:
            try:
                cur.close()
            except:
                pass
            try:
                conn.close()
            except:
                pass

    # --- VOYAGE HELPERS (new) ---
    def resolve_or_create_voyage(self, voyage_code: str) -> str:
        """
        Ensure a voyage row exists for the given string code and return that code.
        Uses INSERT OR IGNORE (SQLite) / INSERT IGNORE (MySQL).
        """
        vc = (voyage_code or "").strip()
        if not vc:
            raise ValueError("Voyage code is required.")

        with self.get_connection() as conn:
            cur = conn.cursor()
            if self.backend == "sqlite":
                cur.execute("INSERT OR IGNORE INTO voyages (code) VALUES (?)", (vc,))
            else:
                # MySQL
                cur.execute("INSERT IGNORE INTO voyages (code) VALUES (%s)", (vc,))
        return vc

    def set_current_voyage_by_code(self, voyage_code: str) -> str:
        # Store the alphanumeric code as the single source of truth
        self.set_config_value("current_voyage_id", voyage_code)
        # (Optionally keep this for backwards compatibility—set both to same code)
        self.set_config_value("current_voyage_code", voyage_code)
        self.current_voyage_id = voyage_code
        self.current_voyage_code = voyage_code
        return voyage_code

    def load_current_voyage_from_config(self):
        vid = self.get_config_value("current_voyage_id", "")
        if vid:
            # Don’t cast to int; keep as string code.
            self.current_voyage_id = vid
            # Keep code mirror for old UI pieces that display it
            self.current_voyage_code = self.get_config_value("current_voyage_code", vid)
            return vid
        # Nothing set
        return None


    # --- USER METHODS ---
    def add_user(self, username: str, password: str, role: str) -> bool:
        """
        Create a user with a bcrypt-hashed password. Returns True on success,
        False if the username already exists or on error.
        """
        try:
            import bcrypt
            hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
            sql = f"INSERT INTO users (username, password_hash, role) VALUES ({self._param()},{self._param()},{self._param()})"
            with self.get_connection() as conn:
                cur = conn.cursor()
                cur.execute(sql, (username, hashed, role))
            return True
        except Exception as e:
            # Handle duplicate/unique constraints cross-DB
            msg = str(e).lower()
            if "unique" in msg or "duplicate" in msg or "1062" in msg:  # MySQL 1062 dup key
                return False
            import logging
            logging.error("add_user failed", exc_info=True)
            return False

    def start_new_voyage(self, voyage_id: str, df, mapping: dict):
        """
        Atomic: import guests for voyage_id, then set current_voyage_id.
        mapping = {"cabin": "A", "last": "B", "first": "C"}  # Excel letters (A,B,C…)
        df = pandas DataFrame of the manifest.

        Guarantees:
          - On success: guests(voyage_id=…) inserted, app_config.current_voyage_id updated.
          - On failure: no changes are persisted (transaction rollback).
        """
        import pandas as pd

        voyage_id = (voyage_id or "").strip()
        if not voyage_id:
            raise ValueError("Voyage ID is required.")
        if len(voyage_id) > 64:
            raise ValueError("Voyage ID too long (max 64 chars).")

        # letter -> index
        def idx(letter: str) -> int:
            result = 0
            for ch in letter.strip().upper():
                result = result * 26 + (ord(ch) - 64)
            return result - 1

        try:
            col_c = df.columns[idx(mapping["cabin"])]
            col_l = df.columns[idx(mapping["last"])]
            col_f = df.columns[idx(mapping["first"])]
        except Exception:
            raise ValueError("Invalid column mapping. Please map Cabin / Last / First correctly.")

        # build rows
        rows = []
        for _, r in df.iterrows():
            try:
                cabin = str(r[col_c]).strip()
                last = str(r[col_l]).strip()
                first = str(r[col_f]).strip()
            except Exception:
                continue
            if not cabin or not last or not first:
                continue
            rows.append((cabin, first, last, voyage_id))

        if not rows:
            raise ValueError("No valid guest rows found after mapping.")

        p = self._param()
        if self.backend == "mysql":
            ins_sql = "INSERT IGNORE INTO guests (cabin_number, first_name, last_name, voyage_id) VALUES (%s,%s,%s,%s)"
            set_sql = "INSERT INTO app_config (`key`,`value`) VALUES ('current_voyage_id', %s) ON DUPLICATE KEY UPDATE `value`=VALUES(`value`)"
        else:
            ins_sql = "INSERT OR IGNORE INTO guests (cabin_number, first_name, last_name, voyage_id) VALUES (?,?,?,?)"
            set_sql = "INSERT OR REPLACE INTO app_config (`key`,`value`) VALUES ('current_voyage_id', ?)"

        # transactional commit
        with self.get_connection() as conn:
            cur = conn.cursor()
            try:
                # IMPORTANT: we do NOT delete other voyages here.
                # New voyage gets its own rows; old voyages remain untouched for Audit.
                batch = 1000
                for i in range(0, len(rows), batch):
                    cur.executemany(ins_sql, rows[i:i + batch])

                # flip current voyage only after successful inserts
                cur.execute(set_sql, (voyage_id,))
                conn.commit()

                # persist last mapping for convenience (keys: cabin/last/first)
                try:
                    self.save_last_mapping(cabin=mapping["cabin"], last=mapping["last"], first=mapping["first"])
                except Exception:
                    pass

                return {"inserted": len(rows), "voyage_id": voyage_id}
            except Exception:
                conn.rollback()
                raise

    def get_user_password_hash(self, username):
        """
        Retrieve the password_hash for a given username.
        Return None if not found.
        """
        conn = None
        cur = None
        try:
            conn = self.get_connection()
            if conn is None:
                return None

            cur = conn.cursor()
            sql = f"SELECT password_hash FROM users WHERE username = {self._param()}"
            cur.execute(sql, (username,))
            row = cur.fetchone()
            if not row:
                return None

            # MySQL gives tuple; SQLite (Row) allows key access
            return row[0] if self.backend == "mysql" else row["password_hash"]

        except Exception as e:
            logging.error(f"Error fetching user '{username}': {e}")
            return None

        finally:
            if cur:
                try:
                    cur.close()
                except:
                    pass
            if conn:
                try:
                    conn.close()
                except:
                    pass

    def update_user_password(self, username: str, new_password: str) -> bool:
        """
        Update user's password hash. Robust against SQLite 'database is locked' by retrying briefly.
        Uses the contextmanager get_connection() so transactions/closures are guaranteed.
        """
        import time
        import bcrypt

        hashed = bcrypt.hashpw(new_password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
        p = self._param()

        # Case-insensitive username match for SQLite; MySQL default collation often is case-insensitive anyway.
        if self.backend == "sqlite":
            sql = f"UPDATE users SET password_hash = {p} WHERE username = {p} COLLATE NOCASE"
        else:
            sql = f"UPDATE users SET password_hash = {p} WHERE username = {p}"

        # Small retry loop helps when another connection briefly holds a write lock
        max_attempts = 3
        delay = 0.15  # seconds

        for attempt in range(1, max_attempts + 1):
            try:
                with self.get_connection() as conn:
                    cur = conn.cursor()
                    cur.execute(sql, (hashed, username))
                    # The contextmanager will commit on exit if no exception
                    return cur.rowcount > 0
            except Exception as e:
                # Handle transient SQLite lock specifically
                msg = str(e).lower()
                if self.backend == "sqlite" and ("database is locked" in msg or "database is busy" in msg):
                    if attempt < max_attempts:
                        time.sleep(delay)
                        delay *= 2  # exponential backoff
                        continue
                # Log and fail on non-transient or final attempt
                logging.error(f"update_user_password failed (attempt {attempt}): {e}", exc_info=True)
                return False

        return False

    def get_config_value(self, key, default=None):
        conn = None
        cur = None
        try:
            conn = self.get_connection()
            cur = conn.cursor()
            sql = f"SELECT value FROM app_config WHERE `key`={self._param()}"
            cur.execute(sql, (key,))
            row = cur.fetchone()
            if not row:
                return default
            # MySQL returns tuple; SQLite Row supports key access
            return row[0] if self.backend == "mysql" else (row["value"] if isinstance(row, sqlite3.Row) else row[0])
        except Exception as e:
            logging.error(f"get_config_value({key}): {e}")
            return default
        finally:
            try:
                cur.close()
            except:
                pass
            try:
                conn.close()
            except:
                pass

    def set_config_value(self, key, value):
        conn = None
        cur = None
        try:
            conn = self.get_connection()
            cur = conn.cursor()
            if self.backend == "sqlite":
                sql = "INSERT OR REPLACE INTO app_config (`key`,`value`) VALUES (?,?)"
            else:
                sql = (
                    "INSERT INTO app_config (`key`,`value`) VALUES (%s,%s) "
                    "ON DUPLICATE KEY UPDATE `value`=VALUES(`value`)"
                )
            cur.execute(sql, (key, value))
            conn.commit()
            return True
        except Exception as e:
            logging.error(f"set_config_value({key}): {e}")
            return False
        finally:
            try:
                cur.close()
            except:
                pass
            try:
                conn.close()
            except:
                pass

    def get_all_users(self):
        try:
            conn = self.get_connection(); cur = conn.cursor()
            cur.execute("SELECT id,username,role FROM users ORDER BY id")
            rows = cur.fetchall()
            return [
                {"id":r[0],"username":r[1],"role":r[2]} if self.backend=="mysql" else dict(r)
                for r in rows
            ]
        except Exception as e:
            logging.error(f"get_all_users: {e}")
            return []
        finally:
            cur.close(); conn.close()

    def delete_user(self, user_id, _):
        try:
            conn = self.get_connection(); cur = conn.cursor()
            cur.execute(f"DELETE FROM users WHERE id={self._param()}", (user_id,))
            conn.commit()
            return True
        except Exception as e:
            logging.error(f"delete_user: {e}")
            return False
        finally:
            cur.close(); conn.close()

    def update_user(self, user_id, new_password, new_role):
        try:
            conn = self.get_connection(); cur = conn.cursor()
            if new_password:
                hashed = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt()).decode()
                sql = f"UPDATE users SET password_hash={self._param()}, role={self._param()} WHERE id={self._param()}"
                cur.execute(sql, (hashed, new_role, user_id))
            else:
                sql = f"UPDATE users SET role={self._param()} WHERE id={self._param()}"
                cur.execute(sql, (new_role, user_id))
            conn.commit()
            return True
        except Exception as e:
            logging.error(f"update_user: {e}")
            return False
        finally:
            cur.close(); conn.close()

    # --- VENUE METHODS ---
    def add_venue(self, name, bf=0, ln=0, dn=1):
        try:
            conn = self.get_connection(); cur = conn.cursor()
            sql = f"INSERT INTO venues (name,breakfast_available,lunch_available,dinner_available) VALUES ({self._param()},{self._param()},{self._param()},{self._param()})"
            cur.execute(sql, (name, bf, ln, dn))
            conn.commit()
            return True
        except Exception as e:
            if "UNIQUE" in str(e): return False
            logging.error(f"add_venue: {e}")
            return False
        finally:
            cur.close(); conn.close()

    def get_all_venues(self):
        try:
            conn = self.get_connection(); cur = conn.cursor()
            cur.execute("SELECT id,name,breakfast_available,lunch_available,dinner_available FROM venues ORDER BY id")
            rows = cur.fetchall()
            return [
                {"id":r[0],"name":r[1],"breakfast_available":r[2],"lunch_available":r[3],"dinner_available":r[4]}
                if self.backend=="mysql" else dict(r)
                for r in rows
            ]
        except Exception as e:
            logging.error(f"get_all_venues: {e}")
            return []
        finally:
            cur.close(); conn.close()

    def delete_venue(self, venue_id: int) -> bool:
        """
        Delete a venue if there are no linked preorders. Returns True if deleted,
        False if blocked or on error.
        """
        try:
            with self.get_connection() as conn:
                cur = conn.cursor()
                sql_cnt = f"SELECT COUNT(*) FROM preorders WHERE venue_id={self._param()}"
                cur.execute(sql_cnt, (venue_id,))
                count = cur.fetchone()[0]

                if count and int(count) > 0:
                    return False  # cannot delete while linked data exists

                sql_del = f"DELETE FROM venues WHERE id={self._param()}"
                cur.execute(sql_del, (venue_id,))
            return True
        except Exception:
            import logging
            logging.error("delete_venue failed", exc_info=True)
            return False

    # --- ALLERGY METHODS ---
    def get_all_allergies(self):
        try:
            conn = self.get_connection(); cur = conn.cursor()
            cur.execute("SELECT id,name FROM allergies ORDER BY name")
            rows = cur.fetchall()
            return [
                {"id":r[0],"name":r[1]} if self.backend=="mysql" else dict(r)
                for r in rows
            ]
        except Exception as e:
            logging.error(f"get_all_allergies: {e}")
            return []
        finally:
            cur.close(); conn.close()

    def add_allergy(self, name):
        try:
            conn = self.get_connection(); cur = conn.cursor()
            cur.execute(f"INSERT INTO allergies (name) VALUES ({self._param()})", (name,))
            conn.commit()
            return True
        except Exception as e:
            if "UNIQUE" in str(e): return False
            logging.error(f"add_allergy: {e}")
            return False
        finally:
            cur.close(); conn.close()

    def delete_allergy(self, aid, aname):
        try:
            conn = self.get_connection(); cur = conn.cursor()
            cur.execute(f"SELECT COUNT(*) FROM preorders WHERE allergy_notes LIKE {self._param()}", (f"%{aname}%",))
            cnt = cur.fetchone()[0] if self.backend=="mysql" else cur.fetchone()[0]
            if cnt>0:
                return False, f"Cannot delete allergy '{aname}'—it’s in use."
            cur.execute(f"DELETE FROM allergies WHERE id={self._param()}", (aid,))
            conn.commit()
            return True, f"Allergy '{aname}' deleted."
        except Exception as e:
            logging.error(f"delete_allergy: {e}")
            return False, "Error deleting allergy"
        finally:
            cur.close(); conn.close()

    def edit_allergy(self, aid, new_name):
        try:
            conn = self.get_connection(); cur = conn.cursor()
            cur.execute(f"UPDATE allergies SET name={self._param()} WHERE id={self._param()}", (new_name, aid))
            conn.commit()
            return True
        except Exception as e:
            logging.error(f"edit_allergy: {e}")
            return False
        finally:
            cur.close(); conn.close()

    # --- GUEST METHODS ---
    def add_guest(self, cab, first, last):
        try:
            conn = self.get_connection()
            cur = conn.cursor()
            vid = getattr(self, "current_voyage_id", None)
            if not vid:
                raise Exception("Current voyage not set")

            if self.backend == "mysql":
                cur.execute(
                    f"INSERT IGNORE INTO guests (cabin_number, first_name, last_name, voyage_id) "
                    f"VALUES ({self._param()},{self._param()},{self._param()},{self._param()})",
                    (cab, first, last, vid)
                )
            else:
                cur.execute(
                    f"INSERT OR IGNORE INTO guests (cabin_number, first_name, last_name, voyage_id) "
                    f"VALUES ({self._param()},{self._param()},{self._param()},{self._param()})",
                    (cab, first, last, vid)
                )
            conn.commit()
            return True
        except Exception as e:
            logging.error(f"add_guest: {e}")
            return False
        finally:
            try:
                cur.close()
            except:
                pass
            try:
                conn.close()
            except:
                pass

    # --- ORDERS & RESET ---
    def get_all_orders_sorted_by_date(self, voyage_id: str | None = None):
        """
        Return orders sorted by date/time/section, optionally scoped to a voyage_id (string).
        Output is list[dict] on SQLite; normalized dict list for MySQL too.
        """
        with self.get_connection() as conn:
            cur = conn.cursor()
            if voyage_id:
                sql = f"""
                    SELECT p.id, p.manager, p.cabin_number, p.guest_name, p.dish, p.pax,
                           p.allergy_notes, p.special_requests, p.service_time_slot,
                           p.galley_section, p.standing_order, p.service_date,
                           v.name AS venue_name
                      FROM preorders p
                      JOIN venues v ON p.venue_id = v.id
                     WHERE p.voyage_id = {self._param()}
                     ORDER BY p.service_date, p.service_time_slot, p.galley_section
                """
                cur.execute(sql, (voyage_id,))
            else:
                sql = """
                    SELECT p.id, p.manager, p.cabin_number, p.guest_name, p.dish, p.pax,
                           p.allergy_notes, p.special_requests, p.service_time_slot,
                           p.galley_section, p.standing_order, p.service_date,
                           v.name AS venue_name
                      FROM preorders p
                      JOIN venues v ON p.venue_id = v.id
                     ORDER BY p.service_date, p.service_time_slot, p.galley_section
                """
                cur.execute(sql)

            rows = cur.fetchall()

            # Normalize to list of dicts (works for both backends)
            cols = ["id", "manager", "cabin_number", "guest_name", "dish", "pax",
                    "allergy_notes", "special_requests", "service_time_slot",
                    "galley_section", "standing_order", "service_date", "venue_name"]
            out = []
            for r in rows:
                if isinstance(r, dict):
                    out.append(r)
                else:
                    out.append({c: r[i] for i, c in enumerate(cols)})
            return out

    def reset_orders(self):
        """
        Clear orders (and guests) for a new cruise.
        Also resets auto-increment counters on MySQL.
        """
        try:
            conn = self.get_connection();
            cur = conn.cursor()
            if self.backend == "mysql":
                # TRUNCATE is faster and resets AUTO_INCREMENT
                cur.execute("TRUNCATE TABLE preorders")
                cur.execute("TRUNCATE TABLE guests")
            else:
                cur.execute("DELETE FROM preorders")
                cur.execute("DELETE FROM guests")
                # Optional: reset SQLite autoincrement counters
                try:
                    cur.execute("DELETE FROM sqlite_sequence WHERE name IN ('preorders','guests')")
                except Exception:
                    pass
            conn.commit()
            return True
        except Exception as e:
            logging.error(f"reset_orders: {e}")
            return False
        finally:
            try:
                cur.close()
            except:
                pass
            try:
                conn.close()
            except:
                pass

    # --- IMPORT MAPPINGS ---
    def save_last_mapping(self, *, cabin_col, last_name_col, first_name_col):
        conn = self.get_connection()
        cur = conn.cursor()
        try:
            if self.backend == "sqlite":
                sql = f"""
                    INSERT OR REPLACE INTO import_mappings 
                    (id, cabin_col, last_name_col, first_name_col)
                    VALUES (1, {self._param()}, {self._param()}, {self._param()})
                """
            else:  # MySQL
                sql = f"""
                    INSERT INTO import_mappings 
                    (id, cabin_col, last_name_col, first_name_col)
                    VALUES (1, {self._param()}, {self._param()}, {self._param()})
                    ON DUPLICATE KEY UPDATE
                        cabin_col = VALUES(cabin_col),
                        last_name_col = VALUES(last_name_col),
                        first_name_col = VALUES(first_name_col)
                """
            cur.execute(sql, (cabin_col, last_name_col, first_name_col))
            conn.commit()
        except Exception as e:
            logging.error(f"Error saving import mapping: {e}")
            raise
        finally:
            try:
                cur.close()
            except:
                pass
            try:
                conn.close()
            except:
                pass

    def load_last_mapping(self):
        try:
            conn = self.get_connection(); cur = conn.cursor()
            cur.execute("SELECT cabin_col,last_name_col,first_name_col FROM import_mappings WHERE id=1")
            row = cur.fetchone()
            return {"cabin":row[0],"last":row[1],"first":row[2]} if row else {}
        except Exception as e:
            logging.error(f"load_last_mapping: {e}")
            return {}
        finally:
            cur.close(); conn.close()
### AUDIT #####
    def audit_list_voyage_ids(self, prefix=""):
        """
        Distinct voyage_id values observed in preorders/guests, newest-first.
        """
        p = self._param()
        sql = f"""
            SELECT voyage_id FROM (
                SELECT DISTINCT voyage_id FROM preorders WHERE voyage_id IS NOT NULL AND TRIM(voyage_id) <> ''
                UNION
                SELECT DISTINCT voyage_id FROM guests    WHERE voyage_id IS NOT NULL AND TRIM(voyage_id) <> ''
            ) x
            {("WHERE voyage_id LIKE " + p) if prefix else ""}
            ORDER BY voyage_id DESC
            LIMIT 200
        """
        params = (f"{prefix}%",) if prefix else ()
        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute(sql, params)
            rows = cur.fetchall()
        return [(r[0] if self.backend == "mysql" else r["voyage_id"]) for r in rows]

    def audit_list_managers(self, voyage_id=None):
        p = self._param()
        where = []
        params = []
        if voyage_id:
            where.append(f"voyage_id = {p}")
            params.append(voyage_id)
        sql = "SELECT DISTINCT manager FROM preorders"
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY manager"
        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute(sql, tuple(params))
            rows = cur.fetchall()
        return [(r[0] if self.backend == "mysql" else r["manager"]) for r in rows]

    def audit_list_venues(self, voyage_id=None):
        """
        Return [(id, name)] for venues that appear in preorders (optionally scoped to a voyage).
        """
        p = self._param()
        where = []
        params = []
        if voyage_id:
            where.append(f"p.voyage_id = {p}")
            params.append(voyage_id)
        sql = f"""
            SELECT DISTINCT v.id, COALESCE(v.name, CAST(p.venue_id AS CHAR))
              FROM preorders p
              LEFT JOIN venues v ON v.id = p.venue_id
             {("WHERE " + " AND ".join(where)) if where else ""}
             ORDER BY 2
        """
        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute(sql, tuple(params))
            rows = cur.fetchall()
        if self.backend == "mysql":
            return [(r[0], r[1]) for r in rows]
        return [(r["id"], r[1]) for r in rows]

    def audit_fetch_orders(self, voyage_id=None, date_from=None, date_to=None,
                           venue_id=None, manager=None, search=None,
                           limit=200, offset=0):
        """
        Fetch rows for the audit table.
        """
        p = self._param()
        where = ["1=1"]
        params = []

        if voyage_id:
            where.append(f"p.voyage_id = {p}")
            params.append(voyage_id.strip())
        if date_from:
            where.append(f"p.service_date >= {p}")
            params.append(date_from)
        if date_to:
            where.append(f"p.service_date <= {p}")
            params.append(date_to)
        if venue_id not in (None, "", 0):
            where.append(f"p.venue_id = {p}")
            params.append(int(venue_id))
        if manager:
            where.append(f"p.manager = {p}")
            params.append(manager.strip())
        if search:
            like = f"%{search.strip()}%"
            where.append(
                f"(p.guest_name LIKE {p} OR p.dish LIKE {p} OR p.allergy_notes LIKE {p} OR p.special_requests LIKE {p})")
            params += [like, like, like, like]

        sql = f"""
            SELECT p.id, p.service_date, p.voyage_id, p.manager,
                   p.cabin_number, p.guest_name, p.dish, p.pax,
                   p.service_time_slot, p.galley_section, p.venue_id,
                   COALESCE(v.name, CAST(p.venue_id AS CHAR)) AS venue_name,
                   p.allergy_notes, p.special_requests
              FROM preorders p
              LEFT JOIN venues v ON v.id = p.venue_id
             WHERE {" AND ".join(where)}
             ORDER BY p.service_date DESC, p.id DESC
             LIMIT {limit} OFFSET {offset}
        """
        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute(sql, tuple(params))
            rows = cur.fetchall()
        if self.backend == "mysql":
            cols = ["id", "service_date", "voyage_id", "manager", "cabin_number", "guest_name", "dish", "pax",
                    "service_time_slot", "galley_section", "venue_id", "venue_name", "allergy_notes",
                    "special_requests"]
            return [dict(zip(cols, r)) for r in rows]
        return [dict(r) for r in rows]

    def audit_count_orders(self, voyage_id=None, date_from=None, date_to=None,
                           venue_id=None, manager=None, search=None):
        p = self._param()
        where = ["1=1"]
        params = []

        if voyage_id:
            where.append(f"voyage_id = {p}")
            params.append(voyage_id.strip())
        if date_from:
            where.append(f"service_date >= {p}")
            params.append(date_from)
        if date_to:
            where.append(f"service_date <= {p}")
            params.append(date_to)
        if venue_id not in (None, "", 0):
            where.append(f"venue_id = {p}")
            params.append(int(venue_id))
        if manager:
            where.append(f"manager = {p}")
            params.append(manager.strip())
        if search:
            like = f"%{search.strip()}%"
            where.append(
                f"(guest_name LIKE {p} OR dish LIKE {p} OR allergy_notes LIKE {p} OR special_requests LIKE {p})"
            )
            params += [like, like, like, like]

        sql = f"SELECT COUNT(*) AS cnt FROM preorders WHERE {' AND '.join(where)}"
        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute(sql, tuple(params))
            v = cur.fetchone()

        # Works for both MySQL tuples and sqlite3.Row
        if not v:
            return 0
        try:
            return int(v[0])
        except Exception:
            # In case a backend returns a mapping-like row with a key
            return int(v["cnt"])


class AdminLoginFrame(ttk.Frame):
    """
    A simple login frame that requires 'ADMIN' user to input password.
    If the password is still the default, user is forced to change it.
    """
    def __init__(self, master, controller):
        super().__init__(master)
        self.controller = controller
        self.pack(fill="both", expand=True)

        ttk.Label(self, text="Admin Login", font=("Helvetica", 16, "bold")).pack(pady=20)

        form_frame = ttk.Frame(self)
        form_frame.pack(padx=30, pady=10)

        # Password Field
        ttk.Label(form_frame, text="Password (for ADMIN):").grid(row=0, column=0, sticky="e", pady=5)
        self.password_var = tk.StringVar()
        self.password_entry = ttk.Entry(form_frame, textvariable=self.password_var, show='*', width=30)
        self.password_entry.grid(row=0, column=1, pady=5, sticky='w')
        self.password_entry.bind("<Return>", lambda e: self.check_password())

        # Login Button
        login_btn = ttk.Button(self, text="Login", command=self.check_password)
        login_btn.pack(pady=10)

        # Force an admin user to exist
        self.ensure_admin_exists()

    def ensure_admin_exists(self):
        """
        Ensure that an 'ADMIN' user is in the DB.
        If not, create one with the default password '123456'.
        """
        existing_hash = self.controller.db_manager.get_user_password_hash("ADMIN")
        if existing_hash is None:
            # Admin user does not exist; create with default
            self.controller.db_manager.add_user("ADMIN", "123456", "admin")

    def check_password(self):
        """
        Verify admin password, if default => ask to change.
        Else => show main admin panel.
        """
        entered_pw = self.password_var.get().strip()
        if not entered_pw:
            messagebox.showwarning("Validation Error", "Please enter the ADMIN password.")
            return

        # Compare hashed password from DB
        stored_hash = self.controller.db_manager.get_user_password_hash("ADMIN")
        if not stored_hash:
            messagebox.showerror("Login Error", "ADMIN user not found. Contact support.")
            return

        # If user typed the default pass or typed something else, check properly
        if bcrypt.checkpw(entered_pw.encode('utf-8'), stored_hash.encode('utf-8')):
            # If we matched the DB hash
            if entered_pw == DEFAULT_ADMIN_PASSWORD:
                # Force a password change
                messagebox.showinfo("Force Password Change", "Please set a new password for ADMIN.")
                self.controller.show_admin_forced_change()
            else:
                # Good to go
                messagebox.showinfo("Login Successful", "Welcome, ADMIN!")
                self.controller.create_main_panel()
        else:
            messagebox.showerror("Login Failed", "Wrong password for ADMIN.")

# ----------------------------
# AdminForceChangeFrame: Force new admin password if default
# ----------------------------
class AdminForceChangeFrame(ttk.Frame):
    """
    Forcibly ask user to set a new admin password if the default is still in place.
    """
    def __init__(self, master, controller):
        super().__init__(master)
        self.controller = controller
        self.pack(fill="both", expand=True)

        ttk.Label(self, text="Change ADMIN Password", font=("Helvetica", 16, "bold")).pack(pady=20)

        form_frame = ttk.Frame(self)
        form_frame.pack(padx=30, pady=10)

        # New Password
        ttk.Label(form_frame, text="New Password:").grid(row=0, column=0, sticky="e", pady=5)
        self.new_pw_var = tk.StringVar()
        self.new_pw_entry = ttk.Entry(form_frame, textvariable=self.new_pw_var, show='*', width=30)
        self.new_pw_entry.grid(row=0, column=1, pady=5, sticky='w')

        # Confirm Password
        ttk.Label(form_frame, text="Confirm Password:").grid(row=1, column=0, sticky="e", pady=5)
        self.confirm_pw_var = tk.StringVar()
        self.confirm_pw_entry = ttk.Entry(form_frame, textvariable=self.confirm_pw_var, show='*', width=30)
        self.confirm_pw_entry.grid(row=1, column=1, pady=5, sticky='w')

        save_btn = ttk.Button(self, text="Save", command=self.save_new_password)
        save_btn.pack(pady=10)

    def save_new_password(self):
        pw1 = self.new_pw_var.get().strip()
        pw2 = self.confirm_pw_var.get().strip()

        if not pw1 or not pw2:
            messagebox.showwarning("Validation Error", "All fields are required.")
            return
        if pw1 != pw2:
            messagebox.showwarning("Validation Error", "Passwords do not match.")
            return
        if len(pw1) < PASSWORD_MIN_LENGTH:
            messagebox.showwarning("Validation Error", f"Password must be at least {PASSWORD_MIN_LENGTH} characters.")
            return

        # Update the DB
        success = self.controller.db_manager.update_user_password("ADMIN", pw1)
        if success:
            messagebox.showinfo("Success", "ADMIN password changed successfully!")
            self.controller.create_main_panel()
        else:
            messagebox.showerror("Error", "Failed to update the ADMIN password. Try again.")

# ----------------------------
# Main Admin Panels and Frames
# ----------------------------
class AddUserFrame(ttk.Frame):
    def __init__(self, master, controller):
        super().__init__(master)
        self.controller = controller

        ttk.Label(self, text="Add New User", font=("Helvetica", 16)).pack(pady=20)

        form_frame = ttk.Frame(self)
        form_frame.pack(padx=50, pady=10)

        # Username
        ttk.Label(form_frame, text="Username:").grid(row=0, column=0, pady=5, sticky='e')
        self.username_var = tk.StringVar()
        username_entry = ttk.Entry(form_frame, textvariable=self.username_var, width=30)
        username_entry.grid(row=0, column=1, pady=5, sticky='w')

        # Password
        ttk.Label(form_frame, text="Password:").grid(row=1, column=0, pady=5, sticky='e')
        self.password_var = tk.StringVar()
        password_entry = ttk.Entry(form_frame, textvariable=self.password_var, show='*', width=30)
        password_entry.grid(row=1, column=1, pady=5, sticky='w')

        # Role
        ttk.Label(form_frame, text="Role:").grid(row=2, column=0, pady=5, sticky='e')
        self.role_var = tk.StringVar(value=ROLES[0])
        role_dropdown = ttk.Combobox(form_frame, textvariable=self.role_var, values=ROLES, state='readonly')
        role_dropdown.grid(row=2, column=1, pady=5, sticky='w')

        # Save Button
        save_button = ttk.Button(self, text="Save User", command=self.save_user)
        save_button.pack(pady=20)

    def save_user(self):
        username = self.username_var.get().strip()
        password = self.password_var.get().strip()
        role = self.role_var.get().strip()

        # Validation
        if not username:
            messagebox.showwarning("Validation Error", "Username is required.")
            return
        if not password:
            messagebox.showwarning("Validation Error", "Password is required.")
            return
        if len(password) < PASSWORD_MIN_LENGTH:
            messagebox.showwarning("Validation Error", f"Password must be at least {PASSWORD_MIN_LENGTH} characters long.")
            return
        if role not in ROLES:
            messagebox.showwarning("Validation Error", "Invalid role selected.")
            return

        success = self.controller.db_manager.add_user(username, password, role)
        if success:
            messagebox.showinfo("Success", f"User '{username}' added successfully.")
            self.username_var.set("")
            self.password_var.set("")
            self.role_var.set(ROLES[0])
        else:
            messagebox.showerror("Error", "Username already exists. Please choose another one.")
class AuditWindow(tk.Toplevel):

    def __init__(self, master):
        super().__init__(master)
        self.title("Audit – Historical Orders")
        self.geometry("1150x640")
        self.db = master.db_manager

        # try tkcalendar for date pickers
        try:
            from tkcalendar import DateEntry  # type: ignore
            self._DateEntry = DateEntry
        except Exception:
            self._DateEntry = None  # will fall back to Entry

        # Filters row
        f = ttk.Frame(self, padding=10); f.pack(fill="x")

        ttk.Label(f, text="Voyage").grid(row=0, column=0, sticky="w")
        self.voy_var = tk.StringVar()
        self.voy_cb = ttk.Combobox(f, textvariable=self.voy_var, width=16, state="readonly")
        self.voy_cb.grid(row=0, column=1, padx=6)

        ttk.Label(f, text="Manager").grid(row=0, column=2, sticky="w")
        self.mgr_var = tk.StringVar()
        self.mgr_cb = ttk.Combobox(f, textvariable=self.mgr_var, width=16, state="readonly")
        self.mgr_cb.grid(row=0, column=3, padx=6)

        ttk.Label(f, text="Venue").grid(row=0, column=4, sticky="w")
        self.venue_var = tk.StringVar()
        self.venue_cb = ttk.Combobox(f, textvariable=self.venue_var, width=18, state="readonly")
        self.venue_cb.grid(row=0, column=5, padx=6)

        ttk.Label(f, text="From").grid(row=1, column=0, sticky="w", pady=(8,0))
        self.from_var = tk.StringVar()
        if self._DateEntry:
            self.from_widget = self._DateEntry(f, textvariable=self.from_var, date_pattern="yyyy-mm-dd", width=14)
        else:
            self.from_widget = ttk.Entry(f, textvariable=self.from_var, width=16)
        self.from_widget.grid(row=1, column=1, padx=6, pady=(8,0))

        ttk.Label(f, text="To").grid(row=1, column=2, sticky="w", pady=(8,0))
        self.to_var = tk.StringVar()
        if self._DateEntry:
            self.to_widget = self._DateEntry(f, textvariable=self.to_var, date_pattern="yyyy-mm-dd", width=14)
        else:
            self.to_widget = ttk.Entry(f, textvariable=self.to_var, width=16)
        self.to_widget.grid(row=1, column=3, padx=6, pady=(8,0))

        ttk.Label(f, text="Search").grid(row=1, column=4, sticky="w", pady=(8,0))
        self.q_var = tk.StringVar()
        ttk.Entry(f, textvariable=self.q_var, width=20).grid(row=1, column=5, padx=6, pady=(8,0))

        # Buttons
        b = ttk.Frame(self, padding=(10,0)); b.pack(fill="x")
        ttk.Button(b, text="Search", command=self._manual_search).pack(side="left")
        ttk.Button(b, text="Export CSV", command=self.export_csv).pack(side="left", padx=8)
        ttk.Button(b, text="Export Excel", command=self.export_excel).pack(side="left")
        ttk.Button(b, text="Close", command=self.destroy).pack(side="right")

        # Table
        cols = ("date","voy","mgr","venue","cabin","guest","dish","pax","slot","galley","allergies","requests")
        self.tree = ttk.Treeview(self, columns=cols, show="headings", selectmode="browse")
        self.tree.pack(fill="both", expand=True, pady=10, padx=10)

        headings = [
            ("date","Date",100), ("voy","Voyage",90), ("mgr","Manager",110), ("venue","Venue",140),
            ("cabin","Cabin",70), ("guest","Guest",160), ("dish","Dish",200), ("pax","Pax",40),
            ("slot","Slot",80), ("galley","Galley",80), ("allergies","Allergies",220), ("requests","Requests",220)
        ]
        for key, text, w in headings:
            self.tree.heading(key, text=text)
            self.tree.column(key, width=w, anchor="w")

        # Pagination
        pgr = ttk.Frame(self, padding=10); pgr.pack(fill="x")
        self.page = 0
        self.page_size = 200
        self.prev_btn = ttk.Button(pgr, text="◀ Prev", command=self.prev_page)
        self.next_btn = ttk.Button(pgr, text="Next ▶", command=self.next_page)
        self.prev_btn.pack(side="left")
        self.next_btn.pack(side="left", padx=6)
        self.count_lbl = ttk.Label(pgr, text="")
        self.count_lbl.pack(side="right")

        # Events (auto-refresh)
        self._bind_auto_refresh()

        # Initial data
        self._preload_filters()
        self.reload()

    def _preload_filters(self):
        try:
            voyages = self.db.audit_list_voyage_ids()
            self.voy_cb["values"] = ["ALL"] + voyages
            if not self.voy_var.get():
                self.voy_var.set("ALL")
        except Exception:
            self.voy_cb["values"] = ["ALL"]
            self.voy_var.set("ALL")
        self._refresh_manager_venue_lists()

    def _refresh_manager_venue_lists(self):
        vid = None if self.voy_var.get() == "ALL" else self.voy_var.get().strip()
        try:
            managers = self.db.audit_list_managers(vid)
            self.mgr_cb["values"] = ["ALL"] + managers
            if not self.mgr_var.get():
                self.mgr_var.set("ALL")
        except Exception:
            self.mgr_cb["values"] = ["ALL"]
            self.mgr_var.set("ALL")

        try:
            venues = self.db.audit_list_venues(vid)
            items = ["ALL"] + [f"{vid_} - {name}" for vid_, name in venues]
            self.venue_cb["values"] = items
            if not self.venue_var.get():
                self.venue_var.set("ALL")
        except Exception:
            self.venue_cb["values"] = ["ALL"]
            self.venue_var.set("ALL")

    def _parse_venue_id(self):
        raw = (self.venue_var.get() or "").strip()
        if " - " in raw:
            left = raw.split(" - ", 1)[0]
            return int(left) if left.isdigit() else None
        return int(raw) if raw.isdigit() else None

    def _filters(self):
        voy = None if self.voy_var.get().strip().upper() == "ALL" else self.voy_var.get().strip() or None
        d1 = self.from_var.get().strip() or None
        d2 = self.to_var.get().strip() or None
        mgr = None if self.mgr_var.get().strip().upper() == "ALL" else self.mgr_var.get().strip() or None
        ven = self._parse_venue_id() if self.venue_var.get().strip().upper() != "ALL" else None
        q = self.q_var.get().strip() or None
        return voy, d1, d2, ven, mgr, q

    def _manual_search(self):
        # Allow the Search button to reset to page 0 and reload
        self.page = 0
        self.reload()

    def _bind_auto_refresh(self):
        # Voyage change → refresh dependent lists, then reload
        self.voy_cb.bind("<<ComboboxSelected>>", lambda e: (self._refresh_manager_venue_lists(), self._auto_reload()))
        # Manager / Venue changes → reload
        self.mgr_cb.bind("<<ComboboxSelected>>", lambda e: self._auto_reload())
        self.venue_cb.bind("<<ComboboxSelected>>", lambda e: self._auto_reload())

        # Date pickers: DateEntry fires a virtual event; Entry fallback uses Return/FocusOut
        if self._DateEntry:
            self.from_widget.bind("<<DateEntrySelected>>", lambda e: self._auto_reload())
            self.to_widget.bind("<<DateEntrySelected>>", lambda e: self._auto_reload())
        else:
            self.from_widget.bind("<Return>", lambda e: self._auto_reload())
            self.from_widget.bind("<FocusOut>", lambda e: self._auto_reload())
            self.to_widget.bind("<Return>", lambda e: self._auto_reload())
            self.to_widget.bind("<FocusOut>", lambda e: self._auto_reload())

    def _auto_reload(self):
        self.page = 0
        self.reload()

    def reload(self):
        voy, d1, d2, ven, mgr, q = self._filters()
        off = self.page * self.page_size
        rows = self.db.audit_fetch_orders(voy, d1, d2, ven, mgr, q, limit=self.page_size, offset=off)
        total = self.db.audit_count_orders(voy, d1, d2, ven, mgr, q)

        # Fill table
        self.tree.delete(*self.tree.get_children())
        for r in rows:
            self.tree.insert("", "end", values=(
                r["service_date"], r["voyage_id"], r["manager"], r["venue_name"],
                r["cabin_number"], r["guest_name"], r["dish"], r["pax"],
                r["service_time_slot"], r["galley_section"],
                r["allergy_notes"] or "", r["special_requests"] or ""
            ))

        # Count label
        self.count_lbl.config(text=f"{min(total, off + len(rows))}/{total} (page {self.page + 1})")

        # Enable/disable pager buttons
        self.prev_btn.config(state=("normal" if self.page > 0 else "disabled"))
        # Disable "Next" if this page is not full OR we're at/over total
        at_end = (off + len(rows)) >= total
        page_full = (len(rows) == self.page_size)
        self.next_btn.config(state=("normal" if (page_full and not at_end) else "disabled"))

    def next_page(self):
        # Only advance if next is enabled
        if str(self.next_btn.cget("state")) == "normal":
            self.page += 1
            self.reload()

    def prev_page(self):
        if self.page > 0:
            self.page -= 1
            self.reload()

    def export_csv(self):
        """Export current filter results to CSV."""
        import csv
        import tkinter.filedialog as fd

        voy, d1, d2, ven, mgr, q = self._filters()
        # pull a large page so you get everything that matches the filters
        rows = self.db.audit_fetch_orders(voy, d1, d2, ven, mgr, q, limit=50000, offset=0)
        path = fd.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV", "*.csv")])
        if not path:
            return
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["Date", "Voyage", "Manager", "Venue", "Cabin", "Guest", "Dish", "Pax",
                        "Time Slot", "Galley", "Allergies", "Requests"])
            for r in rows:
                w.writerow([
                    r["service_date"], r["voyage_id"], r["manager"], r["venue_name"],
                    r["cabin_number"], r["guest_name"], r["dish"], r["pax"],
                    r["service_time_slot"], r["galley_section"],
                    r["allergy_notes"] or "", r["special_requests"] or ""
                ])

    def export_excel(self):
        """Export current filter results to a nicely formatted Excel workbook."""
        import tkinter.filedialog as fd
        from tkinter import messagebox

        # --- deps check ---
        try:
            import pandas as pd
        except ImportError:
            messagebox.showerror("Missing", "Install pandas to export Excel:\n\npip install pandas")
            return
        try:
            import xlsxwriter  # noqa: F401 - only to ensure engine availability
            excel_engine = "xlsxwriter"
        except Exception:
            # Fallback to openpyxl (less formatting power but still ok)
            excel_engine = "openpyxl"

        # --- data ---
        voy, d1, d2, ven, mgr, q = self._filters()
        rows = self.db.audit_fetch_orders(voy, d1, d2, ven, mgr, q, limit=50000, offset=0)
        if not rows:
            messagebox.showinfo("Empty", "No data to export.")
            return

        # Order & rename columns for presentation
        export_cols = [
            ("service_date", "Date"),
            ("voyage_id", "Voyage"),
            ("manager", "Manager"),
            ("venue_name", "Venue"),
            ("cabin_number", "Cabin"),
            ("guest_name", "Guest"),
            ("dish", "Dish"),
            ("pax", "Pax"),
            ("service_time_slot", "Slot"),
            ("galley_section", "Galley"),
            ("allergy_notes", "Allergies"),
            ("special_requests", "Requests"),
        ]
        df = pd.DataFrame(rows)
        df = df[[src for src, _ in export_cols]]
        df.columns = [dst for _, dst in export_cols]

        # Reasonable types
        if "Pax" in df.columns:
            df["Pax"] = pd.to_numeric(df["Pax"], errors="coerce")
        # Date stays as text if your DB stores it as 'YYYY-MM-DD'; formatting will handle it.

        # --- save path ---
        path = fd.asksaveasfilename(defaultextension=".xlsx", filetypes=[("Excel", "*.xlsx")])
        if not path:
            return

        # --- writer + formats ---
        with pd.ExcelWriter(path, engine=excel_engine) as writer:
            sheet = "Orders"
            # Leave 2 rows at top for a title/subtitle
            df.to_excel(writer, sheet_name=sheet, index=False, startrow=2)

            wb = writer.book
            ws = writer.sheets[sheet]

            # Title + subtitle
            title = "Audit – Historical Orders"
            filters_desc = []
            if voy: filters_desc.append(f"Voyage: {voy}")
            if d1:  filters_desc.append(f"From: {d1}")
            if d2:  filters_desc.append(f"To: {d2}")
            if mgr: filters_desc.append(f"Manager: {mgr}")
            if ven: filters_desc.append(f"Venue ID: {ven}")
            if q:   filters_desc.append(f"Search: {q}")
            subtitle = " | ".join(filters_desc) if filters_desc else "All records (current filter set)"

            if excel_engine == "xlsxwriter":
                # Nice formats
                f_title = wb.add_format({"bold": True, "font_size": 16})
                f_sub = wb.add_format({"italic": True, "font_size": 10, "font_color": "#666666"})
                ws.write(0, 0, title, f_title)
                ws.write(1, 0, subtitle, f_sub)

                # Header format
                f_header = wb.add_format({
                    "bold": True, "text_wrap": True, "align": "center", "valign": "vcenter",
                    "bg_color": "#2F5597", "font_color": "white", "border": 1
                })

                # Body formats
                f_text = wb.add_format({"text_wrap": False, "valign": "top", "border": 1})
                f_wrap = wb.add_format({"text_wrap": True, "valign": "top", "border": 1})
                f_center = wb.add_format({"align": "center", "valign": "top", "border": 1})
                f_date = wb.add_format({"num_format": "yyyy-mm-dd", "valign": "top", "border": 1})
                f_int = wb.add_format({"num_format": "0", "align": "center", "valign": "top", "border": 1})

                # Range info
                n_rows, n_cols = df.shape
                header_row = 2
                first_data_row = header_row + 1
                last_row = first_data_row + n_rows - 1
                last_col = n_cols - 1

                # Convert to a formal Excel Table (built-in style)
                ws.add_table(header_row, 0, last_row, last_col, {
                    "name": "OrdersTable",
                    "style": {"theme": "Table Style Light 9"},
                    "columns": [{"header": c} for c in df.columns]
                })

                # Autofilter is included with add_table, but freeze panes needs manual set
                ws.freeze_panes(first_data_row, 0)

                # Column widths: smart estimate
                def _col_width(series, min_w=8, max_w=40, pad=2):
                    try:
                        max_len = max((len(str(x)) for x in series.dropna().astype(str)), default=min_w)
                    except Exception:
                        max_len = min_w
                    return max(min_w, min(max_w, max_len + pad))

                # Preferred widths per column (fallback to auto)
                pref_widths = {
                    "Date": 12, "Voyage": 14, "Manager": 16, "Venue": 18, "Cabin": 10,
                    "Guest": 20, "Dish": 26, "Pax": 6, "Slot": 10, "Galley": 12,
                    "Allergies": 28, "Requests": 30,
                }

                # Apply column formats & widths
                for col_idx, col_name in enumerate(df.columns):
                    series = df[col_name]
                    # Decide width
                    auto_w = _col_width(series)
                    width = max(pref_widths.get(col_name, 12), auto_w)

                    # Decide format
                    if col_name in ("Allergies", "Requests", "Dish", "Guest"):
                        col_fmt = f_wrap
                    elif col_name in ("Pax",):
                        col_fmt = f_int
                    elif col_name in ("Date",):
                        # If your Date is text not datetime, we still use normal text format; adjust if needed
                        col_fmt = f_date if pd.api.types.is_datetime64_any_dtype(series) else f_center
                    elif col_name in ("Cabin", "Slot", "Galley", "Voyage", "Manager", "Venue"):
                        col_fmt = f_center
                    else:
                        col_fmt = f_text

                    ws.set_column(col_idx, col_idx, width, col_fmt)

                # Re-apply custom header (since add_table uses its own—overwrite visually)
                for col_idx, col_name in enumerate(df.columns):
                    ws.write(header_row, col_idx, col_name, f_header)

                # Zebra striping with conditional formatting (applies to data rows only)
                if n_rows > 0:
                    zebra_format = wb.add_format({"bg_color": "#F7F7F7"})
                    ws.conditional_format(first_data_row, 0, last_row, last_col, {
                        "type": "formula",
                        "criteria": "=MOD(ROW(),2)=0",
                        "format": zebra_format
                    })

                # Optional: highlight high PAX counts
                if "Pax" in df.columns:
                    pax_idx = list(df.columns).index("Pax")
                    ws.conditional_format(first_data_row, pax_idx, last_row, pax_idx, {
                        "type": "cell", "criteria": ">=", "value": 6,
                        "format": wb.add_format({"bg_color": "#FFF2CC"})
                    })

            else:
                # openpyxl path: we can still freeze, set widths, and add filter
                ws = writer.sheets[sheet]

                # Freeze header row
                ws.freeze_panes = ws["A3"]  # first data row

                # Autofilter
                ws.auto_filter.ref = ws.dimensions

                # Basic width heuristic
                from openpyxl.utils import get_column_letter
                def _col_width_text(series, min_w=8, max_w=40, pad=2):
                    try:
                        max_len = max((len(str(x)) for x in series.dropna().astype(str)), default=min_w)
                    except Exception:
                        max_len = min_w
                    return max(min_w, min(max_w, max_len + pad))

                for i, col_name in enumerate(df.columns, start=1):
                    col_letter = get_column_letter(i)
                    width = max(12, _col_width_text(df[col_name]))
                    ws.column_dimensions[col_letter].width = width

                # Title & subtitle (basic)
                ws["A1"] = "Audit – Historical Orders"
                ws["A2"] = (" | ".join([
                    f"Voyage: {voy}" if voy else "",
                    f"From: {d1}" if d1 else "",
                    f"To: {d2}" if d2 else "",
                    f"Manager: {mgr}" if mgr else "",
                    f"Venue ID: {ven}" if ven else "",
                    f"Search: {q}" if q else "",
                ])).strip(" | ")

        messagebox.showinfo("Exported", f"Excel saved to:\n{path}")


class ManageUsersFrame(ttk.Frame):
    def __init__(self, master, controller):
        super().__init__(master)
        self.controller = controller

        ttk.Label(self, text="Manage Users", font=("Helvetica", 16)).pack(pady=20)

        columns = ("ID", "Username", "Role")
        self.tree = ttk.Treeview(self, columns=columns, show="headings")
        for col in columns:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=150, anchor='center')
        self.tree.pack(fill='both', expand=True, padx=20, pady=10)

        self.load_users()

        button_frame = ttk.Frame(self)
        button_frame.pack(pady=10)

        edit_button = ttk.Button(button_frame, text="Edit Selected", command=self.edit_user)
        edit_button.pack(side='left', padx=10)

        delete_button = ttk.Button(button_frame, text="Delete Selected", command=self.delete_user)
        delete_button.pack(side='left', padx=10)

    def load_users(self):
        for row in self.tree.get_children():
            self.tree.delete(row)
        users = self.controller.db_manager.get_all_users()
        for user in users:
            self.tree.insert("", tk.END, values=(user["id"], user["username"], user["role"]))

    def delete_user(self):
        selected_item = self.tree.selection()
        if not selected_item:
            messagebox.showwarning("No Selection", "Please select a user to delete.")
            return
        user_id, username, role = self.tree.item(selected_item[0], 'values')
        if username.upper() == "ADMIN":
            messagebox.showerror("Error", "Cannot delete the built-in ADMIN user.")
            return
        confirm = messagebox.askyesno("Confirm Deletion", f"Are you sure you want to delete user '{username}'?")
        if confirm:
            success = self.controller.db_manager.delete_user(user_id, username)
            if success:
                messagebox.showinfo("Deleted", f"User '{username}' has been deleted.")
                self.load_users()
            else:
                messagebox.showerror("Error", "Failed to delete the user.")

    def edit_user(self):
        selected_item = self.tree.selection()
        if not selected_item:
            messagebox.showwarning("No Selection", "Please select a user to edit.")
            return
        user_id, username, role = self.tree.item(selected_item[0], 'values')
        edit_dialog = EditUserDialog(self, self.controller, user_id, username, role)
        self.wait_window(edit_dialog)
        self.load_users()

class EditUserDialog(tk.Toplevel):
    def __init__(self, parent, controller, user_id, username, role):
        super().__init__(parent)
        self.controller = controller
        self.user_id = user_id
        self.username = username
        self.role = role

        self.title(f"Edit User: {username}")
        self.geometry("400x300")
        self.resizable(False, False)

        ttk.Label(self, text=f"Edit User: {username}", font=("Helvetica", 14)).pack(pady=10)

        form_frame = ttk.Frame(self)
        form_frame.pack(padx=20, pady=10, fill='both', expand=True)

        ttk.Label(form_frame, text="New Password:").grid(row=0, column=0, pady=5, sticky='e')
        self.new_password_var = tk.StringVar()
        new_password_entry = ttk.Entry(form_frame, textvariable=self.new_password_var, show='*', width=30)
        new_password_entry.grid(row=0, column=1, pady=5, sticky='w')

        ttk.Label(form_frame, text="Role:").grid(row=1, column=0, pady=5, sticky='e')
        self.new_role_var = tk.StringVar(value=role)
        new_role_dropdown = ttk.Combobox(form_frame, textvariable=self.new_role_var, values=ROLES, state='readonly')
        new_role_dropdown.grid(row=1, column=1, pady=5, sticky='w')

        save_button = ttk.Button(self, text="Save Changes", command=self.save_changes)
        save_button.pack(pady=20)

    def save_changes(self):
        new_password = self.new_password_var.get().strip()
        new_role = self.new_role_var.get().strip()

        if new_role not in ROLES:
            messagebox.showwarning("Validation Error", "Invalid role selected.")
            return
        if self.username.upper() == "ADMIN" and new_role != "admin":
            messagebox.showerror("Error", "Cannot change the ADMIN user role.")
            return

        if new_password and len(new_password) < PASSWORD_MIN_LENGTH:
            messagebox.showwarning("Validation Error", f"Password must be at least {PASSWORD_MIN_LENGTH} characters long.")
            return

        success = self.controller.db_manager.update_user(self.user_id, new_password, new_role)
        if success:
            messagebox.showinfo("Success", f"User '{self.username}' updated successfully.")
            self.destroy()
        else:
            messagebox.showerror("Error", "Failed to update the user.")

class AddVenueFrame(ttk.Frame):
    def __init__(self, master, controller):
        super().__init__(master)
        self.controller = controller

        ttk.Label(self, text="Add New Venue", font=("Helvetica", 16)).pack(pady=20)

        form_frame = ttk.Frame(self)
        form_frame.pack(padx=50, pady=10)

        # Venue Name
        ttk.Label(form_frame, text="Venue Name:").grid(row=0, column=0, pady=5, sticky='e')
        self.venue_name_var = tk.StringVar()
        venue_name_entry = ttk.Entry(form_frame, textvariable=self.venue_name_var, width=30)
        venue_name_entry.grid(row=0, column=1, pady=5, sticky='w')

        # Meal Availability Checkboxes
        self.breakfast_var = tk.BooleanVar()
        self.lunch_var = tk.BooleanVar()
        self.dinner_var = tk.BooleanVar(value=True)  # Dinner available by default

        breakfast_cb = ttk.Checkbutton(form_frame, text="Breakfast Available", variable=self.breakfast_var)
        breakfast_cb.grid(row=1, column=0, columnspan=2, pady=5, sticky='w')

        lunch_cb = ttk.Checkbutton(form_frame, text="Lunch Available", variable=self.lunch_var)
        lunch_cb.grid(row=2, column=0, columnspan=2, pady=5, sticky='w')

        dinner_cb = ttk.Checkbutton(form_frame, text="Dinner Available", variable=self.dinner_var)
        dinner_cb.grid(row=3, column=0, columnspan=2, pady=5, sticky='w')

        save_button = ttk.Button(self, text="Save Venue", command=self.save_venue)
        save_button.pack(pady=20)

    def save_venue(self):
        venue_name = self.venue_name_var.get().strip()
        if not venue_name:
            messagebox.showwarning("Validation Error", "Venue name is required.")
            return

        # Convert boolean to integer
        breakfast_int = 1 if self.breakfast_var.get() else 0
        lunch_int = 1 if self.lunch_var.get() else 0
        dinner_int = 1 if self.dinner_var.get() else 0

        success = self.controller.db_manager.add_venue(venue_name, breakfast_int, lunch_int, dinner_int)
        if success:
            messagebox.showinfo("Success", f"Venue '{venue_name}' added successfully with availability:\n"
                                           f"Breakfast: {bool(breakfast_int)}, Lunch: {bool(lunch_int)}, Dinner: {bool(dinner_int)}")
            self.venue_name_var.set("")
            self.breakfast_var.set(False)
            self.lunch_var.set(False)
            self.dinner_var.set(True)
        else:
            messagebox.showerror("Error", "Venue name already exists. Please choose another one.")


class StartNewVoyageWindow(tk.Toplevel):
    def __init__(self, master):
        super().__init__(master)
        self.db = master.db_manager
        self.title("Start New Voyage")
        self.geometry("820x560")
        self.resizable(True, True)

        # state
        self.voy_var  = tk.StringVar()
        self.cabin_var = tk.StringVar()
        self.last_var  = tk.StringVar()
        self.first_var = tk.StringVar()
        self.df = None
        self.columns = []
        self.preview_rows = []

        # layout
        container = ttk.Frame(self, padding=12)
        container.pack(fill="both", expand=True)

        # --- Step 1: Voyage ID ---
        box1 = ttk.LabelFrame(container, text="Step 1 — Voyage", padding=10)
        box1.pack(fill="x")
        ttk.Label(box1, text="Voyage ID:").grid(row=0, column=0, sticky="w")
        ttk.Entry(box1, textvariable=self.voy_var, width=24).grid(row=0, column=1, padx=8, sticky="w")
        self.cur_lbl = ttk.Label(box1, text=f"Current: {self.db.get_config_value('current_voyage_id','') or '—'}")
        self.cur_lbl.grid(row=0, column=2, padx=12, sticky="w")

        # --- Step 2: Manifest + Mapping ---
        box2 = ttk.LabelFrame(container, text="Step 2 — Manifest & Mapping", padding=10)
        box2.pack(fill="x", pady=(10,0))

        ttk.Button(box2, text="Select Excel/CSV", command=self._select_file).grid(row=0, column=0, sticky="w")
        self.file_lbl = ttk.Label(box2, text="No file selected")
        self.file_lbl.grid(row=0, column=1, columnspan=3, padx=8, sticky="w")

        for c in range(6):
            box2.columnconfigure(c, weight=1)

        ttk.Label(box2, text="Cabin Col").grid(row=1, column=0, sticky="e", pady=(8,0))
        self.cabin_cb = ttk.Combobox(box2, textvariable=self.cabin_var, state="readonly", width=8)
        self.cabin_cb.grid(row=1, column=1, sticky="w", pady=(8,0))

        ttk.Label(box2, text="Last Name Col").grid(row=1, column=2, sticky="e", pady=(8,0))
        self.last_cb = ttk.Combobox(box2, textvariable=self.last_var, state="readonly", width=8)
        self.last_cb.grid(row=1, column=3, sticky="w", pady=(8,0))

        ttk.Label(box2, text="First Name Col").grid(row=1, column=4, sticky="e", pady=(8,0))
        self.first_cb = ttk.Combobox(box2, textvariable=self.first_var, state="readonly", width=8)
        self.first_cb.grid(row=1, column=5, sticky="w", pady=(8,0))

        # --- Step 3: Preview + Commit ---
        box3 = ttk.LabelFrame(container, text="Step 3 — Preview & Commit", padding=10)
        box3.pack(fill="both", expand=True, pady=(10,0))

        self.preview = ttk.Treeview(box3, columns=("cabin","last","first"), show="headings", height=12)
        self.preview.heading("cabin", text="Cabin")
        self.preview.heading("last",  text="Last")
        self.preview.heading("first", text="First")
        self.preview.column("cabin", width=110, anchor="w")
        self.preview.column("last",  width=180, anchor="w")
        self.preview.column("first", width=180, anchor="w")
        self.preview.pack(fill="both", expand=True)

        btns = ttk.Frame(container)
        btns.pack(fill="x", pady=(8,0))
        ttk.Button(btns, text="Commit New Voyage", command=self._commit).pack(side="left")
        ttk.Button(btns, text="Close", command=self.destroy).pack(side="right")

        # preload last mapping if available
        try:
            last_map = self.db.load_last_mapping() or {}
            self.cabin_var.set(last_map.get("cabin",""))
            self.last_var.set(last_map.get("last",""))
            self.first_var.set(last_map.get("first",""))
        except Exception:
            pass

    # ---- helpers ----
    def _letters(self, n):
        out = []
        for i in range(n):
            s, k = "", i
            while True:
                k, r = divmod(k, 26)
                s = chr(65+r) + s
                if k == 0: break
            out.append(s)
        return out

    def _select_file(self):
        from tkinter import filedialog, messagebox
        path = filedialog.askopenfilename(filetypes=[("Excel/CSV", "*.xls *.xlsx *.csv")])
        if not path: return
        self.file_lbl.config(text=path)

        # read to DataFrame (use existing pyexcel path for xls/xlsx)
        try:
            import pandas as pd
            if path.lower().endswith(".csv"):
                df = pd.read_csv(path)
            else:
                import pyexcel, pyexcel_xls, pyexcel_xlsx  # ensure plugins
                records = pyexcel.get_records(file_name=path)
                df = pd.DataFrame(records)
        except Exception as e:
            messagebox.showerror("Read Error", f"Failed to read file:\n{e}")
            return

        self.df = df
        self.columns = list(df.columns)
        letters = self._letters(len(self.columns))
        for cb in (self.cabin_cb, self.last_cb, self.first_cb):
            cb["values"] = letters
            if not cb.get():
                cb.set("")
        self._refresh_preview()
        self.focus()

    def _refresh_preview(self):
        # build preview if df + mapping are present
        for i in self.preview.get_children():
            self.preview.delete(i)
        if self.df is None: return
        if not self.cabin_var.get() or not self.last_var.get() or not self.first_var.get():
            return

        # convert letter->index
        def idx(letter: str) -> int:
            res = 0
            for ch in letter.strip().upper():
                res = res*26 + (ord(ch)-64)
            return res-1

        try:
            ci = idx(self.cabin_var.get()); li = idx(self.last_var.get()); fi = idx(self.first_var.get())
            ccol = self.columns[ci]; lcol = self.columns[li]; fcol = self.columns[fi]
        except Exception:
            return

        # first 100 rows
        cnt = 0
        for _, r in self.df.iterrows():
            cabin = str(r.get(ccol,"")).strip()
            last  = str(r.get(lcol,"")).strip()
            first = str(r.get(fcol,"")).strip()
            if not cabin and not last and not first:
                continue
            self.preview.insert("", "end", values=(cabin,last,first))
            cnt += 1
            if cnt >= 100: break


    def _commit(self):
        from tkinter import messagebox
        import pandas as pd

        vid = (self.voy_var.get() or "").strip()
        if not vid:
            messagebox.showwarning("Missing", "Please enter a Voyage ID.")
            return
        if self.df is None:
            messagebox.showwarning("Missing", "Please select a manifest file first.")
            return
        if not self.cabin_var.get() or not self.last_var.get() or not self.first_var.get():
            messagebox.showwarning("Missing", "Please map Cabin / Last / First columns.")
            return

        mapping = {"cabin": self.cabin_var.get(), "last": self.last_var.get(), "first": self.first_var.get()}

        # Confirm boundary rule
        if not messagebox.askyesno("Confirm", f"Start new voyage '{vid}'?\n"
                                              f"This will activate the voyage and use the imported guests.\n"
                                              f"Previous voyages remain in Audit; nothing will be carried over."):
            return

        # Run atomic service
        try:
            stats = self.db.start_new_voyage(vid, self.df, mapping)
            messagebox.showinfo("Voyage Activated",
                                f"Voyage {stats['voyage_id']} is now active.\n"
                                f"Guests imported: {stats['inserted']}")
            # update label
            self.cur_lbl.config(text=f"Current: {stats['voyage_id']}")
            # optional: close window
            # self.destroy()
        except Exception as e:
            messagebox.showerror("Failed", f"Could not start voyage:\n{e}")
            return

        # persist last mapping (convenience)
        try:
            self.db.save_last_mapping(cabin=mapping["cabin"], last=mapping["last"], first=mapping["first"])
        except Exception:
            pass

class RemoveVenueFrame(ttk.Frame):
    def __init__(self, master, controller):
        super().__init__(master)
        self.controller = controller

        ttk.Label(self, text="Remove Venue", font=("Helvetica", 16)).pack(pady=20)

        columns = ("ID", "Venue Name", "Breakfast", "Lunch", "Dinner")
        self.tree = ttk.Treeview(self, columns=columns, show="headings")
        for col in columns:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=150, anchor='center')
        self.tree.pack(fill='both', expand=True, padx=20, pady=10)

        self.load_venues()

        button_frame = ttk.Frame(self)
        button_frame.pack(pady=10)

        delete_button = ttk.Button(button_frame, text="Delete Selected", command=self.delete_venue)
        delete_button.pack(side='left', padx=10)

    def load_venues(self):
        for row in self.tree.get_children():
            self.tree.delete(row)
        venues = self.controller.db_manager.get_all_venues()
        for venue in venues:
            # venue: id, name, breakfast_available, lunch_available, dinner_available
            self.tree.insert("", tk.END, values=(
                venue["id"],
                venue["name"],
                "Yes" if venue["breakfast_available"] else "No",
                "Yes" if venue["lunch_available"] else "No",
                "Yes" if venue["dinner_available"] else "No"
            ))

    def delete_venue(self):
        selected_item = self.tree.selection()
        if not selected_item:
            messagebox.showwarning("No Selection", "Please select a venue to delete.")
            return
        venue_id, venue_name, bf, ln, dn = self.tree.item(selected_item[0], 'values')
        confirm = messagebox.askyesno("Confirm Deletion", f"Are you sure you want to delete venue '{venue_name}'?")
        if confirm:
            success, message = self.controller.db_manager.delete_venue(venue_id, venue_name)
            if success:
                messagebox.showinfo("Deleted", message)
                self.load_venues()
            else:
                messagebox.showerror("Error", message)

class AddAllergyFrame(ttk.Frame):
    def __init__(self, master, controller):
        super().__init__(master)
        self.controller = controller

        ttk.Label(self, text="Add New Allergy", font=("Helvetica", 16)).pack(pady=20)

        form_frame = ttk.Frame(self)
        form_frame.pack(padx=50, pady=10)

        ttk.Label(form_frame, text="Allergy Name:").grid(row=0, column=0, pady=5, sticky='e')
        self.allergy_name_var = tk.StringVar()
        allergy_name_entry = ttk.Entry(form_frame, textvariable=self.allergy_name_var, width=30)
        allergy_name_entry.grid(row=0, column=1, pady=5, sticky='w')

        save_button = ttk.Button(self, text="Save Allergy", command=self.save_allergy)
        save_button.pack(pady=20)

    def save_allergy(self):
        allergy_name = self.allergy_name_var.get().strip()
        if not allergy_name:
            messagebox.showwarning("Validation Error", "Allergy name is required.")
            return

        success = self.controller.db_manager.add_allergy(allergy_name)
        if success:
            messagebox.showinfo("Success", f"Allergy '{allergy_name}' added successfully.")
            self.allergy_name_var.set("")
        else:
            messagebox.showerror("Error", "Allergy name already exists. Please choose another one.")
import os, json, csv, shutil, hashlib, subprocess, platform
from datetime import datetime
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

class BackupManagementWindow(tk.Toplevel):
    """
    Simple per-voyage backup UI:
    - Backup Now: exports CSVs + manifest.json into ./backups/<voyage_code>/<timestamp> and zips them.
    - Lists existing backups by voyage and timestamp.
    - Export Selected: copy the generated ZIP to a user location.
    - Open Folder: open the backups root folder.
    """
    BACKUP_ROOT = os.path.join(os.getcwd(), "backups")
    TABLES = ["preorders", "venues", "guests", "users", "allergies", "app_config", "voyages"]

    def __init__(self, master):
        super().__init__(master)
        self.title("Backup Management")
        self.geometry("760x460")
        self.resizable(True, True)
        self.db = master.db_manager

        frm = ttk.Frame(self, padding=12)
        frm.pack(fill="both", expand=True)
        top = ttk.Frame(frm); top.pack(fill="x")
        ttk.Button(top, text="Backup Now", command=self.create_backup).pack(side="left", padx=(0, 8))
        ttk.Button(top, text="Export Selected…", command=self.export_selected).pack(side="left", padx=(0, 8))
        ttk.Button(top, text="Open Folder", command=self.open_folder).pack(side="left", padx=(0, 8))
        ttk.Button(top, text="Close", command=self.destroy).pack(side="right")

        cols = ("Voyage", "Timestamp", "Path", "Zip")
        self.tree = ttk.Treeview(frm, columns=cols, show="headings", selectmode="browse")
        for c in cols:
            self.tree.heading(c, text=c)
            self.tree.column(c, anchor="center", width=160 if c != "Path" else 320)
        self.tree.pack(fill="both", expand=True, pady=(10,0))

        self.refresh_list()

    # ---------- UI helpers ----------
    def refresh_list(self):
        self.tree.delete(*self.tree.get_children())
        root = self.BACKUP_ROOT
        if not os.path.isdir(root):
            os.makedirs(root, exist_ok=True)
        for voyage in sorted(os.listdir(root)):
            vdir = os.path.join(root, voyage)
            if not os.path.isdir(vdir):
                continue
            for ts in sorted(os.listdir(vdir)):
                bdir = os.path.join(vdir, ts)
                if not os.path.isdir(bdir):
                    continue
                zip_path = os.path.join(bdir, "archive.zip")
                self.tree.insert("", "end", values=(voyage, ts, bdir, (zip_path if os.path.isfile(zip_path) else "")))

    def open_folder(self):
        path = self.BACKUP_ROOT
        if platform.system() == "Windows":
            os.startfile(path)
        elif platform.system() == "Darwin":
            subprocess.run(["open", path], check=False)
        else:
            subprocess.run(["xdg-open", path], check=False)

    def current_selection(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("No selection", "Please select a backup from the list.")
            return None
        voyage, ts, bdir, zip_path = self.tree.item(sel[0], "values")
        return {"voyage": voyage, "timestamp": ts, "dir": bdir, "zip": zip_path}

    def export_selected(self):
        info = self.current_selection()
        if not info:
            return
        if not info["zip"] or not os.path.isfile(info["zip"]):
            messagebox.showwarning("Missing ZIP", "Selected backup has no archive.zip. Create a new backup.")
            return
        dest = filedialog.asksaveasfilename(
            title="Export Backup ZIP",
            defaultextension=".zip",
            initialfile=f"{info['voyage']}_{info['timestamp']}.zip",
            filetypes=[("ZIP archive", "*.zip")]
        )
        if not dest:
            return
        shutil.copy2(info["zip"], dest)
        messagebox.showinfo("Exported", f"Backup exported to:\n{dest}")

    # ---------- Backup core ----------
    def create_backup(self):
        vcode = getattr(self.db, "current_voyage_code", None) or self.db.get_config_value(
            "current_voyage_code") or "UNKNOWN"
        vid = getattr(self.db, "current_voyage_id", None) or self.db.get_config_value("current_voyage_id") or ""
        ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

        base = os.path.join(self.BACKUP_ROOT, vcode, ts)
        meta_dir = os.path.join(base, "meta")
        os.makedirs(meta_dir, exist_ok=True)

        # 1) Export Excel workbook
        excel_path, row_counts = self._export_tables_to_excel(vcode, vid, base)

        # 2) Manifest
        manifest = {
            "created_at": ts,
            "voyage_code": vcode,
            "voyage_id": vid,
            "backend": self.db.backend,
            "tables": row_counts,
        }
        with open(os.path.join(meta_dir, "manifest.json"), "w", encoding="utf-8") as f:
            json.dump(manifest, f, ensure_ascii=False, indent=2)

        # 3) Zip everything
        zip_path = os.path.join(base, "archive.zip")
        self._zip_dir([base], zip_path)

        # 4) SHA256 checksum
        sha = self._sha256_file(zip_path)
        with open(os.path.join(base, "archive.sha256"), "w", encoding="utf-8") as f:
            f.write(f"{sha}  archive.zip\n")

        self.refresh_list()
        messagebox.showinfo("Backup Complete",
                            f"Excel backup created for voyage {vcode} (id: {vid})\n\n"
                            f"File:\n{excel_path}\n\narchive.zip SHA256:\n{sha}")
        self.focus()

    def _export_tables_to_excel(self, vcode, vid, base_dir):
        """
        Creates one Excel file with one sheet per table.
        Adds headers in bold with background fill.
        """


        wb = Workbook()
        row_counts = {}

        # Remove default empty sheet
        default_ws = wb.active
        wb.remove(default_ws)

        for table in self.TABLES:
            ws = wb.create_sheet(title=table)
            with self.db.get_connection() as conn:
                cur = conn.cursor()
                if table == "preorders" and str(vid).strip():
                    p = self.db._param()
                    cur.execute(f"SELECT * FROM {table} WHERE voyage_id={p}", (vid,))

                else:
                    cur.execute(f"SELECT * FROM {table}")
                rows = cur.fetchall()
                headers = [c[0] for c in cur.description]

            # Write headers with style
            header_fill = PatternFill("solid", fgColor="1E90FF")  # DodgerBlue
            header_font = Font(bold=True, color="FFFFFF")
            for col, header in enumerate(headers, 1):
                cell = ws.cell(row=1, column=col, value=header)
                cell.font = header_font
                cell.fill = header_fill
                cell.alignment = Alignment(horizontal="center", vertical="center")

            # Write data rows
            for r, row in enumerate(rows, 2):
                for c, val in enumerate(row, 1):
                    ws.cell(row=r, column=c, value=val)

            # Autofit column widths
            for col_idx, header in enumerate(headers, 1):
                max_len = max(
                    (len(str(val)) if val is not None else 0) for val in [header] + [row[col_idx - 1] for row in rows])
                ws.column_dimensions[chr(64 + col_idx)].width = min(max_len + 2, 40)

            row_counts[table] = len(rows)

        excel_path = os.path.join(base_dir, f"backup_{vcode}.xlsx")
        wb.save(excel_path)
        return excel_path, row_counts
    # ---------- Low-level helpers ----------
    def _export_table_to_csv(self, table, out_dir, vcode, vid):
        """
        Exports a whole table to CSV. For 'preorders', it scopes to current voyage_id to keep backup small.
        If you want full-history backups, remove the WHERE for preorders.
        """
        path = os.path.join(out_dir, f"{table}.csv")
        with self.db.get_connection() as conn:
            cur = conn.cursor()
            if table == "preorders" and str(vid).strip():
                p = self.db._param()
                cur.execute(f"SELECT * FROM {table} WHERE voyage_id={p}", (int(vid),))
            else:
                cur.execute(f"SELECT * FROM {table}")
            rows = cur.fetchall()
            headers = [c[0] for c in cur.description]
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(headers)
            w.writerows(rows)
        return len(rows)

    def _zip_dir(self, paths, out_zip):
        import zipfile
        with zipfile.ZipFile(out_zip, "w", compression=zipfile.ZIP_DEFLATED) as z:
            for p in paths:
                for root, _, files in os.walk(p):
                    for name in files:
                        full = os.path.join(root, name)
                        rel  = os.path.relpath(full, os.path.dirname(paths[0]))
                        z.write(full, rel)

    def _sha256_file(self, file_path):
        h = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                h.update(chunk)
        return h.hexdigest()

class ManageAllergiesFrame(ttk.Frame):
    def __init__(self, master, controller):
        super().__init__(master)
        self.controller = controller

        ttk.Label(self, text="Manage Allergies", font=("Helvetica", 16)).pack(pady=20)

        columns = ("ID", "Allergy Name")
        self.tree = ttk.Treeview(self, columns=columns, show="headings")
        for col in columns:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=200, anchor='center')
        self.tree.pack(fill='both', expand=True, padx=20, pady=10)

        self.load_allergies()

        button_frame = ttk.Frame(self)
        button_frame.pack(pady=10)

        edit_button = ttk.Button(button_frame, text="Edit Selected", command=self.edit_allergy)
        edit_button.pack(side='left', padx=10)

        delete_button = ttk.Button(button_frame, text="Delete Selected", command=self.delete_allergy)
        delete_button.pack(side='left', padx=10)

    def load_allergies(self):
        for row in self.tree.get_children():
            self.tree.delete(row)
        allergies = self.controller.db_manager.get_all_allergies()
        for allergy in allergies:
            self.tree.insert("", tk.END, values=(allergy["id"], allergy["name"]))

    def delete_allergy(self):
        selected_item = self.tree.selection()
        if not selected_item:
            messagebox.showwarning("No Selection", "Please select an allergy to delete.")
            return
        allergy_id, allergy_name = self.tree.item(selected_item[0], 'values')
        confirm = messagebox.askyesno("Confirm Deletion", f"Are you sure you want to delete allergy '{allergy_name}'?")
        if confirm:
            success, message = self.controller.db_manager.delete_allergy(allergy_id, allergy_name)
            if success:
                messagebox.showinfo("Deleted", message)
                self.load_allergies()
            else:
                messagebox.showerror("Error", message)

    def edit_allergy(self):
        selected_item = self.tree.selection()
        if not selected_item:
            messagebox.showwarning("No Selection", "Please select an allergy to edit.")
            return
        allergy_id, allergy_name = self.tree.item(selected_item[0], 'values')
        edit_dialog = EditAllergyDialog(self, self.controller, allergy_id, allergy_name)
        self.wait_window(edit_dialog)
        self.load_allergies()



class ImportGuestSetupFrame(ttk.Frame):
    def __init__(self, parent, controller, on_complete_callback):
        super().__init__(parent)
        self.controller = controller
        self.db = controller.db_manager
        self.on_complete = on_complete_callback

        self.columns = []
        self.df = None

        self.cabin_col_var = tk.StringVar()
        self.last_name_col_var = tk.StringVar()
        self.first_name_col_var = tk.StringVar()

        self.create_widgets()

    def create_widgets(self):
        ttk.Label(self, text="Guest Import Setup", font=("Helvetica", 16, "bold")).pack(pady=10)
        ttk.Button(self, text="Select Excel File", command=self.load_excel).pack(pady=10)

        self.dropdown_frame = ttk.Frame(self)
        self.dropdown_frame.pack(pady=10)

        for col in range(4):
            self.dropdown_frame.columnconfigure(col, weight=1)

        ttk.Label(self.dropdown_frame, text="Cabin Column:").grid(row=0, column=0, padx=5, pady=5, sticky="e")
        self.cabin_dropdown = ttk.Combobox(
            self.dropdown_frame,
            textvariable=self.cabin_col_var,
            state="readonly",
            width=10
        )
        self.cabin_dropdown.grid(row=0, column=1, padx=5, pady=5, sticky="w")

        ttk.Label(self.dropdown_frame, text="Last Name Column:").grid(row=1, column=0, padx=5, pady=5, sticky="e")
        self.last_dropdown = ttk.Combobox(
            self.dropdown_frame,
            textvariable=self.last_name_col_var,
            state="readonly",
            width=10
        )
        self.last_dropdown.grid(row=1, column=1, padx=5, pady=5, sticky="w")

        ttk.Label(self.dropdown_frame, text="First Name Column:").grid(row=1, column=2, padx=5, pady=5, sticky="e")
        self.first_dropdown = ttk.Combobox(
            self.dropdown_frame,
            textvariable=self.first_name_col_var,
            state="readonly",
            width=10
        )
        self.first_dropdown.grid(row=1, column=3, padx=5, pady=5, sticky="w")

        ttk.Button(self, text="Save and Import", command=self.save_and_import).pack(pady=20)

    def load_excel(self):
        import sys, tkinter.messagebox as mb

        file_path = filedialog.askopenfilename(
            filetypes=[("Excel files", "*.xls *.xlsx")]
        )
        if not file_path:
            return

        # 1) Make sure pyexcel core is installed
        try:
            import pyexcel
        except ImportError as e:
            messagebox.showerror(
                "Missing Dependency",
                "To import old Excel files, install:\n\n"
                "    pip install pyexcel\n\n"
                f"(ImportError: {e})"
            )
            return

        # 2) Make sure the pandas engine is available
        try:
            import pandas as pd
        except ImportError as e:
            messagebox.showerror(
                "Missing Dependency",
                "To process Excel data, install:\n\n"
                "    pip install pandas\n\n"
                f"(ImportError: {e})"
            )
            return

        # 3) Ensure XLS/XLSX plugins are present
        try:
            import pyexcel_xls  # plugin for .xls
            import pyexcel_xlsx  # plugin for .xlsx
        except ImportError:
            messagebox.showerror(
                "Missing Plugin",
                "To read .xls/.xlsx files, install:\n\n"
                "    pip install pyexcel-xls pyexcel-xlsx"
            )
            return

        # 4) Finally, read the sheet
        try:
            records = pyexcel.get_records(file_name=file_path)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load Excel file:\n{e}")
            return

        # Wrap into a DataFrame and continue as before
        self.df = pd.DataFrame(records)
        self.columns = self.df.columns.tolist()
        column_letters = self.get_column_letters(len(self.columns))
        for dd in (self.cabin_dropdown, self.last_dropdown, self.first_dropdown):
            dd["values"] = column_letters
            dd.set("")

        # FIXED: use correct keys returned by load_last_mapping(): {"cabin","last","first"}
        last_map = self.db.load_last_mapping() or {}
        self.cabin_col_var.set(last_map.get("cabin", ""))
        self.last_name_col_var.set(last_map.get("last", ""))
        self.first_name_col_var.set(last_map.get("first", ""))

    # Rest of the class remains the same (save_and_import, get_column_letters, get_column_index)
    def save_and_import(self):
        import threading
        import pandas as pd  # ensure pd is available here too

        cabin_col = self.cabin_col_var.get()
        last_name_col = self.last_name_col_var.get()
        first_name_col = self.first_name_col_var.get()

        if not all([cabin_col, last_name_col, first_name_col]):
            messagebox.showerror("Missing Fields", "All columns must be mapped before importing.")
            return

        # REQUIRE a current voyage_id before importing (alphanumeric like 'SU542')
        vid = getattr(self.db, "current_voyage_id", None)
        if not vid:
            messagebox.showerror("Missing Voyage", "Please set the current voyage first (Admin → Voyage Settings).")
            return

        def do_import():
            try:
                conn = self.db.get_connection()
                cur = conn.cursor()

                # 1) Clear existing guests for THIS voyage only
                if self.db.backend == "mysql":
                    cur.execute("DELETE FROM guests WHERE voyage_id = %s", (vid,))
                else:
                    cur.execute("DELETE FROM guests WHERE voyage_id = ?", (vid,))
                conn.commit()

                # 2) Save mapping
                self.db.save_last_mapping(
                    cabin_col=cabin_col,
                    last_name_col=last_name_col,
                    first_name_col=first_name_col
                )

                idx_c = self.get_column_index(cabin_col)
                idx_l = self.get_column_index(last_name_col)
                idx_f = self.get_column_index(first_name_col)
                col_c = self.columns[idx_c]
                col_l = self.columns[idx_l]
                col_f = self.columns[idx_f]

                # 3) Bulk insert (fast method) WITH voyage_id
                guests = []
                for _, row in self.df.iterrows():
                    if any(pd.isna(row.get(c)) for c in (col_c, col_l, col_f)):
                        continue
                    cabin = str(row[col_c]).strip()
                    first = str(row[col_f]).strip()
                    last  = str(row[col_l]).strip()
                    guests.append((cabin, first, last, vid))

                if guests:
                    batch_size = 1000
                    if self.db.backend == "mysql":
                        sql = "INSERT IGNORE INTO guests (cabin_number, first_name, last_name, voyage_id) VALUES (%s, %s, %s, %s)"
                    else:
                        sql = "INSERT OR IGNORE INTO guests (cabin_number, first_name, last_name, voyage_id) VALUES (?, ?, ?, ?)"

                    for i in range(0, len(guests), batch_size):
                        batch = guests[i:i + batch_size]
                        cur.executemany(sql, batch)
                    conn.commit()

                cur.close()
                conn.close()

                self.after(0, lambda: [
                    loader.destroy(),
                    messagebox.showinfo("Success", f"Guest list imported successfully for voyage: {vid}."),
                    self.on_complete()
                ])
            except Exception as e:
                self.after(0, lambda err=e: [
                    loader.destroy(),
                    messagebox.showerror("Import Failed", f"An error occurred:\n{err}")
                ])

        loader = LoadingDialog(self, "Importing guests... Please wait.")
        threading.Thread(target=do_import, daemon=True).start()

    def get_column_letters(self, n):
        letters = []
        for i in range(n):
            result = ""
            temp = i
            while True:
                temp, r = divmod(temp, 26)
                result = chr(65 + r) + result
                if temp == 0:
                    break
            letters.append(result)
        return letters

    def get_column_index(self, letter):
        result = 0
        for char in letter:
            result = result * 26 + (ord(char.upper()) - ord('A') + 1)
        return result - 1  # zero-based

class DatabaseSettingsWindow(tk.Toplevel):
    def __init__(self, master=None, config_file='db_config.json'):
        super().__init__(master)
        self.title("Database Settings")
        self.geometry("400x450")
        self.resizable(False, False)
        self.config_file = config_file

        # Load existing config if available
        self.db_mode = tk.StringVar(value="sqlite")
        self.mysql_host = tk.StringVar(value="localhost")
        self.mysql_port = tk.StringVar(value="3306")
        self.mysql_db = tk.StringVar(value="")
        self.mysql_user = tk.StringVar(value="")
        self.mysql_pass = tk.StringVar(value="")
        self.tz_var = tk.StringVar(value="UTC")
        try:
            current_tz = self.master.db_manager.get_config_value("server_time_zone", "UTC")
            self.tz_var.set(current_tz or "UTC")
        except Exception:
            self.tz_var.set("UTC")

        self.load_config()

        self.create_widgets()

    def create_widgets(self):
        # Database Mode
        db_mode_frame = ttk.LabelFrame(self, text="Database Mode", padding=10)
        db_mode_frame.pack(fill='x', padx=16, pady=8)

        ttk.Radiobutton(db_mode_frame, text="Offline (SQLite)", variable=self.db_mode, value="sqlite", command=self.toggle_mysql_fields).pack(anchor='w')
        ttk.Radiobutton(db_mode_frame, text="Online (MySQL)", variable=self.db_mode, value="mysql", command=self.toggle_mysql_fields).pack(anchor='w')

        # MySQL Settings Frame
        self.mysql_frame = ttk.LabelFrame(self, text="MySQL Settings", padding=10)
        self.mysql_frame.pack(fill='x', padx=16, pady=8)

        self.create_labeled_entry(self.mysql_frame, "Host:", self.mysql_host, 0)
        self.create_labeled_entry(self.mysql_frame, "Port:", self.mysql_port, 1)
        self.create_labeled_entry(self.mysql_frame, "Database Name:", self.mysql_db, 2)
        self.create_labeled_entry(self.mysql_frame, "Username:", self.mysql_user, 3)
        self.create_labeled_entry(self.mysql_frame, "Password:", self.mysql_pass, 4, show="*")

        # Time Zone Settings
        tz_frame = ttk.LabelFrame(self, text="Time Zone", padding=10)
        tz_frame.pack(fill='x', padx=16, pady=8)

        # Build a timezone list (pytz if available; fallback to a small curated list)
        try:
            import pytz
            tz_list = list(pytz.all_timezones)
        except Exception:
            tz_list = [
                "UTC",
                "Europe/Athens",
                "Europe/Istanbul",
                "Europe/London",
                "America/New_York",
                "America/Los_Angeles",
                "Asia/Dubai",
                "Asia/Singapore",
                "Australia/Sydney",
            ]

        ttk.Label(tz_frame, text="Server Time Zone:").grid(row=0, column=0, sticky='e', pady=4)
        tz_combo = ttk.Combobox(tz_frame, textvariable=self.tz_var, values=tz_list, state='readonly', width=32)
        tz_combo.grid(row=0, column=1, sticky='w', pady=4)

        # Buttons
        btn_frame = ttk.Frame(self)
        btn_frame.pack(fill='x', padx=16, pady=16)

        ttk.Button(btn_frame, text="Test Connection", command=self.test_connection).pack(side='left')
        ttk.Button(btn_frame, text="Sync Data", command=self.sync_databases).pack(side='left', padx=8)
        ttk.Button(btn_frame, text="Save", command=self.save_config).pack(side='right')
        ttk.Button(btn_frame, text="Cancel", command=self.destroy).pack(side='right', padx=8)

        self.toggle_mysql_fields()

    def sync_databases(self):
        """
        Bidirectional migration between SQLite and MySQL that tolerates schema drift.
        Copies: users, venues, allergies, voyages, guests, preorders, import_mappings, app_config.
        Only common columns are transferred per table. Properly quotes identifiers (e.g., `key`).
        """
        from tkinter import messagebox

        # Build source & dest configs
        if self.db_mode.get() == "mysql":
            src_cfg = {"type": "sqlite"}
            dst_cfg = {
                "type": "mysql",
                "host": self.mysql_host.get(),
                "port": int(self.mysql_port.get()),
                "database": self.mysql_db.get(),
                "user": self.mysql_user.get(),
                "password": self.mysql_pass.get()
            }
            direction = "SQLite → MySQL"
        else:
            src_cfg = {
                "type": "mysql",
                "host": self.mysql_host.get(),
                "port": int(self.mysql_port.get()),
                "database": self.mysql_db.get(),
                "user": self.mysql_user.get(),
                "password": self.mysql_pass.get()
            }
            dst_cfg = {"type": "sqlite"}
            direction = "MySQL → SQLite"

        if not messagebox.askyesno(
                "Confirm Migration",
                f"This will overwrite data in the destination database.\n\nMigrate all data ({direction})?"
        ):
            return

        # --- helpers -------------------------------------------------------------
        def quote_ident(backend: str, name: str) -> str:
            # Basic identifier quoting to survive reserved words like `key`
            if backend == "sqlite":
                return f"\"{name}\""
            return f"`{name}`"  # MySQL

        def _cols(conn, table, backend):
            cur = conn.cursor()
            try:
                if backend == "sqlite":
                    cur.execute(f"PRAGMA table_info({table})")
                    return [r[1] for r in cur.fetchall()]
                else:
                    cur.execute("""
                        SELECT COLUMN_NAME
                          FROM information_schema.COLUMNS
                         WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s
                         ORDER BY ORDINAL_POSITION
                    """, (table,))
                    return [r[0] for r in cur.fetchall()]
            finally:
                try:
                    cur.close()
                except:
                    pass

        def _disable_fks(conn, backend):
            cur = conn.cursor()
            try:
                cur.execute("PRAGMA foreign_keys = OFF" if backend == "sqlite" else "SET FOREIGN_KEY_CHECKS = 0")
            finally:
                try:
                    cur.close()
                except:
                    pass

        def _enable_fks(conn, backend):
            cur = conn.cursor()
            try:
                cur.execute("PRAGMA foreign_keys = ON" if backend == "sqlite" else "SET FOREIGN_KEY_CHECKS = 1")
            finally:
                try:
                    cur.close()
                except:
                    pass

        try:
            # Managers and connections
            src_db = DatabaseManager(src_cfg)
            dst_db = DatabaseManager(dst_cfg)

            # Ensure destination schema (creates voyages, app_config with `key`,`value`, etc.)
            dst_db.setup_database()  # Admin/Restaurant DBs create app_config with backticked columns. :contentReference[oaicite:2]{index=2} :contentReference[oaicite:3]{index=3}

            src_conn = src_db.get_connection()
            dst_conn = dst_db.get_connection()

            # Copy in dependency order
            tables = ["users", "venues", "allergies", "voyages", "guests", "preorders", "import_mappings", "app_config"]

            _disable_fks(dst_conn, dst_db.backend)

            for tbl in tables:
                s_cols = _cols(src_conn, tbl, src_db.backend)
                d_cols = _cols(dst_conn, tbl, dst_db.backend)
                common = [c for c in s_cols if c in d_cols]
                if not common:
                    continue

                # Quoted names for SQL strings; keep raw names for mapping
                q_tbl_src = quote_ident(src_db.backend, tbl)
                q_tbl_dst = quote_ident(dst_db.backend, tbl)
                q_common = [quote_ident(src_db.backend, c) for c in common]
                q_common_dst = [quote_ident(dst_db.backend, c) for c in common]

                # 1) fetch from source (only common columns)
                s_cur = src_conn.cursor()
                s_select = f"SELECT {','.join(q_common)} FROM {q_tbl_src}"
                s_cur.execute(s_select)
                rows = s_cur.fetchall()

                # 2) clear destination table
                d_cur = dst_conn.cursor()
                d_cur.execute(f"DELETE FROM {q_tbl_dst}")

                # 3) insert into destination
                placeholder = ",".join(["?" if dst_db.backend == "sqlite" else "%s"] * len(common))
                d_insert = f"INSERT INTO {q_tbl_dst} ({','.join(q_common_dst)}) VALUES ({placeholder})"

                # Build index map once for tuple rows
                idx_map = [s_cols.index(c) for c in common]

                for r in rows:
                    # sqlite Row or tuple
                    if hasattr(r, "keys"):
                        vals = [r[c] for c in common]
                    else:
                        vals = [r[i] for i in idx_map]
                    d_cur.execute(d_insert, vals)

                dst_conn.commit()

            # Optional: keep current voyage code mirror key consistent on destination
            try:
                dv = dst_db.get_config_value("current_voyage_id", "")
                if dv:
                    dst_db.set_config_value("current_voyage_code", dv)
            except Exception:
                pass

            messagebox.showinfo("Migration Complete", "All data synced successfully!")
        except Exception as e:
            messagebox.showerror("Migration Failed", f"An error occurred:\n{e}")
        finally:
            try:
                _enable_fks(dst_conn, dst_db.backend)
            except Exception:
                pass
            try:
                src_conn.close()
            except Exception:
                pass
            try:
                dst_conn.close()
            except Exception:
                pass

    def create_labeled_entry(self, parent, label, variable, row, show=None):
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky='e', pady=4)
        entry = ttk.Entry(parent, textvariable=variable, show=show)
        entry.grid(row=row, column=1, sticky='ew', pady=4)
        parent.columnconfigure(1, weight=1)

    def toggle_mysql_fields(self):
        state = "normal" if self.db_mode.get() == "mysql" else "disabled"
        for child in self.mysql_frame.winfo_children():
            child.configure(state=state)

    def _config_path(self):
        import os, sys
        if getattr(sys, "frozen", False):
            base_dir = os.path.dirname(sys.executable)
        else:
            base_dir = os.path.dirname(os.path.abspath(__file__))
        return os.path.join(base_dir, self.config_file)

    def load_config(self):
        import json, os
        path = self._config_path()
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                cfg = json.load(f)

            # Apply config values to UI
            self.db_mode.set(cfg.get("type", "sqlite"))
            self.mysql_host.set(cfg.get("host", "localhost"))
            self.mysql_port.set(str(cfg.get("port", 3306)))  # <-- cast to str
            self.mysql_db.set(cfg.get("database", ""))
            self.mysql_user.set(cfg.get("user", ""))
            self.mysql_pass.set(cfg.get("password", ""))
        else:
            # Defaults if config missing
            self.db_mode.set("sqlite")

    def save_config(self):
        import json
        path = self._config_path()
        cfg = {"type": self.db_mode.get()}
        if cfg["type"] == "mysql":
            cfg.update({
                "host": self.mysql_host.get(),
                "port": int(self.mysql_port.get()),
                "database": self.mysql_db.get(),
                "user": self.mysql_user.get(),
                "password": self.mysql_pass.get(),
            })
        with open(path, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)

        # Persist selected time zone into the DB
        self.master.db_manager.set_config_value("server_time_zone", self.tz_var.get())

        messagebox.showinfo("Saved", f"Database configuration saved to:\n{path}")
        self.destroy()

    # DatabaseSettingsWindow.test_connection()
    def test_connection(self):
        if self.db_mode.get() == "sqlite":
            messagebox.showinfo("Info", "SQLite does not require a connection test.")
            return

        try:
            import pymysql
            conn = pymysql.connect(
                host=self.mysql_host.get(),
                port=int(self.mysql_port.get()),
                user=self.mysql_user.get(),
                password=self.mysql_pass.get(),
                database=self.mysql_db.get(),
                charset="utf8mb4",
            )
            conn.close()
            messagebox.showinfo("Success", "Connection to MySQL successful!")
        except Exception as e_pymysql:
            # fallback to mysql.connector in pure mode
            try:
                import mysql.connector
                conn = mysql.connector.connect(
                    host=self.mysql_host.get(),
                    port=int(self.mysql_port.get()),
                    database=self.mysql_db.get(),
                    user=self.mysql_user.get(),
                    password=self.mysql_pass.get(),
                    use_pure=True,
                    auth_plugin='mysql_native_password',
                    connect_timeout=5
                )
                conn.close()
                messagebox.showinfo("Success", "Connection to MySQL successful!")
            except Exception as e_connector:
                messagebox.showerror("Error", f"Connection failed:\n{e_connector}")

class VoyageSettingsWindow(tk.Toplevel):
    def __init__(self, master):
        super().__init__(master)
        self.db = master.db_manager
        self.title("Voyage Settings")
        self.geometry("420x260")
        self.resizable(False, False)

        current_code = self.db.get_config_value("current_voyage_code", "") or ""
        current_id   = self.db.get_config_value("current_voyage_id", "") or ""

        frm = ttk.Frame(self, padding=16); frm.pack(fill="both", expand=True)

        ttk.Label(frm, text="Current Voyage:", font=("Helvetica", 12, "bold")).grid(row=0, column=0, sticky="w")
        self.lbl_cur = ttk.Label(frm, text=f"{current_code} (id: {current_id})" if current_code else "—")
        self.lbl_cur.grid(row=0, column=1, sticky="w", padx=(8,0))

        ttk.Label(frm, text="Voyage Code:", font=("Helvetica", 11)).grid(row=1, column=0, sticky="e", pady=(16,4))
        self.code_var = tk.StringVar(value=current_code or "")
        ttk.Entry(frm, textvariable=self.code_var, width=28).grid(row=1, column=1, sticky="w", pady=(16,4))

        ttk.Button(frm, text="Set / Create Voyage",
                   command=self._apply).grid(row=2, column=1, sticky="w", pady=(12,0))
        ttk.Button(frm, text="Close", command=self.destroy).grid(row=3, column=1, sticky="e", pady=(24,0))

    def _apply(self):
        code = (self.code_var.get() or "").strip()
        if not code:
            messagebox.showwarning("Missing", "Please enter a voyage code (e.g., SPE-2025-VOY-0123).")
            return
        vid = self.db.set_current_voyage_by_code(code)
        self.lbl_cur.config(text=f"{code} (id: {vid})")
        messagebox.showinfo("Voyage Set", f"Current voyage is now:\n{code} (id: {vid})")
class LoadingDialog(tk.Toplevel):
    def __init__(self, parent, message="Processing..."):
        super().__init__(parent)
        self.title("Please Wait")
        self.geometry("300x100")
        self.resizable(False, False)
        ttk.Label(self, text=message).pack(expand=True)
        self.grab_set()  # Make the dialog modal
        self.update()  # Ensure the window is updated
class EditAllergyDialog(tk.Toplevel):
    def __init__(self, parent, controller, allergy_id, allergy_name):
        super().__init__(parent)
        self.controller = controller
        self.allergy_id = allergy_id
        self.allergy_name = allergy_name

        self.title(f"Edit Allergy: {allergy_name}")
        self.geometry("400x200")
        self.resizable(False, False)

        ttk.Label(self, text=f"Edit Allergy: {allergy_name}", font=("Helvetica", 14)).pack(pady=10)

        form_frame = ttk.Frame(self)
        form_frame.pack(padx=20, pady=10, fill='both', expand=True)

        ttk.Label(form_frame, text="New Allergy Name:").grid(row=0, column=0, pady=5, sticky='e')
        self.new_allergy_name_var = tk.StringVar(value=allergy_name)
        new_allergy_name_entry = ttk.Entry(form_frame, textvariable=self.new_allergy_name_var, width=30)
        new_allergy_name_entry.grid(row=0, column=1, pady=5, sticky='w')

        save_button = ttk.Button(self, text="Save Changes", command=self.save_changes)
        save_button.pack(pady=20)

    def save_changes(self):
        new_allergy_name = self.new_allergy_name_var.get().strip()
        if not new_allergy_name:
            messagebox.showwarning("Validation Error", "Allergy name is required.")
            return

        success = self.controller.db_manager.edit_allergy(self.allergy_id, new_allergy_name)
        if success:
            messagebox.showinfo("Success", f"Allergy '{self.allergy_name}' updated to '{new_allergy_name}'.")
            self.destroy()
        else:
            messagebox.showerror("Error", "Allergy name already exists or failed to update.")

# ----------------------------
# Admin Application Class
# ----------------------------
class AdminApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Administration - User and Venue Management")
        self.geometry("1200x800")
        self.resizable(True, True)
        db_config = load_db_config()
        self.db_manager = DatabaseManager(db_config)

        # Ensure tables exist for the active backend (SQLite/MySQL) and correct file
        self.db_manager.setup_database()

        # Now safe to read config values
        self.db_manager.load_current_voyage_from_config()

        # Now ADMIN can be created because `users` exists
        self.ensure_admin_user_exists()
        self.iconbitmap('icons/icon_app.ico')


        # Immediately show the admin login frame instead of main panel
        self.show_admin_login_frame()
    def ensure_admin_user_exists(self):
        """Ensure ADMIN and CHEF users exists with default password"""
        existing_hash = self.db_manager.get_user_password_hash("ADMIN")
        existing_hash_chef = self.db_manager.get_user_password_hash("CHEF")
        if existing_hash is None:
            # Admin user does not exist; create with default
            success = self.db_manager.add_user("ADMIN", "123456", "admin")
            if success:
                logging.info("Default ADMIN user created with password '123456'")
            else:
                logging.error("Failed to create default ADMIN user")

        if existing_hash_chef is None:
            time.sleep(0.2)
            success_chef = self.db_manager.add_user("CHEF", "123456", "galley")
            if success_chef:
                logging.info("Default CHEF user has been created with password 123456")
            else:
                logging.error("Failed to create CHEF account")

    def show_admin_login_frame(self):
        """
        Clear the window and show AdminLoginFrame for password check.
        """
        for widget in self.winfo_children():
            widget.destroy()
        self.login_frame = AdminLoginFrame(self, controller=self)
        self.login_frame.pack(fill="both", expand=True)

    def show_admin_forced_change(self):
        """
        Show the forced password change frame if default password is still used.
        """
        for widget in self.winfo_children():
            widget.destroy()
        self.force_frame = AdminForceChangeFrame(self, controller=self)
        self.force_frame.pack(fill="both", expand=True)

    def create_main_panel(self):
        """
        After successful login and possibly forced password change, create the main UI.
        """
        for widget in self.winfo_children():
            widget.destroy()

        # Create a paned window to hold the menu and the content as before
        self.paned_window = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        self.paned_window.pack(fill='both', expand=True)

        # Menu Frame (Left side)
        self.menu_frame = ttk.Frame(self.paned_window, width=200)
        self.paned_window.add(self.menu_frame, weight=1)

        # Content Frame (Right side)
        self.content_frame = ttk.Frame(self.paned_window)
        self.paned_window.add(self.content_frame, weight=4)

        ttk.Label(self.menu_frame, text="Admin Panel", font=("Helvetica", 16)).pack(pady=20)

        ttk.Button(self.menu_frame, text="Add User", width=25, command=self.show_add_user).pack(pady=10)
        ttk.Button(self.menu_frame, text="Manage Users", width=25, command=self.show_manage_users).pack(pady=10)
        ttk.Button(self.menu_frame, text="Add Venue", width=25, command=self.show_add_venue).pack(pady=10)
        ttk.Button(self.menu_frame, text="Remove Venue", width=25, command=self.show_remove_venue).pack(pady=10)
        ttk.Button(self.menu_frame, text="Add Allergy", width=25, command=self.show_add_allergy).pack(pady=10)
        ttk.Button(self.menu_frame, text="Manage Allergies", width=25, command=self.show_manage_allergies).pack(pady=10)
        ttk.Button(self.menu_frame, text="Backup Management", width=25,
                   command=self.show_backup_management).pack(pady=10)
        #ttk.Button(self.menu_frame, text="Voyage Settings", width=25, command=self.show_voyage_settings).pack(pady=10)
        #ttk.Button(self.menu_frame, text="Import Guest Names", width=25, command=self.import_guest_manifest).pack(pady=10)
        ttk.Button(self.menu_frame, text="Audit Orders",
                   command=lambda: AuditWindow(self)).pack(fill="x", padx=12, pady=6)
        # e.g., in your admin sidebar/menu build code:
        ttk.Button(self.menu_frame, text="Start New Voyage",
                   command=lambda: StartNewVoyageWindow(self)).pack(fill="x", padx=12, pady=6)

        ttk.Button(self.menu_frame, text="Database Settings", width=25, command=self.show_database_settings).pack(
            pady=10)
        ttk.Button(self.menu_frame, text="Exit", width=25, command=self.quit).pack(pady=10)

        # Initialize Frames Dictionary for the main panel frames
        self.frames = {}

        # Initialize all management frames here as before
        for F in (AddUserFrame, ManageUsersFrame, AddVenueFrame,
                  RemoveVenueFrame, AddAllergyFrame, ManageAllergiesFrame):
            frame = F(self.content_frame, controller=self)
            self.frames[F] = frame
            frame.grid(row=0, column=0, sticky='nsew')

        # Show default frame (AddUserFrame, or pick your favorite)
        self.show_frame(AddUserFrame)
    def show_voyage_settings(self):
        VoyageSettingsWindow(self)

    def show_backup_management(self):
        BackupManagementWindow(self)

    def show_frame(self, frame_class):
        frame = self.frames[frame_class]
        frame.tkraise()

    # -------------- Admin Panel Buttons --------------
    def show_add_user(self):
        self.show_frame(AddUserFrame)

    def show_manage_users(self):
        self.show_frame(ManageUsersFrame)

    def show_database_settings(self):
        DatabaseSettingsWindow(self)

    def show_add_venue(self):
        self.show_frame(AddVenueFrame)

    def show_remove_venue(self):
        self.show_frame(RemoveVenueFrame)

    def show_add_allergy(self):
        self.show_frame(AddAllergyFrame)

    def show_manage_allergies(self):
        self.show_frame(ManageAllergiesFrame)

    def import_guest_manifest(self):
        def back_to_main():
            self.show_frame(AddUserFrame)  # veya istediğin frame neyse

        frame = ImportGuestSetupFrame(self.content_frame, self, on_complete_callback=back_to_main)
        frame.grid(row=0, column=0, sticky="nsew")  # ✅ DOĞRU


    # -------------- Reset Database Method --------------
    def reset_database(self):
        """
        Start a new voyage without wiping existing data.
        Sets a new voyage code and marks it current so all apps write/read under it.
        """
        # Suggest a code stub the admin can edit
        from datetime import datetime
        suggested = f"SPE-{datetime.now():%Y}-VOY-XXXX"

        code = tk.simpledialog.askstring("New Voyage", "Enter new voyage code:", initialvalue=suggested, parent=self)
        if not code:
            return

        vid = self.db_manager.set_current_voyage_by_code(code.strip())
        messagebox.showinfo("Voyage Created",
            f"New voyage set:\n{code} (id: {vid})\n\n"
            f"Restaurant & Galley apps will pick this up from app_config on next launch.")


# ----------------------------
# Database Initialization Function
# ----------------------------
def init_db():
    db_path = get_database_path()
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        # Create users table (with 'admin' role possible)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('admin', 'restaurant', 'galley'))
        );
        """)

        # Create venues table with meal availability columns
        cur.execute("""
        CREATE TABLE IF NOT EXISTS venues (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            breakfast_available INTEGER DEFAULT 0,
            lunch_available INTEGER DEFAULT 0,
            dinner_available INTEGER DEFAULT 1
        );
        """)

        # Create allergies table
        cur.execute("""
        CREATE TABLE IF NOT EXISTS allergies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL
        );
        """)

        cur.execute("""
                CREATE TABLE IF NOT EXISTS guests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    cabin_number TEXT,
                    last_name TEXT,
                    first_name TEXT
                );
                """)

        # Create preorders table
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
            guest_name TEXT,
            FOREIGN KEY (venue_id) REFERENCES venues(id) ON DELETE CASCADE
        );
        """)

        # app_config table for various settings
        cur.execute("""
        CREATE TABLE IF NOT EXISTS app_config (
            key TEXT PRIMARY KEY,
            value TEXT
        );
        """)

        conn.commit()
        logging.info("Database initialized successfully.")
    except sqlite3.Error as e:
        logging.error(f"Error initializing database: {e}")
    finally:
        conn.close()

# ----------------------------
# Main Function
# ----------------------------
def main():
    # Initialize DB
    app = AdminApp()
    app.mainloop()

if __name__ == "__main__":
    main()
