"""An implementation of the protocol for creating a fully signed promissory note."""

from promissory_note import PromissoryNote

bank_repository = []


def register_bank(bank):
    bank_repository.append(bank)


def known_banks():
    return bank_repository


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
    note = PromissoryNote.from_bytes(PromissoryNote.sign_seller(note.to_bytes(), seller_device.private_key))
    note = PromissoryNote.from_bytes(PromissoryNote.sign_buyer(note.to_bytes(), buyer_device.private_key))

    return note


def verify_promissory_note(promissory_note):
    """Verify the promissory note."""
    # Verify the signatures
    if not promissory_note.is_seller_signature_authentic:
        raise ValueError("The signature of the the seller is not authentic.")

    if not promissory_note.is_buyer_signature_authentic:
        raise ValueError("The signature of the the buyer is not authentic.")

    # Verify amount on promissory note
    if not promissory_note.has_correct_total_check_value:
        raise ValueError("The total check value contained within the promissory note "
                         "does not correspond to the value specified by that selfsame note.")

    # Verify check amounts
    if not promissory_note.has_correct_check_values:
        raise ValueError("Some of the checks contained within the promissory note "
                         "list values exceeding their respective maximum values.")


def transfer(promissory_note, buyer_device):
    """Transfer a promissory note from a buyer device to the banks."""
    # Send it to the bank; well, all the banks...
    for bank in filter(lambda b: b.public_key in buyer_device.bank_keys.values(), known_banks()):
        bank.redeem_promissory_note(promissory_note)


def perform_transaction(buyer_device, seller_device, amount):
    """Transfers a particular amount of money from one account holder
       (the "buyer") to another (the "seller")."""
    # Create and sign a note.
    note = create_promissory_note(buyer_device, seller_device, amount)
    verify_promissory_note(note)
    transfer(note, buyer_device)
