"""Lokale Steuerung für Wayland-Desktop-Tastenkürzel.

Der laufende Prozess lauscht ausschließlich auf einem Unix-Socket im privaten
HufiVoice-Ordner. ``--start`` beginnt, ``--stopp`` beendet die Aufnahme.
"""
import os
import socket
import threading


def socket_pfad():
    # Eigener Name für diese Testkopie: eine laufende normale HufiVoice-Instanz
    # und ihr späterer Produktions-Socket werden dadurch nicht berührt.
    return os.path.expanduser("~/.hufi/voice/steuer-test-wave.sock")


def senden(befehl):
    pfad = socket_pfad()
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
            sock.settimeout(1.0)
            sock.connect(pfad)
            sock.sendall((befehl + "\n").encode("ascii"))
        return True
    except OSError as fehler:
        print(f"HufiVoice läuft nicht oder ist nicht erreichbar: {fehler}")
        return False


def server_starten(schlange):
    pfad = socket_pfad()
    os.makedirs(os.path.dirname(pfad), mode=0o700, exist_ok=True)
    try:
        os.unlink(pfad)
    except FileNotFoundError:
        pass
    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server.bind(pfad)
    os.chmod(pfad, 0o600)
    server.listen(2)

    def laufen():
        while True:
            verbindung, _ = server.accept()
            with verbindung:
                befehl = verbindung.recv(32).decode("ascii", "ignore").strip()
            if befehl == "start":
                schlange.put("vorbereiten")
                schlange.put("start")
            elif befehl == "stopp":
                schlange.put("ende")
            elif befehl == "abbruch":
                schlange.put("abbruch")

    threading.Thread(target=laufen, daemon=True, name="hufivoice-steuerung").start()
    return server
