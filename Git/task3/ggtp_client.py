import socket
import time
import sys
import math
from typing import Optional, Tuple

class GGTPClient:
    def __init__(self, host='127.0.0.1', port=8888, timeout=5.0):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.settimeout(timeout)
        self.game_active = False
        self.lower_bound = None
        self.upper_bound = None
        self.max_attempts = None
        self.attempts = 0
        
    def send_with_retry(self, message: str, retries: int = 3) -> Optional[str]:
        for attempt in range(retries):
            try:
                self.sock.sendto(message.encode(), (self.host, self.port))
                data, _ = self.sock.recvfrom(4096)
                return data.decode().strip()
            except socket.timeout:
                print(f"Timeout, retry {attempt + 1}/{retries}")
                if attempt == retries - 1:
                    return None
        return None
    
    def start_game(self) -> bool:
        helo_msg = f"HELO {self.timeout}"
        response = self.send_with_retry(helo_msg)
        
        if not response:
            print("Failed to start game: No response from server")
            return False
        
        if response.startswith("WLCM"):
            parts = response.split()
            if len(parts) == 3:
                self.lower_bound = int(parts[1])
                self.upper_bound = int(parts[2])
                range_size = self.upper_bound - self.lower_bound + 1
                self.max_attempts = math.ceil(math.log2(range_size))
                self.game_active = True
                print(f"Game started! Range: [{self.lower_bound}, {self.upper_bound}]")
                print(f"Maximum attempts: {self.max_attempts}")
                return True
        
        print(f"Unexpected response: {response}")
        return False
    
    def make_guess(self, guess: int) -> Tuple[bool, Optional[str]]:
        if not self.game_active:
            print("Game not active")
            return False, None
        
        if guess < self.lower_bound or guess > self.upper_bound:
            print(f"Guess must be between {self.lower_bound} and {self.upper_bound}")
            return False, None
        
        self.attempts += 1
        gues_msg = f"GUES {guess}"
        response = self.send_with_retry(gues_msg)
        
        if not response:
            print("No response from server")
            return False, None
        
        if response == "MORE":
            self.lower_bound = guess + 1
            print(f"Too low! New range: [{self.lower_bound}, {self.upper_bound}]")
            print(f"Attempts left: {self.max_attempts - self.attempts}")
            return False, None
        elif response == "LESS":
            self.upper_bound = guess - 1
            print(f"Too high! New range: [{self.lower_bound}, {self.upper_bound}]")
            print(f"Attempts left: {self.max_attempts - self.attempts}")
            return False, None
        elif response.startswith("BING"):
            key = response.split()[1] if len(response.split()) > 1 else ""
            print(f"Correct! You won! Key: {key}")
            self.game_active = False
            return True, key
        elif response == "FAIL":
            print("Game over! You lost.")
            self.game_active = False
            return False, None
        else:
            print(f"Unexpected response: {response}")
            return False, None
    
    def play(self):
        print("=== GGTP Guessing Game ===")
        
        if not self.start_game():
            return
        
        while self.game_active:
            try:
                guess_str = input(f"\nEnter your guess ({self.lower_bound}-{self.upper_bound}): ")
                if guess_str.lower() == 'quit':
                    print("Game abandoned")
                    break
                
                guess = int(guess_str)
                won, _ = self.make_guess(guess)
                
                if won or not self.game_active:
                    break
                    
            except ValueError:
                print("Please enter a valid number")
            except KeyboardInterrupt:
                print("\nGame interrupted")
                break
        
        self.sock.close()

if __name__ == "__main__":
    timeout = 5.0
    if len(sys.argv) > 1:
        try:
            timeout = float(sys.argv[1])
        except ValueError:
            pass
    
    client = GGTPClient(timeout=timeout)
    client.play()
