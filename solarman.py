import hashlib
import requests

APP_ID = "312604108356496"
APP_SECRET = "17d7a339e0b089d510f40f86141aec40"
BASE_URL = "https://globalapi.solarmanpv.com"

DEVICE_SN = "BRBN302019653063"
LOGGER_SNS = [645450063, 3912868676]


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

    def _num(v):
        try:
            return float(v)
        except (TypeError, ValueError):
            return None

    def find(*needles, prefer_unit=None):
        """Retorna o primeiro valor numérico cujo name/key contém algum dos trechos."""
        needles = [n.lower() for n in needles]
        for it in items:
            name = str(it.get("name", "")).lower()
            key = str(it.get("key", "")).lower()
            haystack = name + " " + key
            if any(n in haystack for n in needles):
                if prefer_unit and prefer_unit.lower() not in str(it.get("unit", "")).lower():
                    continue
                v = _num(it.get("value"))
                if v is not None:
                    return v
        return 0

    result = {
        # Potência ativa de saída AC (W)
        "ac_potencia":      find("total ac output power", "output active power",
                                 "active power", "generation power", "ac_power", "apo"),
        # Energia gerada hoje (kWh)
        "energia_hoje":     find("daily production", "production today", "today production",
                                 "daily generation", "e_today", "etoday", "et_ge0"),
        # Energia acumulada total (kWh)
        "energia_total":    find("cumulative production", "total production",
                                 "total generation", "e_total", "etotal", "et_ge"),
        "temperatura":      find("temperature", "temp"),
        "pv1_tensao":       find("dc voltage pv1", "pv1 voltage", "voltage pv1", "dv1"),
        "pv1_corrente":     find("dc current pv1", "pv1 current", "current pv1", "dc1"),
        "pv2_tensao":       find("dc voltage pv2", "pv2 voltage", "voltage pv2", "dv2"),
        "pv2_corrente":     find("dc current pv2", "pv2 current", "current pv2", "dc2"),
        "ac_tensao":        find("ac voltage", "grid voltage", "av1"),
        "ac_frequencia":    find("ac frequency", "grid frequency", "frequency"),
        "modelo":           raw.get("deviceType", "Solarman"),
        "potencia_nominal": 0,
        "_raw_solarman":    raw,
        "_data_keys":       [it.get("key") for it in items],
    }
    return result
