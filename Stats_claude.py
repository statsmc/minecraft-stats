import paramiko
import json
import hashlib
import re
import os
import base64
from datetime import datetime

# ================= CONFIG =================
CONFIG_FILE = "config.json"
OUTPUT_HTML = "stats_panel_ultra.html"
TOP_LIMIT = 100

# ================= UTILS =================
def offline_uuid(name):
    base = ("OfflinePlayer:" + name).encode("utf-8")
    return hashlib.md5(base).hexdigest()

def ticks_to_time(ticks):
    seconds = ticks // 20
    # Calculamos el total de horas directamente
    hours = seconds // 3600
    # Calculamos los minutos restantes
    minutes = (seconds % 3600) // 60
    
    return f"{hours}h {minutes}m"
    
    if days > 0:
        return f"{days}d {hours}h {minutes}m"
    elif hours > 0:
        return f"{hours}h {minutes}m"
    else:
        return f"{minutes}m"

def cm_to_readable(cm):
    """Convierte cm a la unidad más legible"""
    meters = int(cm) / 100
    if meters >= 1000:
        return f"{meters/1000:.2f}"
    else:
        return f"{meters:.0f}"

def damage_to_hearts(damage):
    """Convierte daño a corazones"""
    hearts = int(damage) / 2
    return f"{hearts:.1f}"

def sum_values(d):
    try:
        return sum(int(v) for v in d.values())
    except:
        return 0

def clean_stat(name):
    """Traduce nombres de estadísticas"""
    translate = {
        "total_blocks": "Bloques Minados",
        "total_killed": "Criaturas Eliminadas",
        "deaths": "Muertes",
        "jumps": "Saltos",
        "time_txt": "Tiempo Jugado",
        "minecraft:walk_one_cm": "Caminada",
        "minecraft:sprint_one_cm": "Corriendo",
        "minecraft:crouch_one_cm": "Agachado",
        "minecraft:fly_one_cm": "Volando",
        "minecraft:swim_one_cm": "Nadando",
        "minecraft:aviate_one_cm": "Con Elytra",
        "minecraft:boat_one_cm": "En Bote",
        "minecraft:minecart_one_cm": "En Vagoneta",
        "minecraft:horse_one_cm": "A Caballo",
        "minecraft:mob_kills": "Criaturas Eliminadas",
        "minecraft:player_kills": "Jugadores Eliminados",
        "minecraft:damage_dealt": "Daño Infligido",
        "minecraft:damage_taken": "Daño Recibido",
        "minecraft:damage_blocked_by_shield": "Daño Bloqueado",
        "minecraft:jump": "Saltos",
        "minecraft:leave_game": "Desconexiones",
        "minecraft:interact_with_crafting_table": "Crafteos",
        "minecraft:interact_with_furnace": "Hornos Usados",
        "minecraft:open_chest": "Cofres Abiertos",
        "minecraft:open_enderchest": "Cofres de Ender",
        "minecraft:trade_with_villager": "Intercambios",
        "minecraft:animals_bred": "Animales Criados",
        "minecraft:fish_caught": "Peces Pescados",
    }
    return translate.get(name, name.replace("minecraft:", "").replace("_", " ").title())

def format_stat_value(key, value):
    """Formatea valores"""
    distance_stats = [
        "minecraft:walk_one_cm", "minecraft:sprint_one_cm", "minecraft:crouch_one_cm",
        "minecraft:fly_one_cm", "minecraft:swim_one_cm", "minecraft:aviate_one_cm",
        "minecraft:boat_one_cm", "minecraft:minecart_one_cm", "minecraft:horse_one_cm"
    ]
    
    damage_stats = [
        "minecraft:damage_dealt", "minecraft:damage_taken", "minecraft:damage_blocked_by_shield"
    ]
    
    if key in distance_stats:
        return cm_to_readable(value)
    elif key in damage_stats:
        return damage_to_hearts(value)
    else:
        try:
            return f"{int(value):,}".replace(",", ".")
        except:
            return str(value)

def get_unit(key):
    """Obtiene la unidad de una estadística"""
    distance_stats = [
        "minecraft:walk_one_cm", "minecraft:sprint_one_cm", "minecraft:crouch_one_cm",
        "minecraft:fly_one_cm", "minecraft:swim_one_cm", "minecraft:aviate_one_cm",
        "minecraft:boat_one_cm", "minecraft:minecart_one_cm", "minecraft:horse_one_cm"
    ]
    
    damage_stats = ["minecraft:damage_dealt", "minecraft:damage_taken", "minecraft:damage_blocked_by_shield"]
    
    if key in distance_stats:
        return "km"
    elif key in damage_stats:
        return "❤"
    else:
        return ""

