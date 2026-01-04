"""
SheetFlow AI - Token Encryption Service
Fernet symmetric encryption for OAuth tokens at rest.
"""
from cryptography.fernet import Fernet, InvalidToken
from typing import Optional
import base64
import logging

logger = logging.getLogger(__name__)


class TokenEncryption:
    """
    Encrypts and decrypts OAuth tokens using Fernet symmetric encryption.
    
    Fernet guarantees that a message encrypted using it cannot be 
    manipulated or read without the key. It uses AES-128-CBC with 
    PKCS7 padding and HMAC-SHA256 for authentication.
    """
    
    def __init__(self, key: str):
        """
        Initialize with encryption key.
        
        Args:
            key: A URL-safe base64-encoded 32-byte key.
                 Generate with: Fernet.generate_key().decode()
        """
        try:
            # Validate key format
            self.fernet = Fernet(key.encode() if isinstance(key, str) else key)
        except Exception as e:
            logger.error(f"Invalid encryption key format: {e}")
            raise ValueError(
                "Invalid encryption key. Generate one with: "
                "python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'"
            )
    
    def encrypt(self, plaintext: str) -> bytes:
        """
        Encrypt a plaintext string (e.g., OAuth token).
        
        Args:
            plaintext: The token string to encrypt.
            
        Returns:
            Encrypted bytes suitable for database storage.
        """
        if not plaintext:
            raise ValueError("Cannot encrypt empty token")
        
        return self.fernet.encrypt(plaintext.encode("utf-8"))
    
    def decrypt(self, ciphertext: bytes) -> str:
        """
        Decrypt ciphertext back to the original token string.
        
        Args:
            ciphertext: Encrypted bytes from database.
            
        Returns:
            Original plaintext token string.
            
        Raises:
            InvalidToken: If decryption fails (wrong key or corrupted data).
        """
        if not ciphertext:
            raise ValueError("Cannot decrypt empty ciphertext")
        
        try:
            return self.fernet.decrypt(ciphertext).decode("utf-8")
        except InvalidToken:
            logger.error("Token decryption failed - invalid key or corrupted data")
            raise
    
    def rotate_key(self, old_ciphertext: bytes, new_fernet: "Fernet") -> bytes:
        """
        Re-encrypt data with a new key (for key rotation).
        
        Args:
            old_ciphertext: Data encrypted with the current key.
            new_fernet: Fernet instance with the new key.
            
        Returns:
            Data encrypted with the new key.
        """
        plaintext = self.decrypt(old_ciphertext)
        return new_fernet.encrypt(plaintext.encode("utf-8"))


# Singleton instance - initialized in main.py
_encryption_instance: Optional[TokenEncryption] = None


def get_encryption() -> TokenEncryption:
    """Get the global encryption instance."""
    if _encryption_instance is None:
        raise RuntimeError("Encryption not initialized. Call init_encryption() first.")
    return _encryption_instance


def init_encryption(key: str) -> TokenEncryption:
    """Initialize the global encryption instance."""
    global _encryption_instance
    _encryption_instance = TokenEncryption(key)
    return _encryption_instance
