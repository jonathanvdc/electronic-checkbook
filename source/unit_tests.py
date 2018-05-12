#!/usr/bin/env python3
"""A collection of unit tests for our electronic checkbook system"""

import unittest
import random
from Crypto.PublicKey import ECC

from bank import Bank, Account, AccountDeviceData, FraudException
from account_holder_device import AccountHolderDevice
from promissory_note import Check, PromissoryNote, PromissoryNoteDraft
from signing_protocol import create_promissory_note, perform_transaction, register_bank
from main_cli import Person

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
        """Tests that a device can be added to a bank."""
        bank = Bank(42)
        device = AccountHolderDevice()
        account = Account(Person("Bill"))
        device_data, cert = bank.add_device(account, device.public_key)
        device.set_cert(cert)
        assert bank.get_account(device.public_key) == account
        assert bank.get_device(device.public_key) == device_data


class TestSerializable(unittest.TestCase):
    def test_serialize_check(self):
        """Tests that a check can be serialized."""
        bank = Bank(42)
        device = AccountHolderDevice()
        data = AccountDeviceData(device.public_key, 1000)
        random.seed(None)
        val = random.randint(1, 10)
        check = data.generate_check(val, bank)
        serialized = check.to_bytes()
        deserialized = Check.from_bytes(serialized)
        assert deserialized.to_bytes() == serialized
        assert deserialized.bank_id == 42
        assert deserialized.value == val

    def test_serialize_promissory_note_draft(self):
        """Tests that a promissory note draft can be serialized."""
        device = AccountHolderDevice()
        random.seed(None)
        draft = device.draft_promissory_note(random.randint(1, 10))
        serialized = draft.to_bytes()
        deserialized = PromissoryNoteDraft.from_bytes(serialized)
        assert deserialized.to_bytes() == serialized

    def test_serialize_promisory_note(self):
        """Tests that a promisory note can be serialized."""
        device = AccountHolderDevice()
        random.seed(None)
        draft = device.draft_promissory_note(random.randint(1, 10))
        note = PromissoryNote(draft.to_bytes())
        serialized = note.to_bytes()
        deserialized = PromissoryNote.from_bytes(serialized)
        assert deserialized.to_bytes() == serialized


