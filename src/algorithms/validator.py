from typing import List

from ipv8.community import CommunitySettings
from ipv8.types import Peer

from da_types import Blockchain, message_wrapper
from .messages import Announcement, TransactionBody, Gossip, BlockHeader
from threading import RLock

starting_balance = 1000


class Validator(Blockchain):
    """_summary_
    Simple example that just echoes messages between two nodes
    Args:
        Blockchain (_type_): _description_
    """

    def __init__(self, settings: CommunitySettings) -> None:
        super().__init__(settings)
        self.validators = {}  # dict of nodeID : peer
        self.clients = {}  # dict of nodeID : peer
        self.balances = {}  # dict of nodeID: balance
        self.echo_counter = 0

        self.buffered_transactions: list[TransactionBody] = []
        self.pending_transactions: list[TransactionBody] = []
        self.finalized_transactions: dict[bytes, list[TransactionBody]] = {}
        self.can_start = False
        self.receive_lock = RLock()

        # register the handlers
        self.add_message_handler(Gossip, self.on_gossip)
        self.add_message_handler(Announcement, self.on_announcement)
        self.add_message_handler(TransactionBody, self.on_transaction)

    def on_start(self):
        # announce ourselves to the other nodes as a validator
        for peer in self.nodes.values():
            self.ez_send(peer, Announcement(self.node_id, False))
        # set the initial values
        print(f"{self.nodes}")

        # register tasks
        self.register_task(
            "check_tx",
            self.check_tx,
            delay=
        )
        self.register_task(
            "send_buffered_transactions",
            self.send_buffered_transactions,
            delay=5,
            interval=3,
        )

    def init_transaction(self):
        """The init transactions are executed after the announcements have been completed."""
        print("Init TX")
        for node_id, peer in self.clients.items():
            # if the node_id was not in the validator database, add it
            if node_id not in self.balances:
                self.balances[node_id] = starting_balance
            transaction = TransactionBody(
                -1, node_id, self.balances[node_id], 0
            )
            print(f"Creating transaction: {transaction=}")
            print(f"{self.clients=}")
            self.ez_send(peer, transaction)

    # TODO implement concensus system

    def check_tx(self):
        """Temporary function to execute"""
        for tx in self.pending_transactions.values():
            self.execute_transaction(tx)

    # TODO only execute if we're leader, produces blockheader
    # or only execute if we have block finality?
    def execute_transactions(self):
        """Executes a set of transactions if approved"""
        transactions = self.pending_transactions[message_id]
        for transaction in transactions:
            if self.balances[transaction.sender_id] >= transaction.amount:
                self.balances[transaction.sender_id] -= transaction.amount
                self.balances[transaction.target_id] += transaction.amount
            elif transaction.sender_id == -1:
                self.balances[transaction.target_id] += transaction.amount
            else:
                print(
                    f"Sender {transaction.sender_id} has insuffienct funds to give {transaction.amount} to {transaction.target_id}"
                )

            # send transaction to target client
            # TODO check if we still want to do it like that, or clients just request their balance
            target_id = transaction.target_id
            for node_id, peer in self.clients.items():
                if node_id == target_id:
                    self.ez_send(peer, transaction)

    def send_buffered_transactions(self):
        """Function to broadcast the buffered transactions on the network."""
        with self.receive_lock:
            # get all buffered transactions
            for transaction in self.buffered_transactions:
                if transaction not in self.pending_transactions:
                    self.pending_transactions.append(transaction)

            # bundle the valid transactions in a gossip and send it on the network
            gossip_message = Gossip(self.buffered_transactions)
            gossip_message.create_message_id()
            for peer in self.validators.values():
                self.ez_send(peer, gossip_message)

            print(f"Sending {len(self.buffered_transactions)=}")
            self.buffered_transactions = []

    @message_wrapper(Gossip)
    async def on_gossip(self, peer: Peer, payload: Gossip) -> None:
        """When a gossip message is received, pass it on to other validators and to clients."""
        # sender_id = self.node_id_from_peer(peer)
        # print(
        #     f"[Node {self.node_id}] Got a message from node: {sender_id}.\t msg id: {payload.message_id}"
        # )

        if payload.message_id is None:
            print(f"Received Gossip without message ID from {peer}")
        if payload.message_id not in self.pending_transactions:
            self.pending_transactions[payload.message_id] = payload.transactions
            # broadcast to other validators
            payload.hop_counter += 1
            for val in self.validators.values():
                if val == peer:
                    continue
                self.ez_send(val, payload)

    @message_wrapper(Announcement)
    async def on_announcement(self, peer: Peer, payload: Announcement) -> None:
        """When an announcement message is received, register it as a fellow validator or client."""
        sender_id = payload.sender_id
        if payload.is_client:
            if sender_id not in self.clients:
                self.clients[sender_id] = peer
                self.balances[sender_id] = (
                    0 if sender_id not in self.balances else self.balances[sender_id]
                )
                # broadcast the announcement so other validators get the client as well
                for val in self.validators.values():
                    self.ez_send(val, payload)

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

    def is_new_transaction(self, transaction: TransactionBody) -> bool:
        """Function to check if a transaction is not yet in buffered, pending or finalized transactions."""

        # first check if transaction is in the buffer
        if transaction in self.buffered_transactions:
            return False

        # then check if a transaction is in the pending
        if transaction in list(self.pending_transactions.values()):
            return False

        # least likely: a transaction has already been finalized
        if transaction in list(self.finalized_transactions.values()):
            return False

        return True

    @message_wrapper(TransactionBody)
    async def on_transaction(self, peer: Peer, payload: TransactionBody) -> None:
        """When a transaction message is received from a client, add it to the buffer to be gossiped it to the rest of the network."""
        with self.receive_lock:
            print(f"[Validator {self.node_id}] got TX from {self.node_id_from_peer(peer)}")

            if self.is_new_transaction(payload):
                self.buffered_transactions.append(payload)
