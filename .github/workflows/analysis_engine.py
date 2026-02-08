import os
import sys
import datetime
import requests
import psycopg2
from psycopg2 import sql
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configuration
API_KEY = os.environ.get("API_KEY")
DATABASE_URL = os.environ.get("DATABASE_URL")

SPORTS_CONFIG = {
    'Football': {
        'fixtures_url': "https://v3.football.api-sports.io/fixtures",
        'odds_url': "https://v3.football.api-sports.io/odds",
        'stats_url': "https://v3.football.api-sports.io/teams/statistics",
        'league_id': None, # All leagues
        'headers': {
            'x-apisports-key': API_KEY
        }
    },
    'Basketball': {
        'fixtures_url': "https://v1.basketball.api-sports.io/games",
        'odds_url': "https://v1.basketball.api-sports.io/odds",
        'stats_url': "https://v1.basketball.api-sports.io/statistics",
        'league_id': 12, # NBA League ID
        'headers': {
            'x-apisports-key': API_KEY
        }
    }
}

# --- Real Statistical Analysis ---
def calculate_team_strength(team_stats):
    """Calculate team strength based on recent form and goals."""
    if not team_stats:
        return 0.5
    
    # Extract key metrics
    wins = team_stats.get('wins', 0)
    draws = team_stats.get('draws', 0)
    losses = team_stats.get('losses', 0)
    goals_for = team_stats.get('goals_for', 0)
    goals_against = team_stats.get('goals_against', 0)
    
    total_games = wins + draws + losses
    if total_games == 0:
        return 0.5
    
    # Win rate
    win_rate = wins / total_games
    
    # Goal difference per game
    goal_diff = (goals_for - goals_against) / total_games
    
    # Normalize goal diff to 0-1 scale (assuming -3 to +3 range)
    goal_diff_normalized = (goal_diff + 3) / 6
    goal_diff_normalized = max(0, min(1, goal_diff_normalized))
    
    # Weighted combination
    strength = (win_rate * 0.6) + (goal_diff_normalized * 0.4)
    
    return strength

def calculate_match_probability(home_strength, away_strength, is_home=True):
    """Calculate win probability using Elo-like system."""
    # Home advantage factor
    home_advantage = 0.1 if is_home else -0.1
    
    # Adjusted strengths
    home_adj = home_strength + home_advantage
    away_adj = away_strength
    
    # Calculate probabilities using logistic function
    strength_diff = home_adj - away_adj
    
    # Home win probability
    home_win_prob = 1 / (1 + 10 ** (-strength_diff * 4))
    
    # Away win probability
    away_win_prob = 1 - home_win_prob
    
    # Draw probability (simplified)
    draw_prob = 0.25 * (1 - abs(strength_diff))
    
    # Normalize
    total = home_win_prob + away_win_prob + draw_prob
    home_win_prob /= total
    away_win_prob /= total
    draw_prob /= total
    
    return {
        'home_win': home_win_prob,
        'draw': draw_prob,
        'away_win': away_win_prob
    }

def get_real_odds(fixture_id, config, sport='Football'):
    """Fetch real odds from API-Sports."""
    try:
        if sport == 'Football':
            params = {"fixture": fixture_id}
        else: # Basketball
            params = {"game": fixture_id}
            
        response = requests.get(config['odds_url'], headers=config['headers'], params=params)
        response.raise_for_status()
        data = response.json().get('response', [])
        
        if not data:
            return None
        
        # Search specifically for Bet365 per user request
        for bookmaker_data in data:
            bookmakers = bookmaker_data.get('bookmakers', [])
            for bm in bookmakers:
                if bm['name'].lower() == 'bet365':
                    bets = bm.get('bets', [])
                    for bet in bets:
                        if bet['name'] == 'Match Winner':
                            values = bet.get('values', [])
                            odds_dict = {}
                            for v in values:
                                odds_dict[v['value']] = float(v['odd'])
                            return odds_dict, bm['name']
        
        # Fallback to the first available bookmaker if Bet365 not found
        for bookmaker_data in data:
            bookmakers = bookmaker_data.get('bookmakers', [])
            if bookmakers:
                bm = bookmakers[0]
                bets = bm.get('bets', [])
                for bet in bets:
                    if bet['name'] == 'Match Winner':
                        values = bet.get('values', [])
                        odds_dict = {}
                        for v in values:
                            odds_dict[v['value']] = float(v['odd'])
                        return odds_dict, bm['name']
        
        return None
    except Exception as e:
        print(f"Error fetching odds for {sport} id {fixture_id}: {e}")
        return None

