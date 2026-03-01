"""
Event Bus for asynchronous messaging and event-driven architecture.

This module provides a lightweight event bus implementation that supports:
- Publishing events to topics
- Subscribing to topics with callback handlers
- Broadcasting events to all subscribers
- Async execution of event handlers

The bus is designed to be easily replaceable with production message brokers
like NATS, Redis Streams, or Kafka for horizontal scalability.

Event Types:
- grammar_correction: Fired when grammar analysis completes
- conversation_turn: Fired when a conversation turn is logged
- player_moved: Fired when player position updates
- proximity_status: Fired when player proximity to NPC changes
- context_change: Fired when scene/context changes
"""
import asyncio
from typing import Dict, List, Callable, Any
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Event:
    """
    Standard event structure for the message bus.
    """
    type: str
    topic: str
    data: Dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)


class EventBus:
    """
    In-memory event bus for development and small-scale deployments.
    
    For production scaling, replace with:
    - NATS (ultra-low latency, recommended for gaming)
    - Redis Streams (good balance of features and simplicity)
    - Kafka (high throughput, complex deployments)
    """
    
    def __init__(self):
        self._subscribers: Dict[str, List[Callable]] = defaultdict(list)
        self._global_subscribers: List[Callable] = []
        self._event_history: List[Event] = []  # For debugging/replay
        self._max_history = 1000
    
    def subscribe(self, topic: str, callback: Callable) -> None:
        """
        Subscribe to events on a specific topic.
        
        Args:
            topic: Event topic to subscribe to (e.g., "grammar_correction")
            callback: Async function to call when event is published
        """
        self._subscribers[topic].append(callback)
    
    def subscribe_all(self, callback: Callable) -> None:
        """
        Subscribe to all events regardless of topic.
        Useful for logging, analytics, or monitoring.
        
        Args:
            callback: Async function to call for every event
        """
        self._global_subscribers.append(callback)
    
    def unsubscribe(self, topic: str, callback: Callable) -> None:
        """Remove a subscriber from a topic."""
        if topic in self._subscribers and callback in self._subscribers[topic]:
            self._subscribers[topic].remove(callback)
    
    async def publish(
        self,
        topic: str,
        event_type: str,
        data: Dict[str, Any],
        metadata: Dict[str, Any] = None,
    ) -> None:
        """
        Publish an event to a topic.
        
        All subscribers to this topic will be notified asynchronously.
        Handlers are executed concurrently (fire-and-forget).
        
        Args:
            topic: Event topic (e.g., "grammar", "conversation", "movement")
            event_type: Specific event type (e.g., "grammar_correction")
            data: Event payload
            metadata: Optional metadata (player_id, session_id, etc.)
        """
        event = Event(
            type=event_type,
            topic=topic,
            data=data,
            metadata=metadata or {},
        )
        
        # Store in history
        self._event_history.append(event)
        if len(self._event_history) > self._max_history:
            self._event_history.pop(0)
        
        # Notify topic-specific subscribers
        handlers = []
        
        if topic in self._subscribers:
            for callback in self._subscribers[topic]:
                handlers.append(callback(event))
        
        # Notify global subscribers
        for callback in self._global_subscribers:
            handlers.append(callback(event))
        
        # Execute all handlers concurrently (non-blocking)
        if handlers:
            await asyncio.gather(*handlers, return_exceptions=True)
    
    async def publish_and_wait(
        self,
        topic: str,
        event_type: str,
        data: Dict[str, Any],
        metadata: Dict[str, Any] = None,
    ) -> List[Any]:
        """
        Publish an event and wait for all handlers to complete.
        Returns the results from all handlers.
        
        Use this sparingly — most events should be fire-and-forget.
        """
        event = Event(
            type=event_type,
            topic=topic,
            data=data,
            metadata=metadata or {},
        )
        
        handlers = []
        
        if topic in self._subscribers:
            for callback in self._subscribers[topic]:
                handlers.append(callback(event))
        
        for callback in self._global_subscribers:
            handlers.append(callback(event))
        
        if handlers:
            results = await asyncio.gather(*handlers, return_exceptions=True)
            return results
        
        return []
    
    def get_recent_events(self, topic: str = None, limit: int = 100) -> List[Event]:
        """
        Get recent events from history.
        
        Args:
            topic: Filter by topic (None for all topics)
            limit: Maximum number of events to return
        
        Returns:
            List of recent events
        """
        events = self._event_history
        
        if topic:
            events = [e for e in events if e.topic == topic]
        
        return events[-limit:]
    
    def clear_history(self) -> None:
        """Clear event history (useful for tests)."""
        self._event_history.clear()


