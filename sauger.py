import os
import json
import requests
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

def run_sauger():
    # 1. API Keys laden (werden vom GitHub-Tresor bereitgestellt)
    tk_key = os.environ.get("TANKERKOENIG_API_KEY")
    gcp_json = os.environ.get("GCP_SERVICE_ACCOUNT")
    
    if not tk_key or not gcp_json:
        print("Fehler: API-Keys fehlen!")
        return

    # 2. Tankerkönig abfragen (Suche nach der günstigsten E5-Tankstelle im Umkreis)
    lat = 54.516
    lng = 9.565
    url = f"https://creativecommons.tankerkoenig.de/json/list.php?lat={lat}&lng={lng}&rad=5&sort=price&type=e5&apikey={tk_key}"
    
    try:
        response = requests.get(url)
        data = response.json()
        
        if data.get("ok") and len(data.get("stations", [])) > 0:
            bester_preis = data["stations"][0]["price"]
            station_name = data["stations"][0]["name"]
        else:
            print("Keine Tankstellen-Daten gefunden.")
            return
    except Exception as e:
        print(f"Fehler bei der Tankerkönig-API: {e}")
        return

    # 3. In Google Sheets speichern
    try:
        # Den JSON-String wieder in ein Verzeichnis umwandeln
        creds_dict = json.loads(gcp_json)
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        
        sheet = client.open("Tankprotokoll").worksheet("Tabellenblatt1")
        
        zeitstempel = datetime.now().strftime("%d.%m.%Y %H:%M")
        
        # Die Spaltenstruktur: Zeit | Ort | Sorte | Preis | KI-Preis | Differenz | Bot-Notiz | Station
        neue_zeile = [zeitstempel, "24837", "e5", bester_preis, "", "", "🤖 Auto-Sauger", station_name]
        
        sheet.append_row(neue_zeile)
        print(f"Erfolgreich gespeichert: {bester_preis}€ bei {station_name}")
    except Exception as e:
        print(f"Fehler bei Google Sheets: {e}")

if __name__ == "__main__":
    run_sauger()
