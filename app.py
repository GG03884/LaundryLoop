#!/usr/bin/env python3
"""
Threadline - Campus Laundry Requests, Payments & Tracking
Built entirely on the Python standard library (http.server + sqlite3).
No pip installs required. Run with:  python3 app.py
Then open http://localhost:8000 in your browser.
"""

import sqlite3
import html
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from datetime import datetime

DB_FILE = "threadline.db"
PORT = 8000

BASE_PRICE = 150       # flat base price per request (INR)
PRIORITY_FEE = 75      # extra charge for priority handling

STATUS_STAGES = ["requested", "accepted", "in_progress", "ready_for_pickup", "completed"]
STATUS_LABELS = {
    "requested": "Requested",
    "accepted": "Accepted",
    "in_progress": "In Progress",
    "ready_for_pickup": "Ready for Pickup",
    "completed": "Completed",
}

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

def get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_db()
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS locations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            discount REAL NOT NULL
        );

        CREATE TABLE IF NOT EXISTS requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_name TEXT NOT NULL,
            description TEXT NOT NULL,
            priority INTEGER NOT NULL DEFAULT 0,
            location_id INTEGER,
            base_price REAL NOT NULL,
            priority_fee REAL NOT NULL DEFAULT 0,
            discount REAL NOT NULL DEFAULT 0,
            total_price REAL NOT NULL,
            status TEXT NOT NULL DEFAULT 'requested',
            payment_status TEXT NOT NULL DEFAULT 'unpaid',
            provider_name TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (location_id) REFERENCES locations(id)
        );
        """
    )
    # Seed a couple of common drop points if none exist yet
    row = conn.execute("SELECT COUNT(*) AS c FROM locations").fetchone()
    if row["c"] == 0:
        conn.executemany(
            "INSERT INTO locations (name, discount) VALUES (?, ?)",
            [("Hostel Block A Reception", 20), ("Main Gate Security Desk", 30)],
        )
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Shared page chrome (styling)
# ---------------------------------------------------------------------------

STYLE = """
<style>
  :root {
    --navy: #16223f;
    --navy-2: #223258;
    --paper: #f0efe9;
    --thread: #2e8b7a;
    --thread-dark: #1f6357;
    --clay: #c15b3f;
    --ink: #232323;
    --line: #d8d5cb;
  }
  * { box-sizing: border-box; }
  body {
    margin: 0;
    background: var(--paper);
    color: var(--ink);
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;
    line-height: 1.5;
  }
  h1, h2, h3 {
    font-family: Georgia, 'Times New Roman', serif;
    color: var(--navy);
    margin: 0 0 0.4em 0;
  }
  header.top {
    background: var(--navy);
    color: #fff;
    padding: 18px 28px;
    display: flex;
    justify-content: space-between;
    align-items: baseline;
  }
  header.top a { color: #fff; text-decoration: none; }
  header.top .brand {
    font-family: Georgia, serif;
    font-size: 1.4em;
    letter-spacing: 0.02em;
  }
  header.top .tag {
    color: #c9d2e6;
    font-size: 0.85em;
  }
  main {
    max-width: 900px;
    margin: 0 auto;
    padding: 28px 20px 60px 20px;
  }
  .card {
    background: #fff;
    border: 1px solid var(--line);
    border-radius: 6px;
    padding: 22px 24px;
    margin-bottom: 24px;
  }
  label {
    display: block;
    font-size: 0.85em;
    font-weight: 600;
    margin-bottom: 4px;
    margin-top: 14px;
    color: var(--navy-2);
  }
  input[type=text], input[type=number], select {
    width: 100%;
    padding: 9px 10px;
    border: 1px solid var(--line);
    border-radius: 4px;
    font-size: 1em;
    font-family: inherit;
  }
  .checkbox-row {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-top: 14px;
  }
  .checkbox-row input { width: auto; }
  button, .btn {
    background: var(--thread);
    color: #fff;
    border: none;
    padding: 9px 18px;
    border-radius: 4px;
    font-size: 0.95em;
    cursor: pointer;
    font-weight: 600;
    margin-top: 16px;
  }
  button:hover, .btn:hover { background: var(--thread-dark); }
  button.secondary { background: var(--navy-2); }
  button.small { padding: 5px 12px; font-size: 0.85em; margin-top: 0; }
  table {
    width: 100%;
    border-collapse: collapse;
    margin-top: 10px;
    font-size: 0.92em;
  }
  th, td {
    text-align: left;
    padding: 10px 8px;
    border-bottom: 1px solid var(--line);
    vertical-align: top;
  }
  th { color: var(--navy-2); font-size: 0.8em; text-transform: uppercase; letter-spacing: 0.04em; }
  .price { font-weight: 700; color: var(--navy); }
  .badge {
    display: inline-block;
    padding: 2px 9px;
    border-radius: 20px;
    font-size: 0.78em;
    font-weight: 600;
  }
  .badge.unpaid { background: #f6dede; color: var(--clay); }
  .badge.paid { background: #e2ecd8; color: var(--thread-dark); }
  .badge.received { background: var(--thread); color: #fff; }

  /* Threadline signature: a clothesline progress tracker */
  .clothesline {
    position: relative;
    display: flex;
    justify-content: space-between;
    margin: 10px 0 4px 0;
    padding-top: 14px;
  }
  .clothesline::before {
    content: "";
    position: absolute;
    top: 20px;
    left: 4%;
    right: 4%;
    height: 2px;
    background: var(--line);
  }
  .clothesline .pin {
    position: relative;
    z-index: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    width: 20%;
  }
  .clothesline .peg {
    width: 13px;
    height: 13px;
    border-radius: 50%;
    background: #fff;
    border: 2px solid var(--line);
    margin-bottom: 6px;
  }
  .clothesline .pin.done .peg { background: var(--thread); border-color: var(--thread-dark); }
  .clothesline .pin.current .peg { background: var(--clay); border-color: var(--clay); box-shadow: 0 0 0 4px rgba(193,91,63,0.18); }
  .clothesline .pin span {
    font-size: 0.68em;
    text-align: center;
    color: #777;
  }
  .clothesline .pin.done span, .clothesline .pin.current span { color: var(--ink); font-weight: 600; }

  .role-choice { display: flex; gap: 20px; flex-wrap: wrap; }
  .role-choice .card { flex: 1; min-width: 260px; margin-bottom: 0; }
  .muted { color: #777; font-size: 0.85em; }
  .empty { color: #888; font-style: italic; padding: 10px 0; }
  .breakdown { font-size: 0.85em; color: #555; }
</style>
"""


def page(title, name, role, body):
    nav = ""
    if name and role:
        other_role = "provider" if role == "student" else "student"
        nav = f'<a href="/">Switch view</a>'
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)} · Threadline</title>
{STYLE}
</head><body>
<header class="top">
  <div><a href="/"><span class="brand">Threadline</span></a>
  <div class="tag">Campus laundry, on one line</div></div>
  <div>{nav}</div>
</header>
<main>
{body}
</main>
</body></html>"""


def clothesline(current_status):
    idx = STATUS_STAGES.index(current_status) if current_status in STATUS_STAGES else 0
    is_complete = current_status == "completed"
    pins = []
    for i, stage in enumerate(STATUS_STAGES):
        cls = "pin"
        if i < idx or is_complete:
            cls += " done"
        elif i == idx:
            cls += " current"
        pins.append(f'<div class="{cls}"><div class="peg"></div><span>{STATUS_LABELS[stage]}</span></div>')
    return f'<div class="clothesline">{"".join(pins)}</div>'


def payment_badge(status):
    label = {"unpaid": "Unpaid", "paid": "Paid – awaiting confirmation", "received": "Payment received"}[status]
    return f'<span class="badge {status}">{label}</span>'


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------

class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass  # keep console quiet

    # -- helpers -------------------------------------------------------
    def send_html(self, body, code=200):
        encoded = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def redirect(self, location):
        self.send_response(303)
        self.send_header("Location", location)
        self.end_headers()

    def query(self):
        parsed = urllib.parse.urlparse(self.path)
        return parsed.path, urllib.parse.parse_qs(parsed.query)

    def read_form(self):
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length).decode("utf-8") if length else ""
        return urllib.parse.parse_qs(raw)

    # -- routing ---------------------------------------------------------
    def do_GET(self):
        path, qs = self.query()
        name = html.unescape(qs.get("name", [""])[0]).strip()
        try:
            if path == "/":
                self.send_html(self.render_home())
            elif path == "/student":
                self.send_html(self.render_student(name))
            elif path == "/provider":
                self.send_html(self.render_provider(name))
            else:
                self.send_html("<h1>Not found</h1>", code=404)
        except Exception as e:
            self.send_html(f"<h1>Something went wrong</h1><p>{html.escape(str(e))}</p>", code=500)

    def do_POST(self):
        path, _ = self.query()
        form = self.read_form()

        def f(key, default=""):
            return html.unescape(form.get(key, [default])[0]).strip()

        try:
            if path == "/create_request":
                self.handle_create_request(form, f)
            elif path == "/accept":
                self.handle_accept(f)
            elif path == "/update_status":
                self.handle_update_status(f)
            elif path == "/pay":
                self.handle_pay(f)
            elif path == "/mark_received":
                self.handle_mark_received(f)
            elif path == "/add_location":
                self.handle_add_location(f)
            else:
                self.send_html("<h1>Not found</h1>", code=404)
        except Exception as e:
            self.send_html(f"<h1>Something went wrong</h1><p>{html.escape(str(e))}</p>", code=500)

    # -- POST actions ------------------------------------------------------
    def handle_create_request(self, form, f):
        name = f("name")
        description = f("description")
        priority = "priority" in form
        location_id_raw = f("location_id")
        location_id = int(location_id_raw) if location_id_raw not in ("", "none") else None

        conn = get_db()
        discount = 0.0
        if location_id is not None:
            loc = conn.execute("SELECT * FROM locations WHERE id=?", (location_id,)).fetchone()
            if loc:
                discount = loc["discount"]
        priority_fee = PRIORITY_FEE if priority else 0
        total = max(0, BASE_PRICE + priority_fee - discount)

        if name and description:
            conn.execute(
                """INSERT INTO requests
                   (student_name, description, priority, location_id, base_price,
                    priority_fee, discount, total_price, status, payment_status, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'requested', 'unpaid', ?)""",
                (name, description, int(priority), location_id, BASE_PRICE,
                 priority_fee, discount, total, datetime.now().isoformat(timespec="seconds")),
            )
            conn.commit()
        conn.close()
        self.redirect(f"/student?name={urllib.parse.quote(name)}")

    def handle_accept(self, f):
        request_id = f("request_id")
        provider_name = f("provider_name")
        conn = get_db()
        conn.execute(
            "UPDATE requests SET status='accepted', provider_name=? WHERE id=? AND status='requested'",
            (provider_name, request_id),
        )
        conn.commit()
        conn.close()
        self.redirect(f"/provider?name={urllib.parse.quote(provider_name)}")

    def handle_update_status(self, f):
        request_id = f("request_id")
        new_status = f("status")
        provider_name = f("provider_name")
        if new_status in STATUS_STAGES:
            conn = get_db()
            conn.execute("UPDATE requests SET status=? WHERE id=?", (new_status, request_id))
            conn.commit()
            conn.close()
        self.redirect(f"/provider?name={urllib.parse.quote(provider_name)}")

    def handle_pay(self, f):
        request_id = f("request_id")
        name = f("name")
        conn = get_db()
        conn.execute(
            "UPDATE requests SET payment_status='paid' WHERE id=? AND payment_status='unpaid'",
            (request_id,),
        )
        conn.commit()
        conn.close()
        self.redirect(f"/student?name={urllib.parse.quote(name)}")

    def handle_mark_received(self, f):
        request_id = f("request_id")
        provider_name = f("provider_name")
        conn = get_db()
        conn.execute(
            "UPDATE requests SET payment_status='received' WHERE id=? AND payment_status='paid'",
            (request_id,),
        )
        conn.commit()
        conn.close()
        self.redirect(f"/provider?name={urllib.parse.quote(provider_name)}")

    def handle_add_location(self, f):
        provider_name = f("provider_name")
        loc_name = f("loc_name")
        discount = f("discount") or "0"
        if loc_name:
            conn = get_db()
            conn.execute("INSERT INTO locations (name, discount) VALUES (?, ?)", (loc_name, float(discount)))
            conn.commit()
            conn.close()
        self.redirect(f"/provider?name={urllib.parse.quote(provider_name)}")

    # -- page renders ------------------------------------------------------
    def render_home(self):
        body = """
        <h1>Welcome to Threadline</h1>
        <p class="muted">One line for every laundry request on campus — raise it, pay for it, track it.</p>
        <div class="role-choice">
          <div class="card">
            <h2>I'm a student</h2>
            <form method="GET" action="/student">
              <label>Your name</label>
              <input type="text" name="name" required placeholder="e.g. Aisha Rao">
              <button type="submit">Continue</button>
            </form>
          </div>
          <div class="card">
            <h2>I'm a laundry provider</h2>
            <form method="GET" action="/provider">
              <label>Your name / service name</label>
              <input type="text" name="name" required placeholder="e.g. QuickWash Services">
              <button type="submit" class="secondary">Continue</button>
            </form>
          </div>
        </div>
        """
        return page("Home", "", "", body)

    def render_student(self, name):
        if not name:
            return page("Student", "", "", "<p>Please <a href='/'>go back</a> and enter your name.</p>")

        conn = get_db()
        locations = conn.execute("SELECT * FROM locations ORDER BY name").fetchall()
        my_requests = conn.execute(
            "SELECT * FROM requests WHERE student_name=? ORDER BY id DESC", (name,)
        ).fetchall()
        conn.close()

        loc_options = '<option value="none">No — home / room pickup</option>'
        for loc in locations:
            loc_options += f'<option value="{loc["id"]}">{html.escape(loc["name"])} (–₹{loc["discount"]:.0f})</option>'

        form = f"""
        <div class="card">
          <h2>Raise a new laundry request</h2>
          <form method="POST" action="/create_request">
            <input type="hidden" name="name" value="{html.escape(name)}">
            <label>What needs washing?</label>
            <input type="text" name="description" required placeholder="e.g. 1 bag – shirts, jeans, towels">
            <div class="checkbox-row">
              <input type="checkbox" id="priority" name="priority">
              <label for="priority" style="margin:0;">Prioritize this request (+₹{PRIORITY_FEE})</label>
            </div>
            <label>Drop &amp; pick up at a common location for a discount?</label>
            <select name="location_id">{loc_options}</select>
            <p class="muted">Base price ₹{BASE_PRICE}. Choosing a common drop point lowers the price; priority handling adds to it.</p>
            <button type="submit">Submit request</button>
          </form>
        </div>
        """

        rows = ""
        if not my_requests:
            rows = '<p class="empty">No requests yet — raise one above.</p>'
        else:
            for r in my_requests:
                pay_action = ""
                if r["payment_status"] == "unpaid" and r["status"] != "requested":
                    pay_action = f"""
                    <form method="POST" action="/pay" style="display:inline;">
                      <input type="hidden" name="request_id" value="{r['id']}">
                      <input type="hidden" name="name" value="{html.escape(name)}">
                      <button class="small" type="submit">Pay ₹{r['total_price']:.0f} now</button>
                    </form>"""
                elif r["payment_status"] == "unpaid":
                    pay_action = '<span class="muted">Available once accepted</span>'

                breakdown = f"Base ₹{r['base_price']:.0f}"
                if r["priority_fee"]:
                    breakdown += f" + priority ₹{r['priority_fee']:.0f}"
                if r["discount"]:
                    breakdown += f" − drop point ₹{r['discount']:.0f}"

                rows += f"""
                <div class="card" style="margin-bottom:16px;">
                  <div style="display:flex; justify-content:space-between; align-items:baseline;">
                    <h3 style="margin:0;">#{r['id']} · {html.escape(r['description'])}</h3>
                    <span class="price">₹{r['total_price']:.0f}</span>
                  </div>
                  <p class="breakdown">{breakdown}</p>
                  {clothesline(r['status'])}
                  <p>{payment_badge(r['payment_status'])}
                     {' · Priority' if r['priority'] else ''}
                     {' · Provider: ' + html.escape(r['provider_name']) if r['provider_name'] else ''}</p>
                  {pay_action}
                </div>
                """

        body = form + "<h2>My requests</h2>" + rows
        return page(f"{name} · Student", name, "student", body)

    def render_provider(self, name):
        if not name:
            return page("Provider", "", "", "<p>Please <a href='/'>go back</a> and enter your name.</p>")

        conn = get_db()
        incoming = conn.execute(
            "SELECT * FROM requests WHERE status='requested' ORDER BY priority DESC, id ASC"
        ).fetchall()
        mine = conn.execute(
            "SELECT * FROM requests WHERE provider_name=? AND status!='requested' ORDER BY id DESC",
            (name,),
        ).fetchall()
        locations = conn.execute("SELECT * FROM locations ORDER BY id").fetchall()
        conn.close()

        loc_rows = "".join(
            f"<tr><td>{html.escape(l['name'])}</td><td>₹{l['discount']:.0f}</td></tr>" for l in locations
        ) or "<tr><td colspan='2' class='empty'>No drop points yet.</td></tr>"

        loc_card = f"""
        <div class="card">
          <h2>Common drop &amp; pickup points</h2>
          <table><tr><th>Location</th><th>Discount</th></tr>{loc_rows}</table>
          <form method="POST" action="/add_location">
            <input type="hidden" name="provider_name" value="{html.escape(name)}">
            <label>Add a new location</label>
            <input type="text" name="loc_name" placeholder="e.g. Library Entrance" required>
            <label>Discount amount (₹)</label>
            <input type="number" name="discount" value="20" min="0" step="5" required>
            <button type="submit" class="secondary">Add location</button>
          </form>
        </div>
        """

        incoming_rows = ""
        if not incoming:
            incoming_rows = '<p class="empty">No new requests waiting.</p>'
        else:
            for r in incoming:
                incoming_rows += f"""
                <div class="card" style="margin-bottom:14px;">
                  <div style="display:flex; justify-content:space-between;">
                    <h3 style="margin:0;">#{r['id']} · {html.escape(r['description'])}
                      {' <span class="badge unpaid">Priority</span>' if r['priority'] else ''}</h3>
                    <span class="price">₹{r['total_price']:.0f}</span>
                  </div>
                  <p class="muted">Student: {html.escape(r['student_name'])}</p>
                  <form method="POST" action="/accept">
                    <input type="hidden" name="request_id" value="{r['id']}">
                    <input type="hidden" name="provider_name" value="{html.escape(name)}">
                    <button type="submit">Accept request</button>
                  </form>
                </div>
                """

        mine_rows = ""
        if not mine:
            mine_rows = '<p class="empty">You haven\'t accepted any requests yet.</p>'
        else:
            for r in mine:
                options = "".join(
                    f'<option value="{s}" {"selected" if s == r["status"] else ""}>{STATUS_LABELS[s]}</option>'
                    for s in STATUS_STAGES if s != "requested"
                )
                receive_action = ""
                if r["payment_status"] == "paid":
                    receive_action = f"""
                    <form method="POST" action="/mark_received" style="display:inline;">
                      <input type="hidden" name="request_id" value="{r['id']}">
                      <input type="hidden" name="provider_name" value="{html.escape(name)}">
                      <button class="small" type="submit">Confirm payment received</button>
                    </form>"""
                mine_rows += f"""
                <div class="card" style="margin-bottom:14px;">
                  <div style="display:flex; justify-content:space-between; align-items:baseline;">
                    <h3 style="margin:0;">#{r['id']} · {html.escape(r['description'])}</h3>
                    <span class="price">₹{r['total_price']:.0f}</span>
                  </div>
                  <p class="muted">Student: {html.escape(r['student_name'])}</p>
                  {clothesline(r['status'])}
                  <p>{payment_badge(r['payment_status'])}</p>
                  <form method="POST" action="/update_status">
                    <input type="hidden" name="request_id" value="{r['id']}">
                    <input type="hidden" name="provider_name" value="{html.escape(name)}">
                    <label>Update progress</label>
                    <select name="status">{options}</select>
                    <button type="submit" class="small">Update</button>
                  </form>
                  {receive_action}
                </div>
                """

        body = loc_card + "<h2>Incoming requests</h2>" + incoming_rows + "<h2>My accepted requests</h2>" + mine_rows
        return page(f"{name} · Provider", name, "provider", body)


def main():
    init_db()
    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    print(f"Threadline is running → http://localhost:{PORT}")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
