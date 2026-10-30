"""
database.py  –  BusGo data layer
Real Indian city routes + real bus operator names.
"""
import sqlite3, os, random, string
from datetime import datetime
from contextlib import contextmanager

DB_PATH = os.path.join(os.path.dirname(__file__), "busgo.db")

@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def init_db():
    with get_conn() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS routes (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            route_name  TEXT UNIQUE NOT NULL,
            origin      TEXT NOT NULL,
            destination TEXT NOT NULL,
            distance_km REAL NOT NULL,
            duration_h  REAL NOT NULL,
            base_fare   REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS buses (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            operator_name  TEXT NOT NULL,
            bus_type       TEXT NOT NULL DEFAULT 'AC Sleeper',
            total_seats    INTEGER NOT NULL DEFAULT 40,
            route_id       INTEGER NOT NULL REFERENCES routes(id),
            departure_time TEXT NOT NULL,
            arrival_time   TEXT NOT NULL,
            travel_date    TEXT NOT NULL,
            status         TEXT NOT NULL DEFAULT 'Active'
        );
        CREATE TABLE IF NOT EXISTS seats (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            bus_id      INTEGER NOT NULL REFERENCES buses(id),
            seat_number TEXT NOT NULL,
            seat_type   TEXT NOT NULL DEFAULT 'Window',
            is_booked   INTEGER NOT NULL DEFAULT 0,
            UNIQUE(bus_id, seat_number)
        );
        CREATE TABLE IF NOT EXISTS passengers (
            id      INTEGER PRIMARY KEY AUTOINCREMENT,
            name    TEXT NOT NULL,
            age     INTEGER NOT NULL,
            gender  TEXT NOT NULL,
            phone   TEXT NOT NULL,
            email   TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS bookings (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            booking_ref    TEXT UNIQUE NOT NULL,
            passenger_id   INTEGER NOT NULL REFERENCES passengers(id),
            bus_id         INTEGER NOT NULL REFERENCES buses(id),
            seat_id        INTEGER NOT NULL REFERENCES seats(id),
            booking_time   TEXT NOT NULL,
            status         TEXT NOT NULL DEFAULT 'Confirmed',
            fare_paid      REAL NOT NULL,
            payment_method TEXT NOT NULL DEFAULT 'UPI'
        );
        CREATE TABLE IF NOT EXISTS booking_history (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            bus_id      INTEGER NOT NULL,
            route_id    INTEGER NOT NULL,
            travel_date TEXT NOT NULL,
            passengers  INTEGER NOT NULL DEFAULT 0,
            revenue     REAL NOT NULL DEFAULT 0.0
        );
        """)
    _seed()

def _seed():
    with get_conn() as c:
        if c.execute("SELECT COUNT(*) FROM routes").fetchone()[0] > 0:
            return

        # 15 real Indian city routes
        routes = [
            ("Mumbai to Pune",           "Mumbai",    "Pune",          148, 3.0,  350),
            ("Pune to Mumbai",           "Pune",      "Mumbai",        148, 3.0,  350),
            ("Mumbai to Nagpur",         "Mumbai",    "Nagpur",        835, 13.5, 1100),
            ("Bengaluru to Chennai",     "Bengaluru", "Chennai",       346, 6.5,  650),
            ("Chennai to Bengaluru",     "Chennai",   "Bengaluru",     346, 6.5,  650),
            ("Hyderabad to Bengaluru",   "Hyderabad", "Bengaluru",     570, 9.5,  900),
            ("Delhi to Jaipur",          "Delhi",     "Jaipur",        281, 5.5,  550),
            ("Jaipur to Delhi",          "Jaipur",    "Delhi",         281, 5.5,  550),
            ("Delhi to Agra",            "Delhi",     "Agra",          210, 4.0,  420),
            ("Kolkata to Bhubaneswar",   "Kolkata",   "Bhubaneswar",   441, 7.5,  750),
            ("Ahmedabad to Mumbai",      "Ahmedabad", "Mumbai",        524, 8.5,  880),
            ("Mumbai to Goa",            "Mumbai",    "Goa",           589, 9.5,  950),
            ("Hyderabad to Chennai",     "Hyderabad", "Chennai",       626, 10.0, 980),
            ("Bengaluru to Hyderabad",   "Bengaluru", "Hyderabad",     570, 9.5,  900),
            ("Pune to Bengaluru",        "Pune",      "Bengaluru",     838, 13.0, 1150),
        ]
        c.executemany(
            "INSERT INTO routes (route_name,origin,destination,distance_km,duration_h,base_fare) VALUES (?,?,?,?,?,?)",
            routes,
        )

        # Real Indian bus operators per route
        # (operator_name, bus_type, seats, route_id, dep, arr)
        buses_tmpl = [
            # Mumbai - Pune (route 1)
            ("Neeta Travels",      "AC Sleeper",      40, 1, "06:00","09:00"),
            ("VRL Travels",        "Luxury Volvo",    30, 1, "08:00","11:00"),
            ("MSRTC Shivneri",     "AC Semi-Sleeper", 45, 1, "10:30","13:30"),
            ("SRS Travels",        "Non-AC Seater",   55, 1, "14:00","17:00"),
            # Pune - Mumbai (route 2)
            ("Neeta Travels",      "AC Sleeper",      40, 2, "07:00","10:00"),
            ("Konduskar Travels",  "AC Semi-Sleeper", 45, 2, "09:00","12:00"),
            # Mumbai - Nagpur (route 3)
            ("MSRTC Nagpur Express","AC Sleeper",     40, 3, "20:00","09:30"),
            ("Orange Travels",     "Luxury Volvo",    30, 3, "21:00","10:30"),
            # Bengaluru - Chennai (route 4)
            ("KSRTC Rajahamsa",    "AC Sleeper",      40, 4, "21:00","03:30"),
            ("SRS Travels",        "Non-AC Seater",   55, 4, "22:30","05:00"),
            ("VRL Travels",        "AC Semi-Sleeper", 45, 4, "23:00","05:30"),
            # Chennai - Bengaluru (route 5)
            ("TNSTC Express",      "AC Sleeper",      40, 5, "21:30","04:00"),
            ("Patel Travels",      "Luxury Volvo",    30, 5, "22:00","04:30"),
            # Hyderabad - Bengaluru (route 6)
            ("TSRTC Garuda Plus",  "Luxury Volvo",    30, 6, "20:30","06:00"),
            ("VRL Travels",        "AC Sleeper",      40, 6, "21:30","07:00"),
            # Delhi - Jaipur (route 7)
            ("RSRTC Volvo",        "Luxury Volvo",    30, 7, "07:00","12:30"),
            ("Raj National Express","AC Sleeper",     40, 7, "09:00","14:30"),
            ("National Travels",   "Non-AC Seater",   55, 7, "11:00","16:30"),
            # Jaipur - Delhi (route 8)
            ("RSRTC Volvo",        "Luxury Volvo",    30, 8, "08:00","13:30"),
            ("Patel Travels",      "AC Semi-Sleeper", 45, 8, "10:00","15:30"),
            # Delhi - Agra (route 9)
            ("UP SRTC Agra Express","AC Sleeper",     40, 9, "06:30","10:30"),
            ("Raj National Express","Non-AC Seater",  55, 9, "09:00","13:00"),
            # Kolkata - Bhubaneswar (route 10)
            ("OSRTC Express",      "AC Sleeper",      40,10, "22:00","05:30"),
            ("Shyamoli Paribahan", "Non-AC Seater",   50,10, "23:00","06:30"),
            # Ahmedabad - Mumbai (route 11)
            ("GSRTC Volvo",        "Luxury Volvo",    30,11, "21:00","05:30"),
            ("Patel Travels",      "AC Sleeper",      40,11, "22:00","06:30"),
            # Mumbai - Goa (route 12)
            ("Paulo Travels",      "Luxury Volvo",    30,12, "16:00","01:30"),
            ("Kadamba Transport",  "AC Sleeper",      40,12, "17:00","02:30"),
            ("Neeta Travels",      "Non-AC Seater",   55,12, "18:00","03:30"),
            # Hyderabad - Chennai (route 13)
            ("TSRTC Garuda",       "AC Sleeper",      40,13, "19:00","05:00"),
            ("Orange Travels",     "Luxury Volvo",    30,13, "20:00","06:00"),
            # Bengaluru - Hyderabad (route 14)
            ("KSRTC Airavata",     "Luxury Volvo",    30,14, "20:00","05:30"),
            ("SRS Travels",        "AC Sleeper",      40,14, "21:00","06:30"),
            # Pune - Bengaluru (route 15)
            ("VRL Travels",        "AC Sleeper",      40,15, "18:00","07:00"),
            ("Konduskar Travels",  "AC Semi-Sleeper", 45,15, "19:00","08:00"),
        ]

        travel_dates = ["2026-10-27","2026-10-28","2026-10-29","2026-10-30"]
        for td in travel_dates:
            for tmpl in buses_tmpl:
                c.execute(
                    "INSERT INTO buses (operator_name,bus_type,total_seats,route_id,departure_time,arrival_time,travel_date,status) VALUES (?,?,?,?,?,?,?,?)",
                    (*tmpl, td, "Active"),
                )

        # Seats for all buses
        all_buses = c.execute("SELECT id,total_seats FROM buses").fetchall()
        for bus in all_buses:
            bid, total = bus["id"], bus["total_seats"]
            for i in range(1, total + 1):
                side   = "L" if i % 2 == 1 else "R"
                row    = (i + 1) // 2
                snum   = f"{side}{row:02d}"
                stype  = "Window" if side == "L" else "Aisle"
                booked = 1 if random.random() < 0.28 else 0
                try:
                    c.execute(
                        "INSERT INTO seats (bus_id,seat_number,seat_type,is_booked) VALUES (?,?,?,?)",
                        (bid, snum, stype, booked),
                    )
                except sqlite3.IntegrityError:
                    pass

        # Booking history seed
        hist = [
            (1, 1,"2026-10-20",35,12250),(1, 1,"2026-10-21",28, 9800),
            (4, 4,"2026-10-20",38,24700),(4, 4,"2026-10-21",32,20800),
            (7, 7,"2026-10-20",30,16500),(7, 7,"2026-10-22",40,22000),
            (10,6,"2026-10-20",26,23400),(10,6,"2026-10-21",28,25200),
            (11,7,"2026-10-22",42,23100),(11,7,"2026-10-23",48,26400),
            (21,11,"2026-10-20",36,31680),(21,11,"2026-10-21",34,29920),
            (25,12,"2026-10-20",25,23750),(25,12,"2026-10-22",28,26600),
            (29,13,"2026-10-21",38,37240),(31,14,"2026-10-21",40,36000),
            (3, 3,"2026-10-22",38,41800),(6, 6,"2026-10-22",28,25200),
            (2, 1,"2026-10-23",45,15750),(5, 2,"2026-10-23",32,11200),
        ]
        c.executemany(
            "INSERT INTO booking_history (bus_id,route_id,travel_date,passengers,revenue) VALUES (?,?,?,?,?)",
            hist,
        )


# ── Query helpers ──────────────────────────────────────────────────────────────
def get_all_routes():
    with get_conn() as c:
        return [dict(r) for r in c.execute("SELECT * FROM routes ORDER BY route_name").fetchall()]


def get_popular_routes():
    with get_conn() as c:
        rows = c.execute("""
            SELECT r.route_name, r.origin, r.destination,
                   r.distance_km, r.duration_h, r.base_fare,
                   COALESCE(SUM(bh.passengers),0) AS total_passengers
            FROM routes r
            LEFT JOIN booking_history bh ON bh.route_id = r.id
            GROUP BY r.id ORDER BY total_passengers DESC LIMIT 6
        """).fetchall()
        return [dict(r) for r in rows]


def search_buses(route_name, travel_date):
    with get_conn() as c:
        rows = c.execute("""
            SELECT b.id, b.operator_name, b.bus_type, b.total_seats,
                   b.departure_time, b.arrival_time, b.travel_date, b.status,
                   r.route_name, r.origin, r.destination,
                   r.distance_km, r.duration_h, r.base_fare, r.id AS route_id,
                   (SELECT COUNT(*) FROM seats s WHERE s.bus_id=b.id AND s.is_booked=0) AS available_seats,
                   (SELECT COUNT(*) FROM seats s WHERE s.bus_id=b.id AND s.is_booked=1) AS booked_seats
            FROM buses b JOIN routes r ON b.route_id=r.id
            WHERE r.route_name=? AND b.travel_date=? AND b.status='Active'
            ORDER BY b.departure_time
        """, (route_name, travel_date)).fetchall()
        return [dict(r) for r in rows]


def get_bus_seats(bus_id):
    with get_conn() as c:
        return [dict(r) for r in c.execute(
            "SELECT * FROM seats WHERE bus_id=? ORDER BY seat_number", (bus_id,)
        ).fetchall()]


def create_booking(name, age, gender, phone, email, bus_id, seat_id, payment_method):
    ref = "BUS" + "".join(random.choices(string.ascii_uppercase + string.digits, k=7))
    with get_conn() as c:
        seat = c.execute("SELECT * FROM seats WHERE id=?", (seat_id,)).fetchone()
        if not seat or seat["is_booked"]:
            return None, "Seat already taken. Please pick another seat."
        bus = c.execute(
            "SELECT b.*, r.base_fare FROM buses b JOIN routes r ON b.route_id=r.id WHERE b.id=?",
            (bus_id,),
        ).fetchone()
        if not bus:
            return None, "Invalid bus."
        fare = bus["base_fare"]
        cur = c.execute(
            "INSERT INTO passengers (name,age,gender,phone,email) VALUES (?,?,?,?,?)",
            (name, int(age), gender, phone, email),
        )
        pid = cur.lastrowid
        c.execute("UPDATE seats SET is_booked=1 WHERE id=?", (seat_id,))
        c.execute("""
            INSERT INTO bookings
              (booking_ref,passenger_id,bus_id,seat_id,booking_time,status,fare_paid,payment_method)
            VALUES (?,?,?,?,?,?,?,?)
        """, (ref, pid, bus_id, seat_id, datetime.now().isoformat(), "Confirmed", fare, payment_method))
        return ref, None


def get_booking(ref):
    with get_conn() as c:
        row = c.execute("""
            SELECT bk.booking_ref, bk.booking_time, bk.status,
                   bk.fare_paid, bk.payment_method,
                   p.name, p.age, p.gender, p.phone, p.email,
                   b.operator_name, b.bus_type, b.departure_time,
                   b.arrival_time, b.travel_date,
                   r.route_name, r.origin, r.destination,
                   s.seat_number, s.seat_type
            FROM bookings bk
            JOIN passengers p ON bk.passenger_id=p.id
            JOIN buses b      ON bk.bus_id=b.id
            JOIN routes r     ON b.route_id=r.id
            JOIN seats s      ON bk.seat_id=s.id
            WHERE bk.booking_ref=?
        """, (ref,)).fetchone()
        return dict(row) if row else None


def cancel_booking(ref):
    with get_conn() as c:
        bk = c.execute(
            "SELECT id,seat_id FROM bookings WHERE booking_ref=? AND status='Confirmed'", (ref,)
        ).fetchone()
        if not bk:
            return False, "Booking not found or already cancelled."
        c.execute("UPDATE bookings SET status='Cancelled' WHERE id=?", (bk["id"],))
        c.execute("UPDATE seats SET is_booked=0 WHERE id=?", (bk["seat_id"],))
        return True, "Booking cancelled. Refund will be processed in 5-7 business days."


def get_dashboard_stats():
    with get_conn() as c:
        s = {}
        s["total_bookings"] = c.execute(
            "SELECT COUNT(*) FROM bookings WHERE status='Confirmed'"
        ).fetchone()[0]
        s["total_revenue"] = c.execute(
            "SELECT COALESCE(SUM(fare_paid),0) FROM bookings WHERE status='Confirmed'"
        ).fetchone()[0]
        s["total_routes"] = c.execute("SELECT COUNT(*) FROM routes").fetchone()[0]
        s["total_buses"]  = c.execute("SELECT COUNT(DISTINCT operator_name) FROM buses").fetchone()[0]
        s["recent_bookings"] = [dict(r) for r in c.execute("""
            SELECT bk.booking_ref, p.name, r.route_name,
                   b.travel_date, bk.fare_paid, bk.status
            FROM bookings bk
            JOIN passengers p ON bk.passenger_id=p.id
            JOIN buses b      ON bk.bus_id=b.id
            JOIN routes r     ON b.route_id=r.id
            ORDER BY bk.booking_time DESC LIMIT 10
        """).fetchall()]
        s["route_popularity"] = [dict(r) for r in c.execute("""
            SELECT r.route_name, r.origin, r.destination,
                   COUNT(bk.id) AS bookings,
                   COALESCE(SUM(bk.fare_paid),0) AS revenue
            FROM routes r
            LEFT JOIN buses b  ON b.route_id=r.id
            LEFT JOIN bookings bk ON bk.bus_id=b.id AND bk.status='Confirmed'
            GROUP BY r.id ORDER BY bookings DESC
        """).fetchall()]
        s["history"] = [dict(r) for r in c.execute(
            "SELECT * FROM booking_history ORDER BY travel_date DESC LIMIT 30"
        ).fetchall()]
        return s


def get_route_analytics(route_id):
    import pandas as pd
    with get_conn() as c:
        rows = c.execute(
            "SELECT travel_date,passengers,revenue FROM booking_history WHERE route_id=? ORDER BY travel_date",
            (route_id,),
        ).fetchall()
    if not rows:
        return {"dates": [], "passengers": [], "revenue": []}
    df = pd.DataFrame([dict(r) for r in rows])
    return {"dates": df["travel_date"].tolist(),
            "passengers": df["passengers"].tolist(),
            "revenue": df["revenue"].tolist()}
