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

    # Verify the signatures
    if not note.is_seller_signature_authentic:
        raise ValueError("The signature of the the seller is not authentic.")

    if not note.is_buyer_signature_authentic:
        raise ValueError("The signature of the the buyer is not authentic.")

    # Verify amount on promissory note
    if not note.has_correct_total_check_value:
        raise ValueError("The total check value contained within the promissory note "
                         "does not correspond to the value specified by that selfsame note.")

    # Verify check amounts
    if not note.has_correct_check_values:
        raise ValueError("Some of the checks contained within the promissory note "
                         "list values exceeding their respective maximum values.")

    # Send it to the bank.
    # TODO: actually implement this.

    raise NotImplementedError
