import streamlit as st
import requests
import hashlib
import time

# Configurações da Página
st.set_page_config(page_title="Monitor Solar Omnik", page_icon="☀️", layout="wide")

st.title("☀️ Meu Painel Solar (Omnik)")

# Sidebar para Login
st.sidebar.header("Configurações de Acesso")
email = st.sidebar.text_input("E-mail Solarman")
password = st.sidebar.text_input("Senha Solarman", type="password")
app_id = st.sidebar.text_input("App ID (se tiver)")
app_secret = st.sidebar.text_input("App Secret (se tiver)")

def get_token(u, p):
    # Hash da senha para o padrão Solarman
    pass_hash = hashlib.sha256(p.encode()).hexdigest()
    url = "https://globalapi.solarmanpv.com/account/v1.0/login"
    payload = {"appId": app_id, "appSecret": app_secret, "email": u, "password": pass_hash}
    # Nota: Como o portal open não abriu, tentaremos via login direto
    # Se falhar, usaremos uma biblioteca específica.
    return "token_exemplo" 

# Interface do App
if email and password:
    st.info(f"Conectado como: {email}")
    
    # Criando colunas para os medidores
    col1, col2, col3 = st.columns(3)
    
    # Simulando dados (Enquanto ajustamos a conexão final com sua API)
    with col1:
        st.metric(label="Potência Atual", value="1.540 W", delta="210 W")
    with col2:
        st.metric(label="Gerado Hoje", value="12.4 kWh")
    with col3:
        st.metric(label="Economia Estimada", value="R$ 11,16")

    # Gráfico de exemplo
    st.subheader("Histórico de Produção")
    st.area_chart([100, 400, 1200, 2500, 3000, 2800, 1500, 200])
else:
    st.warning("Por favor, preencha seu e-mail e senha na barra lateral.")
