from ipv8.community import CommunitySettings
from ipv8.messaging.payload_dataclass import overwrite_dataclass
from dataclasses import dataclass
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


class Validator(Blockchain):
    """_summary_
    Simple example that just echoes messages between two nodes
    Args:
        Blockchain (_type_): _description_
    """

    def __init__(self, settings: CommunitySettings) -> None:
        super().__init__(settings)
        self.history = {}
        self.validators = []
        self.clients = {}  # dict of clientID: balance
        self.echo_counter = 0
        self.add_message_handler(Gossip, self.on_gossip)
        self.add_message_handler(Announcement, self.on_announcement)

    def on_start(self):
        if self.node_id == 1:
            #  Only node 1 starts
            peer = self.nodes[0]
            self.ez_send(peer, Announcement(False))

    @message_wrapper(Gossip)
    async def on_gossip(self, peer: Peer, payload: Gossip) -> None:
        sender_id = self.node_id_from_peer(peer)
        print(
            f"[Node {self.node_id}] Got a message from node: {sender_id}.\t msg id: {payload.message_id}"
        )
        if payload not in self.history:
            # broadcast
            payload.hop_counter += 1
            self.history[payload.message_id] = payload
            for val in self.validators:
                if val == peer:
                    continue
                self.ez_send(val, payload)

    @message_wrapper(Announcement)
    async def on_announcement(self, peer: Peer, payload: Announcement) -> None:
        sender_id = self.node_id_from_peer(peer)
        if payload.is_client:
            self.clients[sender_id] = peer
        else:
            self.validators[sender_id] = peer
        print(
            f"Announcement received: peer {sender_id} is {'client' if payload.is_client else 'validator'}"
        )
