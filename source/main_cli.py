import shlex
from cmd import Cmd
from tabulate import tabulate

from account_holder_device import AccountHolderDevice
from bank import Bank, Account
from signing_protocol import register_bank, create_promissory_note, verify_promissory_note, transfer, perform_transaction


class ArgException(Exception):
    pass


class MainPrompt(Cmd):

    def __init__(self):
        super().__init__()
        self.prompt = 'SimPay $ '

        self.id = 0

        self.banks = []
        self.accounts = []
        self.ahds = []
        self.promissory_notes = []

        self.str_to_coll = {
            "bank": self.banks,
            "account": self.accounts,
            "ahd": self.ahds,
            "pn": self.promissory_notes,
        }

        # start the prompt
        self.cmdloop("Simple Payments - version 0.0.1")

    def __parse_args_(self, fun_name, args, types):
        try:
            return [types[i](arg) for i, arg in enumerate(shlex.split(args))]
        except ValueError:
            print("*** Incorrect input given.\n")
            self.do_help(fun_name)
            return False

    def __check_len_arg(self, fun_name, args, valid_amounts):
        args = shlex.split(args)
        if len(args) not in valid_amounts:
            print("*** Incorrect amount of arguments provided.\n")
            self.do_help(fun_name)
            return False

        return True

    def __get_choice(self, collection_name, collection, prompt):
        while True:
            answer = input(prompt + " (type 'l' to see the available choices) ")

            if answer == 'l':
                self.do_list(collection_name)
                continue

            try:
                value = collection[int(answer)][0]
                break
            except ValueError:
                print("*** Incorrect input given.\n")
                continue
            except (IndexError, KeyError):
                print("*** {} is not a valid choice.\n".format(answer))
                continue

        return value

    def do_bulk(self, args):
        """Create objects in bulk."""
        pass

    def do_create(self, args):
        """Create a single object.

        Usage: create bank|account|ahd|check|pn
        """

        if not self.__check_len_arg('create', args, [1]):
            return

        param = self.__parse_args_('create', args, [str])
        if not param:
            return
        else:
            param = param[0].lower()

        if param == "bank":
            result = Bank(len(self.banks))  # TODO: optional parameters?
            self.banks.append([result])
            register_bank(result)

        elif param == "account":
            owner = input("Under which name do you want to create an account? ")
            max_credit = input("Max credit for account? (leave blank for default) ")
            if max_credit:
                result = Account(owner, int(max_credit))
            else:
                result = Account(owner)
            self.accounts.append([result])

        elif param == "ahd":
            result = AccountHolderDevice()
            self.ahds.append([result])

        elif param == "check":
            bank = \
                self.__get_choice("bank", self.str_to_coll["bank"], "Which bank should issue the check?")
            device = \
                self.__get_choice("ahd", self.str_to_coll["ahd"], "For which account holder device?")
            amount = int(input("What amount? "))

            try:
                result = bank.issue_check(device.public_key, amount)
                device.add_unspent_check(result)
            except ValueError as e:
                print("*** " + str(e))
                return

        elif param == "pn":
            seller_device = \
                self.__get_choice("ahd", self.str_to_coll["ahd"], "Which account holder device is the seller?")
            buyer_device = \
                self.__get_choice("ahd", self.str_to_coll["ahd"], "Which account holder device is the buyer?")
            amount = int(input("What amount? "))

            # TODO: maybe split this process (especially signing protocol) for demonstration purposes
            result = create_promissory_note(buyer_device, seller_device, amount)
            self.promissory_notes.append([result])

        else:
            print("*** Cannot create an instance of {}\n".format(param))
            return

        print("Object creation successful:\n{}\n".format(result))

    def do_internet(self, args):
        """Toggle the internet connection of an account holder device.

        Usage: internet
        """

        device = \
            self.__get_choice("ahd", self.str_to_coll["ahd"], "For which account holder device?")
        device.toggle_internet()
        print("Device is now {}.\n".format("online" if device.internet_connection else "offline"))

    def do_list(self, args):
        """List all available objects of a certain type.

        Usage: list bank|account|ahd|pn
        """
        if not self.__check_len_arg('list', args, [1]):
            return

        param = self.__parse_args_('list', args, [str])
        if not param:
            return
        else:
            param = param[0].lower()

        try:
            table = self.str_to_coll[param][:]
            table.insert(0, ["#", param.capitalize() + "s"])

            print(tabulate(table, headers="firstrow", showindex=True) + "\n")  # tablefmt="grid"
        except KeyError:
            print("*** Incorrect input given.\n")
            self.do_help('list')

    def do_register(self, args):
        """Register an account holder device at a bank.

        Usage: register
        """

        device = \
            self.__get_choice("ahd", self.str_to_coll["ahd"], "Which account holder device do you want to register?")

        bank = \
            self.__get_choice("bank", self.str_to_coll["bank"], "At which bank should the device be registered?")

        device.register_bank(bank.identifier, bank.public_key)
        print("Registration was successful.\n")

    def do_transaction(self, args):
        """Transfers a particular amount of money from one account holder (the "buyer") to another (the "seller").

        Usage: transaction
        """

        seller_device = \
            self.__get_choice("ahd", self.str_to_coll["ahd"], "Which account holder device is the seller?")
        buyer_device = \
            self.__get_choice("ahd", self.str_to_coll["ahd"], "Which account holder device is the buyer?")
        amount = int(input("What amount? "))

        perform_transaction(buyer_device, seller_device, amount)
        print("Transaction was successful.\n")

    def do_transfer(self, args):
        """Transfer a promissory note from a buyer device to the banks.
        
        Usage: transfer
        """

        buyer_device = \
            self.__get_choice("ahd", self.str_to_coll["ahd"], "Which account holder device is the buyer?")

        pn = \
            self.__get_choice("pn", self.str_to_coll["pn"], "Which promissory note needs to be redeemed?")

        transfer(pn, buyer_device)
        print("Transfer was successful.\n")

    def do_verify(self, args):
        """Perform verification process on a promissory note.

        Usage: verify
        """

        pn = \
            self.__get_choice("pn", self.str_to_coll["pn"], "Which promissory note needs to be verified?")

        try:
            verify_promissory_note(pn)
        except ValueError as e:
            print("*** " + str(e))

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

    def onecmd(self, args):
        try:
            super().onecmd(args)
        except SystemExit:
            return input('\nDo you want to quit the application? (y/n): ') in ['y', 'Y']
        except KeyboardInterrupt:  # Press 'CTRL + C' to cancel a command
            print()
            pass


if __name__ == '__main__':
    main = MainPrompt()
