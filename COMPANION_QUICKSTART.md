# Quick Start: Bitfocus Companion Integration

## ✅ Feature Now Available!

Your application now has a **WebSocket server** that Bitfocus Companion can connect to and send commands to trigger videos!

## 🚀 Quick Start

### Step 1: Update Config File

Add these lines to your `config.json`:

```json
{
  "COMPANION_WEBSOCKET_PORT": 55555,
  "COMPANION_ENABLED": true
}
```

### Step 2: Start Your Application

Run your app normally:

```bash
python sos-obs-videoplayer.py
```

You should see output like:

```
✓ Companion WebSocket server running on localhost:55555
```

### Step 3: Configure Bitfocus Companion

#### 3a. Add Generic TCP Module

1. Open **Bitfocus Companion**
2. Go to **Connections** (or **Settings → Modules**)
3. Add new connection → Search for **"TCP/UDP"** or **"Websocket"**
4. Create a new instance with:
   - **IP/Host:** `localhost` (or your computer IP if Companion is on different PC)
   - **Port:** `55555`
   - **Protocol:** Websocket

#### 3b. Create Button

1. Create a new button on any page
2. Add **Action** → Select your TCP/Websocket module
3. Select action type: **"Send Command"** (or similar)
4. In the **Data/Command** field, paste:

```json
{ "command": "play_matchup" }
```

5. Click the button → **Matchup video plays!** 🎉

---

## 📋 Available Commands

### Play Matchup Video (Main Button)

```json
{ "command": "play_matchup" }
```

**Response:**

```json
{
  "status": "success",
  "command": "play_matchup",
  "message": "Matchup video started"
}
```

---

### Play Team Victory Video

**Blue Team:**

```json
{ "command": "play_video", "team": "HSMW", "color": "BLAU" }
```

**Orange Team:**

```json
{ "command": "play_video", "team": "LES", "color": "PINK" }
```

**Response:**

```json
{ "status": "success", "command": "play_video", "video": "WIN HSMW BLAU.mp4" }
```

---

### Play Audio Stinger

```json
{ "command": "play_audio" }
```

**Response:**

```json
{ "status": "success", "command": "play_audio", "message": "Audio started" }
```

---

### Simulate Match End (Trigger Win Animation)

**Blue Team Wins:**

```json
{ "command": "trigger_win", "team_num": 0 }
```

**Orange Team Wins:**

```json
{ "command": "trigger_win", "team_num": 1 }
```

**Response:**

```json
{ "status": "success", "command": "trigger_win", "team": "Blue/Cyan" }
```

---

### Set Current Match

Change which match will be played when you use `play_matchup` or `trigger_win`:

```json
{ "command": "set_match", "match_index": 2 }
```

**Parameters:**

- `match_index`: Match number (0-6 for Match 1-7)

**Response:**

```json
{
  "status": "success",
  "command": "set_match",
  "match_index": 2,
  "match_number": 3,
  "blue_team": "LES",
  "orange_team": "UIA B"
}S
```

---

### Get Current Match

Query which match is currently selected:

```json
{ "command": "get_current_match" }
```

**Response:**

```json
{
  "status": "success",
  "command": "get_current_match",
  "match_index": 2,
  "match_number": 3,
  "blue_team": "LES",
  "orange_team": "UIA B"
}
```

---

### List All Matches

Get information about all available matches:

```json
{ "command": "list_matches" }
```

**Response:**

```json
{
  "status": "success",
  "command": "list_matches",
  "current_match_index": 2,
  "matches": [
    {
      "match_index": 0,
      "match_number": 1,
      "blue_team": "HSMW",
      "orange_team": "UIA B"
    },
    {
      "match_index": 1,
      "match_number": 2,
      "blue_team": "TLU",
      "orange_team": "WHZ"
    },
    {
      "match_index": 2,
      "match_number": 3,
      "blue_team": "LES",
      "orange_team": "UIA B"
    },
    {
      "match_index": 3,
      "match_number": 4,
      "blue_team": "TLU",
      "orange_team": "UIA A"
    },
    {
      "match_index": 4,
      "match_number": 5,
      "blue_team": "HSMW",
      "orange_team": "LES"
    },
    {
      "match_index": 5,
      "match_number": 6,
      "blue_team": "UIA A",
      "orange_team": "WHZ"
    },
    {
      "match_index": 6,
      "match_number": 7,
      "blue_team": "HSMW",
      "orange_team": "HSMW"
    }
  ]
}
```

