import hashlib
import datetime
from collections import OrderedDict

import requests

try:
    from zoneinfo import ZoneInfo
    TZ = ZoneInfo("America/Sao_Paulo")
except Exception:
    TZ = datetime.timezone(datetime.timedelta(hours=-3))

APP_ID = "312604108356496"
APP_SECRET = "17d7a339e0b089d510f40f86141aec40"
BASE_URL = "https://globalapi.solarmanpv.com"

DEVICE_SN = "BRBN302019653063"
LOGGER_SNS = [645450063, 3912868676]

# Dispositivos disponíveis (rótulo -> SN)
DEVICES = {
    "Inversor (BRBN30...653063)": "BRBN302019653063",
    "Micro-inversor (2302026889)": "2302026889",
}


def combinar(dados_list: list) -> dict:
    """Soma métricas de vários inversores em uma visão única da usina."""
    soma_keys = ["ac_potencia", "energia_hoje", "energia_total",
                 "pv1_potencia", "pv2_potencia"]
    combinado = {k: 0 for k in soma_keys}
    for d in dados_list:
        for k in soma_keys:
            combinado[k] += d.get(k) or 0
    # Médias/máximos para grandezas que não somam
    temps = [d.get("temperatura") for d in dados_list if d.get("temperatura")]
    combinado["temperatura"] = max(temps) if temps else 0
    combinado["modelo"] = f"{len(dados_list)} inversores (somados)"
    combinado["potencia_nominal"] = 0
    combinado["_combinado"] = [d.get("_raw_solarman") for d in dados_list]
    return combinado


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def get_token(email: str, password: str) -> str:
    url = f"{BASE_URL}/account/v1.0/token?appId={APP_ID}&language=pt"
    resp = requests.post(url, json={
        "email": email,
        "appSecret": APP_SECRET,
        "password": _sha256(password),
    }, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    # Na API Solarman, sucesso vem com success=true e code/msg = null
    token = data.get("access_token")
    if not token:
        msg = data.get("msg") or data.get("error") or data
        raise RuntimeError(f"Erro ao obter token: {msg}")
    return token


def get_realtime_data(token: str, device_sn: str = DEVICE_SN) -> dict:
    url = f"{BASE_URL}/device/v1.0/currentData?appId={APP_ID}&language=pt"
    resp = requests.post(url, json={"deviceSn": device_sn}, headers={
        "Authorization": f"Bearer {token}",
    }, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    if not data.get("success", False) and not data.get("dataList"):
        msg = data.get("msg") or data.get("error") or data
        raise RuntimeError(f"Erro ao buscar dados: {msg}")
    return data


def parse_realtime(raw: dict) -> dict:
    """Convert Solarman API response to the same schema used by omnik.parse_response.

    Os códigos (`key`) da Solarman variam por modelo de inversor, então casamos
    por trechos do nome (`name`) e da `key`, em vez de nomes exatos.
    """
    items = raw.get("dataList", [])
    by_key = {it.get("key"): it for it in items}

    def _num(v):
        try:
            return float(v)
        except (TypeError, ValueError):
            return None

    def val(*keys):
        """Valor numérico pela key exata (tenta cada uma na ordem)."""
        for k in keys:
            it = by_key.get(k)
            if it is not None:
                v = _num(it.get("value"))
                if v is not None:
                    return v
        return 0

    def text(*keys):
        for k in keys:
            it = by_key.get(k)
            if it is not None and it.get("value") is not None:
                return it["value"]
        return None

    result = {
        # Chaves reais (inversor e micro-inversor têm códigos um pouco diferentes)
        "ac_potencia":      val("APo_t1"),                 # Potência Total Saída CA (Ativa) - W
        "energia_hoje":     val("Etdy_ge0", "Etdy_ge1"),   # Produção diária ativa - kWh
        "energia_total":    val("Et_ge0"),                 # Produção total ativa - kWh
        "temperatura":      val("INV_T0", "AC_RDT_T1"),    # Temperatura - °C
        "pv1_tensao":       val("DV1"),
        "pv1_corrente":     val("DC1"),
        "pv1_potencia":     val("DP1"),
        "pv2_tensao":       val("DV2"),
        "pv2_corrente":     val("DC2"),
        "pv2_potencia":     val("DP2"),
        "ac_tensao":        val("AV1"),                    # Voltagem AC
        "ac_corrente":      val("AC1"),
        "ac_frequencia":    val("A_Fo1", "AF1"),           # Frequência AC
        "estado":           text("INV_ST1", "ST_PG1"),     # Estado do inversor/rede
        "horas_operacao":   val("t_w_hou1"),
        "modelo":           raw.get("deviceType", "Solarman"),
        "potencia_nominal": 0,
        "_raw_solarman":    raw,
        "_data_keys":       [it.get("key") for it in items],
    }
    return result


# ─── Histórico ──────────────────────────────────────────────────────────────

# timeType da API Solarman: 1=dia (intervalos de 5min), 2=mês (por dia), 3=ano (por mês)
TIME_DAY, TIME_MONTH, TIME_YEAR = 1, 2, 3


def get_historical(token: str, device_sn: str, start_date: str,
                   end_date: str, time_type: int) -> dict:
    """Busca dados históricos de um dispositivo. Datas no formato YYYY-MM-DD."""
    url = f"{BASE_URL}/device/v1.0/historical?appId={APP_ID}&language=pt"
    resp = requests.post(url, json={
        "deviceSn": device_sn,
        "startTime": start_date,
        "endTime": end_date,
        "timeType": time_type,
    }, headers={"Authorization": f"Bearer {token}"}, timeout=25)
    resp.raise_for_status()
    data = resp.json()
    if not data.get("success", False) and not data.get("paramDataList"):
        msg = data.get("msg") or data.get("error") or data
        raise RuntimeError(f"Erro no histórico: {msg}")
    return data


def _ponto_valor(ponto: dict, *keys):
    """Extrai valor numérico de uma das keys dentro de um ponto histórico."""
    dl = {it.get("key"): it for it in ponto.get("dataList", [])}
    for k in keys:
        it = dl.get(k)
        if it is not None:
            try:
                return float(it.get("value"))
            except (TypeError, ValueError):
                pass
    return None


def _label_tempo(ponto: dict, fmt: str) -> str:
    ct = ponto.get("collectTime") or ponto.get("time") or ponto.get("collectionTime")
    try:
        return datetime.datetime.fromtimestamp(int(ct), TZ).strftime(fmt)
    except (TypeError, ValueError):
        return str(ct)


def parse_curva_potencia(raw: dict) -> list:
    """Curva de potência do dia: lista de (hora 'HH:MM', potência W)."""
    pontos = []
    for p in raw.get("paramDataList", []):
        val = _ponto_valor(p, "APo_t1")
        if val is not None:
            pontos.append((_label_tempo(p, "%H:%M"), val))
    return pontos


def parse_historico_energia(raw: dict, fmt: str = "%d/%m") -> list:
    """Produção por período: lista de (label, kWh).

    Tenta produção diária ativa (Etdy_ge0/Etdy_ge1); cai para campos genéricos
    de geração ou para o produto encontrado em 'generationValue'.
    """
    pontos = []
    for p in raw.get("paramDataList", []):
        val = _ponto_valor(p, "Etdy_ge0", "Etdy_ge1", "Et_ge0")
        if val is None:
            # alguns formatos trazem direto no ponto
            for k in ("generationValue", "value", "energy"):
                try:
                    val = float(p.get(k))
                    break
                except (TypeError, ValueError):
                    continue
        if val is not None:
            pontos.append((_label_tempo(p, fmt), val))
    return pontos


def combinar_series(series_list: list) -> list:
    """Soma várias séries (lista de (label, valor)) alinhando pelos labels."""
    acc = OrderedDict()
    for serie in series_list:
        for label, v in serie:
            acc[label] = acc.get(label, 0) + (v or 0)
    return list(acc.items())
