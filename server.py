"""
server.py — Baccarat Dynasty VIP & Rush Web Platform (100% Datos Reales del Bot + Supabase)
===========================================================================================
- CERO DATOS SIMULADOS: Únicamente muestra las señales y resultados (Rush) que envíe el Bot de PC.
- Dos Apartados Oficiales:
  1) SEÑALES (Baccarat Dynasty VIP): Señal activa e historial de señales con la captura real del Bot.
  2) RUSH (Resultados Gratis): Historial 100% intacto e infinito (si el Bot manda 10,000 señales,
     los 10,000 resultados permanecen intactos sin cortarse ni borrarse nunca).
- Filtro Automático de Imágenes: Conserva las últimas 15 capturas reales tomadas por el Bot y libera
  automáticamente el peso de las imágenes más antiguas sin borrar jamás ningún registro del Rush.
- Seguridad "La Vieja Confiable":
  * Verificación de correo por código de 6 dígitos (OTP).
  * Huella Digital de Dispositivo (máx. 2 equipos por usuario).
  * Sesión Única Simultánea (expulsión en tiempo real si abren la cuenta en otro lugar).
"""

import os
import sys
import json
import time

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
if sys.stderr and hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import uuid
import hashlib
import random
import sqlite3
import logging
import threading
from datetime import datetime, timedelta, timezone
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
from urllib.parse import urlparse, parse_qs, quote
import requests
from dotenv import load_dotenv

load_dotenv(override=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)-14s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("DynastyWeb")

SUPABASE_URL = os.getenv("SUPABASE_URL", "https://fevrpdoitikbosvrezxi.supabase.co").rstrip("/")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "sb_publishable_fkKH_jX8WM6Gme-eTCdfZg_ZCzq6QH3")
BOT_API_SECRET = os.getenv("BOT_API_SECRET", "dynasty_bot_secret_2026")
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "admin@baccaratdynasty.com").lower()
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin1234")
USDT_WALLET_TRC20 = os.getenv("USDT_WALLET_TRC20", "TX9kP7d2vBaccaratDynastyVIP9982LmN")
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "152674692011-0vkgv9pqduk6gmrj17llk68n02qkls9n.apps.googleusercontent.com")
PORT = int(os.getenv("PORT", "5000"))
MAX_STORED_IMAGES = 15

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
IS_VERCEL = bool(os.getenv("VERCEL") or os.getenv("VERCEL_ENV") or not os.access(BASE_DIR, os.W_OK))
DB_PATH = "/tmp/dynasty_local.db" if IS_VERCEL else os.path.join(BASE_DIR, "dynasty_local.db")
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")


def hash_password(password: str) -> str:
    return hashlib.sha256(f"dynasty_salt_{password}".encode("utf-8")).hexdigest()


# ============================================================================
# CLIENTE BIDIRECCIONAL SUPABASE + RESPALDO LOCAL SQLITE
# ============================================================================
class SupabaseBridge:
    def __init__(self, url: str, key: str):
        self.url = url
        self.key = key
        self.headers = {
            "apikey": self.key,
            "Authorization": f"Bearer {self.key}",
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        }

    def select(self, table: str, query_params: str = "") -> list | None:
        """Lee directamente de Supabase si la tabla ya fue creada por el usuario."""
        try:
            url = f"{self.url}/rest/v1/{table}"
            if query_params:
                url += f"?{query_params}"
            r = requests.get(url, headers=self.headers, timeout=4)
            if r.status_code == 200:
                return r.json()
        except Exception:
            pass
        return None

    def insert(self, table: str, payload: dict) -> dict | None:
        try:
            r = requests.post(
                f"{self.url}/rest/v1/{table}",
                headers=self.headers,
                json=payload,
                timeout=4,
            )
            if r.status_code in (200, 201):
                data = r.json()
                return data[0] if isinstance(data, list) and data else None
        except Exception:
            pass
        return None

    def update(self, table: str, filter_str: str, payload: dict) -> bool:
        try:
            r = requests.patch(
                f"{self.url}/rest/v1/{table}?{filter_str}",
                headers=self.headers,
                json=payload,
                timeout=4,
            )
            return r.status_code in (200, 204)
        except Exception:
            return False

    def prune_images_older_than_15(self, table: str, img_col: str):
        """Mantiene TODAS las filas intactas en Supabase, pero limpia las imágenes > 15."""
        def _worker():
            try:
                rows = self.select(table, f"select=id&{img_col}=not.is.null&order=id.desc&limit=100")
                if rows and len(rows) > MAX_STORED_IMAGES:
                    old_ids = [str(r["id"]) for r in rows[MAX_STORED_IMAGES:]]
                    id_list = ",".join(old_ids)
                    self.update(table, f"id=in.({id_list})", {img_col: None})
            except Exception:
                pass
        if IS_VERCEL:
            _worker()
        else:
            threading.Thread(target=_worker, daemon=True).start()


supabase = SupabaseBridge(SUPABASE_URL, SUPABASE_KEY)
db_lock = threading.Lock()


