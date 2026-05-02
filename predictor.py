import os
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import timesfm

def get_timesfm_prediction(historie):
    print(f"Starte TimesFM mit {len(historie)} Datenpunkten...")
    
    try:
        # 1. TimesFM Modell initialisieren (für CPU in GitHub Actions)
        tfm = timesfm.TimesFm(
            context_len=24,       # Wir schauen uns bis zu 24 Stunden an
            horizon_len=1,        # Wir wollen 1 Stunde in die Zukunft schauen
            input_patch_len=32,
            output_patch_len=128,
            backend='cpu'         # GitHub Actions nutzt die CPU
        )
        
        # 2. Die Gewichte (das "Wissen") des Modells herunterladen
        print("Lade KI-Gewichte von Google (TimesFM-1.0-200m)...")
        tfm.load_from_checkpoint(repo_id="google/timesfm-1.0-200m")
        
        # 3. Vorhersage machen
        forecast_daten = tfm.forecast([historie])
        
        # 4. Das Ergebnis auslesen
        ki_preis = float(forecast_daten[0][0])
        
        return round(ki_preis, 3)
        
    except Exception as e:
        print(f"Fehler bei der KI-Berechnung: {e}")
        # Falls die KI abstürzt (z.B. weil GitHub zu wenig Speicher hat), 
        # geben wir als Notlösung den letzten gemessenen Preis zurück
        if historie:
            return historie[-1]
        return 0.0

def run_predictor():
    gcp_json = os.environ.get("GCP_SERVICE_ACCOUNT")
    
    if not gcp_json:
        print("Fehler: Keine Google Cloud Zugangsdaten gefunden!")
        return

    try:
        # 1. Verbindung zum Google Sheet aufbauen
        creds_dict = json.loads(gcp_json)
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        sheet = client.open("Tankprotokoll").sheet1

        # 2. Alle Daten holen
        alle_daten = sheet.get_all_records()
        
        # 3. Wir konzentrieren uns erst einmal auf Diesel
        diesel_daten = []
        zeilen_nummern = []
        
        aktuelle_zeile = 2 
        
        for row in alle_daten:
            if str(row.get('Sorte', '')).lower() == 'diesel':
                try:
                    preis = float(str(row.get('Bestpreis', '')).replace(',', '.'))
                    diesel_daten.append(preis)
                    zeilen_nummern.append(aktuelle_zeile)
                except ValueError:
                    # Falls doch noch Text wie "Warten..." drin steht, überspringen
                    pass 
            aktuelle_zeile += 1

        # 4. Prüfen, ob wir überhaupt Daten haben
        if not diesel_daten:
            print("Noch keine Diesel-Preise gefunden.")
            return

        if len(diesel_daten) < 24:
            print(f"Hinweis: Wir haben erst {len(diesel_daten)} Punkte. TimesFM schaut sich die trotzdem schon mal an!")

        # Wir nehmen maximal die letzten 24 Stunden für die Vorhersage
        historie_fuer_ki = diesel_daten[-24:]
        
        # 5. KI nach der Vorhersage fragen
        ki_preis = get_timesfm_prediction(historie_fuer_ki)
        
        # 6. Vorhersage in die Tabelle eintragen (Spalte E = 5)
        letzte_diesel_zeile = zeilen_nummern[-1]
        sheet.update_cell(letzte_diesel_zeile, 5, ki_preis)
        
        print(f"Erfolg: KI-Preis ({ki_preis}€) in Zeile {letzte_diesel_zeile} (Spalte E) eingetragen!")

    except Exception as e:
        print(f"Fehler im Predictor: {e}")

if __name__ == "__main__":
    run_predictor()
