# Bitfocus Companion Integration Guide

## Solution Overview

We'll add a **WebSocket Server** to your application that Bitfocus Companion can connect to and send commands. This is the cleanest approach because:

1. ✅ No external dependencies (Companion connects via generic WebSocket)
2. ✅ Works with Bitfocus Companion's generic WebSocket module
3. ✅ Non-blocking (async/concurrent with existing functionality)
4. ✅ Supports multiple button triggers
5. ✅ Easy to extend with more commands

## Architecture

```
┌─────────────────────────────────────────────────────┐
│            Your Application                          │
│  ┌────────────────────────────────────────────────┐ │
│  │  WebSocket Server (localhost:8765)            │ │
│  │  - Listens for Companion commands             │ │
│  │  - Executes play_matchup_video()              │ │
│  │  - Can be extended for other buttons          │ │
│  └────────────────────────────────────────────────┘ │
│  ┌────────────────────────────────────────────────┐ │
│  │  OBSSOSController (existing)                   │ │
│  │  - Handles OBS/SOS events                      │ │
│  └────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────┘
        ▲
        │ WebSocket Connection
        │ (JSON commands)
        │
┌──────────────────────────────────┐
│  Bitfocus Companion              │
│  Button: "Play Matchup Video"    │
│  Action: Send JSON command       │
└──────────────────────────────────┘
```

## Implementation Steps

### Step 1: Add Configuration for Companion Server

Add to `CONFIG_FILE` (in config.json):

```json
{
  "COMPANION_WEBSOCKET_PORT": 8765,
  "COMPANION_ENABLED": true
}
```

### Step 2: Add WebSocket Server to OBSSOSController

Add this code to the `OBSSOSController` class:

```python
async def start_companion_server(self) -> None:
    """Start WebSocket server for Bitfocus Companion integration.

    Listens on localhost:COMPANION_WEBSOCKET_PORT for JSON commands
    from Bitfocus Companion. Supported commands:
    - {"command": "play_matchup"} - Triggers matchup video
    - {"command": "play_video", "team": "HSMW", "color": "BLAU"} - Play team video
    - {"command": "play_audio"} - Play audio stinger
    """
    port = config.get('COMPANION_WEBSOCKET_PORT', 8765)

    async def handler(websocket, path):
        """Handle incoming Companion commands."""
        print(f"✓ Companion connected from {websocket.remote_address}")
        try:
            async for message in websocket:
                try:
                    command = json.loads(message)
                    await self._handle_companion_command(command, websocket)
                except json.JSONDecodeError:
                    await websocket.send(json.dumps({
                        "status": "error",
                        "message": "Invalid JSON"
                    }))
                except Exception as e:
                    print(f"✗ Error processing command: {e}")
                    await websocket.send(json.dumps({
                        "status": "error",
                        "message": str(e)
                    }))
        except websockets.exceptions.ConnectionClosed:
            print(f"⏹ Companion disconnected")
        except Exception as e:
            print(f"✗ Companion error: {e}")

    try:
        server = await websockets.serve(handler, "localhost", port)
        print(f"✓ Companion WebSocket server running on localhost:{port}")
        await server.wait_closed()
    except Exception as e:
        print(f"✗ Failed to start Companion server: {e}")

async def _handle_companion_command(self, command: dict, websocket) -> None:
    """Process command from Bitfocus Companion.

    Args:
        command: Dictionary with "command" key and optional parameters
        websocket: Connection to send response back to Companion
    """
    cmd = command.get("command", "").lower()

    try:
        if cmd == "play_matchup":
            self.play_matchup_video()
            await websocket.send(json.dumps({
                "status": "success",
                "command": "play_matchup",
                "message": "Matchup video started"
            }))

        elif cmd == "play_video":
            team = command.get("team")
            color = command.get("color")
            if team and color:
                video_name = get_video_name(team, color)
                self.play_video(video_name)
                await websocket.send(json.dumps({
                    "status": "success",
                    "command": "play_video",
                    "video": video_name
                }))
            else:
                await websocket.send(json.dumps({
                    "status": "error",
                    "message": "Missing 'team' or 'color' parameter"
                }))

        elif cmd == "play_audio":
            self.play_audio()
            await websocket.send(json.dumps({
                "status": "success",
                "command": "play_audio",
                "message": "Audio started"
            }))

        else:
            await websocket.send(json.dumps({
                "status": "error",
                "message": f"Unknown command: {cmd}"
            }))

    except Exception as e:
        await websocket.send(json.dumps({
            "status": "error",
            "message": str(e)
        }))
```

### Step 3: Integrate with Main Event Loop

Modify the `run()` method to start the Companion server:

