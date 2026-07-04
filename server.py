from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from contextlib import closing
from pathlib import Path
from urllib.parse import parse_qs, urlparse
import json
import os
import re
import sqlite3
import time


BASE_DIR = Path(__file__).resolve().parent
PUBLIC_DIR = BASE_DIR / "public"
DB_PATH = BASE_DIR / "app.sqlite3"
SCHEMA_PATH = BASE_DIR / "schema.sql"
SENSITIVE_WORDS_PATH = BASE_DIR / "sensitive_words.txt"

DEFAULT_QUESTION_TITLE = "你最倾向于哪个选项？"
DEFAULT_OPTIONS = ["喜爱一个人吃饭", "喜爱和对象两个人吃饭", "喜爱和三五好友聚会", "喜爱在家和家人亲戚一起吃饭"]
MESSAGE_MAX_LENGTH = 50
MESSAGE_FETCH_LIMIT = 50
AUDIENCE_POLL_INTERVAL_MS = 1500


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


def is_admin_password_valid(password):
    admin_password = os.environ.get("ADMIN_PASSWORD")
    return bool(admin_password) and password == admin_password


def get_admin_questions_payload():
    with closing(connect_db()) as conn:
        question_rows = conn.execute(
            """
            SELECT id, title, status, created_at, updated_at
            FROM questions
            ORDER BY
                CASE WHEN status = 'active' THEN 0 ELSE 1 END,
                updated_at DESC,
                id DESC
            """
        ).fetchall()

        questions = []
        for question in question_rows:
            option_rows = conn.execute(
                """
                SELECT id, label, sort_order
                FROM question_options
                WHERE question_id = ?
                ORDER BY sort_order, id
                """,
                (question["id"],),
            ).fetchall()
            questions.append(
                {
                    "id": question["id"],
                    "title": question["title"],
                    "status": question["status"],
                    "created_at": question["created_at"],
                    "updated_at": question["updated_at"],
                    "options": [dict(row) for row in option_rows],
                }
            )

    return questions


def normalize_question_payload(payload):
    title = str(payload.get("title") or "").strip()
    options = [
        str(option).strip()
        for option in payload.get("options", [])
        if str(option).strip()
    ]

    if not title:
        raise ValueError("题目不能为空")
    if len(options) < 2 or len(options) > 6:
        raise ValueError("选项数量必须是 2-6 个")

    return title, options


def save_admin_question(payload):
    title, options = normalize_question_payload(payload)
    question_id = payload.get("id")

    with closing(connect_db()) as conn:
        if question_id:
            question_id = int(question_id)
            existing = conn.execute(
                "SELECT id FROM questions WHERE id = ?",
                (question_id,),
            ).fetchone()
            if not existing:
                raise ValueError("题目不存在")
            conn.execute(
                """
                UPDATE questions
                SET title = ?, description = '后台题目', updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (title, question_id),
            )
            conn.execute("DELETE FROM votes WHERE question_id = ?", (question_id,))
            conn.execute("DELETE FROM question_options WHERE question_id = ?", (question_id,))
        else:
            cursor = conn.execute(
                """
                INSERT INTO questions (title, description, status)
                VALUES (?, '后台题目', 'draft')
                """,
                (title,),
            )
            question_id = cursor.lastrowid

        conn.executemany(
            """
            INSERT INTO question_options (question_id, label, sort_order)
            VALUES (?, ?, ?)
            """,
            [
                (question_id, label, index)
                for index, label in enumerate(options, start=1)
            ],
        )
        activate_question_in_connection(conn, question_id)
        conn.commit()

    return get_current_question_payload()


def activate_question_in_connection(conn, question_id):
    existing = conn.execute(
        "SELECT id FROM questions WHERE id = ?",
        (question_id,),
    ).fetchone()
    if not existing:
        raise ValueError("题目不存在")

    conn.execute("UPDATE questions SET status = 'draft'")
    conn.execute(
        """
        UPDATE questions
        SET status = 'active', updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (question_id,),
    )
    conn.execute("DELETE FROM votes WHERE question_id = ?", (question_id,))
    clear_messages_in_connection(conn)


def activate_admin_question(question_id):
    with closing(connect_db()) as conn:
        activate_question_in_connection(conn, int(question_id))
        conn.commit()

    return get_current_question_payload()


def clear_current_votes():
    with closing(connect_db()) as conn:
        question = get_active_question(conn)
        conn.execute("DELETE FROM votes WHERE question_id = ?", (question["id"],))
        clear_messages_in_connection(conn)
        conn.commit()

    return get_current_question_payload()


def clear_messages_in_connection(conn):
    conn.execute("DELETE FROM messages WHERE is_test = 0")


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


