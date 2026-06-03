import streamlit as st
import pandas as pd
import datetime
import omnik
import solarman
import time

# ─── Config ──────────────────────────────────────────────────────────────────

DEFAULT_SN = 645450063

SOLARMAN_EMAIL = "liaejefer@hotmail.com"
SOLARMAN_PASSWORD = "Je08mwd2501L@"

st.set_page_config(page_title="Monitor Solar — Residência Deimling", page_icon="☀️", layout="centered")
st.title("☀️ Monitor Solar — Residência Deimling")

# ─── Sidebar ─────────────────────────────────────────────────────────────────

st.sidebar.header("Configuração")
fonte = st.sidebar.radio("Fonte de dados", ["☁️ Solarman (nuvem)", "🏠 Inversor local (TCP)"])


# ─── Helpers Solarman ─────────────────────────────────────────────────────────

def _coletar(token, escolha):
    """Retorna (dados_atuais, metodo) para a escolha de dispositivo."""
    if escolha.startswith("🔆"):
        lista = [solarman.parse_realtime(solarman.get_realtime_data(token, sn))
                 for sn in solarman.DEVICES.values()]
        return solarman.combinar(lista), "Usina (somada)"
    sn = solarman.DEVICES[escolha]
    return solarman.parse_realtime(solarman.get_realtime_data(token, sn)), escolha


def _sns_da_escolha(escolha):
    if escolha.startswith("🔆"):
        return list(solarman.DEVICES.values())
    return [solarman.DEVICES[escolha]]


def _coletar_historico(token, escolha):
    """Busca curva do dia, histórico diário (mês) e mensal (ano)."""
    hoje = datetime.date.today()
    ini_mes = hoje.replace(day=1)
    ini_ano = hoje.replace(month=1, day=1)
    sns = _sns_da_escolha(escolha)

    curvas, diarios, mensais = [], [], []
    diag = {}
    for sn in sns:
        try:
            r = solarman.get_historical(token, sn, str(hoje), str(hoje), solarman.TIME_DAY)
            curvas.append(solarman.parse_curva_potencia(r))
            diag[f"dia_{sn}"] = r
        except Exception as e:
            diag[f"dia_{sn}_erro"] = str(e)
        try:
            r = solarman.get_historical(token, sn, str(ini_mes), str(hoje), solarman.TIME_MONTH)
            diarios.append(solarman.parse_historico_energia(r, "%d/%m"))
            diag[f"mes_{sn}"] = r
        except Exception as e:
            diag[f"mes_{sn}_erro"] = str(e)
        try:
            r = solarman.get_historical(token, sn, str(ini_ano), str(hoje), solarman.TIME_YEAR)
            mensais.append(solarman.parse_historico_energia(r, "%m/%Y"))
            diag[f"ano_{sn}"] = r
        except Exception as e:
            diag[f"ano_{sn}_erro"] = str(e)

    return {
        "curva":   solarman.combinar_series(curvas),
        "diario":  solarman.combinar_series(diarios),
        "mensal":  solarman.combinar_series(mensais),
        "_diag":   diag,
    }


# ─── Modo Solarman ────────────────────────────────────────────────────────────

if fonte == "☁️ Solarman (nuvem)":
    opcoes = ["🔆 Usina (somar os dois)"] + list(solarman.DEVICES.keys())
    if 'device_choice' not in st.session_state:
        st.session_state['device_choice'] = opcoes[0]

    # Botões de seleção de dispositivo abaixo do título
    cols = st.columns(len(opcoes))
    rotulos_curtos = ["🔆 Usina", "Inversor", "Micro-inversor"]
    for col, opc, rot in zip(cols, opcoes, rotulos_curtos):
        tipo = "primary" if st.session_state['device_choice'] == opc else "secondary"
        if col.button(rot, use_container_width=True, type=tipo, key=f"btn_{opc}"):
            st.session_state['device_choice'] = opc
            st.session_state['trigger_fetch'] = True   # busca automática ao trocar
            st.rerun()

    escolha = st.session_state['device_choice']

    col_btn, col_auto = st.columns([1, 1])
    with col_btn:
        conectar = st.button("⚡ Ler dados agora", type="primary", use_container_width=True)
    with col_auto:
        auto = st.toggle("Auto (60s)", value=False)

    # Dispara busca ao trocar de inversor (botões) ou no auto-refresh
    if st.session_state.pop('trigger_fetch', False):
        conectar = True
    if auto and 'last_update' not in st.session_state:
        conectar = True
    elif auto and time.time() - st.session_state.get('last_update', 0) >= 60:
        conectar = True

    if conectar:
        with st.spinner("Conectando à API Solarman..."):
            try:
                token = solarman.get_token(SOLARMAN_EMAIL, SOLARMAN_PASSWORD)
                dados, sufixo = _coletar(token, escolha)
                st.session_state['dados'] = dados
                st.session_state['metodo'] = f"Solarman API — {sufixo}"
                st.session_state['last_update'] = time.time()
                st.session_state['historico'] = _coletar_historico(token, escolha)
            except Exception as e:
                st.error(f"Erro ao consultar Solarman: {e}")
                st.stop()

    if auto:
        time.sleep(60)
        st.rerun()

# ─── Modo local (TCP) ─────────────────────────────────────────────────────────

