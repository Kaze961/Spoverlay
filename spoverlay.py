import tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image, ImageTk, ImageDraw
import requests
from io import BytesIO
from pynput import keyboard
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import time
import json
import threading

# **Konfigurationsdatei laden**
def load_config():
    try:
        with open("config.json", "r") as config_file:
            return json.load(config_file)
    except FileNotFoundError:
        print("Fehler: Konfigurationsdatei 'config.json' nicht gefunden.")
        exit(1)
    except json.JSONDecodeError:
        print("Fehler: Ungültiges JSON-Format in der Konfigurationsdatei.")
        exit(1)

# Konfiguration laden
config = load_config()
SPOTIFY_CLIENT_ID = config["spotify_client_id"]
SPOTIFY_CLIENT_SECRET = config["spotify_client_secret"]
HOTKEY = config["hotkey"]

# **Globale Variablen**
overlay = None
cover_label = None
song_label = None
progress_scale = None
time_label = None
overlay_visible = False
overlay_x, overlay_y = 100, 100
dragging = False
last_update_time = 0
current_track_id = None
current_cover_url = None
sp = None  # Spotify-API-Objekt
tk_play = None
tk_pause = None
play_pause_btn = None

# **Spotify API initialisieren**
def initialize_spotify():
    return spotipy.Spotify(auth_manager=SpotifyOAuth(
        client_id=SPOTIFY_CLIENT_ID,
        client_secret=SPOTIFY_CLIENT_SECRET,
        redirect_uri="http://localhost:8080",
        scope="user-modify-playback-state user-read-playback-state user-read-currently-playing"
    ))

# **Play/Pause mit sofortigem Update**
def play_pause():
    try:
        playback = sp.current_playback()
        if not playback:
            return

        if playback["is_playing"]:
            sp.pause_playback()
            play_pause_btn.config(image=tk_play)
            print("⏸ Musik pausiert")
        else:
            sp.start_playback()
            play_pause_btn.config(image=tk_pause)
            print("▶ Musik fortgesetzt")

        time.sleep(0.5)  # Kurze Pause für Spotify-Update
        update_overlay(force=True)
    except spotipy.exceptions.SpotifyException as e:
        messagebox.showwarning("API-Warning", f"Spotify-API-Meldung: {e}")
        print(f"Details: {e}")

# **Overlay aktualisieren (Cover, Songtitel, Fortschritt & verbleibende Zeit)**
def update_overlay(force=False):
    global last_update_time, current_track_id, current_cover_url

    current_time = time.time()
    if current_time - last_update_time < 1 and not force:  # Alle 1 Sekunde aktualisieren
        return
    last_update_time = current_time

    try:
        playback = sp.current_playback()
        if not playback or not playback["is_playing"]:
            song_label.config(text="Keine Wiedergabe", fg="#ffffff")
            placeholder_img = ImageTk.PhotoImage(Image.open("placeholder.png").resize((150, 150), Image.LANCZOS))
            cover_label.config(image=placeholder_img)
            cover_label.image = placeholder_img
            progress_scale.config(state="disabled")
            time_label.config(text="0:00 / 0:00")
            if not playback:
                return
            play_pause_btn.config(image=tk_play)

        else:
            track = playback["item"]
            track_id = track["id"]
            song_title = track["name"]
            artist_name = track["artists"][0]["name"]
            cover_url = track["album"]["images"][0]["url"]
            progress_ms = playback["progress_ms"]
            duration_ms = track["duration_ms"]

            # Immer das Cover aktualisieren, wenn die Wiedergabe fortgesetzt wird
            if track_id != current_track_id or cover_url != current_cover_url or force:
                current_track_id = track_id
                current_cover_url = cover_url

                formatted_text = f"{song_title} - {artist_name}"
                song_label.config(text=formatted_text, fg="white")

                # Cover herunterladen und anzeigen
                response = requests.get(cover_url)
                img_data = Image.open(BytesIO(response.content))
                img_data = img_data.resize((150, 150), Image.LANCZOS)
                cover_img = ImageTk.PhotoImage(img_data)

                cover_label.config(image=cover_img)
                cover_label.image = cover_img

            # Fortschrittsbalken aktualisieren
            progress_scale.config(state="normal", to=duration_ms / 1000, value=progress_ms / 1000)

            # Verbleibende Zeit anzeigen
            remaining_time = (duration_ms - progress_ms) / 1000
            time_label.config(text=f"-{format_time(remaining_time)}")

            play_pause_btn.config(image=tk_pause)

        # Nächste Aktualisierung planen
        overlay.after(1000, update_overlay)
    except spotipy.exceptions.SpotifyException as e:
        messagebox.showwarning("API-Warning", f"Spotify-API-Meldung: {e}")
        print(f"Details: {e}")

