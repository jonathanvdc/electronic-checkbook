"""Implements the data store used by account holder devices."""

from collections import deque
from Crypto.PublicKey import ECC

from promissory_note import Check, PromissoryNote, PromissoryNoteDraft


class AccountHolderDevice(object):
    """The data store used by account holder devices."""

    def __init__(self, private_key=None):
        """Creates an empty account holder device from a private key.
           Generates a private key automatically if none is specified."""
        if private_key is None:
            # Generate an ECC private key.
            private_key = ECC.generate(curve='P-256')

        self.private_key = private_key
        self.public_key = private_key.public_key()
        self.promissory_note_counter = 0
        self.unspent_checks = deque()
        self.bank_keys = {}

    @property
    def total_check_value(self):
        """Gets the total value of all checks in this account holder device."""
        return sum(check.value for check in self.unspent_checks)

    def add_unspent_check(self, check):
        """Adds an unspent check to this account holder device."""
        assert check.owner_public_key == self.public_key
        self.unspent_checks.append(check)

    def register_bank(self, bank_id, bank_public_key):
        """Registers a bank by mapping its unique identifier to its public key."""
        self.bank_keys[bank_id] = bank_public_key

    def is_known_bank(self, bank_id):
        """Tests if the bank with a particular identifier is known to
           this account holder device."""
        return bank_id in self.bank_keys

    def get_bank_public_key(self, bank_id):
        """Gets the public key for the bank with a particular identifier."""
        return self.bank_keys[bank_id]

    def draft_promissory_note(self, amount):
        """Creates a draft promissory note for a particular amount of money.
           This account holder serves as the "seller" party, that is, the
           recipient of the money."""
        draft = PromissoryNoteDraft(self.public_key,
                                    self.promissory_note_counter, amount)
        self.promissory_note_counter += 1
        return draft

    def add_payment(self, draft):
        """Adds a number of checks to a particular promissory note draft."""
        assert draft.total_check_value == 0

        if draft.value > self.total_check_value:
            raise ValueError(
                'Cannot add payment to the promissory note draft: '
                'not enough checks on hand.')

        # Simply add checks to the draft promissory note until the total
        # amount of money specified by the checks equals the amount
        # specified by the draft promissory note.
        #
        # TODO: maybe we should be smarter here and try to minimize both the
        # number of used checks and the amount of 'lost value' due to spending
        # checks that are too large.
        remaining_value = draft.value
        while remaining_value > 0:
            unused_check = self.unspent_checks.popleft()
            amount = min(remaining_value, unused_check.value)
            draft.append_check(unused_check, check)
            remaining_value -= amount

        assert draft.total_check_value == draft.value