# ================= BOT DETECTION =================
def is_bot(p):
    """Detección mejorada de bots"""
    ticks = p["ticks"]
    blocks = p["total_blocks"]
    kills = p["total_killed"]
    jumps = p["jumps"]
    deaths = p["deaths"]
    
    walk = int(p["extras"].get("minecraft:walk_one_cm", 0))
    sprint = int(p["extras"].get("minecraft:sprint_one_cm", 0))
    sneak = int(p["extras"].get("minecraft:sneak_time", 0))
    leaves = int(p["extras"].get("minecraft:leave_game", 0))
    crafted = int(p["extras"].get("minecraft:interact_with_crafting_table", 0))
    chests = int(p["extras"].get("minecraft:open_chest", 0))
    
    score = 0
    
    if ticks < 1200: score += 4
    if walk < 500 and sprint < 200: score += 3
    if blocks == 0 and kills == 0 and crafted == 0: score += 3
    if jumps == 0 and ticks > 600: score += 3
    
    name_lower = p["name"].lower()
    bot_patterns = [
        r"^(bot|npc|test|debug|dummy|fake|afk)",
        r"(bot|npc|test|afk)$",
        r"^player[_-]?\d+$",
        r"^[0-9a-f]{8,}$",
        r"^(admin|mod|helper|server)(bot|_bot|-bot)",
        r"^\d+$",
    ]
    
    for pattern in bot_patterns:
        if re.match(pattern, name_lower):
            score += 5
            break
    
    if ticks > 20000 and blocks < 10 and kills < 5 and jumps < 100: score += 4
    if ticks > 6000:
        total_actions = blocks + kills + jumps + crafted + chests
        if total_actions < 5: score += 3
    
    if walk > 10000:
        action_count = blocks + kills + jumps + crafted
        if action_count < 15: score += 3
    
    if leaves > 10 and ticks < 72000: score += 3
    elif leaves > 5 and ticks < 36000: score += 2
    
    if sneak == 0 and ticks > 12000: score += 2
    if deaths == 0 and ticks > 72000:
        if blocks < 100 and kills < 20: score += 3
    
    if chests == 0 and crafted == 0 and ticks > 18000: score += 2
    if blocks < 3 and kills < 2 and jumps < 10 and ticks > 3600: score += 3
    
    return score >= 7

# ================= LOAD CONFIG =================
# Intenta leer de variables de entorno (GitHub), si no existen, usa el JSON (Local)
HOST = os.getenv("MC_HOST")
PORT = os.getenv("MC_PORT")
USER = os.getenv("MC_USER")
PASS = os.getenv("MC_PASS")
WORLD = os.getenv("MC_WORLD", "/world")

# Si no hay variables de entorno (caso de ejecución local), intenta cargar el JSON
if not all([HOST, USER, PASS]):
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, encoding="utf-8") as f:
            config = json.load(f)
            HOST = config.get("host")
            PORT = config.get("port")
            USER = config.get("user")
            PASS = config.get("pass")
            WORLD = config.get("world", "/world")
    else:
        print("❌ ERROR: No se encontraron credenciales en Environment ni en config.json")
        exit(1)

# Asegurar que el puerto sea un entero
PORT = int(PORT) if PORT else 22
STATS_FOLDER = WORLD.rstrip("/") + "/stats"
SKINRESTORER_FOLDER = WORLD.rstrip("/") + "/skinrestorer"

# ================= CONNECT SFTP =================
print(f"🔗 Conectando a {HOST}...")

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, port=PORT, username=USER, password=PASS, timeout=15)

sftp = ssh.open_sftp()

# ================= LOAD SKINRESTORER =================
print("🎨 Cargando texturas de SkinRestorer...")
skin_textures = {}

try:
    sftp.chdir(SKINRESTORER_FOLDER)
    for fname in sftp.listdir():
        if not fname.endswith(".json"):
            continue
        
        uuid = fname[:-5]
        try:
            with sftp.open(fname) as f:
                skin_data = json.load(f)
                
            if "value" in skin_data and "value" in skin_data["value"]:
                texture_data = base64.b64decode(skin_data["value"]["value"]).decode('utf-8')
                texture_json = json.loads(texture_data)
                
                if "textures" in texture_json and "SKIN" in texture_json["textures"]:
                    skin_url = texture_json["textures"]["SKIN"]["url"]
                    texture_hash = skin_url.split("/")[-1]
                    skin_textures[uuid.replace("-", "")] = texture_hash
        except:
            continue
    
    print(f"✅ {len(skin_textures)} texturas cargadas")
except Exception as e:
    print(f"⚠️ No se pudo cargar SkinRestorer: {e}")

# ================= UUID → NAME =================
uuid_to_name = {}

def try_json(path):
    try:
        with sftp.open(path) as f:
            return json.load(f)
    except:
        return None

print("📝 Cargando nombres...")

uc = try_json("/usercache.json")
if uc:
    for e in uc:
        uuid_to_name[e["uuid"].replace("-", "")] = e["name"]

for path in ["/ops.json", "/whitelist.json", "/banned-players.json"]:
    data = try_json(path)
    if data:
        for e in data:
            if "uuid" in e and "name" in e:
                uuid_to_name[e["uuid"].replace("-", "")] = e["name"]

# ================= READ STATS =================
print("📊 Leyendo estadísticas...")
players = []

try:
    sftp.chdir(STATS_FOLDER)
except:
    print("❌ ERROR: carpeta stats no encontrada")
    exit()

for fname in sftp.listdir():
    if not fname.endswith(".json"):
        continue

    uuid = fname[:-5]
    name = uuid_to_name.get(uuid.replace("-", ""), uuid)

    try:
        with sftp.open(fname) as f:
            stats_data = json.load(f)
    except:
        continue

    s = stats_data.get("stats", {})
    mined = s.get("minecraft:mined", {}) or {}
    killed = s.get("minecraft:killed", {}) or {}
    custom = s.get("minecraft:custom", {}) or {}

    total_blocks = sum_values(mined)
    total_killed = sum_values(killed) + int(custom.get("minecraft:mob_kills", 0))
    deaths = int(custom.get("minecraft:deaths", 0))
    jumps = int(custom.get("minecraft:jump", 0))
    ticks = int(custom.get("minecraft:play_time", 0))
    time_txt = ticks_to_time(ticks)

    extras = {}
    for k, v in custom.items():
        if k not in ("minecraft:deaths", "minecraft:jump", "minecraft:play_time"):
            extras[k] = v

    players.append({
        "uuid": uuid,
        "name": name,
        "total_blocks": total_blocks,
        "total_killed": total_killed,
        "deaths": deaths,
        "jumps": jumps,
        "ticks": ticks,
        "time_txt": time_txt,
        "extras": extras
    })

