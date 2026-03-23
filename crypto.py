from cryptography.fernet import Fernet
import os

key = os.getenv("ENCRYPTION_KEY").encode()
cipher = Fernet(key)

def encrypt(text: str) -> str:
    return cipher.encrypt(text.encode()).decode()

def decrypt(token: str) -> str:
    return cipher.decrypt(token.encode()).decode()