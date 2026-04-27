import network, socket, math, gc
import dht
from machine import Pin
from config import (WIFI_SSID, WIFI_PASSWORD, DASHBOARD_USER,
                    DASHBOARD_PASS, UMBRAL_TEMP, UMBRAL_HUM,
                    DHT_PIN, LED_PIN)
import ubinascii

# ── FIX T2: GPIO4 en lugar de GPIO2 (pin strapping) ─────────
led    = Pin(LED_PIN, Pin.OUT)
sensor = dht.DHT11(Pin(DHT_PIN))   # FIX T1: lectura real DHT11

# ── FIX S2: token de autenticación básica ───────────────────
_creds = ubinascii.b2a_base64(
    (DASHBOARD_USER + ':' + DASHBOARD_PASS).encode()
).decode().strip()
AUTH_HEADER = 'Basic ' + _creds

ap = network.WLAN(network.AP_IF)
ap.active(True)
ap.config(essid=WIFI_SSID, password=WIFI_PASSWORD)   # FIX S1
print("Red WiFi creada:", ap.ifconfig()[0])

# ── FIX T1: lectura real del DHT11 ──────────────────────────
def leer_sensor():
    sensor.measure()
    temp  = sensor.temperature()    # valor real, no random
    hum   = sensor.humidity()       # valor real, no random
    press = 1013.0                  # DHT11 no mide presión; valor fijo estándar
    return float(temp), float(hum), float(press)

def indice_calor(T, H):
    hi = (-8.78469475556 + 1.61139411*T + 2.33854883889*H
          - 0.14611605*T*H - 0.012308094*T**2
          - 0.0164248277778*H**2 + 0.002211732*T**2*H
          + 0.00072546*T*H**2 - 0.000003582*T**2*H**2)
    return round(hi, 1)

def check_auth(req):
    """FIX S2: verifica cabecera Authorization en la petición."""
    return ('Authorization: Basic ' + _creds) in req

