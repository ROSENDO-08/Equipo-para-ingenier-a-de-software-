# config.py — Credenciales y umbrales
# Modifica este archivo antes de flashear al ESP32

WIFI_SSID     = 'DataLogger-ESP32'
WIFI_PASSWORD = 'datalogger123'   # <-- cambia esto

DASHBOARD_USER = 'admin'
DASHBOARD_PASS = 'esp32pass'      # <-- cambia esto

UMBRAL_TEMP = 30.0   # °C
UMBRAL_HUM  = 75.0   # %

DHT_PIN = 4          # GPIO4 (pin seguro, no strapping)
LED_PIN = 4          # Cambiar si usas LED externo; GPIO2 es pin strapping
