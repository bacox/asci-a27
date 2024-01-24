# Design of our Blockchain

## Assumptions
1. Non-byzantine. 
2. Clients are only connected to validators. 

## Properties
1. Clients send transactions to their validators. 
2. Clients keep a local shadow balance that is updated by validators, so clients do not need to request their balance, limiting network traffic. 

## Limitations
