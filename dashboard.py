import streamlit as st
import pandas as pd
import psycopg2
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Page Config
st.set_page_config(page_title="Betting AI Dashboard", page_icon="⚽", layout="wide")

# Data Fetching
@st.cache_data(ttl=600) # Cache data for 10 min
def get_data():
    url = os.environ.get("DATABASE_URL")
    conn = psycopg2.connect(url)
    
    query = """
    SELECT 
        match_name, 
        match_time,
        league, 
        sport, 
        main_prediction, 
        secondary_prediction, 
        confidence_level, 
        odds_value, 
        ai_justification,
        created_at
    FROM bets_analysis
    WHERE created_at::date = CURRENT_DATE
    ORDER BY confidence_level DESC
    """
    df = pd.read_sql(query, conn)
    conn.close()
    return df

# Sidebar Filters
st.sidebar.header("Filtros")
sport_filter = st.sidebar.multiselect("Esporte", ["Football", "Basketball"], default=["Football", "Basketball"])
min_confidence = st.sidebar.slider("Confiança Mínima (%)", 0, 100, 70)

# Main Content
st.title("🤖 Betting AI - Oportunidades do Dia")
st.markdown("Apostas identificadas pela Inteligência Artificial para hoje.")

try:
    df = get_data()
    
    if df.empty:
        st.warning("Nenhuma aposta encontrada para hoje. Rode o script de análise primeiro.")
    else:
        # Apply Filters
        filtered_df = df[
            (df['sport'].isin(sport_filter)) & 
            (df['confidence_level'] >= min_confidence)
        ]
        
        # Metrics
        col1, col2, col3 = st.columns(3)
        col1.metric("Total de Oportunidades", len(filtered_df))
        if not filtered_df.empty:
            avg_conf = filtered_df['confidence_level'].mean()
            col2.metric("Confiança Média", f"{avg_conf:.1f}%")
            avg_odd = filtered_df['odds_value'].mean()
            col3.metric("Odd Média", f"{avg_odd:.2f}")

        st.subheader("📋 Lista de Apostas")
        
        # Display Cards or Table
        for index, row in filtered_df.iterrows():
            with st.expander(f"🕒 {row['match_time']} | {row['sport']} | {row['match_name']} - {row['main_prediction']} ({row['confidence_level']}%)"):
                c1, c2 = st.columns(2)
                c1.markdown(f"**Horário:** {row['match_time']}")
                c1.markdown(f"**Liga:** {row['league']}")
                c1.markdown(f"**Odd:** {row['odds_value']}")
                c1.markdown(f"**Aposta Secundária:** {row['secondary_prediction']}")
                
                c2.info(f"**Justificativa AI:** {row['ai_justification']}")

except Exception as e:
    st.error(f"Erro ao carregar dados: {e}")
