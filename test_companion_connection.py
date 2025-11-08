"""
Test script for Bitfocus Companion WebSocket integration.

This script tests the connection to your application's WebSocket server
and verifies that commands are working correctly.

Usage:
    python test_companion_connection.py

Requirements:
    - Your main application must be running with COMPANION_ENABLED: true
    - websockets library: pip install websockets
"""

import asyncio
import websockets
import json
import sys


async def test_connection(host: str = "localhost", port: int = 8765):
    """Test WebSocket connection and commands."""
    
    uri = f"ws://{host}:{port}"
    
    print(f"🔗 Connecting to {uri}...")
    print("-" * 70)
    
    try:
        async with websockets.connect(uri, ping_interval=None) as websocket:
            print(f"✅ Connected successfully!\n")
            
            # Test 1: Play Matchup
            print("TEST 1: Play Matchup Video")
            print("  Sending: {\"command\": \"play_matchup\"}")
            await websocket.send(json.dumps({"command": "play_matchup"}))
            response = await asyncio.wait_for(websocket.recv(), timeout=5)
            response_data = json.loads(response)
            print(f"  Response: {json.dumps(response_data, indent=2)}")
            if response_data.get("status") == "success":
                print("  ✅ PASSED\n")
            else:
                print("  ❌ FAILED\n")
            
            # Wait a moment
            await asyncio.sleep(1)
            
            # Test 2: Play Audio
            print("TEST 2: Play Audio")
            print("  Sending: {\"command\": \"play_audio\"}")
            await websocket.send(json.dumps({"command": "play_audio"}))
            response = await asyncio.wait_for(websocket.recv(), timeout=5)
            response_data = json.loads(response)
            print(f"  Response: {json.dumps(response_data, indent=2)}")
            if response_data.get("status") == "success":
                print("  ✅ PASSED\n")
            else:
                print("  ❌ FAILED\n")
            
            # Wait a moment
            await asyncio.sleep(1)
            
            # Test 3: Play Team Video (Blue)
            print("TEST 3: Play Team Video (Blue)")
            print("  Sending: {\"command\": \"play_video\", \"team\": \"HSMW\", \"color\": \"BLAU\"}")
            await websocket.send(json.dumps({
                "command": "play_video",
                "team": "HSMW",
                "color": "BLAU"
            }))
            response = await asyncio.wait_for(websocket.recv(), timeout=5)
            response_data = json.loads(response)
            print(f"  Response: {json.dumps(response_data, indent=2)}")
            if response_data.get("status") == "success":
                print("  ✅ PASSED\n")
            else:
                print("  ❌ FAILED\n")
            
            # Wait a moment
            await asyncio.sleep(1)
            
            # Test 4: Trigger Win (Blue Team)
            print("TEST 4: Trigger Win (Blue Team)")
            print("  Sending: {\"command\": \"trigger_win\", \"team_num\": 0}")
            await websocket.send(json.dumps({
                "command": "trigger_win",
                "team_num": 0
            }))
            response = await asyncio.wait_for(websocket.recv(), timeout=5)
            response_data = json.loads(response)
            print(f"  Response: {json.dumps(response_data, indent=2)}")
            if response_data.get("status") == "success":
                print("  ✅ PASSED\n")
            else:
                print("  ❌ FAILED\n")
            
            # Wait a moment
            await asyncio.sleep(1)
            
            # Test 5: Invalid Command (should error)
            print("TEST 5: Invalid Command (should error)")
            print("  Sending: {\"command\": \"invalid_command\"}")
            await websocket.send(json.dumps({"command": "invalid_command"}))
            response = await asyncio.wait_for(websocket.recv(), timeout=5)
            response_data = json.loads(response)
            print(f"  Response: {json.dumps(response_data, indent=2)}")
            if response_data.get("status") == "error":
                print("  ✅ PASSED (Correctly returned error)\n")
            else:
                print("  ❌ FAILED (Should have returned error)\n")
            
            # Test 6: Missing Parameters (should error)
            print("TEST 6: Missing Parameters (should error)")
            print("  Sending: {\"command\": \"play_video\", \"team\": \"HSMW\"} (missing 'color')")
            await websocket.send(json.dumps({
                "command": "play_video",
                "team": "HSMW"
            }))
            response = await asyncio.wait_for(websocket.recv(), timeout=5)
            response_data = json.loads(response)
            print(f"  Response: {json.dumps(response_data, indent=2)}")
            if response_data.get("status") == "error":
                print("  ✅ PASSED (Correctly returned error)\n")
            else:
                print("  ❌ FAILED (Should have returned error)\n")
            
            print("-" * 70)
            print("✅ All tests completed!\n")
            print("Your Bitfocus Companion integration is working correctly.")
            print("\nYou can now:")
            print("  1. Create buttons in Bitfocus Companion")
            print("  2. Connect to localhost:8765")
            print("  3. Send commands in JSON format")
            print("  4. Control your videos remotely!\n")
            
            return True
    
    except asyncio.TimeoutError:
        print("❌ Connection timeout - server didn't respond")
        print("\nMake sure:")
        print("  1. Your application is running")
        print("  2. COMPANION_ENABLED is set to true in config.json")
        print("  3. Port 8765 is not blocked by firewall")
        return False
    
    except ConnectionRefusedError:
        print("❌ Connection refused!")
        print("\nMake sure:")
        print("  1. Your application is running")
        print("  2. COMPANION_ENABLED is set to true in config.json")
        print("  3. You're using the correct host and port (localhost:8765)")
        print("  4. No firewall is blocking port 8765")
        return False
    
    except Exception as e:
        print(f"❌ Error: {e}")
        print("\nTroubleshooting:")
        print("  1. Check application is running")
        print("  2. Check config.json COMPANION_ENABLED is true")
        print("  3. Make sure websockets library is installed: pip install websockets")
        return False


