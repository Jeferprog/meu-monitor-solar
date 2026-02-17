import streamlit as st
import requests
import hashlib

# SEGUNDA TENTATIVA DE CHAVES (Comunidade Solarman)
COMMON_APP_ID = "2020042400000001"
COMMON_APP_SECRET = "60f640960548121c"

st.set_page_config(page_title="Monitor Solar Omnik", page_icon="☀️")

st.title("☀️ Monitor Solar Omnik (Teste AppId 2)")

# Barra Lateral
st.sidebar.header("Login Solarman")
user_email = st.sidebar.text_input("E-mail")
user_pass = st.sidebar.text_input("Senha", type="password")
station_id = st.sidebar.text_input("ID da Usina (Station ID)")

def get_solarman_token(email, password):
    # Criptografia SHA256 da senha
    pass_hash = hashlib.sha256(password.encode()).hexdigest()
    
    # Endpoint oficial para obter o Token
    url = "https://globalapi.solarmanpv.com/account/v1.0/token"
    
    # Parâmetros de URL
    params = {"appId": COMMON_APP_ID}
    
    # Corpo da Requisição
    payload = {
        "appId": COMMON_APP_ID,
        "appSecret": COMMON_APP_SECRET,
        "grantType": "password",
        "email": email,
        "password": pass_hash
    }
    
    try:
        response = requests.post(url, params=params, json=payload, timeout=15)
        res_json = response.json()
        
        if response.status_code == 200 and "access_token" in res_json:
            return res_json["access_token"]
        else:
            # Captura o erro específico para sabermos se este AppId também está bloqueado
            st.error(f"Erro {res_json.get('code')}: {res_json.get('msg')}")
            return None
    except Exception as e:
        st.error(f"Erro de conexão: {e}")
        return None

def get_station_data(token, s_id):
    url = "https://globalapi.solarmanpv.com/station/v1.0/realTime"
    params = {"appId": COMMON_APP_ID}
    headers = {"Authorization": f"Bearer {token}"}
    # O ID da usina deve ser enviado como número
    payload = {"stationId": int(s_id)}
    
    try:
        response = requests.post(url, params=params, headers=headers, json=payload, timeout=15)
        return response.json()
    except Exception as e:
        st.error(f"Erro ao buscar dados: {e}")
        return None

# Execução do Aplicativo
if st.sidebar.button("🚀 Conectar"):
    if user_email and user_pass and station_id:
        with st.spinner('Validando novas chaves...'):
            token = get_solarman_token(user_email, user_pass)
            
            if token:
                data = get_station_data(token, station_id)
                
                if data and (data.get("code") == "200" or data.get("success")):
                    # SUCESSO! Vamos extrair os valores
                    st.balloons()
                    
                    # A estrutura de resposta pode variar, tentamos pegar os nomes comuns
                    potencia = data.get("generationPower", "0")
                    gerado_hoje = data.get("dailyGeneration", "0")
                    status = data.get("stationStatus", "Ativo")

                    st.success(f"Status: {status}")
                    
                    c1, c2 = st.columns(2)
                    c1.metric("Produção Agora", f"{potencia} W")
                    c2.metric("Total Hoje", f"{gerado_hoje} kWh")
                    
                    st.info(f"💰 Economia Estimada Hoje: R$ {float(gerado_hoje) * 0.95:.2f}")
                else:
                    st.warning("Login bem sucedido, mas a usina não retornou dados. Verifique o ID da Usina.")
                    if data: st.write("Resposta do servidor:", data)
    else:
        st.warning("Preencha todos os campos na lateral.")