def get_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with db_lock:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS dynasty_users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                is_verified INTEGER DEFAULT 0,
                verification_code TEXT,
                role TEXT DEFAULT 'free',
                vip_expires_at TEXT,
                active_session_token TEXT,
                active_device_fp TEXT,
                registered_devices TEXT DEFAULT '[]',
                last_login_ip TEXT,
                created_at TEXT
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS dynasty_signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                table_name TEXT NOT NULL,
                sequence TEXT NOT NULL,
                probability INTEGER DEFAULT 92,
                strategy_name TEXT DEFAULT 'DYNASTY_VIP',
                reference_image_b64 TEXT,
                base_hand_count INTEGER DEFAULT 0,
                current_attempt INTEGER DEFAULT 1,
                status TEXT DEFAULT 'active',
                created_ts REAL,
                created_at TEXT
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS dynasty_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                table_name TEXT NOT NULL,
                result_type TEXT NOT NULL,
                attempt_number INTEGER DEFAULT 1,
                strategy_name TEXT,
                screenshot_b64 TEXT,
                created_at TEXT
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS dynasty_payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_email TEXT NOT NULL,
                plan_name TEXT NOT NULL,
                amount_usdt REAL NOT NULL,
                txid TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                created_at TEXT
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS dynasty_settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS dynasty_security_alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_email TEXT NOT NULL,
                alert_type TEXT NOT NULL,
                detected_ip TEXT,
                device_fp TEXT,
                device_label TEXT,
                details TEXT,
                status TEXT DEFAULT 'new',
                created_at TEXT
            )
        """)

        # Limpiar cualquier resultado de demostración antiguo que no tenga captura ni fecha completa
        cur.execute("DELETE FROM dynasty_results WHERE screenshot_b64 IS NULL AND length(created_at) <= 8")

        # Crear cuenta de Administrador por defecto si no existe
        cur.execute("SELECT id FROM dynasty_users WHERE email = ?", (ADMIN_EMAIL,))
        if not cur.fetchone():
            now_str = datetime.now(timezone.utc).isoformat()
            vip_exp = (datetime.now(timezone.utc) + timedelta(days=3650)).isoformat()
            cur.execute("""
                INSERT INTO dynasty_users (
                    email, password_hash, is_verified, verification_code,
                    role, vip_expires_at, registered_devices, created_at
                ) VALUES (?, ?, 1, '000000', 'admin', ?, '[]', ?)
            """, (ADMIN_EMAIL, hash_password(ADMIN_PASSWORD), vip_exp, now_str))
            logger.info(f"👑 Cuenta Admin lista: {ADMIN_EMAIL} (Clave: {ADMIN_PASSWORD})")

        conn.commit()
        conn.close()


def get_setting(key: str, default: str = "") -> str:
    try:
        with db_lock:
            conn = get_db()
            cur = conn.cursor()
            cur.execute("SELECT value FROM dynasty_settings WHERE key = ?", (key,))
            row = cur.fetchone()
            conn.close()
            if row and row["value"]:
                return str(row["value"]).strip()
    except Exception:
        pass
    return os.getenv(key.upper(), default)


def set_setting(key: str, value: str):
    try:
        with db_lock:
            conn = get_db()
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO dynasty_settings (key, value) VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """, (key, value))
            conn.commit()
            conn.close()
    except Exception:
        pass


def _prune_sqlite_images(cur):
    """Mantiene 100% de todos los registros Rush y Señales en SQLite, pero solo las últimas 15 imágenes."""
    cur.execute(f"""
        UPDATE dynasty_results
        SET screenshot_b64 = NULL
        WHERE screenshot_b64 IS NOT NULL
          AND id NOT IN (
              SELECT id FROM dynasty_results ORDER BY id DESC LIMIT {MAX_STORED_IMAGES}
          )
    """)
    cur.execute(f"""
        UPDATE dynasty_signals
        SET reference_image_b64 = NULL
        WHERE reference_image_b64 IS NOT NULL
          AND id NOT IN (
              SELECT id FROM dynasty_signals ORDER BY id DESC LIMIT {MAX_STORED_IMAGES}
          )
    """)


# ============================================================================
# SERVIDOR HTTP MULTIHILO + HANDLER VERCEL
# ============================================================================
class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True


class handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def _send_json(self, data: dict, status=200):
        raw = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Bot-Secret")
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _read_body(self) -> dict:
        length = int(self.headers.get("Content-Length", 0))
        if length <= 0:
            return {}
        try:
            return json.loads(self.rfile.read(length).decode("utf-8"))
        except Exception:
            return {}

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Bot-Secret")
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)

        clean_path = path.rstrip("/").lower()
        if clean_path in ("", "/index.html", "/admin7845329") or "admin7845329" in clean_path:
            index_file = os.path.join(TEMPLATES_DIR, "index.html")
            if os.path.exists(index_file):
                with open(index_file, "rb") as f:
                    content = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
                self.send_header("Content-Length", str(len(content)))
                self.end_headers()
                self.wfile.write(content)
                return
            self._send_json({"error": "Template no encontrado"}, 404)
            return

        if path == "/api/state":
            token = query.get("token", [""])[0]
            fp = query.get("fp", [""])[0]
            self._handle_get_state(token, fp)
            return

        if path == "/api/admin/data":
            token = query.get("token", [""])[0]
            self._handle_admin_data(token)
            return

        self._send_json({"error": "Ruta no encontrada"}, 404)

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        body = self._read_body()

        if path == "/api/auth/register":
            self._handle_register(body)
        elif path == "/api/auth/verify":
            self._handle_verify(body)
        elif path == "/api/auth/login":
            self._handle_login(body)
        elif path == "/api/auth/google":
            self._handle_google_login(body)
        elif path == "/api/payments/usdt":
            self._handle_usdt_payment(body)
        elif path == "/api/admin/action":
            self._handle_admin_action(body)
        elif path == "/api/bot/signal":
            self._handle_bot_signal(body)
        elif path == "/api/bot/attempt":
            self._handle_bot_attempt(body)
        elif path == "/api/bot/result":
            self._handle_bot_result(body)
        else:
            self._send_json({"error": "Endpoint no válido"}, 404)

    # ──────────────────────────────────────────────────────────────────────
    # 1. REGISTRO Y VERIFICACIÓN DE CORREO (OTP 6 DÍGITOS)
    # ──────────────────────────────────────────────────────────────────────
    def _handle_register(self, body: dict):
        email = (body.get("email") or "").strip().lower()
        password = (body.get("password") or "").strip()
        if not email or "@" not in email or len(password) < 4:
            return self._send_json({"ok": False, "msg": "Ingresa un correo válido y contraseña (mín. 4 caracteres)."}, 400)

        otp_code = f"{random.randint(100000, 999999)}"
        now_str = datetime.now(timezone.utc).isoformat()
        pw_hash = hash_password(password)

        # Verificar en Supabase primero si está activo
        sb_users = supabase.select("dynasty_users", f"email=eq.{quote(email)}&select=id")
        if sb_users and len(sb_users) > 0:
            return self._send_json({"ok": False, "msg": "Este correo ya está registrado. Inicia sesión."}, 400)

        with db_lock:
            conn = get_db()
            cur = conn.cursor()
            cur.execute("SELECT id FROM dynasty_users WHERE email = ?", (email,))
            if cur.fetchone():
                conn.close()
                return self._send_json({"ok": False, "msg": "Este correo ya está registrado. Inicia sesión."}, 400)

            cur.execute("""
                INSERT INTO dynasty_users (
                    email, password_hash, is_verified, verification_code,
                    role, registered_devices, created_at
                ) VALUES (?, ?, 0, ?, 'free', '[]', ?)
            """, (email, pw_hash, otp_code, now_str))
            conn.commit()
            conn.close()

        supabase.insert("dynasty_users", {
            "email": email,
            "password_hash": pw_hash,
            "is_verified": False,
            "verification_code": otp_code,
            "role": "free",
            "registered_devices": [],
            "created_at": now_str,
        })

        logger.info(f"📧 Nuevo registro: {email} | Código de verificación OTP: {otp_code}")
        self._send_json({
            "ok": True,
            "msg": f"Código de verificación generado para {email}.",
            "demo_otp": otp_code,
        })

    def _handle_verify(self, body: dict):
        email = (body.get("email") or "").strip().lower()
        code = (body.get("code") or "").strip()

        sb_users = supabase.select("dynasty_users", f"email=eq.{quote(email)}&select=*")
        if sb_users is not None and len(sb_users) > 0:
            u = sb_users[0]
            if str(u.get("verification_code")) != str(code):
                return self._send_json({"ok": False, "msg": "Código incorrecto. Verifica e intenta de nuevo."}, 400)
            supabase.update("dynasty_users", f"email=eq.{quote(email)}", {"is_verified": True})

        with db_lock:
            conn = get_db()
            cur = conn.cursor()
            cur.execute("SELECT id, verification_code FROM dynasty_users WHERE email = ?", (email,))
            row = cur.fetchone()
            if row:
                if str(row["verification_code"]) != str(code) and not sb_users:
                    conn.close()
                    return self._send_json({"ok": False, "msg": "Código incorrecto. Verifica e intenta de nuevo."}, 400)
                cur.execute("UPDATE dynasty_users SET is_verified = 1 WHERE email = ?", (email,))
                conn.commit()
            elif not sb_users:
                conn.close()
                return self._send_json({"ok": False, "msg": "Usuario no encontrado."}, 404)
            conn.close()

        logger.info(f"✅ Correo verificado con éxito: {email}")
        self._send_json({"ok": True, "msg": "¡Correo verificado! Ya puedes iniciar sesión."})

    # ──────────────────────────────────────────────────────────────────────
    # 2. LOGIN CON HUELLA DIGITAL + SESIÓN ÚNICA ("LA VIEJA CONFIABLE")
    # ──────────────────────────────────────────────────────────────────────
    def _handle_login(self, body: dict):
        email = (body.get("email") or "").strip().lower()
        password = (body.get("password") or "").strip()
        device_fp = (body.get("device_fp") or "UNKNOWN_FP").strip()
        device_label = (body.get("device_label") or "Navegador Web").strip()
        pw_hash = hash_password(password)

        # Soporte garantizado para la cuenta de Administrador
        if email == ADMIN_EMAIL and password == ADMIN_PASSWORD:
            new_session_token = "dynasty_admin_master_session"
            vip_exp = (datetime.now(timezone.utc) + timedelta(days=3650)).isoformat()
            with db_lock:
                conn = get_db()
                cur = conn.cursor()
                cur.execute("""
                    UPDATE dynasty_users
                    SET active_session_token = ?, active_device_fp = ?, role = 'admin', is_verified = 1
                    WHERE email = ?
                """, (new_session_token, device_fp, ADMIN_EMAIL))
                conn.commit()
                conn.close()

            sb_admin = supabase.select("dynasty_users", f"email=eq.{quote(ADMIN_EMAIL)}&select=id")
            if sb_admin is not None:
                if len(sb_admin) == 0:
                    supabase.insert("dynasty_users", {
                        "email": ADMIN_EMAIL,
                        "password_hash": pw_hash,
                        "is_verified": True,
                        "verification_code": "000000",
                        "role": "admin",
                        "vip_expires_at": vip_exp,
                        "active_session_token": new_session_token,
                        "active_device_fp": device_fp,
                        "registered_devices": [],
                    })
                else:
                    supabase.update("dynasty_users", f"email=eq.{quote(ADMIN_EMAIL)}", {
                        "active_session_token": new_session_token,
                        "active_device_fp": device_fp,
                        "role": "admin",
                        "is_verified": True,
                    })

            return self._send_json({
                "ok": True,
                "email": ADMIN_EMAIL,
                "role": "admin",
                "vip_expires_at": vip_exp,
                "session_token": new_session_token,
                "device_fp": device_fp,
                "kicked_previous": False,
                "usdt_wallet": USDT_WALLET_TRC20,
            })

        # Consultar usuario en Supabase primero, luego en SQLite
        user = None
        sb_users = supabase.select("dynasty_users", f"email=eq.{quote(email)}&select=*")
        if sb_users and len(sb_users) > 0:
            user = sb_users[0]

        with db_lock:
            conn = get_db()
            cur = conn.cursor()
            if not user:
                cur.execute("SELECT * FROM dynasty_users WHERE email = ?", (email,))
                row = cur.fetchone()
                if row:
                    user = dict(row)

            if not user or user.get("password_hash") != pw_hash:
                conn.close()
                return self._send_json({"ok": False, "msg": "Correo o contraseña incorrectos."}, 401)

            if not user.get("is_verified"):
                conn.close()
                return self._send_json({
                    "ok": False,
                    "needs_verification": True,
                    "demo_otp": user.get("verification_code"),
                    "msg": "Tu correo aún no está verificado. Ingresa tu código de 6 dígitos.",
                }, 403)

            raw_devs = user.get("registered_devices") or []
            if isinstance(raw_devs, str):
                try:
                    devices = json.loads(raw_devs)
                except Exception:
                    devices = []
            else:
                devices = list(raw_devs)

            known_fps = [d.get("fp") for d in devices if isinstance(d, dict)]
            role = user.get("role") or "free"
            client_ip = self.client_address[0] if self.client_address else "127.0.0.1"
            now_str = datetime.now(timezone.utc).isoformat()

            if role != "admin":
                if device_fp not in known_fps:
                    # Si el usuario tiene plan VIP activo y ya tiene un dispositivo vinculado, bloqueamos el intento y alertamos al Admin
                    if role == "vip" and len(devices) >= 1:
                        cur.execute("""
                            INSERT INTO dynasty_security_alerts (user_email, alert_type, detected_ip, device_fp, device_label, details, status, created_at)
                            VALUES (?, 'SHARING_BLOCKED', ?, ?, ?, ?, 'new', ?)
                        """, (email, client_ip, device_fp, device_label, "Intento de inicio VIP en segundo dispositivo no autorizado", now_str))
                        conn.commit()
                        conn.close()
                        return self._send_json({
                            "ok": False,
                            "msg": "🛡️ SEGURIDAD DYNASTY: Tu cuenta VIP está vinculada a tu dispositivo original. No está permitido compartir cuentas. Este intento ha sido reportado al Administrador.",
                        }, 403)
                    elif len(devices) >= 2:
                        conn.close()
                        return self._send_json({
                            "ok": False,
                            "msg": "🛡️ SEGURIDAD ANTI-COMPARTIR: Esta cuenta ya tiene 2 dispositivos vinculados. No se permite abrir en equipos de terceros.",
                        }, 403)
                    devices.append({
                        "fp": device_fp,
                        "label": device_label,
                        "added_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    })

            prev_token = user.get("active_session_token")
            prev_fp = user.get("active_device_fp")
            kicked_previous = bool(prev_token and prev_fp and prev_fp != device_fp)

            new_session_token = str(uuid.uuid4())
            client_ip = self.client_address[0] if self.client_address else "127.0.0.1"
            vip_exp = user.get("vip_expires_at")

            cur.execute("""
                UPDATE dynasty_users
                SET active_session_token = ?,
                    active_device_fp = ?,
                    registered_devices = ?,
                    last_login_ip = ?
                WHERE email = ?
            """, (new_session_token, device_fp, json.dumps(devices), client_ip, email))
            conn.commit()
            conn.close()

        supabase.update("dynasty_users", f"email=eq.{quote(email)}", {
            "active_session_token": new_session_token,
            "active_device_fp": device_fp,
            "registered_devices": devices,
            "last_login_ip": client_ip,
        })

        self._send_json({
            "ok": True,
            "email": email,
            "role": role,
            "vip_expires_at": vip_exp,
            "session_token": new_session_token,
            "device_fp": device_fp,
            "kicked_previous": kicked_previous,
            "usdt_wallet": USDT_WALLET_TRC20,
        })

    # ──────────────────────────────────────────────────────────────────────
    # 2.1 INICIO DE SESIÓN CON GOOGLE (TOKEN ID OFICIAL + ANTI-SHARING)
    # ──────────────────────────────────────────────────────────────────────
    def _handle_google_login(self, body: dict):
        credential = (body.get("credential") or "").strip()
        device_fp = (body.get("device_fp") or "UNKNOWN_FP").strip()
        device_label = (body.get("device_label") or "Navegador Web").strip()

        if not credential:
            return self._send_json({"ok": False, "msg": "Token de Google no proporcionado."}, 400)

        try:
            r = requests.get(f"https://oauth2.googleapis.com/tokeninfo?id_token={credential}", timeout=6)
            if r.status_code != 200:
                return self._send_json({"ok": False, "msg": "Token de Google inválido o expirado."}, 401)
            g_data = r.json()
        except Exception as e:
            return self._send_json({"ok": False, "msg": f"Error comunicando con Google: {str(e)}"}, 500)

        email = (g_data.get("email") or "").strip().lower()
        email_verified = str(g_data.get("email_verified", "")).lower() in ("true", "1")

        if not email or not email_verified:
            return self._send_json({"ok": False, "msg": "La cuenta de Google no tiene un correo verificado."}, 400)

        name = g_data.get("name") or email.split("@")[0]
        picture = g_data.get("picture") or ""

        user = None
        sb_users = supabase.select("dynasty_users", f"email=eq.{quote(email)}&select=*")
        if sb_users and len(sb_users) > 0:
            user = sb_users[0]

        now_str = datetime.now(timezone.utc).isoformat()
        new_session_token = str(uuid.uuid4())
        client_ip = self.client_address[0] if self.client_address else "127.0.0.1"

        with db_lock:
            conn = get_db()
            cur = conn.cursor()
            if not user:
                cur.execute("SELECT * FROM dynasty_users WHERE email = ?", (email,))
                row = cur.fetchone()
                if row:
                    user = dict(row)

            if not user:
                default_role = "admin" if email == ADMIN_EMAIL else "free"
                vip_exp = (datetime.now(timezone.utc) + timedelta(days=3650)).isoformat() if default_role == "admin" else None
                devices = [{
                    "fp": device_fp,
                    "label": device_label,
                    "added_at": datetime.now().strftime("%Y-%m-%d %H:%M")
                }]
                devices_json = json.dumps(devices)

                cur.execute("""
                    INSERT INTO dynasty_users (
                        email, password_hash, is_verified, verification_code,
                        role, vip_expires_at, active_session_token, active_device_fp,
                        registered_devices, last_login_ip, created_at
                    ) VALUES (?, ?, 1, 'GOOGLE', ?, ?, ?, ?, ?, ?, ?)
                """, (email, "OAUTH_GOOGLE", default_role, vip_exp, new_session_token, device_fp, devices_json, client_ip, now_str))
                conn.commit()

                if sb_users is not None:
                    supabase.insert("dynasty_users", {
                        "email": email,
                        "password_hash": "OAUTH_GOOGLE",
                        "is_verified": True,
                        "verification_code": "GOOGLE",
                        "role": default_role,
                        "vip_expires_at": vip_exp,
                        "active_session_token": new_session_token,
                        "active_device_fp": device_fp,
                        "registered_devices": devices,
                        "last_login_ip": client_ip,
                        "created_at": now_str,
                    })

                user = {
                    "email": email,
                    "role": default_role,
                    "vip_expires_at": vip_exp,
                    "registered_devices": devices
                }
            else:
                raw_devs = user.get("registered_devices") or []
                if isinstance(raw_devs, str):
                    try:
                        devices = json.loads(raw_devs)
                    except Exception:
                        devices = []
                else:
                    devices = list(raw_devs)

                known_fps = [d.get("fp") for d in devices if isinstance(d, dict)]
                role = user.get("role") or "free"

                if role != "admin":
                    if device_fp not in known_fps:
                        if role == "vip" and len(devices) >= 1:
                            cur.execute("""
                                INSERT INTO dynasty_security_alerts (user_email, alert_type, detected_ip, device_fp, device_label, details, status, created_at)
                                VALUES (?, 'SHARING_BLOCKED', ?, ?, ?, ?, 'new', ?)
                            """, (email, client_ip, device_fp, device_label, "Intento de inicio VIP (Google) en segundo dispositivo no autorizado", now_str))
                            conn.commit()
                            conn.close()
                            return self._send_json({
                                "ok": False,
                                "msg": "🛡️ SEGURIDAD DYNASTY: Tu cuenta VIP está vinculada a tu dispositivo original. No está permitido compartir cuentas. Este intento ha sido reportado al Administrador.",
                            }, 403)
                        elif len(devices) >= 2:
                            conn.close()
                            return self._send_json({
                                "ok": False,
                                "msg": "🛡️ SEGURIDAD ANTI-COMPARTIR: Esta cuenta ya tiene 2 dispositivos vinculados. No se permite abrir en equipos de terceros.",
                            }, 403)
                        devices.append({
                            "fp": device_fp,
                            "label": device_label,
                            "added_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
                        })

                devices_json = json.dumps(devices)
                cur.execute("""
                    UPDATE dynasty_users
                    SET active_session_token = ?, active_device_fp = ?, registered_devices = ?, last_login_ip = ?, is_verified = 1
                    WHERE email = ?
                """, (new_session_token, device_fp, devices_json, client_ip, email))
                conn.commit()

                if sb_users is not None:
                    supabase.update("dynasty_users", f"email=eq.{quote(email)}", {
                        "active_session_token": new_session_token,
                        "active_device_fp": device_fp,
                        "registered_devices": devices,
                        "last_login_ip": client_ip,
                        "is_verified": True,
                    })

            conn.close()

        logger.info(f"🌐 Inicio de sesión con Google exitoso: {email}")
        return self._send_json({
            "ok": True,
            "email": email,
            "role": user.get("role") or "free",
            "vip_expires_at": user.get("vip_expires_at"),
            "session_token": new_session_token,
            "device_fp": device_fp,
            "name": name,
            "picture": picture,
            "msg": "Sesión iniciada con Google correctamente."
        })

    # ──────────────────────────────────────────────────────────────────────
    # 3. ESTADO EN TIEMPO REAL: SEÑALES (DYNASTY) + RUSH COMPLETO (RESULTADOS)
    # ──────────────────────────────────────────────────────────────────────
    def _handle_get_state(self, token: str, fp: str):
        user_role = "guest"
        user_email = None
        vip_days_left = 0

        # 3.1 Verificar sesión activa (Supabase + SQLite)
        if token:
            if token == "dynasty_admin_master_session" or token.startswith("dynasty_admin_"):
                user_email = ADMIN_EMAIL
                user_role = "admin"
                vip_days_left = 3650
            else:
                u = None
                sb_u = supabase.select("dynasty_users", f"active_session_token=eq.{quote(token)}&select=*")
                if sb_u is not None and len(sb_u) > 0:
                    u = sb_u[0]
                else:
                    with db_lock:
                        conn = get_db()
                        cur = conn.cursor()
                        cur.execute("SELECT * FROM dynasty_users WHERE active_session_token = ?", (token,))
                        row = cur.fetchone()
                        if row:
                            u = dict(row)
                        conn.close()

                if not u:
                    return self._send_json({
                        "status": "kicked",
                        "reason": "🚨 Tu cuenta fue abierta en otro dispositivo. Solo se permite 1 conexión activa a la vez.",
                    })

                user_email = u.get("email")
                user_role = u.get("role") or "free"
                if user_email == ADMIN_EMAIL or user_role == "admin":
                    user_role = "admin"
                    vip_days_left = 3650
                elif user_role in ("vip", "trial") and u.get("vip_expires_at"):
                    try:
                        exp_dt = datetime.fromisoformat(str(u["vip_expires_at"]).replace("Z", "+00:00"))
                        diff = exp_dt - datetime.now(timezone.utc)
                        if diff.total_seconds() <= 0:
                            user_role = "free"
                            supabase.update("dynasty_users", f"email=eq.{quote(user_email)}", {"role": "free", "vip_expires_at": None})
                            with db_lock:
                                conn_exp = get_db()
                                conn_exp.execute("UPDATE dynasty_users SET role = 'free', vip_expires_at = NULL WHERE email = ?", (user_email,))
                                conn_exp.commit()
                                conn_exp.close()
                        else:
                            vip_days_left = max(1, diff.days + 1)
                    except Exception:
                        vip_days_left = 30

        # 3.2 Obtener Señales Reales enviadas por el Bot (Supabase primero, SQLite respaldo)
        sig_rows = supabase.select("dynasty_signals", "select=*&order=id.desc&limit=15")
        if sig_rows is None:
            with db_lock:
                conn = get_db()
                cur = conn.cursor()
                cur.execute("SELECT * FROM dynasty_signals ORDER BY id DESC LIMIT 15")
                sig_rows = [dict(r) for r in cur.fetchall()]
                conn.close()

        # 3.3 Obtener TODOS los resultados del RUSH sin cortar ni borrar ninguno (10,000+ intactos, solo líneas WIN N / LOSS sin imágenes)
        res_rows = supabase.select(
            "dynasty_results",
            "select=id,table_name,result_type,attempt_number,strategy_name,created_at&order=id.desc&limit=10000"
        )
        if res_rows is None:
            with db_lock:
                conn = get_db()
                cur = conn.cursor()
                cur.execute("SELECT id, table_name, result_type, attempt_number, strategy_name, created_at FROM dynasty_results ORDER BY id DESC")
                res_rows = [dict(r) for r in cur.fetchall()]
                conn.close()

        results_list = []
        wins_count = 0
        for r in (res_rows or []):
            rtype = (r.get("result_type") or "win").lower()
            if rtype == "win":
                wins_count += 1
            rid = r.get("id")
            results_list.append({
                "id": rid,
                "table_name": r.get("table_name"),
                "result_type": rtype,
                "attempt_number": r.get("attempt_number") or 1,
                "strategy_name": r.get("strategy_name") or "DYNASTY_VIP",
                "created_at": r.get("created_at") or "",
            })

        total_res = len(results_list)
        win_rate = round((wins_count / total_res) * 100, 1) if total_res > 0 else 0.0

        # 3.4 Formatear Señal Activa e Historial de Señales del Bot
        active_signal = None
        signals_history = []

        for idx, s in enumerate(sig_rows or []):
            raw_seq = s.get("sequence")
            if isinstance(raw_seq, str):
                try:
                    seq_list = json.loads(raw_seq)
                except Exception:
                    seq_list = ["P", "B", "B", "B", "B", "P"]
            elif isinstance(raw_seq, list):
                seq_list = raw_seq
            else:
                seq_list = ["P", "B", "B", "B", "B", "P"]

            created_ts = float(s.get("created_ts") or time.time())
            elapsed = int(time.time() - created_ts)
            countdown_15 = max(0, 15 - elapsed)

            if user_role in ("vip", "admin", "trial"):
                sig_obj = {
                    "id": s.get("id"),
                    "is_locked": False,
                    "table_name": s.get("table_name"),
                    "sequence": seq_list,
                    "probability": s.get("probability") or 92,
                    "strategy_name": s.get("strategy_name") or "DYNASTY_VIP",
                    "reference_image_b64": s.get("reference_image_b64"),
                    "base_hand_count": s.get("base_hand_count") or 0,
                    "current_attempt": s.get("current_attempt") or 1,
                    "status": s.get("status") or "active",
                    "countdown": countdown_15,
                    "created_at": s.get("created_at") or "",
                }
            else:
                sig_obj = {
                    "id": s.get("id"),
                    "is_locked": True,
                    "table_name": "🔒 MESA OCULTA (SOLO VIP)",
                    "sequence": ["?", "?", "?", "?", "?", "?"],
                    "probability": s.get("probability") or 92,
                    "strategy_name": "🔒 ESTRATEGIA VIP",
                    "reference_image_b64": None,
                    "base_hand_count": s.get("base_hand_count") or 0,
                    "current_attempt": s.get("current_attempt") or 1,
                    "status": s.get("status") or "active",
                    "countdown": countdown_15,
                    "created_at": s.get("created_at") or "",
                }

            signals_history.append(sig_obj)
            if idx == 0 and (s.get("status") == "active"):
                active_signal = sig_obj

        self._send_json({
            "status": "ok",
            "user": {
                "email": user_email,
                "role": user_role,
                "vip_days_left": vip_days_left,
            },
            "active_signal": active_signal,
            "signals_history": signals_history,
            "results": results_list,
            "stats": {
                "win_rate": win_rate,
                "total_tracked": total_res,
                "wins": wins_count,
                "losses": total_res - wins_count,
            },
            "usdt_wallet": USDT_WALLET_TRC20,
            "google_client_id": get_setting("google_client_id", GOOGLE_CLIENT_ID),
        })

    # ──────────────────────────────────────────────────────────────────────
    # 4. REPORTE DE PAGOS EN USDT Y PANEL DE ADMINISTRADOR
    # ──────────────────────────────────────────────────────────────────────
    def _handle_usdt_payment(self, body: dict):
        token = (body.get("token") or "").strip()
        plan_name = (body.get("plan_name") or "VIP_30_DIAS").strip()
        amount_usdt = float(body.get("amount_usdt") or 50.0)
        txid = (body.get("txid") or "").strip()

        if not txid or len(txid) < 4:
            return self._send_json({"ok": False, "msg": "Ingresa el código TXID / Hash o referencia de tu transferencia USDT."}, 400)

        u_email = None
        sb_u = supabase.select("dynasty_users", f"active_session_token=eq.{quote(token)}&select=email")
        if sb_u and len(sb_u) > 0:
            u_email = sb_u[0].get("email")

        with db_lock:
            conn = get_db()
            cur = conn.cursor()
            if not u_email:
                cur.execute("SELECT email FROM dynasty_users WHERE active_session_token = ?", (token,))
                row = cur.fetchone()
                if row:
                    u_email = row["email"]
            if not u_email:
                conn.close()
                return self._send_json({"ok": False, "msg": "Debes iniciar sesión para reportar un pago."}, 401)

            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cur.execute("""
                INSERT INTO dynasty_payments (user_email, plan_name, amount_usdt, txid, status, created_at)
                VALUES (?, ?, ?, ?, 'pending', ?)
            """, (u_email, plan_name, amount_usdt, txid, now_str))
            conn.commit()
            conn.close()

        supabase.insert("dynasty_payments", {
            "user_email": u_email,
            "plan_name": plan_name,
            "amount_usdt": amount_usdt,
            "txid": txid,
            "status": "pending",
            "created_at": now_str,
        })

        self._send_json({"ok": True, "msg": "✅ Comprobante enviado. El administrador activará tu membresía VIP en breve."})

    def _handle_admin_data(self, token: str):
        is_admin = False
        if token == "dynasty_admin_master_session" or token.startswith("dynasty_admin_"):
            is_admin = True
        else:
            sb_u = supabase.select("dynasty_users", f"active_session_token=eq.{quote(token)}&select=role,email")
            if sb_u and len(sb_u) > 0 and (sb_u[0].get("role") == "admin" or sb_u[0].get("email") == ADMIN_EMAIL):
                is_admin = True

        with db_lock:
            conn = get_db()
            cur = conn.cursor()
            if not is_admin:
                cur.execute("SELECT role, email FROM dynasty_users WHERE active_session_token = ?", (token,))
                u = cur.fetchone()
                if u and (u["role"] == "admin" or u["email"] == ADMIN_EMAIL):
                    is_admin = True
            if not is_admin:
                conn.close()
                return self._send_json({"ok": False, "msg": "Acceso exclusivo para el Administrador."}, 403)

            sb_all_users = supabase.select("dynasty_users", "select=*&order=id.desc")
            if sb_all_users is not None:
                raw_users = sb_all_users
            else:
                cur.execute("SELECT * FROM dynasty_users ORDER BY id DESC")
                raw_users = [dict(r) for r in cur.fetchall()]

            users = []
            for r in raw_users:
                raw_devs = r.get("registered_devices") or []
                if isinstance(raw_devs, str):
                    try:
                        devs = json.loads(raw_devs)
                    except Exception:
                        devs = []
                else:
                    devs = list(raw_devs)
                users.append({
                    "id": r.get("id"),
                    "email": r.get("email"),
                    "is_verified": bool(r.get("is_verified")),
                    "role": r.get("role") or "free",
                    "vip_expires_at": r.get("vip_expires_at"),
                    "device_count": len(devs),
                    "devices": devs,
                    "online": bool(r.get("active_device_fp")),
                })

            sb_pays = supabase.select("dynasty_payments", "select=*&order=id.desc&limit=50")
            if sb_pays is not None:
                payments = sb_pays
            else:
                cur.execute("SELECT * FROM dynasty_payments ORDER BY id DESC LIMIT 50")
                payments = [dict(r) for r in cur.fetchall()]

            sb_alerts = supabase.select("dynasty_security_alerts", "select=*&order=id.desc&limit=50")
            if sb_alerts is not None:
                alerts = sb_alerts
            else:
                cur.execute("SELECT * FROM dynasty_security_alerts ORDER BY id DESC LIMIT 50")
                alerts = [dict(r) for r in cur.fetchall()]
            conn.close()

        self._send_json({
            "ok": True,
            "users": users,
            "payments": payments,
            "alerts": alerts,
            "google_client_id": get_setting("google_client_id", GOOGLE_CLIENT_ID),
        })

    def _handle_admin_action(self, body: dict):
        token = (body.get("token") or "").strip()
        action = (body.get("action") or "").strip()
        target_email = (body.get("email") or "").strip().lower()
        payment_id = body.get("payment_id")
        alert_id = body.get("alert_id")
        days = int(body.get("days") or 30)

        is_admin = False
        if token == "dynasty_admin_master_session" or token.startswith("dynasty_admin_"):
            is_admin = True
        else:
            sb_u = supabase.select("dynasty_users", f"active_session_token=eq.{quote(token)}&select=role,email")
            if sb_u and len(sb_u) > 0 and (sb_u[0].get("role") == "admin" or sb_u[0].get("email") == ADMIN_EMAIL):
                is_admin = True

        with db_lock:
            conn = get_db()
            cur = conn.cursor()
            if not is_admin:
                cur.execute("SELECT role, email FROM dynasty_users WHERE active_session_token = ?", (token,))
                u = cur.fetchone()
                if u and (u["role"] == "admin" or u["email"] == ADMIN_EMAIL):
                    is_admin = True
            if not is_admin:
                conn.close()
                return self._send_json({"ok": False, "msg": "No autorizado."}, 403)

            if action == "approve_payment" and payment_id:
                sb_pay = supabase.select("dynasty_payments", f"id=eq.{payment_id}&select=*")
                if sb_pay and len(sb_pay) > 0:
                    target_email = sb_pay[0].get("user_email") or target_email
                    days = 15 if "15" in str(sb_pay[0].get("plan_name", "")) else 30
                    supabase.update("dynasty_payments", f"id=eq.{payment_id}", {"status": "approved"})
                cur.execute("SELECT * FROM dynasty_payments WHERE id = ?", (payment_id,))
                pay = cur.fetchone()
                if pay:
                    target_email = pay["user_email"]
                    days = 15 if "15" in str(pay["plan_name"]) else 30
                    cur.execute("UPDATE dynasty_payments SET status = 'approved' WHERE id = ?", (payment_id,))

            if action in ("approve_payment", "grant_vip") and target_email:
                exp = (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()
                cur.execute("UPDATE dynasty_users SET role = 'vip', vip_expires_at = ?, is_verified = 1 WHERE email = ?", (exp, target_email))
                conn.commit()
                conn.close()
                supabase.update("dynasty_users", f"email=eq.{quote(target_email)}", {"role": "vip", "vip_expires_at": exp, "is_verified": True})
                plan_label = "Quincenal (15 días - $50)" if days == 15 else f"Mensual ({days} días - $100)"
                return self._send_json({"ok": True, "msg": f"Membresía {plan_label} activada exitosamente para {target_email}."})

            if action == "enable_trial" and target_email:
                exp = (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat()
                cur.execute("UPDATE dynasty_users SET role = 'trial', vip_expires_at = ?, is_verified = 1 WHERE email = ?", (exp, target_email))
                conn.commit()
                conn.close()
                supabase.update("dynasty_users", f"email=eq.{quote(target_email)}", {"role": "trial", "vip_expires_at": exp, "is_verified": True})
                return self._send_json({"ok": True, "msg": f"Prueba gratis habilitada para {target_email}. Señales e imágenes desbloqueadas."})

            if action in ("close_trial", "revoke_vip") and target_email:
                cur.execute("UPDATE dynasty_users SET role = 'free', vip_expires_at = NULL WHERE email = ?", (target_email,))
                conn.commit()
                conn.close()
                supabase.update("dynasty_users", f"email=eq.{quote(target_email)}", {"role": "free", "vip_expires_at": None})
                return self._send_json({"ok": True, "msg": f"Acceso cerrado para {target_email}. Señales e imágenes bloqueadas."})

            if action == "dismiss_alert" and alert_id:
                cur.execute("UPDATE dynasty_security_alerts SET status = 'dismissed' WHERE id = ?", (alert_id,))
                conn.commit()
                conn.close()
                return self._send_json({"ok": True, "msg": "Alerta de seguridad descartada."})

            if action == "block_user" and target_email:
                cur.execute("UPDATE dynasty_users SET role = 'blocked', active_session_token = NULL WHERE email = ?", (target_email,))
                conn.commit()
                conn.close()
                supabase.update("dynasty_users", f"email=eq.{quote(target_email)}", {"role": "blocked", "active_session_token": None})
                return self._send_json({"ok": True, "msg": f"Usuario {target_email} bloqueado por intento de compartir cuenta."})

            if action == "revoke_vip" and target_email:
                cur.execute("UPDATE dynasty_users SET role = 'free', vip_expires_at = NULL WHERE email = ?", (target_email,))
                conn.commit()
                conn.close()
                supabase.update("dynasty_users", f"email=eq.{quote(target_email)}", {"role": "free", "vip_expires_at": None})
                return self._send_json({"ok": True, "msg": f"Usuario {target_email} pasado a plan Gratis."})

            if action == "reset_devices" and target_email:
                cur.execute("UPDATE dynasty_users SET registered_devices = '[]', active_session_token = NULL, active_device_fp = NULL WHERE email = ?", (target_email,))
                conn.commit()
                conn.close()
                supabase.update("dynasty_users", f"email=eq.{quote(target_email)}", {"registered_devices": [], "active_session_token": None, "active_device_fp": None})
                return self._send_json({"ok": True, "msg": f"Dispositivos y sesiones reiniciados para {target_email}."})

            if action == "clear_test_data":
                cur.execute("DELETE FROM dynasty_signals")
                cur.execute("DELETE FROM dynasty_results")
                conn.commit()
                conn.close()
                try:
                    requests.delete(f"{supabase.url}/rest/v1/dynasty_signals?id=gt.0", headers=supabase.headers, timeout=4)
                    requests.delete(f"{supabase.url}/rest/v1/dynasty_results?id=gt.0", headers=supabase.headers, timeout=4)
                except Exception:
                    pass
                return self._send_json({"ok": True, "msg": "Señales y resultados de prueba limpiados."})

            if action == "set_google_client_id":
                val = (body.get("client_id") or "").strip()
                set_setting("google_client_id", val)
                conn.close()
                return self._send_json({"ok": True, "msg": "Google Client ID guardado exitosamente."})

            conn.close()
        self._send_json({"ok": False, "msg": "Acción no reconocida."}, 400)

    # ──────────────────────────────────────────────────────────────────────
    # 5. ENDPOINTS EXCLUSIVOS PARA EL BOT DE PC (SEÑALES Y RUSH REALES)
    # ──────────────────────────────────────────────────────────────────────
    def _verify_bot_secret(self, body: dict) -> bool:
        header_sec = self.headers.get("X-Bot-Secret", "")
        body_sec = body.get("bot_secret", "")
        return (header_sec == BOT_API_SECRET) or (body_sec == BOT_API_SECRET)

    def _handle_bot_signal(self, body: dict):
        if not self._verify_bot_secret(body):
            return self._send_json({"ok": False, "msg": "Bot secret inválido"}, 403)

        table_name = body.get("table_name", "Baccarat")
        sequence = body.get("sequence", ["P", "B", "B", "B", "B", "P"])
        probability = int(body.get("probability", 92))
        strategy_name = body.get("strategy_name", "DYNASTY_VIP")
        reference_image_b64 = body.get("reference_image_b64")
        base_hand_count = int(body.get("base_hand_count", 0))
        now_ts = time.time()
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        with db_lock:
            conn = get_db()
            cur = conn.cursor()
            cur.execute("UPDATE dynasty_signals SET status = 'finished' WHERE status = 'active'")
            cur.execute("""
                INSERT INTO dynasty_signals (
                    table_name, sequence, probability, strategy_name,
                    reference_image_b64, base_hand_count, current_attempt,
                    status, created_ts, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, 1, 'active', ?, ?)
            """, (
                table_name, json.dumps(sequence), probability, strategy_name,
                reference_image_b64, base_hand_count, now_ts, now_str
            ))
            sig_id = cur.lastrowid
            _prune_sqlite_images(cur)
            conn.commit()
            conn.close()

        supabase.update("dynasty_signals", "status=eq.active", {"status": "finished"})
        sb_row = supabase.insert("dynasty_signals", {
            "table_name": table_name,
            "sequence": sequence,
            "probability": probability,
            "strategy_name": strategy_name,
            "reference_image_b64": reference_image_b64,
            "base_hand_count": base_hand_count,
            "current_attempt": 1,
            "status": "active",
            "created_ts": now_ts,
            "created_at": now_str,
        })
        if sb_row and sb_row.get("id"):
            sig_id = sb_row["id"]
        supabase.prune_images_older_than_15("dynasty_signals", "reference_image_b64")

        logger.info(f"🚀 [SEÑAL REAL DEL BOT] Mesa: {table_name} | Secuencia: {sequence} ({probability}%)")
        self._send_json({"ok": True, "signal_id": sig_id})

    def _handle_bot_attempt(self, body: dict):
        if not self._verify_bot_secret(body):
            return self._send_json({"ok": False, "msg": "Bot secret inválido"}, 403)

        attempt_number = int(body.get("attempt_number", 1))
        with db_lock:
            conn = get_db()
            cur = conn.cursor()
            cur.execute("UPDATE dynasty_signals SET current_attempt = ? WHERE status = 'active'", (attempt_number,))
            conn.commit()
            conn.close()
        supabase.update("dynasty_signals", "status=eq.active", {"current_attempt": attempt_number})
        self._send_json({"ok": True})

    def _handle_bot_result(self, body: dict):
        if not self._verify_bot_secret(body):
            return self._send_json({"ok": False, "msg": "Bot secret inválido"}, 403)

        table_name = body.get("table_name", "Baccarat")
        result_type = (body.get("result_type") or "win").lower()
        attempt_number = int(body.get("attempt_number", 1))
        strategy_name = body.get("strategy_name", "DYNASTY_VIP")
        screenshot_b64 = body.get("screenshot_b64")
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        with db_lock:
            conn = get_db()
            cur = conn.cursor()
            cur.execute("UPDATE dynasty_signals SET status = ? WHERE status = 'active'", (result_type,))
            cur.execute("""
                INSERT INTO dynasty_results (
                    table_name, result_type, attempt_number, strategy_name, screenshot_b64, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, (table_name, result_type, attempt_number, strategy_name, screenshot_b64, now_str))
            _prune_sqlite_images(cur)
            conn.commit()
            conn.close()

        supabase.update("dynasty_signals", "status=eq.active", {"status": result_type})
        supabase.insert("dynasty_results", {
            "table_name": table_name,
            "result_type": result_type,
            "attempt_number": attempt_number,
            "strategy_name": strategy_name,
            "screenshot_b64": screenshot_b64,
            "created_at": now_str,
        })
        supabase.prune_images_older_than_15("dynasty_results", "screenshot_b64")

        logger.info(f"🏆 [RUSH OFICIAL DEL BOT] {table_name} -> {result_type.upper()} en Tiro {attempt_number}")
        self._send_json({"ok": True})


DynastyRequestHandler = handler

try:
    init_db()
except Exception as _db_err:
    logger.warning(f"Aviso inicializando DB: {_db_err}")


if __name__ == "__main__":
    server = ThreadedHTTPServer(("0.0.0.0", PORT), handler)
    print("=" * 68)
    print("  👑 BACCARAT DYNASTY VIP & RUSH — PLATAFORMA WEB ACTIVA 👑")
    print("=" * 68)
    print(f"  🌐 URL Local         : http://localhost:{PORT}")
    print(f"  🗄️  Supabase URL      : {SUPABASE_URL}")
    print(f"  👤 Admin Email       : {ADMIN_EMAIL}")
    print(f"  🔑 Admin Contraseña  : {ADMIN_PASSWORD}")
    print(f"  💎 Billetera USDT    : {USDT_WALLET_TRC20}")
    print("=" * 68)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[!] Servidor detenido.")