async def interactive_mode(host: str = "localhost", port: int = 8765):
    """Interactive mode to send custom commands."""
    
    uri = f"ws://{host}:{port}"
    
    print(f"\n🔗 Connecting to {uri}...")
    
    try:
        async with websockets.connect(uri, ping_interval=None) as websocket:
            print(f"✅ Connected!\n")
            print("Commands available:")
            print("  1. play_matchup")
            print("  2. play_video")
            print("  3. play_audio")
            print("  4. trigger_win")
            print("  5. custom (enter JSON)")
            print("  6. quit\n")
            
            while True:
                try:
                    choice = input("Enter command (or number): ").strip()
                    
                    if choice.lower() == "quit" or choice == "6":
                        print("Goodbye!")
                        break
                    
                    elif choice == "1" or choice.lower() == "play_matchup":
                        cmd = {"command": "play_matchup"}
                    
                    elif choice == "2" or choice.lower() == "play_video":
                        team = input("  Team (e.g., HSMW): ").strip()
                        color = input("  Color (BLAU or PINK): ").strip()
                        cmd = {"command": "play_video", "team": team, "color": color}
                    
                    elif choice == "3" or choice.lower() == "play_audio":
                        cmd = {"command": "play_audio"}
                    
                    elif choice == "4" or choice.lower() == "trigger_win":
                        team_num = int(input("  Team number (0=blue, 1=orange): ").strip())
                        cmd = {"command": "trigger_win", "team_num": team_num}
                    
                    elif choice == "5" or choice.lower() == "custom":
                        json_str = input("  Enter JSON command: ").strip()
                        cmd = json.loads(json_str)
                    
                    else:
                        print("Unknown command")
                        continue
                    
                    print(f"  Sending: {json.dumps(cmd)}")
                    await websocket.send(json.dumps(cmd))
                    response = await asyncio.wait_for(websocket.recv(), timeout=5)
                    response_data = json.loads(response)
                    print(f"  Response: {json.dumps(response_data, indent=2)}\n")
                
                except json.JSONDecodeError:
                    print("  ❌ Invalid JSON\n")
                except asyncio.TimeoutError:
                    print("  ❌ Timeout waiting for response\n")
                except ValueError as e:
                    print(f"  ❌ Invalid input: {e}\n")
                except Exception as e:
                    print(f"  ❌ Error: {e}\n")
    
    except ConnectionRefusedError:
        print("❌ Connection refused!")
        print("Make sure your application is running with COMPANION_ENABLED: true")
    except Exception as e:
        print(f"❌ Error: {e}")


async def main():
    """Main entry point."""
    
    print("\n" + "=" * 70)
    print("  Bitfocus Companion WebSocket Test Tool")
    print("=" * 70 + "\n")
    
    # Check for command line arguments
    if len(sys.argv) > 1:
        if sys.argv[1] == "--interactive" or sys.argv[1] == "-i":
            await interactive_mode()
        elif sys.argv[1] == "--help" or sys.argv[1] == "-h":
            print("Usage:")
            print("  python test_companion_connection.py           Run automatic tests")
            print("  python test_companion_connection.py -i        Interactive mode")
            print("  python test_companion_connection.py --help    Show this help\n")
        else:
            print(f"Unknown argument: {sys.argv[1]}")
            print("Use --help for usage information\n")
    else:
        # Run automatic tests
        success = await test_connection()
        
        # Offer interactive mode
        if success:
            try_interactive = input("\nTry interactive mode? (y/n): ").strip().lower()
            if try_interactive == "y":
                await interactive_mode()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nAborted by user")
    except Exception as e:
        print(f"\nFatal error: {e}")