else:
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

    if ip_mode == "Descobrir automaticamente":
        all_ips = omnik.get_all_local_ips()
        subnets = list(dict.fromkeys(ip.rsplit('.', 1)[0] + '.0/24' for ip in all_ips))

        subnet_escolhida = st.sidebar.selectbox(
            "Interface de rede",
            options=subnets,
            help="Escolha a subnet do Wi-Fi onde o inversor está conectado."
        )

        if st.sidebar.button("🔍 Buscar inversor na rede"):
            st.info(f"Escaneando subnet **{subnet_escolhida}** — aguarde...")
            with st.spinner("Procurando inversor..."):
                found = omnik.scan_subnet(subnet_escolhida)
            if found:
                ip, porta = found[0]
                st.success(f"Inversor encontrado: **{ip}** (porta {porta})")
                st.session_state['inverter_ip'] = ip
                st.session_state['inverter_port'] = porta
            else:
                st.error("Nenhum dispositivo encontrado na porta 8899.")

        if 'inverter_ip' in st.session_state:
            inverter_ip = st.session_state['inverter_ip']
            st.sidebar.success(f"IP: {inverter_ip} | Porta: {st.session_state.get('inverter_port', omnik.OMNIK_PORT)}")

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
                http_dados = omnik.read_via_http(inverter_ip)
                if http_dados and len([k for k in http_dados if not k.startswith('_')]) > 0:
                    dados = http_dados
                    st.session_state['metodo'] = 'HTTP'
                else:
                    if http_dados:
                        with st.expander("🌐 Conteúdo bruto da interface web (diagnóstico)"):
                            st.code(http_dados.get('_raw_html', '')[:3000], language='html')
                    try:
                        raw = omnik.read_inverter(inverter_ip, serial_no)
                        dados = omnik.parse_response(raw)
                        st.session_state['metodo'] = 'TCP:8899'
                    except ConnectionRefusedError:
                        st.error("Conexão recusada na porta 8899.")
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
                    st.session_state.pop('historico', None)

        if auto:
            time.sleep(30)
            st.rerun()

# ─── Exibição dos dados ───────────────────────────────────────────────────────

if 'dados' in st.session_state:
    d = st.session_state['dados']
    metodo = st.session_state.get('metodo', '?')
    ts = st.session_state.get('last_update')
    ts_str = time.strftime('%H:%M:%S', time.localtime(ts)) if ts else '—'
    st.caption(f"Fonte: `{metodo}` | Atualizado: `{ts_str}`")

    st.divider()
    st.subheader("Produção atual")

    gerando = (d.get('ac_potencia') or 0) > 0
    status_txt = "🟢 Gerando energia" if gerando else "🔴 Sem geração (sem sol)"
    modelo = d.get('modelo', '—')
    st.info(f"**Status:** {status_txt} | **Modelo:** {modelo}")

    c1, c2, c3 = st.columns(3)
    c1.metric("⚡ Potência agora", f"{d.get('ac_potencia', 0):.0f} W")
    c2.metric("📅 Energia hoje", f"{d.get('energia_hoje', 0):.2f} kWh")
    c3.metric("📊 Total acumulado", f"{d.get('energia_total', 0):.1f} kWh")

    energia_hoje = d.get('energia_hoje', 0)
    if energia_hoje and energia_hoje > 0:
        economia = energia_hoje * 0.95
        st.success(f"💰 Economia estimada hoje: **R$ {economia:.2f}**")

    temp = d.get('temperatura', 0)
    if temp and temp > 0:
        st.caption(f"🌡️ Temperatura do inversor: {temp} °C")

    # ─── Gráficos e histórico (Solarman) ──────────────────────────────────────
    hist = st.session_state.get('historico')
    if hist:
        curva = hist.get('curva') or []
        diario = hist.get('diario') or []
        mensal = hist.get('mensal') or []

        if curva:
            st.divider()
            st.subheader("📈 Produção de hoje")
            df = pd.DataFrame(curva, columns=["Hora", "Potência (W)"]).set_index("Hora")
            st.area_chart(df, height=240)

        if diario or mensal:
            st.divider()
            st.subheader("📅 Histórico de produção")
            tab_d, tab_m = st.tabs(["Diário (mês atual)", "Mensal (ano)"])
            with tab_d:
                if diario:
                    df = pd.DataFrame(diario, columns=["Dia", "kWh"]).set_index("Dia")
                    st.bar_chart(df, height=260)
                    st.caption(f"Total no período: **{df['kWh'].sum():.2f} kWh**")
                else:
                    st.info("Sem dados diários disponíveis.")
            with tab_m:
                if mensal:
                    df = pd.DataFrame(mensal, columns=["Mês", "kWh"]).set_index("Mês")
                    st.bar_chart(df, height=260)
                    st.caption(f"Total no ano: **{df['kWh'].sum():.2f} kWh**")
                else:
                    st.info("Sem dados mensais disponíveis.")

        if not (diario or mensal) and hist.get('_diag'):
            with st.expander("🩺 Diagnóstico do histórico (resposta crua)"):
                st.json(hist['_diag'])

    if d.get('ac_tensao') or d.get('pv1_tensao'):
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

    with st.expander("🔧 Dados brutos"):
        raw_sm = d.get('_raw_solarman') or d.get('_combinado')
        if raw_sm:
            st.json(raw_sm)
        else:
            campos = d.get('_campos_brutos', [])
            if campos:
                for i, v in enumerate(campos):
                    st.text(f"[{i}] = {v!r}")
            elif '_raw_hex' in d:
                st.code(d['_raw_hex'][:3000], language='text')
            elif '_raw_html' in d:
                st.code(d['_raw_html'][:3000], language='html')
