#!/usr/bin/env python3
import asyncio
import json
import websockets

async def simple_test():
    """Simple WebSocket connection test."""
    uri = "ws://localhost:3789"
    
    try:
        async with websockets.connect(uri) as websocket:
            print("✅ Connected to WebSocket")
            
            # Wait for initial message
            try:
                initial = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                print(f"📨 Initial message: {initial}")
            except asyncio.TimeoutError:
                print("⏰ No initial message received")
            
            # Send a simple query
            message = {
                "command": "agent_query",
                "query": "What is the current time?"
            }
            
            print(f"📤 Sending: {json.dumps(message)}")
            await websocket.send(json.dumps(message))
            
            # Wait for response
            try:
                response = await asyncio.wait_for(websocket.recv(), timeout=10.0)
                print(f"📨 Response: {response}")
            except asyncio.TimeoutError:
                print("⏰ No response received")
                
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    asyncio.run(simple_test())