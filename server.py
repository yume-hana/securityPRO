# server.py

import json
import socket
import mysql.connector
from hashlib import sha256
from rsa import generate_keys, encrypt, decrypt
import os

# ---------------------------
# 1. Connect to Database
# ---------------------------
db = mysql.connector.connect(
    host     = "localhost",
    port= 3308,
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
# 3. Listen for connections
# ---------------------------
HOST = "127.0.0.1"
PORT = 65432

with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
    s.bind((HOST, PORT))
    s.listen()
    print(f"\n🟢 Server listening on {HOST}:{PORT}...")
    print("=" * 40)

    while True:
        conn, addr = s.accept()
        with conn:
            print(f"\n📩 Connection from {addr}")

            # استقبال البيانات
            data = conn.recv(4096).decode()
            packet = json.loads(data)

            student_id         = packet["student_id"]
            encrypted_vote     = packet["vote"]
            signature          = packet["signature"]
            student_public_key = tuple(packet["student_public_key"])

            print(f"👤 Student ID: {student_id}")

            # ---------------------------
            # 4. Check if already voted
            # ---------------------------
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

            # ---------------------------
            # 5. Verify signature ✅ FIXED
            # ---------------------------
            vote_hash    = sha256(encrypted_vote.encode()).hexdigest()
            hash_int     = int(vote_hash, 16) % student_public_key[1]

            # نفك التوقيع بالمفتاح العام للطالب
            e, n         = student_public_key
            hash_from_sig = pow(signature, e, n)

            if hash_from_sig != hash_int:
                conn.sendall("❌ Rejected: Invalid signature!".encode())
                print("❌ Invalid signature!")
                continue

            print("✅ Signature verified!")

            # ---------------------------
            # 6. Decrypt vote
            # ---------------------------
            real_vote = decrypt(encrypted_vote, server_private_key)
            print(f"🗳️  Vote revealed: {real_vote}")

            # ---------------------------
            # 7. Count vote in database
            # ---------------------------
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

            # ---------------------------
            # 8. Show current results
            # ---------------------------
            cursor.execute("SELECT candidate, votes FROM results")
            rows = cursor.fetchall()
            print("\n📊 Current Results:")
            print("-" * 25)
            for row in rows:
                print(f"  {row[0]}: {row[1]} votes")
            print("-" * 25)

            conn.sendall("✅ Vote accepted and counted!".encode())