from typing import List
from time import time

from ipv8.community import CommunitySettings
from ipv8.types import Peer
from collections import defaultdict
from ipv8.messaging.serialization import default_serializer
from hashlib import sha256
from da_types import Blockchain, message_wrapper
from .messages import Announcement, Block, BlockVote, TransactionBody, Gossip, BlockHeader
from threading import RLock

starting_balance = 1000
block_width = 5

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
        self.balances = defaultdict(lambda: 0)  # dict of nodeID: balance
        self.buffered_transactions: list[TransactionBody] = []
        self.pending_transactions: list[TransactionBody] = []
        self.finalized_transactions: list[TransactionBody] = []
        self.can_start = False
        self.receive_lock = RLock()
        self.blocks = []
        self.block_votes = defaultdict(lambda: set())

        # elections
        self.time_since_election = int(time())
        self.in_elections = False
        self.available_stake = 100
        self.active_block_proposal = False

        # register the handlers
        self.add_message_handler(Gossip, self.on_gossip)
        self.add_message_handler(Announcement, self.on_announcement)
        self.add_message_handler(TransactionBody, self.on_transaction)
        self.add_message_handler(Block, self.on_block)
        self.add_message_handler(BlockVote, self.on_block_vote)

    def on_start(self):
        # announce ourselves to the other nodes as a validator
        for peer in self.nodes.values():
            self.ez_send(peer, Announcement(self.node_id, False))
        # set the initial values
        print(f"{self.nodes}")
        self.genesis_block()

        # register tasks
        # self.register_task(
        #     "execute_transactions", self.execute_transactions, delay=4, interval=3
        # )

        self.register_task('act_leader', self.act_leader, delay=5, interval=2)
        self.register_task(
            "send_buffered_transactions",
            self.send_buffered_transactions,
            delay=4,
            interval=3,
        )

    def init_transaction(self):
        """The init transactions are executed after the announcements have been completed."""
        print("Init TX")
        for node_id, peer in self.clients.items():
            # if the node_id was not in the validator database, add it
            if node_id not in self.balances:
                self.balances[node_id] = starting_balance
            transaction = TransactionBody(-1, node_id, starting_balance, 0)
            print(f"Creating transaction: {transaction=}")
            print(f"{self.clients=}")
            self.buffered_transactions.append(transaction)
            # self.ez_send(peer, transaction)

    # TODO implement concensus system

    # def check_tx(self):
    #     """Temporary function to execute"""
    #     for tx in self.pending_transactions:
    #         self.execute_transaction(tx)

    # TODO only execute if we have block finality
    def execute_transactions(self, transactions):
        """Executes a set of transactions if approved"""
        for transaction in transactions:         
            if transaction.sender_id == -1:
                self.balances[transaction.target_id] += transaction.amount
                print(f"Executing special {transaction=}")
            elif self.balances[transaction.sender_id] >= transaction.amount:
                # print(f'Executing {transaction=}')
                self.balances[transaction.sender_id] -= transaction.amount
                self.balances[transaction.target_id] += transaction.amount
            # send transaction to target client
            target_id = transaction.target_id
            sender_id = transaction.sender_id

            for node_id, peer in self.clients.items():
                if node_id == target_id or node_id == sender_id:
                    self.ez_send(peer, transaction)
            
            self.pending_transactions.remove(transaction)
            self.finalized_transactions.append(transaction)

    def genesis_block(self):
        pass
        # prev_block_hash = b'0'
        # self.blocks.append(Block(self.get_block_height()+1, prev_block_hash, 1, []))

    def validate_block(self, block: Block) -> bool:
        # @TODO FIX THIS FUNCTION!
        return True
        if len(self.blocks) == 0:
            return True
        prev_block_hash = b'0'
        if len(self.blocks) > 0:
            prev_block_hash = sha256(default_serializer.pack('payload', self.blocks[-1])).digest()
        if block.prev_block_hash == prev_block_hash:
            # Check all transactions
            return True
        else:
            print(f'Invalid: {block.prev_block_hash} == {prev_block_hash}')
            return False

    def act_leader(self):
        if self.node_id != 0:
            return
        if self.active_block_proposal:
            return
        self.active_block_proposal = True
        self.form_block()

    def form_block(self):
        # We assume that blocks are ordered.
        prev_block_hash = b'0'
        if len(self.blocks) > 0:
            prev_block_hash = sha256(default_serializer.pack('payload', self.blocks[-1])).digest()

        block = Block(self.get_block_height() + 1, prev_block_hash, int(time()),
                      [tx for tx in self.pending_transactions[:block_width]])

        self.blocks.append(block)

        # Gossip to other nodes
        for peer in self.validators.values():
            self.ez_send(peer, block)

        # We confirm our own block
        #@TODO: DO conformation
        self.broadcast_block_confirmation(block)

    def get_block_height(self):
        if len(self.blocks) > 0:
            return self.blocks[-1].block_height
        return 0
    
    def broadcast_block_confirmation(self, block):
        block_package = default_serializer.pack("payload", block)
        block_hash = sha256(block_package).digest()
        block_vote = BlockVote(block.block_height, block_hash)
        self.block_votes[block_hash].add(self.node_id)
        for peer in self.validators.values():
            self.ez_send(peer, block_vote)
        


    def send_buffered_transactions(self):
        """Function to broadcast the buffered transactions on the network."""
        with self.receive_lock:
            # get all buffered transactions
            for transaction in self.buffered_transactions:
                if transaction not in self.pending_transactions:
                    self.pending_transactions.append(transaction)

            # bundle the valid transactions in a gossip and send it on the network
            gossip_message = Gossip(self.buffered_transactions)
            for peer in self.validators.values():
                self.ez_send(peer, gossip_message)

            # print(f"Sending {len(self.buffered_transactions)} buffered transactions")
            self.buffered_transactions = []

    def finalize_block(self, block: Block):
        print('Finalizing block')
        self.execute_transactions(block.transactions)
        
        # self.check_transactions(block.transactions)
        print(f'[Node {self.node_id}] Finalized block {block.block_height} with {len(block.transactions)} transactions')
        self.active_block_proposal = False

    @message_wrapper(Block)
    async def on_block(self, peer: Peer, payload: Block) -> None:
        if self.validate_block(payload):
            if payload not in self.blocks:
                self.blocks.append(payload)

                for peer in self.validators.values():
                    self.ez_send(peer, payload)

                # TODO: there might be soft forks.
                # @TODO: Call block confirmation
                self.broadcast_block_confirmation(payload)
            print(f'[Node {self.node_id}] Received block {payload.block_height} ({len(self.blocks)})')
        else:
            print(f'[Node {self.node_id}] Received invalid block {payload.block_height}')

    @message_wrapper(Gossip)
    async def on_gossip(self, peer: Peer, payload: Gossip) -> None:
        """When a gossip message is received, pass it on to other validators and to clients."""
        # sender_id = self.node_id_from_peer(peer)
        # print(
        #     f"[Node {self.node_id}] Got a message from node: {sender_id}.\t msg id: {payload.message_id}"
        # )
        to_gossip = []
        for tx in payload.transactions:
            if tx not in self.pending_transactions:
                self.pending_transactions.append(tx)
                to_gossip.append(tx)

        if len(to_gossip) > 0:
            gossip_obj = Gossip(to_gossip)
            for val in self.validators.values():
                if val == peer:
                    continue
                self.ez_send(val, gossip_obj)

        # if payload.message_id is None:
        #     print(f"Received Gossip without message ID from {peer}")
        # if payload.message_id not in self.pending_transactions:
        #     self.pending_transactions[] = payload.transactions
        #     # broadcast to other validators
        #     payload.hop_counter += 1
        #     for val in self.validators.values():
        #         if val == peer:
        #             continue
        #         self.ez_send(val, payload)

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

        if (self.node_id == 0 and
            len(self.validators) + len(self.clients) >= len(self.nodes)
            and len(self.clients) > 0
            and not self.can_start
        ):
            
            self.can_start = True
            self.register_anonymous_task('init transaction', self.init_transaction, delay=2)
            # self.init_transaction()

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
        if transaction in self.pending_transactions:
            return False

        # least likely: a transaction has already been finalized
        if transaction in self.finalized_transactions:
            return False

        return True

    @message_wrapper(TransactionBody)
    async def on_transaction(self, peer: Peer, payload: TransactionBody) -> None:
        """When a transaction message is received from a client, add it to the buffer to be gossiped it to the rest of the network."""
        with self.receive_lock:
            # print(f"[Validator {self.node_id}] got TX from {self.node_id_from_peer(peer)}")

            if self.is_new_transaction(payload):
                self.buffered_transactions.append(payload)
    
    @message_wrapper(BlockVote)
    async def on_block_vote(self, peer: Peer, payload: BlockVote) -> None:
        # Find corresponding block
        block = [block for block in self.blocks if block.block_height == payload.block_height]
        if len(block) == 0:
            print(f'[Node {self.node_id}] Received invalid vote for block {payload.block_height} 1')
            return
        block = block[0]

        # Check hash
        block_package = default_serializer.pack("payload", block)
        block_hash = sha256(block_package).digest()
        if block_hash != payload.block_hash:
            print(f'[Node {self.node_id}] Received invalid vote for block {payload.block_height} 2')
            return

        # Record vote
        self.block_votes[payload.block_hash].add(self.node_id_from_peer(peer))
        print(f'[Node {self.node_id}] Received vote for block {payload.block_height}')

        # Check for majority votes (two thirds).
        if len(self.block_votes[payload.block_hash]) >= 2 * (len(self.validators) + 1) / 3:
            self.finalize_block(block)
            self.block_votes.pop(payload.block_hash)
