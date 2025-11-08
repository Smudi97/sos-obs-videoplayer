import asyncio
import json
import os
from obswebsocket import obsws, requests as obs_requests
import websockets
import tkinter as tk
from tkinter import ttk
import threading

CONFIG_FILE = "config.json"

# Global Config - wird durch GUI aktualisiert
config = {
    'BLUE_TEAM': "HSMW",
    'ORANGE_TEAM': "HSMW",
    'OBS_HOST': "localhost",
    'OBS_PORT': 4455,
    'OBS_PASSWORD': "",
    'WIN_SCENE_NAME': "SCN Win Animation",
    'MATCHUP_SCENE_NAME': "SCN Matchup Animation",
    'AUDIO_SCENE_NAME': "SCN Musik-Output",
    'AUDIO_SOURCE_NAME': "MED Game Win Stinger Audio",
    'OBS2_HOST': "localhost",
    'OBS2_PORT': 4455,
    'OBS2_PASSWORD': "",
    'SOS_HOST': "localhost",
    'SOS_PORT': 49322,
    'CURRENT_MATCH': 0,  # 0-6 für Match 1-7
    'MATCHES': [
        {'blue_team': "HSMW", 'orange_team': "UIA B"},
        {'blue_team': "WHZ", 'orange_team': "TLU"},
        {'blue_team': "LES", 'orange_team': "UIA B"},
        {'blue_team': "TLU", 'orange_team': "UIA A"},
        {'blue_team': "HSMW", 'orange_team': "LES"},
        {'blue_team': "UIA A", 'orange_team': "WHZ"},
        {'blue_team': "HSMW", 'orange_team': "HSMW"},
    ]
}

# Team Kürzel
TEAMS = ["HSMW", "LES", "UIA A", "UIA B", "WHZ", "TLU"]

def get_video_name(team_kuerzel, color):
    """Generiere Video-Namen nach dem Muster: WIN [TEAM] [COLOR].mp4"""
    return f"WIN {team_kuerzel} {color}.mp4"

def save_config():
    """Speichere Config in JSON Datei"""
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=2)
        print(f"✓ Config gespeichert in {CONFIG_FILE}")
    except Exception as e:
        print(f"✗ Fehler beim Speichern der Config: {e}")

def load_config():
    """Lade Config aus JSON Datei"""
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

