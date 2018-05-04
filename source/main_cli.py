#!/usr/bin/env python3

import json
import shlex

from cmd import Cmd
from collections import defaultdict
from json import JSONEncoder
from tabulate import tabulate

from account_holder_device import AccountHolderDevice
from bank import Bank, Account
from signing_protocol import register_bank, create_promissory_note, verify_promissory_note, transfer, \
    perform_transaction, known_banks


class Person(JSONEncoder):
    def __init__(self, name):
        super().__init__()
        self.name = name
        self._ahds_ = {}
        self._bank_to_accounts_ = defaultdict(set)

    # setters
    def add_account(self, account, bank_id):
        self._bank_to_accounts_[bank_id].add(account)

    def add_ahd(self, ahd):
        self._ahds_[ahd.public_key.export_key(format='PEM')] = ahd

    # getters
    def get_ahd(self, public_key):
        return self._ahds_[public_key]

    def get_accounts(self, bank_id=None):
        if bank_id:
            return self._bank_to_accounts_[bank_id]
        return self._bank_to_accounts_.values()

    def ahds(self):
        return self._ahds_.values()

    def accounts(self):
        return self._bank_to_accounts_.values()

    def to_json(self):
        return {'Name': self.name}

    def __str__(self):
        return json.dumps(self.to_json(), indent=2)


