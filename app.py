import streamlit as st
from PIL import Image, ImageDraw
import os
import math
import time
import re 

# ---------- Konfiguration ----------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_IMG_FILENAME = "Hibiskus.jpg"
DEFAULT_IMG_PATH = os.path.join(SCRIPT_DIR, DEFAULT_IMG_FILENAME)

# Das Pflege-Bild
CARE_IMG_FILENAME = "Hibiskus pflege.jpg"
CARE_IMG_PATH = os.path.join(SCRIPT_DIR, CARE_IMG_FILENAME)

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
        display: block; 
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
        text-align: right;
    }}
    .contrast-text {{
        font-style: italic;
        color: #B0BEC5;
        font-size: 0.9em;
        margin-top: 10px;
        padding-top: 8px;
        border-top: 1px solid #444;
        display: block;
    }}
    .typing-indicator {{
        font-style: italic;
        color: #888;
        font-size: 0.9em;
        margin-left: 10px;
        margin-bottom: 10px;
    }}
    h1, h2, h3, p, li {{
        color: {TEXT_COLOR} !important;
    }}
    
    /* Standard Buttons (Grau, Navigations-Buttons) */
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

    /* NEU: Primary Buttons (Hervorgehoben, Grün gefüllt) */
    /* Targetiert Buttons mit type="primary" */
    button[kind="primary"] {{
        background-color: {PRIMARY_COLOR} !important;
        color: white !important;
        border: none !important;
        font-size: 1.1em !important;
        box-shadow: 0 4px 10px rgba(76, 175, 80, 0.3);
    }}
    button[kind="primary"]:hover {{
        background-color: #43A047 !important;
        box-shadow: 0 6px 12px rgba(76, 175, 80, 0.5);
    }}
