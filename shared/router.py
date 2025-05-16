import time
import psutil
import socket
import threading
import json
import os
import subprocess
import ipaddress
import datetime


def formated_printf(string: str):
    """
    Prints a message with standardized format including container name.
    """
    try:
        container_name = os.getenv("CONTAINER_NAME")
        with print_lock:
            print(f"[{container_name}] {string}")
    except NameError:
        print(string)

class LSDB:
    """
    Represents the Link State Database (LSDB), responsible for storing information received via 
    Link State Advertisement (LSA) and calculating the best network paths using Dijkstra's algorithm.
    
    Attributes:
        _table (dict): Database storing router information received via LSA
        _router_id (str): Unique identifier for this router
        _routing_table (dict): Maintains destination routers and next hops to reach them
        _neighbors_ip (dict): Dictionary mapping neighbor IDs to their IP addresses
        _start_time (float): Timestamp when the LSDB was initialized
        _router_count (int): Count of known routers in the network
    """

    def __init__(self, router_id: str, neighbors_ip: dict[str, str]):
        """
        Initializes a new LSDB instance.

        Args: 
            router_id (str): Unique identifier for the router
            neighbors_ip (dict[str, str]): Dictionary where keys are neighbor IDs and values are their IP addresses
        """
        self._router_id = router_id
        self._neighbors_ip = neighbors_ip
        self._table = {}  # Stores LSA received information
        self._routing_table = {}  # Maps destinations to next hops
        self._start_time = time.time()
        self._router_count = 0

    def create_entry(self, sequence_number: int, timestamp: float, addresses: list[str], links: dict[str, int]) -> dict:
        """
        Creates a new entry in the LSDB table based on packet information.

        Args:
            sequence_number (int): LSA sequence number
            timestamp (float): Packet creation time
            addresses (list[str]): List of all interface IP addresses
            links (dict[str, int]): Dictionary where keys are neighbor IDs and values are link costs

        Returns: 
            dict: Dictionary containing the entry data
        """
        return {
            "sequence_number": sequence_number,
            "timestamp": timestamp,
            "addresses": addresses,
            "links": links,
        }

    def update(self, packet: dict) -> bool:
        """
        Updates the routing table upon receiving a valid LSA packet.

        Args:
            packet (dict): LSA packet in dictionary format

        Returns:
            bool: True if the table was updated, False otherwise
        """
        router_id = packet["router_id"]
        sequence_number = packet["sequence_number"]
        entry = self._table.get(router_id)

        # Packet is invalid if we already have an equal or newer entry
        if entry and sequence_number <= entry["sequence_number"]:
            return False

        # Create new table entry
        self._table[router_id] = self.create_entry(
            sequence_number, packet["timestamp"], packet["addresses"], packet["links"])

        # Check if network has converged (we know routes to all known routers)
        self._router_count = len(self._table.keys())
        self.recalculate_routes(packet["links"].keys())

        return True

    def dijkstra(self) -> dict:
        """
        Calculates the shortest path between this router and all other known routers.

        Returns:
            dict: Dictionary where keys are destination routers and values are previous routers
        """
        distances = {}
        paths = {}
        visited = {}

        # Initialize dictionaries
        for router in self._table.keys():
            distances[router] = float('inf')
            paths[router] = None

        distances[self._router_id] = 0

        while len(visited) < len(self._table):
            current_router = None
            min_distance = float('inf')
            
            # Find the unvisited router with smallest distance
            for node, distance in distances.items():
                if node not in visited and distance < min_distance:
                    current_router = node
                    min_distance = distance

            if current_router is None:
                break

            visited[current_router] = True
            neighbors = self._table[current_router]["links"]

            # Update distances for neighboring routers
            for neighbor, cost in neighbors.items():
                if neighbor not in visited:
                    total_cost = cost + distances[current_router]
                    if total_cost < distances[neighbor]:
                        distances[neighbor] = total_cost
                        paths[neighbor] = current_router

        return paths

    def update_next_hop(self, paths: dict):
        """
        Traverses the shortest paths to determine the next hop for each router from this router.

        Args:
            paths (dict): Dictionary where keys are destination routers and values are previous routers
        """
        for destination in paths.keys():
            if destination != self._router_id:
                hop = destination
                while hop is not None and paths[hop] != self._router_id:
                    hop = paths[hop]
                self._routing_table[destination] = hop

        self._routing_table = dict(sorted(self._routing_table.items()))

    def update_routes(self):
        """
        Updates the routing table based on next hops found by update_next_hop().
        """
        for dest_router, gateway_router in list(self._routing_table.items()):
            if dest_router != self._router_id:
                if gateway_router not in self._neighbors_ip:
                    formated_printf(
                        f"[LSDB] Ignoring route to {dest_router} via {gateway_router}: gateway not yet known")
                else:
                    # Update route associating all neighbor IPs to the next hop
                    for dest_ip in self._table[dest_router]["addresses"]:
                        gateway_ip = self._neighbors_ip[gateway_router]

                        command = ["ip", "route", "replace",
                                 dest_ip, "via", gateway_ip]
                        try:
                            subprocess.run(command, check=True)
                            formated_printf(
                                f"Route added: {dest_ip} -> {gateway_ip} [{gateway_router}]")
                        except subprocess.CalledProcessError as e:
                            formated_printf(
                                f"[ERROR] Failed to add route: [{command}] -> [{e}] ({self._router_id} -> {gateway_router})")

    def recalculate_routes(self, observed_routers: list[str]):
        """
        Recalculates routes using Dijkstra's algorithm and applies them to the routing table.

        Args:
            observed_routers (list[str]): List of observed routers
        """
        # Check for unknown routers in observed routers
        for neighbor in observed_routers:
            if neighbor not in self._table:
                formated_printf(f"[LSDB] Discovered new router: {neighbor}")
                self._table[neighbor] = self.create_entry(-1, 0, [], {})

        # Calculate shortest paths to each router
        paths = self.dijkstra()
        # Determine next hops for each path
        self.update_next_hop(paths)
        # Update routing table
        self.update_routes()

