import unittest
from Crypto.PublicKey import ECC

from account_holder_device import AccountHolderDevice
from promissory_note import Check, PromissoryNote, PromissoryNoteDraft


class TestAccountHolderDevice(unittest.TestCase):
    def test_create(self):
        """Tests that an account holder device can be created."""
        AccountHolderDevice()

    def test_bank_keyring(self):
        """Tests that the bank keyring functionality of an account
           holder device works as advertised."""
        device = AccountHolderDevice()
        bank_id = 42
        bank_key = ECC.generate(curve='P-256')
        assert not device.is_known_bank(bank_id)
        device.register_bank(bank_id, bank_key)
        assert device.is_known_bank(bank_id)
        assert device.get_bank_public_key(bank_id) == bank_key


if __name__ == '__main__':
    unittest.main()
