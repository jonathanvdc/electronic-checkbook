"""Implements the data store used by the bank."""

import json
from Crypto.PublicKey import ECC

from promissory_note import Check
from signing_protocol import known_banks


class FraudException(Exception):
    pass


class AccountDeviceData(object):
    """The bank's view of a device belonging to a particular account."""

    def __init__(self, public_key, cap=0):
        """Creates device data from a device's public key and a cap on
           the amount of money that can be issued in checks over the
           course of a month/week/other timespan ."""
        self.public_key = public_key
        self.check_counter = 0
        self.cap = cap
        self.issued_check_value = 0
        self.unspent_checks = set()

    @property
    def total_unspent_check_value(self):
        """Gets the total value of all unspent checks for this device."""
        return sum(check.value for check in self.unspent_checks)

    def is_unspent(self, check):
        """Checks if a check has not yet been spent."""
        return check in self.unspent_checks

    def spend_check(self, check):
        """Spends a check. This action removes the check from the set of
           unspent checks."""
        self.unspent_checks.remove(check)

    def reset_issued_check_value_counter(self):
        """Resets the issued check value counter back to the total unspent
           check value for this device."""
        self.issued_check_value = self.total_unspent_check_value

    def generate_check(self, value, bank):
        """Generates a check that has a particular max value. The check is
           signed immediately by the bank."""
        assert value <= self.cap

        if self.issued_check_value + value > self.cap:
            raise ValueError(
                'Cannot issue a check worth %d because doing so would exceed '
                'the cap for the device.' % value)

        # Generate a check.
        check = Check(bank.identifier, self.public_key, value,
                      self.check_counter)
        # Increment the check counter.
        self.check_counter += 1
        # Add the check's value to the issued check value.
        self.issued_check_value += value
        # Sign the check.
        check.sign(bank.private_key)
        self.unspent_checks.add(check)
        return check


class Account(object):
    """Describes an account at a bank."""

    def __init__(self, owner, max_credit=0):
        """Creates a new account from the account owner's personal information."""
        self.owner = owner
        self.max_credit = max_credit
        self.balance = 0
        self.devices = {}

    @property
    def total_unspent_check_value(self):
        """Gets the total value of all unspent checks for all devices associated
           with this account."""
        return sum(device.total_unspent_check_value
                   for device in self.devices.values())

    def deposit(self, amount):
        """Deposits a certain amount of cash into this account."""
        assert amount >= 0
        self.balance += amount

    def withdraw(self, amount):
        """Withdraws a certain amount of cash from this account."""
        assert amount >= 0

        # No need to check the assertion below because
        #   1. the user might have a `max_credit` greater than zero and
        #   2. it should be impossible *by design* for the bank to issue
        #      checks such that their total value exceeds `balance + max_credit`.
        #
        # assert amount <= self.balance
        self.balance -= amount

    def get_device(self, public_key):
        """Gets the device with a particular public key."""
        return self.devices[public_key.export_key(format='PEM')]

    def to_json(self):
        return {'Owner': self.owner, 'Max credit': self.max_credit, 'Balance': self.balance}

    def __str__(self) -> str:
        return json.dumps(self.to_json(), indent=2)


class Bank(object):
    """The data store used by banks."""

    def __init__(self, identifier, private_key=None, default_cap=0):
        """Creates an empty bank data store from a unique identifier
           and a private key. Generates a private key automatically if
           none is specified."""
        if private_key is None:
            # Generate an ECC private key.
            private_key = ECC.generate(curve='P-256')

        self.identifier = identifier
        self.private_key = private_key
        self.public_key = private_key.public_key()
        self.default_cap = default_cap
        self.accounts = {}

    def add_device(self, account, device_public_key, cap=None):
        """Associates a new device with an account. The device to add is
           identified by a public key. Returns the data for the device."""
        if cap is None:
            cap = self.default_cap
        exported_key = device_public_key.export_key(format='PEM')
        self.accounts[exported_key] = account
        device_data = AccountDeviceData(device_public_key, cap)
        account.devices[exported_key] = device_data
        return device_data

    def has_account(self, public_key):
        """Verifies whether a particular public key has been
        registered with this bank."""
        return public_key.export_key(format='PEM') in self.accounts

    def get_account(self, public_key):
        """Gets the account that owns a particular public key."""
        return self.accounts[public_key.export_key(format='PEM')]

    def get_device(self, public_key):
        """Gets the data for the device with a particular public key."""
        return self.get_account(public_key).get_device(public_key)

    def reset_issued_check_value_counters(self):
        """Resets the issued check value counters for this month."""
        for account in self.accounts.values():
            for device in account.devices.values():
                device.reset_issued_check_value_counter()

    def issue_check(self, public_key, value):
        """Issues a check of a particular value for the device associated
           with the given public key."""
        # TODO: error if public key doesn't exist within the bank
        account = self.get_account(public_key)
        data = account.get_device(public_key)

        # Make sure that issuing a new check will not exceed the balance + credit
        # for the account.
        if account.balance + account.max_credit < account.total_unspent_check_value + value:
            raise ValueError(
                'Check cannot be issued because doing so would exceed '
                'the account\'s credit.')

        # Actually generate the check.
        return data.generate_check(value, self)

    def redeem_promissory_note(self, note):
        """Actually does the transfer of payments for the relevant checks
           contained within a given promissory note."""
        assert note.is_buyer_signature_authentic
        assert note.is_seller_signature_authentic

        relevant_checks = filter(lambda c: c[0].bank_id == self.identifier,
                                 note.draft.checks)
        for check, amount in relevant_checks:
            buyer_account = self.get_account(check.owner_public_key)
            seller_bank = list(
                filter(lambda b: b.has_account(note.draft.seller_public_key),
                       known_banks()))[0]
            seller_account = seller_bank.get_account(
                note.draft.seller_public_key)

            assert buyer_account
            assert seller_account

            buyer_device_data = buyer_account.get_device(
                check.owner_public_key)

            if buyer_device_data.is_unspent(check):
                buyer_device_data.spend_check(check)
            else:
                raise FraudException(
                    'Oh lawd %s is double-spending!' % buyer_account.owner)

            buyer_account.withdraw(amount)
            seller_account.deposit(amount)

    def to_json(self):
        return {'Identifier': self.identifier, 'Public key': str(self.public_key), 'Private key': str(self.private_key)}

    def __str__(self) -> str:
        return json.dumps(self.to_json(), indent=2)
