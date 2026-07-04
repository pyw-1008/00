from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse
import json
import os
import sqlite3
import time


BASE_DIR = Path(__file__).resolve().parent
PUBLIC_DIR = BASE_DIR / "public"
DB_PATH = BASE_DIR / "app.sqlite3"
SCHEMA_PATH = BASE_DIR / "schema.sql"


def load_dotenv():
    env_path = BASE_DIR / ".env"
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def connect_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    schema = SCHEMA_PATH.read_text(encoding="utf-8")
    with connect_db() as conn:
        conn.executescript(schema)


def write_and_read_test_row():
    marker = f"db-check-{int(time.time() * 1000)}"
    with connect_db() as conn:
        cursor = conn.execute(
            """
            INSERT INTO messages (author_name, body, is_test)
            VALUES (?, ?, 1)
            """,
            ("system", marker),
        )
        message_id = cursor.lastrowid
        row = conn.execute(
            """
            SELECT id, author_name, body, is_test, created_at
            FROM messages
            WHERE id = ?
            """,
            (message_id,),
        ).fetchone()
        conn.commit()

    return dict(row)


class AppHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(PUBLIC_DIR), **kwargs)

    def do_GET(self):
        path = urlparse(self.path).path

        if path == "/":
            self.redirect("/audience")
            return

        routes = {
            "/audience": "audience.html",
            "/screen": "screen.html",
            "/admin": "admin.html",
        }
        if path in routes:
            self.serve_file(routes[path])
            return

        if path == "/api/health":
            self.send_json({"ok": True})
            return

        if path == "/api/db-check":
            try:
                row = write_and_read_test_row()
                self.send_json({"ok": True, "row": row})
            except Exception as exc:
                self.send_json({"ok": False, "error": str(exc)}, status=500)
            return

        super().do_GET()

    def serve_file(self, filename):
        self.path = f"/{filename}"
        super().do_GET()

    def redirect(self, location):
        self.send_response(302)
        self.send_header("Location", location)
        self.end_headers()

    def send_json(self, payload, status=200):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main():
    load_dotenv()
    init_db()

    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "8000"))
    admin_password = os.environ.get("ADMIN_PASSWORD")

    server = ThreadingHTTPServer((host, port), AppHandler)
    print(f"Server running at http://{host}:{port}")
    print(f"SQLite database: {DB_PATH}")
    print(f"Admin password configured from env: {bool(admin_password)}")
    server.serve_forever()


if __name__ == "__main__":
    main()
