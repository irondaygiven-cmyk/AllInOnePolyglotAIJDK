#!/usr/bin/env python3
import sys
import json
import struct

def send_message(message):
    encoded = json.dumps(message).encode("utf-8")
    sys.stdout.buffer.write(struct.pack('I', len(encoded)))
    sys.stdout.buffer.write(encoded)
    sys.stdout.buffer.flush()

def read_message():
    raw_length = sys.stdin.buffer.read(4)
    if not raw_length:
        return None
    length = struct.unpack('I', raw_length)[0]
    return json.loads(sys.stdin.buffer.read(length).decode("utf-8"))

while True:
    msg = read_message()
    if msg is None:
        break

    if msg.get("action") == "executeJS":
        # This would normally forward to the Chrome Extension
        send_message({"status": "success", "result": "Command sent to active tab"})
    else:
        send_message({"status": "unknown_command"})