class HelloSender:
    """
    Class responsible for creating and periodically sending HELLO packets to neighbors in a network.
    
    Attributes:
        _router_id (str): Unique identifier for the router
        _interfaces (list[dict]): List of network interfaces
        _neighbors (dict): Dictionary of known neighbors
        _interval (int): Time interval between HELLO packets
        _PORT (int): UDP port for communication
    """

    def __init__(self, router_id: str, interfaces: list[dict[str, str]], neighbors: dict[str, str], interval: int = 10, PORT: int = 5000):
        """
        Initializes a new HelloSender instance.

        Args:
            router_id (str): Unique router identifier
            interfaces (list[dict[str, str]]): List of network interface dictionaries containing:
                - "address": Interface IP
                - "broadcast": Broadcast IP (if applicable)
            neighbors (dict[str, str]): Dictionary of known neighbors (key: neighbor ID, value: IP)
            interval (int, optional): Time interval between HELLO packets (default: 10)
            PORT (int, optional): UDP listening port (default: 5000)
        """
        self._router_id = router_id
        self._interfaces = interfaces
        self._neighbors = neighbors
        self._interval = interval
        self._PORT = PORT

    def create_packet(self, ip_address: str) -> dict:
        """
        Creates a HELLO packet.

        Args:
            ip_address (str): Local interface IP address

        Returns: 
            dict: Dictionary containing HELLO packet data
        """
        return {
            "type": "HELLO",
            "router_id": self._router_id,
            "timestamp": time.time(),
            "ip_address": ip_address,
            "known_neighbors": list(self._neighbors.keys()),
        }

    def send_to_all_neighbors(self):
        """
        Starts periodic broadcast of HELLO packets.
        """
        # Filter interfaces that have broadcast addresses
        interfaces = [item for item in self._interfaces if "broadcast" in item]

        sock = create_socket()
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

        while True:
            for interface_info in interfaces:
                ip_address = interface_info["address"]
                broadcast_ip = interface_info["broadcast"]

                packet = self.create_packet(ip_address)
                message = json.dumps(packet).encode("utf-8")

                try:
                    sock.sendto(message, (broadcast_ip, self._PORT))
                    formated_printf(f"HELLO packet sent to {broadcast_ip} [broadcast]")
                except Exception as e:
                    formated_printf(f"Error sending to {broadcast_ip}: {e}")

            time.sleep(self._interval)

    def start(self):
        """
        Starts the HelloSender operation:
        - Initializes a thread for broadcasting HELLO packets
        """
        sender_thread = threading.Thread(
            target=self.send_to_all_neighbors, daemon=True)
        sender_thread.start()

