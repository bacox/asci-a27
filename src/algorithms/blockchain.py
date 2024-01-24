import random
import time
from collections import defaultdict
from hashlib import sha256
from typing import List

from ipv8.community import CommunitySettings
from ipv8.messaging.payload_dataclass import overwrite_dataclass
from dataclasses import dataclass

from ipv8.messaging.serialization import default_serializer
from ipv8.types import Peer

from da_types import Blockchain, message_wrapper

# We are using a custom dataclass implementation.
dataclass = overwrite_dataclass(dataclass)


@dataclass(
    msg_id=1
)  # The value 1 identifies this message and must be unique per community.
class Transaction:
    sender: int
    receiver: int
    amount: int
    nonce: int = 1
    is_stake: bool = False


@dataclass(msg_id=2)
class Block:
    block_height: int
    prev_block_hash: bytes
    timestamp: int
    transactions: [Transaction]


@dataclass(msg_id=3)
class BlockVote:
    block_height: int
    block_hash: bytes


MAX_TX_AMOUNT = 5


class BlockchainNode(Blockchain):

    def __init__(self, settings: CommunitySettings) -> None:
        super().__init__(settings)
        self.counter = 1

        self.pending_txs = []
        self.finalized_txs = []

        self.balances = defaultdict(lambda: 1000)
        self.stakes = defaultdict(lambda: 0)

        self.blocks = []

        self.block_votes = defaultdict(lambda: set())

        self.add_message_handler(Transaction, self.on_transaction)
        self.add_message_handler(Block, self.on_block)
        self.add_message_handler(BlockVote, self.on_block_vote)

    def on_start(self):
        if self.node_id % 2 == 0:
            #  Run client
            self.start_client()
        else:
            # Run validator
            self.start_validator()

    def create_transaction(self):
        peer = random.choice([i for i in self.get_peers() if self.node_id_from_peer(i) % 2 == 1])
        peer_id = self.node_id_from_peer(peer)

        tx = Transaction(self.node_id,
                         peer_id,
                         10,
                         self.counter)
        self.counter += 1
        print(f'[Node {self.node_id}] Sending transaction {tx.nonce} to {self.node_id_from_peer(peer)}')
        self.ez_send(peer, tx)

    def start_client(self):
        # Create transaction and send to random validator
        # Or put node_id
        self.register_task("tx_create",
                           self.create_transaction, delay=1,
                           interval=10)

    def start_validator(self):
        self.register_task("select_leader", self.select_leader, delay=5, interval=10)
        self.register_task("update_stake", self.send_stake, delay=5, interval=10)

        # Assume some stake
        all_validators = [self.node_id_from_peer(peer) for peer in self.get_validators()] + [self.node_id]
        all_validators = sorted(all_validators)
        for validator in all_validators:
            self.stakes[validator] = 100

    def get_block_height(self):
        if len(self.blocks) > 0:
            return self.blocks[-1].block_height
        return 0

    def get_validators(self):
        return [i for i in self.get_peers() if self.node_id_from_peer(i) % 2 == 1]

    def send_stake(self):
        # Create stake
        stake = Transaction(self.node_id, -1, 10, self.counter, True)
        self.counter += 1
        for peer in self.get_validators():
            self.ez_send(peer, stake)

    def select_leader(self):
        random.seed(self.get_block_height() + 1)
        leader = random.choices([i for i in self.stakes.keys() if self.stakes[i] > 0],
                                weights=list(self.stakes.values()))[0]
        print(f'[Node {self.node_id}] Selected leader {leader}')
        if self.node_id == leader:
            print(f'[Node {self.node_id}] Selected as leader')
            self.form_block()

    def form_block(self):
        # We assume that blocks are ordered.
        prev_block_hash = b'0'
        if len(self.blocks) > 0:
            prev_block_hash = sha256(default_serializer.pack('payload', self.blocks[-1])).digest()

        block = Block(self.get_block_height() + 1, prev_block_hash, int(time.time()),
                      [tx for tx in self.pending_txs[:MAX_TX_AMOUNT]])

        self.blocks.append(block)

        # Gossip to other nodes
        for peer in self.get_validators():
            self.ez_send(peer, block)

        # We confirm our own block
        self.broadcast_block_confirmation(block)

    def check_transactions(self, transactions: List[Transaction]):
        for tx in transactions:

            if tx.is_stake:
                self.handle_stake(tx)
            else:
                self.handle_tx(tx)

            self.pending_txs.remove(tx)
            self.finalized_txs.append(tx)

    def handle_tx(self, tx):
        if self.balances[tx.sender] - tx.amount >= 0:
            self.balances[tx.sender] -= tx.amount
            self.balances[tx.receiver] += tx.amount

    def handle_stake(self, payload):
        if self.balances[payload.sender] - payload.amount >= 0:
            self.balances[payload.sender] -= payload.amount
            self.stakes[payload.sender] += payload.amount
            print(f'[Node {self.node_id}] Staked {payload.amount} by {payload.sender}')
        else:
            print(f'[Node {self.node_id}] Not enough balance to stake {payload.amount} by {payload.sender}')

    def handle_transactions(self, payload):
        # Add to pending transactions
        if (payload.sender, payload.nonce) not in [(tx.sender, tx.nonce) for tx in self.finalized_txs] and (
                payload.sender, payload.nonce) not in [(tx.sender, tx.nonce) for tx in self.pending_txs]:
            self.pending_txs.append(payload)

            # Gossip to other nodes
            for peer in self.get_validators():
                self.ez_send(peer, payload)

    def validate_block(self, block: Block):
        # Left as an assignment for the reader.
        # TODO: validate block
        return True

    def finalize_block(self, block: Block):
        self.check_transactions(block.transactions)
        print(f'[Node {self.node_id}] Finalized block {block.block_height} with {len(block.transactions)} transactions')

    def broadcast_block_confirmation(self, block):
        block_package = default_serializer.pack("payload", block)
        block_hash = sha256(block_package).digest()
        block_vote = BlockVote(block.block_height, block_hash)
        self.block_votes[block_hash].add(self.node_id)
        for peer in self.get_validators():
            self.ez_send(peer, block_vote)
        pass

    @message_wrapper(Transaction)
    async def on_transaction(self, peer: Peer, payload: Transaction) -> None:
        self.handle_transactions(payload)

    @message_wrapper(Block)
    async def on_block(self, peer: Peer, payload: Block) -> None:
        if self.validate_block(payload):
            if payload not in self.blocks:
                self.blocks.append(payload)

                for peer in self.get_validators():
                    self.ez_send(peer, payload)

                # TODO: there might be soft forks.
                self.broadcast_block_confirmation(payload)
            print(f'[Node {self.node_id}] Received block {payload.block_height}')
            return
        else:
            print(f'[Node {self.node_id}] Received invalid block {payload.block_height}')

    @message_wrapper(BlockVote)
    async def on_block_vote(self, peer: Peer, payload: BlockVote) -> None:
        # Find corresponding block
        block = [block for block in self.blocks if block.block_height == payload.block_height]
        if len(block) == 0:
            print(f'[Node {self.node_id}] Received invalid vote for block {payload.block_height}')
            return
        block = block[0]

        # Check hash
        block_package = default_serializer.pack("payload", block)
        block_hash = sha256(block_package).digest()
        if block_hash != payload.block_hash:
            print(f'[Node {self.node_id}] Received invalid vote for block {payload.block_height}')
            return

        # Record vote
        self.block_votes[payload.block_hash].add(self.node_id_from_peer(peer))
        print(f'[Node {self.node_id}] Received vote for block {payload.block_height}')

        # Check for majority votes (two thirds).
        if len(self.block_votes[payload.block_hash]) >= 2 * (len(self.get_validators()) + 1) / 3:
            self.finalize_block(block)
            self.block_votes.pop(payload.block_hash)
