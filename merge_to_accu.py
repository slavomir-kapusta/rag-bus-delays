import os
import pandas as pd
import glob

# 1. Define the folder path and the output file name
folder_path = r"C:\AI\aJizdniVykony\delay\data\accu"
output_file = os.path.join(folder_path, "accu_17mar_21apr.csv")

# 2. Find all CSV files in the folder
# We use glob to match all files ending in .csv
csv_files = glob.glob(os.path.join(folder_path, "*.csv"))

# Exclude the output file from the list just in case it already exists from a previous run
csv_files = [f for f in csv_files if not f.endswith("accu_17mar_21apr.csv")]

df_list = []

# 3. Loop through the list of files and read them into a pandas DataFrame
for file in csv_files:
    try:
        # Using sep=';' based on the structure of the file you uploaded
        df = pd.read_csv(file, sep=';', on_bad_lines='skip')
        df_list.append(df)
        print(f"Successfully loaded: {os.path.basename(file)}")
    except Exception as e:
        print(f"Error reading {file}: {e}")

# 4. Concatenate all dataframes and export to a single CSV
if df_list:
    merged_df = pd.concat(df_list, ignore_index=True)
    
    # Save the merged dataframe to the specified output file
    merged_df.to_csv(output_file, sep=';', index=False)
    print(f"\nSuccess! Merged {len(csv_files)} files into {output_file}")
else:
    print("\nNo CSV files found to merge.")