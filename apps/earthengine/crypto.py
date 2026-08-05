from cryptography.fernet import Fernet
from django.conf import settings


def _fernet():
    return Fernet(settings.EE_TOKEN_ENCRYPTION_KEY)


def encrypt(value):
    return _fernet().encrypt(value.encode()).decode()


def decrypt(value):
    return _fernet().decrypt(value.encode()).decode()