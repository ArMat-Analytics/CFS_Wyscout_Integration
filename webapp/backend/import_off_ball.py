import pandas as pd
import os
from pathlib import Path
from sqlalchemy import create_engine
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

print(f"Connecting to {DATABASE_URL}")
engine = create_engine(DATABASE_URL)

# CSV lives in H3_Off_Ball_Movement/data/ (two levels up to repo root, then into H3)
csv_path = Path(__file__).resolve().parents[2] / "H3_Off_Ball_Movement" / "data" / "player_urs_aggregated.csv"
print(f"Reading {csv_path}")
df = pd.read_csv(csv_path)

table_name = "player_off_ball"
print(f"Importing to table {table_name}")
df.to_sql(table_name, engine, if_exists="replace", index=False)
print("Done!")
