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
   11. If more than f contradictory results are received, a new election must be started. 
   12. The elected leader 
   13. The elected leader waits to receive their number of other validators' confirmation messages:
      1. If they do not include contradictory information, the leader proposes a block. 
      2. If there is contradictory information, the leader can not propose a new block and a new election is called. 

## Limitations

1. If a validator joins the network after the first election, its election round number is mismatched, so it can not propose a new election. 
