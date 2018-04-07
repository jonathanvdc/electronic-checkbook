"""Implements the data store used by the bank."""

from collections import deque
from Crypto.PublicKey import ECC

from promissory_note import Check, PromissoryNote, PromissoryNoteDraft
from signing_protocol import known_banks

class AccountDeviceData(object):
    """The bank's view of a device belonging to a particular account."""

    def __init__(self, public_key, cap=0):
        """Creates device data from a device's public key and a cap on
           the amount of money that can be issued in checks over the
           course of a month."""
        self.public_key = public_key
        self.check_counter = 0
        self.cap = cap

    def reset_counter(self):
        """Resets the check counter for this device data."""
        self.check_counter = 0

    def generate_check(self, value, bank):
        """Generates a check that has a particular max value. The check is
           signed immediately by the bank."""
        assert value <= self.cap
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

    def deposit(self, amount):
        """Deposits a certain amount of cash into this account."""
        assert amount >= 0
        self.balance += amount

    def withdraw(self, amount):
        """Withdraws a certain amount of cash from this account."""
        assert amount >= 0
        assert amount <= self.balance
        self.balance -= amount

    def get_device(self, public_key):
        """Gets the device with a particular public key."""
        return self.devices[public_key.export_key(format='PEM')]


class Bank(object):
    """The data store used by banks."""

    def __init__(self, identifier, private_key=None, global_cap=1000, distribution_cap=50):
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
        self.distribution_cap = distribution_cap
        self.accounts = {}

    def add_device(self, account, device):
        """Associates a new device with an account."""
        self.accounts[device.public_key.export_key(format='PEM')] = account
        account.devices[device.public_key.export_key(format='PEM')] = (device,
                                                                       AccountDeviceData(device.public_key,
                                                                                         min(account.balance,
                                                                                             self.global_cap)))

    def has_account(self, public_key):
        """Verifies whether a particular public key has been
        registered with this bank."""
        return public_key.export_key(format='PEM') in self.accounts

    def get_account(self, public_key):
        """Gets the account that owns a particular public key."""
        return self.accounts[public_key.export_key(format='PEM')]

    def get_device(self, public_key):
        """Gets the device with a particular public key."""
        return self.get_account(public_key).get_device(public_key)[0]

    def issue_check(self, public_key):
        """Issues a check for the device associated with the given public key."""
        # TODO: atm the value allotted by the bank is determined by the monthly cap divided by the
        # maximum number of checks the bank can assign to a given device.
        # This is not a very smart way of doing this. Better would be to dynamically determine
        # the size of assigned checks, thereby adapting to the user's spending behaviour.
        device_and_data = self.get_account(public_key).get_device(public_key)

        assert device_and_data[1].check_counter < self.distribution_cap
        device_and_data[0].add_unspent_check(
            device_and_data[1].generate_check(device_and_data[1].cap / self.distribution_cap, self))
        device_and_data[1].check_counter += 1

    def monthly_reset(self):
        """Resets all check counters."""
        for account in self.accounts.values():
            for device_and_data in account.devices:
                device_and_data[1].reset_counter()

    def redeem_promissory_note(self, note):
        """Actually does the transfer of payments for the relevant checks
        contained within a given promissory note."""
        assert note.is_buyer_signature_authentic
        assert note.is_seller_signature_authentic

        relevant_checks = filter(lambda c: c[0].bank_id == self.identifier, note.draft.checks)
        for check in relevant_checks:
            buyer_account = self.get_account(check[0].owner_public_key)
            seller_bank = list(filter(lambda b: b.has_account(note.draft.seller_public_key), known_banks()))[0]
            seller_account = seller_bank.get_account(note.draft.seller_public_key)

            assert buyer_account
            assert seller_account
            buyer_account.withdraw(check[1])
            seller_account.deposit(check[1])
