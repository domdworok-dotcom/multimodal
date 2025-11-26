import streamlit as st
from PIL import Image, ImageDraw
import os
import math
import time

# ---------- Konfiguration ----------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_IMG_FILENAME = "Hibiskus.jpg"
DEFAULT_IMG_PATH = os.path.join(SCRIPT_DIR, DEFAULT_IMG_FILENAME)

# ---------- Design-Farben (Dark Mode) ----------
PRIMARY_COLOR = "#4CAF50"
APP_BG        = "#121212"
TEXT_COLOR    = "#E0E0E0"
BOT_BG        = "#2C2C2C"
USER_BG       = "#1B5E20"
HIGHLIGHT_RGB = (80, 220, 220)
BORDER_RGB    = (180, 255, 255)

# ---------- Page Config ----------
st.set_page_config(
    page_title="Flori - KI-Assistent zur Pflanzenidentifikation",
    page_icon="🌿",
    layout="centered"
)

# ---------- CSS Styling (Dark Mode) ----------
st.markdown(f"""
<style>
    .stApp {{
        background-color: {APP_BG};
        color: {TEXT_COLOR};
    }}
    .chat-message {{
        padding: 1rem;
        border-radius: 10px;
        margin-bottom: 10px;
        display: flex;
        flex-direction: column;
        color: {TEXT_COLOR};
        font-family: Arial, sans-serif;
        line-height: 1.5;
    }}
    .bot-message {{
        background-color: {BOT_BG};
        border-left: 5px solid {PRIMARY_COLOR};
    }}
    .user-message {{
        background-color: {USER_BG};
        align-items: flex-end;
        text-align: right;
    }}
    .highlight-text {{
        color: #80CBC4; 
        font-weight: bold;
    }}
    .contrast-text {{
        font-style: italic;
        color: #B0BEC5;
        font-size: 0.9em;
        margin-top: 5px;
        border-top: 1px solid #444;
        padding-top: 5px;
    }}
    .typing-indicator {{
        font-style: italic;
        color: #888;
        font-size: 0.9em;
        margin-left: 10px;
        margin-bottom: 10px;
    }}
    h1, h2, h3, p {{
        color: {TEXT_COLOR} !important;
    }}
    .stButton>button {{
        width: 100%;
        border-radius: 20px;
        font-weight: bold;
        background-color: #333;
        color: white;
        border: 1px solid #555;
    }}
    .stButton>button:hover {{
        border-color: {PRIMARY_COLOR};
        color: {PRIMARY_COLOR};
    }}
</style>
""", unsafe_allow_html=True)

# ---------- Logik-Funktionen (Bildbearbeitung) ----------

# ÄNDERUNG: Neuer Parameter 'radius_factor' (Standard 0.45)
def add_highlight_to_crop(pil_crop_img, radius_factor=0.45):
    """Fügt den Highlight-Effekt (türkiser Kreis) hinzu."""
    if pil_crop_img is None: return None
    base = pil_crop_img.convert("RGBA")
    w, h = base.size
    cx, cy = w / 2, h / 2
    
    # ÄNDERUNG: Radius wird nun über den variablen Faktor bestimmt
    max_radius = min(w, h) * radius_factor

    # Maske erstellen
    gradient_mask = Image.new("L", (w, h), 0)
    mask_data = []
    max_opacity = 180 
    for y in range(h):
        for x in range(w):
            dist = math.sqrt((x - cx)**2 + (y - cy)**2)
            if dist < max_radius:
                norm_dist = dist / max_radius
                alpha = int(max_opacity * (1 - norm_dist**2))
                mask_data.append(alpha)
            else:
                mask_data.append(0)
    gradient_mask.putdata(mask_data)

    # Farbe & Rand
    solid_color = Image.new("RGBA", (w, h), HIGHLIGHT_RGB + (255,))
    solid_color.putalpha(gradient_mask)
    combined = Image.alpha_composite(base, solid_color)

    border_layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    border_draw = ImageDraw.Draw(border_layer)
    # Rand etwas enger am Gradienten
    border_rad = max_radius * 0.98 
    border_draw.ellipse((cx - border_rad, cy - border_rad, cx + border_rad, cy + border_rad),
                        fill=None, outline=BORDER_RGB + (255,), width=3)
    
    return Image.alpha_composite(combined, border_layer).convert("RGB")

def get_crops(img):
    """Erstellt die Ausschnitte."""
    crops_pct = {
        "overview":   (0.10, 0.05, 0.90, 0.95), 
        "petal_edge": (0.65, 0.20, 0.95, 0.50), 
        "stamens":    (0.45, 0.35, 0.65, 0.65), 
    }
    crops = {}
    w, h = img.size
    for key, (l, t, r, b) in crops_pct.items():
        box = (int(l*w), int(t*h), int(r*w), int(b*h))
        crops[key] = img.crop(box)
    return crops

# ---------- State Management ----------

if 'history' not in st.session_state:
    st.session_state['history'] = [] 
if 'step_index' not in st.session_state:
    st.session_state['step_index'] = -1 