class OBSSOSController:
    def __init__(self):
        self.obs = None
        self.obs2 = None
        self.sos_ws = None
        
    async def connect_obs(self):
        """Verbindung zu OBS WebSocket herstellen"""
        try:
            self.obs = obsws(config['OBS_HOST'], config['OBS_PORT'], config['OBS_PASSWORD'])
            self.obs.connect()
            print(f"✓ Mit OBS verbunden ({config['OBS_HOST']}:{config['OBS_PORT']})")
            return True
        except Exception as e:
            print(f"✗ OBS Fehler: {e}")
            return False
    
    async def connect_obs_with_retry(self, max_retries=None):
        """Verbindung zu OBS mit automatischen Wiederholung"""
        retry_count = 0
        while True:
            if await self.connect_obs():
                return True
            retry_count += 1
            print(f"⏳ OBS Wiederverbindung in 5 Sekunden... (Versuch {retry_count})")
            await asyncio.sleep(5)
    
    async def connect_obs2(self):
        """Verbindung zu zweiter OBS WebSocket herstellen"""
        try:
            self.obs2 = obsws(config['OBS2_HOST'], config['OBS2_PORT'], config['OBS2_PASSWORD'])
            self.obs2.connect()
            print(f"✓ Mit OBS 2 verbunden ({config['OBS2_HOST']}:{config['OBS2_PORT']})")
            return True
        except Exception as e:
            print(f"✗ OBS 2 Fehler: {e}")
            return False
    
    async def connect_obs2_with_retry(self, max_retries=None):
        """Verbindung zu zweiter OBS mit automatischen Wiederholung"""
        retry_count = 0
        while True:
            if await self.connect_obs2():
                return True
            retry_count += 1
            print(f"⏳ OBS 2 Wiederverbindung in 5 Sekunden... (Versuch {retry_count})")
            await asyncio.sleep(5)
    
    async def connect_sos(self):
        """Verbindung zu SOS WebSocket herstellen"""
        try:
            self.sos_ws = await websockets.connect(f"ws://{config['SOS_HOST']}:{config['SOS_PORT']}")
            print(f"✓ Mit SOS verbunden ({config['SOS_HOST']}:{config['SOS_PORT']})")
            return True
        except Exception as e:
            print(f"✗ SOS Fehler: {e}")
            return False
    
    async def connect_sos_with_retry(self, max_retries=None):
        """Verbindung zu SOS mit automatischen Wiederholung"""
        retry_count = 0
        while True:
            if await self.connect_sos():
                return True
            retry_count += 1
            print(f"⏳ Wiederverbindung in 5 Sekunden... (Versuch {retry_count})")
            await asyncio.sleep(5)
    
    def ensure_obs_connected(self):
        """Stelle sicher, dass OBS verbunden ist, versuche sonst neu zu verbinden"""
        if self.obs is None:
            print("⚠ OBS nicht verbunden, versuche zu verbinden...")
            asyncio.create_task(self.connect_obs_with_retry())
            return False
        return True
    
    def play_video(self, source_name):
        """Video abspielen und anzeigen auf beiden OBS Instanzen"""
        # Versuche auf beiden OBS Instanzen zu spielen, fehlgeschlagene sollten nicht andere blockieren
        if self.obs:
            try:
                self._play_video_on_obs(self.obs, source_name, 1)
            except Exception as e:
                print(f"✗ Fehler auf OBS 1: {e}")
        else:
            print("⚠ OBS 1 nicht verbunden")
        
        if self.obs2:
            try:
                self._play_video_on_obs(self.obs2, source_name, 2)
            except Exception as e:
                print(f"✗ Fehler auf OBS 2: {e}")
        else:
            print("⚠ OBS 2 nicht verbunden")
        
        if not self.obs and not self.obs2:
            print("✗ Keine OBS Instanz verfügbar, Video kann nicht abgespielt werden")
    
    def _play_video_on_obs(self, obs_instance, source_name, obs_num):
        """Spiele Video auf einer bestimmten OBS Instanz ab"""
        try:
            # Nutze konfigurierte Scene oder aktuelle Scene
            if config['WIN_SCENE_NAME']:
                scene_name = config['WIN_SCENE_NAME']
            else:
                current_scene = obs_instance.call(obs_requests.GetCurrentProgramScene())
                scene_name = current_scene.datain['currentProgramSceneName']
            
            # Finde Scene Item ID
            scene_items = obs_instance.call(obs_requests.GetSceneItemList(sceneName=scene_name))
            scene_item_id = None
            for item in scene_items.datain['sceneItems']:
                if item['sourceName'] == source_name:
                    scene_item_id = item['sceneItemId']
                    break
            
            if scene_item_id is None:
                print(f"✗ Source '{source_name}' nicht gefunden in OBS {obs_num}")
                return
            
            # Source sichtbar machen
            obs_instance.call(obs_requests.SetSceneItemEnabled(
                sceneName=scene_name,
                sceneItemId=scene_item_id,
                sceneItemEnabled=True
            ))
            print(f"✓ Source sichtbar gemacht (OBS {obs_num}): {source_name}")
            
            # Video abspielen
            obs_instance.call(obs_requests.TriggerMediaInputAction(
                inputName=source_name,
                mediaAction="OBS_WEBSOCKET_MEDIA_INPUT_ACTION_RESTART"
            ))
            print(f"▶ Video gestartet (OBS {obs_num}): {source_name}")
            
            # Source nach dem Video wieder unsichtbar machen (asynchron)
            self.hide_video_later(obs_instance, scene_name, scene_item_id, source_name, obs_num)
            
        except Exception as e:
            print(f"✗ Fehler beim Abspielen auf OBS {obs_num}: {e}")
            raise
    
    def hide_video_later(self, obs_instance, scene_name, scene_item_id, source_name, obs_num, delay=10):
        """Verstecke Video nach Verzögerung in separatem Thread"""
        def hide():
            import time
            time.sleep(delay)
            try:
                obs_instance.call(obs_requests.SetSceneItemEnabled(
                    sceneName=scene_name,
                    sceneItemId=scene_item_id,
                    sceneItemEnabled=False
                ))
                print(f"✓ Source versteckt (OBS {obs_num}): {source_name}")
            except Exception as e:
                print(f"✗ Fehler beim Verstecken auf OBS {obs_num}: {e}")
        
        hide_thread = threading.Thread(target=hide, daemon=True)
        hide_thread.start()
    
    def play_audio(self):
        """Spiele Win Audio auf beiden OBS Instanzen ab"""
        if not config['AUDIO_SCENE_NAME'] or not config['AUDIO_SOURCE_NAME']:
            print("✗ Audio Scene oder Source nicht konfiguriert")
            return
        
        # Versuche auf beiden OBS Instanzen zu spielen
        if self.obs:
            try:
                self._play_audio_on_obs(self.obs, 1)
            except Exception as e:
                print(f"✗ Fehler beim Audio auf OBS 1: {e}")
        
        if self.obs2:
            try:
                self._play_audio_on_obs(self.obs2, 2)
            except Exception as e:
                print(f"✗ Fehler beim Audio auf OBS 2: {e}")
    
    def _play_audio_on_obs(self, obs_instance, obs_num):
        """Spiele Audio auf einer bestimmten OBS Instanz ab"""
        try:
            scene_name = config['AUDIO_SCENE_NAME']
            source_name = config['AUDIO_SOURCE_NAME']
            
            # Finde Scene Item ID
            scene_items = obs_instance.call(obs_requests.GetSceneItemList(sceneName=scene_name))
            scene_item_id = None
            for item in scene_items.datain['sceneItems']:
                if item['sourceName'] == source_name:
                    scene_item_id = item['sceneItemId']
                    break
            
            if scene_item_id is None:
                print(f"✗ Audio Source '{source_name}' nicht gefunden in Scene '{scene_name}' (OBS {obs_num})")
                return
            
            # Audio abspielen
            obs_instance.call(obs_requests.TriggerMediaInputAction(
                inputName=source_name,
                mediaAction="OBS_WEBSOCKET_MEDIA_INPUT_ACTION_RESTART"
            ))
            print(f"♫ Audio gestartet (OBS {obs_num}): {source_name}")
            
        except Exception as e:
            print(f"✗ Fehler beim Abspielen des Audio auf OBS {obs_num}: {e}")
            raise
    
    def handle_match_ended(self, winner_team_num):
        """Match beendet - spiele Video und Audio ab"""
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
    
    def play_matchup_video(self):
        """Spiele Matchup Video mit aktuellem Match auf beiden OBS Instanzen"""
        if not config['MATCHUP_SCENE_NAME']:
            print("✗ Matchup Scene nicht konfiguriert")
            return
        
        if not self.obs and not self.obs2:
            print("✗ Keine OBS Instanz verfügbar")
            return
        
        match_idx = config['CURRENT_MATCH']
        match = config['MATCHES'][match_idx]
        blue_team = match['blue_team']
        orange_team = match['orange_team']
        
        # Generiere Matchup Video Namen
        matchup_video = f"{blue_team} vs {orange_team}.mp4"
        
        # Versuche auf beiden OBS Instanzen zu spielen
        if self.obs:
            try:
                self._play_matchup_on_obs(self.obs, matchup_video, 1)
            except Exception as e:
                print(f"✗ Fehler beim Matchup auf OBS 1: {e}")
        
        if self.obs2:
            try:
                self._play_matchup_on_obs(self.obs2, matchup_video, 2)
            except Exception as e:
                print(f"✗ Fehler beim Matchup auf OBS 2: {e}")
    
    def _play_matchup_on_obs(self, obs_instance, matchup_video, obs_num):
        """Spiele Matchup Video auf einer bestimmten OBS Instanz ab"""
        try:
            scene_name = config['MATCHUP_SCENE_NAME']
            
            # Finde Scene Item ID
            scene_items = obs_instance.call(obs_requests.GetSceneItemList(sceneName=scene_name))
            scene_item_id = None
            for item in scene_items.datain['sceneItems']:
                if item['sourceName'] == matchup_video:
                    scene_item_id = item['sceneItemId']
                    break
            
            if scene_item_id is None:
                print(f"✗ Matchup Video '{matchup_video}' nicht gefunden in Scene '{scene_name}' (OBS {obs_num})")
                return
            
            # Source sichtbar machen
            obs_instance.call(obs_requests.SetSceneItemEnabled(
                sceneName=scene_name,
                sceneItemId=scene_item_id,
                sceneItemEnabled=True
            ))
            print(f"✓ Matchup Source sichtbar (OBS {obs_num}): {matchup_video}")
            
            # Video abspielen
            obs_instance.call(obs_requests.TriggerMediaInputAction(
                inputName=matchup_video,
                mediaAction="OBS_WEBSOCKET_MEDIA_INPUT_ACTION_RESTART"
            ))
            print(f"▶ Matchup Video gestartet (OBS {obs_num}): {matchup_video}")
            
            # Source nach 77 Sekunden wieder unsichtbar machen (asynchron)
            self.hide_video_later(obs_instance, scene_name, scene_item_id, matchup_video, obs_num, delay=77)
            
        except Exception as e:
            print(f"✗ Fehler beim Abspielen des Matchup Videos auf OBS {obs_num}: {e}")
            raise
    
    async def listen_sos_events(self):
        """Auf SOS Events lauschen mit automatischer Wiederverbindung"""
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
                        
            except websockets.exceptions.ConnectionClosed:
                print("✗ SOS Verbindung geschlossen - Wiederverbindung wird versucht...")
                await self.connect_sos_with_retry()
            except Exception as e:
                print(f"✗ Fehler: {e} - Wiederverbindung wird versucht...")
                await asyncio.sleep(5)
                await self.connect_sos_with_retry()
    
    async def run(self):
        """Hauptloop"""
        print("=== OBS + SOS Video Player ===\n")
        
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
            if self.obs:
                self.obs.disconnect()
            if self.obs2:
                self.obs2.disconnect()
            if self.sos_ws:
                await self.sos_ws.close()

class ConfigGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("OBS SOS Video Player - Konfiguration")
        self.root.geometry("620x700")
        self.root.resizable(True, True)
        
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
        
        # Title
        title = ttk.Label(main_frame, text="Konfiguration", font=("Arial", 14, "bold"))
        title.grid(row=0, column=0, columnspan=6, pady=10, sticky="w", padx=10)
        
        # OBS 1 Configuration Section
        obs_label = ttk.Label(main_frame, text="OBS 1 WebSocket", font=("Arial", 11, "bold"), foreground="blue")
        obs_label.grid(row=1, column=0, columnspan=2, pady=(10, 5), sticky="w", padx=10)
        
        # OBS 2 Configuration Section
        obs2_label = ttk.Label(main_frame, text="OBS 2 WebSocket", font=("Arial", 11, "bold"), foreground="blue")
        obs2_label.grid(row=1, column=2, columnspan=2, pady=(10, 5), sticky="w", padx=10)
        
        # OBS 1 Host
        ttk.Label(main_frame, text="Host:").grid(row=2, column=0, sticky="w", padx=20, pady=5)
        self.obs_host_input = ttk.Entry(main_frame, width=18)
        self.obs_host_input.insert(0, config['OBS_HOST'])
        self.obs_host_input.grid(row=2, column=1, padx=20, pady=5, sticky="w")
        self.obs_host_input.bind('<KeyRelease>', self.update_config)
        
        # OBS 2 Host
        ttk.Label(main_frame, text="Host:").grid(row=2, column=2, sticky="w", padx=20, pady=5)
        self.obs2_host_input = ttk.Entry(main_frame, width=18)
        self.obs2_host_input.insert(0, config['OBS2_HOST'])
        self.obs2_host_input.grid(row=2, column=3, padx=20, pady=5, sticky="w")
        self.obs2_host_input.bind('<KeyRelease>', self.update_config)
        
        # OBS 1 Port
        ttk.Label(main_frame, text="Port:").grid(row=3, column=0, sticky="w", padx=20, pady=5)
        self.obs_port_input = ttk.Entry(main_frame, width=18)
        self.obs_port_input.insert(0, str(config['OBS_PORT']))
        self.obs_port_input.grid(row=3, column=1, padx=20, pady=5, sticky="w")
        self.obs_port_input.bind('<KeyRelease>', self.update_config)
        
        # OBS 2 Port
        ttk.Label(main_frame, text="Port:").grid(row=3, column=2, sticky="w", padx=20, pady=5)
        self.obs2_port_input = ttk.Entry(main_frame, width=18)
        self.obs2_port_input.insert(0, str(config['OBS2_PORT']))
        self.obs2_port_input.grid(row=3, column=3, padx=20, pady=5, sticky="w")
        self.obs2_port_input.bind('<KeyRelease>', self.update_config)
        
        # OBS 1 Password
        ttk.Label(main_frame, text="Password:").grid(row=4, column=0, sticky="w", padx=20, pady=5)
        self.obs_password_input = ttk.Entry(main_frame, width=18, show="*")
        self.obs_password_input.insert(0, config['OBS_PASSWORD'])
        self.obs_password_input.grid(row=4, column=1, padx=20, pady=5, sticky="w")
        self.obs_password_input.bind('<KeyRelease>', self.update_config)
        
        # OBS 2 Password
        ttk.Label(main_frame, text="Password:").grid(row=4, column=2, sticky="w", padx=20, pady=5)
        self.obs2_password_input = ttk.Entry(main_frame, width=18, show="*")
        self.obs2_password_input.insert(0, config['OBS2_PASSWORD'])
        self.obs2_password_input.grid(row=4, column=3, padx=20, pady=5, sticky="w")
        self.obs2_password_input.bind('<KeyRelease>', self.update_config)
        
        # SOS Configuration Section
        sos_label = ttk.Label(main_frame, text="SOS WebSocket", font=("Arial", 11, "bold"), foreground="blue")
        sos_label.grid(row=5, column=2, columnspan=2, pady=(10, 5), sticky="w", padx=10)
        
        # SOS Host
        ttk.Label(main_frame, text="Host:").grid(row=6, column=2, sticky="w", padx=20, pady=5)
        self.sos_host_input = ttk.Entry(main_frame, width=18)
        self.sos_host_input.insert(0, config['SOS_HOST'])
        self.sos_host_input.grid(row=6, column=3, padx=20, pady=5, sticky="w")
        self.sos_host_input.bind('<KeyRelease>', self.update_config)
        
        # SOS Port
        ttk.Label(main_frame, text="Port:").grid(row=7, column=2, sticky="w", padx=20, pady=5)
        self.sos_port_input = ttk.Entry(main_frame, width=18)
        self.sos_port_input.insert(0, str(config['SOS_PORT']))
        self.sos_port_input.grid(row=7, column=3, padx=20, pady=5, sticky="w")
        self.sos_port_input.bind('<KeyRelease>', self.update_config)
        
        # Winchamber Scene Name
        ttk.Label(main_frame, text="Win Video Scene:").grid(row=5, column=0, sticky="w", padx=20, pady=5)
        self.obs_scene_input = ttk.Entry(main_frame, width=18)
        self.obs_scene_input.insert(0, config['WIN_SCENE_NAME'])
        self.obs_scene_input.grid(row=5, column=1, padx=20, pady=5, sticky="w")
        self.obs_scene_input.bind('<KeyRelease>', self.update_config)
        
        # Matchup Scene Name
        ttk.Label(main_frame, text="Matchup Scene:").grid(row=6, column=0, sticky="w", padx=20, pady=5)
        self.matchup_scene_input = ttk.Entry(main_frame, width=18)
        self.matchup_scene_input.insert(0, config['MATCHUP_SCENE_NAME'])
        self.matchup_scene_input.grid(row=6, column=1, padx=20, pady=5, sticky="w")
        self.matchup_scene_input.bind('<KeyRelease>', self.update_config)
        
        # Audio Scene Name
        ttk.Label(main_frame, text="Audio Scene:").grid(row=7, column=0, sticky="w", padx=20, pady=5)
        self.audio_scene_input = ttk.Entry(main_frame, width=18)
        self.audio_scene_input.insert(0, config['AUDIO_SCENE_NAME'])
        self.audio_scene_input.grid(row=7, column=1, padx=20, pady=5, sticky="w")
        self.audio_scene_input.bind('<KeyRelease>', self.update_config)
        
        # Audio Source Name
        ttk.Label(main_frame, text="Audio Source:").grid(row=8, column=0, sticky="w", padx=20, pady=5)
        self.audio_source_input = ttk.Entry(main_frame, width=18)
        self.audio_source_input.insert(0, config['AUDIO_SOURCE_NAME'])
        self.audio_source_input.grid(row=8, column=1, padx=20, pady=5, sticky="w")
        self.audio_source_input.bind('<KeyRelease>', self.update_config)
        
        # Play Matchup Button
        self.play_matchup_btn = ttk.Button(main_frame, text="▶ Play Matchup", command=self.play_matchup)
        self.play_matchup_btn.grid(row=9, column=0, columnspan=2, padx=20, pady=5, sticky="w")
        
        # Matches Section
        matches_label = ttk.Label(main_frame, text="Matches", font=("Arial", 11, "bold"), foreground="blue")
        matches_label.grid(row=10, column=0, columnspan=4, pady=(15, 10), sticky="w", padx=10)
        
        # Column headers
        ttk.Label(main_frame, text="Match", font=("Arial", 9, "bold")).grid(row=11, column=0, padx=10, pady=5, sticky="w")
        ttk.Label(main_frame, text="Cyan Team", font=("Arial", 9, "bold")).grid(row=11, column=1, padx=10, pady=5, sticky="w")
        ttk.Label(main_frame, text="Pink Team", font=("Arial", 9, "bold")).grid(row=11, column=2, padx=10, pady=5, sticky="w")
        ttk.Label(main_frame, text="Test", font=("Arial", 9, "bold")).grid(row=11, column=3, padx=10, pady=5, sticky="w")
        
        self.match_vars = []
        self.match_dropdowns_blue = []
        self.match_dropdowns_orange = []
        
        # Create 7 matches
        for i in range(7):
            row = 12 + i
            
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
    
    def set_current_match(self, match_idx):
        """Setze aktuelles Match"""
        # Deselect all other matches
        for i, var in enumerate(self.match_vars):
            if i != match_idx:
                var.set(False)
            else:
                var.set(True)
        
        config['CURRENT_MATCH'] = match_idx
        save_config()
        print(f"🎯 Aktuelles Match geändert zu: Match {match_idx + 1}")
    
    def update_match(self, match_idx, team_type):
        """Update Match Teams"""
        if team_type == 'blue':
            config['MATCHES'][match_idx]['blue_team'] = self.match_dropdowns_blue[match_idx].get()
        else:
            config['MATCHES'][match_idx]['orange_team'] = self.match_dropdowns_orange[match_idx].get()
        save_config()
    
    def update_config(self, event=None):
        """Aktualisiere Config in Echtzeit"""
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
        
        config['SOS_HOST'] = self.sos_host_input.get()
        try:
            config['SOS_PORT'] = int(self.sos_port_input.get())
        except ValueError:
            pass
        
        save_config()
    
    def test_win(self, match_idx, winner_team_num):
        """Test Funktion um Sieg manuell zu triggern"""
        # Setze das Match als aktuell
        config['CURRENT_MATCH'] = match_idx
        
        # Rufe die handle_match_ended Funktion im Controller auf
        if hasattr(self, 'controller') and self.controller:
            self.controller.handle_match_ended(winner_team_num)
            print(f"🧪 Test: Match {match_idx + 1} - Team {winner_team_num} gewinnt")
        else:
            print("✗ Controller nicht verfügbar")
    
    def play_matchup(self):
        """Rufe play_matchup_video im Controller auf"""
        # Der Controller wird global gespeichert, daher können wir ihn hier zugreifen
        if hasattr(self, 'controller') and self.controller:
            self.controller.play_matchup_video()
        else:
            print("✗ Controller nicht verfügbar")

def run_async_in_thread(loop, controller):
    """Führe den Async Loop in einem Thread aus"""
    asyncio.set_event_loop(loop)
    loop.run_until_complete(controller.run())

async def main():
    controller = OBSSOSController()
    await controller.run()

# Global controller instance
app_controller = None

if __name__ == "__main__":
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