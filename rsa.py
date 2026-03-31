import random


def gcd(a, b):
    while b != 0:
        a, b = b, a % b
    return a

def mod_inverse(e, phi):
    for d in range(1, phi):
        if (d * e) % phi == 1:
            return d


def is_prime(n):
    if n < 2:
        return False
    for i in range(2, int(n**0.5)+1):
        if n % i == 0:
            return False
    return True

def generate_prime(start=100, end=300):
    while True:
        num = random.randint(start, end)
        if is_prime(num):
            return num
        
def generate_keys():
    p = generate_prime()
    q = generate_prime()

    n = p * q
    phi = (p - 1) * (q - 1)

    e = 17  

    d = mod_inverse(e, phi)

    return (e, n), (d, n)   

     
def encrypt(message, public_key):
    e, n = public_key
    cipher = ""

    for char in message:
        m = ord(char)
        c = pow(m, e, n)
        cipher += hex(c) + " "

    return cipher

def decrypt(cipher, private_key):
    d, n = private_key
    message = ""

    cipher_list = cipher.split()

    for c in cipher_list:
        c_int = int(c, 16)  
        m = pow(c_int, d, n)
        message += chr(m)

    return message


    
