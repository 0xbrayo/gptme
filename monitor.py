import time
import random
import psutil
import sys
from datetime import datetime

def get_system_stats():
    cpu = psutil.cpu_percent(interval=1)
    mem = psutil.virtual_memory().percent
    return f"CPU: {cpu}% | Memory: {mem}%"

def generate_ascii_pattern(t):
    patterns = [
        "▁▂▃▄▅▆▇█",
        "←↖↑↗→↘↓↙",
        "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏",
        "◐◓◑◒"
    ]
    pattern = patterns[t % len(patterns)]
    return pattern[t % len(pattern)]

def random_event():
    events = [
        "🚀 Processing batch job",
        "📊 Analyzing data",
        "🔄 Syncing resources",
        "🔍 Running diagnostics",
        "📡 Network activity detected",
    ]
    return random.choice(events)

def main():
    t = 0
    while True:
        sys.stdout.write("\033[2J\033[H")  # Clear screen
        
        # Current time
        print(f"🕒 {datetime.now().strftime('%H:%M:%S')}")
        print("-" * 40)
        
        # System stats
        print(get_system_stats())
        print("-" * 40)
        
        # ASCII animation
        print(f"Status: {generate_ascii_pattern(t)}")
        
        # Random events
        if t % 3 == 0:
            print(f"\nEvent: {random_event()}")
        
        # Progress bar
        width = 30
        progress = t % width
        bar = "█" * progress + "▒" * (width - progress)
        print(f"\nProgress: [{bar}] {(progress/width)*100:.1f}%")
        
        sys.stdout.flush()
        time.sleep(1)
        t += 1

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nMonitoring stopped.")
