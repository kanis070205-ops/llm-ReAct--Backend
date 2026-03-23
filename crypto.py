from cryptography.fernet import Fernet
import os
from dotenv import load_dotenv

load_dotenv()

_key = os.getenv("ENCRYPTION_KEY")
if not _key:
    raise RuntimeError("ENCRYPTION_KEY is not set in .env")

cipher = Fernet(_key.encode())


def encrypt(text: str) -> str:
    return cipher.encrypt(text.encode()).decode()


def decrypt(token: str) -> str:
    return cipher.decrypt(token.encode()).decode()
