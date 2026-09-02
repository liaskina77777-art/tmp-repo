import socket
import zlib
import random
import hashlib
import time
from typing import Dict, Tuple, Optional
from dataclasses import dataclass
import math

@dataclass
class GameSession:
    ip: str
    seed: int
    secret_number: int
    lower_bound: int
    upper_bound: int
    attempts_left: int
    last_activity: float
    expected_seq: int = 0

class GGTPServer:
    def __init__(self, host='127.0.0.1', port=8888, timeout=30.0):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.sessions: Dict[str, GameSession] = {}
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.settimeout(0.1)  # Non-blocking for manual timeout checking
        self.sock.bind((host, port))
        
    def crc32_ip(self, ip: str) -> int:
        return zlib.crc32(ip.encode()) & 0xffffffff
    
    def generate_game(self, ip: str) -> Tuple[int, int, int]:
        seed = self.crc32_ip(ip)
        random.seed(seed)
        upper_bound = random.randint(100, 1000)
        lower_bound = 1
        secret = random.randint(lower_bound, upper_bound)
        max_attempts = math.ceil(math.log2(upper_bound - lower_bound + 1))
        return seed, secret, lower_bound, upper_bound, max_attempts
    
    def generate_win_key(self, ip: str, number: int) -> str:
        data = f"{ip}:{number}".encode()
        return hashlib.sha256(data).hexdigest()
    
    def handle_helo(self, data: str, addr: Tuple[str, int]) -> Optional[str]:
        parts = data.split()
        if len(parts) >= 2:
            try:
                client_timeout = float(parts[1])
            except ValueError:
                client_timeout = 5.0
        else:
            client_timeout = 5.0
            
        ip = addr[0]
        
        if ip in self.sessions:
            session = self.sessions[ip]
            return f"WLCM {session.lower_bound} {session.upper_bound}"
        
        seed, secret, lower, upper, max_attempts = self.generate_game(ip)
        self.sessions[ip] = GameSession(
            ip=ip, seed=seed, secret_number=secret,
            lower_bound=lower, upper_bound=upper,
            attempts_left=max_attempts, last_activity=time.time()
        )
        print(f"New game for {ip}: range [{lower}, {upper}], secret={secret}, attempts={max_attempts}")
        return f"WLCM {lower} {upper}"
    
    def handle_gues(self, data: str, addr: Tuple[str, int]) -> Optional[str]:
        ip = addr[0]
        
        if ip not in self.sessions:
            return None
        
        session = self.sessions[ip]
        session.last_activity = time.time()
        
        parts = data.split()
        if len(parts) != 2:
            return "FAIL Invalid format"
        
        try:
            guess = int(parts[1])
        except ValueError:
            return "FAIL Invalid number"
        
        session.attempts_left -= 1
        
        if guess == session.secret_number:
            key = self.generate_win_key(ip, session.secret_number)
            del self.sessions[ip]
            return f"BING {key}"
        elif guess < session.secret_number:
            if session.attempts_left <= 0:
                del self.sessions[ip]
                return "FAIL"
            return "MORE"
        else:
            if session.attempts_left <= 0:
                del self.sessions[ip]
                return "FAIL"
            return "LESS"
    
    def cleanup_stale_sessions(self):
        current_time = time.time()
        stale_ips = [ip for ip, session in self.sessions.items() 
                    if current_time - session.last_activity > self.timeout]
        for ip in stale_ips:
            print(f"Cleaning stale session for {ip}")
            del self.sessions[ip]
    
    def run(self):
        print(f"GGTP Server running on {self.host}:{self.port}")
        
        while True:
            try:
                data, addr = self.sock.recvfrom(4096)
                message = data.decode('utf-8').strip()
                print(f"Received from {addr}: {message}")
                
                response = None
                if message.startswith("HELO"):
                    response = self.handle_helo(message, addr)
                elif message.startswith("GUES"):
                    response = self.handle_gues(message, addr)
                else:
                    response = "FAIL Unknown command"
                
                if response:
                    self.sock.sendto(response.encode(), addr)
                    print(f"Sent to {addr}: {response}")
                    
            except socket.timeout:
                pass
            except Exception as e:
                print(f"Error: {e}")
            
            self.cleanup_stale_sessions()

if __name__ == "__main__":
    server = GGTPServer()
    server.run()
