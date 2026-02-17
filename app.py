import streamlit as st
import requests
import hashlib

# Chaves padrão da comunidade Solarman
COMMON_APP_ID = "2019102100000001"
COMMON_APP_SECRET = "236c56f91609121c"

st.set_page_config(page_title="Monitor Solar Omnik", page_icon="☀️")

st.title("☀️ Monitor Solar Omnik")

# Barra Lateral
st.sidebar.header("Configuração de Acesso")
user_email = st.sidebar.text_input("E-mail Cadastrado")
user_pass = st.sidebar.text_input("Senha")
station_id = st.sidebar.text_input("ID da Usina (Station ID)")

def get_solarman_token(email, password):
    # A Solarman exige a senha em formato SHA256 (Hex)
    pass_hash = hashlib.sha256(password.encode()).hexdigest()
    
    # URL CORRETA: O endpoint para login via API é '/token'
    url = "https://globalapi.solarmanpv.com/account/v1.0/token"
    
    # A API da Solarman pede o AppId na URL (Query String)
    params = {"appId": COMMON_APP_ID}
    
    # O corpo da mensagem (JSON)
    payload = {
        "appId": COMMON_APP_ID,
        "appSecret": COMMON_APP_SECRET,
        "grantType": "password",  # Indica que vamos usar e-mail/senha
        "email": email,
        "password": pass_hash
    }
    
    try:
        response = requests.post(url, params=params, json=payload, timeout=15)
        res_json = response.json()
        
        # Se o código for 200, deu certo
        if response.status_code == 200 and "access_token" in res_json:
            return res_json["access_token"]
        else:
            # Mostra o erro exato que o servidor retornar agora
            st.error(f"Erro {res_json.get('code')}: {res_json.get('msg') or res_json.get('message')}")
            return None
            
    except Exception as e:
        st.error(f"Falha na conexão: {e}")
        return None

def get_station_data(token, s_id):
    url = "https://globalapi.solarmanpv.com/station/v1.0/realTime"
    params = {"appId": COMMON_APP_ID}
    headers = {"Authorization": f"Bearer {token}"}
    payload = {"stationId": int(s_id)}
    
    try:
        response = requests.post(url, params=params, headers=headers, json=payload)
        return response.json()
    except:
        return None

# Botão de Execução
if st.sidebar.button("📊 Atualizar Dados"):
    if user_email and user_pass and station_id:
        with st.spinner('Conectando à nuvem Solarman...'):
            token = get_solarman_token(user_email, user_pass)
            
            if token:
                data = get_station_data(token, station_id)
                
                if data and data.get("code") == "200" or data.get("success") == True:
                    # Se chegamos aqui, temos os dados reais!
                    potencia = data.get("generationPower", 0)
                    hoje = data.get("dailyGeneration", 0)
                    
                    st.balloons()
                    col1, col2 = st.columns(2)
                    col1.metric("Produção Agora", f"{potencia} W")
                    col2.metric("Total Hoje", f"{hoje} kWh")
                    
                    # Cálculo de economia
                    st.info(f"💰 Economia aproximada hoje: R$ {float(hoje) * 0.95:.2f}")
                else:
                    st.warning("Login ok, mas não encontrei dados da usina. Verifique o ID da Usina.")
    else:
        st.warning("Preencha todos os campos na barra lateral.")