</style>
""", unsafe_allow_html=True)

# ---------- Logik-Funktionen (Bildbearbeitung) ----------

def add_highlight_to_crop(pil_crop_img, radius_factor=0.45):
    """Fügt den Highlight-Effekt (türkiser Kreis) hinzu."""
    if pil_crop_img is None: return None
    base = pil_crop_img.convert("RGBA")
    w, h = base.size
    cx, cy = w / 2, h / 2
    
    max_radius = min(w, h) * radius_factor

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

    solid_color = Image.new("RGBA", (w, h), HIGHLIGHT_RGB + (255,))
    solid_color.putalpha(gradient_mask)
    combined = Image.alpha_composite(base, solid_color)

    border_layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    border_draw = ImageDraw.Draw(border_layer)
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
if 'final_timer_done' not in st.session_state:
    st.session_state['final_timer_done'] = False

# Definition der Schritte
STEPS = [
    {
        "intro": "🔎 Zuerst der Gesamteindruck:",
        "img_key": "overview",
        "caption": "Gesamtform",
        "desc": "Die Blüte ist groß, trichterförmig und die Kronblätter überlappen sich.",
        "contrast": "💡 Abgrenzung: Im Gegensatz dazu sind Rosenblüten viel kompakter und gefüllt.",
        "highlight_word": None,
        "use_img_highlight": False
    },
    {
        "intro": "🌸 Hier kommt das erste wichtige Detail zur Identifikation:",
        "img_key": "petal_edge",
        "caption": "Detail: Blütenrand",
        "desc": "Die Kanten sind sanft gewellt. Besonders wichtig ist hier der Blütenrand, an dem die Aderung endet.",
        "contrast": "💡 Abgrenzung: Viele andere Gartenblumen (z.B. Tulpen) haben ganz glatte Ränder ohne Wellen.",
        "highlight_word": "Blütenrand", 
        "use_img_highlight": True,
    },
    {
        "intro": "🌺 Das zweite wichtige Merkmal ist im Zentrum der Blüte zu finden.",
        "img_key": "stamens",
        "caption": "Detail: Staubgefäße",
        "desc": "Diese lange Säule mit den gelben Pollen (Staubgefäß) ist das sicherste Erkennungszeichen.",
        "contrast": "💡 Abgrenzung: Bei der ähnlichen Malve ist diese Säule viel kürzer und buschiger.",
        "highlight_word": "Staubgefäße",
        "use_img_highlight": True,
        "radius_factor": 0.28, 
    }
]

# ---------- Helper Funktionen ----------

def add_bot_message(text, image=None, caption=None, contrast=None, highlight_word=None, delay=True):
    """
    Fügt Bot-Nachricht hinzu. Wenn delay=True, wird der Text WORT FÜR WORT generiert.
    """
    
    if highlight_word and highlight_word in text:
        # Türkis (#80CBC4) und Fett, inline
        text = text.replace(highlight_word, f"<span style='color: #80CBC4; font-weight: bold;'>{highlight_word}</span>")
    
    full_inner_html = f"<div>{text}</div>"
    if contrast:
        full_inner_html += f"<div class='contrast-text'>{contrast}</div>"

    if delay:
        if image:
            with st.chat_message("assistant", avatar="🌿"):
                st.image(image, caption=caption, use_container_width=True)
        
        placeholder = st.empty()
        
        # Word-by-Word Streaming Logik
        tokens = re.findall(r'(<[^>]+>|[^<]+)', full_inner_html)
        stream_parts = []
        for token in tokens:
            if token.startswith('<'):
                stream_parts.append(token)
            else:
                words = re.split(r'(\s+)', token)
                stream_parts.extend(words)
        
        displayed_text = ""
        for part in stream_parts:
            if not part: continue 
            displayed_text += part
            current_html = f"<div class='bot-message chat-message'>{displayed_text}</div>"
            placeholder.markdown(current_html, unsafe_allow_html=True)
            
            if not part.startswith('<'):
                if part.strip() == "":
                    time.sleep(0.01) 
                else:
                    time.sleep(0.05) 
            
        placeholder.empty()

    st.session_state['history'].append({
        "role": "bot",
        "content": full_inner_html,
        "image": image,
        "caption": caption
    })

def add_user_message(text):
    st.session_state['history'].append({
        "role": "user",
        "content": text
    })

# ---------- UI Rendering ----------

# Header
st.markdown(f"""
<div style='background-color:{PRIMARY_COLOR}; padding:15px; border-radius:5px; margin-bottom:20px; box-shadow: 0 4px 6px rgba(0,0,0,0.3);'>
    <h1 style='color:white !important; margin:0; font-size:24px;'>Flori 🌿 <span style="font-size:14px; opacity:0.8;">| KI-Assistent zur Pflanzenidentifikation</span></h1>