sftp.close()
ssh.close()

print(f"✅ {len(players)} jugadores encontrados")

# ================= CLASSIFY =================
print("🤖 Detectando bots...")
real = []
bots = []

for p in players:
    if is_bot(p):
        bots.append(p)
    else:
        real.append(p)

real.sort(key=lambda x: x["ticks"], reverse=True)
bots.sort(key=lambda x: x["ticks"], reverse=True)

real = real[:TOP_LIMIT]
bots = bots[:TOP_LIMIT]

print(f"👥 Jugadores reales: {len(real)}")
print(f"🤖 Bots detectados: {len(bots)}")

# ================= CALCULATE AGGREGATES =================
def calculate_aggregates(lst):
    """Calcula estadísticas agregadas del servidor"""
    total_time = sum(p["ticks"] for p in lst)
    total_blocks = sum(p["total_blocks"] for p in lst)
    total_kills = sum(p["total_killed"] for p in lst)
    total_deaths = sum(p["deaths"] for p in lst)
    
    # Distancia total
    total_distance = 0
    for p in lst:
        for key in ["minecraft:walk_one_cm", "minecraft:sprint_one_cm", "minecraft:fly_one_cm", 
                    "minecraft:swim_one_cm", "minecraft:aviate_one_cm"]:
            total_distance += int(p["extras"].get(key, 0))
    
    total_distance_km = total_distance / 100000
    
    return {
        "total_time": ticks_to_time(total_time),
        "total_blocks": f"{total_blocks:,}".replace(",", "."),
        "total_kills": f"{total_kills:,}".replace(",", "."),
        "total_deaths": f"{total_deaths:,}".replace(",", "."),
        "total_distance": f"{total_distance_km:,.0f}".replace(",", "."),
        "player_count": len(lst),
        "avg_time": ticks_to_time(total_time // len(lst)) if lst else "0m"
    }

server_stats = calculate_aggregates(real)

# ================= HTML BUILD =================
def get_skin_url(uuid, name, size=80):
    """Obtiene la URL de la skin"""
    uuid_clean = uuid.replace("-", "")
    if uuid_clean in skin_textures:
        return f"https://mc-heads.net/avatar/{skin_textures[uuid_clean]}/{size}"
    else:
        return f"https://mc-heads.net/avatar/{name}/{size}"

# Convertir datos a JSON para JavaScript
players_json = json.dumps([{
    "uuid": p["uuid"],
    "name": p["name"],
    "skin": get_skin_url(p["uuid"], p["name"], 80),
    "time_txt": p["time_txt"],
    "ticks": p["ticks"],
    "blocks": p["total_blocks"],
    "kills": p["total_killed"],
    "deaths": p["deaths"],
    "jumps": p["jumps"],
    "extras": p["extras"]
} for p in real])

bots_json = json.dumps([{
    "uuid": p["uuid"],
    "name": p["name"],
    "skin": get_skin_url(p["uuid"], p["name"], 80),
    "time_txt": p["time_txt"],
    "ticks": p["ticks"],
    "blocks": p["total_blocks"],
    "kills": p["total_killed"],
    "deaths": p["deaths"],
    "jumps": p["jumps"],
    "extras": p["extras"]
} for p in bots])

now = datetime.now().strftime("%d/%m/%Y %H:%M")

html = f"""
<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Minecraft Stats - Ultra Premium Dashboard</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap" rel="stylesheet">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
<style>
* {{
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}}

:root {{
    --bg-primary: #0a0a0f;
    --bg-secondary: #13131a;
    --bg-tertiary: #1a1a24;
    --bg-elevated: #20202d;
    
    --text-primary: #ffffff;
    --text-secondary: #a8a8b8;
    --text-tertiary: #6b6b7e;
    
    --accent-primary: #6366f1;
    --accent-secondary: #8b5cf6;
    --accent-gradient: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
    
    --success: #10b981;
    --warning: #f59e0b;
    --error: #ef4444;
    
    --border-subtle: rgba(255, 255, 255, 0.06);
    --border-medium: rgba(255, 255, 255, 0.1);
    
    --shadow-sm: 0 1px 2px rgba(0, 0, 0, 0.3);
    --shadow-md: 0 4px 12px rgba(0, 0, 0, 0.4);
    --shadow-lg: 0 12px 40px rgba(0, 0, 0, 0.5);
    --shadow-glow: 0 0 24px rgba(99, 102, 241, 0.3);
    
    --radius-sm: 8px;
    --radius-md: 12px;
    --radius-lg: 16px;
    --radius-xl: 24px;
    
    --transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}}

body {{
    background: var(--bg-primary);
    color: var(--text-primary);
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    font-size: 15px;
    line-height: 1.6;
    -webkit-font-smoothing: antialiased;
    -moz-osx-font-smoothing: grayscale;
    overflow-x: hidden;
}}

.app {{
    min-height: 100vh;
}}

/* Hero Header */
.hero {{
    position: relative;
    background: var(--bg-secondary);
    padding: 60px 24px 80px;
    overflow: hidden;
}}

.hero::before {{
    content: '';
    position: absolute;
    inset: 0;
    background: var(--accent-gradient);
    opacity: 0.05;
    z-index: 0;
}}

.hero::after {{
    content: '';
    position: absolute;
    top: 0;
    left: 50%;
    transform: translateX(-50%);
    width: 800px;
    height: 400px;
    background: radial-gradient(circle, rgba(99, 102, 241, 0.15) 0%, transparent 70%);
    z-index: 0;
}}

.hero-content {{
    position: relative;
    z-index: 1;
    max-width: 1400px;
    margin: 0 auto;
}}

.hero-title {{
    font-size: 56px;
    font-weight: 800;
    text-align: center;
    margin-bottom: 16px;
    background: var(--accent-gradient);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    letter-spacing: -0.03em;
}}

.hero-subtitle {{
    text-align: center;
    font-size: 18px;
    color: var(--text-secondary);
    margin-bottom: 8px;
    font-weight: 400;
}}

.hero-timestamp {{
    text-align: center;
    font-size: 13px;
    color: var(--text-tertiary);
    font-weight: 500;
}}

/* Server Stats Bar */
.server-stats {{
    max-width: 1400px;
    margin: -40px auto 0;
    padding: 0 24px;
    position: relative;
    z-index: 2;
}}

.stats-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 16px;
    background: var(--bg-tertiary);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-xl);
    padding: 24px;
    box-shadow: var(--shadow-lg);
}}

.stat-item {{
    text-align: center;
    padding: 16px;
}}

.stat-value {{
    font-size: 32px;
    font-weight: 700;
    color: var(--text-primary);
    margin-bottom: 4px;
    letter-spacing: -0.02em;
}}

.stat-label {{
    font-size: 13px;
    color: var(--text-tertiary);
    text-transform: uppercase;
    letter-spacing: 0.05em;
    font-weight: 600;
}}

/* Main Container */
.container {{
    max-width: 1400px;
    margin: 0 auto;
    padding: 40px 24px;
}}

/* Search & Filters */
.controls {{
    margin-bottom: 32px;
}}

.search-wrapper {{
    position: relative;
    margin-bottom: 24px;
}}

.search-input {{
    width: 100%;
    background: var(--bg-secondary);
    border: 1px solid var(--border-medium);
    border-radius: var(--radius-lg);
    padding: 16px 52px 16px 52px;
    font-size: 16px;
    color: var(--text-primary);
    font-family: inherit;
    transition: var(--transition);
    outline: none;
}}

.search-input:focus {{
    border-color: var(--accent-primary);
    box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.1);
}}

.search-input::placeholder {{
    color: var(--text-tertiary);
}}

.search-icon {{
    position: absolute;
    left: 18px;
    top: 50%;
    transform: translateY(-50%);
    color: var(--text-tertiary);
    font-size: 18px;
    pointer-events: none;
}}

.clear-search {{
    position: absolute;
    right: 16px;
    top: 50%;
    transform: translateY(-50%);
    background: none;
    border: none;
    color: var(--text-tertiary);
    cursor: pointer;
    padding: 8px;
    border-radius: var(--radius-sm);
    transition: var(--transition);
    display: none;
}}

.clear-search:hover {{
    color: var(--text-primary);
    background: var(--bg-tertiary);
}}

.clear-search.visible {{
    display: block;
}}

/* Filter Tabs */
.filter-tabs {{
    display: flex;
    gap: 12px;
    flex-wrap: wrap;
}}

.tab-btn {{
    background: var(--bg-secondary);
    border: 1px solid var(--border-subtle);
    color: var(--text-secondary);
    padding: 10px 20px;
    border-radius: var(--radius-lg);
    font-size: 14px;
    font-weight: 600;
    cursor: pointer;
    transition: var(--transition);
    font-family: inherit;
}}

.tab-btn:hover {{
    border-color: var(--border-medium);
    background: var(--bg-tertiary);
}}

.tab-btn.active {{
    background: var(--accent-gradient);
    border-color: transparent;
    color: white;
    box-shadow: var(--shadow-glow);
}}

/* Section Header */
.section-header {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin: 48px 0 24px;
}}

.section-title {{
    display: flex;
    align-items: center;
    gap: 12px;
    font-size: 24px;
    font-weight: 700;
    color: var(--text-primary);
}}

.section-count {{
    background: var(--bg-tertiary);
    border: 1px solid var(--border-subtle);
    padding: 4px 12px;
    border-radius: var(--radius-lg);
    font-size: 14px;
    font-weight: 600;
    color: var(--text-secondary);
}}

/* Player Grid */
.player-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
    gap: 16px;
    margin-bottom: 40px;
}}

.player-card {{
    background: var(--bg-secondary);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-lg);
    padding: 20px;
    cursor: pointer;
    transition: var(--transition);
    position: relative;
    overflow: hidden;
}}

.player-card::before {{
    content: '';
    position: absolute;
    inset: 0;
    background: var(--accent-gradient);
    opacity: 0;
    transition: opacity 0.3s;
    pointer-events: none;
}}

.player-card:hover {{
    transform: translateY(-4px);
    border-color: var(--accent-primary);
    box-shadow: var(--shadow-md);
}}

.player-card:hover::before {{
    opacity: 0.05;
}}

.player-card-content {{
    position: relative;
    z-index: 1;
}}

.rank-badge {{
    position: absolute;
    top: 16px;
    right: 16px;
    background: var(--bg-tertiary);
    border: 1px solid var(--border-subtle);
    padding: 4px 10px;
    border-radius: var(--radius-md);
    font-size: 12px;
    font-weight: 700;
    color: var(--text-secondary);
}}

.player-header {{
    display: flex;
    align-items: center;
    gap: 16px;
    margin-bottom: 16px;
}}

.player-avatar {{
    width: 64px;
    height: 64px;
    border-radius: var(--radius-md);
    image-rendering: pixelated;
    box-shadow: var(--shadow-sm);
}}

.player-info {{
    flex: 1;
}}

.player-name {{
    font-size: 18px;
    font-weight: 700;
    color: var(--text-primary);
    margin-bottom: 4px;
}}

.player-time {{
    font-size: 14px;
    color: var(--text-tertiary);
    font-weight: 500;
}}

.player-stats-mini {{
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 12px;
}}

.stat-mini {{
    text-align: center;
    padding: 8px;
    background: var(--bg-tertiary);
    border-radius: var(--radius-sm);
}}

.stat-mini-value {{
    font-size: 16px;
    font-weight: 700;
    color: var(--text-primary);
    margin-bottom: 2px;
}}

.stat-mini-label {{
    font-size: 11px;
    color: var(--text-tertiary);
    text-transform: uppercase;
    letter-spacing: 0.05em;
    font-weight: 600;
}}

/* Profile Modal */
.profile-modal {{
    display: none;
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.8);
    backdrop-filter: blur(8px);
    z-index: 1000;
    overflow-y: auto;
    padding: 40px 20px;
}}

.profile-modal.active {{
    display: block;
    animation: fadeIn 0.3s ease;
}}

@keyframes fadeIn {{
    from {{ opacity: 0; }}
    to {{ opacity: 1; }}
}}

.profile-content {{
    max-width: 1000px;
    margin: 0 auto;
    background: var(--bg-secondary);
    border: 1px solid var(--border-medium);
    border-radius: var(--radius-xl);
    padding: 40px;
    box-shadow: var(--shadow-lg);
    animation: slideUp 0.3s ease;
}}

@keyframes slideUp {{
    from {{
        opacity: 0;
        transform: translateY(40px);
    }}
    to {{
        opacity: 1;
        transform: translateY(0);
    }}
}}

.profile-close {{
    position: absolute;
    top: 24px;
    right: 24px;
    background: var(--bg-tertiary);
    border: 1px solid var(--border-subtle);
    width: 40px;
    height: 40px;
    border-radius: var(--radius-md);
    color: var(--text-secondary);
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 20px;
    transition: var(--transition);
}}

.profile-close:hover {{
    background: var(--bg-elevated);
    color: var(--text-primary);
}}

.profile-hero {{
    display: flex;
    align-items: center;
    gap: 32px;
    margin-bottom: 40px;
    padding-bottom: 32px;
    border-bottom: 1px solid var(--border-subtle);
}}

.profile-avatar {{
    width: 128px;
    height: 128px;
    border-radius: var(--radius-lg);
    image-rendering: pixelated;
    box-shadow: var(--shadow-md);
}}

.profile-meta h1 {{
    font-size: 36px;
    font-weight: 800;
    margin-bottom: 8px;
    background: var(--accent-gradient);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
}}

.profile-uuid {{
    font-size: 13px;
    color: var(--text-tertiary);
    font-family: 'Courier New', monospace;
    letter-spacing: 0.05em;
}}

/* Stat Cards Large */
.stat-cards-large {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
    gap: 16px;
    margin-bottom: 32px;
}}

.stat-card-large {{
    background: var(--bg-tertiary);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-lg);
    padding: 24px;
    transition: var(--transition);
}}

.stat-card-large:hover {{
    border-color: var(--border-medium);
    transform: translateY(-2px);
}}

.stat-card-icon {{
    width: 48px;
    height: 48px;
    border-radius: var(--radius-md);
    background: var(--accent-gradient);
    display: flex;
    align-items: center;
    justify-content: center;
    margin-bottom: 16px;
    font-size: 24px;
}}

.stat-card-value {{
    font-size: 32px;
    font-weight: 800;
    color: var(--text-primary);
    margin-bottom: 4px;
    letter-spacing: -0.02em;
}}

.stat-card-label {{
    font-size: 14px;
    color: var(--text-tertiary);
    font-weight: 600;
}}

/* Category Sections */
.category-section {{
    margin-bottom: 32px;
}}

.category-header {{
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 20px;
    padding-bottom: 12px;
    border-bottom: 1px solid var(--border-subtle);
}}

.category-icon {{
    width: 32px;
    height: 32px;
    border-radius: var(--radius-sm);
    background: var(--accent-gradient);
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 16px;
}}

.category-title {{
    font-size: 20px;
    font-weight: 700;
    color: var(--text-primary);
}}

.category-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
    gap: 12px;
}}

.stat-row {{
    background: var(--bg-tertiary);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-md);
    padding: 16px 20px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    transition: var(--transition);
}}

.stat-row:hover {{
    border-color: var(--border-medium);
    background: var(--bg-elevated);
}}

.stat-row-label {{
    font-size: 15px;
    color: var(--text-secondary);
    font-weight: 500;
}}

.stat-row-value {{
    font-size: 18px;
    font-weight: 700;
    color: var(--text-primary);
    display: flex;
    align-items: baseline;
    gap: 6px;
}}

.stat-unit {{
    font-size: 13px;
    color: var(--text-tertiary);
    font-weight: 600;
}}

/* Empty State */
.empty-state {{
    text-align: center;
    padding: 80px 32px;
    background: var(--bg-secondary);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-xl);
}}

.empty-icon {{
    font-size: 64px;
    color: var(--text-tertiary);
    margin-bottom: 16px;
    opacity: 0.5;
}}

.empty-text {{
    font-size: 18px;
    color: var(--text-secondary);
}}

/* Responsive */
@media (max-width: 768px) {{
    .hero-title {{
        font-size: 36px;
    }}
    
    .stats-grid {{
        grid-template-columns: repeat(2, 1fr);
    }}
    
    .player-grid {{
        grid-template-columns: 1fr;
    }}
    
    .profile-content {{
        padding: 24px;
    }}
    
    .profile-hero {{
        flex-direction: column;
        text-align: center;
    }}
    
    .stat-cards-large {{
        grid-template-columns: 1fr;
    }}
    
    .category-grid {{
        grid-template-columns: 1fr;
    }}
}}

/* Scrollbar */
::-webkit-scrollbar {{
    width: 12px;
}}

::-webkit-scrollbar-track {{
    background: var(--bg-primary);
}}

::-webkit-scrollbar-thumb {{
    background: var(--bg-elevated);
    border-radius: 6px;
    border: 2px solid var(--bg-primary);
}}

::-webkit-scrollbar-thumb:hover {{
    background: var(--accent-primary);
}}
</style>
</head>
<body>

<div class="app">
    <!-- Hero -->
    <div class="hero">
        <div class="hero-content">
            <h1 class="hero-title">⛏️ Minecraft Stats</h1>
            <p class="hero-subtitle">Panel Ultra Premium de Estadísticas</p>
            <p class="hero-timestamp">Actualizado: {now}</p>
        </div>
    </div>

    <!-- Server Stats -->
    <div class="server-stats">
        <div class="stats-grid">
            <div class="stat-item">
                <div class="stat-value">{server_stats['player_count']}</div>
                <div class="stat-label">Jugadores</div>
            </div>
            <div class="stat-item">
                <div class="stat-value">{server_stats['total_time']}</div>
                <div class="stat-label">Tiempo Total</div>
            </div>
            <div class="stat-item">
                <div class="stat-value">{server_stats['total_blocks']}</div>
                <div class="stat-label">Bloques Minados</div>
            </div>
            <div class="stat-item">
                <div class="stat-value">{server_stats['total_distance']}</div>
                <div class="stat-label">Kilómetros</div>
            </div>
            <div class="stat-item">
                <div class="stat-value">{server_stats['total_kills']}</div>
                <div class="stat-label">Criaturas</div>
            </div>
            <div class="stat-item">
                <div class="stat-value">{server_stats['avg_time']}</div>
                <div class="stat-label">Promedio/Jugador</div>
            </div>
        </div>
    </div>

    <!-- Main Container -->
    <div class="container">
        <!-- Search & Controls -->
        <div class="controls">
            <div class="search-wrapper">
                <i class="fas fa-search search-icon"></i>
                <input type="text" class="search-input" id="searchInput" placeholder="Buscar jugadores...">
                <button class="clear-search" id="clearSearch">
                    <i class="fas fa-times"></i>
                </button>
            </div>
            
            <div class="filter-tabs">
                <button class="tab-btn active" data-tab="all">
                    <i class="fas fa-users"></i> Todos
                </button>
                <button class="tab-btn" data-tab="players">
                    <i class="fas fa-user"></i> Jugadores
                </button>
                <button class="tab-btn" data-tab="bots">
                    <i class="fas fa-robot"></i> Bots
                </button>
            </div>
        </div>

        <!-- Players Section -->
        <div class="section-header">
            <div class="section-title">
                <i class="fas fa-trophy"></i>
                <span>Jugadores</span>
            </div>
            <div class="section-count" id="playerCount">{len(real)}</div>
        </div>
        <div class="player-grid" id="playersGrid"></div>

        <!-- Bots Section -->
        <div class="section-header">
            <div class="section-title">
                <i class="fas fa-robot"></i>
                <span>Bots Detectados</span>
            </div>
            <div class="section-count" id="botCount">{len(bots)}</div>
        </div>
        <div class="player-grid" id="botsGrid"></div>
    </div>
</div>

<!-- Profile Modal -->
<div class="profile-modal" id="profileModal">
    <div class="profile-content" style="position: relative;">
        <button class="profile-close" onclick="closeProfile()">
            <i class="fas fa-times"></i>
        </button>
        <div id="profileData"></div>
    </div>
</div>

<script>
const playersData = {players_json};
const botsData = {bots_json};
let currentFilter = 'all';
let searchQuery = '';

// Renderizar tarjetas
function renderCards(data, containerId) {{
    const container = document.getElementById(containerId);
    if (!data || data.length === 0) {{
        container.innerHTML = `
            <div class="empty-state">
                <div class="empty-icon"><i class="fas fa-inbox"></i></div>
                <div class="empty-text">No se encontraron jugadores</div>
            </div>
        `;
        return;
    }}
    
    container.innerHTML = data.map((player, index) => {{
        const rank = index === 0 ? '🥇' : index === 1 ? '🥈' : index === 2 ? '🥉' : `#${{index + 1}}`;
        return `
            <div class="player-card" onclick="openProfile('${{player.uuid}}', ${{containerId === 'botsGrid'}})">
                <div class="player-card-content">
                    <div class="rank-badge">${{rank}}</div>
                    <div class="player-header">
                        <img src="${{player.skin}}" alt="${{player.name}}" class="player-avatar">
                        <div class="player-info">
                            <div class="player-name">${{player.name}}</div>
                            <div class="player-time">
                                <i class="fas fa-clock"></i> ${{player.time_txt}}
                            </div>
                        </div>
                    </div>
                    <div class="player-stats-mini">
                        <div class="stat-mini">
                            <div class="stat-mini-value">${{player.blocks.toLocaleString('es-ES')}}</div>
                            <div class="stat-mini-label">Bloques</div>
                        </div>
                        <div class="stat-mini">
                            <div class="stat-mini-value">${{player.kills}}</div>
                            <div class="stat-mini-label">Kills</div>
                        </div>
                        <div class="stat-mini">
                            <div class="stat-mini-value">${{player.deaths}}</div>
                            <div class="stat-mini-label">Muertes</div>
                        </div>
                    </div>
                </div>
            </div>
        `;
    }}).join('');
}}

// Filtrar datos
function filterData() {{
    let filteredPlayers = playersData;
    let filteredBots = botsData;
    
    if (searchQuery) {{
        filteredPlayers = playersData.filter(p => 
            p.name.toLowerCase().includes(searchQuery.toLowerCase())
        );
        filteredBots = botsData.filter(p => 
            p.name.toLowerCase().includes(searchQuery.toLowerCase())
        );
    }}
    
    if (currentFilter === 'players') {{
        renderCards(filteredPlayers, 'playersGrid');
        document.getElementById('botsGrid').innerHTML = '';
    }} else if (currentFilter === 'bots') {{
        renderCards(filteredBots, 'botsGrid');
        document.getElementById('playersGrid').innerHTML = '';
    }} else {{
        renderCards(filteredPlayers, 'playersGrid');
        renderCards(filteredBots, 'botsGrid');
    }}
    
    document.getElementById('playerCount').textContent = filteredPlayers.length;
    document.getElementById('botCount').textContent = filteredBots.length;
}}

// Búsqueda
const searchInput = document.getElementById('searchInput');
const clearSearch = document.getElementById('clearSearch');

searchInput.addEventListener('input', (e) => {{
    searchQuery = e.target.value;
    clearSearch.classList.toggle('visible', searchQuery.length > 0);
    filterData();
}});

clearSearch.addEventListener('click', () => {{
    searchInput.value = '';
    searchQuery = '';
    clearSearch.classList.remove('visible');
    filterData();
}});

// Filtros
document.querySelectorAll('.tab-btn').forEach(btn => {{
    btn.addEventListener('click', () => {{
        document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        currentFilter = btn.dataset.tab;
        filterData();
    }});
}});

// Abrir perfil
function openProfile(uuid, isBot) {{
    const player = isBot ? 
        botsData.find(p => p.uuid === uuid) : 
        playersData.find(p => p.uuid === uuid);
    
    if (!player) return;
    
    // Calcular distancia total
    const distances = [
        'minecraft:walk_one_cm', 'minecraft:sprint_one_cm', 'minecraft:fly_one_cm',
        'minecraft:swim_one_cm', 'minecraft:aviate_one_cm'
    ];
    let totalDistance = 0;
    distances.forEach(key => {{
        totalDistance += parseInt(player.extras[key] || 0);
    }});
    const distanceKm = (totalDistance / 100000).toFixed(2);
    
    // Daño total
    const damageDealt = (parseInt(player.extras['minecraft:damage_dealt'] || 0) / 2).toFixed(1);
    const damageTaken = (parseInt(player.extras['minecraft:damage_taken'] || 0) / 2).toFixed(1);
    
    let categoriesHtml = '';
    
    // Movimiento
    const movementStats = [
        {{ key: 'minecraft:walk_one_cm', label: 'Caminada', icon: 'walking' }},
        {{ key: 'minecraft:sprint_one_cm', label: 'Corriendo', icon: 'running' }},
        {{ key: 'minecraft:fly_one_cm', label: 'Volando', icon: 'wind' }},
        {{ key: 'minecraft:swim_one_cm', label: 'Nadando', icon: 'person-swimming' }},
        {{ key: 'minecraft:aviate_one_cm', label: 'Con Elytra', icon: 'jet-fighter' }}
    ];
    
    let movementHtml = '';
    movementStats.forEach(stat => {{
        const value = parseInt(player.extras[stat.key] || 0);
        if (value > 0) {{
            const km = (value / 100000).toFixed(2);
            movementHtml += `
                <div class="stat-row">
                    <span class="stat-row-label">${{stat.label}}</span>
                    <span class="stat-row-value">${{km}} <span class="stat-unit">km</span></span>
                </div>
            `;
        }}
    }});
    
    if (movementHtml) {{
        categoriesHtml += `
            <div class="category-section">
                <div class="category-header">
                    <div class="category-icon"><i class="fas fa-person-running"></i></div>
                    <h3 class="category-title">Movimiento</h3>
                </div>
                <div class="category-grid">${{movementHtml}}</div>
            </div>
        `;
    }}
    
    // Combate
    const combatStats = [
        {{ key: 'minecraft:mob_kills', label: 'Criaturas Eliminadas' }},
        {{ key: 'minecraft:player_kills', label: 'Jugadores Eliminados' }},
        {{ key: 'minecraft:damage_dealt', label: 'Daño Infligido', unit: '❤' }},
        {{ key: 'minecraft:damage_taken', label: 'Daño Recibido', unit: '❤' }},
        {{ key: 'minecraft:damage_blocked_by_shield', label: 'Daño Bloqueado', unit: '❤' }}
    ];
    
    let combatHtml = '';
    combatStats.forEach(stat => {{
        const value = parseInt(player.extras[stat.key] || 0);
        if (value > 0) {{
            let displayValue = value;
            if (stat.unit === '❤') displayValue = (value / 2).toFixed(1);
            combatHtml += `
                <div class="stat-row">
                    <span class="stat-row-label">${{stat.label}}</span>
                    <span class="stat-row-value">${{displayValue}} <span class="stat-unit">${{stat.unit || ''}}</span></span>
                </div>
            `;
        }}
    }});
    
    if (combatHtml) {{
        categoriesHtml += `
            <div class="category-section">
                <div class="category-header">
                    <div class="category-icon"><i class="fas fa-hand-fist"></i></div>
                    <h3 class="category-title">Combate</h3>
                </div>
                <div class="category-grid">${{combatHtml}}</div>
            </div>
        `;
    }}
    
    // Interacciones
    const interactionStats = [
        {{ key: 'minecraft:interact_with_crafting_table', label: 'Crafteos' }},
        {{ key: 'minecraft:open_chest', label: 'Cofres Abiertos' }},
        {{ key: 'minecraft:trade_with_villager', label: 'Intercambios' }},
        {{ key: 'minecraft:animals_bred', label: 'Animales Criados' }},
        {{ key: 'minecraft:fish_caught', label: 'Peces Pescados' }}
    ];
    
    let interactionHtml = '';
    interactionStats.forEach(stat => {{
        const value = parseInt(player.extras[stat.key] || 0);
        if (value > 0) {{
            interactionHtml += `
                <div class="stat-row">
                    <span class="stat-row-label">${{stat.label}}</span>
                    <span class="stat-row-value">${{value.toLocaleString('es-ES')}}</span>
                </div>
            `;
        }}
    }});
    
    if (interactionHtml) {{
        categoriesHtml += `
            <div class="category-section">
                <div class="category-header">
                    <div class="category-icon"><i class="fas fa-hand-pointer"></i></div>
                    <h3 class="category-title">Interacciones</h3>
                </div>
                <div class="category-grid">${{interactionHtml}}</div>
            </div>
        `;
    }}
    
    document.getElementById('profileData').innerHTML = `
        <div class="profile-hero">
            <img src="${{player.skin.replace('/80', '/128')}}" alt="${{player.name}}" class="profile-avatar">
            <div class="profile-meta">
                <h1>${{player.name}}</h1>
                <p class="profile-uuid">${{player.uuid}}</p>
            </div>
        </div>
        
        <div class="stat-cards-large">
            <div class="stat-card-large">
                <div class="stat-card-icon"><i class="fas fa-clock"></i></div>
                <div class="stat-card-value">${{player.time_txt}}</div>
                <div class="stat-card-label">Tiempo Jugado</div>
            </div>
            <div class="stat-card-large">
                <div class="stat-card-icon"><i class="fas fa-cubes"></i></div>
                <div class="stat-card-value">${{player.blocks.toLocaleString('es-ES')}}</div>
                <div class="stat-card-label">Bloques Minados</div>
            </div>
            <div class="stat-card-large">
                <div class="stat-card-icon"><i class="fas fa-skull"></i></div>
                <div class="stat-card-value">${{player.kills}}</div>
                <div class="stat-card-label">Criaturas Eliminadas</div>
            </div>
            <div class="stat-card-large">
                <div class="stat-card-icon"><i class="fas fa-heart-crack"></i></div>
                <div class="stat-card-value">${{player.deaths}}</div>
                <div class="stat-card-label">Muertes</div>
            </div>
        </div>
        
        ${{categoriesHtml}}
    `;
    
    document.getElementById('profileModal').classList.add('active');
    document.body.style.overflow = 'hidden';
}}

function closeProfile() {{
    document.getElementById('profileModal').classList.remove('active');
    document.body.style.overflow = '';
}}

// Cerrar modal con ESC
document.addEventListener('keydown', (e) => {{
    if (e.key === 'Escape') closeProfile();
}});

// Cerrar modal al hacer clic fuera
document.getElementById('profileModal').addEventListener('click', (e) => {{
    if (e.target.id === 'profileModal') closeProfile();
}});

// Inicializar
filterData();
</script>

</body>
</html>
"""
# Obtener la hora actual de la ejecución
# Usamos el formato Día/Mes/Año Hora:Minuto
ahora = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

# ================= SAVE HTML =================
with open(OUTPUT_HTML, "w", encoding="utf-8") as f:
    f.write(html)

print(f"\n✅ Panel ultra-premium generado: {OUTPUT_HTML}")
print(f"📊 Estadísticas:")
print(f"   👥 Jugadores reales: {len(real)}")
print(f"   🤖 Bots detectados: {len(bots)}")

print(f"   📈 Total analizados: {len(players)}")

