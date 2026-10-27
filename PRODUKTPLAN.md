# HufiVoice: vom privaten Test zur verkaufbaren App

## Jetzt in dieser Testkopie

- Linux-Desktop: frei wählbare Halte-Taste, C920-Mikrofon, Wave-Overlay und Einfügen in lokale Programme oder Webformulare.
- Linux-Web: lokale Browser-App auf `127.0.0.1`, Aufnahme und Erkennung bleiben auf dem eigenen Rechner, wenn `modus: lokal` gewählt ist.
- Android-Web: responsive installierbare PWA ist vorbereitet. Ein echter Gerätetest braucht einen vertrauenswürdigen HTTPS-Zugang.
- Online: Die PWA kann einen eigenen HTTPS-Endpunkt ansprechen. Die offizielle Website bietet derzeit öffentlich Download, Warteliste und Kontakt, aber noch keine bestätigte Web-Transkription.

## Vor der privaten Online-Nutzung

1. Einen privaten HTTPS-Endpunkt bereitstellen und nur die benötigte Herkunft per CORS erlauben.
2. Benutzerzugang statt eines gemeinsam genutzten Tokens einbauen.
3. Größen-, Zeit- und Anfragelimits serverseitig erzwingen; Rohaufnahmen standardmäßig nicht speichern.
4. Android mit echtem Mikrofon, gesperrtem Bildschirm, Netzwechsel und PWA-Installation testen.
5. Lösch- und Sicherungskonzept dokumentieren.

## Vor einem Verkauf

- Eigene HufiVoice-Lizenz und Rechtekette festlegen; Abhängigkeiten und Modelle einzeln prüfen.
- Mandantentrennung, Benutzerkonten, E-Mail-Bestätigung, Missbrauchsschutz, Abrechnung und Support bauen.
- Datenschutz- und Vertragstexte professionell für das tatsächliche Geschäftsmodell prüfen lassen.
- Sicherheitsprüfung für Uploads, Authentifizierung, Protokolle, Schlüsselverwaltung und Updates durchführen.
- Reproduzierbare Linux-Pakete signieren; Android zunächst als PWA testen und erst danach über eine native Hülle oder App entscheiden.

## Später

- Windows: eigener globaler Hotkey, Fokus-sicheres Einfügen und signierter Installer.
- Apple/macOS: Accessibility-Berechtigung, globaler Hotkey und notarisiertes Paket.
- iPhone/iPad: PWA oder native App; eine systemweite Desktop-Haltetaste ist dort nicht gleich umsetzbar.

Die Plattformen teilen sich Web-Oberfläche, WAV-Format und Transkriptions-API. Betriebssystemnahe Hotkeys und Texteinfügung bleiben kleine, getrennte Adapter. So kann die Kernfunktion gemeinsam weiterentwickelt werden, ohne Linux-Verhalten auf andere Systeme zu kopieren.
