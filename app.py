import streamlit as st
import omnik

# ─── Config ──────────────────────────────────────────────────────────────────

DEFAULT_SN = 645450063  # WiFi SN: 0645450063

st.set_page_config(page_title="Monitor Solar Omnik", page_icon="☀️", layout="centered")

st.title("☀️ Monitor Solar — Omniksol-3k-TL2")

# ─── Sidebar ─────────────────────────────────────────────────────────────────

st.sidebar.header("Configuração")

serial_input = st.sidebar.text_input("Número de Série WiFi", value=str(DEFAULT_SN))
try:
    serial_no = int(serial_input)
except ValueError:
    st.sidebar.error("SN inválido — use apenas números.")
    st.stop()

ip_mode = st.sidebar.radio("IP do inversor", ["Descobrir automaticamente", "Inserir manualmente"])

inverter_ip = None

if ip_mode == "Inserir manualmente":
    inverter_ip = st.sidebar.text_input("IP do inversor", placeholder="ex: 192.168.1.100")
    if not inverter_ip:
        st.info("Informe o IP do inversor na barra lateral ou use a descoberta automática.")

# ─── Descoberta automática ────────────────────────────────────────────────────

if ip_mode == "Descobrir automaticamente":
    all_ips = omnik.get_all_local_ips()
    subnets = list(dict.fromkeys(ip.rsplit('.', 1)[0] + '.0/24' for ip in all_ips))

    subnet_escolhida = st.sidebar.selectbox(
        "Interface de rede",
        options=subnets,
        help="Escolha a subnet do Wi-Fi onde o inversor está conectado."
    )

    if st.sidebar.button("🔍 Buscar inversor na rede"):
        subnet = subnet_escolhida
        st.info(f"Escaneando subnet **{subnet}** — aguarde...")

        with st.spinner("Procurando inversor..."):
            found = omnik.scan_subnet(subnet)

        if found:
            ip, porta = found[0]
            st.success(f"Inversor encontrado: **{ip}** (porta {porta})")
            st.session_state['inverter_ip'] = ip
            st.session_state['inverter_port'] = porta
        else:
            st.error(
                "Nenhum dispositivo encontrado na porta 8899. "
                "Verifique se o inversor está ligado e na mesma rede Wi-Fi."
            )

    if 'inverter_ip' in st.session_state:
        inverter_ip = st.session_state['inverter_ip']
        st.sidebar.success(f"IP: {inverter_ip} | Porta: {st.session_state.get('inverter_port', omnik.OMNIK_PORT)}")

# ─── Leitura dos dados ────────────────────────────────────────────────────────

if inverter_ip:
    col_btn, col_ip = st.columns([1, 2])
    with col_btn:
        conectar = st.button("⚡ Ler dados agora", type="primary", use_container_width=True)
    with col_ip:
        st.caption(f"Conectando em `{inverter_ip}:{omnik.OMNIK_PORT}`")

    if conectar:
        with st.spinner("Conectando ao inversor..."):
            try:
                raw = omnik.read_inverter(inverter_ip, serial_no)
                dados = omnik.parse_response(raw)
                st.session_state['dados'] = dados
                st.session_state['raw'] = raw
            except ConnectionRefusedError:
                st.error("Conexão recusada. Verifique se o IP está correto e o inversor está ligado.")
                st.stop()
            except TimeoutError:
                st.error("Tempo esgotado. O inversor não respondeu.")
                st.stop()
            except ValueError as e:
                st.warning(str(e))
                if 'raw' in st.session_state:
                    with st.expander("📦 Dados brutos recebidos"):
                        st.code(st.session_state['raw'].hex(' '), language='text')
                st.stop()
            except Exception as e:
                st.error(f"Erro inesperado: {e}")
                st.stop()

# ─── Exibição dos dados ───────────────────────────────────────────────────────

if 'dados' in st.session_state:
    d = st.session_state['dados']

    st.divider()
    st.subheader("Produção atual")

    c1, c2, c3 = st.columns(3)
    c1.metric("⚡ Potência AC", f"{d['ac_potencia']} W")
    c2.metric("📅 Energia Hoje", f"{d['energia_hoje']} kWh")
    c3.metric("📊 Energia Total", f"{d['energia_total']} kWh")

    economia = d['energia_hoje'] * 0.95
    st.success(f"💰 Economia estimada hoje: **R$ {economia:.2f}**")

    st.divider()
    st.subheader("Painéis (CC)")

    p1, p2 = st.columns(2)
    p1.metric("String 1 — Tensão", f"{d['pv1_tensao']} V")
    p1.metric("String 1 — Corrente", f"{d['pv1_corrente']} A")
    p2.metric("String 2 — Tensão", f"{d['pv2_tensao']} V")
    p2.metric("String 2 — Corrente", f"{d['pv2_corrente']} A")

    st.divider()
    st.subheader("Rede elétrica (CA)")

    a1, a2, a3 = st.columns(3)
    a1.metric("Tensão AC", f"{d['ac_tensao']} V")
    a2.metric("Frequência", f"{d['ac_frequencia']} Hz")
    a3.metric("Temperatura", f"{d['temperatura']} °C")

    st.divider()
    st.metric("⏱ Horas de operação total", f"{d['horas_total']} h")

    with st.expander("🔧 Dados brutos (diagnóstico)"):
        st.caption(f"Tamanho da resposta: {d['_raw_len']} bytes")
        st.code(d['_raw_hex'], language='text')
