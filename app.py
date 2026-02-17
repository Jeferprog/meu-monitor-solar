import streamlit as st
import requests
import hashlib
import time
import pandas as pd

# Configurações de acesso (Chaves da comunidade que geralmente funcionam)
COMMON_APP_ID = "2019102100000001"
COMMON_APP_SECRET = "236c56f91609121c"

st.set_page_config(page_title="Meu Monitor Solar", page_icon="☀️")

st.title("☀️ Monitor Solar Omnik")

# Barra Lateral
st.sidebar.header("Login Solarman")
user_email = st.sidebar.text_input("E-mail")
user_pass = st.sidebar.text_input("Senha", type="password")
station_id = st.sidebar.text_input("ID da Usina (Station ID)")

def get_solarman_token(email, password):
    # Criptografa a senha em SHA256
    pass_hash = hashlib.sha256(password.encode()).hexdigest()
    url = "https://globalapi.solarmanpv.com/account/v1.0/login?appId=" + COMMON_APP_ID
    payload = {
        "appId": COMMON_APP_ID,
        "appSecret": COMMON_APP_SECRET,
        "email": email,
        "password": pass_hash
    }
    try:
        response = requests.post(url, json=payload, timeout=10)
        return response.json().get("access_token")
    except:
        return None

def get_realtime_data(token, s_id):
    url = f"https://globalapi.solarmanpv.com/station/v1.0/realTime?stationId={s_id}"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        response = requests.post(url, headers=headers, timeout=10)
        return response.json()
    except:
        return None

if st.sidebar.button("Conectar e Atualizar"):
    if user_email and user_pass and station_id:
        token = get_solarman_token(user_email, user_pass)
        
        if token:
            data = get_realtime_data(token, station_id)
            
            if data:
                # Extraindo os dados reais
                # Nota: Os nomes dos campos podem variar levely dependendo da versão da API
                potencia = data.get("generationPower", 0)
                gerado_hoje = data.get("dailyGeneration", 0)
                status = data.get("stationStatus", "Desconhecido")
                
                # Exibição no App
                st.success(f"Conectado! Status da Usina: {status}")
                
                c1, c2, c3 = st.columns(3)
                c1.metric("Potência Agora", f"{potencia} W")
                c2.metric("Gerado Hoje", f"{gerado_hoje} kWh")
                c3.metric("Economia Estimada", f"R$ {float(gerado_hoje) * 0.90:.2f}") # Ajuste o valor do kWh aqui
                
                # Criando um gráfico fake enquanto não puxamos o histórico
                st.subheader("Curva de Produção Estimada")
                dados_grafico = [0, 0, 100, 500, 1200, potencia, potencia*0.8, 200, 0]
                st.area_chart(dados_grafico)
                
            else:
                st.error("Não foi possível ler os dados da usina. Verifique o ID.")
        else:
            st.error("Falha no login. Verifique e-mail e senha.")
    else:
        st.warning("Preencha todos os campos na barra lateral.")
else:
    st.info("Aguardando conexão... Insira seus dados ao lado e clique em Atualizar.")
