import os
import csv
import glob

# Directory path
DIRECTORY = r"C:\AI\aJizdniVykony\delay\data\csv\test"

# Delimiter settings
INPUT_DELIMITER = ","   # Change this to ";" if your original files are ALREADY semicolon-separated
OUTPUT_DELIMITER = ";"  # This forces the new files to use semicolons so Excel reads them correctly

# The new, correct header (12 columns)
NEW_HEADER = [
    "ID Záznamu", "Timestamp", "Den", "Čas příjezdu", "Linka", 
    "Oběh", "Vozidlo", "Zpoždění (min)", "Zastávka", "Směr", 
    "Zeměpisná šířka (Lat)", "Zeměpisná délka (Lon)"
]

def fix_csv_headers(directory):
    csv_files = glob.glob(os.path.join(directory, "*.csv"))
    
    if not csv_files:
        print(f"No CSV files found in {directory}.")
        return

    for filepath in csv_files:
        filename = os.path.basename(filepath)
        
        # 1. Read the original file
        try:
            with open(filepath, mode='r', encoding='utf-8-sig', newline='') as infile:
                # Added the input delimiter here
                reader = csv.reader(infile, delimiter=INPUT_DELIMITER)
                
                try:
                    current_header = next(reader)
                except StopIteration:
                    print(f"Skipping (empty file): {filename}")
                    continue
                
                rows = []
                for row in reader:
                    # If data has only 10 columns, add the 2 missing empty columns
                    if len(row) == 10:
                        row.insert(5, "")  # Empty value for Oběh
                        row.insert(6, "")  # Empty value for Vozidlo
                    
                    rows.append(row)
        except Exception as e:
            print(f"Error reading file {filename}: {e}")
            continue
            
        # 2. Write to the same file with the new header and semicolon delimiter
        try:
            with open(filepath, mode='w', encoding='utf-8-sig', newline='') as outfile:
                # Added the output delimiter here (semicolon for Excel)
                writer = csv.writer(outfile, delimiter=OUTPUT_DELIMITER)
                
                # Write the new header
                writer.writerow(NEW_HEADER)
                
                # Write the modified data
                writer.writerows(rows)
                
            print(f"Successfully fixed: {filename}")
            
        except Exception as e:
            print(f"Error writing to file {filename}: {e}")

if __name__ == "__main__":
    fix_csv_headers(DIRECTORY)
    print("Done!")