class LSASender:
    """
    Class responsible for creating, sending, and forwarding LSA (Link State Advertisement) packets.
    
    Attributes:
        _router_id (str): Unique router identifier
        _neighbors_ip (dict): Neighbor IDs mapped to IPs
        _neighbors_cost (dict): Neighbor IDs mapped to link costs
        _interval (int): Time interval between LSA packets
        _PORT (int): UDP port for communication
        _sequence_number (int): LSA sequence number
        _started (bool): Flag indicating if sender is active
        _lsdb (LSDB): Link State Database reference
        _interfaces (list): List of network interfaces
    """

    def __init__(self, router_id: str, neighbors_ip: dict[str, str], neighbors_cost: dict[str, int], 
                 interfaces: list[dict[str, str]], lsdb: LSDB, interval: int = 30, PORT: int = 5000):
        """
        Initializes a new LSASender instance.

        Args:
            router_id (str): Unique router identifier
            neighbors_ip (dict[str, str]): Neighbor IDs mapped to IPs
            neighbors_cost (dict[str, str]): Neighbor IDs mapped to link costs
            interfaces (list[dict[str, str]]): Network interfaces
            lsdb (LSDB): Link State Database reference
            interval (int, optional): Time between LSA packets (default: 30)
            PORT (int, optional): UDP port (default: 5000)
        """
        self._router_id = router_id
        self._neighbors_ip = neighbors_ip
        self._neighbors_cost = neighbors_cost
        self._interval = interval
        self._PORT = PORT
        self._sequence_number = 0
        self._started = False
        self._lsdb = lsdb
        self._interfaces = interfaces

    @property
    def neighbors_ip(self):
        return self._neighbors_ip

    @property
    def neighbors_cost(self):
        return self._neighbors_cost

    def create_packet(self) -> dict:
        """
        Creates an LSA packet.

        Returns: 
            dict: Dictionary containing LSA packet data
        """
        self._sequence_number += 1
        return {
            "type": "LSA",
            "router_id": self._router_id,
            "timestamp": time.time(),
            "addresses": [item["address"] for item in self._interfaces],
            "sequence_number": self._sequence_number,
            "links": {neighbor_id: cost for (neighbor_id, cost) in self._neighbors_cost.items()}
        }

    def send_to_neighbors(self):
        """
        Starts periodic sending of LSA packets to all direct neighbors.
        """
        sock = create_socket()
        while True:
            packet = self.create_packet()
            self._lsdb.update(packet)
            message = json.dumps(packet).encode("utf-8")

            for neighbor_id, ip in self._neighbors_ip.items():
                try:
                    sock.sendto(message, (ip, self._PORT))
                    formated_printf(f"LSA packet sent to {ip} [{neighbor_id}]")
                except Exception as e:
                    formated_printf(f"Error sending to [{neighbor_id}]: {e}")

            time.sleep(self._interval)

    def forward_to_neighbors(self, packet: dict, sender_ip: str):
        """
        Forwards received LSA packets to all neighbors except the original sender.

        Args: 
            packet (dict): LSA packet in dictionary format
            sender_ip (str): IP of the packet sender
        """
        sock = create_socket()
        message = json.dumps(packet).encode("utf-8")

        # Create list of neighbors to receive the packet (excluding sender)
        neighbors_list = [
            (neighbor_id, ip) for neighbor_id, ip in self._neighbors_ip.items() if ip != sender_ip]

        for neighbor_id, ip in neighbors_list:
            try:
                sock.sendto(message, (ip, self._PORT))
                formated_printf(f"LSA packet forwarded to {ip} [{neighbor_id}]")
            except Exception as e:
                formated_printf(f"Error forwarding to [{neighbor_id}]: {e}")

    def start(self):
        """
        Starts the LSASender operation if not already started.
        """
        if not self._started:
            self._started = True
            sender_thread = threading.Thread(
                target=self.send_to_neighbors, daemon=True)
            sender_thread.start()

