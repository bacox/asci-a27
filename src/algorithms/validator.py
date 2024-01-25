from time import time
from math import ceil
import random

from threading import RLock
from collections import defaultdict

from ipv8.community import CommunitySettings
from ipv8.types import Peer
from collections import defaultdict
from ipv8.messaging.serialization import default_serializer
from hashlib import sha256
from da_types import Blockchain, message_wrapper
from .messages import (
    Announcement,
    Block,
    BlockVote,
    TransactionBody,
    Gossip,
    BlockHeader,
)
from threading import RLock

from da_types import Blockchain, message_wrapper
from .messages import (
    Announcement,
    TransactionBody,
    Gossip,
    AnnounceConcensusParticipation,
    AnnounceConcensusWinner,
)

# parameters
starting_balance = 1000
block_width = 5
factor_non_byzantine = 0.66
early_election_minimum_transactions = (
    4  # number of pending transactions before an early election is called
)
election_phases = (
    "none",
    "announce",
    "announce_grace",
    "elect",
    "elect_grace",
    "ratify",
)


class Validator(Blockchain):
    """_summary_
    Simple example that just echoes messages between two nodes
    Args:
        Blockchain (_type_): _description_
    """

    def __init__(self, settings: CommunitySettings) -> None:
        super().__init__(settings)
        self.validators: dict[int, Peer] = {}  # dict of nodeID : peer
        self.clients: dict[int, Peer] = {}  # dict of nodeID : peer
        self.balances = defaultdict(lambda: 0)  # dict of nodeID: balance
        self.buffered_transactions: list[TransactionBody] = []
        self.pending_transactions: list[TransactionBody] = []
        self.finalized_transactions: list[TransactionBody] = []
        self.can_start = False
        self.receive_lock = RLock()
        self.blocks = []
        self.block_votes = defaultdict(lambda: set())

        # elections
        self.election_round = 1
        self.election_phase = "none"
        self.time_since_election = int(time())  # time since last succesful election
        self.available_stake = 100
        self.active_block_proposal = False
        self.stake_registration = {}  # dict of validatorID : stake
        self.result_registration = {}  # dict of validatorID : payload
        self.election_random_seed = None
        self.election_winner_id = None
        self.election_announcement_grace_period = (
            5  # the grace period duration in seconds
        )
        self.election_winner_grace_period = 5

        # register the handlers
        self.add_message_handler(Gossip, self.on_gossip)
        self.add_message_handler(Announcement, self.on_announcement)
        self.add_message_handler(TransactionBody, self.on_transaction)
        self.add_message_handler(Block, self.on_block)
        self.add_message_handler(BlockVote, self.on_block_vote)
        self.add_message_handler(
            AnnounceConcensusParticipation, self.on_election_announcement
        )
        self.add_message_handler(AnnounceConcensusWinner, self.on_election_result)

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

        self.register_task("act_leader", self.act_leader, delay=5, interval=2)
        self.register_task(
            "send_buffered_transactions",
            self.send_buffered_transactions,
            delay=4,
            interval=3,
        )
        self.register_task("election_timer", self.start_election, delay=30, interval=30)

    def init_transaction(self):
        """The init transactions are executed after the announcements have been completed."""
        print("Init TX")
        for node_id in self.clients:
            # if the node_id was not in the validator database, add it
            if node_id not in self.balances:
                self.balances[node_id] = starting_balance
            transaction = TransactionBody(-1, node_id, starting_balance, 0)
            print(f"Creating transaction: {transaction=}")
            print(f"{self.clients=}")
            self.buffered_transactions.append(transaction)

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
        prev_block_hash = b"0"
        if len(self.blocks) > 0:
            prev_block_hash = sha256(
                default_serializer.pack("payload", self.blocks[-1])
            ).digest()
        if block.prev_block_hash == prev_block_hash:
            # Check all transactions
            return True
        else:
            print(f"Invalid: {block.prev_block_hash} == {prev_block_hash}")
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
        prev_block_hash = b"0"
        if len(self.blocks) > 0:
            prev_block_hash = sha256(
                default_serializer.pack("payload", self.blocks[-1])
            ).digest()

        block = Block(
            self.get_block_height() + 1,
            prev_block_hash,
            int(time()),
            [tx for tx in self.pending_transactions[:block_width]],
        )

        self.blocks.append(block)

        # Gossip to other nodes
        for peer in self.validators.values():
            self.ez_send(peer, block)

        # We confirm our own block
        # @TODO: DO conformation
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
            self.broadcast(gossip_message, self.my_peer, validators=True, clients=False)

            # print(f"Sending {len(self.buffered_transactions)} buffered transactions")
            self.buffered_transactions = []
            if len(self.pending_transactions) >= early_election_minimum_transactions:
                self.start_election()

    def start_election(self):
        """Starts an election."""
        if self.election_phase != "none":
            return
        self.election_announce(self.node_id)

    def election_announce(self, origin_id: int):
        """Broadcasts election participation."""
        if self.election_phase != "announce_grace":
            self.election_phase = "announce"
        print(
            f" [V{self.node_id}] Election {self.election_round} phase: {self.election_phase} started by {origin_id}"
        )
        self.election_winner_id = None
        stake = round(self.available_stake * 0.5)
        self.stake_registration[self.node_id] = stake
        message = AnnounceConcensusParticipation(
            self.election_round, self.node_id, stake, origin_id
        )
        print(message)
        self.broadcast(message, self.my_peer, validators=True, clients=False)

    @message_wrapper(AnnounceConcensusParticipation)
    async def on_election_announcement(
        self, peer: Peer, payload: AnnounceConcensusParticipation
    ):
        """When an election participation is received, save the result."""
        print(
            f" [V{self.node_id}] received election participation from {payload.sender_id}:"
        )

        # check whether we're able to receive participations
        if self.election_phase not in ("none", "announce", "announce_grace"):
            print(
                f"[V{self.node_id}] received election participation from {payload.sender_id}, but is already in phase {self.election_phase}, ignoring"
            )
            return

        # check whether this is a valid election round
        if payload.election_round < self.election_round:
            print(
                f"Ignoring received old election announcement (round {payload.election_round=}<{self.election_round=})"
            )
            return
        elif payload.election_round > self.election_round:
            self.election_round = payload.election_round

        # if the message came from an unseen validator, add it to the known validators
        if (
            payload.sender_id not in self.validators
            and payload.sender_id != self.node_id
        ):
            self.validators[payload.sender_id] = peer

        # send our own participation if not done yet
        if self.election_phase == "none":
            self.election_announce(payload.origin_id)

        # save the received stakes and broadcast
        if payload.sender_id not in self.stake_registration:
            self.stake_registration[payload.sender_id] = payload.stake
            self.broadcast(payload, peer, validators=True, clients=False)

        # if we have received the minimum expected announcements, start a grace period
        if len(self.stake_registration) - 1 >= ceil(
            len(self.validators) * factor_non_byzantine
        ):  # minus 1 on stake_registration because that includes ourselves
            if self.election_phase == "announce_grace":
                self.cancel_pending_task("election_announce_participation_grace_period")
            # after the grace period, figure out the winner
            self.election_phase = "announce_grace"
            self.register_task(
                "election_announce_participation_grace_period",
                self.election_announce_winner,
                delay=self.election_announcement_grace_period,
            )
            print(f"Node {self.node_id} Election phase: {self.election_phase}")

    def election_announce_winner(self):
        """Calculates and broadcasts the election winner."""
        assert self.election_phase == "announce_grace"
        self.cancel_pending_task(
            "election_announce_participation_grace_period"
        )  # cancel to avoid double execution
        self.election_phase = "elect"
        # print(
        #     f" [V{self.node_id}] Election {self.election_round} phase: {self.election_phase}"
        # )

        # sum the stake values, and use the outcome as a random seed
        self.election_random_seed = sum(self.stake_registration.values())
        random.seed(self.election_random_seed)

        # the random seed is used to choose the validator proportional to the stakes, ordered by node ID
        self.stake_registration = dict(sorted(self.stake_registration.items()))
        self.election_winner_id = random.choices(
            list(self.stake_registration.keys()), list(self.stake_registration.values())
        )[0]
        print(
            f" [V{self.node_id}] elected {self.election_winner_id} with seed {self.election_random_seed}"
        )

        # broadcast the election result and number of validators
        message = AnnounceConcensusWinner(
            self.election_round,
            self.node_id,
            self.election_winner_id,
            self.election_random_seed,
            len(self.validators),
        )
        self.broadcast(message, self.my_peer, validators=True, clients=False)

    @message_wrapper(AnnounceConcensusWinner)
    async def on_election_result(self, peer: Peer, payload: AnnounceConcensusWinner):
        """When an election winner is received, store it for verification."""
        print(f" [V{self.node_id}] received election result from {payload.sender_id}:")

        # check whether we're able to receive participations
        if self.election_phase not in ("elect", "elect_grace"):
            print(
                f"[V{self.node_id}] received election participation from {payload.sender_id}, but is in phase {self.election_phase}, ignoring"
            )
            return

        # check whether this is a valid election round
        if payload.election_round < self.election_round:
            print(
                f"Ignoring received old election announcement (round {payload.election_round=}<{self.election_round=})"
            )
            return
        elif payload.election_round > self.election_round:
            # self.election_round = payload.election_round
            raise ValueError("TF is going on here")

        # if the message came from an unseen validator, add it to the known validators
        if (
            payload.sender_id not in self.validators
            and payload.sender_id != self.node_id
        ):
            self.validators[payload.sender_id] = peer

        # send our own result if not done yet
        if self.election_winner_id is None:
            self.election_announce_winner()

        # save the received results and broadcast
        if payload.sender_id not in self.result_registration:
            self.result_registration[payload.sender_id] = payload
            self.broadcast(payload, peer, validators=True, clients=False)

        # if we have received the minimum expected announcements, start a grace period
        if len(self.result_registration) >= ceil(
            len(self.validators) * factor_non_byzantine
        ):
            if self.election_phase == "elect_grace":
                self.cancel_pending_task("election_announce_winner_grace_period")
            # after the grace period, ratify the results
            self.election_phase = "elect_grace"
            self.register_task(
                "election_announce_winner_grace_period",
                self.election_ratify,
                delay=self.election_winner_grace_period,
            )

    def election_ratify(self):
        """If no contradictory results have been received, ratify the election outcome."""
        assert (
            self.election_phase == "elect_grace" and self.election_winner_id is not None
        )
        self.cancel_pending_task(
            "election_announce_winner_grace_period"
        )  # cancel to avoid double execution
        self.election_phase = "ratify"

        # for each result received, check if it confirms our findings
        valid = 0
        for key, payload in self.result_registration.items():
            if (
                payload.sender_id == key
                and payload.election_round == self.election_round
                and payload.winner_id == self.election_winner_id
                and payload.random_seed == self.election_random_seed
                and payload.number_of_validators == len(self.validators)
            ):
                valid += 1
            else:
                print(
                    f" [V{self.node_id}] Election result of {key} does not match ours"
                )
                print(
                    f"Ours: {self.election_round=}, {self.election_winner_id=}, {self.election_random_seed=}, {len(self.validators)=}"
                )
                print("Theirs:")
                print(payload)

        # prepare the variables for a next election
        self.election_phase = "none"
        self.election_random_seed = None
        self.stake_registration = {}
        self.result_registration = {}
        self.election_round += 1

        # if less than N-f contradictory results are received, a new election must be started
        if valid < ceil(len(self.validators) * factor_non_byzantine):
            self.election_round += 1
            self.election_winner_id = None
            self.start_election()

    def finalize_block(self, block: Block):
        print("Finalizing block")
        self.execute_transactions(block.transactions)

        # self.check_transactions(block.transactions)
        print(
            f"[Node {self.node_id}] Finalized block {block.block_height} with {len(block.transactions)} transactions"
        )
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
            print(
                f"[Node {self.node_id}] Received block {payload.block_height} ({len(self.blocks)})"
            )
        else:
            print(
                f"[Node {self.node_id}] Received invalid block {payload.block_height}"
            )

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

        # broadcast the gossip
        if len(to_gossip) > 0:
            gossip_message = Gossip(to_gossip)
            self.broadcast(gossip_message, peer, validators=True, clients=False)

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
                self.broadcast(payload, peer, validators=True, clients=False)
        elif sender_id != self.node_id:
            self.validators[sender_id] = peer

        # create the initial transaction
        if (
            self.node_id == 0
            and len(self.validators) + len(self.clients) >= len(self.nodes)
            and len(self.clients) > 0
            and not self.can_start
        ):
            self.can_start = True
            self.register_anonymous_task(
                "init transaction", self.init_transaction, delay=2
            )
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
        block = [
            block for block in self.blocks if block.block_height == payload.block_height
        ]
        if len(block) == 0:
            print(
                f"[Node {self.node_id}] Received invalid vote for block {payload.block_height} 1"
            )
            return
        block = block[0]

        # Check hash
        block_package = default_serializer.pack("payload", block)
        block_hash = sha256(block_package).digest()
        if block_hash != payload.block_hash:
            print(
                f"[Node {self.node_id}] Received invalid vote for block {payload.block_height} 2"
            )
            return

        # Record vote
        self.block_votes[payload.block_hash].add(self.node_id_from_peer(peer))
        print(f"[Node {self.node_id}] Received vote for block {payload.block_height}")

        # Check for majority votes (two thirds).
        if (
            len(self.block_votes[payload.block_hash])
            >= 2 * (len(self.validators) + 1) / 3
        ):
            self.finalize_block(block)
            self.block_votes.pop(payload.block_hash)

    def broadcast(self, payload, originator: Peer, validators=True, clients=True):
        """Utility function to broadcast a message to a selection of nodes."""
        if validators:
            # use set of validator peers to make sure we don't send to the same peers
            for validator in set(self.validators.values()):
                if validator is not originator and validator is not self.my_peer:
                    self.ez_send(validator, payload)
        if clients:
            for client in set(self.clients.values()):
                if client is not originator and client is not self.my_peer:
                    self.ez_send(client, payload)
