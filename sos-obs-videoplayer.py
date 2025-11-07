import asyncio
import json
from obswebsocket import obsws, requests as obs_requests
import websockets
import tkinter as tk
from tkinter import ttk
import threading

# Konfiguration
OBS_HOST = "localhost"
OBS_PORT = 4455
OBS_PASSWORD = "your_password_here"

SOS_HOST = "localhost"
SOS_PORT = 49122

# Global Config - wird durch GUI aktualisiert
config = {
    'BLUE_TEAM': "HSMW",
    'ORANGE_TEAM': "HSMW",
    'OBS_HOST': "localhost",
    'OBS_PORT': 4455,
    'OBS_PASSWORD': "",
    'OBS_SCENE_NAME': "",
    'CURRENT_MATCH': 0,  # 0-5 für Match 1-6
    'MATCHES': [
        {'blue_team': "HSMW", 'orange_team': "UIA"},
        {'blue_team': "WHZ", 'orange_team': "TLU"},
        {'blue_team': "LES", 'orange_team': "UIA"},
        {'blue_team': "TLU", 'orange_team': "UIA"},
        {'blue_team': "HSMW", 'orange_team': "LES"},
        {'blue_team': "UIA", 'orange_team': "WHZ"},
    ]
}

# Team Kürzel
TEAMS = ["HSMW", "LES", "UIA", "WHZ", "TLU"]

def get_video_name(team_kuerzel, color):
    """Generiere Video-Namen nach dem Muster: WIN [TEAM] [COLOR].mp4"""
    return f"WIN {team_kuerzel} {color}.mp4"

class OBSSOSController:
    def __init__(self):
        self.obs = None
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
    
    async def connect_sos(self):
        """Verbindung zu SOS WebSocket herstellen"""
        try:
            self.sos_ws = await websockets.connect(f"ws://{SOS_HOST}:{SOS_PORT}")
            print(f"✓ Mit SOS verbunden")
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
        """Video abspielen und anzeigen"""
        if not self.ensure_obs_connected():
            print("✗ OBS nicht verfügbar, Video kann nicht abgespielt werden")
            return
            
        try:
            # Nutze konfigurierte Scene oder aktuelle Scene
            if config['OBS_SCENE_NAME']:
                scene_name = config['OBS_SCENE_NAME']
            else:
                current_scene = self.obs.call(obs_requests.GetCurrentProgramScene())
                scene_name = current_scene.datain['currentProgramSceneName']
            
            # Finde Scene Item ID
            scene_items = self.obs.call(obs_requests.GetSceneItemList(sceneName=scene_name))
            scene_item_id = None
            for item in scene_items.datain['sceneItems']:
                if item['sourceName'] == source_name:
                    scene_item_id = item['sceneItemId']
                    break
            
            if scene_item_id is None:
                print(f"✗ Source '{source_name}' nicht gefunden")
                return
            
            # Source sichtbar machen
            self.obs.call(obs_requests.SetSceneItemEnabled(
                sceneName=scene_name,
                sceneItemId=scene_item_id,
                sceneItemEnabled=True
            ))
            print(f"✓ Source sichtbar gemacht: {source_name}")
            
            # Video abspielen
            self.obs.call(obs_requests.TriggerMediaInputAction(
                inputName=source_name,
                mediaAction="OBS_WEBSOCKET_MEDIA_INPUT_ACTION_RESTART"
            ))
            print(f"▶ Video gestartet: {source_name}")
            
            # Source nach dem Video wieder unsichtbar machen (asynchron)
            self.hide_video_later(scene_name, scene_item_id, source_name)
            
        except Exception as e:
            print(f"✗ Fehler beim Abspielen: {e}")
    
    def hide_video_later(self, scene_name, scene_item_id, source_name):
        """Verstecke Video nach Verzögerung in separatem Thread"""
        def hide():
            import time
            time.sleep(10)  # Warte 10 Sekunden (anpassen falls nötig)
            try:
                self.obs.call(obs_requests.SetSceneItemEnabled(
                    sceneName=scene_name,
                    sceneItemId=scene_item_id,
                    sceneItemEnabled=False
                ))
                print(f"✓ Source versteckt: {source_name}")
            except Exception as e:
                print(f"✗ Fehler beim Verstecken: {e}")
        
        hide_thread = threading.Thread(target=hide, daemon=True)
        hide_thread.start()
    
    def handle_match_ended(self, winner_team_num):
        """Match beendet - spiele Video ab"""
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
        
        if not await self.connect_obs_with_retry():
            return
        
        if not await self.connect_sos_with_retry():
            self.obs.disconnect()
            return
        
        print("🎯 Bereit!\n")
        
        try:
            await self.listen_sos_events()
        except KeyboardInterrupt:
            print("\n⏹ Beendet")
        finally:
            if self.obs:
                self.obs.disconnect()
            if self.sos_ws:
                await self.sos_ws.close()

class ConfigGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("OBS SOS Video Player - Konfiguration")
        self.root.geometry("700x650")
        self.root.resizable(False, True)
        
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
        title.grid(row=0, column=0, columnspan=3, pady=10, sticky="w", padx=10)
        
        # OBS Configuration Section
        obs_label = ttk.Label(main_frame, text="OBS WebSocket", font=("Arial", 11, "bold"), foreground="blue")
        obs_label.grid(row=1, column=0, columnspan=3, pady=(10, 5), sticky="w", padx=10)
        
        # OBS Host
        ttk.Label(main_frame, text="Host:").grid(row=2, column=0, sticky="w", padx=20, pady=5)
        self.obs_host_input = ttk.Entry(main_frame, width=25)
        self.obs_host_input.insert(0, config['OBS_HOST'])
        self.obs_host_input.grid(row=2, column=1, padx=20, pady=5, sticky="w")
        self.obs_host_input.bind('<KeyRelease>', self.update_config)
        
        # OBS Port
        ttk.Label(main_frame, text="Port:").grid(row=3, column=0, sticky="w", padx=20, pady=5)
        self.obs_port_input = ttk.Entry(main_frame, width=25)
        self.obs_port_input.insert(0, str(config['OBS_PORT']))
        self.obs_port_input.grid(row=3, column=1, padx=20, pady=5, sticky="w")
        self.obs_port_input.bind('<KeyRelease>', self.update_config)
        
        # OBS Password
        ttk.Label(main_frame, text="Password:").grid(row=4, column=0, sticky="w", padx=20, pady=5)
        self.obs_password_input = ttk.Entry(main_frame, width=25, show="*")
        self.obs_password_input.insert(0, config['OBS_PASSWORD'])
        self.obs_password_input.grid(row=4, column=1, padx=20, pady=5, sticky="w")
        self.obs_password_input.bind('<KeyRelease>', self.update_config)
        
        # OBS Scene Name
        ttk.Label(main_frame, text="Scene Name:").grid(row=5, column=0, sticky="w", padx=20, pady=5)
        self.obs_scene_input = ttk.Entry(main_frame, width=25)
        self.obs_scene_input.insert(0, config['OBS_SCENE_NAME'])
        self.obs_scene_input.grid(row=5, column=1, padx=20, pady=5, sticky="w")
        self.obs_scene_input.bind('<KeyRelease>', self.update_config)
        
        # Matches Section
        matches_label = ttk.Label(main_frame, text="Matches", font=("Arial", 11, "bold"), foreground="blue")
        matches_label.grid(row=6, column=0, columnspan=3, pady=(15, 10), sticky="w", padx=10)
        
        # Column headers
        ttk.Label(main_frame, text="Match", font=("Arial", 9, "bold")).grid(row=7, column=0, padx=10, pady=5, sticky="w")
        ttk.Label(main_frame, text="Blue Team", font=("Arial", 9, "bold")).grid(row=7, column=1, padx=10, pady=5, sticky="w")
        ttk.Label(main_frame, text="Orange Team", font=("Arial", 9, "bold")).grid(row=7, column=2, padx=10, pady=5, sticky="w")
        
        self.match_vars = []
        self.match_dropdowns_blue = []
        self.match_dropdowns_orange = []
        
        # Create 6 matches
        for i in range(6):
            row = 8 + i
            
            # Current Match Checkbox
            var = tk.BooleanVar(value=(i == config['CURRENT_MATCH']))
            self.match_vars.append(var)
            
            check = ttk.Checkbutton(main_frame, text=f"Match {i+1}", variable=var, 
                                   command=lambda idx=i: self.set_current_match(idx))
            check.grid(row=row, column=0, padx=20, pady=5, sticky="w")
            
            # Blue Team Dropdown
            blue_dropdown = ttk.Combobox(main_frame, values=TEAMS, state="readonly", width=15)
            blue_dropdown.set(config['MATCHES'][i]['blue_team'])
            blue_dropdown.grid(row=row, column=1, padx=10, pady=5, sticky="w")
            blue_dropdown.bind('<<ComboboxSelected>>', lambda e, idx=i: self.update_match(idx, 'blue'))
            self.match_dropdowns_blue.append(blue_dropdown)
            
            # Orange Team Dropdown
            orange_dropdown = ttk.Combobox(main_frame, values=TEAMS, state="readonly", width=15)
            orange_dropdown.set(config['MATCHES'][i]['orange_team'])
            orange_dropdown.grid(row=row, column=2, padx=10, pady=5, sticky="w")
            orange_dropdown.bind('<<ComboboxSelected>>', lambda e, idx=i: self.update_match(idx, 'orange'))
            self.match_dropdowns_orange.append(orange_dropdown)
        
        # Status Label
        row = 14
        self.status_label = ttk.Label(main_frame, text="🟢 Läuft", font=("Arial", 10), foreground="green")
        self.status_label.grid(row=row, column=0, columnspan=3, pady=20)
    
    def set_current_match(self, match_idx):
        """Setze aktuelles Match"""
        # Deselect all other matches
        for i, var in enumerate(self.match_vars):
            if i != match_idx:
                var.set(False)
            else:
                var.set(True)
        
        config['CURRENT_MATCH'] = match_idx
        print(f"🎯 Aktuelles Match geändert zu: Match {match_idx + 1}")
    
    def update_match(self, match_idx, team_type):
        """Update Match Teams"""
        if team_type == 'blue':
            config['MATCHES'][match_idx]['blue_team'] = self.match_dropdowns_blue[match_idx].get()
        else:
            config['MATCHES'][match_idx]['orange_team'] = self.match_dropdowns_orange[match_idx].get()
    
    def update_config(self, event=None):
        """Aktualisiere Config in Echtzeit"""
        config['OBS_HOST'] = self.obs_host_input.get()
        try:
            config['OBS_PORT'] = int(self.obs_port_input.get())
        except ValueError:
            pass
        config['OBS_PASSWORD'] = self.obs_password_input.get()
        config['OBS_SCENE_NAME'] = self.obs_scene_input.get()

def run_async_in_thread(loop):
    """Führe den Async Loop in einem Thread aus"""
    asyncio.set_event_loop(loop)
    loop.run_until_complete(main())

async def main():
    controller = OBSSOSController()
    await controller.run()

if __name__ == "__main__":
    # Starte GUI
    root = tk.Tk()
    gui = ConfigGUI(root)
    
    # Starte Async Loop in separatem Thread
    loop = asyncio.new_event_loop()
    thread = threading.Thread(target=run_async_in_thread, args=(loop,), daemon=True)
    thread.start()
    
    # Starte GUI Main Loop
    root.mainloop()