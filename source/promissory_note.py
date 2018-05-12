"""Introduces the notions of a check, a promissory note draft and a promissory note."""

import pickle
import json
import struct
from Crypto.Hash import SHA3_256
from Crypto.Signature import DSS
from Crypto.PublicKey import ECC
from datetime import date, datetime, timedelta

DAYS_VALID = 10
CHECK_EXPIRATION = 100


def sign_DSS(message, private_key):
    """Signs a particular message using a private key."""
    h = SHA3_256.new(message)
    signer = DSS.new(private_key, 'fips-186-3')
    return signer.sign(h)


def verify_DSS(message, signature, public_key):
    """Verifies that a signature of a particular message is authentic."""
    h = SHA3_256.new(message)
    verifier = DSS.new(public_key, 'fips-186-3')
    try:
        verifier.verify(h, signature)
        return True
    except ValueError:
        return False


def uint32_to_bytes(value):
    """Encodes a 32-bit unsigned integer as a byte string."""
    return struct.pack('<I', value)


def uint64_to_bytes(value):
    """Encodes a 64-bit unsigned integer as a byte string."""
    return struct.pack('<L', value)


def string_to_bytes(value):
    """Encodes a string as a length-prefixed UTF-8 encoded sequence of bytes."""
    return bytestring_to_bytes(value.encode('utf8'))


def bytestring_to_bytes(value):
    """Encodes a byte string as a length-prefixed sequence of bytes."""
    return uint32_to_bytes(len(value)) + value


def uint32_from_bytes(value):
    """Decodes a byte string as a 32-bit unsigned integer.
       Returns the decoded integer and the remainder of
       the byte string."""
    fmt = '<I'
    size = struct.calcsize(fmt)
    result, = struct.unpack_from(fmt, value)
    return result, value[size:]


def uint64_from_bytes(value):
    """Decodes a byte string as a 64-bit unsigned integer.
       Returns the decoded integer and the remainder of
       the byte string."""
    fmt = '<L'
    size = struct.calcsize(fmt)
    result, = struct.unpack_from(fmt, value)
    return result, value[size:]


def bytestring_from_bytes(value):
    """Encodes a byte string as a length-prefixed sequence of bytes.
       Returns the decoded byte string and the remainder of
       the byte string"""
    length, data = uint32_from_bytes(value)
    return data[:length], data[length:]


def string_from_bytes(value):
    """Decodes a byte string as a length-prefixed UTF-8 encoded sequence of bytes."""
    bytestr, remainder = bytestring_from_bytes(value)
    return bytestr.decode('utf8'), remainder


class Serializable(object):
    """A base class for objects that can be encoded and decoded again."""

    def to_bytes(self):
        """Produces a byte string that represents this object."""
        # TODO: we should probably define and implement a *portable*
        # format that is not tied to Python's pickle library.
        return pickle.dumps(self)

    @staticmethod
    def from_bytes(source):
        """Reads an object from a byte string."""
        return pickle.loads(source)


