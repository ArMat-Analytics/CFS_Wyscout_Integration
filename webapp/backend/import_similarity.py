import pandas as pd
import os
from pathlib import Path
from sqlalchemy import create_engine
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    print("Error: DATABASE_URL environment variable is not set.")
    exit(1)

print(f"Connecting to database...")
engine = create_engine(DATABASE_URL)

# CSV lives in H4_Player_Similarity/data/ (two levels up from webapp/backend to repo root, then H4)
csv_path = Path(__file__).resolve().parents[2] / "H4_Player_Similarity" / "data" / "player_similarity.csv"
print(f"Reading similarity CSV from {csv_path}...")
df = pd.read_csv(csv_path)

table_name = "player_similarity"
print(f"Importing to table '{table_name}'...")
df.to_sql(table_name, engine, if_exists="replace", index=False)
print("Done!")
