from dataclasses import dataclass

from hashlib import sha256

from ipv8.messaging.serialization import default_serializer
from ipv8.messaging.payload_dataclass import overwrite_dataclass


def create_hash(item, fmt="payload") -> bytes:
    """Creates a hash out of the contents of the item."""
    transaction_package = default_serializer.pack(fmt=fmt, item=item)
    return sha256(transaction_package).digest()


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


@dataclass(msg_id=4, unsafe_hash=True)
class Gossip:
    """A Gossip message, passed along to communicate pending transactions."""

    transactions: [TransactionBody]
    hop_counter: int = 0
    message_id: bytes = None

    def create_message_id(self):
        self.message_id = create_hash(self.transactions)


@dataclass(msg_id=3, unsafe_hash=True)
class BlockHeader:
    """A Block header, containing an array of transactions."""

    transactions: [TransactionBody]
    timestamp: int
    hash: bytes = None

    def create_hash(self) -> None:
        self.hash = create_hash(self)