# ── Página HTML ──────────────────────────────────────────────
HTML = """\
HTTP/1.1 200 OK\r\nContent-Type: text/html; charset=UTF-8\r\n\r\n
<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Data Logger ESP32</title>
  <style>
    *{box-sizing:border-box;margin:0;padding:0}
    body{background:#0d1117;color:#e6edf3;font-family:'Courier New',monospace;
         display:flex;flex-direction:column;align-items:center;
         min-height:100vh;padding:2rem 1rem}
    h1{color:#ff6b35;font-size:1.6rem;font-weight:500;
       letter-spacing:1px;margin-bottom:0.3rem}
    .sub{font-size:.7rem;color:#484f58;letter-spacing:2px;margin-bottom:2rem}
    .grid{display:grid;grid-template-columns:1fr 1fr;gap:1rem;
          width:100%;max-width:560px;margin-bottom:1rem}
    .card{background:#161b22;border:.5px solid #30363d;border-radius:12px;
          padding:1.25rem;text-align:center;position:relative;overflow:hidden}
    .card::before{content:'';position:absolute;top:0;left:0;right:0;height:3px}
    .t-card::before{background:#ff6b35}
    .h-card::before{background:#2ea8e0}
    .p-card::before{background:#a371f7}
    .hi-card::before{background:#3fb950}
    .val{font-size:2.4rem;font-weight:500;line-height:1;
         transition:color .4s ease}
    .lbl{font-size:.65rem;color:#484f58;margin-top:.35rem;
         letter-spacing:1px;text-transform:uppercase}
    .bar-wrap{margin:.5rem auto 0;width:100%}
    .bar-track{height:3px;background:#21262d;border-radius:4px;overflow:hidden}
    .bar-fill{height:100%;border-radius:4px;transition:width .6s ease,background .4s ease}
    .alerta-card{background:#161b22;border:.5px solid #30363d;
                 border-radius:12px;padding:.9rem 1.25rem;
                 width:100%;max-width:560px;margin-bottom:1rem;
                 display:flex;align-items:center;gap:.75rem}
    .dot{width:10px;height:10px;border-radius:50%;flex-shrink:0;
         transition:background .4s ease}
    .estado{font-size:.85rem;font-weight:500;transition:color .4s ease}
    .log{background:#161b22;border:.5px solid #30363d;border-radius:12px;
         padding:.75rem 1rem;width:100%;max-width:560px;
         font-size:.7rem;color:#484f58;line-height:1.8}
    .log span{color:#3fb950}
    .conn{font-size:.65rem;text-align:right;width:100%;max-width:560px;
          margin-top:.5rem;color:#484f58}
    .conn.ok{color:#3fb950} .conn.err{color:#f85149}
    .footer{font-size:.6rem;color:#21262d;margin-top:1.25rem;letter-spacing:1px}
  </style>
</head>
<body>
  <h1>&#x1F4CA; Data Logger ESP32</h1>
  <div class="sub">UAG · INGENIERÍA DE SOFTWARE</div>

  <div class="grid">
    <div class="card t-card">
      <div class="val" id="temp" style="color:#e8eaf0">-- °C</div>
      <div class="lbl">Temperatura</div>
      <div class="bar-wrap"><div class="bar-track">
        <div class="bar-fill" id="bar-temp" style="width:0%;background:#ff6b35"></div>
      </div></div>
    </div>
    <div class="card h-card">
      <div class="val" id="hum" style="color:#e8eaf0">-- %</div>
      <div class="lbl">Humedad relativa</div>
      <div class="bar-wrap"><div class="bar-track">
        <div class="bar-fill" id="bar-hum" style="width:0%;background:#2ea8e0"></div>
      </div></div>
    </div>
    <div class="card p-card">
      <div class="val" id="press" style="color:#a371f7">-- hPa</div>
      <div class="lbl">Presión atm.</div>
      <div class="bar-wrap"><div class="bar-track">
        <div class="bar-fill" id="bar-press" style="width:0%;background:#a371f7"></div>
      </div></div>
    </div>
    <div class="card hi-card">
      <div class="val" id="heat" style="color:#3fb950">-- °C</div>
      <div class="lbl">Índice de calor</div>
      <div class="bar-wrap"><div class="bar-track">
        <div class="bar-fill" id="bar-heat" style="width:0%;background:#3fb950"></div>
      </div></div>
    </div>
  </div>

  <div class="alerta-card">
    <div class="dot" id="dot" style="background:#484f58"></div>
    <div class="estado" id="estado" style="color:#484f58">Iniciando...</div>
  </div>

  <div class="log">
    <div>[SYS] Servidor activo &nbsp;·&nbsp; Puerto 80</div>
    <div id="log-sen">[SEN] Esperando primera lectura...</div>
    <div id="log-led">[LED] --</div>
  </div>

  <div class="conn" id="conn">&#x25CB; conectando...</div>
  <div class="footer">SIN RECARGA DE PAGINA · FETCH CADA 3 SEG</div>

  <script>
    async function actualizar() {
      try {
        // FIX S2: incluye credenciales en cada fetch al endpoint /datos
        const r = await fetch('/datos', {
          cache: 'no-store',
          headers: {
            'Authorization': 'Basic ' + btoa('""" + DASHBOARD_USER + ":" + DASHBOARD_PASS + """')
          }
        });
        if (r.status === 401) {
          document.getElementById('conn').textContent = '\\u25CB no autorizado';
          document.getElementById('conn').className = 'conn err';
          return;
        }
        if (!r.ok) throw new Error('HTTP ' + r.status);
        const d = await r.json();

        document.getElementById('conn').textContent = '\\u25CF datos OK';
        document.getElementById('conn').className = 'conn ok';

        const cTemp  = d.alerta_temp ? '#ff6b35' : '#e8eaf0';
        const cHum   = d.alerta_hum  ? '#2ea8e0' : '#e8eaf0';
        const cHeat  = d.hi > 32     ? '#f85149' : '#3fb950';

        document.getElementById('temp').textContent  = d.temp  + ' \\u00B0C';
        document.getElementById('hum').textContent   = d.hum   + ' %';
        document.getElementById('press').textContent = d.press + ' hPa';
        document.getElementById('heat').textContent  = d.hi    + ' \\u00B0C';

        document.getElementById('temp').style.color  = cTemp;
        document.getElementById('hum').style.color   = cHum;
        document.getElementById('heat').style.color  = cHeat;

        document.getElementById('bar-temp').style.width      = d.pct_temp  + '%';
        document.getElementById('bar-temp').style.background = cTemp === '#e8eaf0' ? '#ff6b35' : cTemp;
        document.getElementById('bar-hum').style.width       = d.pct_hum   + '%';
        document.getElementById('bar-press').style.width     = d.pct_press + '%';
        document.getElementById('bar-heat').style.width      = d.pct_heat  + '%';
        document.getElementById('bar-heat').style.background = cHeat;

        const dot    = document.getElementById('dot');
        const estado = document.getElementById('estado');
        if (d.alerta_temp && d.alerta_hum) {
          dot.style.background = estado.style.color = '#f85149';
          estado.textContent = '\\u26A0 TEMP Y HUMEDAD ALTAS';
        } else if (d.alerta_temp) {
          dot.style.background = estado.style.color = '#ff6b35';
          estado.textContent = '\\u26A0 TEMPERATURA ALTA';
        } else if (d.alerta_hum) {
          dot.style.background = estado.style.color = '#2ea8e0';
          estado.textContent = '\\u26A0 HUMEDAD ALTA';
        } else {
          dot.style.background = estado.style.color = '#3fb950';
          estado.textContent = '\\u2713 Todo normal';
        }

        document.getElementById('log-sen').innerHTML =
          '[SEN] T=<span>' + d.temp + '\\u00B0C</span>' +
          ' H=<span>' + d.hum + '%</span>' +
          ' P=<span>' + d.press + 'hPa</span>' +
          ' HI=<span>' + d.hi + '\\u00B0C</span>';
        document.getElementById('log-led').textContent =
          '[LED] ' + (d.alerta ? 'ENCENDIDO \\u00B7 alerta activa' : 'APAGADO  \\u00B7 sin alertas');

      } catch(e) {
        document.getElementById('conn').textContent = '\\u25CB sin respuesta...';
        document.getElementById('conn').className = 'conn err';
      }
    }

    actualizar();
    setInterval(actualizar, 3000);
  </script>
</body>
</html>"""