class MainPrompt(Cmd):

    def __init__(self):
        super().__init__()
        self.prompt = 'SimPay $ '

        self.promissory_notes = []
        self.people = []

        # start the prompt
        self.cmdloop("Simple Payments - version 0.0.1")

    """
       ___  ___   __  __  __  __    _    _  _  ___   ___ 
      / __|/ _ \ |  \/  ||  \/  |  /_\  | \| ||   \ / __|
     | (__  (_) || |\/| || |\/| | / _ \ | .` || |) |\__ 
      \___|\___/ |_|  |_||_|  |_|/_/ \_\|_|\_||___/ |___/
                                                         
    """

    def do_bulk(self, args):
        """Create objects in bulk."""
        pass

    def do_create(self, args):
        """Create a single object.

        Usage: create bank|account|person|ahd|check|pn
        """

        if not self._check_len_arg_('create', args, [1]):
            return

        param = self._parse_args_('create', args, [str])
        if not param:
            return
        else:
            param = param[0].lower()

        try:
            creator = getattr(self, "create_" + param)
        except AttributeError:
            return

        result = creator()

        if result:
            print("{} CREATION SUCCESSFUL:\n{}\n".format(param.upper(), result))
        else:
            print("*** Cannot create an instance of {}\n".format(param))

    def do_internet(self, args):
        """Toggle the internet connection of an account holder device.

        Usage: internet
        """

        device = \
            self._get_choice_("ahd", self.ahds(), "For which account holder device?")
        device.toggle_internet()
        print("Device is now {}.\n".format(["offline", "online"][device.internet_connection]))

    def do_list(self, args):
        """List all available objects of a certain type.

        Usage: list banks|accounts|ahds|pns|people
        """
        if not self._check_len_arg_('list', args, [1]):
            return

        param = self._parse_args_('list', args, [str])
        if not param:
            return
        else:
            param = param[0].lower()

        try:
            table = []
            if param == "accounts":
                bank = None
                if input('\nFilter on bank? (y/n): ') in ['y', 'Y']:
                    bank = \
                        self._get_choice_("bank", known_banks(), "Select a bank.")

                table = list(map(lambda x: [x], self.accounts(bank)))
            elif param == "ahds":
                account = None
                if input('\nFilter on account? (y/n): ') in ['y', 'Y']:
                    account = \
                        self._get_choice_("account", self.accounts(), "Select an account.")

                table = list(map(lambda x: [x], self.ahds(account)))
            elif param == "banks":
                table = list(map(lambda x: [x], known_banks()))
            elif param == "pns":
                table = list(map(lambda x: [x], self.promissory_notes))
            elif param == "people":
                table = list(map(lambda x: [x], self.people))

            table.insert(0, ["#", param])

            print(tabulate(table, headers="firstrow", showindex=True) + "\n")  # tablefmt="grid"
        except KeyError:
            print("*** Incorrect input given.\n")
            self.do_help('list')

    def do_transaction(self, args):
        """Transfers a particular amount of money from one account holder (the "buyer") to another (the "seller").

        Usage: transaction
        """

        seller_device = \
            self._get_choice_("ahd", self.ahds(), "Which account holder device is the seller?")
        buyer_device = \
            self._get_choice_("ahd", self.ahds(), "Which account holder device is the buyer?")
        amount = int(input("What amount? "))

        perform_transaction(buyer_device, seller_device, amount)
        print("Transaction was successful.\n")

    def do_transfer(self, args):
        """Transfer a promissory note from a buyer device to the banks.

        Usage: transfer
        """

        buyer_device = \
            self._get_choice_("ahd", self.ahds(), "Which account holder device is the buyer?")

        pn = \
            self._get_choice_("pn", self.promissory_notes, "Which promissory note needs to be redeemed?")

        transfer(pn, buyer_device)
        print("Transfer was successful.\n")

    def do_verify(self, args):
        """Perform verification process on a promissory note.

        Usage: verify
        """

        pn = \
            self._get_choice_("pn", self.promissory_notes, "Which promissory note needs to be verified?")

        try:
            verify_promissory_note(pn)
        except ValueError as e:
            print("*** " + str(e))
            return

        print("Promissory note is correct.\n")

    def do_EOF(self, args):
        """Quit the application by pressing 'CTRL + D' or by typing 'EOF',

        Usage: EOF
        """
        raise SystemExit

    def do_quit(self, args):
        """Quit the application by pressing by typing 'quit'.

        Usage: quit
        """
        raise SystemExit

    """
       ___  ___  ___    _  _____  ___   ___  ___ 
      / __|| _ \| __|  /_\|_   _|/ _ \ | _ \/ __|
     | (__ |   /| _|  / _ \ | | | (_) ||   /\__ 
      \___||_|_\|___|/_/ \_\|_|  \___/ |_|_\|___/
      
      Usage: 
      
             create a function with name "create_{object_name}"                       
             this function will automatically be called when 
             command "create {object_name}" is executed
    """

    def create_bank(self):
        result = Bank(len(known_banks()))  # TODO: optional parameters?
        register_bank(result)
        return result

    def create_person(self):
        person = Person(input("Which name does this person have? "))
        self.people.append(person)
        return person

    def create_account(self, bank=None):
        if bank is None:
            bank = \
                self._get_choice_("bank", known_banks(), "Under which bank will this account be registered?")
        owner = \
            self._get_choice_("person", self.people, "For which person is this account?")
        max_credit = input("Max credit for account? (leave blank for default) ")
        if max_credit:
            result = Account(owner, int(max_credit))
        else:
            result = Account(owner)

        owner.add_account(result, bank.identifier)
        bank.add_account(result)

        return result

    def create_ahd(self, bank=None, account=None):
        if bank is None:
            bank = \
                self._get_choice_("bank", known_banks(), "Under which bank is the account registered?")
        if account is None:
            account = \
                self._get_choice_("account", bank.accounts, "For which account is this ahd?", [bank])

        result = AccountHolderDevice()
        bank.add_device(account, result.public_key)
        account.owner.add_ahd(result)

        return result

    def create_check(self):
        bank = \
            self._get_choice_("bank", known_banks(), "Which bank should issue the check?")
        device = \
            self._get_choice_("ahd", self.ahds(), "For which account holder device?")
        amount = int(input("What amount?"))

        try:
            result = bank.issue_check(device.public_key, amount)
            device.add_unspent_check(result)
        except ValueError as e:
            print("*** " + str(e))
            return

        return result

    def create_pn(self):
        seller_device = \
            self._get_choice_("ahd", self.ahds(), "Which account holder device is the seller?")
        buyer_device = \
            self._get_choice_("ahd", self.ahds(), "Which account holder device is the buyer?")

        amount = int(input("What amount? "))

        # TODO: maybe split this process (especially signing protocol) for demonstration purposes
        result = create_promissory_note(buyer_device, seller_device, amount)
        self.promissory_notes.append(result)
        return result

    """
       ___  ___  _____  _____  ___  ___  ___ 
      / __|| __||_   _||_   _|| __|| _ \/ __|
     | (_ || _|   | |    | |  | _| |   /\__ 
      \___||___|  |_|    |_|  |___||_|_\|___/
                                             
    """

    def ahds(self, account=None):
        if account is None:
            return [ahd for person in self.people for ahd in person.ahds()]
        else:
            return list(account.owner.ahds())

    def accounts(self, bank=None):
        if bank is None:
            return [account for bank in known_banks() for account in bank.accounts]
        else:
            return bank.accounts

    """
       ___  _____  _  _  ___  ___ 
      / _ \|_   _|| || || __|| _ 
     | (_) | | |  | __ || _| |   /
      \___/  |_|  |_||_||___||_|_

    """

    def onecmd(self, args):
        try:
            super().onecmd(args)
        except SystemExit:
            return input('\nDo you want to quit the application? (y/n): ') in ['y', 'Y']
        except KeyboardInterrupt:  # Press 'CTRL + C' to cancel a command
            print()
            pass

    def _parse_args_(self, fun_name, args, types):
        try:
            return [types[i](arg) for i, arg in enumerate(shlex.split(args))]
        except ValueError:
            print("*** Incorrect input given.\n")
            self.do_help(fun_name)
            return False

    def _check_len_arg_(self, fun_name, args, valid_amounts):
        args = shlex.split(args)
        if len(args) not in valid_amounts:
            print("*** Incorrect amount of arguments provided.\n")
            self.do_help(fun_name)
            return False

        return True

    def _get_choice_(self, collection_name, collection, prompt, extra_args=()):
        if extra_args is None:
            extra_args = []

        if not len(collection):
            try:
                creator = getattr(self, "create_" + collection_name)
            except AttributeError:
                return

            print("A {} needs to be created as none are available.".format(collection_name))
            res = creator(*extra_args)
            print("{} has been created and selected...\n".format(collection_name))
            return res

        if len(collection) == 1:
            print("The sole {} in the system was automatically selected.\n".format(collection_name))
            return collection[0]

        while True:
            answer = input(prompt + " (type 'l' to see the available choices) ")

            if answer == 'l':
                table = list(map(lambda x: [x], collection))
                table.insert(0, ["#", collection_name.capitalize() + "s"])
                print(tabulate(table, headers="firstrow", showindex=True) + "\n")
                continue

            try:
                value = collection[int(answer)]
                break
            except ValueError:
                print("*** Incorrect input given.\n")
                continue
            except (IndexError, KeyError):
                print("*** {} is not a valid choice.\n".format(answer))
                continue

        return value


if __name__ == '__main__':
    main = MainPrompt()
