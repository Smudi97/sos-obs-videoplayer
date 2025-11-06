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
            self.obs = obsws(OBS_HOST, OBS_PORT, OBS_PASSWORD)
            self.obs.connect()
            print(f"✓ Mit OBS verbunden")
            return True
        except Exception as e:
            print(f"✗ OBS Fehler: {e}")
            return False
    
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
    
    def play_video(self, source_name):
        """Video abspielen und anzeigen"""
        try:
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
        if winner_team_num == 0:  # Blue gewonnen
            print("🎉 BLUE TEAM GEWINNT!")
            video_name = get_video_name(config['BLUE_TEAM'], "BLAU")
            self.play_video(video_name)
        else:  # Orange gewonnen
            print("🎉 ORANGE TEAM GEWINNT!")
            video_name = get_video_name(config['ORANGE_TEAM'], "PINK")
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
        
        if not await self.connect_obs():
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
        self.root.title("OBS SOS Video Player")
        self.root.geometry("400x220")
        self.root.resizable(False, False)
        
        # Title
        title = ttk.Label(root, text="Team Auswahl", font=("Arial", 14, "bold"))
        title.grid(row=0, column=0, columnspan=2, pady=20)
        
        # Blue Team Label und Dropdown
        ttk.Label(root, text="Blue Team:").grid(row=1, column=0, sticky="w", padx=20, pady=10)
        self.blue_dropdown = ttk.Combobox(root, values=TEAMS, state="readonly", width=27)
        self.blue_dropdown.set(config['BLUE_TEAM'])
        self.blue_dropdown.grid(row=1, column=1, padx=20, pady=10)
        self.blue_dropdown.bind('<<ComboboxSelected>>', self.update_config)
        
        # Orange Team Label und Dropdown
        ttk.Label(root, text="Orange Team:").grid(row=2, column=0, sticky="w", padx=20, pady=10)
        self.orange_dropdown = ttk.Combobox(root, values=TEAMS, state="readonly", width=27)
        self.orange_dropdown.set(config['ORANGE_TEAM'])
        self.orange_dropdown.grid(row=2, column=1, padx=20, pady=10)
        self.orange_dropdown.bind('<<ComboboxSelected>>', self.update_config)
        
        # Status Label
        self.status_label = ttk.Label(root, text="🟢 Läuft", font=("Arial", 10), foreground="green")
        self.status_label.grid(row=3, column=0, columnspan=2, pady=15)
        
    def update_config(self, event=None):
        """Aktualisiere Config in Echtzeit"""
        config['BLUE_TEAM'] = self.blue_dropdown.get()
        config['ORANGE_TEAM'] = self.orange_dropdown.get()

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