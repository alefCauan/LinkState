# LinkState
This project implements a computer network simulation using Python and Docker, where routers implement the Link State Routing Algorithm.

## Overview

The network consists of multiple subnets, each containing:
- 2 hosts
- 1 router

Routers connect to each other in a random (partially connected) topology and implement the link state algorithm, maintaining:
- Link State Database (LSDB)
- Updated routing table based on Dijkstra's algorithm

## Key Features

- Multi-threaded routers with separate threads for:
    - Receiving link state packets
    - Transmitting link state packets
- Docker containerization for hosts and routers
- Dynamic routing table updates
- Random topology generation

## Technologies

- Python: Core network logic
- Docker: Network simulation
- Route command: Routing table maintenance
- Threading: Multi-threading for routers
- Dijkstra's algorithm: Pathfinding for routing table updates
- Link State Routing Algorithm: Core routing algorithm
- Socket programming: Communication between routers and hosts


## Project Status

Project developed for the Information Systems course at UFPI - Campus CSHNB.

## Video Demo

[Project demonstration available on YouTube](#)


