import tkinter as tk
from tkinter import messagebox, scrolledtext
import asyncio
import websockets
import json
from TikTokLive import TikTokLiveClient
from TikTokLive.events import ConnectEvent, LikeEvent, GiftEvent
import threading
import queue
import random

# Global variables
client: TikTokLiveClient = None
enemy_spawn_likes = 20
boss_spawn_likes = 1000
item_spawn_likes = 100

# Variables to track likes
like_count = 0
last_enemy_like = 0
last_boss_like = 0
last_item_like = 0  # Track last item spawn for 100 likes

# Lists of monsters, bosses, and items
monsters = [
    "AcidLarva", "BeetleGuard", "Beetle", "Bell", "Bison", "FlyingVermin",
    "Golem", "Jelly", "Lemurian", "Vermin", "Wisp"
]
bosses = [
    "BeetleQueen", "ClayBoss", "ImpBoss", "MagmaWorm", "Titan", "Vagrant"
]
items = ["Tier1", "Tier2", "Tier3", "Tier4"]  # List of items

# Weights for item tiers
item_weights = {
    "Tier1": 0.5,
    "Tier2": 0.25,
    "Tier3": 0.125,
    "Tier4": 0.125
}

# Dictionary to map gift names to their corresponding event names
gift_monster_event_mapping = {
    "Rose": "Beetle",
    "Gamepad": "BeetleGuard",
    "Cap": "BeetleQueen",
    "Butterfly": "Titan",
    "Goggles": "TitanGold",
    "Boxing Gloves": "MagmaWorm",
    "Money Gun": "ElectricWorm",
    "Galaxy": "MiniVoidRaidCrabMasterPhase1",
}

gift_item_event_mapping = {
    "Finger heart": "Tier1",
    "Doughnut": "Tier2",
    "Game Controller": "Tier3",
    "Hand Heart": "Tier4"
}

# Queue for managing spawn actions
spawn_queue = queue.Queue()

# Function to start the TikTok client
def start_client(username):
    global client
    client = TikTokLiveClient(unique_id=f"@{username}")
    client.add_listener(ConnectEvent, on_connect)
    client.add_listener(LikeEvent, on_like)
    client.add_listener(GiftEvent, on_gift)
    client.run()

# Function to start the WebSocket server
def start_websocket_server():
    # Create a new event loop for this thread
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    server = websockets.serve(websocket_handler, "localhost", 6789)

    # Run the WebSocket server within this event loop
    loop.run_until_complete(server)
    loop.run_forever()

# Keep track of connected clients
connected_clients = set()

# WebSocket server handler
async def websocket_handler(websocket, path):
    # Register the client
    connected_clients.add(websocket)
    try:
        while True:
            # Collect all events in the queue
            batched_events = []
            while not spawn_queue.empty():
                batched_events.append(json.loads(spawn_queue.get()))

            if batched_events:
                # Send all events to every connected client
                message = json.dumps(batched_events)
                await asyncio.gather(*[client.send(message) for client in connected_clients])

            await asyncio.sleep(0.1)  # Wait 0.1 seconds before checking again
    except:
        # Handle client disconnect or errors
        pass
    finally:
        # Unregister the client when disconnected
        connected_clients.remove(websocket)

# Listen to events
async def on_connect(event: ConnectEvent):
    log_message(f"Connected to @{event.unique_id} (Room ID: {client.room_id})")

async def on_like(event: LikeEvent) -> None:
    global like_count, last_enemy_like, last_boss_like, last_item_like

    # Increment like count
    like_count += event.count
    log_message(f"Received {event.count} likes! Total: {like_count}")

    # Send the total like count to WebSocket clients
    like_message = json.dumps({"event": "like_count", "data": like_count, "sender": "chat"})
    enqueue_spawn(like_message)

    # Check if enough likes have passed since the last enemy spawn
    if like_count - last_enemy_like >= enemy_spawn_likes:
        last_enemy_like = like_count
        monster_name = random.choice(monsters)
        spawn_message = json.dumps({"event": "spawn_enemy", "monster": monster_name, "sender": "chat"})
        enqueue_spawn(spawn_message)

    # Check if enough likes have passed since the last boss spawn
    if like_count - last_boss_like >= boss_spawn_likes:
        last_boss_like = like_count
        boss_name = random.choice(bosses)
        boss_message = json.dumps({"event": "spawn_boss", "monster": boss_name, "sender": "chat"})
        enqueue_spawn(boss_message)

    # Check if enough likes have passed to spawn an item (every 100 likes)
    if like_count - last_item_like >= item_spawn_likes:
        last_item_like = like_count
        item_name = weighted_random_choice(item_weights)
        item_message = json.dumps({"event": "spawn_item", "item": item_name, "sender": "chat"})
        enqueue_spawn(item_message)