class Router:
    """
    Represents a network router in a routing protocol simulation.
    
    Attributes:
        _router_id (str): Unique router identifier
        _interfaces (list): Network interfaces
        _PORT (int): UDP listening port
        _hello (HelloSender): HELLO packet sender
        _lsa (LSASender): LSA packet sender
        _lsdb (LSDB): Link State Database
        _BUFFER_SIZE (int): Receive buffer size
        _detected_neighbors (dict): Neighbors detected via HELLO
        _recognized_neighbors (dict): Bidirectionally recognized neighbors
        _neighbor_manager (NeighborManager): Neighbor management component
    """

    def __init__(self, router_id: str, PORT: int = 5000, BUFFER_SIZE: int = 4096):
        """
        Initializes a new Router instance.

        Args:
            router_id (str): Unique router identifier
            PORT (int, optional): UDP listening port (default: 5000)
            BUFFER_SIZE (int, optional): Maximum receive buffer size (default: 4096)
        """
        self._router_id = router_id
        self._interfaces = self.list_addresses()
        self._PORT = PORT
        self._BUFFER_SIZE = BUFFER_SIZE
        self._detected_neighbors = {}  # Neighbors detected via HELLO
        self._recognized_neighbors = {}  # Bidirectionally recognized neighbors
        
        self._hello = HelloSender(
            self._router_id, self._interfaces, self._detected_neighbors
        )

        self._lsdb = LSDB(router_id, self._recognized_neighbors)
        self._lsa = LSASender(
            self._router_id, self._recognized_neighbors,
            self._detected_neighbors, self._interfaces, self._lsdb
        )
        self._neighbor_manager = NeighborManager(
            self._router_id, self._lsa, self._lsdb
        )

    def receive_packets(self):
        """
        Starts listening for UDP packets on the defined port.
        Handles HELLO and LSA packets.
        """
        sock = create_socket()
        sock.bind(("", self._PORT))

        while True:
            try:
                data, address = sock.recvfrom(self._BUFFER_SIZE)
                message = data.decode("utf-8")
                packet = json.loads(message)
                packet_type = packet.get("type")
                sender_id = packet.get("router_id")
                
                if sender_id != self._router_id:
                    sender_ip = address[0]
                    formated_printf(
                        f"{packet_type} packet received from {sender_ip} [{sender_id}]")

                    if packet_type == "HELLO":
                        self._neighbor_manager.process_hello(
                            packet, sender_ip)
                    elif packet_type == "LSA":
                        self._neighbor_manager.process_lsa(
                            packet, sender_ip)

            except Exception as e:
                formated_printf(f"Error receiving packet: {e}")

    def list_addresses(self) -> list[dict]:
        """
        Lists IP addresses of the system's network interfaces.

        Returns: 
            list[dict]: List of interface dictionaries with IP addresses 
                       (and broadcast if applicable). 192.x.x.x addresses
                       are treated as /24 networks.
        """
        interfaces = psutil.net_if_addrs()
        interfaces_list = []
        for interface, addresses in interfaces.items():
            if interface.startswith("eth"):
                for address in addresses:
                    if address.family == socket.AF_INET:
                        if address.address.startswith("192"):
                            ip = ipaddress.ip_address(address.address)
                            network = ipaddress.IPv4Network(
                                f"{ip}/24", strict=False)

                            interfaces_list.append(
                                {"address": f"{network.network_address}/24"})
                        else:
                            interfaces_list.append(
                                {"address": address.address,
                                 "broadcast": address.broadcast}
                            )
        return interfaces_list

    def start(self):
        """
        Starts router operation:
        - Initializes packet listening thread
        - Starts periodic HELLO packet sending
        - Maintains process with infinite loop
        """
        receiver_thread = threading.Thread(
            target=self.receive_packets, daemon=True)
        receiver_thread.start()

        self._hello.start()

        failure_thread = threading.Thread(
            target=self._neighbor_manager.check_failures, daemon=True)
        failure_thread.start()

        while True:
            time.sleep(1)

