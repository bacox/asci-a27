import json
from ipv8.community import CommunitySettings
from ipv8.messaging.payload_dataclass import overwrite_dataclass
from dataclasses import dataclass
from random import randint
from time import time
from ipv8.types import Peer

from da_types import Blockchain, message_wrapper

from binascii import hexlify, unhexlify


def to_hex(bstr: bytes) -> str:
    return hexlify(bstr).decode()


# We are using a custom dataclass implementation.
dataclass = overwrite_dataclass(dataclass)


@dataclass(
    msg_id=2, unsafe_hash=True
)  # frozen makes the class immutable, allowing it to be hashable
class Transaction:
    """Transaction message type."""

    sender_id: int
    target_id: int
    amount: int
    timestamp: int
    nonce: int = 1
    hash: str = "None"

    def create_hash(self) -> None:
        """Creates a hash out of the contents of the transaction."""
        self.hash = "hello world"

    #     self.hash = # TODO


@dataclass(msg_id=3)
class Announcement:
    """Announcement message type."""

    sender_id: int
    is_client: bool


class Client(Blockchain):
    """_summary_
    Simple example that just echoes messages between two nodes
    Args:
        Blockchain (_type_): _description_
    """

    def __init__(self, settings: CommunitySettings) -> None:
        super().__init__(settings)
        self.history = {}
        self.validators = []
        self.echo_counter = 0
        self.local_balance = 0
        self.add_message_handler(Transaction, self.on_transaction)

    def on_start(self):
        # start by announcing ourselves to our only known validator
        self.validators = list(self.nodes.keys())
        peer = self.nodes[self.validators[0]]
        self.ez_send(peer, Announcement(self.node_id, True))

        # register a task that sends transactions to other clients at semi-random intervals
        # (target_id assumes that an even number of validators is defined as the first nodes)
        self.register_task(
            "random_tx",
            self.send_amount,
            delay=randint(2, 4),
            interval=randint(2, 4),
        )

    def send_amount(self, target_id: int = None, amount: int = None):
        """Send some to a target. If target and amount are not specified, make it random."""
        print(f"[C{self.node_id}] Triggering client send {self.local_balance=}")
        if target_id is None:
            target_id = int(
                self.node_id + 1 if self.node_id % 1 == 0 else self.node_id - 1
            )
        if amount is None:
            amount = max(self.local_balance, randint(1, 100))
        if amount <= self.local_balance and self.node_id != target_id:
            timestamp = int(time)
            transaction = Transaction(self.node_id, target_id, amount, timestamp)
            transaction.create_hash()
            for validator in self.validators:
                self.ez_send(self.nodes[validator], transaction)
                print(
                    f"[Client {self.node_id}] send TX to node {self.node_id_from_peer(peer)}"
                )

    @message_wrapper(Transaction)
    async def on_transaction(self, peer: Peer, transaction: Transaction) -> None:
        """Upon reception of a transaction."""

        # To has messages not used right now
        # message = json.dumps({"key": "value", "key2": "value2"})
        # public_key = to_hex(self.my_peer.public_key.key_to_bin())
        # signature = to_hex(self.my_peer.key.signature(message.encode()))

        # sender_id = self.node_id_from_peer(peer)
        # print(
        #     f"[Node {self.node_id}] Got a message from node: {sender_id}.\t msg id: {payload.message_id}"
        # )
        print(f"[C{self.node_id}] Got a TX {transaction=}")
        if (
            transaction.target_id == self.node_id
            and transaction.message_id not in self.history.keys()
        ):
            # add transaction to history
            self.history[transaction.message_id] = transaction

            if transaction.target_id == self.node_id:
                # add amount to balance
                self.local_balance += transaction.amount
            elif transaction.sender_id == self.node_id:
                # deduct from balance
                self.local_balance -= transaction.amount

            # # broadcast
            # transaction.hop_counter += 1
            # self.history[transaction.message_id] = transaction
            # for val in self.validators:
            #     if val == peer:
            #         continue
            #     self.ez_send(val, transaction)
