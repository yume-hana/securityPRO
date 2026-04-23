# server.py

import json
import socket
import threading
import mysql.connector
from hashlib import sha256
from rsa import generate_keys, decrypt
from http.server import HTTPServer, BaseHTTPRequestHandler
import os

# ---------------------------
# 1. Connect to Database
# ---------------------------
db = mysql.connector.connect(
    host     = "localhost",
    port     = 3308,
    user     = "root",
    password = "",
    database = "voting_db"
)
cursor = db.cursor()
print("✅ Connected to database")

# ---------------------------
# 2. Generate server keys
# ---------------------------
server_public_key, server_private_key = generate_keys()

os.makedirs("keys", exist_ok=True)
with open("keys/server_public.json", "w") as f:
    json.dump({"public_key": list(server_public_key)}, f)

print("✅ Server keys generated")
print(f"🔓 Public key saved to keys/server_public.json")

# ---------------------------
# Helper: hash password
# ---------------------------
def hash_password(password):
    return sha256(password.encode()).hexdigest()

# ---------------------------
# HTTP Handler
# ---------------------------
class VotingHandler(BaseHTTPRequestHandler):

    def log_message(self, format, *args):
        pass

    def send_cors(self):
        self.send_header("Access-Control-Allow-Origin",  "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_cors()
        self.end_headers()

    # ─────────────────────────────
    # GET
    # ─────────────────────────────
    def do_GET(self):

        # GET /results
        if self.path == "/results":
            cursor.execute(
                "SELECT candidate, votes FROM results ORDER BY votes DESC"
            )
            rows  = cursor.fetchall()
            total = sum(r[1] for r in rows)

            cursor.execute(
                "SELECT COUNT(*) FROM voters WHERE has_voted = FALSE"
            )
            remaining = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM voters")
            registered = cursor.fetchone()[0]

            self._respond(200, {
                "total":      total,
                "registered": registered,
                "remaining":  remaining,
                "results": [
                    {"candidate": r[0], "votes": r[1]}
                    for r in rows
                ]
            })

        # GET /public_key
        elif self.path == "/public_key":
            self._respond(200, {
                "public_key": list(server_public_key)
            })

        # GET /voters → لصفحة الأدمين
        elif self.path == "/voters":
            cursor.execute(
                "SELECT student_id, has_voted FROM voters ORDER BY id"
            )
            rows = cursor.fetchall()
            self._respond(200, {
                "voters": [
                    {"student_id": r[0], "has_voted": bool(r[1])}
                    for r in rows
                ]
            })

        else:
            self.send_response(404)
            self.end_headers()

    # ─────────────────────────────
    # POST
    # ─────────────────────────────
    def do_POST(self):

        length = int(self.headers["Content-Length"])
        body   = self.rfile.read(length)

        try:
            packet = json.loads(body)
        except:
            self._respond(400, {
                "status":  "error",
                "message": "Invalid JSON"
            })
            return

        # ─────────────────────────
        # POST /vote_simple
        # من voting.html مع password
        # ─────────────────────────
        if self.path == "/vote_simple":
            student_id = packet.get("student_id", "").strip()
            password   = packet.get("password",   "").strip()
            candidate  = packet.get("candidate",  "").strip()# تحقق من الطالب
            cursor.execute(
                "SELECT has_voted, password FROM voters WHERE student_id = %s",
                (student_id,)
            )
            result = cursor.fetchone()

            if result is None:
                self._respond(403, {
                    "status":  "error",
                    "message": "Student not registered!"
                })
                return

            # تحقق من كلمة المرور
            hashed = hash_password(password)
            if result[1] != hashed:
                self._respond(403, {
                    "status":  "error",
                    "message": "Incorrect password!"
                })
                return

            # تحقق من التصويت المزدوج
            if result[0] == 1:
                self._respond(403, {
                    "status":  "error",
                    "message": "Already voted!"
                })
                return

            # تحقق من المرشح
            cursor.execute(
                "SELECT id FROM results WHERE candidate = %s",
                (candidate,)
            )
            if cursor.fetchone() is None:
                self._respond(403, {
                    "status":  "error",
                    "message": "Invalid candidate!"
                })
                return

            # عدّ الصوت
            cursor.execute(
                "UPDATE results SET votes = votes + 1 WHERE candidate = %s",
                (candidate,)
            )
            cursor.execute(
                "UPDATE voters SET has_voted = TRUE WHERE student_id = %s",
                (student_id,)
            )
            db.commit()
            print(f"✅ [HTTP] {student_id} → {candidate}")

            self._respond(200, {
                "status":    "success",
                "message":   "Vote accepted!",
                "candidate": candidate
            })

        # ─────────────────────────
        # POST /add_candidate
        # ─────────────────────────
        elif self.path == "/add_candidate":
            candidate = packet.get("candidate", "").strip()

            if not candidate:
                self._respond(400, {
                    "status":  "error",
                    "message": "Candidate name is empty!"
                })
                return

            try:
                cursor.execute(
                    "INSERT INTO results (candidate, votes) VALUES (%s, 0)",
                    (candidate,)
                )
                db.commit()
                print(f"✅ [ADMIN] Candidate added: {candidate}")
                self._respond(200, {
                    "status":  "success",
                    "message": candidate + " added!"
                })
            except:
                self._respond(400, {
                    "status":  "error",
                    "message": candidate + " already exists!"
                })

        # ─────────────────────────
        # POST /delete_candidate
        # ─────────────────────────
        elif self.path == "/delete_candidate":
            candidate = packet.get("candidate", "").strip()
            cursor.execute(
                "DELETE FROM results WHERE candidate = %s",
                (candidate,)
            )
            db.commit()
            print(f"🗑️  [ADMIN] Candidate deleted: {candidate}")
            self._respond(200, {"status": "success"})

        # ─────────────────────────
        # POST /add_voter
        # مع password
        # ─────────────────────────
        elif self.path == "/add_voter":
            student_id = packet.get("student_id", "").strip()
            password   = packet.get("password",   "").strip()

            if not student_id:
                self._respond(400, {
                    "status":  "error",
                    "message": "Student ID is empty!"
                })
                return
            if not password:
                self._respond(400, {
                    "status":  "error",
                    "message": "Password is empty!"
                })
                return

            hashed = hash_password(password)

            try:
                cursor.execute(
                    "INSERT INTO voters (student_id, password, has_voted) VALUES (%s, %s, FALSE)",
                    (student_id, hashed)
                )
                db.commit()
                print(f"✅ [ADMIN] Voter added: {student_id}")
                self._respond(200, {
                    "status":  "success",
                    "message": student_id + " added!"
                })
            except:
                self._respond(400, {
                    "status":  "error",
                    "message": student_id + " already exists!"
                })

        # ─────────────────────────
        # POST /delete_voter
        # ─────────────────────────
        elif self.path == "/delete_voter":
            student_id = packet.get("student_id", "").strip()
            cursor.execute(
                "DELETE FROM voters WHERE student_id = %s",
                (student_id,)
            )
            db.commit()
            print(f"🗑️  [ADMIN] Voter deleted: {student_id}")
            self._respond(200, {"status": "success"})

        # ─────────────────────────
        # POST /reset_votes
        # ─────────────────────────
        elif self.path == "/reset_votes":
            cursor.execute("UPDATE results SET votes = 0")
            cursor.execute("UPDATE voters  SET has_voted = FALSE")
            db.commit()
            print("🔄 [ADMIN] All votes reset!")
            self._respond(200, {
                "status":  "success",
                "message": "All votes reset!"
            })

        else:
            self._respond(404, {
                "status":  "error",
                "message": "Endpoint not found"
            })

    def _respond(self, code, data):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_cors()
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())


