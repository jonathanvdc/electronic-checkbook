"""Introduces the notions of a check, a promissory note draft and a promissory note."""

import pickle

class Check(object):
    """A check that is signed by the bank."""
    def __init__(self, bank_id, account_holder_public_key, value, identifier, signature):
        self.bank_id = bank_id
        self.account_holder_public_key = account_holder_public_key
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
        """Writes this promissory note to a file."""
        # TODO: we should probably define and implement a *portable*
        # format that is not tied to Python's pickle library.
        pickle.dump(self, target)

    @staticmethod
    def read_from(source):
        """Reads a promissory note from a file."""
        return pickle.load(source)

class PromissoryNote(object):
    """A signed promissory note."""
    def __init__(self, draft_bytes, seller_signature, buyer_signature):
        """Creates a promissory note from a draft promissory note (as bytes),
           a seller signature and a buyer signature."""
        self.draft_bytes = draft_bytes
        self.seller_signature = seller_signature
        self.buyer_signature = buyer_signature

    @property
    def draft(self):
        """Gets the decoded draft promissory note signed here."""
        return PromissoryNoteDraft.read_from(self.draft_bytes)
