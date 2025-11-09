"""
SOS OBS Video Player - Automated Video Playback Control System

This application bridges OBS (Open Broadcaster Software) with SOS (Rocket League tournament API) to automatically
play victory animations and audio when match events occur. It supports dual OBS instances for streaming and monitoring,
with a GUI for configuration and manual testing.

Key Features:
- Listens to SOS WebSocket events for match end notifications
- Automatically plays team-specific victory videos on match completion
- Plays audio stings synchronized across both OBS instances
- Displays matchup videos before matches
- GUI for configuration, match management, and manual testing
- Automatic retry logic for connection failures
- Real-time configuration persistence

Architecture:
- OBSSOSController: Main application logic and event handling
- ConfigGUI: Configuration interface and manual controls
- Async event loop: Handles SOS WebSocket listening
- Threading: Manages GUI and async operations concurrently
"""

import asyncio
import json
import os
import time
import threading
from obswebsocket import obsws, requests as obs_requests
import websockets
import tkinter as tk
from tkinter import ttk

# ============================================================================
# Configuration Constants
# ============================================================================

CONFIG_FILE = "config.json"

# Delay constants (in seconds) for hiding media sources after playback
HIDE_VIDEO_DELAY = 10          # Time to keep victory video visible
HIDE_MATCHUP_DELAY = 70        # Time to keep matchup video visible (full duration)
HIDE_AUDIO_DELAY = 5           # Time to keep audio playing before hiding source

# Connection retry settings
RETRY_DELAY = 5                # Seconds to wait before retrying connection
MAX_RETRY_ATTEMPTS = 0         # 0 = infinite retries

# WebSocket and API constants
OBS_WEBSOCKET_PORT = 4455      # Default OBS WebSocket port
SOS_WEBSOCKET_PORT = 49322     # Default SOS WebSocket port
COMPANION_WEBSOCKET_PORT = 55555  # Default Bitfocus Companion WebSocket port

# Global Config - wird durch GUI aktualisiert
config = {
    'BLUE_TEAM': "HSMW",
    'ORANGE_TEAM': "HSMW",
    'OBS_HOST': "localhost",
    'OBS_PORT': OBS_WEBSOCKET_PORT,
    'OBS_PASSWORD': "",
    'WIN_SCENE_NAME': "SCN Win Animation",
    'MATCHUP_SCENE_NAME': "SCN Matchup Animation",
    'AUDIO_SCENE_NAME': "SCN Musik-Output",
    'AUDIO_SOURCE_NAME': "MED Game Win Stinger Audio",
    'MATCHUP_AUDIO_SOURCE_NAME': "MED Matchup Audio",
    'MATCHUP_AUDIO_FINALE_SOURCE_NAME': "MED Matchup Audio Finale",
    'GOAL_VIDEO_SCENE_NAME': "SCN Goal Video",
    'GOAL_VIDEO_SOURCE_NAME': "MED Goal Video",
    'GOAL_AUDIO_SOURCE_NAME': "MED Goal Audio",
    'OBS2_HOST': "localhost",
    'OBS2_PORT': OBS_WEBSOCKET_PORT,
    'OBS2_PASSWORD': "",
    'SOS_HOST': "localhost",
    'SOS_PORT': SOS_WEBSOCKET_PORT,
    'COMPANION_WEBSOCKET_PORT': COMPANION_WEBSOCKET_PORT,  # WebSocket port for Bitfocus Companion
    'COMPANION_ENABLED': True,          # Enable/disable Companion integration
    'CURRENT_MATCH': 0,  # 0-6 für Match 1-7
    'MATCHES': [
        {'blue_team': "HSMW", 'orange_team': "UIA B"},
        {'blue_team': "TLU", 'orange_team': "WHZ"},
        {'blue_team': "LES", 'orange_team': "UIA B"},
        {'blue_team': "TLU", 'orange_team': "UIA A"},
        {'blue_team': "HSMW", 'orange_team': "LES"},
        {'blue_team': "UIA A", 'orange_team': "WHZ"},
        {'blue_team': "HSMW", 'orange_team': "HSMW"},
    ]
}

# Team Kürzel
TEAMS = ["HSMW", "LES", "UIA A", "UIA B", "WHZ", "TLU"]

def get_video_name(team_kuerzel: str, color: str) -> str:
    """Generate video filename for team victory animation.
    
    Args:
        team_kuerzel: Team abbreviation (e.g., 'HSMW', 'LES')
        color: Team color in German ('BLAU' for blue, 'PINK' for orange)
    
    Returns:
        Formatted video filename (e.g., 'WIN HSMW BLAU.mp4')
    """
    return f"WIN {team_kuerzel} {color}.mp4"

def normalize_team_name(team_name: str) -> str:
    """Normalize team name for matchup video lookup.
    
    Converts "UIA A" and "UIA B" to "UIA" for matchup videos.
    This allows using a single matchup video for both UIA variants.
    
    Args:
        team_name: Team name (e.g., 'HSMW', 'UIA A', 'UIA B')
    
    Returns:
        Normalized team name (e.g., 'HSMW', 'UIA', 'UIA')
    """
    # Remove " A" or " B" suffix if present (for UIA variants)
    if team_name.startswith("UIA"):
        return "UIA"
    return team_name

def save_config() -> None:
    """Persist current configuration to JSON file.
    
    Saves the global config dict to CONFIG_FILE. If file write fails,
    prints error message but doesn't raise exception.
    """
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=2)
        print(f"✓ Config gespeichert in {CONFIG_FILE}")
    except Exception as e:
        print(f"✗ Fehler beim Speichern der Config: {e}")

def load_config() -> bool:
    """Load configuration from JSON file.
    
    Loads configuration from CONFIG_FILE if it exists, merging with
    default values. If file doesn't exist, uses default values.
    
    Returns:
        True if config file was found and loaded, False otherwise
    """
    global config
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r') as f:
                loaded_config = json.load(f)
                # Merge mit defaults (falls neue Keys hinzugefügt wurden)
                config.update(loaded_config)
            print(f"✓ Config geladen aus {CONFIG_FILE}")
            return True
        else:
            print(f"ℹ Keine Config Datei gefunden, verwende Standard-Werte")
            return False
    except Exception as e:
        print(f"✗ Fehler beim Laden der Config: {e}")
        return False

