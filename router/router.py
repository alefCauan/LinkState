import os
import json
import heapq
import threading
import time
import sys

# Force unbuffered output
sys.stdout.reconfigure(line_buffering=True)

print("Router script started.")  # Debug: Confirm script starts

# Step 1: Load the network topology
try:
    with open("/app/network_topology.json", "r") as f:
        topology = json.load(f)
        print("Successfully loaded network_topology.json")  # Debug
except FileNotFoundError:
    print("Error: network_topology.json not found in /app.")
    sys.exit(1)
except json.JSONDecodeError:
    print("Error: network_topology.json is not a valid JSON file.")
    sys.exit(1)

# Step 2: Initialize the LSDB
class LSDB:
    def __init__(self, router_id, topology):
        self.router_id = router_id
        self.graph = {}
        self.shortest_paths = {}
        self.costs = {}
        self.build_graph(topology)

    def build_graph(self, topology):
        for subnet in topology["subnets"]:
            router = subnet["router"]
            self.graph[router] = {}

        for edge in topology["edges"]:
            node1, node2, weight = edge["node1"], edge["node2"], edge["weight"]
            if node1.startswith("R") and node2.startswith("R"):
                self.graph[node1][node2] = weight
                self.graph[node2][node1] = weight

    def dijkstra(self):
        distances = {router: float("infinity") for router in self.graph}
        distances[self.router_id] = 0
        predecessors = {router: None for router in self.graph}
        pq = [(0, self.router_id)]
        visited = set()

        while pq:
            current_distance, current_router = heapq.heappop(pq)

            if current_router in visited:
                continue

            visited.add(current_router)

            for neighbor, weight in self.graph[current_router].items():
                distance = current_distance + weight

                if distance < distances[neighbor]:
                    distances[neighbor] = distance
                    predecessors[neighbor] = current_router
                    heapq.heappush(pq, (distance, neighbor))

        for router in self.graph:
            if router == self.router_id:
                continue
            path = []
            current = router
            while current is not None:
                path.append(current)
                current = predecessors[current]
            path.reverse()
            self.shortest_paths[router] = path
            self.costs[router] = distances[router]

    def print_routes(self):
        print(f"\nShortest paths from {self.router_id}:")
        for router, path in self.shortest_paths.items():
            cost = self.costs[router]
            print(f"To {router}: Path = {' -> '.join(path)}, Cost = {cost}")

# Step 3: Router logic with threading
def receive_link_state_packets(lsdb):
    print(f"{lsdb.router_id}: Receiving link state packets...")
    while True:
        print(f"{lsdb.router_id}: Still receiving...")  # Debug
        time.sleep(10)
        print(f"{lsdb.router_id}: Checking for topology updates...")

def send_link_state_packets(lsdb):
    print(f"{lsdb.router_id}: Sending link state packets...")
    while True:
        print(f"{lsdb.router_id}: Still sending...")  # Debug
        time.sleep(10)
        print(f"{lsdb.router_id}: Broadcasting LSDB...")

def main():

    while True:
        # Get router ID from the container name (e.g., "r1" -> "R1")
        router_id = os.getenv("HOSTNAME", "").upper()
        print(f"HOSTNAME from environment: {router_id}")  # Debug
        if not router_id:
            print("Warning: HOSTNAME environment variable not set.")
            possible_names = ["R1", "R2", "R3"]
            router_id = next((name for name in possible_names if name.lower() in os.getenv("HOSTNAME", "").lower()), None)
            if not router_id:
                print("Error: Router ID could not be determined.")
                sys.exit(1)
        if not router_id.startswith("R"):
            print("Error: Router ID not found or invalid.")
            sys.exit(1)

        print(f"Starting router {router_id}...")

        # Initialize the LSDB
        lsdb = LSDB(router_id, topology)
        print("LSDB initialized.")  # Debug

        # Run Dijkstra's algorithm to compute shortest paths
        lsdb.dijkstra()
        lsdb.print_routes()

        # Start threads for sending and receiving link state packets
        print("Starting threads...")  # Debug
        receive_thread = threading.Thread(target=receive_link_state_packets, args=(lsdb,))
        send_thread = threading.Thread(target=send_link_state_packets, args=(lsdb,))
        receive_thread.start()
        send_thread.start()

        print("Threads started.")  # Debug

        # Keep the main thread alive
        receive_thread.join()
        send_thread.join()
        print("Threads joined - this should not happen!")  # Debug: This line should never be reached

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"Router failed with error: {e}")
        sys.exit(1)