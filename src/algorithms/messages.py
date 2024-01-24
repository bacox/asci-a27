from dataclasses import dataclass

from hashlib import sha256

from ipv8.messaging.serialization import default_serializer
from ipv8.messaging.payload_dataclass import overwrite_dataclass

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


@dataclass(msg_id=4, unsafe_hash=True)
class Gossip:
    """A Gossip message, passed along to communicate pending transactions."""

    message_id: int
    transactions: [TransactionBody]
    hop_counter: int = 0


@dataclass(msg_id=3, unsafe_hash=True)
class BlockHeader:
    """A Block header, containing an array of transactions."""

    transactions: [TransactionBody]
    timestamp: int
    hash: str = None

    def create_hash(self) -> None:
        """Creates a hash out of the contents of the transaction."""
        transaction_package = default_serializer.pack("payload", self)
        self.hash = sha256(transaction_package).digest()
