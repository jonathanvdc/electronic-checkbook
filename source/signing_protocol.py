"""An implementation of the protocol for creating a fully signed promissory note."""

from account_holder_device import AccountHolderDevice
from promissory_note import Check, PromissoryNote, PromissoryNoteDraft


def create_promissory_note(buyer_device, seller_device, amount):
    """Creates a fully signed promissory note for the transferral of
       a particular amount of money from one account holder (the "buyer")
       to another (the "seller")."""
    # Create a draft promissory note.
    draft = seller_device.draft_promissory_note(amount)

    # Have the buyer attach checks to it.
    buyer_device.add_payment(draft)

    # Sign the damn thing already.
    note = PromissoryNote(draft.to_bytes())
    note.sign_seller(seller_device.private_key)
    note.sign_buyer(buyer_device.private_key)

    return note


def transfer(buyer_device, seller_device, amount):
    """Transfers a particular amount of money from one account holder
       (the "buyer") to another (the "seller")."""
    # Create and sign a note.
    note = create_promissory_note(buyer_device, seller_device, amount)

    # TODO: verify the signed note.

    # Send it to the bank.
    # TODO: actually implement this.
    raise NotImplementedError
