import time
from collections import deque

BOT_START_TIME: float = time.monotonic()
maintenance_mode: bool = False
security_events: deque = deque(maxlen=100)
