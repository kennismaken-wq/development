import os
import sqlite3
from datetime import date, timedelta

from flask import Flask, g, jsonify, render_template, request

app = Flask(__name__)

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hours.db")


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(exception=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = sqlite3.connect(DB_PATH)
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            day TEXT NOT NULL,
            start_min INTEGER NOT NULL,
            end_min INTEGER NOT NULL,
            label TEXT NOT NULL DEFAULT ''
        )
        """
    )
    db.commit()
    db.close()


def week_start_from(iso_date_str):
    d = date.fromisoformat(iso_date_str)
    return d - timedelta(days=d.weekday())


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/entries")
def list_entries():
    start_param = request.args.get("week_start")
    if not start_param:
        return jsonify({"error": "week_start is verplicht (YYYY-MM-DD)"}), 400
    start = week_start_from(start_param)
    end = start + timedelta(days=6)
    db = get_db()
    rows = db.execute(
        "SELECT id, day, start_min, end_min, label FROM entries "
        "WHERE day BETWEEN ? AND ? ORDER BY day, start_min",
        (start.isoformat(), end.isoformat()),
    ).fetchall()
    return jsonify([dict(r) for r in rows])


@app.route("/api/entries", methods=["POST"])
def create_entry():
    data = request.get_json(force=True)
    day = data.get("day")
    start_min = data.get("start_min")
    end_min = data.get("end_min")
    label = (data.get("label") or "").strip()
    if not day or start_min is None or end_min is None or end_min <= start_min:
        return jsonify({"error": "ongeldige invoer"}), 400
    db = get_db()
    cur = db.execute(
        "INSERT INTO entries (day, start_min, end_min, label) VALUES (?, ?, ?, ?)",
        (day, int(start_min), int(end_min), label),
    )
    db.commit()
    return jsonify(
        {"id": cur.lastrowid, "day": day, "start_min": int(start_min), "end_min": int(end_min), "label": label}
    ), 201


@app.route("/api/entries/<int:entry_id>", methods=["DELETE"])
def delete_entry(entry_id):
    db = get_db()
    db.execute("DELETE FROM entries WHERE id = ?", (entry_id,))
    db.commit()
    return "", 204


init_db()

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5001)
