import os
import pandas as pd
import requests
import time

def load_table(table_name, batch_size=1000, pause=0.5, max_batch=None):
    base_url = f'https://data.epa.gov/efservice/{table_name}/{{start}}:{{end}}/JSON'
    all_data = []
    start = 1
    batch_count = 0

    while True:
        end = start + batch_size - 1
        url = base_url.format(start=start, end=end)
        print(f"Downloading: {table_name} [{start}:{end}]")

        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            data = response.json()
        except Exception as e:
            print(f"❌ Request error: {e}")
            break

        if not data:
            print("✅ End of data.")
            break

        all_data.extend(data)
        start += batch_size
        batch_count += 1

        if max_batch and batch_count >= max_batch:
            print(f"⚠️ Batch limit reached ({max_batch})")
            break

        time.sleep(pause)

    return pd.DataFrame(all_data)

def load_update_table(table_name, folder='epa', force_update=False):
    os.makedirs(folder, exist_ok=True)
    file_path = os.path.join(folder, f"{table_name}.csv")

    if os.path.exists(file_path) and not force_update:
        print(f"📁 Reading from cache: {file_path}")
        return pd.read_csv(file_path)

    print(f"🔄 Downloading data from API for: {table_name}")
    df = load_table(table_name)

    print(f"💾 Saving local cache to: {file_path}")
    df.to_csv(file_path, index=False)

    return df
