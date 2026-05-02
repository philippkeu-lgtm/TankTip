import os
import json
import requests
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import pytz

def run_sauger():
    tz = pytz.timezone('Europe/Berlin')
    zeit_jetzt = datetime.now(tz).strftime("%d.%m.%Y %H:%M")
    
    tk_key = os.environ.get("TANKERKOENIG_API_KEY")
    gcp_json = os.environ.get("GCP_SERVICE_ACCOUNT")
    
    # Wir fragen im Umkreis von 5km ALLE Sorten ab
    url = f"https://creativecommons.tankerkoenig.de/json/list.php?lat=54.521&lng=9.551&rad=5&sort=dist&type=all&apikey={tk_key}"
    
    try:
        creds_dict = json.loads(gcp_json)
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        sheet = client.open("Tankprotokoll").sheet1

        response = requests.get(url)
        data = response.json()
        
        if data.get("ok"):
            stations = data.get("stations", [])
            
            # Wir erfassen jetzt einfach die Preise der ersten 3 Stationen,
            # um sicherzugehen, dass E5, E10 und Diesel dabei sind!
            for s in stations[:3]: 
                s_name = s.get("name", "Unbekannt")
                preise = {
                    "e5": s.get("e5"),
                    "e10": s.get("e10"),
                    "diesel": s.get("diesel")
                }
                
                for sorte, preis in preise.items():
                    if preis and preis > 0:
                        zeile = [zeit_jetzt, "24837", sorte, preis, "", "", "🤖 Auto-Sauger", s_name]
                        sheet.append_row(zeile)
                        print(f"Eingetragen: {sorte} ({preis}€) von {s_name}")
        else:
            print("API Fehler")

    except Exception as e:
        print(f"Fehler: {e}")

if __name__ == "__main__":
    run_sauger()