RESP_401 = ('HTTP/1.1 401 Unauthorized\r\n'
            'WWW-Authenticate: Basic realm="DataLogger"\r\n'
            'Content-Length: 0\r\n\r\n')

# ── Servidor ─────────────────────────────────────────────────
addr = socket.getaddrinfo('0.0.0.0', 80)[0][-1]
s = socket.socket()
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
s.bind(addr)
s.listen(5)
s.settimeout(1)
print("Servidor escuchando en puerto 80...")

while True:
    try:
        cl, addr = s.accept()
        req = cl.recv(1024).decode('utf-8', 'ignore')

        if '/datos' in req:
            # FIX S2: verificar autenticación antes de servir datos
            if not check_auth(req):
                cl.send(RESP_401)
                cl.close()
                gc.collect()   # FIX T3
                continue

            temp, hum, press = leer_sensor()
            hi = indice_calor(temp, hum)

            alerta_temp = temp > UMBRAL_TEMP
            alerta_hum  = hum  > UMBRAL_HUM
            alerta      = alerta_temp
            led.value(1 if alerta_temp else 0)

            pct_temp  = int(max(0, min(100, (temp  - 18) / 20 * 100)))
            pct_hum   = int(max(0, min(100, (hum   - 40) / 45 * 100)))
            pct_press = int(max(0, min(100, (press - 1005) / 20 * 100)))
            pct_heat  = int(max(0, min(100, (hi    - 18) / 22 * 100)))

            # FIX S3: sin Access-Control-Allow-Origin: *
            json_resp = ('HTTP/1.1 200 OK\r\n'
                         'Content-Type: application/json\r\n\r\n'
                         '{{"temp":{t},"hum":{h},"press":{p},"hi":{hi},'
                         '"alerta_temp":{at},"alerta_hum":{ah},"alerta":{a},'
                         '"pct_temp":{pt},"pct_hum":{ph},'
                         '"pct_press":{pp},"pct_heat":{pheat}}}'
                         ).format(
                             t=temp, h=hum, p=press, hi=hi,
                             at='true' if alerta_temp else 'false',
                             ah='true' if alerta_hum  else 'false',
                             a ='true' if alerta       else 'false',
                             pt=pct_temp, ph=pct_hum,
                             pp=pct_press, pheat=pct_heat
                         )
            cl.send(json_resp)

        else:
            # FIX S2: proteger también la página principal
            if not check_auth(req):
                cl.send(RESP_401)
                cl.close()
                gc.collect()   # FIX T3
                continue
            cl.send(HTML)

        cl.close()
        gc.collect()   # FIX T3: liberar memoria después de cada petición

    except OSError:
        pass
    except Exception as e:
        print("Error:", e)
        try:
            cl.close()
        except:
            pass
        gc.collect()   # FIX T3: también en caso de error
