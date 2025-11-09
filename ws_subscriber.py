import asyncio
import json
import websockets
from typing import Callable, List, Union, Optional, Dict, Any
from collections import defaultdict


class WsSubscriber:
    """
    WebSocket subscriber client with pub/sub pattern support.
    Recreates the functionality of the JavaScript WsSubscribers object.
    """
    
    def __init__(self):
        self._subscribers: Dict[str, Dict[str, List[Callable]]] = defaultdict(lambda: defaultdict(list))
        self.websocket: Optional[websockets.WebSocketClientProtocol] = None
        self.web_socket_connected = False
        self.register_queue: List[str] = []
        self.debug = False
        self.debug_filters: Optional[List[str]] = None
        self._running = False
        
    async def init(self, port: int = 49322, debug: bool = False, debug_filters: Optional[List[str]] = None):
        """
        Initialize and connect to the WebSocket server.
        
        Args:
            port: WebSocket server port (default: 49322)
            debug: Enable debug logging
            debug_filters: List of 'channel:event' strings to exclude from debug output
        """
        self.debug = debug
        self.debug_filters = debug_filters
        
        if debug:
            if debug_filters is not None:
                print("WebSocket Debug Mode enabled with filtering. Only events not in the filter list will be dumped")
            else:
                print("WebSocket Debug Mode enabled without filters applied. All events will be dumped to console")
                print("To use filters, pass in a list of 'channel:event' strings to the debug_filters parameter")
        
        uri = f"ws://localhost:{port}"
        
        try:
            self.websocket = await websockets.connect(uri)
            self.web_socket_connected = True
            self._running = True
            
            # Trigger open event
            await self._trigger_subscribers("ws", "open", None)
            
            # Register queued subscriptions
            for registration in self.register_queue:
                await self.send("wsRelay", "register", registration)
            self.register_queue.clear()
            
            # Start listening for messages
            asyncio.create_task(self._listen())
            
        except Exception as e:
            print(f"WebSocket connection error: {e}")
            self.web_socket_connected = False
            await self._trigger_subscribers("ws", "error", None)
    
    async def _listen(self):
        """Internal method to listen for incoming WebSocket messages."""
        try:
            async for message in self.websocket:
                try:
                    j_event = json.loads(message)
                    
                    if 'event' not in j_event:
                        continue
                    
                    event_split = j_event['event'].split(':', 1)
                    if len(event_split) != 2:
                        continue
                        
                    channel, event_name = event_split
                    data = j_event.get('data')
                    
                    # Debug logging
                    if self.debug:
                        should_log = True
                        if self.debug_filters and j_event['event'] in self.debug_filters:
                            should_log = False
                        if should_log:
                            print(f"[WS] {channel} | {event_name} | {j_event}")
                    
                    # Trigger subscribers
                    await self._trigger_subscribers(channel, event_name, data)
                    
                except json.JSONDecodeError:
                    print(f"Failed to decode message: {message}")
                except Exception as e:
                    print(f"Error processing message: {e}")
                    
        except websockets.exceptions.ConnectionClosed:
            await self._handle_close()
        except Exception as e:
            print(f"Listen error: {e}")
            await self._handle_error()
    
    async def _handle_close(self):
        """Handle WebSocket connection close."""
        self.web_socket_connected = False
        self._running = False
        await self._trigger_subscribers("ws", "close", None)
    
    async def _handle_error(self):
        """Handle WebSocket errors."""
        self.web_socket_connected = False
        self._running = False
        await self._trigger_subscribers("ws", "error", None)
    
    def subscribe(self, channels: Union[str, List[str]], events: Union[str, List[str]], 
                  callback: Callable[[Any], None]):
        """
        Add callbacks for when certain events are thrown.
        Execution is guaranteed to be in First In First Out order.
        
        Args:
            channels: Single channel string or list of channels
            events: Single event string or list of events
            callback: Callback function to execute when event is received
        """
        # Normalize to lists
        if isinstance(channels, str):
            channels = [channels]
        if isinstance(events, str):
            events = [events]
        
        for channel in channels:
            for event in events:
                # Initialize nested dictionaries if needed
                if channel not in self._subscribers:
                    self._subscribers[channel] = defaultdict(list)
                
                # Register with server if this is a new event subscription
                if event not in self._subscribers[channel] or len(self._subscribers[channel][event]) == 0:
                    registration = f"{channel}:{event}"
                    if self.web_socket_connected:
                        # Send registration immediately
                        asyncio.create_task(self.send("wsRelay", "register", registration))
                    else:
                        # Queue for later registration
                        self.register_queue.append(registration)
                
                # Add callback
                self._subscribers[channel][event].append(callback)
    
    def clear_event_callbacks(self, channel: str, event: str):
        """
        Clear all callbacks for a specific channel and event.
        
        Args:
            channel: Channel name
            event: Event name
        """
        if channel in self._subscribers and event in self._subscribers[channel]:
            self._subscribers[channel][event] = []
    
    async def _trigger_subscribers(self, channel: str, event: str, data: Any):
        """
        Internal method to trigger all callbacks for a channel:event combination.
        
        Args:
            channel: Channel name
            event: Event name
            data: Data to pass to callbacks
        """
        if channel in self._subscribers and event in self._subscribers[channel]:
            for callback in self._subscribers[channel][event]:
                if callable(callback):
                    # Support both sync and async callbacks
                    if asyncio.iscoroutinefunction(callback):
                        await callback(data)
                    else:
                        callback(data)
    
    async def send(self, channel: str, event: str, data: Any = None):
        """
        Send a message through the WebSocket or trigger local event.
        
        Args:
            channel: Channel name
            event: Event name
            data: Data to send
        """
        if not isinstance(channel, str):
            print("Error: Channel must be a string")
            return
        
        if not isinstance(event, str):
            print("Error: Event must be a string")
            return
        
        if channel == 'local':
            # Local event, trigger directly without WebSocket
            await self._trigger_subscribers(channel, event, data)
        else:
            # Send through WebSocket
            if not self.web_socket_connected or self.websocket is None:
                print("Error: WebSocket is not connected")
                return
            
            message = {
                'event': f"{channel}:{event}",
                'data': data
            }
            
            try:
                await self.websocket.send(json.dumps(message))
            except Exception as e:
                print(f"Error sending message: {e}")
    
    async def close(self):
        """Close the WebSocket connection."""
        if self.websocket and not self.websocket.closed:
            await self.websocket.close()
        self._running = False
        self.web_socket_connected = False
    
    @property
    def is_connected(self) -> bool:
        """Check if WebSocket is currently connected."""
        return self.web_socket_connected


