import sys
import os
import tkinter as tk
from tkinter import messagebox
import customtkinter
from customtkinter import CTk, CTkFrame, CTkLabel, CTkButton, CTkSlider, set_appearance_mode, set_default_color_theme, CTkProgressBar
from PIL import Image, ImageTk
import requests
from io import BytesIO
from pynput import keyboard
import spotipy
from spotipy.oauth2 import SpotifyPKCE
import time
import json
import threading
import webbrowser
from flask import Flask, request, redirect

# -------------------------------
# Hilfsfunktion zur Ermittlung des Ressourcenpfads
# -------------------------------
def resource_path(relative_path):
    """
    Liefert den absoluten Pfad zur Ressource, funktioniert sowohl im
    Entwicklungsmodus als auch bei gebündelten EXE-Dateien mit PyInstaller.
    """
    try:
        # Bei einem gebündelten EXE enthält sys._MEIPASS den Pfad zum temporären Ordner.
        base_path = sys._MEIPASS
    except AttributeError:
        # Andernfalls wird das aktuelle Arbeitsverzeichnis verwendet.
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

# --- Konfiguration laden ---
def load_config():
    try:
        with open(resource_path('config.json'), 'r') as file:
            config = json.load(file)
        return config
    except FileNotFoundError:
        print("Config file not found.")
        sys.exit(1)  # sys.exit verwenden anstelle von exit
    except json.JSONDecodeError:
        print("Error decoding the config file.")
        sys.exit(1)

config = load_config()
SPOTIFY_CLIENT_ID = config["spotify_client_id"]
HOTKEY = config["hotkey"]
THEME = config.get("theme", "dark-blue")  # Standardwert ist "dark-blue"

# --- Globale Variablen für das Overlay ---
overlay = None
cover_label = None
song_label = None
progress_bar = None
overlay_visible = False
overlay_x, overlay_y = 100, 100
dragging = False
last_update_time = 0
current_track_id = None
current_cover_url = None
sp = None  # Spotify API-Objekt
tk_play = None
tk_pause = None
play_pause_btn = None

# Pfad, in dem das Token (Cache) gespeichert wird
CACHE_PATH = ".cache-spotify"

# --- Flask-App für OAuth-Callback (Port 8080) ---
flask_app = Flask(__name__)
flask_app.secret_key = "39738100218255042701803603745812"  # Beliebiger Schlüssel

# Erstelle einen globalen SpotifyPKCE-Manager – dieser speichert den Token im CACHE_PATH.
sp_oauth = SpotifyPKCE(
    client_id=SPOTIFY_CLIENT_ID,
    redirect_uri="http://localhost:8080/callback",
    scope="user-modify-playback-state user-read-playback-state user-read-currently-playing",
    cache_path=CACHE_PATH,
    open_browser=False
)

@flask_app.route("/")
def flask_index():
    """Startseite der Flask-App, prüft ob ein Token vorhanden ist."""
    token_info = sp_oauth.get_cached_token()
    if token_info:
        return "Token bereits vorhanden. Du kannst jetzt fortfahren."
    else:
        auth_url = sp_oauth.get_authorize_url()
        return redirect(auth_url)

@flask_app.route("/callback")
def flask_callback():
    """Callback-Route für die Spotify-Authentifizierung."""
    code = request.args.get("code")
    if code:
        token_info = sp_oauth.get_access_token(code)
        return "Autorisierung erfolgreich! Du kannst dieses Fenster schließen."
    else:
        return "Autorisierung fehlgeschlagen.", 401

def run_flask():
    """Startet den Flask-Server."""
    flask_app.run(port=8080, debug=False, use_reloader=False)

# --- Spotify initialisieren (verwende Redirect-URI mit /callback) ---
def initialize_spotify():
    """Initialisiert das Spotify-API-Objekt."""
    return spotipy.Spotify(auth_manager=SpotifyPKCE(
        client_id=SPOTIFY_CLIENT_ID,
        redirect_uri="http://localhost:8080/callback",
        scope="user-modify-playback-state user-read-playback-state user-read-currently-playing",
        cache_path=CACHE_PATH
    ))

# --- Funktionen für das Overlay (Play/Pause, Update, Lautstärke, etc.) ---
def play_pause():
    """Pausiert oder startet die Wiedergabe."""
    try:
        playback = sp.current_playback()
        if not playback:
            return

        if playback["is_playing"]:
            sp.pause_playback()
            play_pause_btn.configure(image=tk_play)
            print("Musik pausiert")
        else:
            sp.start_playback()
            play_pause_btn.configure(image=tk_pause)
            print("Musik fortgesetzt")
        time.sleep(0.5)
        update_overlay(force=True)
    except spotipy.exceptions.SpotifyException as e:
        messagebox.showwarning("API-Warning", f"Spotify-API-Meldung: {e}")
        print(f"Details: {e}")

