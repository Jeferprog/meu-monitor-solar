import streamlit as st
import requests
import hashlib

# Chaves padrão da comunidade
COMMON_APP_ID = "2019102100000001"
COMMON_APP_SECRET = "236c56f91609121c"

st.set_page_config(page_title="Monitor Solar Omnik", page_icon="☀️")

st.title("☀️ Monitor Solar (Debug Mode)")

# Barra Lateral
st.sidebar.header("Login Solarman")
user_email = st.sidebar.text_input("E-mail")
user_pass = st.sidebar.text_input("Senha", type="password")
station_id = st.sidebar.text_input("ID da Usina")

def get_solarman_token(email, password):
    # Criptografia da senha
    pass_hash = hashlib.sha256(password.encode()).hexdigest()
    
    # URL da API Global
    url = "https://globalapi.solarmanpv.com/account/v1.0/login"
    
    # Parâmetros exatos que a API espera
    params = {
        "appId": COMMON_APP_ID
    }
    
    payload = {
        "appId": COMMON_APP_ID,
        "appSecret": COMMON_APP_SECRET,
        "email": email,
        "password": pass_hash
    }
    
    try:
        response = requests.post(url, params=params, json=payload, timeout=15)
        res_json = response.json()
        
        # Mostra o que o servidor respondeu caso dê erro
        if response.status_code != 200 or "access_token" not in res_json:
            st.error(f"Erro do Servidor: {res_json.get('msg', 'Erro desconhecido')}")
            st.write("Resposta completa do servidor:", res_json)
            return None
            
        return res_json.get("access_token")
    except Exception as e:
        st.error(f"Erro de conexão: {e}")
        return None

if st.sidebar.button("Tentar Conexão"):
    if user_email and user_pass:
        with st.spinner('Tentando logar na Solarman...'):
            token = get_solarman_token(user_email, user_pass)
            if token:
                st.success("Login realizado com sucesso!")
                st.session_state['token'] = token
                st.info("Agora podemos buscar os dados da usina.")
    else:
        st.warning("Preencha e-mail e senha.")

# Se já temos o token, mostra os dados
if 'token' in st.session_state and station_id:
    # (O código de busca de dados continua aqui abaixo...)
    st.write(f"Token ativo: {st.session_state['token'][:10]}...")
