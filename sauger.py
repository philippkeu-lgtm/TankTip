import os
import json
import requests
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import pytz

def run_sauger():
    # 1. Deutsche Zeit einstellen
    tz = pytz.timezone('Europe/Berlin')
    zeit_jetzt = datetime.now(tz).strftime("%d.%m.%Y %H:%M")
    
    # 2. API-Keys und Zugangsdaten holen
    tk_key = os.environ.get("TANKERKOENIG_API_KEY")
    gcp_json = os.environ.get("GCP_SERVICE_ACCOUNT")
    
    # 3. Tankerkönig abfragen: type=all holt E5, E10 und Diesel gleichzeitig
    # Koordinaten für Schleswig (rund um die Flensburger Str.)
    url = f"https://creativecommons.tankerkoenig.de/json/list.php?lat=54.526&lng=9.546&rad=4&sort=dist&type=all&apikey={tk_key}"
    
    try:
        # 4. Verbindung zu Google Sheets aufbauen
        creds_dict = json.loads(gcp_json)
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        
        # Öffnet dein Dokument
        sheet = client.open("Tankprotokoll").sheet1

        print("Frage Tankerkönig ab...")
        response = requests.get(url)
        data = response.json()
        
        # 5. Daten auswerten
        if data.get("ok") and len(data.get("stations", [])) > 0:
            
            # Wir suchen gezielt nach der WIKING Tankstelle
            ziel_station = None
            for station in data["stations"]:
                if "WIKING" in station.get("name", "").upper():
                    ziel_station = station
                    break
            
            # Fallback: Falls WIKING gerade unsichtbar ist, nehmen wir die nächste verfügbare
            if not ziel_station:
                ziel_station = data["stations"][0]
                print(f"WIKING nicht gefunden, nutze Alternative: {ziel_station.get('name')}")
            
            station_name = ziel_station.get("name", "Unbekannt")
            
            # Alle drei Preise sichern (falls eine Sorte leer ist, steht dort None)
            preise = {
                "e5": ziel_station.get("e5"),
                "e10": ziel_station.get("e10"),
                "diesel": ziel_station.get("diesel")
            }
            
            # 6. Für jede gefundene Spritsorte eine eigene Zeile anlegen
            for sorte, preis in preise.items():
                if preis: # Nur eintragen, wenn die API wirklich einen Preis liefert
                    # Aufbau der Zeile: Zeitstempel | PLZ | Sorte | Preis | KI_Ziel | Empfehlung | News_Status | Tankstelle
                    zeile = [zeit_jetzt, "24837", sorte, preis, "", "", "🤖 Auto-Sauger", station_name]
                    sheet.append_row(zeile)
                    print(f"Erfolg: {sorte.upper()} für {preis}€ bei {station_name} eingetragen.")
        else:
            print("Fehler: Keine Stationen gefunden oder API-Limit erreicht.")

    except Exception as e:
        print(f"Fehler beim Ausführen des Skripts: {e}")

if __name__ == "__main__":
    run_sauger()