class TestSigningProtocol(unittest.TestCase):
    def test_create_promissory_note(self):
        """Tests that a Promissory Note can be created."""
        buyer_device = AccountHolderDevice()
        seller_device = AccountHolderDevice()

        create_promissory_note(buyer_device, seller_device, 0)

    def test_transfer(self):
        """Tests that a transfer can be made between a buyer and a seller."""
        buyer_bank = Bank(42)
        seller_bank = Bank(43)

        register_bank(buyer_bank)
        register_bank(seller_bank)

        buyer_device = AccountHolderDevice()
        seller_device = AccountHolderDevice()

        buyer_device.register_bank(buyer_bank.identifier, buyer_bank.public_key)
        seller_device.register_bank(seller_bank.identifier, seller_bank.public_key)

        buyer_account = Account(Person("buyer"))
        seller_account = Account(Person("seller"))

        buyer_account.deposit(1000)

        buyer_bank.add_device(buyer_account, buyer_device.public_key, 1000, 1000)
        seller_bank.add_device(seller_account, seller_device.public_key)

        check = buyer_bank.issue_check(buyer_device.public_key, 10)
        buyer_device.add_unspent_check(check)

        assert len(buyer_device.all_unspent_checks()) == 1
        assert seller_device.promissory_note_counter == 0

        perform_transaction(buyer_device, seller_device, 10)

        assert len(buyer_device.all_unspent_checks()) == 0
        assert seller_device.promissory_note_counter == 1

        assert buyer_account.balance == 990
        assert seller_account.balance == 10

    def test_catch_double_spender(self):
        """Tests that people who try to double-spend checks are caught."""
        bank = Bank(42)
        register_bank(bank)

        buyer_device = AccountHolderDevice()
        seller_device = AccountHolderDevice()

        buyer_device.register_bank(bank.identifier, bank.public_key)
        seller_device.register_bank(bank.identifier, bank.public_key)

        buyer_account = Account(Person("Eric Laermans"))
        seller_account = Account(Person("Carrefour Berchem"))

        buyer_account.deposit(1000)

        bank.add_device(buyer_account, buyer_device.public_key, 1000, 1000)
        bank.add_device(seller_account, seller_device.public_key)

        # Issue a check and spend it.
        check = bank.issue_check(buyer_device.public_key, 10)
        buyer_device.add_unspent_check(check)
        perform_transaction(buyer_device, seller_device, 10)

        # Now make the buyer device recycle that exact same check
        # (i.e., double-spend it).
        buyer_device.add_unspent_check(check)
        with self.assertRaises(FraudException):
            perform_transaction(buyer_device, seller_device, 10)

    def test_cap_enforcement(self):
        """Tests that the bank enforces the cap on an account holder device."""
        bank = Bank(42)
        register_bank(bank)

        buyer_device = AccountHolderDevice()
        seller_device = AccountHolderDevice()

        buyer_device.register_bank(bank.identifier, bank.public_key)
        seller_device.register_bank(bank.identifier, bank.public_key)

        buyer_account = Account(Person("Eric Laermans"))
        seller_account = Account(Person("Carrefour Berchem"))

        buyer_account.deposit(1000)

        _, cert = bank.add_device(buyer_account, buyer_device.public_key, 20, 20)
        buyer_device.set_cert(cert)
        _, cert = bank.add_device(seller_account, seller_device.public_key)
        seller_device.set_cert(cert)
        # Issue two check and spend one.
        check = bank.issue_check(buyer_device.public_key, 10)
        buyer_device.add_unspent_check(check)
        buyer_device.add_unspent_check(bank.issue_check(buyer_device.public_key, 10))
        perform_transaction(buyer_device, seller_device, 10)

        # Verify that issuing another check would exceed the cap.
        with self.assertRaises(ValueError):
            bank.issue_check(buyer_device.public_key, 10)

        # Now reset the counters.
        bank.reset_monthly_spending_caps()

        # Verify that we can issue exactly one check worth 10.
        buyer_device.add_unspent_check(bank.issue_check(buyer_device.public_key, 10))
        with self.assertRaises(ValueError):
            bank.issue_check(buyer_device.public_key, 10)

    def test_check_choice(self):
        """Tests that reasonable checks are chosen when transfering."""
        buyer_bank = Bank(42)
        seller_bank = Bank(43)

        register_bank(buyer_bank)
        register_bank(seller_bank)

        buyer_device = AccountHolderDevice()
        seller_device = AccountHolderDevice()

        buyer_device.register_bank(buyer_bank.identifier, buyer_bank.public_key)
        seller_device.register_bank(seller_bank.identifier, seller_bank.public_key)

        buyer_account = Account(Person("buyer"))
        seller_account = Account(Person("seller"))

        buyer_account.deposit(1000)

        buyer_bank.add_device(buyer_account, buyer_device.public_key, 1000, 1000)
        seller_bank.add_device(seller_account, seller_device.public_key)
        for value, times in [(5, 3), (10, 2), (50, 1), (100, 1), (20, 2)]:
            for _ in range(times):
                check = buyer_bank.issue_check(buyer_device.public_key, value)
                buyer_device.add_unspent_check(check)

        assert len(buyer_device.all_unspent_checks()) == 9
        assert seller_device.promissory_note_counter == 0

        perform_transaction(buyer_device, seller_device, 99)
        perform_transaction(buyer_device, seller_device, 15)
        perform_transaction(buyer_device, seller_device, 55)
        perform_transaction(buyer_device, seller_device, 51)

        assert buyer_account.balance == 780
        assert seller_account.balance == 220


if __name__ == '__main__':
    unittest.main()
