from dataclasses import dataclass

from hashlib import sha256

from ipv8.messaging.serialization import default_serializer
from ipv8.messaging.payload_dataclass import overwrite_dataclass


def create_hash(item, fmt="payload") -> bytes:
    """Creates a hash out of the contents of the item."""
    bstr = b"".join(default_serializer.pack_serializable(x) for x in item)
    return sha256(bstr).digest()


# We are using a custom dataclass implementation.
dataclass = overwrite_dataclass(dataclass)


@dataclass(msg_id=1)
class Announcement:
    """Announcement message type."""

    sender_id: int
    is_client: bool


@dataclass(msg_id=2)
class TransactionBody:
    """A single transaction."""

    sender_id: int
    target_id: int
    amount: int
    message_id: int  # every node can keep their own counter for this


@dataclass(msg_id=3)
class Gossip:
    """A Gossip message, passed along to communicate pending transactions."""

    transactions: [TransactionBody]


@dataclass(msg_id=4)
class AnnounceConcensusParticipation:
    """A message to announce the election participation of a validator."""

    election_number: int
    sender_id: int
    stake: int


@dataclass(msg_id=5)
class AnnounceConcensusWinner:
    """A message to announce a validator as the election winner, with validation."""

    election_number: int
    winner_id: int
    random_seed: int  # TODO check if this is even necessary
    number_of_validators: int


@dataclass(msg_id=6, unsafe_hash=True)
class BlockHeader:
    """A Block header, containing an array of transactions."""

    transactions: [TransactionBody]
    timestamp: int
    hash: bytes = None

    def create_hash(self) -> None:
        self.hash = create_hash(self)

@dataclass(msg_id=6)
class Block:
    block_height: int
    prev_block_hash: bytes
    timestamp: int
    transactions: [TransactionBody]

