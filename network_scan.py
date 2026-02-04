import socket
import threading
from queue import Queue

target = "192.168.1."
queue = Queue()
open_ports = []

def portscan(port):
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(0.5)
        conn = sock.connect((port, 80))
        return True
    except:
        return False
    finally:
        sock.close()

def worker():
    while not queue.empty():
        ip = queue.get()
        if portscan(ip):
            print(f"Dispositivo encontrado: {ip}")
            open_ports.append(ip)
        queue.task_done()

print("Escaneando red 192.168.1.0/24...")

for x in range(1, 255):
    queue.put(target + str(x))

for x in range(50):
    t = threading.Thread(target=worker)
    t.daemon = True
    t.start()

queue.join()
print("Escaneo finalizado.")
