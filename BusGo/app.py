"""
app.py  –  BusGo | Real-Time Smart Bus Booking
Fixed: all bus cards use native Streamlit components (no raw HTML rendering issue).
Real Indian operator names, saffron-orange theme.

Run:  streamlit run app.py
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import date, timedelta
import os, sys, time

sys.path.insert(0, os.path.dirname(__file__))
import database as db
import ml_engine as ml

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="BusGo – India's Smart Bus Network",
    page_icon="🚌",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Minimal CSS (only safe global styles, NO complex HTML cards) ──────────────
st.markdown("""
<style>
/* Sidebar */
section[data-testid="stSidebar"] {
    background: #0d1b2a !important;
}
section[data-testid="stSidebar"] * { color: #cbd5e1 !important; }
section[data-testid="stSidebar"] .stButton > button {
    background: transparent !important;
    border: 1px solid #1e3a5f !important;
    color: #94a3b8 !important;
    border-radius: 10px !important;
    padding: 0.45rem 1rem !important;
    font-size: 0.88rem !important;
    width: 100%;
    text-align: left !important;
    margin-bottom: 4px;
    transition: all 0.2s;
}
section[data-testid="stSidebar"] .stButton > button:hover {
    background: #1e3a5f !important;
    border-color: #f97316 !important;
    color: #f97316 !important;
}

/* Metric cards */
div[data-testid="metric-container"] {
    background: #fff;
    border: 1px solid #e2e8f0;
    border-left: 4px solid #f97316;
    border-radius: 12px;
    padding: 1rem 1.2rem;
    box-shadow: 0 2px 8px rgba(0,0,0,0.06);
}
div[data-testid="metric-container"] label { color: #64748b !important; font-size: .8rem; }
div[data-testid="metric-container"] [data-testid="stMetricValue"] { color: #0d1b2a !important; font-weight: 800; }

/* Primary buttons */
.stButton > button[kind="primary"] {
    background: linear-gradient(135deg, #f97316, #ea580c) !important;
    color: white !important; border: none !important;
    border-radius: 10px !important; font-weight: 700 !important;
    box-shadow: 0 3px 10px rgba(249,115,22,0.4) !important;
}
.stButton > button[kind="primary"]:hover { opacity: 0.92; }

/* Progress bar */
.stProgress > div > div { background: linear-gradient(90deg,#f97316,#eab308) !important; }

/* Tabs */
.stTabs [data-baseweb="tab-list"] { gap: 4px; }
.stTabs [data-baseweb="tab"] {
    border-radius: 8px !important; font-weight: 600 !important;
    color: #64748b !important; background: #f1f5f9 !important;
}
.stTabs [aria-selected="true"] {
    background: #f97316 !important; color: white !important;
}

/* Dividers */
hr { border-color: #e2e8f0 !important; margin: 1rem 0; }

/* Streamlit containers as cards */
div[data-testid="stVerticalBlock"] > div[data-testid="stVerticalBlock"] {
    border-radius: 12px;
}

/* Hide default footer */
#MainMenu, footer, header { visibility: hidden; }
</style>
""", unsafe_allow_html=True)


# ── Init ───────────────────────────────────────────────────────────────────────
@st.cache_resource
def boot():
    db.init_db()
    ml.get_model()
    return True

boot()


# ── Session helpers ────────────────────────────────────────────────────────────
def ss(k, d=None):
    if k not in st.session_state:
        st.session_state[k] = d
    return st.session_state[k]

ss("page",      "home")
ss("sel_bus",   None)
ss("sel_seat",  None)
ss("bkg_ref",   None)
ss("results",   [])
ss("cancel_bk", None)


# ── Operator icon map ──────────────────────────────────────────────────────────
OPERATOR_ICONS = {
    "VRL Travels":          "🔵",
    "KSRTC Rajahamsa":      "🟢",
    "KSRTC Airavata":       "🟢",
    "MSRTC Shivneri":       "🟠",
    "MSRTC Nagpur Express": "🟠",
    "SRS Travels":          "🔴",
    "Neeta Travels":        "🟣",
    "Konduskar Travels":    "🟤",
    "Paulo Travels":        "⚡",
    "Kadamba Transport":    "🌊",
    "Orange Travels":       "🟡",
    "TSRTC Garuda Plus":    "🦅",
    "TSRTC Garuda":         "🦅",
    "RSRTC Volvo":          "🔷",
    "Raj National Express": "🌟",
    "National Travels":     "🚀",
    "TNSTC Express":        "🟩",
    "Patel Travels":        "💫",
    "UP SRTC Agra Express": "🏰",
    "OSRTC Express":        "🌿",
    "Shyamoli Paribahan":   "🌺",
    "GSRTC Volvo":          "💎",
}

TYPE_EMOJI = {
    "AC Sleeper":       "🛏️ AC Sleeper",
    "Non-AC Seater":    "💺 Non-AC Seater",
    "AC Semi-Sleeper":  "🪑 AC Semi-Sleeper",
    "Luxury Volvo":     "✨ Luxury Volvo",
}

def fmt_dur(h):
    hh = int(h); mm = int((h - hh) * 60)
    return f"{hh}h {mm:02d}m" if mm else f"{hh}h"


# ── Sidebar navigation ────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🚌 BusGo")
    st.markdown("*India's Smart Bus Network*")
    st.markdown("---")

    NAV = [
        ("🏠  Dashboard",          "home"),
        ("🔍  Search & Book",      "search"),
        ("🎫  My Bookings",        "bookings"),
        ("❌  Cancel Booking",     "cancel"),
        ("📊  Analytics",          "analytics"),
        ("🤖  AI Demand Predictor","predictor"),
    ]
    for label, key in NAV:
        if st.button(label, key=f"nav_{key}", use_container_width=True,
                     type="primary" if st.session_state["page"] == key else "secondary"):
            for k in ("page","sel_bus","sel_seat","cancel_bk"):
                st.session_state[k] = key if k == "page" else None
            st.rerun()

    st.markdown("---")
    st.markdown("""
**15 Routes**  |  **20+ Operators**  
🔒 Secure Booking  |  ⚡ Live Availability  
🤖 AI-Powered Pricing
""")


# ════════════════════════════════════════════════════════════════════
#  HOME / DASHBOARD
# ════════════════════════════════════════════════════════════════════
def page_home():
    # Hero using st.markdown with SAFE simple HTML (just color/font)
    st.markdown(
        "<h1 style='color:#0d1b2a; font-size:2.4rem; font-weight:900; margin-bottom:0;'>"
        "🚌 <span style='color:#f97316;'>BusGo</span> – Book Smarter, Travel Better</h1>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<p style='color:#64748b; font-size:1rem; margin-top:.3rem; margin-bottom:1.5rem;'>"
        "Real-time seat availability · AI demand prediction · 15+ routes across India</p>",
        unsafe_allow_html=True,
    )

    stats = db.get_dashboard_stats()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("✅ Confirmed Bookings",  stats["total_bookings"],   "Live")
    c2.metric("💰 Total Revenue",      f"Rs {stats['total_revenue']:,.0f}", "INR")
    c3.metric("🛣️ Active Routes",      stats["total_routes"],     "Nationwide")
    c4.metric("🚌 Bus Operators",      stats["total_buses"],      "Partners")

    st.markdown("---")
    left, right = st.columns([1.5, 1], gap="large")

    with left:
        st.subheader("🔍 Quick Bus Search")
        routes = [r["route_name"] for r in db.get_all_routes()]
        with st.form("qs"):
            r = st.selectbox("Select Route", routes)
            d = st.date_input("Travel Date", value=date.today(),
                              min_value=date.today(),
                              max_value=date.today() + timedelta(30))
            if st.form_submit_button("Search Buses →", type="primary", use_container_width=True):
                st.session_state.update({"search_route": r, "search_date": str(d),
                                         "page": "search", "results": []})
                st.rerun()

        st.markdown("---")
        st.subheader("📋 Recent Bookings")
        if stats["recent_bookings"]:
            df = pd.DataFrame(stats["recent_bookings"])
            df["fare_paid"] = df["fare_paid"].apply(lambda x: f"Rs {x:,.0f}")
            df.columns = ["Ref #", "Passenger", "Route", "Date", "Fare", "Status"]
            st.dataframe(df, use_container_width=True, hide_index=True, height=260)
        else:
            st.info("No bookings yet. Search for a bus above to get started!")

    with right:
        st.subheader("🔥 Popular Routes")
        for r in db.get_popular_routes():
            with st.container(border=True):
                col_info, col_fare = st.columns([2, 1])
                with col_info:
                    st.markdown(
                        f"**{r['origin']} → {r['destination']}**  \n"
                        f"📏 {r['distance_km']} km &nbsp; ⏱ {fmt_dur(r['duration_h'])}"
                    )
                with col_fare:
                    st.markdown(
                        f"<div style='text-align:right; color:#f97316; font-weight:800; font-size:1.1rem;'>"
                        f"from Rs {int(r['base_fare']):,}</div>",
                        unsafe_allow_html=True,
                    )


# ════════════════════════════════════════════════════════════════════
#  SEARCH & BOOK
# ════════════════════════════════════════════════════════════════════
def page_search():
    # Step bar (native)
    steps = ["1 · Route", "2 · Bus", "3 · Seat", "4 · Details", "5 · Confirm"]
    active = 1 if st.session_state["results"] else 0
    if st.session_state["sel_bus"]:
        active = 2
    s_cols = st.columns(len(steps))
    for i, (col, lbl) in enumerate(zip(s_cols, steps)):
        color = "#f97316" if i == active else ("#22c55e" if i < active else "#cbd5e1")
        col.markdown(
            f"<div style='text-align:center; font-size:.78rem; font-weight:700; "
            f"color:{color}; border-bottom:3px solid {color}; padding-bottom:6px;'>{lbl}</div>",
            unsafe_allow_html=True,
        )
    st.markdown("<div style='height:.5rem'></div>", unsafe_allow_html=True)

    st.subheader("🔍 Find Buses")
    routes = [r["route_name"] for r in db.get_all_routes()]
    today  = date.today()

    with st.form("sf"):
        fc1, fc2, fc3 = st.columns([2.2, 1.5, 0.9])
        with fc1:
            rsel = st.selectbox("Route", routes,
                index=routes.index(st.session_state.get("search_route", routes[0]))
                      if st.session_state.get("search_route") in routes else 0)
        with fc2:
            dsel = st.date_input("Travel Date",
                value=date.fromisoformat(st.session_state.get("search_date", str(today))),
                min_value=today, max_value=today + timedelta(30))
        with fc3:
            st.write(""); searched = st.form_submit_button("Search", type="primary", use_container_width=True)

    if searched:
        res = db.search_buses(rsel, str(dsel))
        st.session_state.update({"results": res, "search_route": rsel,
                                  "search_date": str(dsel), "sel_bus": None, "sel_seat": None})

    results = st.session_state["results"]
    if not results:
        st.info("🔎 Select a route and date above, then click Search.")
        return

    route_lbl = st.session_state.get("search_route", "")
    date_lbl  = st.session_state.get("search_date", "")
    st.success(f"🚌  {len(results)} bus(es) found for **{route_lbl}** on **{date_lbl}**")

    sel_bus = st.session_state["sel_bus"]

    for bus in results:
        avail   = bus["available_seats"]
        occ_pct = (bus["booked_seats"] / bus["total_seats"]) * 100
        is_sel  = sel_bus and sel_bus["id"] == bus["id"]

        demand = ml.predict_demand(
            bus["route_id"], bus["distance_km"], bus["duration_h"],
            bus["base_fare"], bus["travel_date"], bus["booked_seats"])
        dyn_fare = round(bus["base_fare"] * demand["mult"])

        icon = OPERATOR_ICONS.get(bus["operator_name"], "🚌")
        type_lbl = TYPE_EMOJI.get(bus["bus_type"], bus["bus_type"])

        # ── Bus card using st.container (native, always renders) ──
        with st.container(border=True):
            # Row 1: Operator name + fare
            r1a, r1b = st.columns([3, 1])
            with r1a:
                st.markdown(
                    f"### {icon} {bus['operator_name']}",
                )
                st.caption(f"{type_lbl}  ·  {bus['bus_number'] if hasattr(bus,'bus_number') else ''}")
            with r1b:
                st.markdown(
                    f"<div style='text-align:right;'>"
                    f"<div style='font-size:1.7rem; font-weight:900; color:#f97316;'>Rs {dyn_fare:,}</div>"
                    + (f"<div style='font-size:.75rem; color:#ef4444;'>↑ from Rs {int(bus['base_fare']):,}</div>"
                       if demand["mult"] > 1 else
                       f"<div style='font-size:.75rem; color:#22c55e;'>Best price</div>")
                    + "</div>",
                    unsafe_allow_html=True,
                )

            # Row 2: Journey info chips
            r2a, r2b, r2c, r2d = st.columns(4)
            r2a.markdown(f"🕐 **{bus['departure_time']}** → **{bus['arrival_time']}**")
            r2b.markdown(f"📏 {bus['distance_km']} km")
            r2c.markdown(f"⏱ {fmt_dur(bus['duration_h'])}")
            r2d.markdown(f"📅 {bus['travel_date']}")

            # Row 3: AI demand + availability
            r3a, r3b = st.columns([2, 1])
            with r3a:
                demand_color = demand["color"]
                st.markdown(
                    f"<span style='background:{demand_color}22; color:{demand_color}; "
                    f"font-weight:700; padding:3px 12px; border-radius:20px; font-size:.82rem;'>"
                    f"🤖 {demand['label']} Demand</span>"
                    f"<span style='color:#64748b; font-size:.82rem; margin-left:.5rem;'>{demand['tip']}</span>",
                    unsafe_allow_html=True,
                )
            with r3b:
                if avail == 0:
                    st.markdown("🔴 **Fully Booked**")
                elif avail <= 6:
                    st.markdown(f"🟡 **Only {avail} seats left!**")
                else:
                    st.markdown(f"🟢 **{avail} seats available**")

            # Row 4: Occupancy bar + Select button
            p_col, b_col = st.columns([3.5, 1])
            with p_col:
                st.progress(min(occ_pct / 100, 1.0))
                st.caption(f"Occupancy: {occ_pct:.0f}%  ({bus['booked_seats']}/{bus['total_seats']} seats filled)")
            with b_col:
                if avail > 0:
                    btn_lbl = "✔ Selected" if is_sel else "Select →"
                    if st.button(btn_lbl, key=f"sel_{bus['id']}", type="primary"):
                        st.session_state["sel_bus"]  = {**bus, "dyn_fare": dyn_fare}
                        st.session_state["sel_seat"] = None
                        st.rerun()
                else:
                    st.button("Bus Full", key=f"f_{bus['id']}", disabled=True)

    # ── Seat Selection ─────────────────────────────────────────────
    sel_bus = st.session_state["sel_bus"]
    if not sel_bus:
        return

    st.markdown("---")
    st.subheader(f"💺 Choose Your Seat — {sel_bus['operator_name']}")
    st.caption(f"{sel_bus['route_name']}  ·  {sel_bus['departure_time']} → {sel_bus['arrival_time']}  ·  Rs {sel_bus['dyn_fare']:,}")

    seats = db.get_bus_seats(sel_bus["id"])
    avail_map = {f"{s['seat_number']} ({s['seat_type']})": s for s in seats if not s["is_booked"]}

    leg1, leg2, leg3 = st.columns(3)
    leg1.markdown("🟢 Available")
    leg2.markdown("🔴 Booked")
    leg3.markdown("🟡 Your Pick")

    sel_seat = st.session_state["sel_seat"]
    chosen = st.selectbox("Select seat number", ["— choose a seat —"] + list(avail_map.keys()), key="seat_dd")
    if chosen != "— choose a seat —":
        st.session_state["sel_seat"] = avail_map[chosen]
        sel_seat = st.session_state["sel_seat"]

    # Visual seat map — 4 seats per row, aisle after col 2
    COLS = 4
    rows = [seats[i:i+COLS] for i in range(0, len(seats), COLS)]
    map_html = "<div style='font-family:monospace; line-height:2;'>"
    for row in rows:
        map_html += "<div style='display:flex; gap:4px; margin-bottom:3px;'>"
        for idx, s in enumerate(row):
            if idx == 2:
                map_html += "<div style='width:16px;'></div>"
            lbl = s["seat_number"]
            if s["is_booked"]:
                bg, fc = "#fee2e2","#dc2626"
            elif sel_seat and sel_seat["id"] == s["id"]:
                bg, fc = "#fef3c7","#d97706"
            else:
                bg, fc = "#dcfce7","#16a34a"
            map_html += (
                f"<div style='background:{bg}; color:{fc}; border-radius:6px; "
                f"padding:4px 6px; font-size:.7rem; font-weight:700; "
                f"min-width:40px; text-align:center; border:1px solid {fc}44;'>"
                f"{lbl}</div>"
            )
        map_html += "</div>"
    map_html += "</div>"
    st.markdown(map_html, unsafe_allow_html=True)

    if sel_seat:
        st.success(f"✅ Seat **{sel_seat['seat_number']}** ({sel_seat['seat_type']}) selected")
        if st.button("➡ Proceed to Passenger Details", type="primary"):
            st.session_state["page"] = "booking_form"
            st.rerun()


# ════════════════════════════════════════════════════════════════════
#  BOOKING FORM
# ════════════════════════════════════════════════════════════════════
def page_booking_form():
    bus  = st.session_state.get("sel_bus")
    seat = st.session_state.get("sel_seat")

    if not bus or not seat:
        st.warning("Please select a bus and seat first.")
        if st.button("Go to Search"):
            st.session_state["page"] = "search"; st.rerun()
        return

    # Step bar
    steps = ["1 · Route", "2 · Bus", "3 · Seat", "4 · Details", "5 · Confirm"]
    s_cols = st.columns(len(steps))
    for i, (col, lbl) in enumerate(zip(s_cols, steps)):
        color = "#f97316" if i == 3 else ("#22c55e" if i < 3 else "#cbd5e1")
        col.markdown(
            f"<div style='text-align:center; font-size:.78rem; font-weight:700; "
            f"color:{color}; border-bottom:3px solid {color}; padding-bottom:6px;'>{lbl}</div>",
            unsafe_allow_html=True,
        )
    st.markdown("<div style='height:.5rem'></div>", unsafe_allow_html=True)

    st.subheader("👤 Passenger Details")

    # Journey summary
    fare = bus.get("dyn_fare", bus["base_fare"])
    icon = OPERATOR_ICONS.get(bus["operator_name"], "🚌")
    with st.container(border=True):
        sa, sb, sc = st.columns([2, 2, 1])
        sa.markdown(f"**{icon} {bus['operator_name']}**  \n{bus['route_name']}")
        sb.markdown(f"**{bus['departure_time']} → {bus['arrival_time']}**  \n📅 {bus['travel_date']}  ·  💺 Seat {seat['seat_number']}")
        sc.markdown(
            f"<div style='text-align:right; font-size:1.5rem; font-weight:900; color:#f97316;'>Rs {fare:,}</div>",
            unsafe_allow_html=True,
        )

    st.markdown("")
    with st.form("pax"):
        c1, c2 = st.columns(2)
        with c1:
            name   = st.text_input("Full Name *",   placeholder="Priya Sharma")
            phone  = st.text_input("Mobile No. *",  placeholder="+91 98765 43210")
            gender = st.selectbox("Gender *", ["Male","Female","Other","Prefer not to say"])
        with c2:
            age    = st.number_input("Age *", 1, 120, 25)
            email  = st.text_input("Email ID *", placeholder="priya@example.com")
            pay    = st.selectbox("Payment *",
                                  ["UPI (GPay / PhonePe)","Credit Card",
                                   "Debit Card","Net Banking","Cash"])
        st.markdown("")
        agree = st.checkbox("I accept the Terms & Conditions and Cancellation Policy.")
        st.markdown("")
        pay_btn = st.form_submit_button(f"Pay Rs {fare:,} & Confirm Booking",
                                        type="primary", use_container_width=True)

        if pay_btn:
            errs = []
            if not name.strip():                      errs.append("Full name required.")
            if not phone.strip():                     errs.append("Mobile number required.")
            if not email.strip() or "@" not in email: errs.append("Valid email required.")
            if not agree:                             errs.append("Please accept Terms & Conditions.")
            if errs:
                for e in errs: st.error(e)
            else:
                with st.spinner("Processing payment..."):
                    time.sleep(1)
                ref, err = db.create_booking(
                    name.strip(), int(age), gender,
                    phone.strip(), email.strip(),
                    bus["id"], seat["id"], pay,
                )
                if err:
                    st.error(f"Booking failed: {err}")
                else:
                    st.session_state.update({"bkg_ref": ref, "page": "confirm",
                                             "sel_bus": None, "sel_seat": None})
                    st.rerun()


# ════════════════════════════════════════════════════════════════════
#  CONFIRMATION
# ════════════════════════════════════════════════════════════════════
def page_confirm():
    ref = st.session_state.get("bkg_ref")
    if not ref:
        st.warning("No booking to display."); return

    bk = db.get_booking(ref)
    if not bk:
        st.error("Booking not found."); return

    st.balloons()

    # Step bar complete
    steps = ["1 · Route","2 · Bus","3 · Seat","4 · Details","5 · Confirm"]
    s_cols = st.columns(len(steps))
    for col, lbl in zip(s_cols, steps):
        col.markdown(
            f"<div style='text-align:center; font-size:.78rem; font-weight:700; "
            f"color:#22c55e; border-bottom:3px solid #22c55e; padding-bottom:6px;'>{lbl}</div>",
            unsafe_allow_html=True,
        )

    st.markdown("")
    st.markdown(
        "<h2 style='text-align:center; color:#22c55e;'>🎉 Booking Confirmed!</h2>",
        unsafe_allow_html=True,
    )
    st.markdown(
        f"<div style='text-align:center; font-family:monospace; font-size:2rem; "
        f"font-weight:900; color:#f97316; background:#0d1b2a; padding:1rem; "
        f"border-radius:12px; letter-spacing:5px; margin:.5rem 0 1.2rem;'>"
        f"{bk['booking_ref']}</div>",
        unsafe_allow_html=True,
    )
    st.caption("Save this reference number to manage your booking.")

    icon = OPERATOR_ICONS.get(bk["operator_name"], "🚌")

    col_p, col_j = st.columns(2)
    with col_p:
        with st.container(border=True):
            st.markdown("#### 👤 Passenger")
            st.markdown(f"**Name:** {bk['name']}")
            st.markdown(f"**Age / Gender:** {bk['age']} yrs / {bk['gender']}")
            st.markdown(f"**Mobile:** {bk['phone']}")
            st.markdown(f"**Email:** {bk['email']}")
    with col_j:
        with st.container(border=True):
            st.markdown("#### 🚌 Journey")
            st.markdown(f"**Operator:** {icon} {bk['operator_name']}")
            st.markdown(f"**Route:** {bk['origin']} → {bk['destination']}")
            st.markdown(f"**Date:** {bk['travel_date']}")
            st.markdown(f"**Time:** {bk['departure_time']} → {bk['arrival_time']}")
            st.markdown(f"**Seat:** {bk['seat_number']} ({bk['seat_type']})")
            st.markdown(f"**Bus Type:** {bk['bus_type']}")

    with st.container(border=True):
        pc1, pc2, pc3 = st.columns(3)
        pc1.markdown(f"**Payment Method:**  \n{bk['payment_method']}")
        pc2.markdown(f"**Status:**  \n🟢 {bk['status']}")
        pc3.markdown(
            f"<div style='font-size:1.5rem; font-weight:900; color:#f97316;'>Rs {bk['fare_paid']:,.0f}</div>",
            unsafe_allow_html=True,
        )

    st.info("📧 A confirmation SMS and email have been sent to you (simulated).")
    st.markdown("")

    b1, b2, b3 = st.columns(3)
    with b1:
        if st.button("🔍 Book Another Bus", use_container_width=True, type="primary"):
            st.session_state["page"] = "search"; st.rerun()
    with b2:
        if st.button("🎫 View My Bookings", use_container_width=True):
            st.session_state["page"] = "bookings"; st.rerun()
    with b3:
        if st.button("🏠 Go to Dashboard", use_container_width=True):
            st.session_state["page"] = "home"; st.rerun()


# ════════════════════════════════════════════════════════════════════
#  MY BOOKINGS
# ════════════════════════════════════════════════════════════════════
def page_bookings():
    st.subheader("🎫 My Bookings")
    ref_in = st.text_input("Enter Booking Reference", placeholder="e.g. BUS3F7XQRA", max_chars=12).strip().upper()

    if st.button("🔍 Look Up Booking", type="primary"):
        if not ref_in:
            st.warning("Please enter your booking reference number.")
        else:
            bk = db.get_booking(ref_in)
            if not bk:
                st.error(f"No booking found for **{ref_in}**.")
            else:
                icon = OPERATOR_ICONS.get(bk["operator_name"], "🚌")
                status_icon = "🟢" if bk["status"] == "Confirmed" else "🔴"

                with st.container(border=True):
                    st.markdown(
                        f"<div style='font-size:1.4rem; font-weight:900; color:#f97316; font-family:monospace;'>"
                        f"{bk['booking_ref']}</div>",
                        unsafe_allow_html=True,
                    )
                    st.markdown(f"{status_icon} **Status: {bk['status']}**")
                    st.markdown("---")
                    c1, c2 = st.columns(2)
                    with c1:
                        st.markdown("**👤 Passenger Details**")
                        st.markdown(f"- Name: {bk['name']}")
                        st.markdown(f"- Age / Gender: {bk['age']} / {bk['gender']}")
                        st.markdown(f"- Mobile: {bk['phone']}")
                        st.markdown(f"- Email: {bk['email']}")
                    with c2:
                        st.markdown("**🚌 Journey Details**")
                        st.markdown(f"- Operator: {icon} {bk['operator_name']}")
                        st.markdown(f"- Route: {bk['origin']} → {bk['destination']}")
                        st.markdown(f"- Date: {bk['travel_date']}")
                        st.markdown(f"- Time: {bk['departure_time']} → {bk['arrival_time']}")
                        st.markdown(f"- Seat: {bk['seat_number']} ({bk['seat_type']})")
                        st.markdown(f"- Fare: **Rs {bk['fare_paid']:,.0f}**")
                        st.markdown(f"- Payment: {bk['payment_method']}")


# ════════════════════════════════════════════════════════════════════
#  CANCEL BOOKING
# ════════════════════════════════════════════════════════════════════
def page_cancel():
    st.subheader("❌ Cancel Booking")
    st.warning("Cancellations 24h+ before departure: 90% refund. Within 24h: 50% refund. Processed in 5-7 business days.")

    ref_in = st.text_input("Booking Reference Number", placeholder="e.g. BUS3F7XQRA", max_chars=12).strip().upper()

    if st.button("🔍 Verify Booking", type="secondary"):
        if not ref_in:
            st.warning("Enter booking reference.")
        else:
            bk = db.get_booking(ref_in)
            if not bk:
                st.error("Booking not found.")
            elif bk["status"] == "Cancelled":
                st.error("This booking is already cancelled.")
            else:
                st.session_state["cancel_bk"] = bk

    bk = st.session_state.get("cancel_bk")
    if bk and bk["status"] != "Cancelled":
        refund = round(bk["fare_paid"] * 0.9)
        icon   = OPERATOR_ICONS.get(bk["operator_name"], "🚌")

        with st.container(border=True):
            st.markdown(f"**Booking Ref:** `{bk['booking_ref']}`")
            st.markdown(f"**Passenger:** {bk['name']}")
            st.markdown(f"**Operator:** {icon} {bk['operator_name']}")
            st.markdown(f"**Route:** {bk['origin']} → {bk['destination']}")
            st.markdown(f"**Date:** {bk['travel_date']}  |  **Seat:** {bk['seat_number']}")
            st.markdown(f"**Fare Paid:** Rs {bk['fare_paid']:,.0f}  |  **Estimated Refund:** Rs {refund:,}")

        if st.button("🚨 Confirm Cancellation", type="primary"):
            ok, msg = db.cancel_booking(bk["booking_ref"])
            if ok:
                st.success(f"✅ {msg}")
                st.session_state["cancel_bk"] = None
            else:
                st.error(msg)


# ════════════════════════════════════════════════════════════════════
#  ANALYTICS
# ════════════════════════════════════════════════════════════════════
def page_analytics():
    st.subheader("📊 Analytics Dashboard")

    stats = db.get_dashboard_stats()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("✅ Bookings",  stats["total_bookings"])
    c2.metric("💰 Revenue",   f"Rs {stats['total_revenue']:,.0f}")
    c3.metric("🛣️ Routes",   stats["total_routes"])
    c4.metric("🚌 Operators", stats["total_buses"])

    st.markdown("---")
    tab1, tab2, tab3 = st.tabs(["📈 Passenger Trends", "💵 Revenue Trends", "🏆 Route Performance"])

    history = stats.get("history", [])
    color_seq = px.colors.qualitative.Bold

    with tab1:
        if history:
            df = pd.DataFrame(history)
            fig = px.line(df, x="travel_date", y="passengers", color="route_id",
                          markers=True, title="Daily Passengers by Route",
                          labels={"travel_date":"Date","passengers":"Passengers","route_id":"Route"},
                          color_discrete_sequence=color_seq)
            fig.update_layout(height=380, plot_bgcolor="rgba(0,0,0,0)",
                              paper_bgcolor="rgba(0,0,0,0)", font_color="#334155")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No historical data yet.")

    with tab2:
        if history:
            df = pd.DataFrame(history)
            fig = px.area(df, x="travel_date", y="revenue", color="route_id",
                          title="Daily Revenue (Rs) by Route",
                          labels={"travel_date":"Date","revenue":"Revenue (Rs)","route_id":"Route"},
                          color_discrete_sequence=color_seq)
            fig.update_layout(height=380, plot_bgcolor="rgba(0,0,0,0)",
                              paper_bgcolor="rgba(0,0,0,0)", font_color="#334155")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No historical data yet.")

    with tab3:
        pop = stats.get("route_popularity", [])
        if pop:
            df_p = pd.DataFrame(pop)
            fc1, fc2 = st.columns(2)
            with fc1:
                fig = px.pie(df_p, names="route_name", values="bookings",
                             title="Booking Share by Route", hole=0.4,
                             color_discrete_sequence=color_seq)
                fig.update_layout(height=360, paper_bgcolor="rgba(0,0,0,0)", font_color="#334155")
                st.plotly_chart(fig, use_container_width=True)
            with fc2:
                fig = px.bar(df_p, x="route_name", y="revenue", color="bookings",
                             title="Revenue per Route (Rs)",
                             labels={"route_name":"Route","revenue":"Revenue","bookings":"Bookings"},
                             color_continuous_scale="Oranges")
                fig.update_layout(height=360, plot_bgcolor="rgba(0,0,0,0)",
                                  paper_bgcolor="rgba(0,0,0,0)", font_color="#334155",
                                  xaxis_tickangle=-35)
                st.plotly_chart(fig, use_container_width=True)

            st.markdown("---")
            st.markdown("**Route Table**")
            df_p["revenue"] = df_p["revenue"].apply(lambda x: f"Rs {x:,.0f}")
            df_p = df_p[["route_name","origin","destination","bookings","revenue"]]
            df_p.columns = ["Route","From","To","Bookings","Revenue"]
            st.dataframe(df_p, use_container_width=True, hide_index=True)
        else:
            st.info("No booking data yet.")


# ════════════════════════════════════════════════════════════════════
#  AI DEMAND PREDICTOR
# ════════════════════════════════════════════════════════════════════
def page_predictor():
    st.subheader("🤖 AI Demand Predictor")
    st.markdown(
        "Gradient Boosting ML model predicts seat occupancy and adjusts fares based on demand. "
        "Enter journey details below to get a prediction."
    )

    routes = db.get_all_routes()
    rnames = [r["route_name"] for r in routes]

    with st.form("pred"):
        pc1, pc2 = st.columns(2)
        with pc1:
            rsel     = st.selectbox("Route", rnames)
            tdt      = st.date_input("Travel Date", value=date.today(),
                                     min_value=date.today(), max_value=date.today()+timedelta(60))
        with pc2:
            cur_pax  = st.slider("Current Passengers Booked", 0, 55, 12)
            st.write("")
        pred_btn = st.form_submit_button("🔮 Predict Demand & Fare", type="primary", use_container_width=True)

    if pred_btn:
        ri = next((r for r in routes if r["route_name"] == rsel), None)
        if ri:
            d   = ml.predict_demand(ri["id"], ri["distance_km"], ri["duration_h"],
                                    ri["base_fare"], str(tdt), cur_pax)
            dyn = round(ri["base_fare"] * d["mult"])

            # Gauge
            fig = go.Figure(go.Indicator(
                mode="gauge+number",
                value=d["pct"],
                number={"suffix":"%","font":{"size":40,"color":d["color"]}},
                title={"text":"Predicted Seat Occupancy","font":{"size":16,"color":"#334155"}},
                gauge={
                    "axis":{"range":[0,100]},
                    "bar":{"color":d["color"]},
                    "bgcolor":"#f8fafc",
                    "steps":[
                        {"range":[0,50],"color":"#f0fdf4"},
                        {"range":[50,70],"color":"#fefce8"},
                        {"range":[70,85],"color":"#fff7ed"},
                        {"range":[85,100],"color":"#fff1f2"},
                    ],
                    "threshold":{"line":{"color":"#ef4444","width":3},"thickness":.8,"value":85},
                },
            ))
            fig.update_layout(height=300, paper_bgcolor="rgba(0,0,0,0)",
                              margin=dict(t=40,b=10,l=20,r=20))
            st.plotly_chart(fig, use_container_width=True)

            m1, m2, m3, m4 = st.columns(4)
            m1.metric("📊 Occupancy",     f"{d['pct']}%")
            m2.metric("🏷️ Demand Level",  d["label"])
            m3.metric("💰 Base Fare",     f"Rs {int(ri['base_fare']):,}")
            m4.metric("🔥 Dynamic Fare",  f"Rs {dyn:,}", f"{d['mult']}x multiplier")

            st.info(f"🤖 AI Recommendation: {d['tip']}")

            # Historical chart
            hist = db.get_route_analytics(ri["id"])
            if hist["dates"]:
                df_h = pd.DataFrame(hist)
                fig2 = px.bar(df_h, x="dates", y="passengers",
                              title=f"Historical Daily Demand — {rsel}",
                              labels={"dates":"Date","passengers":"Passengers"},
                              color="passengers", color_continuous_scale="Oranges")
                fig2.update_layout(height=300, plot_bgcolor="rgba(0,0,0,0)",
                                   paper_bgcolor="rgba(0,0,0,0)", font_color="#334155")
                st.plotly_chart(fig2, use_container_width=True)

        with st.expander("ℹ️ How does the AI model work?"):
            st.table(pd.DataFrame({
                "Component": ["Algorithm","Features","Target","Pricing Rule"],
                "Detail": [
                    "Gradient Boosting Regressor (sklearn, 120 estimators)",
                    "Route, Distance, Duration, Fare, Day of Week, Is Weekend, Current Passengers",
                    "Seat Occupancy Rate (0-100%)",
                    ">=85%: 1.5x | >=70%: 1.3x | >=50%: 1.1x | <50%: 1.0x",
                ]
            }))


# ── Router ─────────────────────────────────────────────────────────
_PAGE = st.session_state["page"]
if   _PAGE == "home":         page_home()
elif _PAGE == "search":       page_search()
elif _PAGE == "booking_form": page_booking_form()
elif _PAGE == "confirm":      page_confirm()
elif _PAGE == "bookings":     page_bookings()
elif _PAGE == "cancel":       page_cancel()
elif _PAGE == "analytics":    page_analytics()
elif _PAGE == "predictor":    page_predictor()
else:
    st.session_state["page"] = "home"; st.rerun()
