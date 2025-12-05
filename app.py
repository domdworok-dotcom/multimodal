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

# --- Zusätzliche Bilder für Analyse ---
TRICHTER_IMG_FILENAME = "trichter.png"
TRICHTER_IMG_PATH = os.path.join(SCRIPT_DIR, TRICHTER_IMG_FILENAME)

HEATMAP_IMG_FILENAME = "heatmap.png"
HEATMAP_IMG_PATH = os.path.join(SCRIPT_DIR, HEATMAP_IMG_FILENAME)

# ---------- Design-Farben (Light Mode) ----------
PRIMARY_COLOR = "#2E7D32"
APP_BG        = "#FFFFFF"
TEXT_COLOR    = "#333333"
BOT_BG        = "#F0F2F6"
USER_BG       = "#E8F5E9"
HIGHLIGHT_TEXT_COL = "#00695C"
CONTRAST_TEXT_COL  = "#666666"

# Farben für die Bildbearbeitung (Image Draw)
HIGHLIGHT_RGB = (0, 150, 136)
BORDER_RGB    = (255, 255, 255)

# ---------- Page Config ----------
st.set_page_config(
    page_title="Flori - KI-Assistent zur Pflanzenidentifikation",
    page_icon="🌿",
    layout="centered"
)

# ---------- CSS Styling (Light Mode - Optimiert) ----------
st.markdown(f"""
<style>
    /* Globale App-Farben */
    .stApp {{
        background-color: {APP_BG};
        color: {TEXT_COLOR};
    }}

    /* --- ÜBERSCHRIFTEN FIX --- */
    .white-header {{
        color: #FFFFFF !important;
        opacity: 1 !important;
        text-decoration: none !important;
    }}
    .header-container h1 {{
        color: #FFFFFF !important;
    }}

    /* --- CSS ANIMATION FÜR LADEBALKEN --- */
    @keyframes fillProgress {{
        0% {{ width: 0%; }}
        100% {{ width: 100%; }}
    }}

    /* --- CHAT CONTAINER FIX --- */
    .stChatMessage {{
        background-color: transparent !important;
        border: none !important;
    }}
    div[data-testid="stChatMessage"] {{
        background-color: transparent !important;
    }}

    /* --- Nachricht-Boxen Design --- */
    .chat-message {{
        padding: 1rem;
        border-radius: 10px;
        display: block; 
        color: {TEXT_COLOR};
        font-family: Arial, sans-serif;
        line-height: 1.5;
        box-shadow: 0 1px 2px rgba(0,0,0,0.1); 
        width: fit-content; 
        max-width: 85%; 
    }}
    .bot-message {{
        background-color: {BOT_BG};
        border-left: 5px solid {PRIMARY_COLOR};
        margin-right: auto; 
    }}
    .user-message {{
        background-color: {USER_BG};
        color: #1B5E20; 
        margin-left: auto; 
        text-align: right;
    }}

    /* --- Sonstiges --- */
    .contrast-text {{
        font-style: italic;
        color: {CONTRAST_TEXT_COL};
        font-size: 0.9em;
        margin-top: 10px;
        padding-top: 8px;
        border-top: 1px solid #DDD; 
        display: block;
        text-align: left; 
    }}
    
    /* Typing Indicator */
    .typing-indicator {{
        font-style: italic;
        color: #888;
        font-size: 0.9em;
        animation: blink 1.5s infinite;
    }}
    @keyframes blink {{
        0% {{ opacity: 0.3; }}
        50% {{ opacity: 1; }}
        100% {{ opacity: 0.3; }}
    }}
    
    h1, h2, h3, p, li {{
        color: {TEXT_COLOR} !important;
    }}
    
    /* Buttons */
    .stButton>button {{
        width: 100%;
        border-radius: 20px;
        font-weight: bold;
        background-color: #FFFFFF;
        color: #333;
        border: 1px solid #CCC;
        transition: all 0.3s ease;
    }}
    .stButton>button:hover {{
        border-color: {PRIMARY_COLOR};
        color: {PRIMARY_COLOR};
        background-color: #F9F9F9;
    }}

    /* Primary Buttons */
    button[kind="primary"] {{
        background-color: {PRIMARY_COLOR} !important;
        color: white !important;
        border: none !important;
        font-size: 1.1em !important;
        box-shadow: 0 4px 10px rgba(46, 125, 50, 0.3);
    }}
    button[kind="primary"]:hover {{
        background-color: #1B5E20 !important;
        box-shadow: 0 6px 12px rgba(46, 125, 50, 0.5);
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
        "intro": "🔎 Wir beginnen mit dem Gesamteindruck der Blüte:",
        "custom_img_path": TRICHTER_IMG_PATH, 
        "caption": "Gesamtform & Textur",
        "desc": "Die Blüte ist auffällig groß und markant trichterförmig. Die fünf Kronblätter öffnen sich fächerartig nach außen.",
        "contrast": "💡 Abgrenzung: Im Gegensatz dazu sind Rosenblüten viel kompakter, die Blätter dicker und meist eng gefüllt, ohne diese offene Trichterform.",
        "highlight_word": "trichterförmig",
        "use_img_highlight": False
    },
    {
        "intro": "🌸 Nun schauen wir uns die Ränder der Blütenblätter an:",
        "img_key": "petal_edge",
        "caption": "Blütenrand & Aderung",
        "desc": "Die Ränder sind unregelmäßig gesägt oder sanft gewellt und nicht glatt geschnitten. Auffällig ist zudem die feine Aderung, die von der Grundfarbe abhebt und fast parallel bis in die äußeren Spitzen verläuft.",
        "contrast": "💡 Abgrenzung: Viele Lilien oder Tulpen haben vollkommen glattrandige Blütenblätter ohne diese charakteristische, unruhige Wellenstruktur.",
        "highlight_word": "Blütenrand", 
        "use_img_highlight": True,
    },
    {
        "intro": "🌺 Das absolut sicherste Erkennungsmerkmal befindet sich im Zentrum:",
        "img_key": "stamens",
        "caption": "Staminalsäule (Columna)",
        "desc": "Hier sind Staubfäden und Griffel zu einer langen Röhre verwachsen – der sogenannten Staminalsäule. Sie ragt weit aus der Blüte heraus. An der Spitze sitzen fünf samtige Narbenäste, darunter die vielen gelben Staubbeutel.",
        "contrast": "💡 Abgrenzung: Bei der ähnlichen Malve ist diese Säule zwar auch vorhanden, aber viel kürzer, gedrungener und wirkt eher buschig als säulenartig.",
        "highlight_word": "Staminalsäule",
        "use_img_highlight": True,
        "radius_factor": 0.28, 
    },
    {
        "intro": "🧠 Meine Analyse hat folgende wichtige Merkmale der Blüte identifiziert:",
        "custom_img_path": HEATMAP_IMG_PATH,
        "caption": "KI-Heatmap & Analyse-Ergebnis",
        "desc": "Die Kombination ist eindeutig: Die <b>offene Trichterform</b>, die <b>gesägten Ränder</b> mit der feinen Aderung und vor allem die <b>lange, herausragende Staminalsäule</b> sind der 'genetische Fingerabdruck' dieser Pflanze.",
        "contrast": "Alle drei Merkmale zusammen schließen Verwechslungen mit Malven oder Rosen fast vollständig aus.",
        "use_img_highlight": False
    }
]

# ---------- Helper Funktionen ----------

def show_smooth_progress_bar(duration_seconds=5):
    """
    Zeigt einen flüssigen HTML-Ladebalken (CSS Animation).
    """
    bar_html = f"""
    <div style="
        width: 100%; 
        background-color: #FFFFFF; 
        border: 1px solid #999999; 
        border-radius: 5px; 
        height: 8px; 
        margin-bottom: 10px;
        overflow: hidden;">
        <div style="
            width: 0%; 
            background-color: {PRIMARY_COLOR}; 
            height: 100%; 
            border-radius: 4px;
            animation: fillProgress {duration_seconds}s linear forwards;">
        </div>
    </div>
    """
    placeholder = st.empty()
    placeholder.markdown(bar_html, unsafe_allow_html=True)
    time.sleep(duration_seconds)
    placeholder.empty()

def add_bot_message(text, image=None, caption=None, contrast=None, highlight_word=None, delay=True, msg_id=None):
    """
    Fügt Bot-Nachricht hinzu.
    msg_id: Eindeutige ID zur Identifizierung der Nachricht (verhindert Loops)
    """
    
    if text and highlight_word and highlight_word in text:
        text = text.replace(highlight_word, f"<span style='color: {HIGHLIGHT_TEXT_COL}; font-weight: bold;'>{highlight_word}</span>")
    
    # NEU: Prüfen, ob wirklich Text existiert, um leere Boxen zu vermeiden
    has_text_content = (text and text.strip()) or (contrast and contrast.strip())
    
    full_inner_html = ""
    if has_text_content:
        full_inner_html = f"<div>{text}</div>"
        if contrast:
            full_inner_html += f"<div class='contrast-text'>{contrast}</div>"

    if delay:
        with st.chat_message("assistant", avatar="🌿"):
            if image:
                st.image(image, caption=caption, use_container_width=True)
            
            # Nur wenn Text da ist, Typing Indicator und Box anzeigen
            if has_text_content:
                msg_placeholder = st.empty()
                msg_placeholder.markdown("<div class='typing-indicator'>✍️ Flori schreibt...</div>", unsafe_allow_html=True)
                
                # Dynamische Zeitberechnung
                clean_text = re.sub(r'<[^>]+>', '', text if text else "")
                if contrast:
                    clean_text += contrast
                    
                calculated_delay = 1.5 + (len(clean_text) * 0.03)
                final_delay = min(calculated_delay, 5.0)
                
                time.sleep(final_delay)
                
                # Überschreiben des Placeholders
                msg_placeholder.markdown(f"<div class='bot-message chat-message'>{full_inner_html}</div>", unsafe_allow_html=True)

    # Nachricht mit ID in History speichern
    # Wenn kein Text da ist, speichern wir einen leeren String, damit das UI später weiß, dass nichts gerendert werden soll
    st.session_state['history'].append({
        "role": "bot",
        "content": full_inner_html if has_text_content else "",
        "image": image,
        "caption": caption,
        "msg_id": msg_id
    })

def add_user_message(text):
    st.session_state['history'].append({
        "role": "user",
        "content": text
    })

# ---------- UI Rendering ----------

# Header (Weiß & Grün)
st.markdown(f"""
<div class="header-container" style='background-color:{PRIMARY_COLOR}; padding:15px; border-radius:5px; margin-bottom:20px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);'>
    <h1 class="white-header" style='margin:0; font-size:24px; font-weight: bold;'>Flori 🌿 <span style="font-size:14px; opacity:0.9; font-weight: normal;">| KI-Assistent zur Pflanzenidentifikation</span></h1>
</div>
""", unsafe_allow_html=True)

# 1. Chat Verlauf anzeigen
for msg in st.session_state['history']:
    if msg['role'] == "bot":
        with st.chat_message("assistant", avatar="🌿"):
            if msg.get('image'):
                st.image(msg['image'], caption=msg['caption'], use_container_width=True)
            
            # NEU: Nur rendern, wenn Inhalt existiert! (Verhindert leere grüne Boxen beim Reload)
            if msg['content'] and msg['content'].strip():
                st.markdown(f"<div class='bot-message chat-message'>{msg['content']}</div>", unsafe_allow_html=True)
    else:
        with st.chat_message("user", avatar="👤"):
            st.markdown(f"<div class='user-message chat-message'>{msg['content']}</div>", unsafe_allow_html=True)

# 2. Logik-Controller

# --- STARTZUSTAND ---
if st.session_state['step_index'] == -1 and st.session_state['img'] is None:
    if len(st.session_state['history']) == 0:
        add_bot_message("Hallo, ich bin Flori. 🌿 Ich helfe dir Schritt für Schritt zu bestimmen, um welche Pflanze es sich auf dem gegebenen Bild handelt. Ich habe bereits ein Bild von dem Studienleiter bekommen, also können wir direkt loslegen!", delay=True, msg_id="welcome_msg")
        st.rerun()

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
    # Prüfen, ob die Bild-Nachricht schon da ist (via ID)
    photo_msg_id = "photo_loaded_msg"
    photo_msg_sent = any(m.get('msg_id') == photo_msg_id for m in st.session_state['history'])
    
    if not photo_msg_sent:
        thumb = st.session_state['img'].copy()
        thumb.thumbnail((400, 400))
        time.sleep(0.5)
        add_bot_message("Alles klar – hier ist das Bild. Bist du bereit für die Analyse?", image=thumb, caption="Das Foto", delay=True, msg_id=photo_msg_id)
        st.rerun()
    
    st.write("---")
    col_l, col_r = st.columns([3, 1])
    with col_r:
        if st.button("🔎 Analyse starten"):
            add_user_message("Analyse starten")
            st.session_state['step_index'] = 0
            st.rerun()

# --- HAUPT-FLOW (ANGEPASST) ---
elif 0 <= st.session_state['step_index'] < len(STEPS):
    current_step = STEPS[st.session_state['step_index']]
    
    # Prüfen, ob wir im letzten Schritt (Heatmap) sind
    is_last_step = (st.session_state['step_index'] == len(STEPS) - 1)
    
    # 1. Texte und Frage je nach Schritt anpassen
    if is_last_step:
        # Letzter Schritt: Andere Frage
        CONTINUE_QUESTION = "Soll ich mit diesen Ergebnissen die Pflanze identifizieren?"
        ANNOUNCE_TEXT = None # Keine Ankündigung im letzten Schritt
    else:
        # Normale Schritte
        CONTINUE_QUESTION = "Sollen wir die Analyse fortsetzen?"
        ANNOUNCE_TEXT = f"🔬 <i>Ich analysiere jetzt folgenden Bereich:</i> <b>{current_step['caption']}</b>..."

    # --- Generierung eindeutiger IDs für diesen Schritt ---
    step_id_prefix = f"step_{st.session_state['step_index']}"
    
    # IDs für Standard-Ablauf
    announce_msg_id = f"{step_id_prefix}_announce"
    expl_msg_id = f"{step_id_prefix}_expl"
    
    # Spezielle IDs für den Heatmap-Ablauf (Text und Bild getrennt)
    heatmap_text_id = f"{step_id_prefix}_heatmap_text"
    heatmap_img_id = f"{step_id_prefix}_heatmap_img"
    
    question_msg_id = f"{step_id_prefix}_quest"

    # Reset Flags
    announce_sent = False
    explanation_sent = False
    question_sent = False
    
    # --- PRÜFEN DER IDs IN DER HISTORY ---
    for msg in st.session_state['history']:
        # Ankündigung checken
        if msg.get('msg_id') == announce_msg_id:
            announce_sent = True
            
        # Erklärung checken (Unterscheidung normal vs. letzter Schritt)
        if not is_last_step:
            if msg.get('msg_id') == expl_msg_id:
                explanation_sent = True
        else:
            # Im letzten Schritt ist die Erklärung fertig, wenn das BILD (als 2. Teil) gesendet wurde
            if msg.get('msg_id') == heatmap_img_id:
                explanation_sent = True

        # Frage checken
        if msg.get('msg_id') == question_msg_id:
            question_sent = True

    # ------------------------------------------------------------------
    # PHASE 1: Ankündigung UND Erklärung
    # ------------------------------------------------------------------
    if not explanation_sent:
        
        # 1. Ankündigung (NUR wenn NICHT letzter Schritt)
        if not is_last_step and not announce_sent:
            if st.session_state['step_index'] == 0:
                time.sleep(0.2)
            add_bot_message(ANNOUNCE_TEXT, delay=True, msg_id=announce_msg_id)
            time.sleep(0.8) 
        
        # 2. Inhalt (Erklärung & Bild)
        
        # --> SPEZIALFALL: Letzter Schritt (Heatmap)
        if is_last_step:
            # Prüfen ob Text-Teil schon da ist
            text_already_sent = any(m.get('msg_id') == heatmap_text_id for m in st.session_state['history'])
            
            if not text_already_sent:
                # A) Erst den Text senden
                full_text = f"<p style='margin-bottom:10px; margin-top:0;'>{current_step['intro']}</p><p style='margin-bottom:0;'>{current_step['desc']}</p>"
                add_bot_message(
                    full_text,
                    contrast=current_step.get('contrast'),
                    delay=True,
                    msg_id=heatmap_text_id
                )
                st.rerun()
            else:
                # B) Dann das Bild senden (wenn Text schon da ist)
                if os.path.exists(current_step['custom_img_path']):
                    hm_img = Image.open(current_step['custom_img_path']).convert("RGB")
                    add_bot_message(
                        "", # Kein Text, nur Bild. DANK FIX OBEN ERSCHEINT JETZT KEINE LEERE BOX MEHR.
                        image=hm_img,
                        caption=current_step['caption'],
                        delay=True,
                        msg_id=heatmap_img_id 
                    )
                st.rerun()

        # --> STANDARD: Normale Schritte (Bild + Text zusammen)
        else:
            final_img = None
            caption_suffix = ""

            if 'custom_img_path' in current_step:
                # ... (Logic wie vorher) ...
                c_path = current_step['custom_img_path']
                if os.path.exists(c_path):
                    final_img = Image.open(c_path).convert("RGB")
            else:
                crops = get_crops(st.session_state['img'])
                crop_img = crops.get(current_step['img_key'])
                
                if current_step['use_img_highlight']:
                    r_factor = current_step.get('radius_factor', 0.45) 
                    final_img = add_highlight_to_crop(crop_img, radius_factor=r_factor)
                    caption_suffix = " (Fokus)"
                else:
                    final_img = crop_img
            
            full_text = f"<p style='margin-bottom:10px; margin-top:0;'>{current_step['intro']}</p><p style='margin-bottom:0;'>{current_step['desc']}</p>"
            
            add_bot_message(
                full_text, 
                image=final_img, 
                caption=current_step['caption'] + caption_suffix,
                contrast=current_step.get('contrast'),
                highlight_word=current_step.get('highlight_word'),
                delay=True,
                msg_id=expl_msg_id
            )
            st.rerun()

    # PHASE 2: Verzögerung + Frage stellen
    elif explanation_sent and not question_sent:
        
        info_placeholder = st.empty()
        info_placeholder.caption("⏳ Weitere Analyse wird durchgeführt...")
        
        # Kurze Pause für den Flow
        show_smooth_progress_bar(duration_seconds=3 if is_last_step else 5)
        
        info_placeholder.empty() 
        
        add_bot_message(f"<b>{CONTINUE_QUESTION}</b>", delay=True, msg_id=question_msg_id) 
        st.rerun()

    # PHASE 3: Button anzeigen
    else:
        st.write("---")
        col_l, col_r = st.columns([3, 1])
        
        # Dynamischer Button-Text
        button_label = "Pflanze identifizieren" if is_last_step else "➡️ Analyse fortsetzen"
        
        with col_r:
            if st.button(button_label, key=f"next_{st.session_state['step_index']}"):
                add_user_message(button_label) # User message passt sich auch an
                st.session_state['step_index'] += 1
                st.rerun()

# --- ENDE / ERGEBNIS / CODE-ANZEIGE ---
elif st.session_state['step_index'] >= len(STEPS):
    
    if not st.session_state['finished']:
        # 1. Ergebnis
        # Auch hier können wir IDs nutzen, um ganz sicher zu gehen
        res_msg_id = "result_final_msg"
        if not any(m.get('msg_id') == res_msg_id for m in st.session_state['history']):
            add_bot_message("✅ <b>Ergebnis:</b> Bei dieser Pflanze handelt es sich eindeutig um einen Hibiskus (Hibiscus rosa-sinensis).", delay=True, msg_id=res_msg_id)
            time.sleep(3) 
        
        # 2. Pflege-Bild 
        care_msg_id = "care_img_msg"
        if os.path.exists(CARE_IMG_PATH) and not any(m.get('msg_id') == care_msg_id for m in st.session_state['history']):
            care_img = Image.open(CARE_IMG_PATH).convert("RGB")
            add_bot_message(
                "", # KEIN TEXT -> KEINE LEERE BOX DURCH FIX
                image=care_img,
                caption="Links: Fingertest zur Wasserkontrolle | Rechts: Schnitt über einem Auge",
                delay=True,
                msg_id=care_msg_id
            )
        
        # 3. Pflege-Tipps Text
        tips_msg_id = "tips_text_msg"
        if not any(m.get('msg_id') == tips_msg_id for m in st.session_state['history']):
            tip_text = """💡 <b>Profi-Pflegetipps für den Chinesischen Roseneibisch (Hibiscus rosa-sinensis):</b><br><br>
<ul style='padding-left: 20px;'>
<li><b>🚿 Wasserbedarf:</b> Der Hibiskus ist durstig! Im Sommer täglich gießen, aber <b>Staunässe unbedingt vermeiden</b> (Wurzelfäule-Gefahr). <br><i>Tipp:</i> Mach die Fingerprobe! </li>
<li><b>☀️ Standort & Licht:</b> Er liebt es hell, aber keine pralle Mittagssonne hinter Glas (Verbrennungsgefahr). Im Sommer blüht er am besten an einem windgeschützten Platz im Freien.</li>
<li><b>🧴 Nährstoffe:</b> Als "Starkzehrer" braucht er viel Energie. Gib von April bis September wöchentlich flüssigen Kübelpflanzendünger ins Gießwasser. Gelbe Blätter deuten oft auf Eisenmangel hin (Chlorose).</li>
<li><b>❄️ Überwinterung:</b> Diese Art ist <b>nicht winterhart</b>! Hol ihn rein, sobald es nachts unter 12°C wird. Er überwintert am besten hell bei ca. 15°C. <br><i>Hinweis:</i> Blattabwurf im Winter ist bei trockener Heizungsluft normal – sprühe ihn gelegentlich mit Wasser ein.</li>
<li><b>✂️ Schnitt:</b> Ein kräftiger Rückschnitt im Februar/März fördert die Verzweigung. Da Hibiskus nur an den neuen Trieben blüht, sorgt der Schnitt für mehr Blüten im Sommer.</li>
</ul>"""
            add_bot_message(tip_text, delay=True, msg_id=tips_msg_id)
        
        st.session_state['finished'] = True
        st.rerun() 
    
    st.success("Chat beendet. Vielen Dank für die Teilnahme!")

    # ----------------------------------------------------
    # FINAL: Button (Groß & Mittig & Grün) -> 5 Sekunden Timer -> Code
    # ----------------------------------------------------
    
    if not st.session_state['final_timer_done']:
        st.write("---")
        
        _, col_mid, _ = st.columns([1, 2, 1])
        with col_mid:
            if st.button("🔐 CODE FÜR UMFRAGE GENERIEREN", type="primary"):
                placeholder = st.empty()
                with placeholder.container():
                    st.info("Dein Bestätigungscode wird generiert... Bitte warten.")
                    # Auch hier die neue Animation
                    show_smooth_progress_bar(duration_seconds=5)
                
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

        st.info("Bitte gebe den Code nun unten in das Feld ein um fortfahren zu können.")
        
        st.write("---")
        col_l, col_r = st.columns([3, 1])
        with col_r:
            if st.button("🔄 Neuer Durchlauf"):
                st.session_state.clear()
                st.rerun()