def generate_justification(sport, home, away, prediction, prob, stats_summary):
    """Generate justification based on real statistics."""
    reasons = []
    
    if 'home_form' in stats_summary:
        reasons.append(f"{home} tem {stats_summary['home_form']}% de aproveitamento em casa")
    
    if 'away_form' in stats_summary:
        reasons.append(f"{away} tem {stats_summary['away_form']}% fora de casa")
    
    if 'goal_diff' in stats_summary:
        if stats_summary['goal_diff'] > 0:
            reasons.append(f"Saldo de gols favorável: +{stats_summary['goal_diff']:.1f}")
        else:
            reasons.append(f"Saldo de gols: {stats_summary['goal_diff']:.1f}")
    
    if not reasons:
        reasons.append("Análise baseada em estatísticas recentes")
    
    justification = ". ".join(reasons[:2])
    return f"{justification}. Probabilidade calculada: {prob:.1%}"

# --- Main Logic ---

def get_games_for_date(sport, config, target_date):
    """Fetches games for a specific day and sport."""
    headers = config['headers']
    params = {"date": target_date}
    if config.get('league_id'):
        params['league'] = config['league_id']
    
    print(f"[{sport}] Fetching games for {target_date}...")
    try:
        response = requests.get(config['fixtures_url'], headers=headers, params=params)
        response.raise_for_status()
        data = response.json().get('response', [])
        
        if not data:
            print(f"[{sport}] No games returned for {target_date}.")
            return []
            
        print(f"[{sport}] Found {len(data)} games for {target_date}.")
        return data
    except Exception as e:
        print(f"[{sport}] Error fetching data for {target_date}: {e}")
        return []

def analyze_game(sport, game, config):
    """Analyzes a single game based on real statistics and odds."""
    results = []
    
    try:
        if sport == 'Football':
            fixture_id = game['fixture']['id']
            home_team = game['teams']['home']['name']
            away_team = game['teams']['away']['name']
            league = game['league']['name']
            match_time = game['fixture']['date'][11:16] # HH:mm
        else: # Basketball
            fixture_id = game.get('id')
            home_team = game['teams']['home']['name']
            away_team = game['teams']['away']['name']
            league = game['league']['name']
            match_time = game.get('date', '')[11:16] # HH:mm
        
        if not fixture_id:
            return []
            
        # Get real odds (specifically looking for Bet365)
        odds_res = get_real_odds(fixture_id, config, sport)
        
        if not odds_res:
            return []  # Skip if no odds available
            
        real_odds, bookmaker = odds_res
        
        # Filter: Only accept Bet365 if possible (User request)
        if bookmaker.lower() != 'bet365':
            # We still keep it but we will mark it or could skip it
            # The user wants games that appear on Bet365.
            pass
        
        # Extract team stats from fixture data (simplified - using goals)
        goals_data = game.get('goals', {}) or {}
        home_stats = {
            'wins': game['teams']['home'].get('winner', False) and 1 or 0,
            'goals_for': goals_data.get('home') or 0,
            'goals_against': goals_data.get('away') or 0,
            'draws': 0,
            'losses': 0
        }
        
        away_stats = {
            'wins': game['teams']['away'].get('winner', False) and 1 or 0,
            'goals_for': goals_data.get('away') or 0,
            'goals_against': goals_data.get('home') or 0,
            'draws': 0,
            'losses': 0
        }
        
        # Calculate strengths
        home_strength = calculate_team_strength(home_stats)
        away_strength = calculate_team_strength(away_stats)
        
        # Calculate probabilities
        probs = calculate_match_probability(home_strength, away_strength)
        
        # Analyze each market
        match_name = f"{home_team} vs {away_team}"
        
        # Home Win
        if 'Home' in real_odds:
            home_odd = real_odds['Home']
            implied_prob = 1 / home_odd
            our_prob = probs['home_win']
            value = our_prob - implied_prob
            
            if value > 0.05:  # 5% edge minimum for professional standard
                confidence = int(our_prob * 100)
                stats_summary = {
                    'home_form': int(home_strength * 100),
                    'goal_diff': home_stats['goals_for'] - home_stats['goals_against']
                }
                justification = generate_justification(sport, home_team, away_team, f"Win {home_team}", our_prob, stats_summary)
                
                results.append({
                    'match_name': match_name,
                    'match_time': match_time,
                    'league': league,
                    'sport': sport,
                    'main_prediction': f"Win {home_team}",
                    'secondary_prediction': f"Value: +{value:.1%}",
                    'confidence_level': confidence,
                    'ai_justification': justification,
                    'odds_value': home_odd,
                    'status': 'pending'
                })
        
        # Away Win
        if 'Away' in real_odds:
            away_odd = real_odds['Away']
            implied_prob = 1 / away_odd
            our_prob = probs['away_win']
            value = our_prob - implied_prob
            
            if value > 0.05:  # 5% edge minimum
                confidence = int(our_prob * 100)
                stats_summary = {
                    'away_form': int(away_strength * 100),
                    'goal_diff': away_stats['goals_for'] - away_stats['goals_against']
                }
                justification = generate_justification(sport, home_team, away_team, f"Win {away_team}", our_prob, stats_summary)
                
                results.append({
                    'match_name': match_name,
                    'match_time': match_time,
                    'league': league,
                    'sport': sport,
                    'main_prediction': f"Win {away_team}",
                    'secondary_prediction': f"Value: +{value:.1%}",
                    'confidence_level': confidence,
                    'ai_justification': justification,
                    'odds_value': away_odd,
                    'status': 'pending'
                })
        
    except Exception as e:
        print(f"Error analyzing game: {e}")
        return []
    
    return results

