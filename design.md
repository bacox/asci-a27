# Design of our Blockchain

## Assumptions
1. Non-disjoint static network. 
2. All nodes are non-byzantine (non-faulty and non-adversarial). 
3. Clients are only connected to validators. 
4. Nodes are honest about their identifiers.

## Properties
1. All network traffic is lazy, so no polling. 
2. Clients send transactions to their validators. 
3. Validators buffer transactions, only updating the mempool (pending transactions) in batches, limiting network traffic. 
4. Clients keep a local shadow balance that is updated by validators, so clients do not need to request their balance, limiting network traffic. 
5. Achieving Concensus works as follows:
   1. Elections are held after a set amount of time has passed. Any validator with a set amount of pending transactions can also announce an early election. 
   2. There can not be two elections at the same time. If two elections announcements are received at the same time, the caller with the lowest node ID wins.
   3. Every validator willing to participate in the election announces itself as so, along with their stake.
   4. Each validator receives the announcements, and saves them with node ID as key and stake as value. It then forwards the announcement to all but the sender. 
   5. After N-f announcements have been received, wait for a grace period to receive additional ones. 
   6. The validators sum the stake values, and use the outcome as a random seed. 
   7. The random seed is used to choose the validator proportional to the stakes, ordered by node ID. 
   8. Each validator broadcasts their election result and their number of validators. 
   9. Each validator receives the election results, and forwards the result to all but the sender.
   10. After N-f results have been received, wait for a grace period to receive additional ones. 
   11. After this grace period, if more than f contradictory results are received, a new election must be started. If this is not the case, the elected leader is known. 
   12. The leader can propose a new block. 

## Limitations

1. If a validator joins the network after the first election, its election round number is mismatched, so it can not propose a new election. 

## Message complexity

We will use C for number of clients, V for number of validators, and N for C+V. 
Message complexity is defined from the perspective of a single transaction. 
1. Client-validator transaction passing: 1 message to send a transaction to a validator, 1 message to receive a balance update from a validator. 
2. Validator-validator transaction gossiping: transactions are batched and broadcast by every validator. In the worst case where we only have a single transaction in a gossip message, we have V-1^2 messages, best case V-1.  
3. Elections: worst case of announcement / participation is 2^V-1, as every validator must communicate to all other validators that it participates. We have again 2^V-1 for the communication of results to ratify the election. 
4. Block communication: leader proposes block containing multiple transactions, worst case is again V-1^2, best case V-1. 
If we do big-O style and keep only the worst complexity, the worst case for a single transaction is that 2(2^V-1). 