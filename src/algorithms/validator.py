from ipv8.community import CommunitySettings
from ipv8.messaging.payload_dataclass import overwrite_dataclass
from dataclasses import dataclass
from random import randint
from time import time
from .client import Announcement, Transaction

from ipv8.types import Peer

from da_types import Blockchain, message_wrapper

# We are using a custom dataclass implementation.
dataclass = overwrite_dataclass(dataclass)

starting_balance = 1000


@dataclass(
    msg_id=1, unsafe_hash=True
)  # The value 1 identifies this message and must be unique per community.
class Gossip:
    message_id: int
    hop_counter: int
    transaction: Transaction


class Validator(Blockchain):
    """_summary_
    Simple example that just echoes messages between two nodes
    Args:
        Blockchain (_type_): _description_
    """

    def __init__(self, settings: CommunitySettings) -> None:
        super().__init__(settings)
        self.history = {}
        self.validators = {}  # dict of nodeID : peer
        self.clients = {}  # dict of nodeID : peer
        self.balances = {}  # dict of nodeID: balance
        self.echo_counter = 0
        self.transaction_backlog = []
        self.can_start = False

        # register the handlers
        self.add_message_handler(Gossip, self.on_gossip)
        self.add_message_handler(Announcement, self.on_announcement)
        self.add_message_handler(Transaction, self.on_transaction)
        # TODO backlog handler with exponential backoff

    def on_start(self):
        # announce ourselves to the other nodes as a validator
        for peer in self.nodes.values():
            self.ez_send(peer, Announcement(self.node_id, False))
        # set the initial values
        print(f"{self.nodes}")

    def init_transaction(self):
        print("Init TX")
        for node_id, peer in self.clients.items():
            # if the node_id was not in the validator database, add it
            if node_id not in self.balances:
                self.balances[node_id] = starting_balance
            transaction = Transaction(
                self.node_id, node_id, self.balances[node_id], int(time())
            )
            transaction.create_hash()
            print(f"Creating transaction: {transaction=}")
            print(f"{self.clients=}")
            self.ez_send(peer, transaction)

    def execute(self, transaction: Transaction):
        """Executes a transaction if the sender has enough balance."""
        if self.balances[transaction.sender_id] >= transaction.amount:
            self.balances[transaction.sender_id] -= transaction.amount
            self.balances[transaction.target_id] += transaction.amount
        else:
            self.transaction_backlog.append(transaction)
            raise ValueError(
                f"Sender {transaction.sender_id} has insuffienct funds to give {transaction.amount} to {transaction.target_id}"
            )

    @message_wrapper(Gossip)
    async def on_gossip(self, peer: Peer, payload: Gossip) -> None:
        """When a gossip message is received, pass it on to other validators and to clients."""
        # sender_id = self.node_id_from_peer(peer)
        # print(
        #     f"[Node {self.node_id}] Got a message from node: {sender_id}.\t msg id: {payload.message_id}"
        # )

        if payload.message_id not in list(self.history.keys()):
            print(f"[Validator {self.node_id}] {len(self.history)=}")
            # broadcast to other validators
            payload.hop_counter += 1
            self.history[payload.message_id] = payload
            for node_id, val in self.validators.items():
                if val == peer:
                    continue
                self.ez_send(val, payload)
            # send transaction to target client
            transaction = payload.transaction
            target_id = payload.transaction.target_id
            for node_id, peer in self.clients.items():
                if node_id == target_id:
                    # pass
                    self.ez_send(peer, transaction)

    @message_wrapper(Announcement)
    async def on_announcement(self, peer: Peer, payload: Announcement) -> None:
        """When an announcement message is received, register it as a fellow validator or client."""
        sender_id = payload.sender_id
        if payload.is_client:
            self.clients[sender_id] = peer
        else:
            self.validators[sender_id] = peer

        if (
            len(self.validators) + len(self.clients) >= len(self.nodes)
            and len(self.clients) > 0
            and not self.can_start
        ):
            self.can_start = True
            self.init_transaction()

        # print(f'{len(self.validators) + len(self.clients) >= len(self.nodes)}')
        print(
            f"Announcement received: peer {peer} is {'client' if payload.is_client else 'validator'}"
        )

    @message_wrapper(Transaction)
    async def on_transaction(self, peer: Peer, payload: Transaction) -> None:
        """When a transaction message is received, broadcast it on as a gossip message."""
        print(
            f"[Validator {self.node_id}] got TX from {self.node_id_from_peer(peer)} with id {payload.timestamp}"
        )
        gossip_message = Gossip(
            randint(0, 1e9), 0, payload
        )  # TODO use hash as message id instead of random integer
        for peer in self.validators.values():
            self.ez_send(peer, gossip_message)
