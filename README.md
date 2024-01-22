# Lab Template for A27

This code serves as a foundational template for the ASCI course A27 - Fundamentals and Design of Blockchain-based Systems. It has been rigorously tested on Ubuntu 20.04 and MacOS 14, and should be compatible with Windows systems.

**Note:** Ensure that Python version 3.8 or higher is installed when running this code locally.

## Documentation

- [IPv8 Documentation](https://py-ipv8.readthedocs.io/en/latest/index.html)
- [Asyncio Documentation](https://docs.python.org/3/library/asyncio.html): Asyncio is extensively utilized in this code's implementation.

## File Structure

- **src:** Contains all the Python source files.
- **src/algorithms:** Houses code for various distributed algorithms.
- **topologies/default.yaml:** Lists the addresses of participating processes in the algorithm.
- **Dockerfile:** Describes the image used by docker-compose.
- **docker-compose.yml:** YAML file that describes the system for docker-compose.
- **docker-compose.template.yml:** YAML file used as a template for the `src/util.py` script.
- **run_echo.sh:** Script to run the echo example.
- **run_election.sh:** Script to run the ring election example.

## Topology File

The topology file (located in `./topologies`) defines how nodes in the system are interconnected. It comprises a YAML file listing node IDs along with their corresponding connections to other nodes. To alter the number or type of nodes in a topology, adjust the `util.py` script.

## Remarks

1. This template is provided as a starting point with functioning messaging between distributed processes. You are encouraged to modify any of the files as per your requirements.
2. Ensure the topology is aligned with the assignment specifications. The default `util.py` creates a ring topology. Modify the script if you need a different topology (e.g., fully-connected, sparse network).

## Prerequisites

- Docker
- Docker-compose
- (Python >= 3.8 if running locally)

To install dependencies, use:

```bash
pip install -r requirements.txt
```

The expected output should be identical whether running with docker-compose or locally.

## Docker Examples

### Echo Algorithm

```bash
NUM_NODES=2
python src/util.py $NUM_NODES topologies/echo.yaml echo
docker compose build
docker compose up
```

**Expected Output:**

```text
in4150-python-template-node1-1  | [Node 1] Starting
in4150-python-template-node0-1  | [Node 0] Starting
in4150-python-template-node0-1  | [Node 0] Got a message from node: 1.   current counter: 1
in4150-python-template-node1-1  | [Node 1] Got a message from node: 0.   current counter: 2
in4150-python-template-node0-1  | [Node 0] Got a message from node: 1.   current counter: 3
in4150-python-template-node1-1  | [Node 1] Got a message from node: 0.   current counter: 4
in4150-python-template-node0-1  | [Node 0] Got a message from node: 1.   current counter: 5
in4150-python-template-node1-1  | [Node 1] Got a message from node: 0.   current counter: 6
in4150-python-template-node0-1  | [Node 0] Got a message from node: 1.   current counter: 7
in4150-python-template-node1-1  | [Node 1] Got a message from node: 0.   current counter: 8
in4150-python-template-node0-1  | [Node 0] Got a message from node: 1.   current counter: 9
in4150-python-template-node1-1  | Node 1 is stopping
in4150-python-template-node1-1  | [Node 1] Got a message from node: 0.   current counter: 10
in4150-python-template-node1-1  | [Node 1] Stopping algorithm
in4150-python-template-node0-1  | Node 0 is stopping
in4150-python-template-node0-1  | [Node 0] Got a message from node: 1.   current counter: 11
in4150-python-template-node0-1  | [Node 0] Stopping algorithm
in4150-python-template-node1-1 exited with code 0
in4150-python-template-node0-1 exited with code 0
```

### Ring Election Algorithm

```bash
NUM_NODES=4
python src/util.py $NUM_NODES topologies/election.yaml election
docker compose build
docker compose up
```

**Expected Output:**

```text
in4150-python-template-node2-1  | [Node 2] Starting
in4150-python-template-node0-1  | [Node 0] Starting
in4150-python-template-node3-1  | [Node 3] Starting
in4150-python-template-node1-1  | [Node 1] Starting
in4150-python-template-node3-1  | [Node 3] Starting by selecting a node: 0
in4150-python-template-node0-1  | [Node 0] Got a message from with elector id: 3
in4150-python-template-node1-1  | [Node 1] Got a message from with elector id: 3
in4150-python-template-node2-1  | [Node 2] Got a message from with elector id: 3
in4150-python-template-node3-1  | [Node 3] Got a message from with elector id: 3
in4150-python-template-node3-1  | [Node 3] we are elected!
in4150-python-template-node3-1  | [Node 3] Sending message to terminate the algorithm!
in4150-python-template-node0-1  | [Node 0] Stopping algorithm
in4150-python-template-node1-1  | [Node 1] Stopping algorithm
in4150-python-template-node2-1  | [Node 2] Stopping algorithm
in4150-python-template-node3-1  | [Node 3] Stopping algorithm
```

## Local Examples

The expected output is consistent with running through docker-compose.

### Echo Algorithm

```bash
python src/run.py 0 topologies/echo.yaml echo &
python src/run.py 1 topologies/echo.yaml echo &
```

### Ring Election Algorithm

```bash
python src/run.py 0 topologies/election.yaml election &
python src/run.py 1 topologies/election.yaml election &
python src/run.py 2 topologies/election.yaml election &
python src/run.py 3 topologies/election.yaml election &
```

Make use of these commands to execute the respective algorithms locally.

## Acknowledgements
Special thanks to Bart Cox.