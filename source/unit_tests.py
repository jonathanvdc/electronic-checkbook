import unittest

from account_holder_device import AccountHolderDevice
from promissory_note import Check, PromissoryNote, PromissoryNoteDraft


class TestAccountHolderDevice(unittest.TestCase):
    def test_create(self):
        """Tests that an account holder device can be created."""
        AccountHolderDevice()


if __name__ == '__main__':
    unittest.main()
