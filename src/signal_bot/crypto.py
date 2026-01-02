"""
Crypto - Secure encryption for API keys using Fernet (AES-128-CBC).

API keys are encrypted at rest and only decrypted when needed for trading.
"""

import base64
import os
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC


class CryptoError(Exception):
    """Encryption/decryption error."""
    pass


class Crypto:
    """
    Secure encryption for sensitive data using Fernet.
    
    Uses PBKDF2 to derive a key from the master secret.
    """
    
    def __init__(self, master_secret: str):
        """
        Initialize with a master secret.
        
        Args:
            master_secret: The master encryption key (from environment variable)
        """
        if not master_secret or len(master_secret) < 16:
            raise CryptoError("Master secret must be at least 16 characters")
        
        # Derive a Fernet key from the master secret using PBKDF2
        # Using a fixed salt - in production you might want per-user salts
        salt = b"mudrex_signal_bot_v2"
        
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=480000,
        )
        
        key = base64.urlsafe_b64encode(kdf.derive(master_secret.encode()))
        self.fernet = Fernet(key)
    
    def encrypt(self, plaintext: str) -> str:
        """
        Encrypt a string.
        
        Args:
            plaintext: The string to encrypt
            
        Returns:
            Base64-encoded encrypted string
        """
        if not plaintext:
            return ""
        
        try:
            encrypted = self.fernet.encrypt(plaintext.encode())
            return base64.urlsafe_b64encode(encrypted).decode()
        except Exception as e:
            raise CryptoError(f"Encryption failed: {e}")
    
    def decrypt(self, ciphertext: str) -> str:
        """
        Decrypt a string.
        
        Args:
            ciphertext: Base64-encoded encrypted string
            
        Returns:
            Decrypted plaintext
        """
        if not ciphertext:
            return ""
        
        try:
            encrypted = base64.urlsafe_b64decode(ciphertext.encode())
            decrypted = self.fernet.decrypt(encrypted)
            return decrypted.decode()
        except Exception as e:
            raise CryptoError(f"Decryption failed: {e}")


def generate_master_secret() -> str:
    """
    Generate a secure random master secret.
    
    Returns:
        A 32-character hex string
    """
    return os.urandom(16).hex()


# Convenience functions for module-level usage
_crypto_instance: Crypto | None = None


def init_crypto(master_secret: str):
    """Initialize the global crypto instance."""
    global _crypto_instance
    _crypto_instance = Crypto(master_secret)


def encrypt(plaintext: str) -> str:
    """Encrypt using the global crypto instance."""
    if not _crypto_instance:
        raise CryptoError("Crypto not initialized. Call init_crypto() first.")
    return _crypto_instance.encrypt(plaintext)


def decrypt(ciphertext: str) -> str:
    """Decrypt using the global crypto instance."""
    if not _crypto_instance:
        raise CryptoError("Crypto not initialized. Call init_crypto() first.")
    return _crypto_instance.decrypt(ciphertext)
