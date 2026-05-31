"""Protocolo local para inversores Omnik via porta TCP 8899."""
import socket
import struct
import concurrent.futures
import ipaddress

OMNIK_PORT = 8899
SCAN_TIMEOUT = 0.5


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


def get_local_ip() -> str:
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.connect(('8.8.8.8', 80))
        return s.getsockname()[0]


def scan_subnet(subnet: str) -> list[str]:
    network = ipaddress.IPv4Network(subnet, strict=False)
    found = []

    def check(ip):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(SCAN_TIMEOUT)
                if s.connect_ex((str(ip), OMNIK_PORT)) == 0:
                    return str(ip)
        except Exception:
            pass
        return None

    with concurrent.futures.ThreadPoolExecutor(max_workers=100) as ex:
        results = ex.map(check, network.hosts())
        found = [r for r in results if r]

    return found
