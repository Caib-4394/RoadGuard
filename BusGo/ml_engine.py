"""
ml_engine.py – Demand prediction for BusGo
"""
import numpy as np, pandas as pd, sqlite3, os, warnings
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline

warnings.filterwarnings("ignore")
DB_PATH = os.path.join(os.path.dirname(__file__), "busgo.db")


def _load_training_data():
    try:
        conn = sqlite3.connect(DB_PATH)
        df = pd.read_sql_query("""
            SELECT bh.passengers, bh.travel_date,
                   r.distance_km, r.duration_h, r.base_fare, r.id AS route_id,
                   b.total_seats
            FROM booking_history bh
            JOIN buses b  ON bh.bus_id   = b.id
            JOIN routes r ON bh.route_id = r.id
        """, conn)
        conn.close()
    except Exception:
        return None, None
    if df.empty:
        return None, None
    df["travel_date"] = pd.to_datetime(df["travel_date"])
    df["day_of_week"] = df["travel_date"].dt.dayofweek
    df["is_weekend"]  = (df["day_of_week"] >= 5).astype(int)
    df["occupancy"]   = (df["passengers"] / df["total_seats"]).clip(0, 1)
    features = ["route_id","distance_km","duration_h","base_fare",
                "day_of_week","is_weekend","passengers"]
    return df[features], df["occupancy"]


_MODEL = None

def get_model():
    global _MODEL
    if _MODEL is None:
        X, y = _load_training_data()
        if X is not None:
            m = Pipeline([("sc", StandardScaler()),
                          ("gb", GradientBoostingRegressor(n_estimators=120, random_state=42))])
            m.fit(X, y)
            _MODEL = m
    return _MODEL


def predict_demand(route_id, distance_km, duration_h, base_fare, travel_date, current_passengers):
    m = get_model()
    fallback = {"pct": 55.0, "label": "Medium", "color": "#f59e0b",
                "tip": "Moderate demand expected.", "mult": 1.0}
    if m is None:
        return fallback
    try:
        dt  = pd.to_datetime(travel_date)
        dow = dt.dayofweek
        iw  = int(dow >= 5)
        X   = np.array([[route_id, distance_km, duration_h, base_fare, dow, iw, current_passengers]])
        pct = float(np.clip(m.predict(X)[0], 0, 1)) * 100
        if pct >= 85:
            return {"pct": round(pct,1), "label": "Very High", "color": "#ef4444",
                    "tip": "Almost full — book immediately!", "mult": 1.5}
        elif pct >= 70:
            return {"pct": round(pct,1), "label": "High", "color": "#f97316",
                    "tip": "High demand — book soon.", "mult": 1.3}
        elif pct >= 50:
            return {"pct": round(pct,1), "label": "Medium", "color": "#eab308",
                    "tip": "Moderate demand — good availability.", "mult": 1.1}
        else:
            return {"pct": round(pct,1), "label": "Low", "color": "#22c55e",
                    "tip": "Low demand — plenty of seats.", "mult": 1.0}
    except Exception:
        return fallback


def get_route_analytics(route_id):
    return __import__("database").get_route_analytics(route_id)
