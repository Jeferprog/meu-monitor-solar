import streamlit as st
import omnik
import time

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
    col_btn, col_auto, col_ip = st.columns([1, 1, 2])
    with col_btn:
        conectar = st.button("⚡ Ler dados agora", type="primary", use_container_width=True)
    with col_auto:
        auto = st.toggle("Auto (30s)", value=False)
    with col_ip:
        st.caption(f"Conectando em `{inverter_ip}`")

    if auto and 'last_update' not in st.session_state:
        conectar = True
    elif auto and time.time() - st.session_state.get('last_update', 0) >= 30:
        conectar = True

    if conectar:
        with st.spinner("Conectando ao inversor..."):
            dados = None

            # Tenta interface HTTP primeiro
            http_dados = omnik.read_via_http(inverter_ip)
            if http_dados and len([k for k in http_dados if not k.startswith('_')]) > 0:
                dados = http_dados
                st.session_state['metodo'] = 'HTTP'
            else:
                # Fallback: protocolo binário TCP porta 8899
                if http_dados:
                    with st.expander("🌐 Conteúdo bruto da interface web (diagnóstico)"):
                        st.code(http_dados.get('_raw_html', '')[:3000], language='html')
                try:
                    raw = omnik.read_inverter(inverter_ip, serial_no)
                    dados = omnik.parse_response(raw)
                    st.session_state['metodo'] = 'TCP:8899'
                except ConnectionRefusedError:
                    st.error("Conexão recusada na porta 8899. Verifique se o IP está correto.")
                    st.stop()
                except TimeoutError:
                    st.error("Tempo esgotado. O inversor não respondeu.")
                    st.stop()
                except ValueError as e:
                    st.warning(str(e))
                    st.stop()
                except Exception as e:
                    st.error(f"Erro inesperado: {e}")
                    st.stop()

            if dados:
                st.session_state['dados'] = dados
                st.session_state['last_update'] = time.time()

    if auto:
        time.sleep(30)
        st.rerun()

# ─── Exibição dos dados ───────────────────────────────────────────────────────

if 'dados' in st.session_state:
    d = st.session_state['dados']
    metodo = st.session_state.get('metodo', '?')
    st.caption(f"Fonte: `{metodo}` | IP: `{inverter_ip}`")

    st.divider()
    st.subheader("Produção atual")

    gerando = d.get('ac_potencia', 0) > 0
    status_txt = "🟢 Gerando energia" if gerando else "🔴 Sem geração (sem sol)"
    st.info(f"**Status:** {status_txt} | **Modelo:** {d.get('modelo', '—')} | **Nominal:** {d.get('potencia_nominal', 0)} W")

    c1, c2, c3 = st.columns(3)
    c1.metric("⚡ Potência agora", f"{d.get('ac_potencia', 0)} W")
    c2.metric("📅 Energia hoje", f"{d.get('energia_hoje', 0):.2f} kWh")
    c3.metric("📊 Total acumulado", f"{d.get('energia_total', 0):.1f} kWh")

    energia_hoje = d.get('energia_hoje', 0)
    if energia_hoje > 0:
        economia = energia_hoje * 0.95
        st.success(f"💰 Economia estimada hoje: **R$ {economia:.2f}**")

    temp = d.get('temperatura', 0)
    if temp and temp > 0:
        st.caption(f"🌡️ Temperatura do inversor: {temp} °C")

    if 'ac_tensao' in d or 'pv1_tensao' in d:
        st.divider()
        st.subheader("Painéis (CC)")
        p1, p2 = st.columns(2)
        p1.metric("String 1 — Tensão", f"{d.get('pv1_tensao', '—')} V")
        p1.metric("String 1 — Corrente", f"{d.get('pv1_corrente', '—')} A")
        p2.metric("String 2 — Tensão", f"{d.get('pv2_tensao', '—')} V")
        p2.metric("String 2 — Corrente", f"{d.get('pv2_corrente', '—')} A")

        st.divider()
        st.subheader("Rede elétrica (CA)")
        a1, a2 = st.columns(2)
        a1.metric("Tensão AC", f"{d.get('ac_tensao', '—')} V")
        a2.metric("Frequência", f"{d.get('ac_frequencia', '—')} Hz")

    with st.expander("🔧 Campos brutos do inversor"):
        campos = d.get('_campos_brutos', [])
        if campos:
            for i, v in enumerate(campos):
                st.text(f"[{i}] = {v!r}")
        elif '_raw_hex' in d:
            st.code(d['_raw_hex'][:3000], language='text')
        elif '_raw_html' in d:
            st.code(d['_raw_html'][:3000], language='html')
