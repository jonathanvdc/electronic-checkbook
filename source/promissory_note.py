"""Introduces the notions of a check, a promissory note draft and a promissory note."""

import pickle
import json
from Crypto.Hash import SHA3_256
from Crypto.Signature import DSS
from Crypto.PublicKey import ECC
from datetime import date, datetime


def sign_DSS(message, private_key):
    """Signs a particular message using a private key."""
    h = SHA3_256.new(message)
    # TODO: should we use 'fips-186-3' or the deterministic mode here?
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


class Serializable(object):
    """A base class for objects that can be encoded and decoded again."""

    def write_to(self, target):
        """Writes this object to a file."""
        # TODO: we should probably define and implement a *portable*
        # format that is not tied to Python's pickle library.
        pickle.dump(self, target)

    def to_bytes(self):
        """Produces a byte string that represents this object."""
        # TODO: apparently this causes issues, so I switched to pickle.dumps instead
        # buf = io.BytesIO()
        # self.write_to(buf)
        # buf.seek(0)
        # result = buf.read()
        # buf.close()
        return pickle.dumps(self)

    @staticmethod
    def read_from(source):
        """Reads an object from a file."""
        return pickle.load(source)

    @staticmethod
    def from_bytes(source):
        """Reads an object from a byte string."""
        return pickle.loads(source)


class Check(Serializable):
    """A check that is signed by the bank."""

    def __init__(self, bank_id, owner_public_key, value, identifier,
                 signature=b''):
        """Creates a check from a bank id, the public key of the account holder
           for which the check is issued, the max value of the check, an
           identifier for the check and a signature."""
        self.bank_id = bank_id
        self.owner_public_key = owner_public_key
        self.value = value
        self.identifier = identifier
        self.signature = signature

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
        return {'bank_id': self.bank_id,
                'owner_public_key': self.owner_public_key.export_key(format='PEM'),
                'value': self.value,
                'identifier': self.identifier,
                'signature': self.signature}

    def __setstate__(self, state):
        """Sets the state of this object for deserialization."""
        self.bank_id = state['bank_id']
        self.owner_public_key = ECC.import_key(state['owner_public_key'])
        self.value = state['value']
        self.identifier = state['identifier']
        self.signature = state['signature']

    def __get_unsigned_version(self):
        return Check(self.bank_id, self.owner_public_key, self.value, self.identifier, b'')

    def __get_unsigned_bytes(self):
        return self.__get_unsigned_version().to_bytes()

    @property
    def is_signature_authentic(self, bank_public_key):
        """Verifies the bank's signature. Returns a Boolean
           that tells if the signature is authentic."""
        return verify_DSS(self.__get_unsigned_bytes(), self.signature, bank_public_key)

    def sign(self, bank_private_key):
        """Signs this check using the bank's private key."""
        self.signature = sign_DSS(self.__get_unsigned_bytes(), bank_private_key)

    def to_json(self):
        return {'Identifier': self.identifier, 'Bank id': self.bank_id, 'Value': self.value}

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

    def __getstate__(self):
        """Retrieves the state of this object for serialization."""
        # Apparently the public key used by the pycrypto module wasn't supported by pickle,
        # but it was possible to force the issue but using the key's built-in serialization
        return {'seller_public_key': self.seller_public_key.export_key(format='PEM'),
                'identifier': self.identifier,
                'value': self.value,
                'checks': self.checks,
                'transaction_date': self.transaction_date.strftime('%d%m%Y')}

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

    def append_check(self, check, amount):
        """Adds a check to this promissory note draft and annotates it with
           the amount of currency that is assigned to it."""
        assert check.value >= amount
        self.checks.append((check, amount))

    # TODO: Should transaction date be include din the JSON representation? See also 'PromissoryNote'
    def to_json(self):
        return {'Identifier': self.identifier, 'Seller public key': str(self.seller_public_key), 'Value': self.value}

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
        return all(map(lambda check: check[0].value >= check[1], self.draft.checks))

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
        return {'Seller signature': str(self.seller_signature), 'Buyer Signature': str(self.buyer_signature)}

    def __str__(self) -> str:
        return json.dumps(self.to_json(), indent=2)