class RedisEventBus(EventBus):
    """
    Redis Streams-based event bus for production deployments.
    
    Provides:
    - Persistence of events
    - Horizontal scaling with consumer groups
    - At-least-once delivery guarantees
    
    Requires: redis-py with asyncio support
    """
    
    def __init__(self, redis_client):
        super().__init__()
        self._redis = redis_client
        self._consumer_tasks = []
    
    async def publish(
        self,
        topic: str,
        event_type: str,
        data: Dict[str, Any],
        metadata: Dict[str, Any] = None,
    ) -> None:
        """
        Publish event to Redis Stream.
        
        Stream key format: "events:{topic}"
        """
        import json
        
        event = Event(
            type=event_type,
            topic=topic,
            data=data,
            metadata=metadata or {},
        )
        
        stream_key = f"events:{topic}"
        
        # Publish to Redis Stream
        await self._redis.xadd(
            stream_key,
            {
                "type": event_type,
                "data": json.dumps(data),
                "metadata": json.dumps(metadata or {}),
                "timestamp": event.timestamp.isoformat(),
            }
        )
        
        # Also publish to in-memory subscribers for local handlers
        await super().publish(topic, event_type, data, metadata)
    
    async def start_consumer(self, topic: str, consumer_group: str = "default") -> None:
        """
        Start consuming events from a Redis Stream.
        
        This enables horizontal scaling:
        Multiple instances can consume from the same stream with load balancing.
        """
        import json
        
        stream_key = f"events:{topic}"
        
        # Create consumer group if it doesn't exist
        try:
            await self._redis.xgroup_create(stream_key, consumer_group, id="0", mkstream=True)
        except Exception:
            pass  # Group already exists
        
        # Consumer loop
        async def consume():
            consumer_id = f"consumer-{id(self)}"
            
            while True:
                try:
                    messages = await self._redis.xreadgroup(
                        consumer_group,
                        consumer_id,
                        {stream_key: ">"},
                        count=10,
                        block=1000,
                    )
                    
                    for stream, stream_messages in messages:
                        for message_id, message_data in stream_messages:
                            event_type = message_data["type"]
                            data = json.loads(message_data["data"])
                            metadata = json.loads(message_data["metadata"])
                            
                            # Trigger local subscribers
                            if topic in self._subscribers:
                                event = Event(
                                    type=event_type,
                                    topic=topic,
                                    data=data,
                                    metadata=metadata,
                                )
                                
                                for callback in self._subscribers[topic]:
                                    try:
                                        await callback(event)
                                    except Exception as e:
                                        print(f"[EventBus] Error in handler: {e}")
                            
                            # Acknowledge message
                            await self._redis.xack(stream_key, consumer_group, message_id)
                
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    print(f"[EventBus] Consumer error: {e}")
                    await asyncio.sleep(1)
        
        task = asyncio.create_task(consume())
        self._consumer_tasks.append(task)
    
    async def shutdown(self) -> None:
        """Stop all consumers."""
        for task in self._consumer_tasks:
            task.cancel()
        
        await asyncio.gather(*self._consumer_tasks, return_exceptions=True)


# Singleton instance for convenience
_default_bus: EventBus = None


def get_event_bus() -> EventBus:
    """
    Get the default event bus instance.
    """
    global _default_bus
    if _default_bus is None:
        _default_bus = EventBus()
    return _default_bus


def set_event_bus(bus: EventBus) -> None:
    """
    Set a custom event bus instance (for dependency injection).
    """
    global _default_bus
    _default_bus = bus
