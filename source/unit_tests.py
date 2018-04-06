import unittest
from Crypto.PublicKey import ECC

from bank import Bank, Account
from account_holder_device import AccountHolderDevice
from promissory_note import Check, PromissoryNote, PromissoryNoteDraft
from signing_protocol import create_promissory_note
import random


class TestAccountHolderDevice(unittest.TestCase):
    def test_create(self):
        """Tests that an account holder device can be created."""
        AccountHolderDevice()

    def test_bank_keyring(self):
        """Tests that the bank keyring functionality of an account
           holder device works as advertised."""
        device = AccountHolderDevice()
        bank_id = 42
        bank_key = ECC.generate(curve='P-256').public_key()
        assert not device.is_known_bank(bank_id)
        device.register_bank(bank_id, bank_key)
        assert device.is_known_bank(bank_id)
        assert device.get_bank_public_key(bank_id) == bank_key


class TestBank(unittest.TestCase):
    def test_create(self):
        """Tests that a bank can be created."""
        Bank(42)

    def test_add_device(self):
        bank = Bank(42)
        device = AccountHolderDevice()
        account = Account("Bill")
        bank.add_device(account, device)
        assert bank.get_account(device.public_key) == account
        assert bank.get_device(device.public_key)[0] == device


class TestSigningProtocol(unittest.TestCase):
    def test_create_promissory_note(self):
        """Tests that a Promissory Note can be created."""
        buyer = AccountHolderDevice()
        seller = AccountHolderDevice()

        create_promissory_note(buyer, seller, 0)

if __name__ == '__main__':
    unittest.main()
