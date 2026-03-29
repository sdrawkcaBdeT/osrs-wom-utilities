import socket
import time
import threading
import json
import random

# --- CONFIGURATION ---
HOST = '127.0.0.1'
PORT = 5005
TICK_RATE = 0.600  # 600ms OSRS tick
DROP_RATE = 5.0    # 5 seconds between mock kills

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

def send_payload(payload):
    try:
        message = json.dumps(payload).encode('utf-8')
        sock.sendto(message, (HOST, PORT))
        print(f"[TX] {payload}")
    except Exception as e:
        print(f"[Error] Failed to send: {e}")

def tick_daemon():
    print("[Thread] Tick Heartbeat Started")
    tick_count = 1000
    while True:
        payload = {
            "event": "tick_heartbeat",
            "tick": tick_count,
            "state": "idle" 
        }
        send_payload(payload)
        tick_count += 1
        time.sleep(TICK_RATE)

def economy_daemon():
    print("[Thread] Economy Drops Started")
    # Wait a moment for the matrix to initialize before dropping gold
    time.sleep(2) 
    
    while True:
        # 80% chance for a standard base drop, 20% chance for a rune/rare drop
        is_rare = random.random() > 0.8
        
        if is_rare:
            gp_val = random.randint(65000, 105000)
        else:
            gp_val = random.randint(18000, 26000)
            
        payload = {
            "event": "net_profit_delta",
            "value": gp_val
        }
        send_payload(payload)
        time.sleep(DROP_RATE)

if __name__ == "__main__":
    print(f"--- BBD UDP Mock Broadcaster ---")
    print(f"Targeting {HOST}:{PORT}")
    
    t_tick = threading.Thread(target=tick_daemon, daemon=True)
    t_econ = threading.Thread(target=economy_daemon, daemon=True)
    
    t_tick.start()
    t_econ.start()
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down broadcaster.")