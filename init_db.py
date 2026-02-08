import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.environ.get("DATABASE_URL")

def init_db():
    if not DATABASE_URL:
        print("Error: DATABASE_URL not found.")
        return

    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        
        # Read the SQL file
        with open('sql/create_table.sql', 'r') as f:
            sql_commands = f.read()

        print("Executing SQL commands...")
        cur.execute(sql_commands)
        conn.commit()
        
        print("Table 'bets_analysis' created successfully!")
        
        cur.close()
        conn.close()
    except Exception as e:
        print(f"Error initializing database: {e}")

if __name__ == "__main__":
    init_db()