def validate_config() -> tuple[bool, list[str]]:
    """Validate that all required configuration keys are present.
    
    Returns:
        Tuple of (is_valid: bool, missing_keys: list[str])
    """
    required_keys = [
        'OBS_HOST', 'OBS_PORT', 'OBS_PASSWORD',
        'OBS2_HOST', 'OBS2_PORT', 'OBS2_PASSWORD',
        'WIN_SCENE_NAME', 'MATCHUP_SCENE_NAME', 'AUDIO_SCENE_NAME', 'AUDIO_SOURCE_NAME',
        'SOS_HOST', 'SOS_PORT', 'MATCHES'
    ]
    
    missing_keys = [key for key in required_keys if key not in config]
    
    if missing_keys:
        return False, missing_keys
    return True, []

class OBSSOSController:
    """Main controller for OBS and SOS integration.
    
    Manages connections to two OBS instances and SOS WebSocket server.
    Listens for match end events and triggers automatic playback of videos
    and audio on both OBS instances.
    """
    
    def __init__(self) -> None:
        """Initialize controller with no active connections."""
        self.obs: obsws | None = None           # OBS instance 1 connection
        self.obs2: obsws | None = None          # OBS instance 2 connection
        self.sos_ws: websockets.WebSocketClientProtocol | None = None  # SOS connection
        self.obs_reconnect_task: asyncio.Task | None = None  # Task for OBS 1 reconnection monitoring
        self.obs2_reconnect_task: asyncio.Task | None = None  # Task for OBS 2 reconnection monitoring
    
    async def _connect_obs_instance(self, instance_num: int) -> bool:
        """Connect to OBS instance (1 or 2) with retry logic.
        
        Attempts to connect to the specified OBS instance using configured
        host/port/password. Automatically retries on failure with a delay.
        
        Args:
            instance_num: OBS instance number (1 or 2)
        
        Returns:
            True if connection successful, False if aborted
        
        Raises:
            Continues retrying indefinitely unless cancelled externally
        """
        config_prefix = '' if instance_num == 1 else '2'
        obs_attr = f'obs{config_prefix}'
        host_key = f'OBS{config_prefix}_HOST'
        port_key = f'OBS{config_prefix}_PORT'
        pass_key = f'OBS{config_prefix}_PASSWORD'
        
        retry_count = 0
        while True:
            try:
                obs_conn = obsws(config[host_key], config[port_key], config[pass_key])
                obs_conn.connect()
                setattr(self, obs_attr, obs_conn)
                print(f"✓ Mit OBS {instance_num} verbunden ({config[host_key]}:{config[port_key]})")
                return True
            except Exception as e:
                retry_count += 1
                print(f"⏳ OBS {instance_num} Wiederverbindung in {RETRY_DELAY} Sekunden... (Versuch {retry_count})")
                print(f"   Fehler: {e}")
                await asyncio.sleep(RETRY_DELAY)
    
    async def connect_obs_with_retry(self) -> bool:
        """Connect to OBS instance 1 with retry logic.
        
        Returns:
            True if connection successful
        """
        return await self._connect_obs_instance(1)
    
    async def connect_obs2_with_retry(self) -> bool:
        """Connect to OBS instance 2 with retry logic.
        
        Returns:
            True if connection successful
        """
        return await self._connect_obs_instance(2)
    
    async def connect_sos_with_retry(self) -> bool:
        """Connect to SOS WebSocket server with retry logic.
        
        Attempts to connect to SOS WebSocket at configured host/port.
        Automatically retries on failure with RETRY_DELAY between attempts.
        
        Returns:
            True if connection successful
        """
        retry_count = 0
        while True:
            try:
                self.sos_ws = await websockets.connect(f"ws://{config['SOS_HOST']}:{config['SOS_PORT']}")
                print(f"✓ Mit SOS verbunden ({config['SOS_HOST']}:{config['SOS_PORT']})")
                return True
            except Exception as e:
                retry_count += 1
                print(f"⏳ SOS Wiederverbindung in {RETRY_DELAY} Sekunden... (Versuch {retry_count})")
                print(f"   Fehler: {e}")
                await asyncio.sleep(RETRY_DELAY)
    
    def _is_obs_connected(self, obs_instance: obsws | None, obs_num: int) -> bool:
        """Check if OBS instance connection is still alive.
        
        Sends a ping-like request to verify the connection is active.
        
        Args:
            obs_instance: OBS WebSocket connection to check
            obs_num: OBS instance number (1 or 2) for logging
        
        Returns:
            True if connection is alive, False otherwise
        """
        if obs_instance is None:
            return False
        
        try:
            # Try to get version info as a heartbeat check
            obs_instance.call(obs_requests.GetVersion())
            return True
        except Exception as e:
            print(f"✗ OBS {obs_num} Verbindung verloren: {e}")
            return False
    
    async def _monitor_obs_connection(self, instance_num: int) -> None:
        """Monitor and reconnect OBS instance if connection is lost.
        
        Periodically checks if the OBS connection is still alive.
        If connection is lost, automatically attempts to reconnect.
        
        Args:
            instance_num: OBS instance number (1 or 2)
        """
        while True:
            try:
                await asyncio.sleep(RETRY_DELAY)
                
                obs_instance = self.obs if instance_num == 1 else self.obs2
                
                # Check if connection is still alive
                if obs_instance is not None and not self._is_obs_connected(obs_instance, instance_num):
                    print(f"⏳ OBS {instance_num} Verbindung unterbrochen - Wiederverbindung...")
                    
                    # Try to reconnect
                    await self._connect_obs_instance(instance_num)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"✗ Fehler bei OBS {instance_num} Monitoring: {e}")
                await asyncio.sleep(RETRY_DELAY)
    
    def _find_source_in_scene(self, obs_instance: obsws, scene_name: str, source_name: str, obs_num: int) -> int | None:
        """Find scene item ID for a media source in an OBS scene.
        
        Args:
            obs_instance: OBS WebSocket connection
            scene_name: Name of the OBS scene to search in
            source_name: Name of the media source to find
            obs_num: OBS instance number (1 or 2) for logging
        
        Returns:
            Scene item ID if found, None otherwise
        """
        try:
            scene_items = obs_instance.call(obs_requests.GetSceneItemList(sceneName=scene_name))
            for item in scene_items.datain['sceneItems']:
                if item['sourceName'] == source_name:
                    return item['sceneItemId']
            print(f"✗ Source '{source_name}' nicht gefunden in Scene '{scene_name}' (OBS {obs_num})")
            return None
        except Exception as e:
            print(f"✗ Fehler beim Suchen von '{source_name}' (OBS {obs_num}): {e}")
            return None
    
    def _play_media_on_obs(self, obs_instance: obsws, scene_name: str, source_name: str, obs_num: int, delay: float = HIDE_VIDEO_DELAY) -> None:
        """Play media source on OBS instance and hide after delay.
        
        Finds the media source in the scene, makes it visible, starts playback,
        and schedules it to be hidden after the specified delay in a background thread.
        
        Args:
            obs_instance: OBS WebSocket connection
            scene_name: Name of the OBS scene containing the source
            source_name: Name of the media source to play
            obs_num: OBS instance number (1 or 2) for logging
            delay: Seconds to wait before hiding the source (default: HIDE_VIDEO_DELAY)
        
        Raises:
            Exception: Propagates OBS communication errors
        """
        try:
            scene_item_id = self._find_source_in_scene(obs_instance, scene_name, source_name, obs_num)
            if scene_item_id is None:
                return
            
            obs_instance.call(obs_requests.SetSceneItemEnabled(
                sceneName=scene_name,
                sceneItemId=scene_item_id,
                sceneItemEnabled=True
            ))
            
            obs_instance.call(obs_requests.TriggerMediaInputAction(
                inputName=source_name,
                mediaAction="OBS_WEBSOCKET_MEDIA_INPUT_ACTION_RESTART"
            ))
            print(f"▶ Media gestartet (OBS {obs_num}): {source_name}")
            
            self._schedule_hide(obs_instance, scene_name, scene_item_id, source_name, obs_num, delay)
        except Exception as e:
            print(f"✗ Fehler beim Abspielen auf OBS {obs_num}: {e}")
    
    def _schedule_hide(self, obs_instance: obsws, scene_name: str, scene_item_id: int, source_name: str, obs_num: int, delay: float) -> None:
        """Schedule source to be hidden after delay in background thread.
        
        Starts a daemon thread that waits for the specified delay, then disables
        the scene item to hide the source.
        
        Args:
            obs_instance: OBS WebSocket connection
            scene_name: Name of the OBS scene
            scene_item_id: ID of the scene item to hide
            source_name: Name of the source (for logging)
            obs_num: OBS instance number (1 or 2) for logging
            delay: Seconds to wait before hiding
        """
        def hide_after_delay():
            time.sleep(delay)
            try:
                obs_instance.call(obs_requests.SetSceneItemEnabled(
                    sceneName=scene_name,
                    sceneItemId=scene_item_id,
                    sceneItemEnabled=False
                ))
                print(f"✓ Source versteckt (OBS {obs_num}): {source_name}")
            except Exception as e:
                print(f"✗ Fehler beim Verstecken (OBS {obs_num}): {e}")
        
        threading.Thread(target=hide_after_delay, daemon=True).start()
    
    def play_video(self, source_name: str) -> None:
        """Play victory video on both OBS instances.
        
        Plays the team-specific victory animation on both OBS instances
        simultaneously and automatically hides it after HIDE_VIDEO_DELAY seconds.
        Handles connection errors gracefully - failure on one instance doesn't
        prevent playback on the other.
        
        Args:
            source_name: Name of the video media source to play (e.g., 'WIN HSMW BLAU.mp4')
        """
        scene_name = config['WIN_SCENE_NAME']
        if not scene_name:
            print("✗ Win Video Scene nicht konfiguriert")
            return
        
        for obs, obs_num in [(self.obs, 1), (self.obs2, 2)]:
            if obs:
                try:
                    self._play_media_on_obs(obs, scene_name, source_name, obs_num, delay=HIDE_VIDEO_DELAY)
                except Exception as e:
                    print(f"✗ Fehler auf OBS {obs_num}: {e}")
            else:
                print(f"⚠ OBS {obs_num} nicht verbunden")
    
    def play_audio(self) -> None:
        """Play victory audio stinger on both OBS instances.
        
        Plays the configured audio source on both OBS instances and automatically
        hides it after HIDE_AUDIO_DELAY seconds. Typically used for sound effects
        like a victory jingle or crowd reaction.
        """
        scene_name = config['AUDIO_SCENE_NAME']
        source_name = config['AUDIO_SOURCE_NAME']
        if not scene_name or not source_name:
            print("✗ Audio Scene oder Source nicht konfiguriert")
            return
        
        for obs, obs_num in [(self.obs, 1), (self.obs2, 2)]:
            if obs:
                try:
                    self._play_media_on_obs(obs, scene_name, source_name, obs_num, delay=HIDE_AUDIO_DELAY)
                    print(f"♫ Audio gestartet (OBS {obs_num}): {source_name}")
                except Exception as e:
                    print(f"✗ Fehler beim Audio auf OBS {obs_num}: {e}")
    
    def play_goal_video(self) -> None:
        """Play goal video on both OBS instances.
        
        Plays the configured goal video source on both OBS instances and automatically
        hides it after HIDE_VIDEO_DELAY seconds. Triggered when a goal is scored.
        """
        scene_name = config['GOAL_VIDEO_SCENE_NAME']
        source_name = config['GOAL_VIDEO_SOURCE_NAME']
        if not scene_name or not source_name:
            print("✗ Goal Video Scene oder Source nicht konfiguriert")
            return
        
        for obs, obs_num in [(self.obs, 1), (self.obs2, 2)]:
            if obs:
                try:
                    self._play_media_on_obs(obs, scene_name, source_name, obs_num, delay=HIDE_VIDEO_DELAY)
                    print(f"⚽ Goal Video gestartet (OBS {obs_num}): {source_name}")
                except Exception as e:
                    print(f"✗ Fehler beim Goal Video auf OBS {obs_num}: {e}")
    
    def play_goal_audio(self) -> None:
        """Play goal audio on both OBS instances.
        
        Plays the configured goal audio source on both OBS instances and automatically
        hides it after HIDE_AUDIO_DELAY seconds. Triggered when a goal is scored.
        Uses the same scene as the victory audio (AUDIO_SCENE_NAME).
        """
        scene_name = config['AUDIO_SCENE_NAME']
        source_name = config['GOAL_AUDIO_SOURCE_NAME']
        if not scene_name or not source_name:
            print("✗ Goal Audio Source nicht konfiguriert")
            return
        
        for obs, obs_num in [(self.obs, 1), (self.obs2, 2)]:
            if obs:
                try:
                    self._play_media_on_obs(obs, scene_name, source_name, obs_num, delay=HIDE_AUDIO_DELAY)
                    print(f"⚽ Goal Audio gestartet (OBS {obs_num}): {source_name}")
                except Exception as e:
                    print(f"✗ Fehler beim Goal Audio auf OBS {obs_num}: {e}")
    
    def play_matchup_video(self) -> None:
        """Play matchup video and audio on both OBS instances.
        
        Plays the matchup animation showing the upcoming teams before the match starts,
        along with the appropriate audio (finale version for Match 7, regular otherwise).
        Automatically hides the video after HIDE_MATCHUP_DELAY seconds (typically the
        full length of the animation).
        
        Note: Team names are normalized (e.g., "UIA A" and "UIA B" both use "UIA" video)
        to allow using a single matchup video for all variants.
        """
        scene_name = config['MATCHUP_SCENE_NAME']
        if not scene_name:
            print("✗ Matchup Scene nicht konfiguriert")
            return
        
        if not self.obs and not self.obs2:
            print("✗ Keine OBS Instanz verfügbar")
            return
        
        match_idx = config['CURRENT_MATCH']
        match = config['MATCHES'][match_idx]
        
        # Normalize team names for matchup video lookup
        blue_normalized = normalize_team_name(match['blue_team'])
        orange_normalized = normalize_team_name(match['orange_team'])
        matchup_video = f"{blue_normalized} vs {orange_normalized}.mp4"
        
        # Determine which audio to play (finale for Match 7, regular for others)
        is_match_7 = (match_idx == 6)  # Match 7 is index 6
        audio_source = config['MATCHUP_AUDIO_FINALE_SOURCE_NAME'] if is_match_7 else config['MATCHUP_AUDIO_SOURCE_NAME']
        audio_scene = config['AUDIO_SCENE_NAME']
        
        for obs, obs_num in [(self.obs, 1), (self.obs2, 2)]:
            if obs:
                try:
                    # Play the video
                    self._play_media_on_obs(obs, scene_name, matchup_video, obs_num, delay=HIDE_MATCHUP_DELAY)
                    print(f"▶ Matchup Video gestartet (OBS {obs_num}): {matchup_video}")
                    
                    # Play the appropriate audio
                    if audio_source and audio_scene:
                        try:
                            self._play_media_on_obs(obs, audio_scene, audio_source, obs_num, delay=HIDE_AUDIO_DELAY)
                            audio_type = "Finale" if is_match_7 else "Regular"
                            print(f"🔊 Matchup Audio ({audio_type}) gestartet (OBS {obs_num}): {audio_source}")
                        except Exception as e:
                            print(f"✗ Fehler beim Matchup Audio auf OBS {obs_num}: {e}")
                except Exception as e:
                    print(f"✗ Fehler beim Matchup auf OBS {obs_num}: {e}")
    
    def hide_matchup_video(self) -> None:
        """Instantly hide matchup video on both OBS instances.
        
        Finds and disables all scene items in the matchup scene on both OBS instances.
        This provides instant control to stop the matchup video without waiting for
        the automatic hide timer.
        """
        scene_name = config['MATCHUP_SCENE_NAME']
        if not scene_name:
            print("✗ Matchup Scene nicht konfiguriert")
            return
        
        if not self.obs and not self.obs2:
            print("✗ Keine OBS Instanz verfügbar")
            return
        
        for obs, obs_num in [(self.obs, 1), (self.obs2, 2)]:
            if obs:
                try:
                    scene_items = obs.call(obs_requests.GetSceneItemList(sceneName=scene_name))
                    if scene_items and scene_items.datain and 'sceneItems' in scene_items.datain:
                        for item in scene_items.datain['sceneItems']:
                            obs.call(obs_requests.SetSceneItemEnabled(
                                sceneName=scene_name,
                                sceneItemId=item['sceneItemId'],
                                sceneItemEnabled=False
                            ))
                        print(f"✓ Matchup Video versteckt (OBS {obs_num}): {len(scene_items.datain['sceneItems'])} items disabled")
                    else:
                        print(f"ℹ Keine Items in Matchup Scene gefunden (OBS {obs_num})")
                except Exception as e:
                    print(f"✗ Fehler beim Verstecken des Matchup Videos (OBS {obs_num}): {e}")
    
    def handle_match_ended(self, winner_team_num: int) -> None:
        """Handle a match end event from SOS.
        
        Triggered when a match ends, this plays the appropriate victory video
        and audio for the winning team on both OBS instances.
        
        Args:
            winner_team_num: Team number that won (0 for blue/cyan, 1 for orange/pink)
        """
        match_idx = config['CURRENT_MATCH']
        match = config['MATCHES'][match_idx]
        
        if winner_team_num == 0:  # Blue gewonnen
            print(f"🎉 BLUE TEAM GEWINNT (Match {match_idx + 1})!")
            video_name = get_video_name(match['blue_team'], "BLAU")
            self.play_video(video_name)
        else:  # Orange gewonnen
            print(f"🎉 ORANGE TEAM GEWINNT (Match {match_idx + 1})!")
            video_name = get_video_name(match['orange_team'], "PINK")
            self.play_video(video_name)
        
        # Spiele auch Audio ab
        self.play_audio()
    
    def handle_goal_scored(self) -> None:
        """Handle a goal scored event from SOS.
        
        Triggered when a goal is scored, this plays the goal video and audio
        on both OBS instances simultaneously.
        """
        print("⚽ GOAL SCORED!")
        self.play_goal_video()
        self.play_goal_audio()
    
    async def listen_sos_events(self) -> None:
        """Listen for SOS WebSocket events with automatic reconnection.
        
        Continuously monitors the SOS connection for match end events.
        On connection loss, automatically attempts to reconnect.
        Handles deserialization of JSON events and triggers appropriate actions.
        """
        while True:
            try:
                async for message in self.sos_ws:
                    data = json.loads(message)
                    event = data.get('event', 'unknown')
                    
                    if event == 'game:match_ended':
                        print("🎮 Match Ended Event!")
                        
                        # winner_team_num ist unter data.data verschachtelt
                        winner_team_num = data.get('data', {}).get('winner_team_num')
                        
                        if winner_team_num is not None:
                            self.handle_match_ended(winner_team_num)
                        else:
                            print("✗ Kein winner_team_num gefunden!")

                    if event == 'game:goal_scored':
                        self.handle_goal_scored()
                        
            except websockets.exceptions.ConnectionClosed:
                print("✗ SOS Verbindung geschlossen - Wiederverbindung wird versucht...")
                await self.connect_sos_with_retry()
            except Exception as e:
                print(f"✗ Fehler: {e} - Wiederverbindung wird versucht...")
                await asyncio.sleep(5)
                await self.connect_sos_with_retry()
    
    async def start_companion_server(self) -> None:
        """Start WebSocket server for Bitfocus Companion integration.
        
        Listens on localhost:COMPANION_WEBSOCKET_PORT for JSON commands
        from Bitfocus Companion. Supported commands:
        - {"command": "play_matchup"} - Triggers matchup video
        - {"command": "play_video", "team": "HSMW", "color": "BLAU"} - Play team video
        - {"command": "play_audio"} - Play audio stinger
        - {"command": "trigger_win", "team_num": 0} - Simulate match end (0=blue, 1=orange)
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
            
            elif cmd == "trigger_win":
                team_num = command.get("team_num")
                if team_num is not None:
                    self.handle_match_ended(team_num)
                    team_name = "Blue/Cyan" if team_num == 0 else "Orange/Pink"
                    await websocket.send(json.dumps({
                        "status": "success",
                        "command": "trigger_win",
                        "team": team_name
                    }))
                else:
                    await websocket.send(json.dumps({
                        "status": "error",
                        "message": "Missing 'team_num' parameter (0=blue, 1=orange)"
                    }))
            
            elif cmd == "set_match":
                match_idx = command.get("match_index")
                if match_idx is not None and 0 <= match_idx < len(config['MATCHES']):
                    config['CURRENT_MATCH'] = match_idx
                    save_config()
                    match = config['MATCHES'][match_idx]
                    await websocket.send(json.dumps({
                        "status": "success",
                        "command": "set_match",
                        "match_index": match_idx,
                        "match_number": match_idx + 1,
                        "blue_team": match['blue_team'],
                        "orange_team": match['orange_team']
                    }))
                    print(f"📺 Companion set match to: Match {match_idx + 1} ({match['blue_team']} vs {match['orange_team']})")
                else:
                    await websocket.send(json.dumps({
                        "status": "error",
                        "message": f"Invalid 'match_index'. Must be between 0 and {len(config['MATCHES']) - 1}"
                    }))
            
            elif cmd == "get_current_match":
                match_idx = config['CURRENT_MATCH']
                match = config['MATCHES'][match_idx]
                await websocket.send(json.dumps({
                    "status": "success",
                    "command": "get_current_match",
                    "match_index": match_idx,
                    "match_number": match_idx + 1,
                    "blue_team": match['blue_team'],
                    "orange_team": match['orange_team']
                }))
            
            elif cmd == "list_matches":
                matches_list = [
                    {
                        "match_index": i,
                        "match_number": i + 1,
                        "blue_team": match['blue_team'],
                        "orange_team": match['orange_team']
                    }
                    for i, match in enumerate(config['MATCHES'])
                ]
                await websocket.send(json.dumps({
                    "status": "success",
                    "command": "list_matches",
                    "matches": matches_list,
                    "current_match_index": config['CURRENT_MATCH']
                }))
            
            elif cmd == "hide_matchup":
                self.hide_matchup_video()
                await websocket.send(json.dumps({
                    "status": "success",
                    "command": "hide_matchup",
                    "message": "Matchup video hidden on all OBS instances"
                }))
            
            else:
                await websocket.send(json.dumps({
                    "status": "error",
                    "message": f"Unknown command: {cmd}. Valid commands: play_matchup, play_video, play_audio, trigger_win, set_match, get_current_match, list_matches, hide_matchup"
                }))
        
        except Exception as e:
            await websocket.send(json.dumps({
                "status": "error",
                "message": str(e)
            }))
    
    async def run(self) -> None:
        """Main async event loop.
        
        Initializes connections to both OBS instances and SOS WebSocket server.
        Coordinates concurrent connection attempts and starts event listening.
        Optionally starts Companion WebSocket server if enabled.
        Handles graceful shutdown when interrupted or on errors.
        """
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
        
        # Start OBS connection monitoring tasks
        if self.obs:
            self.obs_reconnect_task = asyncio.create_task(self._monitor_obs_connection(1))
        if self.obs2:
            self.obs2_reconnect_task = asyncio.create_task(self._monitor_obs_connection(2))
        
        try:
            await self.listen_sos_events()
        except KeyboardInterrupt:
            print("\n⏹ Beendet")
        finally:
            # Cancel all monitoring tasks
            if self.obs_reconnect_task:
                self.obs_reconnect_task.cancel()
                try:
                    await self.obs_reconnect_task
                except asyncio.CancelledError:
                    pass
            if self.obs2_reconnect_task:
                self.obs2_reconnect_task.cancel()
                try:
                    await self.obs2_reconnect_task
                except asyncio.CancelledError:
                    pass
            if companion_task:
                companion_task.cancel()
                try:
                    await companion_task
                except asyncio.CancelledError:
                    pass
            if self.obs:
                self.obs.disconnect()
            if self.obs2:
                self.obs2.disconnect()
            if self.sos_ws:
                await self.sos_ws.close()

class ConfigGUI:
    """Configuration GUI for OBS SOS Video Player.
    
    Provides a graphical interface for configuring OBS instances, SOS connection,
    scene names, matches, and manual testing of video playback.
    """
    
    def __init__(self, root: tk.Tk) -> None:
        """Initialize configuration GUI.
        
        Args:
            root: Tkinter root window
        """
        self.root = root
        self.root.title("OBS SOS Video Player - Konfiguration")
        self.root.geometry("620x700")
        self.root.resizable(True, True)
        
        # Track config section collapse state
        self.config_collapsed = False
        
        # Create Canvas with Scrollbar
        canvas = tk.Canvas(root)
        scrollbar = ttk.Scrollbar(root, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Pack Canvas and Scrollbar
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        main_frame = scrollable_frame
        
        # Title with Collapse Button
        title_frame = ttk.Frame(main_frame)
        title_frame.grid(row=0, column=0, columnspan=6, pady=10, sticky="ew", padx=10)
        
        title = ttk.Label(title_frame, text="Konfiguration", font=("Arial", 14, "bold"))
        title.pack(side="left")
        
        collapse_btn = ttk.Button(title_frame, text="▼ Collapse", command=self.toggle_config_collapse, width=12)
        collapse_btn.pack(side="right")
        self.collapse_btn = collapse_btn
        
        # Frame to hold all config fields (this will be hidden/shown)
        self.config_fields_frame = ttk.Frame(main_frame)
        self.config_fields_frame.grid(row=1, column=0, columnspan=6, sticky="ew", padx=10)
        
        # OBS 1 Configuration Section
        obs_label = ttk.Label(self.config_fields_frame, text="OBS 1 WebSocket", font=("Arial", 11, "bold"), foreground="blue")
        obs_label.grid(row=0, column=0, columnspan=2, pady=(10, 5), sticky="w")
        
        # OBS 2 Configuration Section
        obs2_label = ttk.Label(self.config_fields_frame, text="OBS 2 WebSocket", font=("Arial", 11, "bold"), foreground="blue")
        obs2_label.grid(row=0, column=2, columnspan=2, pady=(10, 5), sticky="w")
        
        # OBS 1 Host
        self.obs_host_input = self._create_config_field(self.config_fields_frame, "Host:", 1, 0, config['OBS_HOST'])
        
        # OBS 2 Host
        self.obs2_host_input = self._create_config_field(self.config_fields_frame, "Host:", 1, 2, config['OBS2_HOST'])
        
        # OBS 1 Port
        self.obs_port_input = self._create_config_field(self.config_fields_frame, "Port:", 2, 0, str(config['OBS_PORT']))
        
        # OBS 2 Port
        self.obs2_port_input = self._create_config_field(self.config_fields_frame, "Port:", 2, 2, str(config['OBS2_PORT']))
        
        # OBS 1 Password
        self.obs_password_input = self._create_config_field(self.config_fields_frame, "Password:", 3, 0, config['OBS_PASSWORD'], show="*")
        
        # OBS 2 Password
        self.obs2_password_input = self._create_config_field(self.config_fields_frame, "Password:", 3, 2, config['OBS2_PASSWORD'], show="*")
        
        # SOS Configuration Section
        sos_label = ttk.Label(self.config_fields_frame, text="SOS WebSocket", font=("Arial", 11, "bold"), foreground="blue")
        sos_label.grid(row=4, column=2, columnspan=2, pady=(10, 5), sticky="w")
        
        # SOS Host
        self.sos_host_input = self._create_config_field(self.config_fields_frame, "Host:", 5, 2, config['SOS_HOST'])
        
        # SOS Port
        self.sos_port_input = self._create_config_field(self.config_fields_frame, "Port:", 6, 2, str(config['SOS_PORT']))
        
        # Win Video Scene Name
        self.obs_scene_input = self._create_config_field(self.config_fields_frame, "Win Video Scene:", 4, 0, config['WIN_SCENE_NAME'])
        
        # Audio Scene Name
        self.audio_scene_input = self._create_config_field(self.config_fields_frame, "Audio Scene:", 5, 0, config['AUDIO_SCENE_NAME'])
        
        # Audio Source Name (Win Stinger)
        self.audio_source_input = self._create_config_field(self.config_fields_frame, "Win Audio Source:", 6, 0, config['AUDIO_SOURCE_NAME'])
        
        # Matchup Scene Name
        self.matchup_scene_input = self._create_config_field(self.config_fields_frame, "Matchup Scene:", 7, 0, config['MATCHUP_SCENE_NAME'])
        
        # Matchup Audio Source Name
        self.matchup_audio_source_input = self._create_config_field(self.config_fields_frame, "Matchup Audio:", 8, 0, config['MATCHUP_AUDIO_SOURCE_NAME'])
        
        # Matchup Audio Finale Source Name
        self.matchup_audio_finale_source_input = self._create_config_field(self.config_fields_frame, "Matchup Audio Finale:", 9, 0, config['MATCHUP_AUDIO_FINALE_SOURCE_NAME'])
        
        # Goal Video Scene Name
        self.goal_video_scene_input = self._create_config_field(self.config_fields_frame, "Goal Video Scene:", 10, 0, config['GOAL_VIDEO_SCENE_NAME'])
        
        # Goal Video Source Name
        self.goal_video_source_input = self._create_config_field(self.config_fields_frame, "Goal Video Source:", 11, 0, config['GOAL_VIDEO_SOURCE_NAME'])
        
        # Goal Audio Source Name
        self.goal_audio_source_input = self._create_config_field(self.config_fields_frame, "Goal Audio Source:", 12, 0, config['GOAL_AUDIO_SOURCE_NAME'])
        
        # Play Matchup Button
        self.play_matchup_btn = ttk.Button(main_frame, text="▶ Play Matchup", command=self.play_matchup)
        self.play_matchup_btn.grid(row=2, column=0, columnspan=2, padx=20, pady=5, sticky="w")
        
        # Hide Matchup Button
        self.hide_matchup_btn = ttk.Button(main_frame, text="✕ Hide Matchup", command=self.hide_matchup)
        self.hide_matchup_btn.grid(row=2, column=2, columnspan=2, padx=20, pady=5, sticky="w")
        
        # Matches Section
        matches_label = ttk.Label(main_frame, text="Matches", font=("Arial", 11, "bold"), foreground="blue")
        matches_label.grid(row=3, column=0, columnspan=4, pady=(15, 10), sticky="w", padx=10)
        
        # Column headers
        ttk.Label(main_frame, text="Match", font=("Arial", 9, "bold")).grid(row=4, column=0, padx=10, pady=5, sticky="w")
        ttk.Label(main_frame, text="Cyan Team", font=("Arial", 9, "bold")).grid(row=4, column=1, padx=10, pady=5, sticky="w")
        ttk.Label(main_frame, text="Pink Team", font=("Arial", 9, "bold")).grid(row=4, column=2, padx=10, pady=5, sticky="w")
        ttk.Label(main_frame, text="Test", font=("Arial", 9, "bold")).grid(row=4, column=3, padx=10, pady=5, sticky="w")
        
        self.match_vars = []
        self.match_dropdowns_blue = []
        self.match_dropdowns_orange = []
        
        # Create 7 matches
        for i in range(7):
            row = 5 + i
            
            # Current Match Checkbox
            var = tk.BooleanVar(value=(i == config['CURRENT_MATCH']))
            self.match_vars.append(var)
            
            check = ttk.Checkbutton(main_frame, text=f"Match {i+1}", variable=var, 
                                   command=lambda idx=i: self.set_current_match(idx))
            check.grid(row=row, column=0, padx=20, pady=5, sticky="w")
            
            # Blue Team Dropdown
            blue_dropdown = ttk.Combobox(main_frame, values=TEAMS, state="readonly", width=13)
            blue_dropdown.set(config['MATCHES'][i]['blue_team'])
            blue_dropdown.grid(row=row, column=1, padx=10, pady=5, sticky="w")
            blue_dropdown.bind('<<ComboboxSelected>>', lambda e, idx=i: self.update_match(idx, 'blue'))
            self.match_dropdowns_blue.append(blue_dropdown)
            
            # Orange Team Dropdown
            orange_dropdown = ttk.Combobox(main_frame, values=TEAMS, state="readonly", width=13)
            orange_dropdown.set(config['MATCHES'][i]['orange_team'])
            orange_dropdown.grid(row=row, column=2, padx=10, pady=5, sticky="w")
            orange_dropdown.bind('<<ComboboxSelected>>', lambda e, idx=i: self.update_match(idx, 'orange'))
            self.match_dropdowns_orange.append(orange_dropdown)
            
            # WIN Button Frame to hold both buttons
            button_frame = ttk.Frame(main_frame)
            button_frame.grid(row=row, column=3, padx=10, pady=5, sticky="w")
            
            # WIN Cyan Button
            win_blue_btn = ttk.Button(button_frame, text=f"WIN CYAN", width=11,
                                     command=lambda idx=i: self.test_win(idx, 0))
            win_blue_btn.pack(side="left", padx=2)
            
            # WIN Pink Button
            win_orange_btn = ttk.Button(button_frame, text=f"WIN PINK", width=11,
                                       command=lambda idx=i: self.test_win(idx, 1))
            win_orange_btn.pack(side="left", padx=2)
    
    def _create_config_field(self, parent: ttk.Frame, label: str, row: int, column: int, default_value: str, show: str = "") -> ttk.Entry:
        """Create a labeled configuration input field.
        
        Helper method to reduce repetitive field creation code in the GUI.
        Creates a label and Entry widget in a grid layout, pre-fills with
        default value, and binds change handler.
        
        Args:
            parent: Parent frame to add the widgets to
            label: Label text to display
            row: Grid row number
            column: Grid column number
            default_value: Default value to insert into the Entry
            show: Character to show in field (empty for text, "*" for passwords)
        
        Returns:
            The created ttk.Entry widget
        """
        ttk.Label(parent, text=label).grid(row=row, column=column, sticky="w", padx=20, pady=5)
        entry = ttk.Entry(parent, width=18, show=show)
        entry.insert(0, default_value)
        entry.grid(row=row, column=column + 1, padx=20, pady=5, sticky="w")
        entry.bind('<KeyRelease>', self.update_config)
        return entry
    
    def toggle_config_collapse(self) -> None:
        """Toggle collapse/expand state of the configuration section.
        
        Hides or shows all configuration fields above the Matches section.
        """
        self.config_collapsed = not self.config_collapsed
        if self.config_collapsed:
            self.config_fields_frame.grid_remove()
            self.collapse_btn.config(text="▶ Expand")
        else:
            self.config_fields_frame.grid()
            self.collapse_btn.config(text="▼ Collapse")
    
    def set_current_match(self, match_idx: int) -> None:
        """Set the current match for manual testing.
        
        Deselects all other matches and saves the configuration.
        
        Args:
            match_idx: Index of the match to set as current (0-6)
        """
        # Deselect all other matches
        for i, var in enumerate(self.match_vars):
            if i != match_idx:
                var.set(False)
            else:
                var.set(True)
        
        config['CURRENT_MATCH'] = match_idx
        save_config()
        print(f"🎯 Aktuelles Match geändert zu: Match {match_idx + 1}")
    
    def update_match(self, match_idx: int, team_type: str) -> None:
        """Update match teams from dropdown selections.
        
        Args:
            match_idx: Index of the match (0-6)
            team_type: Team to update ('blue' or 'orange')
        """
        if team_type == 'blue':
            config['MATCHES'][match_idx]['blue_team'] = self.match_dropdowns_blue[match_idx].get()
        else:
            config['MATCHES'][match_idx]['orange_team'] = self.match_dropdowns_orange[match_idx].get()
        save_config()
    
    def update_config(self, event=None) -> None:
        """Update configuration in real-time as user types.
        
        Called on every KeyRelease event in any config field.
        Updates the global config dict and persists to file.
        Handles type conversion for port numbers gracefully.
        
        Args:
            event: Tkinter event object (optional, ignored)
        """
        config['OBS_HOST'] = self.obs_host_input.get()
        try:
            config['OBS_PORT'] = int(self.obs_port_input.get())
        except ValueError:
            pass
        config['OBS_PASSWORD'] = self.obs_password_input.get()
        
        config['OBS2_HOST'] = self.obs2_host_input.get()
        try:
            config['OBS2_PORT'] = int(self.obs2_port_input.get())
        except ValueError:
            pass
        config['OBS2_PASSWORD'] = self.obs2_password_input.get()
        
        config['WIN_SCENE_NAME'] = self.obs_scene_input.get()
        config['MATCHUP_SCENE_NAME'] = self.matchup_scene_input.get()
        config['AUDIO_SCENE_NAME'] = self.audio_scene_input.get()
        config['AUDIO_SOURCE_NAME'] = self.audio_source_input.get()
        config['MATCHUP_AUDIO_SOURCE_NAME'] = self.matchup_audio_source_input.get()
        config['MATCHUP_AUDIO_FINALE_SOURCE_NAME'] = self.matchup_audio_finale_source_input.get()
        
        config['GOAL_VIDEO_SCENE_NAME'] = self.goal_video_scene_input.get()
        config['GOAL_VIDEO_SOURCE_NAME'] = self.goal_video_source_input.get()
        config['GOAL_AUDIO_SOURCE_NAME'] = self.goal_audio_source_input.get()
        
        config['SOS_HOST'] = self.sos_host_input.get()
        try:
            config['SOS_PORT'] = int(self.sos_port_input.get())
        except ValueError:
            pass
        
        save_config()
    
    def test_win(self, match_idx: int, winner_team_num: int) -> None:
        """Manually trigger victory video for testing.
        
        Allows manual testing of victory videos and audio without waiting for
        actual SOS events. Sets the match as current and simulates a match end.
        
        Args:
            match_idx: Index of the match (0-6)
            winner_team_num: Team number that won (0 for blue, 1 for orange)
        """
        # Setze das Match als aktuell
        config['CURRENT_MATCH'] = match_idx
        
        # Rufe die handle_match_ended Funktion im Controller auf
        if hasattr(self, 'controller') and self.controller:
            self.controller.handle_match_ended(winner_team_num)
            print(f"🧪 Test: Match {match_idx + 1} - Team {winner_team_num} gewinnt")
        else:
            print("✗ Controller nicht verfügbar")
    
    def play_matchup(self) -> None:
        """Manually trigger matchup video for testing.
        
        Allows manual playback of the current matchup video animation
        without waiting for automatic schedule.
        """
        # Der Controller wird global gespeichert, daher können wir ihn hier zugreifen
        if hasattr(self, 'controller') and self.controller:
            self.controller.play_matchup_video()
        else:
            print("✗ Controller nicht verfügbar")
    
    def hide_matchup(self) -> None:
        """Manually hide matchup video on all OBS instances.
        
        Instantly hides the matchup video without waiting for the automatic timer.
        Useful for manual control when you need to stop playback immediately.
        """
        if hasattr(self, 'controller') and self.controller:
            self.controller.hide_matchup_video()
        else:
            print("✗ Controller nicht verfügbar")

def run_async_in_thread(loop: asyncio.AbstractEventLoop, controller: OBSSOSController) -> None:
    """Run async event loop in a dedicated thread.
    
    Args:
        loop: The asyncio event loop to run
        controller: The OBSSOSController instance to execute
    """
    asyncio.set_event_loop(loop)
    loop.run_until_complete(controller.run())

async def main() -> None:
    """Alternative main entry point for direct async execution.
    
    Creates and runs the OBSSOSController directly without GUI.
    """
    controller = OBSSOSController()
    await controller.run()

# Global controller instance shared between GUI and async loop
app_controller: OBSSOSController | None = None

if __name__ == "__main__":
    """Application entry point.
    
    1. Loads configuration from file (or uses defaults)
    2. Validates configuration
    3. Creates GUI for configuration and manual controls
    4. Starts OBSSOSController in background thread
    5. Runs GUI main loop
    """
    # Lade Config
    load_config()
    
    # Starte GUI
    root = tk.Tk()
    gui = ConfigGUI(root)
    
    # Erstelle Controller
    app_controller = OBSSOSController()
    gui.controller = app_controller
    
    # Starte Async Loop in separatem Thread
    loop = asyncio.new_event_loop()
    thread = threading.Thread(target=run_async_in_thread, args=(loop, app_controller), daemon=True)
    thread.start()
    
    # Starte GUI Main Loop
    root.mainloop()