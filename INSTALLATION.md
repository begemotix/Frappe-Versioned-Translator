# Installation Guide - Versioned Translator

## Installation auf Coolify

### Schritt 1: Site-Namen herausfinden

Im Coolify-Terminal ausführen:

```bash
# Site-Namen anzeigen
ls sites/
# ODER
bench list-sites
```

### Schritt 2: App von GitHub installieren

```bash
# 1. App herunterladen
bench get-app https://github.com/begemotix/Frappe-Versioned-Translator.git

# 2. App installieren (ERSEZEN SIE 'your-site-name' mit dem tatsächlichen Site-Namen)
bench --site your-site-name install-app versioned_translator

# 3. Migration ausführen (DocTypes erstellen)
bench --site your-site-name migrate

# 4. Cache leeren
bench --site your-site-name clear-cache

# 5. Falls nötig, Container neu starten
bench restart
```

### Schritt 3: Nach der Installation

1. **Translation Settings konfigurieren:**
   - Gehen Sie zu: Translation Settings
   - Fügen Sie Ihren DeepL API-Key hinzu
   - Konfigurieren Sie Source- und Target-Sprachen

2. **Translation Maps erstellen:**
   - Gehen Sie zu: Translation Map
   - Wählen Sie einen DocType aus
   - Klicken Sie auf "Get Fields" um Felder automatisch zu mappen
   - Aktivieren Sie die Translation Map

3. **Browser-Cache leeren:**
   - Drücken Sie Ctrl+Shift+R im Browser

## Troubleshooting

### Falls `bench get-app` nicht funktioniert:

```bash
# Manuell klonen
cd /workspace/apps  # oder wo Ihre Apps liegen
git clone https://github.com/begemotix/Frappe-Versioned-Translator.git versioned_translator

# Dann installieren
bench --site your-site-name install-app versioned_translator
```

### Falls die App nicht erscheint:

```bash
# Prüfen ob App vorhanden ist
ls apps/versioned_translator

# Prüfen ob App installiert ist
bench --site your-site-name list-apps
```
