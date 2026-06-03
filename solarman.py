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
    """Convert Solarman API response to the same schema used by omnik.parse_response."""
    dl = {item["key"]: item for item in raw.get("dataList", [])}

    def val(key, default=0):
        item = dl.get(key)
        if item is None:
            return default
        try:
            return float(item["value"])
        except (TypeError, ValueError):
            return item.get("value", default)

    result = {
        "ac_potencia":      val("AC_ActivePower") or val("activePower") or val("AC_Power"),
        "energia_hoje":     val("E_Today") or val("dailyEnergy") or val("daily_power"),
        "energia_total":    val("E_Total") or val("totalEnergy") or val("total_power"),
        "temperatura":      val("DC_Temp") or val("inverterTemperature"),
        "pv1_tensao":       val("DC_Voltage1") or val("PV1_Voltage"),
        "pv1_corrente":     val("DC_Current1") or val("PV1_Current"),
        "pv2_tensao":       val("DC_Voltage2") or val("PV2_Voltage"),
        "pv2_corrente":     val("DC_Current2") or val("PV2_Current"),
        "ac_tensao":        val("AC_Voltage1") or val("GridVoltage"),
        "ac_frequencia":    val("AC_Freq1") or val("GridFrequency"),
        "modelo":           raw.get("deviceType", "Solarman"),
        "potencia_nominal": 0,
        "_raw_solarman":    raw,
        "_data_keys":       list(dl.keys()),
    }
    return result
