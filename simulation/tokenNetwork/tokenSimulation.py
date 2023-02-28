import collections
import logging
import math
import os
import random
import threading
from asyncio import ensure_future, get_event_loop
from dataclasses import dataclass

from ipv8.community import Community
from ipv8.configuration import ConfigBuilder
from ipv8.lazy_community import lazy_wrapper
from ipv8.messaging.payload_dataclass import overwrite_dataclass

from simulation.common.settings import SimulationSettings
from simulation.common.simulation import SimulatedCommunityMixin, BamiSimulation
from simulation.common.utils import time_mark, connected_topology

dataclass = overwrite_dataclass(dataclass)


@dataclass
class Record:
    address: bytes
    tx_id: int
    amount: int


@dataclass(msg_id=1)
class TransferMessage:
    tx_id: int
    tokens: int


@dataclass(msg_id=2)
class BalanceMessage:
    records: [Record]


class TokenCommunity(Community):
    """
    This basic community sends ping messages to other known peers every two seconds.
    """
    community_id = os.urandom(20)

    lock = threading.Lock()

    def __init__(self, my_peer, endpoint, network):
        super().__init__(my_peer, endpoint, network)
        self.add_message_handler(1, self.on_receive_transfer)
        self.add_message_handler(2, self.on_receive_balance)

        self.my_peer.records = {self.my_peer.mid: (0, 1000)}

    def started(self):
        self.register_task("random_transfer", self.random_transfer, interval=100.0, delay=0)

    @lazy_wrapper(TransferMessage)
    def on_receive_transfer(self, peer, payload):
        self.logger.info("🔥 <t=%.1f> peer %s received transfer of %s", get_event_loop().time(), self.my_peer.address,
                         payload.tokens)

        self.logger.info("🔥 <t=%.1f> records: %s", get_event_loop().time(), self.my_peer.records)
        peer_tx_id, peer_amount = self.my_peer.records.get(peer.mid, (0, 1000))
        new_peer_tx_id = max(peer_tx_id, payload.tx_id)
        new_peer_amount = peer_amount - payload.tokens

        self.my_peer.records[peer.mid] = (new_peer_tx_id, new_peer_amount)

        my_tx_id, my_amount = self.my_peer.records.get(self.my_peer.mid)
        new_my_tx_id = my_tx_id + 1
        new_my_amount = my_amount + payload.tokens
        self.my_peer.records[self.my_peer.mid] = (new_my_tx_id, new_my_amount)
        self.logger.info("🔥 <t=%.1f> records: %s", get_event_loop().time(), self.my_peer.records)

        self.gossip_balance(
            [Record(peer.mid, new_peer_tx_id, new_peer_amount), Record(self.my_peer.mid, new_my_tx_id, new_my_amount)])

    @lazy_wrapper(BalanceMessage)
    def on_receive_balance(self, peer, payload):
        self.logger.info("🔥 <t=%.1f> peer %s received balance update of %s", get_event_loop().time(),
                         self.my_peer.address,
                         payload.records)

        new_records = False
        for record in payload.records:
            if record.address not in self.my_peer.records or self.my_peer.records[record.address][0] < record.tx_id:
                new_records = True
                self.my_peer.records[record.address] = (record.tx_id, record.amount)
        if new_records:
            self.gossip_balance(payload.records)

    def random_transfer(self):
        if len(self.network.verified_peers) < 1:
            return

        tx_id, amount = self.my_peer.records[self.my_peer.mid]
        selected_amount = random.randint(1, 3)

        if selected_amount > amount:
            return

        selected_peer = random.choice(tuple(self.network.verified_peers))
        self.logger.info("🔥 <t=%.1f> peer %s sending transfer of %s to %s", get_event_loop().time(),
                         self.my_peer.address, selected_amount, selected_peer.address)

        self.ez_send(selected_peer, TransferMessage(tx_id, selected_amount))
        self.my_peer.records[self.my_peer.mid] = (tx_id + 1, amount - selected_amount)

    def gossip_balance(self, update: [(bytes, int, int)]):
        if len(self.network.verified_peers) < 1:
            return
        peers = random.sample(tuple(self.network.verified_peers), math.ceil(0.25 * len(self.network.verified_peers)))
        for selected_peer in peers:
            self.ez_send(selected_peer, BalanceMessage(update))


class BasicTokenSimulation(BamiSimulation):
    def get_ipv8_builder(self, peer_id: int) -> ConfigBuilder:
        builder = super().get_ipv8_builder(peer_id)
        builder.add_overlay("TokenCommunity", "my peer", [], [], {}, [('started',)])
        return builder


class SimulatedToken(SimulatedCommunityMixin, TokenCommunity):
    random_transfer = time_mark(TokenCommunity.random_transfer)
    gossip_balance = time_mark(TokenCommunity.gossip_balance)


if __name__ == "__main__":
    # We use a discrete event loop to enable quick simulations.
    settings = SimulationSettings()
    settings.peers = 6
    settings.duration = 1000
    settings.topology = connected_topology(settings.peers)
    settings.community_map = {'TokenCommunity': SimulatedToken}

    simulation = BasicTokenSimulation(settings)
    ensure_future(simulation.run())
    simulation.loop.run_forever()

    logger = logging.getLogger()
    logger.info("🔥 <t=%.1f> simulation finished" % get_event_loop().time())
    print("printing results")
    for i in simulation.nodes:
        instance = simulation.nodes[i].overlays[0]
        od = collections.OrderedDict(sorted(instance.my_peer.records.items()))
        logger.info(" Peer %s: balance: %s" % (i, od))
