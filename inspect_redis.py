"""
Redis Inspector - View stored player state and conversations.

Usage:
    python inspect_redis.py                    # List all keys
    python inspect_redis.py test_player_123    # View specific player's data
"""
import asyncio
import sys
import json
from infrastructures.redis import get_redis_client
from dotenv import load_dotenv
load_dotenv()

async def list_all_keys():
    """List all keys in Redis."""
    redis = get_redis_client()
    keys = await redis.keys("*")
    
    if not keys:
        print("📭 No data in Redis yet")
        return []
    
    print(f"📦 Found {len(keys)} keys in Redis:\n")
    for key in sorted(keys):
        key_type = await redis.type(key)
        ttl = await redis.ttl(key)
        ttl_str = f"{ttl}s" if ttl > 0 else "no expiry" if ttl == -1 else "expired"
        print(f"  • {key} ({key_type}) - TTL: {ttl_str}")
    
    return keys


async def inspect_player_state(player_id: str):
    """Inspect a specific player's state."""
    redis = get_redis_client()
    state_key = f"player:state:{player_id}"
    
    print(f"\n🎮 Player State: {player_id}")
    print("=" * 70)
    
    state = await redis.hgetall(state_key)
    if not state:
        print("  ⚠️  No state found for this player")
        return
    
    for field, value in state.items():
        # Try to parse JSON for list fields
        try:
            parsed = json.loads(value)
            print(f"  {field:20} = {parsed}")
        except:
            print(f"  {field:20} = {value}")


async def inspect_conversations(player_id: str):
    """Inspect all conversations for a player."""
    redis = get_redis_client()
    
    # Find all conversation keys for this player
    pattern = f"player:conv:{player_id}:*"
    keys = await redis.keys(pattern)
    
    if not keys:
        print(f"\n💬 No conversations found for player: {player_id}")
        return
    
    for key in sorted(keys):
        npc_id = key.split(":")[-1]
        print(f"\n💬 Conversation with NPC: {npc_id}")
        print("=" * 70)
        
        # Get conversation history
        turns = await redis.lrange(key, 0, -1)
        
        if not turns:
            print("  (empty)")
            continue
        
        for i, turn_json in enumerate(turns, 1):
            turn = json.loads(turn_json)
            role = turn.get("role", "unknown")
            content = turn.get("content", "")
            
            emoji = "👤" if role == "player" else "🤖"
            print(f"  {i}. {emoji} {role.upper()}: {content}")


async def clear_player_data(player_id: str):
    """Clear all data for a specific player."""
    redis = get_redis_client()
    
    # Find all keys for this player
    state_key = f"player:state:{player_id}"
    conv_pattern = f"player:conv:{player_id}:*"
    conv_keys = await redis.keys(conv_pattern)
    
    all_keys = [state_key] + conv_keys
    existing_keys = []
    
    for key in all_keys:
        if await redis.exists(key):
            existing_keys.append(key)
    
    if not existing_keys:
        print(f"⚠️  No data found for player: {player_id}")
        return
    
    print(f"\n🗑️  Deleting {len(existing_keys)} keys for player: {player_id}")
    for key in existing_keys:
        print(f"  • {key}")
    
    confirm = input("\n⚠️  Are you sure? (yes/no): ")
    if confirm.lower() == "yes":
        deleted = await redis.delete(*existing_keys)
        print(f"✅ Deleted {deleted} keys")
    else:
        print("❌ Cancelled")


async def main():
    if len(sys.argv) < 2:
        print("═" * 70)
        print("Redis Inspector - VirtuLingo Backend")
        print("═" * 70)
        await list_all_keys()
        print("\n💡 Usage:")
        print("  python inspect_redis.py <player_id>        # View player data")
        print("  python inspect_redis.py <player_id> clear  # Clear player data")
    elif len(sys.argv) == 2:
        player_id = sys.argv[1]
        await inspect_player_state(player_id)
        await inspect_conversations(player_id)
    elif len(sys.argv) == 3 and sys.argv[2] == "clear":
        player_id = sys.argv[1]
        await clear_player_data(player_id)
    else:
        print("❌ Invalid arguments")
        print("Usage: python inspect_redis.py [player_id] [clear]")


if __name__ == "__main__":
    asyncio.run(main())
