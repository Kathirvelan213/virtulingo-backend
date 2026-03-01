"""
Minimal WebSocket test to isolate the issue.
"""
import asyncio
import websockets


async def test_simple():
    # First test the simple endpoint without dependencies
    uri = "ws://localhost:8000/api/conversations/ws/test"
    print(f"Testing simple endpoint: {uri}...")
    
    try:
        async with websockets.connect(uri) as websocket:
            print("✅ Simple endpoint connected!")
            
            # Try to receive
            response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
            print(f"Received: {response}")
            
    except websockets.exceptions.WebSocketException as e:
        print(f"❌ Simple endpoint failed: {e}")
    except Exception as e:
        print(f"❌ Error: {e}")
    
    print("\n" + "="*60 + "\n")
    
    # Now test the full endpoint with dependencies
    uri2 = "ws://localhost:8000/api/conversations/ws/test_player_123/test_npc_456"
    print(f"Testing full endpoint: {uri2}...")
    
    try:
        async with websockets.connect(uri2) as websocket:
            print("✅ Full endpoint connected!")
            
            # Send test audio
            await websocket.send(b"\x00" * 1000)
            print("Sent test audio")
            
    except websockets.exceptions.WebSocketException as e:
        print(f"❌ Full endpoint failed: {e}")
        print(f"   Type: {type(e).__name__}")
        if hasattr(e, 'status_code'):
            print(f"   Status: {e.status_code}")
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_simple())