def update_overlay(force=False):
    """Aktualisiert das Overlay mit den aktuellen Wiedergabeinformationen."""
    global last_update_time, current_track_id, current_cover_url
    current_time = time.time()
    if current_time - last_update_time < 1 and not force:
        return
    last_update_time = current_time
    try:
        playback = sp.current_playback()
        if not playback or not playback["is_playing"]:
            song_label.configure(text="Keine Wiedergabe", text_color="#ffffff")
            placeholder_img = ImageTk.PhotoImage(
                Image.open(resource_path("placeholder.png")).resize((150, 150), Image.LANCZOS)
            )
            cover_label.configure(image=placeholder_img)
            cover_label.image = placeholder_img
            progress_bar.set(0)
            if not playback:
                return
            play_pause_btn.configure(image=tk_play)
        else:
            track = playback["item"]
            track_id = track["id"]
            song_title = track["name"]
            artist_name = track["artists"][0]["name"]
            cover_url = track["album"]["images"][0]["url"]
            progress_ms = playback["progress_ms"]
            duration_ms = track["duration_ms"]
            if track_id != current_track_id or cover_url != current_cover_url or force:
                current_track_id = track_id
                current_cover_url = cover_url
                formatted_text = f"{song_title} - {artist_name}"
                song_label.configure(text=formatted_text, text_color="white")
                response = requests.get(cover_url)
                img_data = Image.open(BytesIO(response.content))
                img_data = img_data.resize((150, 150), Image.LANCZOS)
                cover_img = ImageTk.PhotoImage(img_data)
                cover_label.configure(image=cover_img)
                cover_label.image = cover_img
            progress_bar.set(progress_ms / duration_ms)
            play_pause_btn.configure(image=tk_pause)
        overlay.after(1000, update_overlay)
    except spotipy.exceptions.SpotifyException as e:
        messagebox.showwarning("API-Warning", f"Spotify-API-Meldung: {e}")
        print(f"Details: {e}")

def set_volume(value):
    """Setzt die Lautstärke von Spotify."""
    try:
        volume_value = int(float(value))
        sp.volume(volume_value)
        print(f"Spotify-Lautstärke auf {volume_value}% gesetzt")
    except spotipy.exceptions.SpotifyException as e:
        messagebox.showwarning("API-Warning", f"Spotify-API-Meldung: {e}")
        print(f"Details: {e}")

def set_progress(value):
    """Setzt den Fortschritt des aktuellen Songs."""
    try:
        progress_value = int(float(value))
        sp.seek_track(progress_value * 1000)
        print(f"Song-Fortschritt auf {progress_value} Sekunden gesetzt")
    except spotipy.exceptions.SpotifyException as e:
        messagebox.showwarning("API-Warning", f"Spotify-API-Meldung: {e}")
        print(f"Details: {e}")

def start_move(event):
    """Startet das Verschieben des Overlays."""
    global dragging
    dragging = True
    overlay.startX = event.x
    overlay.startY = event.y

def on_move(event):
    """Bewegt das Overlay."""
    if dragging:
        x = overlay.winfo_x() + (event.x - overlay.startX)
        y = overlay.winfo_y() + (event.y - overlay.startY)
        overlay.geometry(f"+{x}+{y}")

def stop_move(event):
    """Beendet das Verschieben des Overlays."""
    global dragging
    dragging = False

def close_overlay():
    """Schließt das Overlay."""
    overlay.destroy()
    exit(0)

