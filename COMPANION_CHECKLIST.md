# ✅ Companion Integration - Setup Checklist

Use this checklist to ensure everything is set up correctly.

---

## 📋 Pre-Setup

- [ ] Application code updated (syntax checked)
- [ ] config.json has Companion settings
- [ ] Test tool (`test_companion_connection.py`) available
- [ ] Documentation files created (5 files)

---

## 🚀 Initial Setup

### Step 1: Verify Application

- [ ] Application starts without errors
- [ ] Watch for message: `✓ Companion WebSocket server running on localhost:8765`
- [ ] Application remains running stably

### Step 2: Run Test Script

```bash
python test_companion_connection.py
```

- [ ] Test script connects successfully
- [ ] play_matchup test: PASSED ✓
- [ ] play_audio test: PASSED ✓
- [ ] play_video test: PASSED ✓
- [ ] trigger_win test: PASSED ✓
- [ ] Invalid command returns error ✓
- [ ] Missing parameters returns error ✓

### Step 3: Configuration

- [ ] Verify `config.json` has:

  ```json
  "COMPANION_WEBSOCKET_PORT": 8765,
  "COMPANION_ENABLED": true
  ```

- [ ] Port 8765 is available (not used by another app)
- [ ] Port 8765 not blocked by firewall

---

## 🔌 Bitfocus Companion Setup

### Step 1: Add Module

- [ ] Open Bitfocus Companion
- [ ] Go to Connections/Modules
- [ ] Search for "TCP/UDP" or "Websocket"
- [ ] Create new instance
- [ ] Set IP: `localhost`
- [ ] Set Port: `8765`
- [ ] Set Protocol: Websocket
- [ ] Save configuration

### Step 2: Test Connection

- [ ] Connection shows "Connected" or "OK"
- [ ] No connection errors
- [ ] Status indicator shows healthy

### Step 3: Create Test Button

- [ ] Create new button on a page
- [ ] Add Action → Select TCP/Websocket module
- [ ] Select action type: "Send" or similar
- [ ] Enter JSON command: `{"command":"play_matchup"}`
- [ ] Save button

### Step 4: Test Button

- [ ] Press button in Bitfocus Companion
- [ ] Watch application for activity:
  ```
  ✓ Companion connected from [address]
  ▶ Media gestartet (OBS 1): matchup_video
  ```
- [ ] Button executes without errors
- [ ] Video plays on OBS

---

## 🎮 Create Additional Buttons

### Button Set 1: Video Controls

- [ ] **Play Matchup**

  ```json
  { "command": "play_matchup" }
  ```

- [ ] **Play Audio**
  ```json
  { "command": "play_audio" }
  ```

### Button Set 2: Manual Win (Backup)

- [ ] **Blue Team Wins**

  ```json
  { "command": "trigger_win", "team_num": 0 }
  ```

- [ ] **Orange Team Wins**
  ```json
  { "command": "trigger_win", "team_num": 1 }
  ```

### Button Set 3: Team Videos (Optional)

- [ ] **HSMW Victory (Blue)**

  ```json
  { "command": "play_video", "team": "HSMW", "color": "BLAU" }
  ```

- [ ] **LES Victory (Orange)**
  ```json
  { "command": "play_video", "team": "LES", "color": "PINK" }
  ```

(Add more as needed for your teams)

---

## 🧪 Testing & Validation

### Connectivity Tests

- [ ] Application starts and Companion server starts
- [ ] Bitfocus Companion can connect to server
- [ ] Connection remains stable for extended time
- [ ] No errors in application console

### Command Tests

- [ ] play_matchup command executes
- [ ] play_video command executes
- [ ] play_audio command executes
- [ ] trigger_win command executes
- [ ] Invalid commands return error (expected)
- [ ] Missing parameters return error (expected)

### Button Tests

- [ ] Each button sends correct JSON
- [ ] Commands execute immediately
- [ ] Videos play correctly
- [ ] No lag or delays
- [ ] Multiple presses work correctly
- [ ] Rapid pressing doesn't cause issues

### Edge Cases

