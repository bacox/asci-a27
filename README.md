# BAMI 🍜

[![Tests](https://github.com/grimadas/python-project/workflows/Tests/badge.svg)](https://github.com/grimadas/python-project/actions?workflow=Tests)
[![Codecov](https://codecov.io/gh/grimadas/python-project/branch/master/graph/badge.svg)](https://codecov.io/gh/grimadas/python-project)

> BAMI is short for Base Accounting Mechanisms and Interfaces.

The goal of BAMI is to provide system designers simple tools to build secure ledgers that store valuable information.
BAMI has the following properties:

* **Tamper-resistance**. BAMI achieves tamper-resistance through organizing information in a chain and by entangling
  information with each other.
* **Inconsistency resolution**. BAMI has tools to quickly detect deliberate forks and accidental inconsistencies (e.g.,
  as the result of a software bug). BAMI recovers from partitions in the network while ensuring availability and
  eventual consistency.
* **Reconciliation and Synchronization**. All stored information is organized in groups, which we name communities. A
  community is identified by a public key and maintains a so-called community chain. Through a robust push-pull gossip
  algorithm it is guaranteed that peers will eventually receive all the information within a single community.

BAMI is build with the [IPv8 library](https://github.com/Tribler/py-ipv8). Check
the [documentation](https://py-ipv8.readthedocs.io/en/latest/) for more details.

# Installation

In order to build and run the project, we advise you to use `pip` in combination with Python 3.11. To install
using `pip`, run:

```bash
pip install -r requirements.txt
``` 

To additionally also install the dev-dependencies, run:

```basH
pip install -r dev-requirements.txt
```

You can then run the example simulation by executing `example.py` located in the simulation package. If you are running from a terminal emulator, you might have to update the python path accordingly:

### Unix
```bash
export PYTHONPATH=$PYTHONPATH:.
```
### Windows
```cmd
set PYTHONPATH=%PYTHONPATH%;. 
```

## Troubleshooting

In case you run into issues installing `aioquic` run the following commands before installation:

```bash
export CFLAGS=-I/usr/local/opt/openssl/include
export LDFLAGS=-L/usr/local/opt/openssl/lib
```

### Mac M1/2 users

```zsh
export CFLAGS=-I/opt/homebrew/opt/openssl/include
export LDFLAGS=-L/opt/homebrew/opt/openssl/bin
```