class NeighborManager:
    """
    Class responsible for processing HELLO and LSA packets and managing router neighbors.
    
    Attributes:
        _router_id (str): Unique router identifier
        _lsa (LSASender): LSA packet sender reference
        _lsdb (LSDB): Link State Database reference
        _detected_neighbors (dict): Neighbors detected via HELLO
        _recognized_neighbors (dict): Bidirectionally recognized neighbors
        _hello_timestamps (dict): Timestamps of last HELLO from neighbors
    """

    def __init__(self, router_id: str, lsa: LSASender, lsdb: LSDB):
        """
        Initializes a new NeighborManager instance.

        Args: 
            router_id (str): Unique router identifier
            lsa (LSASender): LSA packet sender reference
            lsdb (LSDB): Link State Database reference
        """
        self._router_id = router_id
        self._lsa = lsa
        self._lsdb = lsdb
        self._detected_neighbors = lsa.neighbors_cost
        self._recognized_neighbors = lsa.neighbors_ip
        self._hello_timestamps = {}

    def process_hello(self, packet: dict, sender_ip: str):
        """
        Processes a HELLO packet, recognizing direct neighbors and starting LSA
        transmission to them if applicable.

        Args: 
            packet (dict): HELLO packet in dictionary format
            sender_ip (str): IP of the sending router
        """
        sender_id = packet.get("router_id")
        self._detected_neighbors[sender_id] = self.get_cost(
            self._router_id, sender_id)
        neighbors = packet.get("known_neighbors")

        self._hello_timestamps[sender_id] = packet.get("timestamp")

        # If sender recognizes this router and we haven't registered it yet
        if (self._router_id in neighbors) and (sender_id not in self._recognized_neighbors):
            self._recognized_neighbors[sender_id] = sender_ip
            self._lsa.start()

    def process_lsa(self, packet: dict, sender_ip: str):
        """
        Processes an LSA packet, updating the LSDB and forwarding valid packets to neighbors.

        Args: 
            packet (dict): LSA packet in dictionary format
            sender_ip (str): IP of the sending router
        """
        valid_packet = self._lsdb.update(packet)
        if valid_packet:
            self._lsa.forward_to_neighbors(packet, sender_ip)

    def get_cost(self, router_id: str, neighbor_id: str) -> int:
        """
        Returns the link cost between this router and a neighbor from environment variables.

        Args:
            router_id (str): Unique router identifier
            neighbor_id (str): Unique neighbor identifier

        Returns:
            int: Link cost (defaults to 1 if not specified)
        """
        cost = os.getenv(f"CONNECTED_TO_ROUTER_{neighbor_id}")
        if cost is None:
            cost = 1
        return int(cost)

    def check_failures(self, hello_interval: int = 10, tolerance: int = 3):
        """
        Periodically checks if neighbors have stopped sending HELLO packets,
        detecting potential router failures.

        Args:
            hello_interval (int, optional): Expected time between HELLO packets (default: 10)
            tolerance (int, optional): Number of missed intervals before declaring inactive (default: 3)
        """
        while True:
            now = time.time()
            failed_routers = [
                router_id for router_id, timestamp in self._hello_timestamps.items() 
                if (now - timestamp) > (hello_interval * tolerance)
            ]

            for router_id in failed_routers:
                formated_printf(f"[FAILURE] Router {router_id} considered inactive")

                if router_id in self._detected_neighbors:
                    del self._detected_neighbors[router_id]

                if router_id in self._recognized_neighbors:
                    del self._recognized_neighbors[router_id]

                if router_id in self._lsdb._table:
                    del self._lsdb._table[router_id]

            self._lsdb.recalculate_routes(failed_routers)
            time.sleep(1)

def create_socket():
    """
    Creates and returns a UDP IPv4 socket.
    """
    return socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

if __name__ == "__main__":
    # Get router name from environment variable
    router_id = os.getenv("CONTAINER_NAME")
    if not router_id:
        raise ValueError("CONTAINER_NAME not defined in environment variables")

    # Print lock to prevent concurrent output
    print_lock = threading.Lock()

    # Start router operation
    router = Router(router_id)
    router.start()