if 'img' not in st.session_state:
    st.session_state['img'] = None
if 'finished' not in st.session_state:
    st.session_state['finished'] = False

# Definition der Schritte
STEPS = [
    {
        "intro": "🔎 Zuerst der Gesamteindruck:",
        "img_key": "overview",
        "caption": "Gesamtform",
        "desc": "Die Blüte ist groß, trichterförmig und die Kronblätter überlappen sich.",
        "contrast": "💡 Abgrenzung: Im Gegensatz dazu sind Rosenblüten viel kompakter und gefüllt.",
        "highlight_word": None,
        "use_img_highlight": False,
        "question": "Erkennst du diese typische Trichterform?" 
    },
    {
        "intro": "🌸 Hier kommt das erste wichtige Detail zur Identifikation:",
        "img_key": "petal_edge",
        "caption": "Detail: Blütenrand",
        "desc": "Die Kanten sind sanft gewellt. Besonders wichtig ist hier der Blütenrand, an dem die Aderung endet.",
        "contrast": "💡 Abgrenzung: Viele andere Gartenblumen (z.B. Tulpen) haben ganz glatte Ränder ohne Wellen.",
        "highlight_word": "Blütenrand", 
        "use_img_highlight": True,
        # Standard Radius (0.45) wird verwendet
        "question": "Siehst du die feine Wellung am Rand?"
    },
    {
        "intro": "🌺 Das zweite wichtige Merkmal ist im Zentrum der Blüte zu finden.",
        "img_key": "stamens",
        "caption": "Detail: Staubgefäße",
        "desc": "Diese lange Säule mit den gelben Pollen (Staubgefäß) ist das sicherste Erkennungszeichen.",
        "contrast": "💡 Abgrenzung: Bei der ähnlichen Malve ist diese Säule viel kürzer und buschiger.",
        "highlight_word": "Staubgefäße",
        "use_img_highlight": True,
        # ÄNDERUNG: Spezieller Radius-Faktor für diesen Schritt (kleiner = enger)
        "radius_factor": 0.28, 
        "question": "Kannst du die gelben Pollen an der Spitze der Säule erkennen?"
    }
]

# ---------- Helper Funktionen ----------

def add_bot_message(text, image=None, caption=None, contrast=None, highlight_word=None, delay=True):
    """
    Fügt eine Bot-Nachricht hinzu und simuliert Tipp-Zeit.
    """
    
    # 1. Tipp-Simulation (Delay)
    if delay:
        # ÄNDERUNG: Berechnung der Wartezeit deutlich verkürzt
        # Basis 0.3s (statt 0.6) + 0.015s pro Zeichen (statt 0.03). Max 2.0s (statt 3.5s).
        char_count = len(text) + (len(contrast) if contrast else 0)
        sleep_time = min(0.3 + (char_count * 0.015), 2.0)
        
        # Zeige "Flori schreibt..." Placeholder
        typing_placeholder = st.empty()
        typing_placeholder.markdown("<div class='typing-indicator'>Flori schreibt ...</div>", unsafe_allow_html=True)
        time.sleep(sleep_time)
        typing_placeholder.empty()

    # 2. Text Formatierung
    if highlight_word and highlight_word in text:
        text = text.replace(highlight_word, f"<span class='highlight-text'>{highlight_word}</span>")
    
    if contrast:
        text += f"<br><div class='contrast-text'>{contrast}</div>"

    # 3. Zum State hinzufügen
    st.session_state['history'].append({
        "role": "bot",
        "content": text,
        "image": image,
        "caption": caption
    })

def add_user_message(text):
    st.session_state['history'].append({
        "role": "user",
        "content": text
    })

# ---------- UI Rendering ----------

# Header (Grüner Balken oben)
st.markdown(f"""
<div style='background-color:{PRIMARY_COLOR}; padding:15px; border-radius:5px; margin-bottom:20px; box-shadow: 0 4px 6px rgba(0,0,0,0.3);'>
    <h1 style='color:white !important; margin:0; font-size:24px;'>Flori 🌿 <span style="font-size:14px; opacity:0.8;">| KI-Assistent zur Pflanzenidentifikation</span></h1>
</div>
""", unsafe_allow_html=True)

# 1. Chat Verlauf anzeigen
for msg in st.session_state['history']:
    if msg['role'] == "bot":
        with st.chat_message("assistant", avatar="🌿"):
            if msg.get('image'):
                st.image(msg['image'], caption=msg['caption'], use_container_width=True)
            st.markdown(f"<div class='bot-message chat-message'>{msg['content']}</div>", unsafe_allow_html=True)
    else:
        with st.chat_message("user", avatar="👤"):
            st.markdown(f"<div class='user-message chat-message'>{msg['content']}</div>", unsafe_allow_html=True)

# 2. Logik-Controller

