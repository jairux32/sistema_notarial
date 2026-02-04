import subprocess
import threading
from queue import Queue
import platform

target_prefix = "192.168.1."
queue = Queue()

def pinger(ip):
    try:
        # -c 1 (count), -W 1 (timeout in seconds)
        # Linux uses -c, Windows uses -n. Docker is Linux.
        cmd = ['ping', '-c', '1', '-W', '1', ip]
        res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if res.returncode == 0:
            print(f"ALIVE: {ip}")
            return True
    except:
        pass
    return False

def worker():
    while not queue.empty():
        ip = queue.get()
        pinger(ip)
        queue.task_done()

print("Iniciando barrido de Ping (192.168.1.1 - 254)...")

for x in range(1, 255):
    queue.put(target_prefix + str(x))

for x in range(50):
    t = threading.Thread(target=worker)
    t.daemon = True
    t.start()

queue.join()
print("Barrido finalizado.")