def create_overlay():
    """Erstellt das Overlay-Fenster."""
    global overlay, cover_label, song_label, volume_scale, progress_bar, tk_play, tk_pause, play_pause_btn
    overlay = CTk()
    overlay.attributes('-topmost', True)
    overlay.overrideredirect(True)
    overlay.geometry(f'300x400+{overlay_x}+{overlay_y}')
    overlay.configure(bg='#333333')
    set_appearance_mode("dark")
    set_default_color_theme(THEME)
    
    title_bar = CTkFrame(overlay, fg_color="#444444", height=25)
    title_bar.pack(fill=customtkinter.X)
    title_label = CTkLabel(title_bar, text="Spoverlay by Kaze", text_color="white", fg_color="#444444", font=("Arial", 13))
    title_label.pack(side=tk.LEFT, padx=5)
    close_button = CTkButton(title_bar, text="X", text_color="white", fg_color="#444444", hover_color="#555555", width=20, height=20, command=close_overlay)
    close_button.pack(side=tk.RIGHT, padx=5, pady=0)
    title_bar.bind("<ButtonPress-1>", start_move)
    title_bar.bind("<B1-Motion>", on_move)
    title_bar.bind("<ButtonRelease-1>", stop_move)
    title_bar.pack(pady=(0, 20))
    
    cover_label = CTkLabel(overlay, fg_color="#333333", text=None)
    cover_label.pack(pady=5)
    
    song_frame = CTkFrame(overlay, fg_color="#333333", corner_radius=5)
    song_frame.pack(pady=2)
    song_label = CTkLabel(song_frame, text="Lade Titel...", text_color="white", fg_color="#333333", font=("Arial", 12), wraplength=280, justify="center")
    song_label.pack(padx=5, pady=5)
    
    progress_bar = CTkProgressBar(overlay, width=220)
    progress_bar.pack(pady=10)
    
    button_frame = CTkFrame(overlay, fg_color="#333")
    button_frame.pack(pady=2)
    tk_prev = ImageTk.PhotoImage(Image.open(resource_path("prev_icon.png")).resize((30, 30)))
    tk_play = ImageTk.PhotoImage(Image.open(resource_path("play_icon.png")).resize((40, 40)))
    tk_pause = ImageTk.PhotoImage(Image.open(resource_path("pause_icon.png")).resize((40, 40)))
    tk_next = ImageTk.PhotoImage(Image.open(resource_path("next_icon.png")).resize((30, 30)))
    prev_btn = CTkButton(button_frame, image=tk_prev, command=lambda: [sp.previous_track(), time.sleep(0.5), update_overlay(force=True)], fg_color="#333", hover_color="#444", text=None, width=70, height=60)
    prev_btn.grid(row=0, column=0, padx=5)
    play_pause_btn = CTkButton(button_frame, image=tk_play, command=play_pause, fg_color="#333", hover_color="#444", text=None, width=70, height=60)
    play_pause_btn.grid(row=0, column=1, padx=5)
    next_btn = CTkButton(button_frame, image=tk_next, command=lambda: [sp.next_track(), time.sleep(0.5), update_overlay(force=True)], fg_color="#333", hover_color="#444", text=None, width=70, height=60)
    next_btn.grid(row=0, column=2, padx=5)
    
    volume_scale = CTkSlider(overlay, from_=0, to=100, orientation="horizontal", command=set_volume, width=220)
    try:
        playback = sp.current_playback()
        if playback:
            current_volume = playback["device"]["volume_percent"]
            volume_scale.set(current_volume)
        else:
            messagebox.showwarning("Spotify-API-Error", "Es läuft derzeit keine Spotify-Wiedergabe.")
    except spotipy.exceptions.SpotifyException as e:
        messagebox.showwarning("API-Warning", f"Spotify-API-Meldung: {e}")
        print(f"Details: {e}")
    volume_scale.pack(pady=10)

def on_press(key):
    """Hotkey-Listener für das Ein- und Ausblenden des Overlays."""
    global overlay_visible
    try:
        if key.char == HOTKEY and not overlay_visible:
            overlay_visible = True
            overlay.deiconify()
            overlay.focus_force()  # Setzt den Fokus auf das Overlay-Fenster
            update_overlay(force=True)
        elif key.char == HOTKEY and overlay_visible:
            overlay_visible = False
            overlay.withdraw()
    except AttributeError:
        pass

# --- Hauptprogramm ---
if __name__ == "__main__":
    try:
        # Starte den Flask-Server in einem separaten Thread
        flask_thread = threading.Thread(target=run_flask, daemon=True)
        flask_thread.start()
        
        # Öffne automatisch den Browser zur Flask-App (auf Port 8080)
        if not sp_oauth.get_cached_token():
            webbrowser.open("http://localhost:8080/")
        
        # Warte, bis der Token im Cache vorhanden ist
        print("Warte auf Token...")
        while not sp_oauth.get_cached_token():
            time.sleep(1)
        print("Token gefunden!")
        
        # Initialisiere das Spotify-API-Objekt (das den Token aus dem Cache verwendet)
        sp = initialize_spotify()
        
        # Erstelle das Overlay und starte den Hotkey-Listener
        create_overlay()
        overlay.withdraw()
        listener = keyboard.Listener(on_press=on_press)
        listener.start()
        overlay.mainloop()
    except Exception as e:
        print(f"Ein Fehler ist aufgetreten: {e}")
    finally:
        input("Drücken Sie die Eingabetaste, um das Fenster zu schließen...")
