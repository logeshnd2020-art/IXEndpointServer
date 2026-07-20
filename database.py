import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATABASE = BASE_DIR / "runtime" / "database" / "ixendpointserver.db"


def get_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def initialize_database():

    conn = get_connection()
    cur = conn.cursor()

    # ------------------------------------------------------------------
    # Devices
    # ------------------------------------------------------------------
    cur.execute("""
    CREATE TABLE IF NOT EXISTS Devices (

        DeviceID INTEGER PRIMARY KEY AUTOINCREMENT,

        Hostname TEXT,

        Username TEXT,

        Serial TEXT UNIQUE,

        Model TEXT,

        OSVersion TEXT,

        IPAddress TEXT,

        AgentVersion TEXT,

        LastSeen DATETIME DEFAULT CURRENT_TIMESTAMP,

        Status TEXT,

        CPU REAL,

        Memory REAL,

        Disk REAL

    );
    """)

    # ------------------------------------------------------------------
    # Applications
    # ------------------------------------------------------------------
    cur.execute("""
    CREATE TABLE IF NOT EXISTS Applications (

        ApplicationID INTEGER PRIMARY KEY AUTOINCREMENT,

        DeviceID INTEGER NOT NULL,

        AppName TEXT,

        Version TEXT,

        BundleID TEXT,

        InstallPath TEXT,

        LastSeen DATETIME DEFAULT CURRENT_TIMESTAMP,

        FOREIGN KEY(DeviceID)
            REFERENCES Devices(DeviceID)

    );
    """)

    # ------------------------------------------------------------------
    # Inventory
    # ------------------------------------------------------------------
    cur.execute("""
    CREATE TABLE IF NOT EXISTS Inventory (

        InventoryID INTEGER PRIMARY KEY AUTOINCREMENT,

        DeviceID INTEGER NOT NULL,

        Model TEXT,

        ModelIdentifier TEXT,

        CPUModel TEXT,

        MemoryInstalled TEXT,

        DiskSize TEXT,

        OSVersion TEXT,

        BuildVersion TEXT,

        Architecture TEXT,

        MACAddress TEXT,

        Gateway TEXT,

        DNS TEXT,

        WiFiSSID TEXT,

        FileVault TEXT,

        Firewall TEXT,

        Gatekeeper TEXT,

        SIP TEXT,

        LastInventorySync DATETIME DEFAULT CURRENT_TIMESTAMP,

        FOREIGN KEY(DeviceID)
            REFERENCES Devices(DeviceID)

    );
    """)

    # ------------------------------------------------------------------
    # Activity Events
    # ------------------------------------------------------------------
    cur.execute("""
    CREATE TABLE IF NOT EXISTS ActivityEvents (

        EventID INTEGER PRIMARY KEY AUTOINCREMENT,

        DeviceID INTEGER NOT NULL,

        Username TEXT,

        EventType TEXT NOT NULL,

        EventName TEXT NOT NULL,

        EventValue TEXT,

        EventTime DATETIME NOT NULL,

        ReceivedAt DATETIME DEFAULT CURRENT_TIMESTAMP,

        FOREIGN KEY(DeviceID)
            REFERENCES Devices(DeviceID)

    );
    """)

    conn.commit()
    conn.close()