class Check(Serializable):
    """A check that is signed by the bank."""

    def __init__(self,
                 bank_id,
                 owner_public_key,
                 value,
                 identifier,
                 signature=b''):
        """Creates a check from a bank id, the public key of the account holder
           for which the check is issued, the max value of the check, an
           identifier for the check and a signature."""
        self.bank_id = bank_id
        self.owner_public_key = owner_public_key
        self.value = value
        self.identifier = identifier
        self.signature = signature
        self.expiration_date = date.today() + timedelta(CHECK_EXPIRATION)

    def __eq__(self, other):
        """Tests if this check equals another check."""
        return self.__getstate__() == other.__getstate__()

    def __hash__(self):
        """Computes a hash value for this check."""
        return hash(frozenset(self.__getstate__().items()))

    def __getstate__(self):
        """Retrieves the state of this object for serialization."""
        # Apparently the public key used by the pycrypto module wasn't supported by pickle,
        # but it was possible to force the issue but using the key's built-in serialization
        return {
            'bank_id': self.bank_id,
            'owner_public_key': self.owner_public_key.export_key(format='PEM'),
            'value': self.value,
            'identifier': self.identifier,
            'signature': self.signature,
            'expiration_date': self.expiration_date.strftime('%d%m%Y')
        }

    def __setstate__(self, state):
        """Sets the state of this object for deserialization."""
        self.bank_id = state['bank_id']
        self.owner_public_key = ECC.import_key(state['owner_public_key'])
        self.value = state['value']
        self.identifier = state['identifier']
        self.signature = state['signature']
        self.expiration_date = datetime.strptime(state['expiration_date'], '%d%m%Y').date()

    def __get_unsigned_version(self):
        return Check(self.bank_id, self.owner_public_key, self.value,
                     self.identifier, b'')

    def __get_unsigned_bytes(self):
        return uint32_to_bytes(self.bank_id) + \
            string_to_bytes(self.owner_public_key.export_key(format='PEM')) + \
            uint32_to_bytes(self.value) + \
            uint64_to_bytes(self.identifier)

    def to_bytes(self):
        """Produces a byte string that represents this check."""
        return self.__get_unsigned_bytes() + bytestring_to_bytes(self.signature)

    @staticmethod
    def from_bytes(check_bytes):
        """Reads a check from a byte string."""
        bank_id, check_bytes = uint32_from_bytes(check_bytes)
        owner_public_key, check_bytes = string_from_bytes(check_bytes)
        value, check_bytes = uint32_from_bytes(check_bytes)
        identifier, check_bytes = uint64_from_bytes(check_bytes)
        signature, check_bytes = bytestring_from_bytes(check_bytes)
        return Check(
            bank_id,
            ECC.import_key(owner_public_key),
            value,
            identifier,
            signature)

    @property
    def expired(self):
        """Indicates if the check has expired and thus can no longer be used in promissory notes."""
        return date.today() > self.expiration_date

    @property
    def unredeemable(self):
        """Indicates if the check can no longer be redeemed by sellers."""
        return date.today() > self.expiration_date + timedelta(DAYS_VALID)

    @property
    def is_signature_authentic(self, bank_public_key):
        """Verifies the bank's signature. Returns a Boolean
           that tells if the signature is authentic."""
        return verify_DSS(self.__get_unsigned_bytes(), self.signature,
                          bank_public_key)

    def sign(self, bank_private_key):
        """Signs this check using the bank's private key."""
        self.signature = sign_DSS(self.__get_unsigned_bytes(),
                                  bank_private_key)

    def to_json(self):
        return {
            'Identifier': self.identifier,
            'Bank id': self.bank_id,
            'Value': self.value
        }

    def __str__(self) -> str:
        return json.dumps(self.to_json(), indent=2)