# **Lautstärke setzen**
def set_volume(value):
    try:
        volume_value = int(float(value))  # Float in Int umwandeln
        sp.volume(volume_value)
        print(f"🔊 Spotify-Lautstärke auf {volume_value}% gesetzt")
    except spotipy.exceptions.SpotifyException as e:
        messagebox.showwarning("API-Warning", f"Spotify-API-Meldung: {e}")
        print(f"Details: {e}")

# **Song-Fortschritt setzen**
def set_progress(value):
    try:
        progress_value = int(float(value))  # Float in Int umwandeln
        sp.seek_track(progress_value * 1000)  # Spotify erwartet Millisekunden
        print(f"⏩ Song-Fortschritt auf {progress_value} Sekunden gesetzt")
    except spotipy.exceptions.SpotifyException as e:
        messagebox.showwarning("API-Warning", f"Spotify-API-Meldung: {e}")
        print(f"Details: {e}")

# **Zeitformatierung (Sekunden in MM:SS umwandeln)**
def format_time(seconds):
    minutes, seconds = divmod(int(seconds), 60)
    return f"{minutes}:{seconds:02}"

# **Fenster verschieben**
def start_move(event):
    global dragging
    dragging = True
    overlay.startX = event.x
    overlay.startY = event.y

def on_move(event):
    if dragging:
        x = overlay.winfo_x() + (event.x - overlay.startX)
        y = overlay.winfo_y() + (event.y - overlay.startY)
        overlay.geometry(f"+{x}+{y}")

def stop_move(event):
    global dragging
    dragging = False

# **Overlay schließen**
def close_overlay():
    overlay.destroy()
    exit(0)

