import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.environ.get("DATABASE_URL")

def update_db():
    if not DATABASE_URL:
        print("Error: DATABASE_URL not found.")
        return

    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        
        # Check if column exists
        cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name='bets_analysis' AND column_name='sport'")
        if cur.fetchone():
            print("Column 'sport' already exists.")
        else:
            print("Adding 'sport' column to bets_analysis...")
            cur.execute("ALTER TABLE bets_analysis ADD COLUMN sport VARCHAR(50) DEFAULT 'Football'")
            conn.commit()
            print("Column added successfully!")
        
        cur.close()
        conn.close()
    except Exception as e:
        print(f"Error updating database: {e}")

if __name__ == "__main__":
    update_db()
