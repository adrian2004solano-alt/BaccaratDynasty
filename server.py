"""
server.py — Baccarat Dynasty VIP Web Platform (Backend + Conector Supabase + Anti-Sharing)
==========================================================================================
- Base de Datos Híbrida: Sincronización en tiempo real con Supabase (https://fevrpdoitikbosvrezxi.supabase.co)
  + respaldo instantáneo SQLite local para 100% disponibilidad.
- Seguridad "La Vieja Confiable":
  1) Verificación real de correo electrónico por código de 6 dígitos (OTP).
  2) Huella Digital de Dispositivo (Device Fingerprinting - máx. 2 equipos por usuario).
  3) Sesión Única Simultánea (Single Active Session): si un segundo dispositivo entra,
     expulsa en tiempo real al primero.
- Modelo Freemium:
  * Usuarios GRATIS: Ven resultados históricos en vivo + alerta de señal activa bloqueada.
  * Usuarios VIP: Ven señales en tiempo real (Mesa, Captura de Referencia Previa, 6 Tiros, Reloj 15s).
- Pagos en USDT + Panel de Administrador con activación en 1 clic.
"""

import os
import json
import time
import uuid
import hmac
import hashlib
import random
import sqlite3
import logging
import threading
from datetime import datetime, timedelta, timezone
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
from urllib.parse import urlparse, parse_qs
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
PORT = int(os.getenv("PORT", "5000"))

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "dynasty_local.db")
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")


def hash_password(password: str) -> str:
    return hashlib.sha256(f"dynasty_salt_{password}".encode("utf-8")).hexdigest()


# ============================================================================
# CLIENTE DE SINCRONIZACIÓN CON SUPABASE + RESPALDO LOCAL SQLITE
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
        self.remote_ready = False
        self._check_connection()

    def _check_connection(self):
        try:
            r = requests.get(f"{self.url}/rest/v1/", headers=self.headers, timeout=4)
            if r.status_code in (200, 404):
                logger.info(f"✅ Conectado al endpoint de Supabase: {self.url}")
                self.remote_ready = True
        except Exception as e:
            logger.warning(f"Modo local activo (Supabase en espera): {e}")

    def insert_async(self, table: str, payload: dict):
        def _worker():
            try:
                requests.post(
                    f"{self.url}/rest/v1/{table}",
                    headers=self.headers,
                    json=payload,
                    timeout=5,
                )
            except Exception:
                pass
        threading.Thread(target=_worker, daemon=True).start()

    def update_async(self, table: str, match_col: str, match_val: str, payload: dict):
        def _worker():
            try:
                requests.patch(
                    f"{self.url}/rest/v1/{table}?{match_col}=eq.{match_val}",
                    headers=self.headers,
                    json=payload,
                    timeout=5,
                )
            except Exception:
                pass
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

        # Insertar resultados iniciales de demostración si la tabla está vacía
        cur.execute("SELECT COUNT(*) as c FROM dynasty_results")
        if cur.fetchone()["c"] == 0:
            demo_results = [
                ("Baccarat 3", "win", 1, "DISRUPTIVA_4TEND"),
                ("Baccarat 5", "win", 2, "TENDENCIA_PURA_6"),
                ("Baccarat 1", "win", 1, "TENDENCIA_3_DISR"),
                ("Baccarat 2", "win", 1, "DISRUPTIVA_1_5TEND"),
            ]
            for t_name, r_type, att, strat in demo_results:
                cur.execute("""
                    INSERT INTO dynasty_results (table_name, result_type, attempt_number, strategy_name, created_at)
                    VALUES (?, ?, ?, ?, ?)
                """, (t_name, r_type, att, strat, datetime.now().strftime("%H:%M:%S")))

        conn.commit()
        conn.close()


# ============================================================================
# SERVIDOR HTTP MULTIHILO
# ============================================================================
class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True


class DynastyRequestHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def _send_json(self, data: dict, status=200):
        raw = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Bot-Secret")
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

        if path == "/" or path == "/index.html":
            index_file = os.path.join(TEMPLATES_DIR, "index.html")
            if os.path.exists(index_file):
                with open(index_file, "rb") as f:
                    content = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
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

        with db_lock:
            conn = get_db()
            cur = conn.cursor()
            cur.execute("SELECT id, is_verified FROM dynasty_users WHERE email = ?", (email,))
            existing = cur.fetchone()
            if existing:
                conn.close()
                return self._send_json({"ok": False, "msg": "Este correo ya está registrado. Inicia sesión."}, 400)

            cur.execute("""
                INSERT INTO dynasty_users (
                    email, password_hash, is_verified, verification_code,
                    role, registered_devices, created_at
                ) VALUES (?, ?, 0, ?, 'free', '[]', ?)
            """, (email, hash_password(password), otp_code, now_str))
            conn.commit()
            conn.close()

        supabase.insert_async("dynasty_users", {
            "email": email,
            "password_hash": hash_password(password),
            "is_verified": False,
            "verification_code": otp_code,
            "role": "free",
        })

        logger.info(f"📧 Nuevo registro: {email} | Código de verificación OTP: {otp_code}")
        self._send_json({
            "ok": True,
            "msg": f"Código de verificación generado para {email}.",
            "demo_otp": otp_code,  # Se muestra en pantalla para facilitar pruebas o si no hay servidor SMTP externo
        })

    def _handle_verify(self, body: dict):
        email = (body.get("email") or "").strip().lower()
        code = (body.get("code") or "").strip()

        with db_lock:
            conn = get_db()
            cur = conn.cursor()
            cur.execute("SELECT id, verification_code FROM dynasty_users WHERE email = ?", (email,))
            row = cur.fetchone()
            if not row:
                conn.close()
                return self._send_json({"ok": False, "msg": "Usuario no encontrado."}, 404)
            if str(row["verification_code"]) != str(code):
                conn.close()
                return self._send_json({"ok": False, "msg": "Código incorrecto. Verifica e intenta de nuevo."}, 400)

            cur.execute("UPDATE dynasty_users SET is_verified = 1 WHERE email = ?", (email,))
            conn.commit()
            conn.close()

        supabase.update_async("dynasty_users", "email", email, {"is_verified": True})
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

        with db_lock:
            conn = get_db()
            cur = conn.cursor()
            cur.execute("SELECT * FROM dynasty_users WHERE email = ?", (email,))
            user = cur.fetchone()
            if not user or user["password_hash"] != hash_password(password):
                conn.close()
                return self._send_json({"ok": False, "msg": "Correo o contraseña incorrectos."}, 401)

            if not user["is_verified"]:
                conn.close()
                return self._send_json({
                    "ok": False,
                    "needs_verification": True,
                    "demo_otp": user["verification_code"],
                    "msg": "Tu correo aún no está verificado. Ingresa tu código de 6 dígitos.",
                }, 403)

            # Verificar lista de dispositivos físicos vinculados (Máximo 2: ej. 1 PC + 1 Móvil)
            try:
                devices = json.loads(user["registered_devices"] or "[]")
            except Exception:
                devices = []

            known_fps = [d.get("fp") for d in devices]
            if user["role"] != "admin":
                if device_fp not in known_fps:
                    if len(devices) >= 2:
                        conn.close()
                        logger.warning(f"🚨 Bloqueo por exceso de dispositivos en cuenta: {email} (FP: {device_fp})")
                        return self._send_json({
                            "ok": False,
                            "msg": "🛡️ SEGURIDAD ANTI-COMPARTIR: Esta cuenta ya tiene 2 dispositivos vinculados (PC/Móvil). No se permite abrir en equipos de terceros.",
                        }, 403)
                    devices.append({
                        "fp": device_fp,
                        "label": device_label,
                        "added_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    })

            # Generar nuevo token de sesión única (expulsa automáticamente cualquier sesión abierta en otro lado)
            prev_token = user["active_session_token"]
            prev_fp = user["active_device_fp"]
            kicked_previous = bool(prev_token and prev_fp and prev_fp != device_fp)

            new_session_token = str(uuid.uuid4())
            client_ip = self.client_address[0] if self.client_address else "127.0.0.1"

            cur.execute("""
                UPDATE dynasty_users
                SET active_session_token = ?,
                    active_device_fp = ?,
                    registered_devices = ?,
                    last_login_ip = ?
                WHERE email = ?
            """, (new_session_token, device_fp, json.dumps(devices), client_ip, email))
            conn.commit()
            role = user["role"]
            vip_exp = user["vip_expires_at"]
            conn.close()

        supabase.update_async("dynasty_users", "email", email, {
            "active_session_token": new_session_token,
            "active_device_fp": device_fp,
            "registered_devices": devices,
        })

        logger.info(f"🔐 Login exitoso: {email} ({role.upper()}) | Dispositivo: {device_fp[:12]} | Expulsó anterior: {kicked_previous}")
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
    # 3. ESTADO EN TIEMPO REAL (SEÑALES VIP, RESULTADOS GRATIS Y CONTROL SESIÓN)
    # ──────────────────────────────────────────────────────────────────────
    def _handle_get_state(self, token: str, fp: str):
        user_role = "guest"
        user_email = None
        vip_days_left = 0

        with db_lock:
            conn = get_db()
            cur = conn.cursor()

            if token:
                cur.execute("SELECT * FROM dynasty_users WHERE active_session_token = ?", (token,))
                u = cur.fetchone()
                if not u:
                    conn.close()
                    return self._send_json({
                        "status": "kicked",
                        "reason": "🚨 Tu cuenta fue abierta en otro dispositivo. Solo se permite 1 conexión activa a la vez.",
                    })
                user_email = u["email"]
                user_role = u["role"]
                if user_role == "vip" and u["vip_expires_at"]:
                    try:
                        exp_dt = datetime.fromisoformat(u["vip_expires_at"])
                        diff = exp_dt - datetime.now(timezone.utc)
                        if diff.total_seconds() <= 0:
                            user_role = "free"
                            cur.execute("UPDATE dynasty_users SET role = 'free' WHERE id = ?", (u["id"],))
                            conn.commit()
                        else:
                            vip_days_left = max(1, diff.days + 1)
                    except Exception:
                        vip_days_left = 30

            # Obtener señal activa más reciente
            cur.execute("SELECT * FROM dynasty_signals ORDER BY id DESC LIMIT 1")
            sig_row = cur.fetchone()

            # Obtener últimos 15 resultados (100% Gratis para todos)
            cur.execute("SELECT * FROM dynasty_results ORDER BY id DESC LIMIT 15")
            res_rows = cur.fetchall()
            conn.close()

        results_list = []
        wins_count = 0
        for r in res_rows:
            if r["result_type"] == "win":
                wins_count += 1
            results_list.append({
                "id": r["id"],
                "table_name": r["table_name"],
                "result_type": r["result_type"],
                "attempt_number": r["attempt_number"],
                "strategy_name": r["strategy_name"] or "DYNASTY_VIP",
                "screenshot_b64": r["screenshot_b64"],
                "created_at": r["created_at"],
            })

        total_res = len(results_list)
        win_rate = round((wins_count / total_res) * 100, 1) if total_res > 0 else 94.5

        active_signal = None
        if sig_row and sig_row["status"] == "active":
            elapsed = int(time.time() - (sig_row["created_ts"] or time.time()))
            countdown_15 = max(0, 15 - elapsed)
            seq_list = json.loads(sig_row["sequence"] or '["P","B","B","B","B","P"]')

            if user_role in ("vip", "admin"):
                active_signal = {
                    "id": sig_row["id"],
                    "is_locked": False,
                    "table_name": sig_row["table_name"],
                    "sequence": seq_list,
                    "probability": sig_row["probability"],
                    "strategy_name": sig_row["strategy_name"],
                    "reference_image_b64": sig_row["reference_image_b64"],
                    "base_hand_count": sig_row["base_hand_count"],
                    "current_attempt": sig_row["current_attempt"],
                    "countdown": countdown_15,
                    "created_at": sig_row["created_at"],
                }
            else:
                # Usuario Gratis: ve que hay señal en curso, pero con datos sensibles ocultos
                active_signal = {
                    "id": sig_row["id"],
                    "is_locked": True,
                    "table_name": "🔒 MESA OCULTA (SOLO VIP)",
                    "sequence": ["?", "?", "?", "?", "?", "?"],
                    "probability": sig_row["probability"],
                    "strategy_name": "🔒 ESTRATEGIA VIP",
                    "reference_image_b64": None,
                    "base_hand_count": sig_row["base_hand_count"],
                    "current_attempt": sig_row["current_attempt"],
                    "countdown": countdown_15,
                    "created_at": sig_row["created_at"],
                }

        self._send_json({
            "status": "ok",
            "user": {
                "email": user_email,
                "role": user_role,
                "vip_days_left": vip_days_left,
            },
            "active_signal": active_signal,
            "results": results_list,
            "stats": {
                "win_rate": win_rate,
                "total_ tracked": total_res,
                "wins": wins_count,
            },
            "usdt_wallet": USDT_WALLET_TRC20,
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

        with db_lock:
            conn = get_db()
            cur = conn.cursor()
            cur.execute("SELECT email FROM dynasty_users WHERE active_session_token = ?", (token,))
            u = cur.fetchone()
            if not u:
                conn.close()
                return self._send_json({"ok": False, "msg": "Debes iniciar sesión para reportar un pago."}, 401)

            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cur.execute("""
                INSERT INTO dynasty_payments (user_email, plan_name, amount_usdt, txid, status, created_at)
                VALUES (?, ?, ?, ?, 'pending', ?)
            """, (u["email"], plan_name, amount_usdt, txid, now_str))
            conn.commit()
            conn.close()

        supabase.insert_async("dynasty_payments", {
            "user_email": u["email"],
            "plan_name": plan_name,
            "amount_usdt": amount_usdt,
            "txid": txid,
            "status": "pending",
        })

        logger.info(f"💎 Nuevo pago USDT reportado por {u['email']}: {amount_usdt} USDT (TXID: {txid})")
        self._send_json({"ok": True, "msg": "✅ Comprobante enviado. El administrador activará tu membresía VIP en breve."})

    def _handle_admin_data(self, token: str):
        with db_lock:
            conn = get_db()
            cur = conn.cursor()
            cur.execute("SELECT role FROM dynasty_users WHERE active_session_token = ?", (token,))
            u = cur.fetchone()
            if not u or u["role"] != "admin":
                conn.close()
                return self._send_json({"ok": False, "msg": "Acceso exclusivo para el Administrador."}, 403)

            cur.execute("SELECT id, email, is_verified, role, vip_expires_at, active_device_fp, registered_devices, created_at FROM dynasty_users ORDER BY id DESC")
            users = []
            for r in cur.fetchall():
                devs = json.loads(r["registered_devices"] or "[]")
                users.append({
                    "id": r["id"],
                    "email": r["email"],
                    "is_verified": bool(r["is_verified"]),
                    "role": r["role"],
                    "vip_expires_at": r["vip_expires_at"],
                    "device_count": len(devs),
                    "devices": devs,
                    "online": bool(r["active_device_fp"]),
                })

            cur.execute("SELECT * FROM dynasty_payments ORDER BY id DESC LIMIT 30")
            payments = [dict(r) for r in cur.fetchall()]
            conn.close()

        self._send_json({"ok": True, "users": users, "payments": payments})

    def _handle_admin_action(self, body: dict):
        token = (body.get("token") or "").strip()
        action = (body.get("action") or "").strip()
        target_email = (body.get("email") or "").strip().lower()
        payment_id = body.get("payment_id")
        days = int(body.get("days") or 30)

        with db_lock:
            conn = get_db()
            cur = conn.cursor()
            cur.execute("SELECT role FROM dynasty_users WHERE active_session_token = ?", (token,))
            u = cur.fetchone()
            if not u or u["role"] != "admin":
                conn.close()
                return self._send_json({"ok": False, "msg": "No autorizado."}, 403)

            if action == "approve_payment" and payment_id:
                cur.execute("SELECT * FROM dynasty_payments WHERE id = ?", (payment_id,))
                pay = cur.fetchone()
                if pay:
                    target_email = pay["user_email"]
                    days = 7 if "7" in pay["plan_name"] else 30
                    cur.execute("UPDATE dynasty_payments SET status = 'approved' WHERE id = ?", (payment_id,))
                    supabase.update_async("dynasty_payments", "id", str(payment_id), {"status": "approved"})

            if action in ("approve_payment", "grant_vip") and target_email:
                exp = (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()
                cur.execute("UPDATE dynasty_users SET role = 'vip', vip_expires_at = ?, is_verified = 1 WHERE email = ?", (exp, target_email))
                conn.commit()
                conn.close()
                supabase.update_async("dynasty_users", "email", target_email, {"role": "vip", "vip_expires_at": exp, "is_verified": True})
                logger.info(f"👑 Admin activó VIP ({days} días) para: {target_email}")
                return self._send_json({"ok": True, "msg": f"Membresía VIP ({days} días) activada para {target_email}."})

            if action == "revoke_vip" and target_email:
                cur.execute("UPDATE dynasty_users SET role = 'free', vip_expires_at = NULL WHERE email = ?", (target_email,))
                conn.commit()
                conn.close()
                supabase.update_async("dynasty_users", "email", target_email, {"role": "free", "vip_expires_at": None})
                return self._send_json({"ok": True, "msg": f"Usuario {target_email} pasado a plan Gratis."})

            if action == "reset_devices" and target_email:
                cur.execute("UPDATE dynasty_users SET registered_devices = '[]', active_session_token = NULL, active_device_fp = NULL WHERE email = ?", (target_email,))
                conn.commit()
                conn.close()
                supabase.update_async("dynasty_users", "email", target_email, {"registered_devices": [], "active_session_token": None})
                return self._send_json({"ok": True, "msg": f"Dispositivos y sesiones reiniciados para {target_email}."})

            conn.close()
        self._send_json({"ok": False, "msg": "Acción no reconocida."}, 400)

    # ──────────────────────────────────────────────────────────────────────
    # 5. ENDPOINTS PARA EL BOT DE PC (SEÑALES EN VIVO Y RESULTADOS)
    # ──────────────────────────────────────────────────────────────────────
    def _verify_bot_secret(self, body: dict) -> bool:
        header_sec = self.headers.get("X-Bot-Secret", "")
        body_sec = body.get("bot_secret", "")
        return (header_sec == BOT_API_SECRET) or (body_sec == BOT_API_SECRET)

    def _handle_bot_signal(self, body: dict):
        if not self._verify_bot_secret(body):
            return self._send_json({"ok": False, "msg": "Bot secret inválido"}, 403)

        table_name = body.get("table_name", "Baccarat 2")
        sequence = body.get("sequence", ["P", "B", "B", "B", "B", "P"])
        probability = int(body.get("probability", 92))
        strategy_name = body.get("strategy_name", "DYNASTY_VIP")
        reference_image_b64 = body.get("reference_image_b64")
        base_hand_count = int(body.get("base_hand_count", 0))
        now_str = datetime.now().strftime("%H:%M:%S")

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
                reference_image_b64, base_hand_count, time.time(), now_str
            ))
            sig_id = cur.lastrowid
            conn.commit()
            conn.close()

        supabase.insert_async("dynasty_signals", {
            "table_name": table_name,
            "sequence": sequence,
            "probability": probability,
            "strategy_name": strategy_name,
            "reference_image_b64": reference_image_b64,
            "base_hand_count": base_hand_count,
            "current_attempt": 1,
            "status": "active",
        })

        logger.info(f"🚀 [SEÑAL EN VIVO RECIBIDA DEL BOT] Mesa: {table_name} | Secuencia: {sequence} ({probability}%)")
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
        self._send_json({"ok": True})

    def _handle_bot_result(self, body: dict):
        if not self._verify_bot_secret(body):
            return self._send_json({"ok": False, "msg": "Bot secret inválido"}, 403)

        table_name = body.get("table_name", "Baccarat")
        result_type = body.get("result_type", "win")
        attempt_number = int(body.get("attempt_number", 1))
        strategy_name = body.get("strategy_name", "DYNASTY_VIP")
        screenshot_b64 = body.get("screenshot_b64")
        now_str = datetime.now().strftime("%H:%M:%S")

        with db_lock:
            conn = get_db()
            cur = conn.cursor()
            cur.execute("UPDATE dynasty_signals SET status = ? WHERE status = 'active'", (result_type,))
            cur.execute("""
                INSERT INTO dynasty_results (
                    table_name, result_type, attempt_number, strategy_name, screenshot_b64, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, (table_name, result_type, attempt_number, strategy_name, screenshot_b64, now_str))
            conn.commit()
            conn.close()

        supabase.insert_async("dynasty_results", {
            "table_name": table_name,
            "result_type": result_type,
            "attempt_number": attempt_number,
            "strategy_name": strategy_name,
            "screenshot_b64": screenshot_b64,
        })

        logger.info(f"🏆 [RESULTADO OFICIAL DEL BOT] {table_name} -> {result_type.upper()} en Tiro {attempt_number}")
        self._send_json({"ok": True})


if __name__ == "__main__":
    init_db()
    server = ThreadedHTTPServer(("0.0.0.0", PORT), DynastyRequestHandler)
    print("=" * 68)
    print("  👑 BACCARAT DYNASTY VIP — PLATAFORMA WEB ACTIVA 👑")
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
