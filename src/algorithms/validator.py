from ipv8.community import CommunitySettings
from ipv8.messaging.payload_dataclass import overwrite_dataclass
from dataclasses import dataclass
from random import randint
from .client import Announcement, Transaction

from ipv8.types import Peer

from da_types import Blockchain, message_wrapper

# We are using a custom dataclass implementation.
dataclass = overwrite_dataclass(dataclass)


@dataclass(
    msg_id=1
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
        self.validators = {}
        self.clients = {}  # dict of clientID: balance
        self.echo_counter = 0
        self.add_message_handler(Gossip, self.on_gossip)
        self.add_message_handler(Announcement, self.on_announcement)
        self.add_message_handler(Transaction, self.on_transaction)

    def on_start(self):
        for peer in self.nodes.values():
            self.ez_send(peer, Announcement(False))

    @message_wrapper(Gossip)
    async def on_gossip(self, peer: Peer, payload: Gossip) -> None:
        """When a gossip message is received, pass it on to other validators and to clients."""
        sender_id = self.node_id_from_peer(peer)
        print(
            f"[Node {self.node_id}] Got a message from node: {sender_id}.\t msg id: {payload.message_id}"
        )
        if payload not in self.history:
            # broadcast to other validators
            payload.hop_counter += 1
            self.history[payload.message_id] = payload
            for val in self.validators:
                if val == peer:
                    continue
                self.ez_send(val, payload)
            # send transaction to target client
            target_id = payload.transaction.target_id
            if target_id in self.clients:
                self.ez_send(self.clients[target_id], payload.transaction)

    @message_wrapper(Announcement)
    async def on_announcement(self, peer: Peer, payload: Announcement) -> None:
        """When an announcement message is received, register it as a fellow validator or client."""
        sender_id = self.node_id_from_peer(peer)
        if payload.is_client:
            self.clients[sender_id] = peer
        else:
            self.validators[sender_id] = peer
        print(
            f"Announcement received: peer {peer} is {'client' if payload.is_client else 'validator'}"
        )

    @message_wrapper(Transaction)
    async def on_transaction(self, peer: Peer, payload: Transaction) -> None:
        """When a transaction message is received, broadcast it on as a gossip message."""
        gossip_message = Gossip(randint(0, 1e9), 0, payload)
        for peer in self.validators.values():
            self.ez_send(peer, gossip_message)