def record_message(body):
    body = str(body or "").strip()
    if not body:
        raise ValueError("留言不能为空")
    if len(body) > MESSAGE_MAX_LENGTH:
        raise ValueError("留言最多 50 字")

    masked_body, is_masked = mask_sensitive_words(body)

    with closing(connect_db()) as conn:
        cursor = conn.execute(
            """
            INSERT INTO messages (author_name, body, is_test)
            VALUES (?, ?, 0)
            """,
            ("观众", masked_body),
        )
        message_id = cursor.lastrowid
        row = conn.execute(
            """
            SELECT id, body, created_at
            FROM messages
            WHERE id = ?
            """,
            (message_id,),
        ).fetchone()
        conn.commit()

    message = dict(row)
    message["masked"] = is_masked
    return message


def load_sensitive_words():
    if not SENSITIVE_WORDS_PATH.exists():
        return []

    words = []
    for raw_line in SENSITIVE_WORDS_PATH.read_text(encoding="utf-8").splitlines():
        word = raw_line.strip()
        if word and not word.startswith("#"):
            words.append(word)
    return words


def mask_sensitive_words(body):
    masked_body = body
    is_masked = False

    for word in load_sensitive_words():
        pattern = re.compile(re.escape(word), re.IGNORECASE)

        def replacement(match):
            nonlocal is_masked
            is_masked = True
            return "*" * len(match.group(0))

        masked_body = pattern.sub(replacement, masked_body)

    return masked_body, is_masked


def list_messages(since_id=0, limit=MESSAGE_FETCH_LIMIT):
    try:
        since_id = int(since_id)
    except (TypeError, ValueError):
        since_id = 0

    with closing(connect_db()) as conn:
        rows = conn.execute(
            """
            SELECT id, body, created_at
            FROM messages
            WHERE is_test = 0 AND id > ?
            ORDER BY id ASC
            LIMIT ?
            """,
            (since_id, limit),
        ).fetchall()

    return [dict(row) for row in rows]


def get_latest_message_id():
    with closing(connect_db()) as conn:
        row = conn.execute(
            """
            SELECT COALESCE(MAX(id), 0) AS latest_id
            FROM messages
            WHERE is_test = 0
            """
        ).fetchone()
    return row["latest_id"]


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
        parsed_url = urlparse(self.path)
        path = parsed_url.path

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

        if path == "/api/messages":
            try:
                query = parse_qs(parsed_url.query)
                since_id = query.get("since_id", [0])[0]
                messages = list_messages(since_id=since_id)
                self.send_json(
                    {
                        "ok": True,
                        "messages": messages,
                        "latest_id": get_latest_message_id(),
                    }
                )
            except Exception as exc:
                self.send_json({"ok": False, "error": str(exc)}, status=500)
            return

        if path == "/api/admin/questions":
            if not self.require_admin():
                return
            try:
                self.send_json({"ok": True, "questions": get_admin_questions_payload()})
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

        if path == "/api/admin/login":
            payload = self.read_json()
            if is_admin_password_valid(payload.get("password")):
                self.send_json({"ok": True})
            else:
                self.send_json({"ok": False, "error": "密码错误"}, status=401)
            return

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

        if path == "/api/messages":
            try:
                payload = self.read_json()
                message = record_message(payload.get("body"))
                self.send_json({"ok": True, "message": message})
            except ValueError as exc:
                self.send_json({"ok": False, "error": str(exc)}, status=400)
            except Exception as exc:
                self.send_json({"ok": False, "error": str(exc)}, status=500)
            return

        if path == "/api/admin/questions":
            if not self.require_admin():
                return
            try:
                payload = self.read_json()
                question = save_admin_question(payload)
                self.send_json({"ok": True, "question": question})
            except ValueError as exc:
                self.send_json({"ok": False, "error": str(exc)}, status=400)
            except Exception as exc:
                self.send_json({"ok": False, "error": str(exc)}, status=500)
            return

        if path == "/api/admin/activate":
            if not self.require_admin():
                return
            try:
                payload = self.read_json()
                question = activate_admin_question(payload.get("id"))
                self.send_json({"ok": True, "question": question})
            except ValueError as exc:
                self.send_json({"ok": False, "error": str(exc)}, status=400)
            except Exception as exc:
                self.send_json({"ok": False, "error": str(exc)}, status=500)
            return

        if path == "/api/admin/clear-votes":
            if not self.require_admin():
                return
            try:
                question = clear_current_votes()
                self.send_json({"ok": True, "question": question})
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

    def require_admin(self):
        password = self.headers.get("X-Admin-Password", "")
        if is_admin_password_valid(password):
            return True
        self.send_json({"ok": False, "error": "未授权"}, status=401)
        return False

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
