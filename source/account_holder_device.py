"""Implements the data store used by account holder devices."""

import math
import json
from collections import deque, defaultdict
from Crypto.PublicKey import ECC

from promissory_note import PromissoryNoteDraft, sign_DSS, verify_DSS, string_to_bytes, uint32_to_bytes, uint64_to_bytes
from datetime import date, datetime, timedelta


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
        self.internet_connection = True
        self.promissory_note_counter = 0
        self.unspent_checks = defaultdict(deque)
        self.bank_keys = {}
        self.max_overcharge = 0.1
        self.check_punishment = 0.5

    @property
    def total_check_value(self):
        """Gets the total value of all checks in this account holder device."""
        return sum([
            check.value
            for value_queue in self.unspent_checks.values()
            for check in value_queue
        ])

    def get_cert(self):
        return self.cert

    def set_cert(self, value):
        self.cert = value

    def all_unspent_checks(self):
        return [
            check
            for value_queue in self.unspent_checks.values()
            for check in value_queue
        ]

    def add_unspent_check(self, check):
        """Adds an unspent check to this account holder device."""
        assert check.owner_public_key == self.public_key
        self.unspent_checks[check.value].append(check)

    def remove_expired_checks(self):
        """Removes all checks that can no longer be used in promissory notes from the unspent checks."""
        for check_deque in self.unspent_checks.values():
            expired_checks = filter(lambda b: b.expired, check_deque)
            for expired_check in expired_checks:
                check_deque.remove(expired_check)

    def register_name(self, name):
        self.name = name

    def register_bank(self, bank_id, bank_public_key):
        """Registers a bank by mapping its unique identifier to its public key."""
        self.bank_keys[bank_id] = bank_public_key

        # future_date = datetime.now()
        # try:
        #     future_date = future_date.replace(year=datetime.now().year + 1)
        # except ValueError:
        #     future_date = future_date + (date(future_date.year + 1, 1, 1) - date(future_date.year, 1, 1))
        #
        # self.set_cert(DeviceCertificate(self.name, self.public_key, self.private_key, future_date))

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

    def toggle_internet(self):
        self.internet_connection = not self.internet_connection

    def add_payment(self, draft):
        """Adds a number of checks to a particular promissory note draft."""
        assert draft.total_check_value == 0

        # Remove all expired checks first so no expired checks will be used in a promissory note.
        self.remove_expired_checks()

        if draft.value > self.total_check_value:
            raise ValueError(
                'Cannot add payment to the promissory note draft: '
                'not enough checks on hand.')
        if draft.value == 0:
            assert draft.total_check_value == draft.value
            return
        if draft.value < 0:
            raise ValueError
        remaining_value = draft.value
        # estimate the maximum total value of checks that will be used in this draft
        max_spending = int(
            math.ceil(remaining_value + remaining_value * self.max_overcharge))
        # use the estimate to filter out some check values.
        # => checks with higher value would never be used anyway
        possible_values = \
            sorted([x for x in self.unspent_checks.keys() if (self.unspent_checks[x]) and (x < max_spending)])
        # the number of usable checks with these values
        checks_per_value = [
            len(self.unspent_checks[x]) for x in possible_values
        ]

        m = []
        biggest_unit = None
        if possible_values:

            # find the gcd of all check values.
            # if all checks are a multiple of 5 then looking for values that are not a multiple of 5 is a waste of time.
            biggest_unit = possible_values[0]
            for value in possible_values[1:]:
                biggest_unit = math.gcd(biggest_unit, value)

            possible_values = [int(x / biggest_unit) for x in possible_values]
            remaining_value = int(math.ceil(remaining_value / biggest_unit))
            max_spending = int(
                math.ceil(remaining_value + min(
                    max(remaining_value * self.max_overcharge, possible_values[
                        0]), possible_values[-1])))

            m = [None] * (max_spending + 1)
            # find the smallest combination of checks needed for different values
            for j, v in enumerate(possible_values):
                if v <= max_spending:
                    m[v] = ([v], list(checks_per_value))
                    m[v][1][j] -= 1

            for i in range(possible_values[0], len(m)):
                for j, v in enumerate(possible_values):
                    if (i - v >= 0) and (m[i - v] is not None) and (
                            m[i - v][1][j] > 0):
                        if (m[i] is None) or (len(m[i][0]) >
                                              (len(m[i - v][0]) + 1)):
                            checks = list(m[i - v][0])
                            checks.append(v)
                            remaining = list(m[i - v][1])
                            remaining[j] -= 1
                            m[i] = (checks, remaining)
            # remove values that are too low.
            m = m[remaining_value:]
            # calculate a score for each of the check combinations
            m = [((sum(x[0]) * biggest_unit - draft.value) + len(x[0]) *
                  self.check_punishment, x) for x in m if x is not None]
            remaining_value = draft.value
        if m:
            # if at least one valid check combination was found, use the combination with the best score
            optimum = [
                x * biggest_unit for x in min(m, key=lambda x: x[0])[1][0]
            ]
            for value in optimum:
                unused_check = self.unspent_checks[value].popleft()
                amount = min(remaining_value, unused_check.value)
                draft.append_check(unused_check, amount)
                remaining_value -= amount
        else:
            # no valid check combination was found.
            # possible causes: all reasonably small checks have been used, ...
            # use an other algorithm instead
            # less optimal
            check_values = sorted(
                [
                    x for x in self.unspent_checks.keys()
                    if self.unspent_checks[x]
                ],
                reverse=True)
            biggest_unit = check_values[0]
            for value in check_values[1:]:
                biggest_unit = math.gcd(biggest_unit, value)

            check_values = iter(check_values)
            pseudo_remaining_value = biggest_unit * (math.ceil(
                remaining_value / biggest_unit))

            value = next(check_values, None)
            checks = []
            while (remaining_value > 0) and (value is not None):
                if (self.unspent_checks[value]) and (
                        value <= pseudo_remaining_value):
                    unused_check = self.unspent_checks[value].popleft()
                    amount = min(unused_check.value, remaining_value)
                    checks.append((unused_check, amount))
                    remaining_value -= amount
                    pseudo_remaining_value -= amount
                else:
                    value = next(check_values, None)
            if remaining_value != 0:
                value = min([
                    x for x in self.unspent_checks.keys()
                    if (self.unspent_checks[x]) and (x >= remaining_value)
                ])
                unused_check = self.unspent_checks[value].popleft()
                checks.append([unused_check, remaining_value])

            # check if some checks can be omitted if so do so
            checks = checks[::-1]
            while True:
                extra = sum([x[0].value for x in checks]) - draft.value
                n = next((x for x in checks if x[0].value <= extra), None)
                if n is not None:
                    checks[0][1] += n[0].value
                    checks.remove(n)
                    self.add_unspent_check(n)
                else:
                    break
            for check, amount in checks:
                assert amount <= check.value
                draft.append_check(check, amount)
        assert draft.total_check_value == draft.value

    def to_json(self):
        return {
            'Public key':
            str(self.public_key),
            'Private key':
            str(self.private_key),
            'Checks': [
                check.to_json()
                for value_queue in self.unspent_checks.values()
                for check in value_queue
            ]
        }

    def __str__(self) -> str:
        return json.dumps(self.to_json(), indent=2)


class DeviceCertificate:
    """A certificate that authenticates an account holder device."""

    def __init__(self, message, AHD_public_key, bank_private_key, valid_until,
                 bankID):
        if not all(x.isalpha() or x.isspace() for x in message):
            raise ValueError("invalid message")
        if not isinstance(valid_until, datetime):
            raise ValueError("invalid end time")

        self.AHD_public_key = AHD_public_key
        self.bankID = bankID
        self.message = message
        self.valid_until = valid_until.strftime('%d%m%Y')
        self.signature = sign_DSS(self.__get_unsigned_bytes(),
                                  bank_private_key)

    def __get_unsigned_bytes(self):
        return string_to_bytes(self.AHD_public_key) + \
            string_to_bytes(self.message) + \
            string_to_bytes(self.valid_until)

    def validate(self, AHD_public_key, bank_public_key):
        if datetime.strptime(self.valid_until, '%d%m%Y') < datetime.now():
            return False
        if AHD_public_key != self.AHD_public_key: return False
        return verify_DSS(self.__get_unsigned_bytes(), self.signature,
                          bank_public_key)
