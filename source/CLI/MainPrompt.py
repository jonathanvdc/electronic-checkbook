import shlex
from cmd import Cmd

class ArgException(Exception):
    pass

class MainPrompt(Cmd):

    def __init__(self):
        super().__init__()
        self.prompt = 'SimPay $ '
        # start the prompt
        self.cmdloop("Simple Payments - version 0.0.1")

    def _check_args_(self, fun_name, args, amount, types):
        # parse args
        args = shlex.split(args)
        if len(args) != amount:
            raise ArgException("not enough arguments provided \n" +
                               "run 'help " + fun_name + "' for usage")

        return [types[i](arg) for i, arg in enumerate(args)]

    def do_test(self, args):
        """
        usage: test arg1:int arg2:str
        """
        try:
            integer, string = self._check_args_("test", args, 2, [int, str])
        except ArgException as e:
            print(str(e))
            return

        return

    def do_quit(self, args):
        raise SystemExit

if __name__ == '__main__':
    prompt = MainPrompt()

