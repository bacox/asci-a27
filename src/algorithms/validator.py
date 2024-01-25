from time import time
from math import ceil

from threading import RLock
from collections import defaultdict

from ipv8.community import CommunitySettings
from ipv8.types import Peer

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
factor_non_byzantine = 0.66
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
        self.validators = {}  # dict of nodeID : peer
        self.clients = {}  # dict of nodeID : peer
        self.balances = defaultdict(lambda: 0)  # dict of nodeID: balance
        self.buffered_transactions: list[TransactionBody] = []
        self.pending_transactions: list[TransactionBody] = []
        self.finalized_transactions: dict[bytes, list[TransactionBody]] = {}
        self.can_start = False
        self.receive_lock = RLock()

        # elections
        self.election_round = 1
        self.election_phase = "none"
        self.time_since_election = int(time())  # time since last succesful election
        self.available_stake = 100
        self.stake_registration = {}  # dict of validatorID : stake
        self.election_last_winner = -1
        self.election_announcement_grace_period = (
            1  # the grace period duration in seconds
        )
        self.election_winner_grace_period = 1

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
            "execute_transactions", self.execute_transactions, delay=4, interval=3
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
            transaction = TransactionBody(-1, node_id, starting_balance, 0)
            print(f"Creating transaction: {transaction=}")
            print(f"{self.clients=}")
            self.buffered_transactions.append(transaction)
            # self.ez_send(peer, transaction)

    # TODO only execute if we have block finality
    def execute_transactions(self):
        """Executes a set of transactions if approved"""
        # transactions = self.pending_transactions:
        transactions = self.pending_transactions.copy()
        self.pending_transactions = []
        for transaction in transactions:
            if transaction.sender_id == -1:
                self.balances[transaction.target_id] += transaction.amount
                print(f"Executing special {transaction=}")
            elif self.balances[transaction.sender_id] >= transaction.amount:
                print(f"Executing {transaction=}")
                self.balances[transaction.sender_id] -= transaction.amount
                self.balances[transaction.target_id] += transaction.amount
            else:
                print(
                    f"Sender {transaction.sender_id} has insuffienct funds to give {transaction.amount} to {transaction.target_id}"
                )
                self.pending_transactions.append(transaction)

            # send transaction to target client
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
            for peer in self.validators.values():
                self.ez_send(peer, gossip_message)

            print(f"Sending {len(self.buffered_transactions)=}")
            self.buffered_transactions = []

    def start_election(self):
        """Starts an election by broadcasting an announcement."""
        if self.election_phase != "none":
            return
        self.election_announce()

    def election_announce(self):
        """Broadcasts election participation."""
        self.election_phase = "announce"
        stake = self.available_stake * 0.5
        message = AnnounceConcensusParticipation(
            self.election_round, self.node_id, stake
        )
        for validator in self.validators.values():
            self.ez_send(validator, message)

    @message_wrapper(AnnounceConcensusParticipation)
    async def on_election_announcement(
        self, peer: Peer, payload: AnnounceConcensusParticipation
    ):
        """When an election participation is received, save the result."""

        # check whether we're not already in an election
        if self.election_phase not in ("none", "elect", "elect_grace"):
            return

        # check whether this is a valid election round
        if payload.election_round < self.election_round:
            print(
                f"Ignoring received old election announcement (round {payload.election_round=}<{self.election_round=})"
            )
            return
        elif payload.election_round > self.election_round:
            self.election_round = payload.election_round

        # send our own participation if not done yet
        if self.election_phase == "none":
            self.election_announce()

        # save the results
        self.stake_registration[payload.sender_id] = payload.stake
        if payload.sender_id not in self.validators:
            self.validators[payload.sender_id] = peer

        # if we have received the minimum expected announcements, start a grace period
        if len(self.stake_registration) >= ceil(
            len(self.validators) * factor_non_byzantine
        ):
            if self.election_phase == "announce_grace":
                self.cancel_pending_task("election_announce_participation_grace_period")
            # after the grace period, announce the winner
            self.election_phase = "announce_grace"
            self.register_task(
                "election_announce_participation_grace_period",
                self.election_announce_winner,
                delay=self.election_announcement_grace_period,
            )

    def election_announce_winner(self):
        """Calculates and broadcasts the election winner."""
        assert self.election_phase == "announce_grace"
        self.election_phase = "elect"
        # TODO
        winner_id = -1
        random_seed = -1

        # broadcast the winner
        message = AnnounceConcensusWinner(
            self.election_round, winner_id, random_seed, len(self.validators)
        )
        for validator in self.validators.values():
            self.ez_send(validator, message)

    @message_wrapper(AnnounceConcensusWinner)
    async def on_election_result(self, peer: Peer, payload: AnnounceConcensusWinner):
        """When an election winner is received, verify it."""
        # TODO
        # verify the incoming

        # if it is not valid, cancel the grace and start a new election round
        if self.election_phase == "elect_grace":
            self.cancel_pending_task("election_announce_winner_grace_period")
        self.election_round += 1
        self.start_election()

        # if we have received the minimum expected announcements, start a grace period
        if len(self.stake_registration) >= ceil(
            len(self.validators) * factor_non_byzantine
        ):
            if self.election_phase == "elect_grace":
                self.cancel_pending_task("election_announce_winner_grace_period")
            # after the grace period, announce the winner
            self.election_phase = "elect_grace"
            self.register_task(
                "election_announce_winner_grace_period",
                self.election_ratify,
                delay=self.election_winner_grace_period,
            )

    def election_ratify(self):
        """If no contradictory results have been received, ratify the election outcome."""
        assert self.election_phase == "elect_grace"
        self.election_phase = "ratify"
        # TODO
        # self.election_last_winner =
        self.election_phase = "none"
        self.election_round += 1

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
        if transaction in self.pending_transactions:
            return False

        # least likely: a transaction has already been finalized
        if transaction in list(self.finalized_transactions.values()):
            return False

        return True

    @message_wrapper(TransactionBody)
    async def on_transaction(self, peer: Peer, payload: TransactionBody) -> None:
        """When a transaction message is received from a client, add it to the buffer to be gossiped it to the rest of the network."""
        with self.receive_lock:
            print(
                f"[Validator {self.node_id}] got TX from {self.node_id_from_peer(peer)}"
            )

            if self.is_new_transaction(payload):
                self.buffered_transactions.append(payload)
