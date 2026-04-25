import zlib
import asyncio
import struct
import random
import hashlib
import time
import math
from typing import Dict, Optional, Tuple
from dataclasses import dataclass

@dataclass
class GameSession:
    ip: str
    seed: int
    secret_number: int
    lower_bound: int
    upper_bound: int
    attempts_left: int
    last_activity: float
    timeout_task: Optional[asyncio.Task] = None

class GGTPAsyncServer:
    def __init__(self, host='127.0.0.1', port=8888, session_timeout=30.0):
        self.host = host
        self.port = port
        self.session_timeout = session_timeout
        self.sessions: Dict[str, GameSession] = {}
        self.transport = None
        
    def crc32_ip(self, ip: str) -> int:
        return zlib.crc32(ip.encode()) & 0xffffffff
    
    def generate_game(self, ip: str):
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
    
    async def timeout_session(self, ip: str):
        await asyncio.sleep(self.session_timeout)
        if ip in self.sessions:
            print(f"Session timeout for {ip}")
            del self.sessions[ip]
    
    async def handle_helo(self, data: str, addr: Tuple[str, int]) -> Optional[str]:
        parts = data.split()
        client_timeout = float(parts[1]) if len(parts) >= 2 else 5.0
        
        ip = addr[0]
        
        if ip in self.sessions:
            session = self.sessions[ip]
            if session.timeout_task:
                session.timeout_task.cancel()
            session.timeout_task = asyncio.create_task(self.timeout_session(ip))
            return f"WLCM {session.lower_bound} {session.upper_bound}"
        
        seed, secret, lower, upper, max_attempts = self.generate_game(ip)
        session = GameSession(
            ip=ip, seed=seed, secret_number=secret,
            lower_bound=lower, upper_bound=upper,
            attempts_left=max_attempts, last_activity=time.time()
        )
        session.timeout_task = asyncio.create_task(self.timeout_session(ip))
        self.sessions[ip] = session
        
        print(f"New game for {ip}: range [{lower}, {upper}], secret={secret}, attempts={max_attempts}")
        return f"WLCM {lower} {upper}"
    
    async def handle_gues(self, data: str, addr: Tuple[str, int]) -> Optional[str]:
        ip = addr[0]
        
        if ip not in self.sessions:
            return None
        
        session = self.sessions[ip]
        session.last_activity = time.time()
        
        if session.timeout_task:
            session.timeout_task.cancel()
            session.timeout_task = asyncio.create_task(self.timeout_session(ip))
        
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
            if session.timeout_task:
                session.timeout_task.cancel()
            del self.sessions[ip]
            return f"BING {key}"
        elif guess < session.secret_number:
            if session.attempts_left <= 0:
                if session.timeout_task:
                    session.timeout_task.cancel()
                del self.sessions[ip]
                return "FAIL"
            return "MORE"
        else:
            if session.attempts_left <= 0:
                if session.timeout_task:
                    session.timeout_task.cancel()
                del self.sessions[ip]
                return "FAIL"
            return "LESS"
    
    def connection_made(self, transport):
        self.transport = transport
    
    def datagram_received(self, data, addr):
        asyncio.create_task(self.process_datagram(data, addr))
    
    async def process_datagram(self, data: bytes, addr: Tuple[str, int]):
        try:
            message = data.decode('utf-8').strip()
            print(f"Received from {addr}: {message}")
            
            response = None
            if message.startswith("HELO"):
                response = await self.handle_helo(message, addr)
            elif message.startswith("GUES"):
                response = await self.handle_gues(message, addr)
            else:
                response = "FAIL Unknown command"
            
            if response and self.transport:
                self.transport.sendto(response.encode(), addr)
                print(f"Sent to {addr}: {response}")
                
        except Exception as e:
            print(f"Error processing datagram: {e}")
    
    def error_received(self, exc):
        print(f"Error received: {exc}")
    
    async def start(self):
        loop = asyncio.get_running_loop()
        transport, protocol = await loop.create_datagram_endpoint(
            lambda: self,
            local_addr=(self.host, self.port)
        )
        print(f"GGTP Async Server running on {self.host}:{self.port}")
        return transport

async def main():
    server = GGTPAsyncServer()
    transport = await server.start()
    
    try:
        await asyncio.Future()  # Run forever
    except KeyboardInterrupt:
        print("\nShutting down server...")
        transport.close()

if __name__ == "__main__":
    asyncio.run(main())