- [ ] Button pressed while video already playing: Works
- [ ] Button pressed during SOS match: Commands priority correct
- [ ] Long delay between button presses: Works
- [ ] Multiple different commands: All execute correctly

---

## 📱 Remote PC Setup (If Applicable)

### If Companion on Different Computer:

- [ ] Found your PC's IP address
- [ ] Updated Companion connection IP to your PC IP
- [ ] Port 8765 open in Windows Firewall:
  ```powershell
  New-NetFirewallRule -DisplayName "Allow Companion" `
    -Direction Inbound -LocalPort 8765 -Protocol TCP -Action Allow
  ```
- [ ] Connection works from remote PC
- [ ] Commands execute from remote PC

---

## 📚 Documentation Review

- [ ] Read `COMPANION_INDEX.md` - Navigation guide
- [ ] Read `COMPANION_QUICKSTART.md` - Quick reference
- [ ] Read `COMPANION_README.md` - For setup details
- [ ] Understand `COMPANION_INTEGRATION.md` - Technical details
- [ ] Reference `COMPANION_TECHNICAL.md` - API reference

---

## 🔧 Configuration Review

### In config.json:

- [ ] `COMPANION_WEBSOCKET_PORT` set correctly
- [ ] `COMPANION_ENABLED` is `true`
- [ ] No JSON syntax errors in config file
- [ ] Config file was saved properly

### In Bitfocus Companion:

- [ ] TCP/Websocket module configured
- [ ] Correct IP address (localhost or your PC IP)
- [ ] Correct port (8765 or your configured port)
- [ ] Connection status shows healthy
- [ ] All buttons use correct JSON format

---

## 🚨 Troubleshooting Checklist

### If Connection Fails:

- [ ] Application is running
- [ ] COMPANION_ENABLED is true in config
- [ ] Port 8765 is not used by another app
- [ ] Firewall allows port 8765
- [ ] Using correct IP (localhost for same PC)

### If Commands Don't Work:

- [ ] JSON syntax is valid (use test script)
- [ ] Command name spelled correctly
- [ ] All required parameters included
- [ ] Application console shows command received
- [ ] No errors in application output

### If Videos Don't Play:

- [ ] OBS connection is active
- [ ] Scenes are correctly configured
- [ ] Media sources exist in OBS
- [ ] Other video triggers work (GUI button)
- [ ] Check OBS logs for errors

### If Button Does Nothing:

- [ ] Button action is set to "Send"
- [ ] Data field has valid JSON
- [ ] TCP module is selected correctly
- [ ] Connection is established
- [ ] Run test script to diagnose

---

## ✅ Final Verification

- [ ] Application starts successfully
- [ ] Companion server starts
- [ ] Test script passes all tests
- [ ] Bitfocus Companion connects
- [ ] Test button works
- [ ] Commands execute immediately
- [ ] Videos play correctly
- [ ] No errors in logs
- [ ] Documentation reviewed
- [ ] Setup complete!

---

## 🎉 You're Ready!

Once all checkboxes are checked, your Bitfocus Companion integration is ready for:

- ✅ Stream control
- ✅ Manual video playback
- ✅ Remote video triggering
- ✅ Production use

---

## 📞 If Issues Remain

1. **Check logs:**

   - Look at application console output
   - Run test script: `python test_companion_connection.py`
   - Check Bitfocus Companion logs

2. **Verify setup:**

   - Recheck all configuration steps
   - Verify IP and port match
   - Confirm firewall settings

3. **Review documentation:**
   - COMPANION_README.md → Troubleshooting section
   - COMPANION_TECHNICAL.md → Code reference

---

## 📋 Maintenance Checklist (Regular)

### Weekly:

- [ ] Verify Companion connection is stable
- [ ] Test a few button presses
- [ ] Check application doesn't crash

### After Config Changes:

- [ ] Test connection immediately
- [ ] Run test script to verify
- [ ] Check all buttons work

### Before Important Event:

- [ ] Run full test script
- [ ] Test all buttons
- [ ] Verify application stability
- [ ] Check OBS connections
- [ ] Do a final button press test

---

**Status:** Ready to deploy when all items checked ✅

**Last Updated:** November 8, 2025