async def on_gift(event: GiftEvent):
    gift_name = event.gift.name
    gift_count = event.combo_count

    log_message(f"{event.user.unique_id} sent {gift_count} \"{gift_name}\"(s)")
    if gift_name in gift_monster_event_mapping:
        for _ in range(gift_count):
            gift_message = json.dumps({"event": "spawn_enemy", "monster": gift_monster_event_mapping[gift_name], "sender": event.user.unique_id})
            enqueue_spawn(gift_message)
    elif gift_name in gift_item_event_mapping:
        for _ in range(gift_count):
            gift_message = json.dumps({"event": "spawn_item", "item": gift_item_event_mapping[gift_name], "sender": event.user.unique_id})
            enqueue_spawn(gift_message)

# Function to select a weighted random item
def weighted_random_choice(weights):
    items, probs = zip(*weights.items())
    return random.choices(items, weights=probs, k=1)[0]

# Function to enqueue spawn actions
def enqueue_spawn(event_message):
    log_message(f"Enqueuing event: {event_message}")  # Print the event message
    spawn_queue.put(event_message)

# Function to start the application
def start_application():
    # Start the TikTokLive client in a separate thread
    client_thread = threading.Thread(target=start_client, args=(username_entry.get(),))
    client_thread.daemon = True
    client_thread.start()

    # Start the WebSocket server in a separate thread
    websocket_thread = threading.Thread(target=start_websocket_server)
    websocket_thread.daemon = True
    websocket_thread.start()

# Function to handle the start button click
def on_start_button_click():
    global enemy_spawn_likes, boss_spawn_likes, item_spawn_likes
    try:
        enemy_spawn_likes = int(enemy_likes_entry.get())
        boss_spawn_likes = int(boss_likes_entry.get())
        item_spawn_likes = int(item_likes_entry.get())
        start_application()
        messagebox.showinfo("Info", "Application started successfully!")
    except ValueError:
        messagebox.showerror("Error", "Please enter valid integers for the number of likes.")

# Function to log messages in the text widget
def log_message(message):
    log_text.config(state=tk.NORMAL)  # Enable editing
    log_text.insert(tk.END, message + "\n")  # Insert the message at the end
    log_text.config(state=tk.DISABLED)  # Disable editing
    log_text.see(tk.END)  # Scroll to the end

# GUI setup
root = tk.Tk()
root.title("TikTok Live Stream Settings")

# Create and place the labels and entry fields
tk.Label(root, text="TikTok Username:").grid(row=0, column=0, padx=10, pady=5)
username_entry = tk.Entry(root)
username_entry.grid(row=0, column=1, padx=10, pady=5)

tk.Label(root, text="Likes for Enemy Spawn:").grid(row=1, column=0, padx=10, pady=5)
enemy_likes_entry = tk.Entry(root)
enemy_likes_entry.grid(row=1, column=1, padx=10, pady=5)

tk.Label(root, text="Likes for Boss Spawn:").grid(row=2, column=0, padx=10, pady=5)
boss_likes_entry = tk.Entry(root)
boss_likes_entry.grid(row=2, column=1, padx=10, pady=5)

tk.Label(root, text="Likes for Item Spawn:").grid(row=3, column=0, padx=10, pady=5)
item_likes_entry = tk.Entry(root)
item_likes_entry.grid(row=3, column=1, padx=10, pady=5)

start_button = tk.Button(root, text="Start", command=on_start_button_click)
start_button.grid(row=4, column=0, columnspan=2, padx=10, pady=10)

# Add the log area using a ScrolledText widget
log_text = scrolledtext.ScrolledText(root, wrap=tk.WORD, width=40, height=10, state=tk.DISABLED)
log_text.grid(row=5, column=0, columnspan=2, padx=10, pady=10)

# Start the main loop
root.mainloop()
