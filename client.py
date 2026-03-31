import json
import socket
from hashlib import sha256
from rsa import generate_keys, encrypt

# ---------------------------
# 1️⃣ Load vote choices dynamically from file
# ---------------------------
with open("choices.json", "r") as f:
    candidates = json.load(f)["candidates"]

print("Available candidates:")
for i, c in enumerate(candidates):
    print(f"{i+1}. {c}")

choice_index = int(input("Enter your choice number: ")) - 1
vote_choice = candidates[choice_index]

# ---------------------------
# 2️⃣ Generate student keys dynamically
# ---------------------------
student_public_key, student_private_key = generate_keys()

# ---------------------------
# 3️⃣ Load server public key dynamically (or generate once)
# ---------------------------
with open("keys/server_public.json", "r") as f:
    server_public_key = tuple(json.load(f)["public_key"])  # e.g., [e, n]

# ---------------------------
# 4️⃣ Encrypt vote with server public key
# ---------------------------
encrypted_vote = encrypt(vote_choice, server_public_key)

# ---------------------------
# 5️⃣ Generate hash and signature
# ---------------------------
vote_hash = sha256(encrypted_vote.encode()).hexdigest()
signature = encrypt(vote_hash, student_private_key)

# ---------------------------
# 6️⃣ Build JSON packet
# ---------------------------
student_id = input("Enter your student ID: ")
packet = {
    "student_id": student_id,
    "vote": encrypted_vote,
    "signature": signature
}
packet_json = json.dumps(packet)
print("JSON packet ready to send:")
print(packet_json)

# ---------------------------
# 7️⃣ Send packet via socket
# ---------------------------
HOST = "127.0.0.1"
PORT = 65432
with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
    s.connect((HOST, PORT))
    s.sendall(packet_json.encode())
    print("Vote successfully sent ✅")