class PromissoryNoteDraft(Serializable):
    """A draft promissory note, that is the unsigned part of a promissory note."""

    def __init__(self, seller_public_key, identifier, value):
        """Creates a promissory note draft from a seller's public key,
           an identifier for the note and the total amount of money
           transferred by the note."""
        self.seller_public_key = seller_public_key
        self.identifier = identifier
        self.value = value
        self.checks = []
        self.transaction_date = date.today()

    def __eq__(self, other):
        """Tests if this draft note equals another draft note."""
        return self.__getstate__() == other.__getstate__()

    def __hash__(self):
        """Computes a hash value for this draft."""
        return hash(frozenset(self.__getstate__().items()))

    def __getstate__(self):
        """Retrieves the state of this object for serialization."""
        # Apparently the public key used by the pycrypto module wasn't supported by pickle,
        # but it was possible to force the issue but using the key's built-in serialization
        return {
            'seller_public_key': self.seller_public_key.export_key(format='PEM'),
            'identifier': self.identifier,
            'value': self.value,
            'checks': self.checks,
            'transaction_date': self.transaction_date.strftime('%d%m%Y')
        }

    def __setstate__(self, state):
        """Sets the state of this object for deserialization."""
        self.seller_public_key = ECC.import_key(state['seller_public_key'])
        self.identifier = state['identifier']
        self.value = state['value']
        self.checks = state['checks']
        self.transaction_date = datetime.strptime(state['transaction_date'], '%d%m%Y').date()

    @property
    def total_check_value(self):
        """Gets the sum of the amounts with which the checks in this
           promissory note draft are annotated."""
        return sum(amount for _, amount in self.checks)

    @property
    def is_claimable(self):
        """Indicates if the note is still claimable (if its transaction date falls within
        a set amount of days of the current date)"""
        return (date.today() - self.transaction_date).days <= DAYS_VALID

    @property
    def affects_monthly_cap(self):
        """Indicates whether the note's transaction date falls in the current month, and thus affects this month's running spending cap"""
        return self.transaction_date.year == date.today().year and self.transaction_date.month == date.today().month

    def append_check(self, check, amount):
        """Adds a check to this promissory note draft and annotates it with
           the amount of currency that is assigned to it."""
        assert check.value >= amount
        self.checks.append((check, amount))

    # TODO: Should transaction date be include din the JSON representation? See also 'PromissoryNote'
    def to_json(self):
        return {
            'Identifier': self.identifier,
            'Seller public key': str(self.seller_public_key),
            'Value': self.value
        }

    def __str__(self) -> str:
        return json.dumps(self.to_json(), indent=2)


class PromissoryNote(Serializable):
    """A signed promissory note."""

    def __init__(self, draft_bytes, seller_signature=b'', buyer_signature=b''):
        """Creates a promissory note from a draft promissory note (as bytes),
           a seller signature and a buyer signature."""
        self.draft_bytes = draft_bytes
        self.seller_signature = seller_signature
        self.buyer_signature = buyer_signature

    @property
    def draft(self):
        """Gets the decoded draft promissory note at the heart of this
           fully-signed promissory note."""
        return PromissoryNoteDraft.from_bytes(self.draft_bytes)

    @property
    def is_seller_signature_authentic(self):
        """Verifies the seller's signature. Returns a Boolean
           that tells if the signature is authentic."""
        return verify_DSS(self.draft_bytes, self.seller_signature,
                          self.draft.seller_public_key)

    @property
    def is_buyer_signature_authentic(self):
        """Verifies the buyer's signature. Returns a Boolean
           that tells if the signature is authentic."""
        return verify_DSS(self.draft_bytes + self.seller_signature,
                          self.buyer_signature,
                          self.draft.checks[0][0].owner_public_key)

    @property
    def has_correct_total_check_value(self):
        """Verifies whether the total check value corresponds to the value
        specified by the promissory note. Returns a Boolean reflecting the truth of this property."""
        return self.draft.total_check_value == self.draft.value

    @property
    def has_correct_check_values(self):
        """Verifies whether the individual checks contained by this promissory note are valid; that is,
        whether their individually contained values do not exceed their respective maximum values."""
        return all(
            map(lambda check: check[0].value >= check[1], self.draft.checks))

    @property
    def has_correct_transaction_date(self):
        """Verifies whether the transaction date corresponds to the current date.
        Returns a Boolean reflecting the truth of this property"""
        return self.draft.transaction_date == date.today()

    def sign_seller(self, private_key):
        """Signs this promissory note using the seller's private key."""
        self.seller_signature = sign_DSS(self.draft_bytes, private_key)

    def sign_buyer(self, private_key):
        """Signs this promissory note using the buyer's private key."""
        self.buyer_signature = sign_DSS(
            self.draft_bytes + self.seller_signature, private_key)

    def to_json(self):
        return {
            'Seller signature': str(self.seller_signature),
            'Buyer Signature': str(self.buyer_signature)
        }

    def __str__(self) -> str:
        return json.dumps(self.to_json(), indent=2)
