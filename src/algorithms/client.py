from random import randint, choice
from ipv8.community import CommunitySettings
from ipv8.types import Peer

from da_types import Blockchain, message_wrapper

from .messages import Announcement, TransactionBody

from binascii import hexlify, unhexlify


client_start_id = 2
num_clients = 2
all_clients = [x + client_start_id for x in range(num_clients)]

def to_hex(bstr: bytes) -> str:
    return hexlify(bstr).decode()


class Client(Blockchain):
    """_summary_
    Simple example that just echoes messages between two nodes
    Args:
        Blockchain (_type_): _description_
    """

    def __init__(self, settings: CommunitySettings) -> None:
        super().__init__(settings)
        self.history: list[TransactionBody] = []
        self.validators = []
        self.local_balance = 0
        self.send_counter = 0
        self.address_book = all_clients
        self.add_message_handler(TransactionBody, self.on_transaction)

    def on_start(self):
        # start by announcing ourselves to our only known validator
        self.address_book.remove(self.node_id)

        self.validators = list(self.nodes.keys())
        peer = self.nodes[self.validators[0]]
        self.ez_send(peer, Announcement(self.node_id, True))

        # register a task that sends transactions to other clients at semi-random intervals
        # (target_id assumes that an even number of validators is defined as the first nodes)
        self.register_task(
            "random_tx",
            self.send_amount,
            delay=randint(3, 4),
            interval=randint(2, 4),
        )

        # self.register_task(
        #     'request_balance',
        #     self.request_balance,
        #     delay=1,
        #     interval=1
        # )

    def send_amount(self, target_id: int = None, amount: int = None):
        """Send some to a target. If target and amount are not specified, make it random."""
        # print(f"[C{self.node_id}] Triggering client send {self.local_balance=}")
        if target_id is None:
            target_id = choice(self.address_book)
            # target_id = int(
            #     self.node_id + 1 if self.node_id % 1 == 0 else self.node_id - 1
            # )
        if amount is None:
            amount = randint(1, 100)
        if amount <= self.local_balance and self.node_id != target_id:
            transaction = TransactionBody(
                self.node_id, target_id, amount, self.send_counter
            )
            self.send_counter += 1
            for validator in self.validators:
                self.ez_send(self.nodes[validator], transaction)
                # print(
                #     f"[C{self.node_id}] sent TX to node {target_id}"
                # )
        else:
            # print(f'[C{self.node_id}] Unable to send amount, state: {self.local_balance=}, {amount=}, {target_id=}')
            pass

    # def request_balance(self):

    @message_wrapper(TransactionBody)
    async def on_transaction(self, peer: Peer, transaction: TransactionBody) -> None:
        """Upon reception of a transaction."""

        # To has messages not used right now
        # message = json.dumps({"key": "value", "key2": "value2"})
        # public_key = to_hex(self.my_peer.public_key.key_to_bin())
        # signature = to_hex(self.my_peer.key.signature(message.encode()))

        # sender_id = self.node_id_from_peer(peer)
        # print(
        #     f"[Node {self.node_id}] Got a message from node: {sender_id}.\t msg id: {payload.message_id}"
        # )
        # print(f"[C{self.node_id}] Got a TX {transaction=}")
        if (transaction.target_id == self.node_id or transaction.sender_id == self.node_id) and transaction not in self.history:
            # add transaction to history
            self.history.append(transaction)

            if transaction.target_id == self.node_id:
                # add amount to balance
                self.local_balance += transaction.amount
                print(f'[C{self.node_id}] Action=incrementing {transaction.amount=} Balance = {self.local_balance}')
            elif transaction.sender_id == self.node_id:
                # deduct from balance
                self.local_balance -= transaction.amount
                print(f'[C{self.node_id}] Action=deducting {transaction.amount=} Balance = {self.local_balance}')