# Example usage
async def main():
    """Example demonstrating how to use the WsSubscriber."""
    
    # Create subscriber instance
    ws = WsSubscriber()
    
    # Define callback functions
    def on_game_update(data):
        print(f"Game update received: {data}")
    
    def on_player_joined(data):
        print(f"Player joined: {data}")
    
    async def on_async_event(data):
        print(f"Async event: {data}")
        # Can do async operations here
        await asyncio.sleep(0.1)
    
    # Subscribe to events (can be done before or after connection)
    ws.subscribe("game", "update", on_game_update)
    ws.subscribe("game", "player_joined", on_player_joined)
    ws.subscribe(["channel1", "channel2"], ["event1", "event2"], on_async_event)
    
    # Subscribe to connection events
    ws.subscribe("ws", "open", lambda _: print("WebSocket connected!"))
    ws.subscribe("ws", "close", lambda _: print("WebSocket closed!"))
    ws.subscribe("ws", "error", lambda _: print("WebSocket error!"))
    
    # Connect to WebSocket server
    await ws.init(port=49322, debug=True)
    
    # Wait a bit to receive messages
    await asyncio.sleep(10)
    
    # Send a message
    await ws.send("game", "player_action", {"action": "jump", "player_id": 123})
    
    # Send a local event (doesn't go through WebSocket)
    await ws.send("local", "test", {"test": "data"})
    
    # Keep running
    try:
        while ws.is_connected:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        print("Shutting down...")
    finally:
        await ws.close()


if __name__ == "__main__":
    asyncio.run(main())