# ---------------------------
# HTTP Server
# ---------------------------
def run_http():
    httpd = HTTPServer(("127.0.0.1", 8080), VotingHandler)
    print("🌐 HTTP API running on http://127.0.0.1:8080")
    httpd.serve_forever()


# ---------------------------
# Socket Server
# ---------------------------
def run_socket():
    HOST = "127.0.0.1"
    PORT = 65432

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((HOST, PORT))
        s.listen()
        print(f"🟢 Socket listening on {HOST}:{PORT}")
        print("=" * 40)

        while True:
            conn, addr = s.accept()
            with conn:
                print(f"\n📩 Connection from {addr}")

                data = conn.recv(4096).decode()

                try:
                    packet = json.loads(data)
                except json.JSONDecodeError:
                    conn.sendall("❌ Rejected: Invalid packet format!".encode())
                    continue

                student_id         = packet["student_id"]
                encrypted_vote     = packet["vote"]
                signature          = packet["signature"]
                student_public_key = tuple(packet["student_public_key"])

                print(f"👤 Student ID: {student_id}")

                # تحقق من التسجيل
                cursor.execute(
                    "SELECT has_voted FROM voters WHERE student_id = %s",
                    (student_id,)
                )
                result = cursor.fetchone()

                if result is None:
                    conn.sendall("❌ Rejected: Student not registered!".encode())
                    print("❌ Student not registered!")
                    continue
                if result[0] == 1:
                    conn.sendall("❌ Rejected: Already voted!".encode())
                    print("❌ Already voted!")
                    continue

                # تحقق من التوقيع
                vote_hash     = sha256(encrypted_vote.encode()).hexdigest()
                hash_int      = int(vote_hash, 16) % student_public_key[1]
                e, n          = student_public_key
                hash_from_sig = pow(signature, e, n)

                if hash_from_sig != hash_int:
                    conn.sendall("❌ Rejected: Invalid signature!".encode())
                    print("❌ Invalid signature!")
                    continue

                print("✅ Signature verified!")

                # فك التشفير
                real_vote = decrypt(encrypted_vote, server_private_key)
                print(f"🗳️  Vote revealed: {real_vote}")

                # تحقق من المرشح
                cursor.execute(
                    "SELECT id FROM results WHERE candidate = %s",
                    (real_vote,)
                )
                if cursor.fetchone() is None:
                    conn.sendall("❌ Rejected: Invalid candidate!".encode())
                    print("❌ Invalid candidate!")
                    continue

                # عدّ الصوت
                cursor.execute(
                    "UPDATE results SET votes = votes + 1 WHERE candidate = %s",
                    (real_vote,)
                )
                cursor.execute(
                    "UPDATE voters SET has_voted = TRUE WHERE student_id = %s",
                    (student_id,)
                )
                db.commit()
                print("✅ Vote counted!")

                # عرض النتائج
                cursor.execute(
                    "SELECT candidate, votes FROM results ORDER BY votes DESC"
                )
                rows = cursor.fetchall()

                print("\n📊 Current Results:")
                print("-" * 30)
                for row in rows:
                    print(f"  {row[0]}: {row[1]} votes")
                print("-" * 30)

                winner       = rows[0]
                winner_name  = winner[0]
                winner_votes = winner[1]
                print(f"\n🏆 Current Leader: {winner_name} ({winner_votes} votes)")

                cursor.execute(
                    "SELECT COUNT(*) FROM voters WHERE has_voted = FALSE"
                )
                remaining = cursor.fetchone()[0]
                print(f"⏳ Remaining voters: {remaining}")

                if remaining == 0:
                    print("\n" + "=" * 30)
                    print("🎉 VOTING FINISHED!")
                    print(f"🏆 WINNER: {winner_name}")
                    print(f"   with {winner_votes} votes!")
                    print("=" * 30)
                    conn.sendall(
                        f"✅ Vote counted! 🏆 FINAL WINNER: {winner_name} with {winner_votes} votes!".encode()
                    )
                else:
                    conn.sendall(
                        f"✅ Vote accepted! Current leader: {winner_name} ({winner_votes} votes). Remaining: {remaining}".encode()
                    )


# ---------------------------
# Main
# ---------------------------
print("\n" + "=" * 40)
t1 = threading.Thread(target=run_http,   daemon=True)
t2 = threading.Thread(target=run_socket, daemon=True)
t1.start()
t2.start()
t1.join()
t2.join()