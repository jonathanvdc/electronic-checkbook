# electronic-checkbook

[![Build Status](https://travis-ci.org/jonathanvdc/electronic-checkbook.svg?branch=master)](https://travis-ci.org/jonathanvdc/electronic-checkbook)

Specification and reference implementation of a protocol for secure, real-time transactions.

The highlights of this repository are
  1. a specification of a protocol for secure, real-time transactions that may or may not be offline,
  2. a reference implementation of that specification.

The former can be found in the `spec/` folder, the latter in the `source/` directory.

## Reference implementation

Reading the specification should be fairly straightforward, but the reference implementation warrants an explanation.

### Dependencies

The reference implementation is coded in Python 3 and depends on the `pycryptodome` library. Install it by spelling `pip3 install pycryptodome`. For more detailed installation instructions, take a look at [pycryptodome's installation guide](https://www.pycryptodome.org/en/latest/src/installation.html).

### Unit tests

To run the automated tests, spell `python3 source/unit_tests.py`.