---

## 🎮 Button Ideas for Companion

### Scenario 1: Pre-Match Setup

- **Button 1:** "Play Matchup" → `{"command": "play_matchup"}`
- **Button 2:** "Play Audio Test" → `{"command": "play_audio"}`

### Scenario 2: Manual Override (If SOS fails)

- **Button 1:** "Blue Wins" → `{"command": "trigger_win", "team_num": 0}`
- **Button 2:** "Orange Wins" → `{"command": "trigger_win", "team_num": 1}`

### Scenario 3: Team Selection (Preset Videos)

- **Page of 6 buttons for each team**
  - **HSMW Wins** → `{"command": "play_video", "team": "HSMW", "color": "BLAU"}`
  - **LES Wins** → `{"command": "play_video", "team": "LES", "color": "PINK"}`
  - etc.

---

## 🧪 Testing Without Bitfocus Companion

If you want to test locally before setting up Companion:

### Option 1: Using Python

Save as `test_companion.py`:

```python
import asyncio
import websockets
import json

async def test():
    try:
        async with websockets.connect("ws://localhost:55555", ping_interval=None) as websocket:
            print("Connected to Companion server!")

            # Test 1: Play matchup
            print("\n▶ Sending: play_matchup")
            await websocket.send(json.dumps({"command": "play_matchup"}))
            response = await websocket.recv()
            print(f"✓ Response: {response}")

            # Wait a moment
            await asyncio.sleep(1)

            # Test 2: Play video
            print("\n▶ Sending: play_video")
            await websocket.send(json.dumps({"command": "play_video", "team": "HSMW", "color": "BLAU"}))
            response = await websocket.recv()
            print(f"✓ Response: {response}")

    except Exception as e:
        print(f"✗ Error: {e}")

asyncio.run(test())
```

Run it while your app is running:

```bash
python test_companion.py
```

### Option 2: Using PowerShell WebSocket Test

```powershell
# Test connection
$uri = "ws://localhost:8765"
$ws = New-WebSocketClientConnection -Uri $uri
$ws.Connect()

# Send command
$ws.Send('{"command":"play_matchup"}')

# Receive response
$response = $ws.Receive()
Write-Host "Response: $response"

$ws.Close()
```

### Option 3: Using Online WebSocket Tester

Visit: https://www.websocket.org/echo.html

Change endpoint to: `ws://localhost:8765`

And send:

```json
{ "command": "play_matchup" }
```

---

## 📱 Remote Connection (Advanced)

If Bitfocus Companion is on a **different computer**:

1. Replace `localhost` with your **PC's IP address** in Companion settings
2. Your PC must be **accessible on the network**
3. Make sure **Windows Firewall** allows connections on port 55555:
   ```powershell
   New-NetFirewallRule -DisplayName "Allow Companion WebSocket" -Direction Inbound -LocalPort 55555 -Protocol TCP -Action Allow
   ```

Or using GUI:

- **Settings** → **Firewall** → **Allow app through firewall**
- Add `Python.exe` for your Python installation

---

## 🔧 Troubleshooting

| Issue                            | Solution                                                         |
| -------------------------------- | ---------------------------------------------------------------- |
| Companion won't connect          | Check IP/Port in Companion settings match (localhost:55555)      |
| Connection refused               | Make sure app is running and `COMPANION_ENABLED: true` in config |
| No response from button          | Check JSON syntax - must be valid JSON                           |
| App crashes on startup           | Check `config.json` syntax is valid                              |
| Companion shows "error" response | Check command spelling and parameters                            |

---

## ✨ Features

✅ **Easy** - Just send JSON to a WebSocket  
✅ **Responsive** - Commands execute immediately  
✅ **Reliable** - Error messages in responses  
✅ **Extensible** - Easy to add new commands  
✅ **Safe** - No external dependencies needed

---

## 🎯 Next Steps

1. **Start your app** with `COMPANION_ENABLED: true`
2. **Add TCP/Websocket connection** in Bitfocus Companion
3. **Create button** with `{"command": "play_matchup"}`
4. **Press button** → Video plays! 🎉

**That's it!** You can now control your video playback from Bitfocus Companion!

---

**Questions or issues?** Check `COMPANION_INTEGRATION.md` for detailed technical information.
