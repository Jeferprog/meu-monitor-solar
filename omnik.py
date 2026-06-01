"""Protocolo local para inversores Omnik via HTTP web interface ou TCP 8899."""
import socket
import struct
import concurrent.futures
import ipaddress
import urllib.request
import re

OMNIK_PORT = 8899
OMNIK_PORT_ALT = 48899
SCAN_TIMEOUT = 0.8


def read_via_http(ip: str, timeout: float = 10.0) -> dict | None:
    """Tenta ler dados do inversor pela interface web HTTP.
    Testa endpoints conhecidos dos módulos WiFi Omnik/Ginlong."""
    endpoints = [
        f'http://{ip}/js/status.js',
        f'http://{ip}/inverter.cgi?embed',
        f'http://{ip}/status.html',
        f'http://{ip}/info.xml',
        f'http://{ip}/',
    ]
    for url in endpoints:
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                content = resp.read().decode('utf-8', errors='replace')
                parsed = _parse_http_content(content, url)
                if parsed:
                    parsed['_source_url'] = url
                    parsed['_raw_html'] = content
                    return parsed
        except Exception:
            continue
    return None


def _parse_http_content(content: str, url: str) -> dict | None:
    """Extrai valores do HTML/JS retornado pelo inversor Omnik."""
    result = {}

    # Formato Omnik/Ginlong: myDeviceArray[0]="SN,FW1,FW2,Model,Rated,Power,EToday_Wh,Temp,..."
    match = re.search(r'myDeviceArray\[0\]="([^"]+)"', content)
    if match:
        fields = match.group(1).split(',')
        try:
            result['modelo']           = fields[3] if len(fields) > 3 else '—'
            result['potencia_nominal'] = int(fields[4]) if len(fields) > 4 and fields[4].isdigit() else 0
            result['ac_potencia']      = int(fields[5]) if len(fields) > 5 and fields[5].isdigit() else 0
            result['energia_hoje_wh']  = int(fields[6]) if len(fields) > 6 and fields[6].isdigit() else 0
            result['energia_hoje']     = result['energia_hoje_wh'] / 1000.0
            result['temperatura']      = int(fields[7]) if len(fields) > 7 and fields[7].isdigit() else 0
            result['status']           = int(fields[9]) if len(fields) > 9 and fields[9].isdigit() else 0
            result['_campos_brutos']   = fields
        except (ValueError, IndexError):
            pass
        if result:
            return result

    # Padrão JavaScript: var webdata_now_p = "1234";
    js_vars = re.findall(r'var\s+(\w+)\s*=\s*["\']?([\d.]+)["\']?', content)
    if js_vars:
        data = {k: v for k, v in js_vars}
        mapping = {
            'webdata_now_p':    ('ac_potencia',   1.0),
            'webdata_today_e':  ('energia_hoje',  1.0),
            'webdata_total_e':  ('energia_total', 1.0),
            'webdata_uac':      ('ac_tensao',     1.0),
            'webdata_fac':      ('ac_frequencia', 1.0),
            'webdata_tmp':      ('temperatura',   1.0),
            'webdata_pv1_vol':  ('pv1_tensao',    1.0),
            'webdata_pv1_cur':  ('pv1_corrente',  1.0),
            'webdata_pv2_vol':  ('pv2_tensao',    1.0),
            'webdata_pv2_cur':  ('pv2_corrente',  1.0),
        }
        for js_key, (field, factor) in mapping.items():
            if js_key in data:
                try:
                    result[field] = float(data[js_key]) * factor
                except ValueError:
                    pass
        if result:
            return result

    if len(content) > 50:
        return {'_raw_html': content}
    return None


def generate_request(serial_no: int) -> bytes:
    header = b'\x68\x02\x40\x30'
    sn_bytes = serial_no.to_bytes(4, byteorder='big')
    body = header + sn_bytes + sn_bytes + b'\x01\x00'
    return body + bytes([115]) + b'\x16'


def read_inverter(ip: str, serial_no: int, timeout: float = 10.0) -> bytes:
    request = generate_request(serial_no)
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(timeout)
        s.connect((ip, OMNIK_PORT))
        s.sendall(request)
        data = b''
        while True:
            chunk = s.recv(1024)
            if not chunk:
                break
            data += chunk
    return data


def parse_response(data: bytes) -> dict:
    if len(data) < 80:
        raise ValueError(f"Resposta muito curta: {len(data)} bytes. Esperado >= 80.")

    def u16(offset):
        return struct.unpack_from('>H', data, offset)[0]

    def u32(offset):
        return struct.unpack_from('>I', data, offset)[0]

    return {
        'temperatura':    u16(31) / 10.0,
        'pv1_tensao':     u16(33) / 10.0,
        'pv2_tensao':     u16(35) / 10.0,
        'pv1_corrente':   u16(39) / 10.0,
        'pv2_corrente':   u16(41) / 10.0,
        'ac_tensao':      u16(51) / 10.0,
        'ac_frequencia':  u16(57) / 100.0,
        'ac_potencia':    u16(59),
        'energia_hoje':   u16(69) / 100.0,
        'energia_total':  u32(71) / 10.0,
        'horas_total':    u32(75),
        '_raw_hex':       data.hex(),
        '_raw_len':       len(data),
    }


def get_all_local_ips() -> list[str]:
    """Retorna todos os IPs IPv4 locais de todas as interfaces."""
    ips = []
    try:
        hostname = socket.gethostname()
        for info in socket.getaddrinfo(hostname, None, socket.AF_INET):
            ip = info[4][0]
            if not ip.startswith('127.'):
                ips.append(ip)
    except Exception:
        pass
    # fallback via rota padrão
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(('8.8.8.8', 80))
            ip = s.getsockname()[0]
            if ip not in ips:
                ips.append(ip)
    except Exception:
        pass
    return list(dict.fromkeys(ips))  # remove duplicatas mantendo ordem


def get_local_ip() -> str:
    ips = get_all_local_ips()
    return ips[0] if ips else '127.0.0.1'


def scan_subnet(subnet: str) -> list[tuple[str, int]]:
    """Retorna lista de (ip, porta) encontrados com inversor Omnik."""
    network = ipaddress.IPv4Network(subnet, strict=False)
    found = []

    def check_tcp(ip, port):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(SCAN_TIMEOUT)
                if s.connect_ex((str(ip), port)) == 0:
                    return (str(ip), port)
        except Exception:
            pass
        return None

    def check_udp(ip, port):
        """Tenta enviar broadcast UDP e aguarda resposta."""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.settimeout(SCAN_TIMEOUT)
                s.sendto(b'\x68\x02\x40\x30', (str(ip), port))
                data, _ = s.recvfrom(1024)
                if data:
                    return (str(ip), port)
        except Exception:
            pass
        return None

    hosts = list(network.hosts())
    tasks = [(ip, p) for ip in hosts for p in (OMNIK_PORT, OMNIK_PORT_ALT)]

    with concurrent.futures.ThreadPoolExecutor(max_workers=150) as ex:
        tcp_results = ex.map(lambda t: check_tcp(*t), tasks)
        found = [r for r in tcp_results if r]

    if not found:
        with concurrent.futures.ThreadPoolExecutor(max_workers=150) as ex:
            udp_results = ex.map(lambda t: check_udp(*t), tasks)
            found = [r for r in udp_results if r]

    return found
