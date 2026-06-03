import hashlib
import requests

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
        # Chaves reais do inversor (confirmadas via Dados brutos)
        "ac_potencia":      val("APo_t1"),       # Saída CA Potência Total (Ativa) - W
        "energia_hoje":     val("Etdy_ge1"),     # Produção diária (ativa) - kWh
        "energia_total":    val("Et_ge0"),       # Produção acumulada (ativa) - kWh
        "temperatura":      val("INV_T0"),       # Temperatura do Inversor - °C
        "pv1_tensao":       val("DV1"),
        "pv1_corrente":     val("DC1"),
        "pv1_potencia":     val("DP1"),
        "pv2_tensao":       val("DV2"),
        "pv2_corrente":     val("DC2"),
        "pv2_potencia":     val("DP2"),
        "ac_tensao":        val("AV1"),           # Voltagem AC R/U/A
        "ac_corrente":      val("AC1"),
        "ac_frequencia":    val("A_Fo1"),         # Frequência de Saída AC R
        "estado":           text("INV_ST1"),      # Estado do inversor
        "horas_operacao":   val("t_w_hou1"),
        "modelo":           raw.get("deviceType", "Solarman"),
        "potencia_nominal": 0,
        "_raw_solarman":    raw,
        "_data_keys":       [it.get("key") for it in items],
    }
    return result
