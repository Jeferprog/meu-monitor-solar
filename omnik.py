"""Protocolo local para inversores Omnik via porta TCP/UDP 8899 ou 48899."""
import socket
import struct
import concurrent.futures
import ipaddress

OMNIK_PORT = 8899
OMNIK_PORT_ALT = 48899
SCAN_TIMEOUT = 0.8


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
