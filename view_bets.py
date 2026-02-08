import os
import psycopg2
from dotenv import load_dotenv
from prettytable import PrettyTable

load_dotenv()

DATABASE_URL = os.environ.get("DATABASE_URL")

def view_bets():
    """Displays today's betting opportunities from the database."""
    if not DATABASE_URL:
        print("Error: DATABASE_URL not found.")
        return

    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        
        # Fetch bets created today
        query = """
        SELECT sport, match_name, main_prediction, odds_value, confidence_level, ai_justification
        FROM bets_analysis
        WHERE created_at::date = CURRENT_DATE
        ORDER BY confidence_level DESC, sport
        LIMIT 20
        """
        
        cur.execute(query)
        rows = cur.fetchall()
        
        if not rows:
            print("Nenhuma aposta encontrada no banco ainda.")
            return

        t = PrettyTable(['Esporte', 'Jogo', 'Palpite', 'Odd', 'Confiança', 'Justificativa'])
        t.encoding = 'utf-8'
        
        print(f"\n--- TOP 20 APOSTAS DO DIA ---\n")
        
        for row in rows:
            sport, match, pred, odd, conf, just = row
            # Truncate justification for display
            just_short = (just[:30] + '..') if len(just) > 30 else just
            t.add_row([sport, match, pred, odd, f"{conf}%", just_short])

        print(t)
        
        cur.close()
        conn.close()
    except Exception as e:
        print(f"Error fetching bets: {e}")

if __name__ == "__main__":
    view_bets()