```python
async def run(self) -> None:
    """Main async event loop."""
    print("=== OBS + SOS Video Player ===\n")

    # Start Companion server if enabled
    companion_task = None
    if config.get('COMPANION_ENABLED', False):
        companion_task = asyncio.create_task(self.start_companion_server())

    # Connect to both OBS instances and SOS concurrently
    obs_result, obs2_result, sos_result = await asyncio.gather(
        self.connect_obs_with_retry(),
        self.connect_obs2_with_retry(),
        self.connect_sos_with_retry(),
        return_exceptions=False
    )

    if not obs_result and not obs2_result:
        print("✗ Keine OBS Instanz konnte verbunden werden")
        return

    if not sos_result:
        if self.obs:
            self.obs.disconnect()
        if self.obs2:
            self.obs2.disconnect()
        return

    print("🎯 Bereit!\n")

    try:
        await self.listen_sos_events()
    except KeyboardInterrupt:
        print("\n⏹ Beendet")
    finally:
        if companion_task:
            companion_task.cancel()
        if self.obs:
            self.obs.disconnect()
        if self.obs2:
            self.obs2.disconnect()
        if self.sos_ws:
            await self.sos_ws.close()
```

## Bitfocus Companion Configuration

### 1. Add Generic TCP/Websocket Module

In Bitfocus Companion:

1. Go to **Settings** → **Modules**
2. Search for **"Generic: TCP/UDP"** or **"TCP/Websocket"**
3. Click **Add module**
4. Configure:
   - **IP/Host:** `localhost` (or your computer's IP)
   - **Port:** `8765`
   - **Protocol:** Websocket

### 2. Create Button Command

On any button:

1. Add **Action** → Search for your TCP module
2. Set action to **"Send"**
3. In the data field, enter:

```json
{ "command": "play_matchup" }
```

### 3. Button Examples

**Button: Play Matchup**

```json
{ "command": "play_matchup" }
```

**Button: Play Blue Team Video**

```json
{ "command": "play_video", "team": "HSMW", "color": "BLAU" }
```

**Button: Play Orange Team Video**

```json
{ "command": "play_video", "team": "LES", "color": "PINK" }
```

**Button: Play Audio Stinger**

```json
{ "command": "play_audio" }
```

## Testing

### Test 1: Manual WebSocket Test (PowerShell)

```powershell
# In PowerShell, you can test with:
$uri = "ws://localhost:8765"
$ws = New-WebSocketClientConnection -Uri $uri
$ws.Connect()
$ws.Send('{"command": "play_matchup"}')
# Check response
$response = $ws.Receive()
```

### Test 2: Using Python

```python
import asyncio
import websockets
import json

async def test():
    uri = "ws://localhost:8765"
    async with websockets.connect(uri) as websocket:
        # Send command
        await websocket.send(json.dumps({"command": "play_matchup"}))
        # Receive response
        response = await websocket.recv()
        print("Response:", response)

asyncio.run(test())
```

### Test 3: Using netcat/wscat

```bash
# Install wscat: npm install -g wscat
wscat -c ws://localhost:8765
# Then type:
{"command": "play_matchup"}
```

## Configuration File Update

Add to your `config.json`:

```json
{
  "BLUE_TEAM": "HSMW",
  "ORANGE_TEAM": "HSMW",
  "OBS_HOST": "localhost",
  "OBS_PORT": 4455,
  "OBS_PASSWORD": "",
  "WIN_SCENE_NAME": "SCN Win Animation",
  "MATCHUP_SCENE_NAME": "SCN Matchup Animation",
  "AUDIO_SCENE_NAME": "SCN Musik-Output",
  "AUDIO_SOURCE_NAME": "MED Game Win Stinger Audio",
  "OBS2_HOST": "localhost",
  "OBS2_PORT": 4455,
  "OBS2_PASSWORD": "",
  "SOS_HOST": "localhost",
  "SOS_PORT": 49322,
  "COMPANION_WEBSOCKET_PORT": 8765,
  "COMPANION_ENABLED": true,
  "CURRENT_MATCH": 0,
  "MATCHES": []
}
```

## Advantages of This Approach

✅ **Simple** - Just a WebSocket server, no special protocol  
✅ **Standard** - Works with Bitfocus Companion's generic TCP module  
✅ **Extensible** - Easy to add more commands  
✅ **Non-blocking** - Runs concurrently with main event loop  
✅ **Responsive** - Commands are processed immediately  
✅ **Observable** - Sends back JSON responses confirming execution

## Future Enhancements

You could add more commands:

```json
{"command": "set_match", "index": 2}
{"command": "get_status"}
{"command": "get_matches"}
{"command": "trigger_win", "team_num": 0}
```

---

**Ready to implement?** I can add this code to your application now!
