# client.py

import json
import socket
from hashlib import sha256
from rsa import generate_keys, encrypt, decrypt

# ---------------------------
# 1. Load candidates from file
# ---------------------------
with open("choices.json", "r") as f:
    candidates = json.load(f)["candidates"]

print("=" * 40)
print("     Electronic Voting System")
print("=" * 40)

print("\nAvailable candidates:")
for i, c in enumerate(candidates):
    print(f"  {i+1}. {c}")

choice_index = int(input("\nEnter your choice number: ")) - 1
vote_choice = candidates[choice_index]
print(f"✅ You voted for: {vote_choice}")

# ---------------------------
# 2. Generate student keys
# ---------------------------
student_public_key, student_private_key = generate_keys()

# ---------------------------
# 3. Load server public key
# ---------------------------
with open("keys/server_public.json", "r") as f:
    server_public_key = tuple(json.load(f)["public_key"])

# ---------------------------
# 4. Encrypt vote with server public key
# ---------------------------
encrypted_vote = encrypt(vote_choice, server_public_key)
print(f"\n🔒 Encrypted vote: {encrypted_vote[:30]}...")

# ---------------------------
# 5. Hash + Sign with student private key
# ---------------------------
vote_hash = sha256(encrypted_vote.encode()).hexdigest()
hash_int = int(vote_hash, 16) % student_private_key[1]  # mod n
signature = pow(hash_int, student_private_key[0], student_private_key[1])
print(f"🖊️  Signature generated ✅")

# ---------------------------
# 6. Build JSON packet
# ---------------------------
student_id = input("\nEnter your student ID: ")

packet = {
    "student_id":       student_id,
    "vote":             encrypted_vote,
    "signature":        signature,
    "student_public_key": list(student_public_key)  # الخادم يحتاجه للتحقق
}

packet_json = json.dumps(packet)
print("\n📦 Packet ready to send!")

# ---------------------------
# 7. Send via socket
# ---------------------------
HOST = "127.0.0.1"
PORT = 65432

with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
    s.connect((HOST, PORT))
    s.sendall(packet_json.encode())
    
    # استقبال رد الخادم
    response = s.recv(1024).decode()
    print(f"\n📨 Server response: {response}")