# --- STARTZUSTAND (Kein Bild) ---
if st.session_state['step_index'] == -1 and st.session_state['img'] is None:
    if len(st.session_state['history']) == 0:
        # Erster Aufruf: Delay aktivieren
        add_bot_message("Hallo, ich bin Flori. 🌿 Ich helfe dir zu bestimmen, um welche Pflanze es sich auf dem gegebenen Bild handelt.", delay=True)
        st.rerun()

    if st.button("📸 Foto laden & Starten"):
        if os.path.exists(DEFAULT_IMG_PATH):
            st.session_state['img'] = Image.open(DEFAULT_IMG_PATH).convert("RGB")
            add_user_message("Foto laden")
            st.rerun()
        else:
            st.error(f"Fehler: '{DEFAULT_IMG_FILENAME}' nicht gefunden.")

# --- BILD GELADEN, ABER ANALYSE NICHT GESTARTET ---
elif st.session_state['step_index'] == -1 and st.session_state['img'] is not None:
    last_bot_msg = next((m for m in reversed(st.session_state['history']) if m['role'] == 'bot'), None)
    
    if last_bot_msg and "Foto ist da" not in last_bot_msg['content']:
        thumb = st.session_state['img'].copy()
        thumb.thumbnail((400, 400))
        # Kurzes Delay für die Bildanalyse-Illusion
        time.sleep(0.7) # Etwas kürzer als vorher
        add_bot_message("Alles klar – Foto ist da. Bereit für die Analyse?", image=thumb, caption="Das Foto", delay=True)
        st.rerun()
    
    st.write("---")
    if st.button("🔎 Analyse starten"):
        add_user_message("Analyse starten")
        st.session_state['step_index'] = 0
        st.rerun()

# --- HAUPT-FLOW (Schritte 0 bis N) ---
elif 0 <= st.session_state['step_index'] < len(STEPS):
    current_step = STEPS[st.session_state['step_index']]
    
    # Prüfen, ob der aktuelle Schritt schon im Verlauf steht
    last_msg = st.session_state['history'][-1]
    is_step_rendered = (last_msg['role'] == "bot" and current_step['question'] in last_msg['content'])

    if not is_step_rendered:
        # Bild vorbereiten
        crops = get_crops(st.session_state['img'])
        crop_img = crops.get(current_step['img_key'])
        
        if current_step['use_img_highlight']:
            # ÄNDERUNG: Prüfen, ob ein spezieller Radius-Faktor im Step definiert ist
            r_factor = current_step.get('radius_factor', 0.45) # Default 0.45 wenn nicht angegeben
            final_img = add_highlight_to_crop(crop_img, radius_factor=r_factor)
            caption_suffix = " (Fokus)"
        else:
            final_img = crop_img
            caption_suffix = ""

        # Schritt 1: Erklärungstext (mit verkürztem Delay)
        full_text = f"{current_step['intro']}<br><br>{current_step['desc']}"
        add_bot_message(
            full_text, 
            image=final_img, 
            caption=current_step['caption'] + caption_suffix,
            contrast=current_step.get('contrast'),
            highlight_word=current_step.get('highlight_word'),
            delay=True
        )
        
        # Schritt 2: Die Frage hinterher (ganz kurzes fixes Delay)
        time.sleep(0.3) 
        add_bot_message(f"<b>{current_step['question']}</b>", delay=False)
        st.rerun()

    else:
        # Interaktions-Buttons
        st.write("---")
        col_y, col_n = st.columns(2)
        
        if col_y.button("✅ Ja, sehe ich", key=f"yes_{st.session_state['step_index']}"):
            add_user_message("Ja, das sehe ich.")
            
            time.sleep(0.3)
            add_bot_message("👍 Super! Weiter geht's.", delay=True)
            
            st.session_state['step_index'] += 1
            st.rerun()
            
        if col_n.button("🤔 Nein / Unsicher", key=f"no_{st.session_state['step_index']}"):
            add_user_message("Nein, bin unsicher.")
            
            if current_step['use_img_highlight']:
                reply = "Kein Problem! Achte genau auf den türkisen Bereich im Bild. Wir machen trotzdem weiter."
            else:
                reply = "Kein Problem, manchmal ist es schwer zu sehen. Wir schauen uns das nächste Detail an."
            
            time.sleep(0.3)
            add_bot_message(reply, delay=True)
            
            st.session_state['step_index'] += 1
            st.rerun()

# --- ENDE / ERGEBNIS ---
elif st.session_state['step_index'] >= len(STEPS):
    
    if not st.session_state['finished']:
        add_bot_message("✅ <b>Ergebnis:</b> Bei dieser Pflanze handelt es sich eindeutig um einen Hibiskus (Hibiscus rosa-sinensis).", delay=True)
        
        tip_text = "💡 <b>Pflege-Tipp:</b><br>Nicht winterhart! Im Sommer draußen, ab < 10°C hell & kühl (12-18°C) überwintern."
        add_bot_message(tip_text, delay=True)
        
        st.session_state['finished'] = True
        st.rerun() 
    
    # 2. Anzeige wenn fertig
    st.success("Chat beendet. Vielen Dank für die Teilnahme!")
    st.info("Bitte kehre nun zu deinem Fragebogen zurück.")
    
    if st.button("🔄 Neuer Durchlauf (für Testzwecke)"):
        st.session_state.clear()
        st.rerun()
    
