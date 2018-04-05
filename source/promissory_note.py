"""Introduces the notions of a check, a promissory note draft and a promissory note."""

import pickle
from Crypto.Hash import SHA256
from Crypto.Signature import DSS


def sign_DSS(message, private_key):
    """Signs a particular message using a private key."""
    # TODO: is SHA256 okay here? Probably not, but pycryptodome doesn't
    # seem to implement SHA-3. So we should probably think about whether
    # SHA256 is good enough for our purposes or not.
    h = SHA256.new(message)
    # TODO: should be use 'fips-186-3' or the deterministic mode here?s
    signer = DSS.new(key, 'fips-186-3')
    return signer.sign(h)


def verify_DSS(message, signature, public_key):
    """Verifies that a signature of a particular message is authentic."""
    h = SHA256.new(message)
    verifier = DSS.new(public_key, 'fips-186-3')
    try:
        verifier.verify(h, signature)
        return True
    except ValueError:
        return False


class Check(object):
    """A check that is signed by the bank."""

    def __init__(self, bank_id, owner_public_key, value, identifier,
                 signature):
        """Creates a check from a bank id, the public key of the account holder
           for which the check is issued, the max value of the check, an
           identifier for the check and a signature."""
        self.bank_id = bank_id
        self.owner_public_key = owner_public_key
        self.value = value
        self.identifier = identifier
        self.signature = signature

    def write_to(self, target):
        """Writes this check to a file."""
        # TODO: we should probably define and implement a *portable*
        # format that is not tied to Python's pickle library.
        pickle.dump(self, target)

    @staticmethod
    def read_from(source):
        """Reads a check from a file."""
        return pickle.load(source)


class PromissoryNoteDraft(object):
    """A draft promissory note, that is the unsigned part of a promissory note."""

    def __init__(self, seller_public_key, identifier, value):
        """Creates a promissory note draft from a seller's public key,
           an identifier for the note and the total amount of money
           transferred by the note."""
        self.seller_public_key = seller_public_key
        self.identifier = identifier
        self.value = value
        self.checks = []

    def append_check(self, check):
        """Adds a check to this promissory note draft."""
        self.checks.append(check)

    def write_to(self, target):
        """Writes this draft promissory note to a file."""
        # TODO: we should probably define and implement a *portable*
        # format that is not tied to Python's pickle library.
        pickle.dump(self, target)

    @staticmethod
    def read_from(source):
        """Reads a draft promissory note from a file."""
        return pickle.load(source)


class PromissoryNote(object):
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
        return PromissoryNoteDraft.read_from(self.draft_bytes)

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
                          self.draft.checks[0].owner_public_key)

    def sign_seller(self, private_key):
        """Signs this promissory note using the seller's private key."""
        self.seller_signature = sign_DSS(self.draft_bytes, private_key)

    def sign_buyer(self, private_key):
        """Signs this promissory note using the buyer's private key."""
        self.buyer_signature = sign_DSS(
            self.draft_bytes + self.seller_signature, private_key)

    def write_to(self, target):
        """Writes this promissory note to a file."""
        pickle.dump(self, target)

    @staticmethod
    def read_from(source):
        """Reads a promissory note from a file."""
        return pickle.load(source)
