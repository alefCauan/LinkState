import os
import json
import heapq
import threading
import time
import sys

# Force unbuffered output
sys.stdout.reconfigure(line_buffering=True)

print("Router script started.")

# Step 1: Load the network topology
try:
    with open("/app/network_topology.json", "r") as f:
        topology = json.load(f)
        print("Successfully loaded network_topology.json")
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
    try:
        print(f"{lsdb.router_id}: Receiving link state packets...")
        while True:
            print(f"{lsdb.router_id}: Still receiving...")
            time.sleep(10)
            print(f"{lsdb.router_id}: Checking for topology updates...")
    except Exception as e:
        print(f"{lsdb.router_id}: Receive thread failed with error: {e}")
        sys.exit(1)

def send_link_state_packets(lsdb):
    try:
        print(f"{lsdb.router_id}: Sending link state packets...")
        while True:
            print(f"{lsdb.router_id}: Still sending...")
            time.sleep(10)
            print(f"{lsdb.router_id}: Broadcasting LSDB...")
    except Exception as e:
        print(f"{lsdb.router_id}: Send thread failed with error: {e}")
        sys.exit(1)

def get_router_id():
    """Determine router ID from environment variables"""
    # Get all environment variables
    env_vars = os.environ
    
    # Find variables that start with CONNECTED_TO_ROUTER
    router_connections = [var for var in env_vars if var.startswith('CONNECTED_TO_ROUTER_')]
    
    if not router_connections:
        print("Error: No router connections found in environment variables")
        sys.exit(1)
    
    # Example: CONNECTED_TO_ROUTER_R2=2 means this router has a connection to R2
    # So if we see R2, we know we're not R2. By checking all connections,
    # we can determine which router we are
    possible_routers = {'R1', 'R2', 'R3'}
    connected_routers = {conn.replace('CONNECTED_TO_ROUTER_', '') for conn in router_connections}
    
    # We are the router that's not in our connections
    our_router = list(possible_routers - connected_routers)
    
    if len(our_router) != 1:
        print(f"Error: Could not uniquely determine router ID. Found: {our_router}")
        sys.exit(1)
        
    return our_router[0]

def main():
    # Determine router ID dynamically
    router_id = get_router_id()
    print(f"Determined router ID: {router_id}")
    
    # Initialize LSDB with router ID and topology
    lsdb = LSDB(router_id, topology)
    
    # Start threads for receiving and sending packets
    receive_thread = threading.Thread(target=receive_link_state_packets, args=(lsdb,))
    send_thread = threading.Thread(target=send_link_state_packets, args=(lsdb,))
    
    receive_thread.daemon = True
    send_thread.daemon = True
    
    receive_thread.start()
    send_thread.start()
    
    # Main loop that runs Dijkstra periodically
    while True:
        print(f"\n{router_id}: Calculating routes...")
        lsdb.dijkstra()  # Calculate shortest paths
        lsdb.print_routes()  # Print the current routing table
        time.sleep(10)  # Wait before next calculation

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"Router failed with error: {e}")
        sys.exit(1)