</div>
""", unsafe_allow_html=True)

# 1. Chat Verlauf
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

# --- STARTZUSTAND ---
if st.session_state['step_index'] == -1 and st.session_state['img'] is None:
    if len(st.session_state['history']) == 0:
        add_bot_message("Hallo, ich bin Flori. 🌿 Ich helfe dir zu bestimmen, um welche Pflanze es sich auf dem gegebenen Bild handelt.", delay=True)
        st.rerun()

    # Button GANZ rechtsbündig (Ratio 3:1)
    col_l, col_r = st.columns([3, 1])
    with col_r:
        if st.button("📸 Foto laden & Starten"):
            if os.path.exists(DEFAULT_IMG_PATH):
                st.session_state['img'] = Image.open(DEFAULT_IMG_PATH).convert("RGB")
                add_user_message("Foto laden")
                st.rerun()
            else:
                st.error(f"Fehler: '{DEFAULT_IMG_FILENAME}' nicht gefunden.")

# --- BILD GELADEN ---
elif st.session_state['step_index'] == -1 and st.session_state['img'] is not None:
    last_bot_msg = next((m for m in reversed(st.session_state['history']) if m['role'] == 'bot'), None)
    
    if last_bot_msg and "Foto ist da" not in last_bot_msg['content']:
        thumb = st.session_state['img'].copy()
        thumb.thumbnail((400, 400))
        time.sleep(0.5)
        add_bot_message("Alles klar – Foto ist da. Bereit für die Analyse?", image=thumb, caption="Das Foto", delay=True)
        st.rerun()
    
    st.write("---")
    # Button GANZ rechtsbündig (Ratio 3:1)
    col_l, col_r = st.columns([3, 1])
    with col_r:
        if st.button("🔎 Analyse starten"):
            add_user_message("Analyse starten")
            st.session_state['step_index'] = 0
            st.rerun()

# --- HAUPT-FLOW ---
elif 0 <= st.session_state['step_index'] < len(STEPS):
    current_step = STEPS[st.session_state['step_index']]
    CONTINUE_QUESTION = "Sollen wir die Analyse fortsetzen?"

    # Check: Wurde Intro schon gepostet?
    explanation_sent = False
    intro_fragment = current_step['intro'][:20]
    for msg in reversed(st.session_state['history']):
        if msg['role'] == 'bot' and intro_fragment in msg['content']:
            explanation_sent = True
            break
    
    # Check: Wurde Frage schon gepostet?
    last_msg = st.session_state['history'][-1]
    question_sent = (last_msg['role'] == 'bot' and CONTINUE_QUESTION in last_msg['content'])

    # PHASE 1: Erklärung + Bild anzeigen
    if not explanation_sent:
        crops = get_crops(st.session_state['img'])
        crop_img = crops.get(current_step['img_key'])
        
        if current_step['use_img_highlight']:
            r_factor = current_step.get('radius_factor', 0.45) 
            final_img = add_highlight_to_crop(crop_img, radius_factor=r_factor)
            caption_suffix = " (Fokus)"
        else:
            final_img = crop_img
            caption_suffix = ""

        full_text = f"<p style='margin-bottom:10px; margin-top:0;'>{current_step['intro']}</p><p style='margin-bottom:0;'>{current_step['desc']}</p>"
        
        add_bot_message(
            full_text, 
            image=final_img, 
            caption=current_step['caption'] + caption_suffix,
            contrast=current_step.get('contrast'),
            highlight_word=current_step.get('highlight_word'),
            delay=True
        )
        st.rerun()

    # PHASE 2: Verzögerung + Frage stellen
    elif explanation_sent and not question_sent:
        # Hier die 5 Sekunden Verzögerung vor der Frage
        placeholder = st.empty()
        with placeholder.container():
            st.caption("⏳ Bitte schau dir das Merkmal genau an...")
            progress_bar = st.progress(0)
            for i in range(50): # 50 * 0.1s = 5 Sekunden
                time.sleep(0.1)
                progress_bar.progress(i * 2 + 2)
        
        placeholder.empty() # Ladebalken entfernen
        
        add_bot_message(f"<b>{CONTINUE_QUESTION}</b>", delay=True) 
        st.rerun()

    # PHASE 3: Button anzeigen
    else:
        st.write("---")
        # Button GANZ rechtsbündig (Ratio 3:1)
        col_l, col_r = st.columns([3, 1])
        with col_r:
            if st.button("➡️ Analyse fortsetzen", key=f"next_{st.session_state['step_index']}"):
                add_user_message("Analyse fortsetzen")
                st.session_state['step_index'] += 1
                st.rerun()

# --- ENDE / ERGEBNIS / CODE-ANZEIGE ---
elif st.session_state['step_index'] >= len(STEPS):
    
    if not st.session_state['finished']:
        # 1. Ergebnis
        add_bot_message("✅ <b>Ergebnis:</b> Bei dieser Pflanze handelt es sich eindeutig um einen Hibiskus (Hibiscus rosa-sinensis).", delay=True)
        
        # 2. Pflege-Bild
        if os.path.exists(CARE_IMG_PATH):
            care_img = Image.open(CARE_IMG_PATH).convert("RGB")
            add_bot_message(
                "Zur besseren Veranschaulichung hier die wichtigsten Handgriffe visualisiert:",
                image=care_img,
                caption="Links: Fingertest zur Wasserkontrolle | Rechts: Schnitt über einem Auge",
                delay=True
            )
        
        # 3. Pflege-Tipps Text
        tip_text = """
        💡 <b>Ausführliche Pflege-Tipps für den Hibiskus (Roseneibisch):</b><br><br>
        <ul style='padding-left: 20px;'>
            <li><b>🚿 Wasser:</b> Im Sommer reichlich gießen, Staunässe aber vermeiden. Im Winter sparsamer.</li>
            <li><b>☀️ Standort:</b> Liebt es hell und sonnig. Im Sommer gerne draußen an einem geschützten Platz.</li>
            <li><b>🧴 Dünger:</b> Von April bis September wöchentlich mit Kübelpflanzendünger versorgen.</li>
            <li><b>❄️ Überwinterung (Wichtig!):</b> Nicht winterhart! Sobald die Temperaturen nachts unter 10°C fallen, muss er rein. Hell und kühl (ca. 12-15°C) überwintern.</li>
            <li><b>✂️ Schnitt:</b> Ein Rückschnitt im Frühjahr fördert einen buschigen Wuchs und neue Blüten. Schneide dazu immer knapp über einem nach außen zeigenden Auge (siehe Bild).</li>
        </ul>
        """
        add_bot_message(tip_text, delay=True)
        
        st.session_state['finished'] = True
        st.rerun() 
    
    st.success("Chat beendet. Vielen Dank für die Teilnahme!")

    # ----------------------------------------------------
    # FINAL: Button (Groß & Mittig & Grün) -> 5 Sekunden Timer -> Code
    # ----------------------------------------------------
    
    if not st.session_state['final_timer_done']:
        st.write("---")
        
        # Zentrieren durch Spalten-Layout [1, 2, 1]
        _, col_mid, _ = st.columns([1, 2, 1])
        with col_mid:
            # type="primary" -> Triggered unser neues CSS (Grün + Fett)
            if st.button("🔐 CODE FÜR UMFRAGE GENERIEREN", type="primary"):
                placeholder = st.empty()
                with placeholder.container():
                    st.info("Dein Bestätigungscode wird generiert... Bitte warten.")
                    progress_bar = st.progress(0)
                    for i in range(50): # 50 * 0.1s = 5 Sekunden
                        time.sleep(0.1)
                        progress_bar.progress(i * 2 + 2)
                
                placeholder.empty()
                st.session_state['final_timer_done'] = True
                st.rerun()

    # ----------------------------------------------------
    # FINAL: Anzeige des Codes + Info Message + Reset Button
    # ----------------------------------------------------
    
    if st.session_state['final_timer_done']:
        code_display_html = f"""
        <div style="background-color: {BOT_BG}; border: 2px solid {PRIMARY_COLOR}; padding: 20px; border-radius: 10px; text-align: center; margin: 20px 0; font-family: Arial, sans-serif;">
            <h3 style="margin: 0 0 10px 0; color: {TEXT_COLOR}; font-size: 1.2em;">Dein Code für die Umfrage:</h3>
            <div style="font-size: 3em; color: {PRIMARY_COLOR}; font-family: monospace; letter-spacing: 2px; font-weight: bold; margin-bottom: 5px;">FL-7562</div>
            <p style="margin-top: 10px; color: #888; font-size: 0.9em;">Bitte notiere diesen Code oder kopiere ihn für den Fragebogen.</p>
        </div>
        """
        st.markdown(code_display_html, unsafe_allow_html=True)

        st.info("Du kannst dieses Browserfenster nun schließen oder zum Fragebogen zurückkehren.")
        
        st.write("---")
        # Reset Button GANZ rechtsbündig (Ratio 3:1)
        col_l, col_r = st.columns([3, 1])
        with col_r:
            if st.button("🔄 Neuer Durchlauf (für Testzwecke)"):
                st.session_state.clear()
                st.rerun()