from cryptography.fernet import Fernet
from core.config import ENCRYPTION_KEY

_cipher = Fernet(ENCRYPTION_KEY.encode())


def encrypt(text: str) -> str:
    return _cipher.encrypt(text.encode()).decode()


def decrypt(token: str) -> str:
    return _cipher.decrypt(token.encode()).decode()