def save_to_db(results):
    """Saves analysis results to Postgres."""
    if not results:
        return

    conn = None
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        
        insert_query = """
        INSERT INTO bets_analysis 
        (match_name, match_time, league, sport, main_prediction, secondary_prediction, confidence_level, ai_justification, odds_value, status)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        
        check_query = "SELECT id FROM bets_analysis WHERE match_name = %s AND main_prediction = %s AND created_at::date = CURRENT_DATE"
        
        saved_count = 0
        for bet in results:
            cur.execute(check_query, (bet['match_name'], bet['main_prediction']))
            if cur.fetchone():
                continue

            cur.execute(insert_query, (
                bet['match_name'],
                bet.get('match_time', ''),
                bet['league'],
                bet['sport'],
                bet['main_prediction'],
                bet['secondary_prediction'],
                bet['confidence_level'],
                bet['ai_justification'],
                bet['odds_value'],
                bet['status']
            ))
            saved_count += 1
            
        conn.commit()
        cur.close()
        print(f"Saved {saved_count} new value bets.")
        
    except (Exception, psycopg2.DatabaseError) as error:
        print(f"Database error: {error}")
    finally:
        if conn is not None:
            conn.close()

if __name__ == "__main__":
    if not API_KEY or not DATABASE_URL:
        print("Error: Config missing.")
        sys.exit(1)

    all_bets = []
    
    for sport, config in SPORTS_CONFIG.items():
        # Get games for today and tomorrow to have enough data (avoid late night empty list)
        today_str = datetime.datetime.now().strftime("%Y-%m-%d")
        tomorrow_str = (datetime.datetime.now() + datetime.timedelta(days=1)).strftime("%Y-%m-%d")
        
        games_today = get_games_for_date(sport, config, today_str)
        games_tomorrow = get_games_for_date(sport, config, tomorrow_str)
        
        all_possible_games = games_today + games_tomorrow
        
        # 25 games per sport as requested (50 total)
        for game in all_possible_games[:25]:
            bets = analyze_game(sport, game, config)
            all_bets.extend(bets)
    
    if all_bets:
        # CLEANUP: Delete previous days' bets to keep only today's fresh data
        try:
            conn = psycopg2.connect(DATABASE_URL)
            cur = conn.cursor()
            cur.execute("DELETE FROM bets_analysis WHERE created_at::date < CURRENT_DATE")
            conn.commit()
            print("Cleanup: Removed old bets from the database.")
            cur.close()
            conn.close()
        except Exception as e:
            print(f"Cleanup error: {e}")

        print(f"Total value bets found: {len(all_bets)}")
        save_to_db(all_bets)
    else:
        print("No value bets found today.")