# **Overlay erstellen**
def create_overlay():
    global overlay, cover_label, song_label, volume_scale, progress_scale, time_label, tk_play, tk_pause, tk_next, tk_prev, play_pause_btn

    overlay = tk.Tk()
    overlay.attributes('-topmost', True)
    overlay.overrideredirect(True)
    overlay.geometry(f'300x400+{overlay_x}+{overlay_y}')
    overlay.configure(bg='#333333')

    # Stil für die Slider definieren
    style = ttk.Style()
    style.theme_use('default')
    style.configure("Custom.Horizontal.TScale",
                    troughcolor='#444444',  # Etwas tieferer Grauton als der Hintergrund
                    background='#ffffff',
                    troughrelief='flat',
                    sliderthickness=15,
                    sliderlength=20,
                    relief='flat',
                    slidercolor='white')  # Slider-Knopf in Weiß
    style.map("Custom.Horizontal.TScale",
              slidercolor=[('!active', 'white'), ('active', 'white')])  # Slider-Knopf immer weiß

    # Titel-Leiste oben
    title_bar = tk.Frame(overlay, bg="#444444", height=25)
    title_bar.pack(fill=tk.X)

    # Titel-Label
    title_label = tk.Label(title_bar, text="Spoverlay by Kaze", fg="white", bg="#444444", font=("Arial", 10))
    title_label.pack(side=tk.LEFT, padx=5)

    # Schließen-Button (X)
    close_btn = tk.Label(title_bar, text="X", fg="white", bg="#444444", font=("Arial", 10), cursor="hand2")
    close_btn.pack(side=tk.RIGHT, padx=5)
    close_btn.bind("<Button-1>", lambda e: close_overlay())

    # Drag-and-Drop für die Titel-Leiste
    title_bar.bind("<ButtonPress-1>", start_move)
    title_bar.bind("<B1-Motion>", on_move)
    title_bar.bind("<ButtonRelease-1>", stop_move)

    # Cover-Bild
    cover_label = tk.Label(overlay, bg="#333333")
    cover_label.pack(pady=5)  # Weniger Abstand

    # Songtitel
    song_label = tk.Label(overlay, text="Lade Titel...", fg="white", bg="#333333", font=("Arial", 12), wraplength=280, justify="center")
    song_label.pack(pady=2)  # Weniger Abstand

    # Steuerungsbuttons
    button_frame = tk.Frame(overlay, bg="#333")
    button_frame.pack(pady=2)  # Weniger Abstand

    tk_prev = ImageTk.PhotoImage(Image.open("prev_icon.png").resize((30, 30)))
    tk_play = ImageTk.PhotoImage(Image.open("play_icon.png").resize((50, 50)))
    tk_pause = ImageTk.PhotoImage(Image.open("pause_icon.png").resize((50, 50)))
    tk_next = ImageTk.PhotoImage(Image.open("next_icon.png").resize((30, 30)))

    prev_btn = tk.Button(button_frame, image=tk_prev, command=lambda: [sp.previous_track(), time.sleep(0.5), update_overlay(force=True)], relief="flat", bg="#333")
    prev_btn.grid(row=0, column=0, padx=10)

    play_pause_btn = tk.Button(button_frame, image=tk_play, command=play_pause, relief="flat", bg="#333")
    play_pause_btn.grid(row=0, column=1, padx=10)

    next_btn = tk.Button(button_frame, image=tk_next, command=lambda: [sp.next_track(), time.sleep(0.5), update_overlay(force=True)], relief="flat", bg="#333")
    next_btn.grid(row=0, column=2, padx=10)

    # Song-Dauer-Leiste
    progress_scale = ttk.Scale(
        overlay,
        from_=0,
        to=100,
        orient=tk.HORIZONTAL,
        command=set_progress,
        style="Custom.Horizontal.TScale",
        length=220
    )
    progress_scale.pack(pady=10)

    # Label für die verbleibende Zeit
    time_label = tk.Label(overlay, text="0:00 / 0:00", fg="white", bg="#333333", font=("Arial", 10))
    time_label.pack(pady=5)

    # Spotify-ähnlicher Lautstärkeregler
    volume_scale = ttk.Scale(
        overlay,
        from_=0,
        to=100,
        orient=tk.HORIZONTAL,
        command=set_volume,
        style="Custom.Horizontal.TScale",
        length=220
    )

    # Aktuelle Lautstärke von Spotify API abrufen und setzen
    try:
        current_volume = sp.current_playback()["device"]["volume_percent"]
        volume_scale.set(current_volume)
    except spotipy.exceptions.SpotifyException as e:
        messagebox.showwarning("API-Warning", f"Spotify-API-Meldung: {e}")
        print(f"Details: {e}")

    volume_scale.pack(pady=10)

# **Hotkey-Steuerung**
def on_press(key):
    global overlay_visible
    try:
        if key.char == HOTKEY and not overlay_visible:
            overlay_visible = True
            overlay.deiconify()
            update_overlay(force=True)
        elif key.char == HOTKEY and overlay_visible:
            overlay_visible = False
            overlay.withdraw()
    except AttributeError:
        pass

# **Hauptprogramm**
if __name__ == "__main__":
    sp = initialize_spotify()
    create_overlay()
    overlay.withdraw()
    listener = keyboard.Listener(on_press=on_press)
    listener.start()
    overlay.mainloop()