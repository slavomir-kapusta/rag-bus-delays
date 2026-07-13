import os
import csv
import glob

# Cesta k adresáři s CSV soubory
DIRECTORY = r"C:\AI\aJizdniVykony\delay\data\csv\test"

# Nová, správná hlavička (12 sloupců)
NEW_HEADER = [
    "ID Záznamu"; "Timestamp"; "Den"; "Čas příjezdu"; "Linka"; 
    "Oběh"; "Vozidlo"; "Zpoždění (min)"; "Zastávka"; "Směr"; 
    "Zeměpisná šířka (Lat)"; "Zeměpisná délka (Lon)"
]

def fix_csv_headers(directory):
    # Hledání všech .csv souborů ve složce
    csv_files = glob.glob(os.path.join(directory, "*.csv"))
    
    if not csv_files:
        print(f"V adresáři {directory} nebyly nalezeny žádné CSV soubory.")
        return

    for filepath in csv_files:
        filename = os.path.basename(filepath)
        
        # 1. Přečtení původního souboru
        try:
            # Používáme utf-8-sig pro bezpečné zpracování s BOM (časté u Windows Excelu)
            with open(filepath, mode='r', encoding='utf-8-sig', newline='') as infile:
                reader = csv.reader(infile)
                
                try:
                    current_header = next(reader)
                except StopIteration:
                    print(f"Přeskočeno (prázdný soubor): {filename}")
                    continue
                
                rows = []
                for row in reader:
                    # Pokud mají data stále jen 10 sloupců jako stará hlavička,
                    # přidáme 2 prázdné sloupce pro "Oběh" (index 5) a "Vozidlo" (index 6).
                    if len(row) == 10:
                        row.insert(5, "")  # Prázdná hodnota pro Oběh
                        row.insert(6, "")  # Prázdná hodnota pro Vozidlo
                    
                    rows.append(row)
        except Exception as e:
            print(f"Chyba při čtení souboru {filename}: {e}")
            continue
            
        # 2. Zápis do stejného souboru s novou hlavičkou
        try:
            with open(filepath, mode='w', encoding='utf-8-sig', newline='') as outfile:
                writer = csv.writer(outfile)
                
                # Zápis nové hlavičky
                writer.writerow(NEW_HEADER)
                
                # Zápis upravených dat
                writer.writerows(rows)
                
            print(f"Úspěšně opraveno: {filename}")
            
        except Exception as e:
            print(f"Chyba při zápisu do souboru {filename}: {e}")

if __name__ == "__main__":
    fix_csv_headers(DIRECTORY)
    print("Hotovo!")