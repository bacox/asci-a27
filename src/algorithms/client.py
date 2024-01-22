from ipv8.community import CommunitySettings
from ipv8.messaging.payload_dataclass import overwrite_dataclass
from dataclasses import dataclass

from ipv8.types import Peer

from da_types import Blockchain, message_wrapper

# We are using a custom dataclass implementation.
dataclass = overwrite_dataclass(dataclass)



@dataclass(
    msg_id=2
)  # The value 1 identifies this message and must be unique per community.
class Transaction:
    message_id: int
    hop_counter: int




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
        self.clients = []
        self.echo_counter = 0
        self.add_message_handler(Gossip, self.on_message)

    def on_start(self):
        if self.node_id == 1:
            #  Only node 1 starts
            peer = self.nodes[0]
            self.ez_send(peer, Gossip(self.echo_counter))

    @message_wrapper(Gossip)
    async def on_message(self, peer: Peer, payload: Gossip) -> None:
        sender_id = self.node_id_from_peer(peer)
        print(f'[Node {self.node_id}] Got a message from node: {sender_id}.\t msg id: {payload.message_id}')
        if payload not in self.history:
            # broadcast
            payload.hop_counter += 1
            self.history[payload.message_id] = payload
            for val in self.validators:
                if val == peer:
                    continue
                self.ez_send(val, payload)
            

        
