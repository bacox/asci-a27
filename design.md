# Design of our Blockchain

## Assumptions
1. Non-disjoint network. 
2. All nodes are non-byzantine (non-faulty and non-adversarial). 
3. Clients are only connected to validators. 

## Properties
1. All network traffic is lazy, so no polling. 
2. Clients send transactions to their validators. 
3. Clients keep a local shadow balance that is updated by validators, so clients do not need to request their balance, limiting network traffic. 
4. Achieving Concensus works as follows:
   1. Elections are held after a set amount of time has passed. Any validator with a set amount of pending transactions can also announce an early election. 
   2. There can not be two elections at the same time. If two elections announcements are received at the same time, the caller with the lowest node ID wins.
   3. Every validator willing to participate in the election announces itself as so, along with their stake.
   4. Each validator receives the announcements, and orders them on node ID (key: node ID, value: stake).
   5. The validators sum the values, and use the outcome as a random seed. 
   6. The random seed is used to select the validator proportional to the stakes. 
   7. Each validator broadcasts their election result and the number of nodes. 
   8. The elected leader waits to receive their number of other validators' confirmation messages:
      1. If they do not include contradictory information, the leader proposes a block. 
      2. If there is contradictory information, the leader can not propose a new block and a new election is called. 

## Limitations

1. If a validator joins the network after the first election, its election round number is mismatched, so it can not propose a new election. 
