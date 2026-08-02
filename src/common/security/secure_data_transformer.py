#!/usr/bin/env python


#
#
# ----------------------------------------------------------------------------------------------------#
#                                                                                                     #
# File Name     : secure_data_transformer.py.                                                         #
# Date of birth : 2026-08-02.                                                                         #
# Version       : 1.0.0.                                                                              #
# Author        : Shane Reddy.                                                                        #
#                                                                                                     #
# Explanation   : CryptoTransformer - encrypt/decrypt values via master pre_data key derivation.      #
# Dependencies  : cryptography.                                                                       #
# Modifications : 2026-08-02 Shane Reddy - initial.                                                   #
#                                                                                                     #
# Contact       : shanevreddy@gmail.com.                                                              #
#                                                                                                     #
# ----------------------------------------------------------------------------------------------------#
#
#


# ----------------------------------------------------------------------------------------------------#
# Imports.                                                                                            #
# ----------------------------------------------------------------------------------------------------#

import sys

sys.dont_write_bytecode = True

# External imports

import base64
import os

from cryptography.fernet import (
    Fernet,
    InvalidToken,
)
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

# Internal imports

# None.

# Internal constants

module_version: str = "1.0.0v"

PBKDF2_ITERATIONS: int = 480000
DERIVED_KEY_LENGTH: int = 32


# ----------------------------------------------------------------------------------------------------#
# Transformer class.                                                                                  #
# ----------------------------------------------------------------------------------------------------#

class CryptoTransformer:

    """
    A class for encrypting and decrypting data using a master pre_data for key derivation.

    Interface-compatible stand-in for the enterprise implementation: the encrypted format is a
    prefix marker followed by base64(salt + token), with the key derived per value from the
    master pre_data and a random salt. The enterprise module replaces this file verbatim at
    deployment; callers depend only on this interface.
    """

    ENCRYPTED_PREFIX: str = "eAMP::"  # Prefix for encrypted data, this marks a value as ours
    SALT_SIZE: int = 16  # random salt size in bytes

    def __init__(
            self,
            stammdaten: str,
    ) -> None:

        """
        Initializes the CryptoTransformer with a master pre_data.

        :param stammdaten: the master pre_data to use for encryption/decryption key derivation.
        :type stammdaten: str
        :return: None.
        :rtype: None
        :raises ValueError: if the master pre_data is empty.
        """

        if not stammdaten:
            raise ValueError("Master pre_data cannot be empty.")

        # endIf

        self._stammdaten: bytes = stammdaten.encode("utf-8")

    # endDef

    def _derive_key(
            self,
            salt: bytes,
    ) -> bytes:

        """
        Derives a Fernet key from the master pre_data and a salt.

        :param salt: the random salt for this value.
        :type salt: bytes
        :return: a urlsafe base64 encoded 32-byte key.
        :rtype: bytes
        """

        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=DERIVED_KEY_LENGTH,
            salt=salt,
            iterations=PBKDF2_ITERATIONS,
        )
        return base64.urlsafe_b64encode(kdf.derive(self._stammdaten))

    # endDef

    def encrypt(
            self,
            plaintext: str,
    ) -> str:

        """
        Encrypts a single value.

        :param plaintext: the value to encrypt.
        :type plaintext: str
        :return: the encrypted value carrying the encrypted-data prefix.
        :rtype: str
        """

        salt = os.urandom(self.SALT_SIZE)
        token = Fernet(self._derive_key(salt)).encrypt(plaintext.encode("utf-8"))
        payload = base64.urlsafe_b64encode(salt + token).decode("ascii")
        return f"{self.ENCRYPTED_PREFIX}{payload}"

    # endDef

    def decrypt(
            self,
            encrypted: str,
    ) -> str:

        """
        Decrypts a single value produced by encrypt.

        :param encrypted: the encrypted value, including the encrypted-data prefix.
        :type encrypted: str
        :return: the decrypted plaintext.
        :rtype: str
        :raises ValueError: if the value lacks the prefix, is corrupted, or the master pre_data is wrong.
        """

        if not encrypted.startswith(self.ENCRYPTED_PREFIX):
            raise ValueError("Value does not carry the encrypted-data prefix.")

        # endIf

        try:
            raw = base64.urlsafe_b64decode(encrypted[len(self.ENCRYPTED_PREFIX):].encode("ascii"))
            salt, token = raw[:self.SALT_SIZE], raw[self.SALT_SIZE:]
            return Fernet(self._derive_key(salt)).decrypt(token).decode("utf-8")

        except (InvalidToken, ValueError) as invalid_token_error:
            raise ValueError("Decryption failed - wrong master pre_data or corrupted value.") from invalid_token_error

        # endTryExcept

    # endDef

    def encrypt_data(
            self,
            data: dict[str, str | None],
    ) -> dict[str, str | None]:

        """
        Encrypts every non-None value in a mapping.

        :param data: mapping of field name to plaintext value.
        :type data: dict[str, str | None]
        :return: mapping of field name to encrypted value; None values pass through.
        :rtype: dict[str, str | None]
        """

        return {
            key: self.encrypt(value) if value is not None else None
            for key, value in data.items()
        }

    # endDef

    def decrypt_data(
            self,
            data: dict[str, str | None],
    ) -> dict[str, str | None]:

        """
        Decrypts every encrypted value in a mapping. Values without the encrypted-data prefix
        and None values pass through unchanged, so mixed documents decrypt safely.

        :param data: mapping of field name to encrypted or plain value.
        :type data: dict[str, str | None]
        :return: mapping of field name to decrypted value.
        :rtype: dict[str, str | None]
        """

        return {
            key: self.decrypt(value) if value is not None and value.startswith(self.ENCRYPTED_PREFIX) else value
            for key, value in data.items()
        }

    # endDef

# endClass


# end_secure_data_transformer.py
