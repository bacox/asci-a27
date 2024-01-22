from ipv8.community import CommunitySettings
from ipv8.messaging.payload_dataclass import overwrite_dataclass
from dataclasses import dataclass
from random import randint
from ipv8.types import Peer

from da_types import Blockchain, message_wrapper


# We are using a custom dataclass implementation.
dataclass = overwrite_dataclass(dataclass)


@dataclass(
    msg_id=2
)  # The value 1 identifies this message and must be unique per community.
class Transaction:
    """Transaction message type."""

    sender_id: int
    target_id: int
    amount: int
    nonce: int = 1
    hash: str = None

    def create_hash(self) -> None:
        """Creates a hash out of the contents of the transaction."""
        pass

    #     self.hash = # TODO


@dataclass(msg_id=3)
class Announcement:
    """Announcement message type."""

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
        self.balance = 0
        self.add_message_handler(Transaction, self.on_transaction)

    def on_start(self):
        # start by announcing ourselves to our only known validator
        self.validators = list(self.nodes.keys())
        peer = self.nodes[self.validators[0]]
        self.ez_send(peer, Announcement(True))

        # register a task that sends transactions to other clients at semi-random intervals
        # (target_id assumes that an even number of validators is defined as the first nodes)
        self.register_task(
            "random_tx",
            self.send_amount,
            [
                self.node_id + 1 if self.node_id % 1 == 0 else self.node_id - 1,
                randint(1, self.balance),
            ],
            delay=randint(2, 4),
            interval=randint(4, 10),
        )

    def send_amount(self, target_id: int, amount: int):
        """Send some to a target."""
        if amount <= self.balance:
            for validator in self.validators:
                self.ez_send(
                    self.nodes[validator], Transaction(self.node_id, target_id, amount)
                )

    @message_wrapper(Transaction)
    async def on_transaction(self, peer: Peer, payload: Transaction) -> None:
        """Upon reception of a transaction."""
        sender_id = self.node_id_from_peer(peer)
        print(
            f"[Node {self.node_id}] Got a message from node: {sender_id}.\t msg id: {payload.message_id}"
        )
        if payload not in self.history:
            # add amount to balance and add transaction to history

            # broadcast
            payload.hop_counter += 1
            self.history[payload.message_id] = payload
            for val in self.validators:
                if val == peer:
                    continue
                self.ez_send(val, payload)
