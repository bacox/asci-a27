from typing import List
from ipv8.community import CommunitySettings
from random import randint
from time import time
from .messages import Announcement, TransactionBody, Gossip, BlockHeader

from ipv8.types import Peer

from da_types import Blockchain, message_wrapper


starting_balance = 1000


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

        self.buffered_transactions: List[TransactionBody] = []
        self.pending_transactions: List[TransactionBody] = []
        self.finalized_transactions: List[TransactionBody] = []
        self.can_start = False

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

        self.register_task("check_txs", self.check_transactions, delay=2, interval=1)
        self.register_task(
            "send_buffered_transactions",
            self.send_buffered_transactions,
            delay=5,
            interval=3,
        )

    def check_transactions(self):
        """Checks pending transactions and attempts to execute if possible."""
        print("Checking transactions")
        for tx in self.pending_transactions:
            if self.balances[tx.sender_id] - tx.amount >= 0:
                print("Exec TX")
                # TODO move to separate execution function that only gets executed if validator is leader
                # the pending list should be communicated among validators
                self.balances[tx.sender_id] -= tx.amount
                self.balances[tx.target_id] += tx.amount
                self.pending_transactions.remove(tx)
                self.finalized_transactions.append(tx)

    def init_transaction(self):
        """The init transactions are executed after the announcements have been completed."""
        print("Init TX")
        for node_id, peer in self.clients.items():
            # if the node_id was not in the validator database, add it
            if node_id not in self.balances:
                self.balances[node_id] = starting_balance
            transaction = TransactionBody(
                self.node_id, node_id, self.balances[node_id], int(time())
            )
            print(f"Creating transaction: {transaction=}")
            print(f"{self.clients=}")
            self.ez_send(peer, transaction)

    def send_buffered_transactions(self):
        """Function to broadcast the buffered transactions on the network."""

        transactions_to_send = self.buffered_transactions
        if len(transactions_to_send) > 0:
            print(f"Sending {len(transactions_to_send)=}")
            # TODO make a unique message ID
            gossip_message = Gossip(ID, transactions_to_send)
            for peer in self.validators.values():
                self.ez_send(peer, gossip_message)
            self.pending_transactions += transactions_to_send
            self.buffered_transactions = []

    # TODO only execute if we're leader, produces blockheader
    # or only execute if we have block finality?
    # def execute(self, transaction: Transaction):
    #     """Executes a transaction if the sender has enough balance."""
    #     if self.balances[transaction.sender_id] >= transaction.amount:
    #         self.balances[transaction.sender_id] -= transaction.amount
    #         self.balances[transaction.target_id] += transaction.amount
    #     else:
    #         self.transaction_backlog.append(transaction)
    #         raise ValueError(
    #             f"Sender {transaction.sender_id} has insuffienct funds to give {transaction.amount} to {transaction.target_id}"
    # )

    @message_wrapper(Gossip)
    async def on_gossip(self, peer: Peer, payload: Gossip) -> None:
        """When a gossip message is received, pass it on to other validators and to clients."""
        # sender_id = self.node_id_from_peer(peer)
        # print(
        #     f"[Node {self.node_id}] Got a message from node: {sender_id}.\t msg id: {payload.message_id}"
        # )

        if payload not in self.pending_transactions:
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

    @message_wrapper(TransactionBody)
    async def on_transaction(self, peer: Peer, payload: TransactionBody) -> None:
        """When a transaction message is received from a client, add it to the buffer to be gossiped it to the rest of the network."""
        print(f"[Validator {self.node_id}] got TX from {self.node_id_from_peer(peer)}")

        if payload not in self.buffered_transactions:
            self.buffered_transactions.append(payload)
