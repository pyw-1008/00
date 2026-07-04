from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from contextlib import closing
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

DEFAULT_QUESTION_TITLE = "你最倾向于哪个选项？"
DEFAULT_OPTIONS = ["喜爱一个人吃饭", "喜爱和对象两个人吃饭", "喜爱和三五好友聚会", "喜爱在家和家人亲戚一起吃饭"]


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
    with closing(connect_db()) as conn:
        conn.executescript(schema)
        seed_default_question(conn)
        conn.commit()


def seed_default_question(conn):
    existing = conn.execute(
        """
        SELECT id, description
        FROM questions
        WHERE status = 'active'
        ORDER BY id
        LIMIT 1
        """
    ).fetchone()
    if existing:
        if existing["description"] == "切片 1 默认题目":
            conn.execute(
                """
                UPDATE questions
                SET title = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (DEFAULT_QUESTION_TITLE, existing["id"]),
            )
            conn.executemany(
                """
                UPDATE question_options
                SET label = ?
                WHERE question_id = ? AND sort_order = ?
                """,
                [
                    (label, existing["id"], index)
                    for index, label in enumerate(DEFAULT_OPTIONS, start=1)
                ],
            )
        return existing["id"]

    cursor = conn.execute(
        """
        INSERT INTO questions (title, description, status)
        VALUES (?, ?, 'active')
        """,
        (DEFAULT_QUESTION_TITLE, "切片 1 默认题目"),
    )
    question_id = cursor.lastrowid
    conn.executemany(
        """
        INSERT INTO question_options (question_id, label, sort_order)
        VALUES (?, ?, ?)
        """,
        [
            (question_id, label, index)
            for index, label in enumerate(DEFAULT_OPTIONS, start=1)
        ],
    )
    return question_id


def get_active_question(conn):
    question = conn.execute(
        """
        SELECT id, title
        FROM questions
        WHERE status = 'active'
        ORDER BY id
        LIMIT 1
        """
    ).fetchone()
    if question:
        return question

    seed_default_question(conn)
    return conn.execute(
        """
        SELECT id, title
        FROM questions
        WHERE status = 'active'
        ORDER BY id
        LIMIT 1
        """
    ).fetchone()


def get_current_question_payload():
    with closing(connect_db()) as conn:
        question = get_active_question(conn)
        conn.commit()
        rows = conn.execute(
            """
            SELECT
                question_options.id,
                question_options.label,
                COUNT(votes.id) AS vote_count
            FROM question_options
            LEFT JOIN votes ON votes.option_id = question_options.id
            WHERE question_options.question_id = ?
            GROUP BY question_options.id, question_options.label, question_options.sort_order
            ORDER BY question_options.sort_order, question_options.id
            """,
            (question["id"],),
        ).fetchall()

    total_votes = sum(row["vote_count"] for row in rows)
    options = []
    for row in rows:
        vote_count = row["vote_count"]
        percentage = round((vote_count / total_votes * 100), 1) if total_votes else 0
        options.append(
            {
                "id": row["id"],
                "label": row["label"],
                "votes": vote_count,
                "percentage": percentage,
            }
        )

    return {
        "id": question["id"],
        "title": question["title"],
        "total_votes": total_votes,
        "options": options,
    }


def record_vote(option_id):
    try:
        option_id = int(option_id)
    except (TypeError, ValueError):
        raise ValueError("无效的选项")

    with closing(connect_db()) as conn:
        question = get_active_question(conn)
        option = conn.execute(
            """
            SELECT id
            FROM question_options
            WHERE id = ? AND question_id = ?
            """,
            (option_id, question["id"]),
        ).fetchone()
        if not option:
            raise ValueError("选项不存在")

        conn.execute(
            """
            INSERT INTO votes (question_id, option_id)
            VALUES (?, ?)
            """,
            (question["id"], option_id),
        )
        conn.commit()

    return get_current_question_payload()


def write_and_read_test_row():
    marker = f"db-check-{int(time.time() * 1000)}"
    with closing(connect_db()) as conn:
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

        if path == "/api/current-question":
            try:
                question = get_current_question_payload()
                self.send_json({"ok": True, "question": question})
            except Exception as exc:
                self.send_json({"ok": False, "error": str(exc)}, status=500)
            return

        if path == "/api/db-check":
            try:
                row = write_and_read_test_row()
                self.send_json({"ok": True, "row": row})
            except Exception as exc:
                self.send_json({"ok": False, "error": str(exc)}, status=500)
            return

        super().do_GET()

    def do_POST(self):
        path = urlparse(self.path).path

        if path == "/api/votes":
            try:
                payload = self.read_json()
                question = record_vote(payload.get("option_id"))
                self.send_json({"ok": True, "question": question})
            except ValueError as exc:
                self.send_json({"ok": False, "error": str(exc)}, status=400)
            except Exception as exc:
                self.send_json({"ok": False, "error": str(exc)}, status=500)
            return

        self.send_json({"ok": False, "error": "接口不存在"}, status=404)

    def serve_file(self, filename):
        self.path = f"/{filename}"
        super().do_GET()

    def redirect(self, location):
        self.send_response(302)
        self.send_header("Location", location)
        self.end_headers()

    def read_json(self):
        content_length = int(self.headers.get("Content-Length", 0))
        raw_body = self.rfile.read(content_length).decode("utf-8")
        if not raw_body:
            return {}
        return json.loads(raw_body)

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
