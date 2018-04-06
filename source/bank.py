"""Implements the data store used by the bank."""

from collections import deque
from Crypto.PublicKey import ECC

from promissory_note import Check, PromissoryNote, PromissoryNoteDraft


class AccountDeviceData(object):
    """The bank's view of a device belonging to a particular account."""

    def __init__(self, public_key, cap=0):
        """Creates device data from a device's public key and a cap on
           the amount of money that can be issued in checks over the
           course of a month."""
        self.public_key = public_key
        self.check_counter = 0
        self.cap = cap

    def generate_check(self, value, bank):
        """Generates a check that has a particular max value. The check is
           signed immediately by the bank."""
        # Generate a check.
        check = Check(bank.identifier, self.public_key, value, self.check_counter)
        # Increment the check counter.
        self.check_counter += 1
        # Sign the check.
        check.sign(bank.private_key)
        return check


class Account(object):
    """Describes an account at a bank."""

    def __init__(self, owner):
        """Creates a new account from the account owner's personal information."""
        self.owner = owner
        self.balance = 0
        self.devices = {}

    def get_device(self, public_key):
        """Gets the device with a particular public key."""
        return self.devices[public_key]


class Bank(object):
    """The data store used by banks."""

    def __init__(self, identifier, private_key=None, global_cap=1000):
        """Creates an empty bank data store from a unique identifier
           and a private key. Generates a private key automatically if
           none is specified."""
        if private_key is None:
            # Generate an ECC private key.
            private_key = ECC.generate(curve='P-256')

        self.identifier = identifier
        self.private_key = private_key
        self.public_key = private_key.public_key()
        self.global_cap = global_cap
        self.accounts = {}

    def add_device(self, account, device):
        """Associates a new device with an account."""
        self.accounts[device.public_key] = account
        account.devices[device.public_key] = (device,
                                              AccountDeviceData(device.public_key,
                                                                min(account.balance, self.global_cap)))

    def get_account(self, public_key):
        """Gets the account that owns a particular public key."""
        return self.accounts[public_key]

    def get_device(self, public_key):
        """Gets the device with a particular public key."""
        return self.get_account(public_key).get_device(public_key)

    def generate_fresh_batch_of_checks(self):
        raise NotImplementedError

    def assign_check(self, check, public_key):
        self.accounts[public_key].get_device(public_key).add_unspent_check(check)
