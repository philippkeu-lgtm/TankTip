import streamlit as st
from supabase import create_client
from PIL import Image
import io
import google.generativeai as genai
import json
import base64
import time

# --- 1. SEITEN-KONFIGURATION ---
st.set_page_config(page_title="Die Schatzkiste", layout="wide", page_icon="💎")

# --- 2. DAS GEHEIMNISVOLLE PORTAL (PASSWÖRTER) ---
# Hier sind die geheimen Passwörter
GEHEIME_PASSWOERTER = ["Drachenfeuer", "Zauberstab", "Feenstaub", "Piratengold", "Ritterburg"]

if "eingeloggt" not in st.session_state:
    st.session_state.eingeloggt = False

if not st.session_state.eingeloggt:
    st.markdown("<h1 style='text-align: center; font-family: \"Press Start 2P\", monospace; color: #4a2e15; margin-top: 50px;'>Das Geheime Portal</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; font-size: 24px;'>Sprich das geheime Losungswort, um die Schatzkiste zu öffnen!</p>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        passwort_eingabe = st.text_input("Losungswort:", type="password")
        if st.button("🚪 EINTRETEN 🚪"):
            if passwort_eingabe in GEHEIME_PASSWOERTER:
                st.session_state.eingeloggt = True
                st.rerun()
            else:
                st.error("Falsches Losungswort! Das Portal bleibt verschlossen.")
    
    st.stop()

# --- 3. VERBINDUNGEN (Supabase & Gemini KI) ---
url = st.secrets["SUPABASE_URL"]
key = st.secrets["SUPABASE_KEY"]
supabase = create_client(url, key)

gemini_key = st.secrets["GEMINI_API_KEY"]
genai.configure(api_key=gemini_key)
model = genai.GenerativeModel('gemini-2.5-flash') 

# WICHTIG: Projekt-ID eintragen!
PROJEKT_ID = "hlfaeckobtfkwywrmpgt" 

# --- HILFSFUNKTION FÜR BILDER ---
@st.cache_data
def get_transparent_egg(file_path):
    try:
        img = Image.open(file_path).convert("RGBA")
        datas = img.getdata()
        new_data = []
        for item in datas:
            if item[0] > 190 and item[1] > 200 and item[2] > 210:
                new_data.append((255, 255, 255, 0))
            else:
                new_data.append(item)
        img.putdata(new_data)
        
        buffered = io.BytesIO()
        img.save(buffered, format="PNG")
        return base64.b64encode(buffered.getvalue()).decode()
    except FileNotFoundError:
        return None

ei_base64 = get_transparent_egg("ei.png")

# --- 4. HEADER BILD ---
try:
    st.image("hintergrund.png", use_container_width=True)
except:
    pass 

# --- 5. CSS DESIGN (KINDGERECHT & RESPONSIVE FÜR HANDYS) ---
st.markdown(f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Press+Start+2P&family=VT323&display=swap');

    .stApp {{ background-color: #e8d5b5; }}

    @keyframes pulsieren {{
        0% {{ transform: scale(1); filter: drop-shadow(0 0 5px rgba(0,0,0,0.2)); }}
        50% {{ transform: scale(1.1); filter: drop-shadow(0 0 25px rgba(255,215,0,1)); }}
        100% {{ transform: scale(1); filter: drop-shadow(0 0 5px rgba(0,0,0,0.2)); }}
    }}

    .magisches-ei {{
        display: block; margin-left: auto; margin-right: auto;
        width: 160px; animation: pulsieren 2.5s infinite ease-in-out;
        image-rendering: pixelated; margin-bottom: 25px;
    }}

    /* --- PC STANDARD GRÖSSEN --- */
    h1, h2, h3 {{
        font-family: 'Press Start 2P', monospace !important;
        color: #4a2e15 !important; text-align: center;
        text-shadow: 2px 2px 0px #c5a070;
        line-height: 1.4 !important;
    }}

    p, label {{
        font-family: 'VT323', monospace !important; font-size: 28px !important; color: #2e1a0f;
    }}

    /* --- FIX: NAMENS-AUSWAHLBOX (SICHER & LESBAR) --- */
    div[data-baseweb="select"] > div {{
        background-color: #fff8e7 !important;
        border: 4px solid #4a2e15 !important;
        border-radius: 10px !important;
    }}
    div[data-baseweb="select"] span {{
        color: #4a2e15 !important; 
        font-family: 'VT323', monospace !important;
        font-size: 32px !important;
    }}
    /* Das Aufklapp-Menü */
    ul[data-baseweb="menu"] {{
        background-color: #fff8e7 !important;
        border: 4px solid #4a2e15 !important;
    }}
    ul[data-baseweb="menu"] li {{
        background-color: #fff8e7 !important;
    }}
    ul[data-baseweb="menu"] li span {{
        color: #4a2e15 !important;
        font-family: 'VT323', monospace !important;
        font-size: 28px !important;
    }}

    /* HAUPT-BUTTONS (Schatz in Kiste legen etc.) */
    div.stButton > button:first-child {{
        background-color: #FF4500 !important; color: white !important;
        font-family: 'Press Start 2P', monospace !important; font-size: 18px !important;
        padding: 30px !important; border: 8px solid #4a2e15 !important;
        border-radius: 15px !important; width: 100% !important;
        box-shadow: 8px 8px 0px 0px #4a2e15 !important;
    }}
    
    /* KAMERA RAHMEN & BUTTONS */
    [data-testid="stCameraInput"] {{
        border: 10px solid #FF4500 !important; border-radius: 15px !important;
        background-color: #fff8e7; box-shadow: 8px 8px 0px #4a2e15;
        padding: 10px !important; margin-top: 20px !important;
    }}

    [data-testid="stCameraInput"] button {{
        background-color: #FF0000 !important; color: white !important; 
        border: 6px solid #4a2e15 !important; border-radius: 40px !important; 
        height: 80px !important; font-family: 'VT323', monospace !important; 
        font-size: 35px !important; margin-top: 10px !important; 
        box-shadow: 4px 4px 0px #4a2e15 !important;
    }}

    [data-testid="stCameraInput"] button[title="Clear photo"],
    [data-testid="stCameraInput"] button:nth-of-type(2) {{
        background-color: #4a2e15 !important; color: white !important;
        border-radius: 10px !important; height: 50px !important;
        font-size: 20px !important; box-shadow: none !important;
        border: 4px solid #2e1a0f !important;
    }}

    /* --- SMARTPHONE ANPASSUNG (Media Query) --- */
    @media (max-width: 768px) {{
        h1 {{ font-size: 22px !important; }}
        h2 {{ font-size: 18px !important; }}
        h3 {{ font-size: 14px !important; }}
        
        p, label {{ font-size: 22px !important; }}
        
        div[data-baseweb="select"] span {{ font-size: 26px !important; }}
        
        div[data-testid="stVerticalBlock"] > div > div {{
            padding: 10px !important;
        }}
    }}
    </style>
""", unsafe_allow_html=True)

# --- DATEN ABRUFEN ---
try:
    response = supabase.table("schaetze").select("*").order("created_at", desc=True).execute()
    alle_schaetze = response.data
except:
    alle_schaetze = []

# --- 6. PROFIL & HELDENAUSWAHL ---
st.title("💎 Schatzkiste")

# Hier ist Philipp nun mit dabei!
alle_helden = ["Jonne", "Bosse", "Frido", "Philipp"]
ich_bin = st.selectbox("Wer bist du?", alle_helden)

meine_schaetze = [s for s in alle_schaetze if s.get('entdecker_name') == ich_bin]

if ei_base64:
    st.markdown(f'<img src="data:image/png;base64,{ei_base64}" class="magisches-ei">', unsafe_allow_html=True)

# --- QUEST LOGIK ---
QUEST_KATEGORIE = "Stein"
QUEST_ZIEL = 3
bisherige_quest_items = len([s for s in meine_schaetze if s.get('kategorie') == QUEST_KATEGORIE])
quest_erledigt = bisherige_quest_items >= QUEST_ZIEL

# --- 7. QUEST-BOARD ---
st.divider()
col1, col2 = st.columns(2)

with col1:
    st.markdown("<div style='border: 6px dashed #4a2e15; padding: 15px; background: #e3f2fd;'>", unsafe_allow_html=True)
    st.subheader("📜 Wochenaufgabe")
    if quest_erledigt:
        st.markdown("✅ **GESCHAFFT!** Du bist ein Meister-Sucher! 🎉")
    else:
        st.markdown(f"Finde **{QUEST_ZIEL} Steine**! *(Du hast: {bisherige_quest_items}/{QUEST_ZIEL})*")
        st.markdown("🎁 **Belohnung:** +100 EP!")
    st.markdown("</div>", unsafe_allow_html=True)

with col2:
    st.markdown("<div style='border: 6px dashed #4a2e15; padding: 15px; background: #fff9c4;'>", unsafe_allow_html=True)
    st.subheader("🏆 Deine XP")
    meine_xp = sum([s.get('xp', 0) for s in meine_schaetze])
    st.markdown(f"⭐ **{meine_xp} Erfahrungspunkte**")
    st.markdown("Das Ei wächst und wächst... 🥚✨")
    st.markdown("</div>", unsafe_allow_html=True)

# --- 8. FORMULAR: MAGISCHER SCANNER ---
st.divider()

st.markdown("<h1 style='font-size: 30px; text-align: center;'>📸 FOTO MACHEN! 📸</h1>", unsafe_allow_html=True)

# Ein kleiner Hinweis zum Umdrehen der Kamera
st.markdown("<p style='text-align: center; font-size: 22px; color: #4a2e15; background-color: rgba(255,255,255,0.5); border-radius: 10px; padding: 5px;'>🔄 <b>Tipp:</b> Nutze den Knopf oben rechts im Bild, um die Kamera umzudrehen!</p>", unsafe_allow_html=True)

st.markdown("<h2 style='text-align: center; color: #FF0000;'>👇 DRÜCKE DEN ROTEN KNOPF! 👇</h2>", unsafe_allow_html=True)

foto = st.camera_input("")

def process_image(uploaded_file):
    img = Image.open(uploaded_file).convert("RGB")
    img.thumbnail((800, 800))
    buffer = io.BytesIO()
    img.save(buffer, format="JPEG", quality=70)
    return buffer.getvalue(), img

if st.button("💎 IN DIE SCHATZKISTE LEGEN 💎"):
    if foto:
        with st.spinner("Das Orakel schaut genau hin... 👀✨"):
            try:
                img_bytes, pil_image = process_image(foto)
                
                ki_prompt = """Du bist ein lustiges magisches Orakel für Kindergarten-Kinder.
                Analysiere das Bild und antworte NUR im JSON Format: {"kategorie": "...", "seltenheit": "...", "lustiger_name": "..."}
                Kategorien: Wähle aus (Stein, Holz, Blatt) ODER erfinde Quatsch-Kategorien (Drachenschuppe, Troll-Popel, Feenstaub, Dinosaurierknochen, Piratengold, Alien-Schleim), wenn es komisch aussieht!
                Lustiger Name: Gib dem Ding einen super lustigen, fantasievollen Namen (z.B. "Glitzernder Matsch-Käfer").
                Seltenheit: Häufig, Selten, Episch, Legendär."""
                
                ki_antwort = model.generate_content([ki_prompt, pil_image])
                ki_daten = json.loads(ki_antwort.text.replace("```json", "").replace("```", "").strip())
                
                kategorie = ki_daten.get("kategorie", "Sonstiges")
                seltenheit = ki_daten.get("seltenheit", "Häufig")
                lustiger_name = ki_daten.get("lustiger_name", "Geheimnisvolles Ding")
                
                file_name = f"{ich_bin}_{lustiger_name.replace(' ', '_')}_{id(foto)}.jpg"
                supabase.storage.from_("schatz_bilder").upload(file_name, img_bytes)
                img_url = f"https://{PROJEKT_ID}.supabase.co/storage/v1/object/public/schatz_bilder/{file_name}"
                
                xp_werte = {"Häufig": 10, "Selten": 25, "Episch": 50, "Legendär": 100}
                punkte = xp_werte.get(seltenheit, 10)
                
                wird_quest_jetzt_erledigt = False
                if kategorie == QUEST_KATEGORIE and bisherige_quest_items + 1 == QUEST_ZIEL:
                    wird_quest_jetzt_erledigt = True
                    punkte += 100 
                
                schatz_daten = {
                    "schatz_name": lustiger_name, 
                    "kategorie": kategorie,
                    "seltenheit": seltenheit,
                    "bild_url": img_url,
                    "entdecker_name": ich_bin,
                    "xp": punkte
                }
                supabase.table("schaetze").insert(schatz_daten).execute()
                
                if wird_quest_jetzt_erledigt:
                    st.snow() 
                    st.balloons()
                    st.success(f"🎉 WOCHENAUFGABE GESCHAFFT! Du bekommst fette +{punkte} XP! 🎉")
                    time.sleep(3)
                else:
                    st.balloons()
                    if seltenheit in ["Episch", "Legendär"]:
                        st.success(f"WOAAAH! Ein {seltenheit}er Fund! Das ist ein {lustiger_name}! (+{punkte} XP)")
                    else:
                        st.success(f"Hihi! Du hast einen '{lustiger_name}' gefunden! (+{punkte} XP)")
                    time.sleep(2.5)
                    
                st.rerun()
                
            except Exception as e:
                st.error(f"☠️ Oh nein, der Zauberstab klemmt: {e}")
    else:
        st.warning("⚠️ Halt! Du musst erst ein Foto machen! 📸")

# --- 9. DAS INVENTAR ---
st.divider()

def render_grid(schaetze_liste, tab_name):
    if not schaetze_liste:
        st.info("Noch leer. Los, ab nach draußen! 🏃‍♂️💨")
        return

    cols = st.columns(3) 
    
    for index, s in enumerate(schaetze_liste):
        with cols[index % 3]:
            farben = {"Häufig": "#8B4513", "Selten": "#4169E1", "Episch": "#9932CC", "Legendär": "#FFD700"}
            hauptfarbe = farben.get(s.get('seltenheit', 'Häufig'), "#8B4513")
            
            st.markdown(f"""
            <div style="border: 6px solid #4a2e15; padding: 15px; text-align: center; background: #fff8e7; box-shadow: 8px 8px 0px {hauptfarbe}; margin-bottom: 10px;">
                <h3 style="margin:5px 0 15px 0; font-family: 'Press Start 2P', monospace; font-size: 14px; color: #4a2e15; text-shadow: none;">{s['schatz_name']}</h3>
                <div style="border: 6px solid #4a2e15; margin-bottom: 15px; background: #000;">
                    <img src="{s['bild_url']}" style="width: 100%; height: 200px; object-fit: cover; image-rendering: pixelated;">
                </div>
                <div style="background-color: {hauptfarbe}; color: white; padding: 6px 12px; display: inline-block; font-family: 'Press Start 2P', monospace; font-size: 12px; margin-bottom: 15px; border: 3px solid #4a2e15; text-transform: uppercase;">
                    {s.get('seltenheit', 'Häufig')} | ⭐ {s.get('xp', 10)} XP
                </div>
                <p style="font-size: 24px; color: #2e1a0f; margin: 0; font-weight: bold;">{s.get('kategorie', 'Sonstiges')}</p>
            </div>
            """, unsafe_allow_html=True)
            
            if st.button("🗑️ Wegwerfen", key=f"del_{tab_name}_{s['bild_url']}"):
                try:
                    supabase.table("schaetze").delete().eq("bild_url", s['bild_url']).execute()
                    file_name = s['bild_url'].split("/")[-1]
                    supabase.storage.from_("schatz_bilder").remove([file_name])
                    st.rerun()
                except:
                    pass
            st.markdown("<br>", unsafe_allow_html=True)

tab_gruppe, tab_ich = st.tabs(["🎒 Alle Schätze", f"🛡️ {ich_bin}s Schätze"])

with tab_gruppe:
    render_grid(alle_schaetze, "alle")
with tab_ich:
    render_grid(meine_schaetze, "ich")
