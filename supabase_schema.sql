-- ============================================================================
-- BACCARAT DYNASTY VIP & RUSH — ESQUEMA OFICIAL DE BASE DE DATOS (SUPABASE)
-- Proyecto: https://fevrpdoitikbosvrezxi.supabase.co
-- Instrucciones:
--   1. Abre tu proyecto en Supabase -> menú izquierdo "SQL Editor" -> "New query"
--   2. Pega TODO este código SQL y haz clic en el botón verde "RUN".
-- ============================================================================

-- 1. Tabla de Usuarios, Verificación de Correo y Control Anti-Sharing ("La Vieja Confiable")
CREATE TABLE IF NOT EXISTS public.dynasty_users (
    id BIGSERIAL PRIMARY KEY,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    is_verified BOOLEAN DEFAULT FALSE,
    verification_code TEXT,
    role TEXT DEFAULT 'free', -- 'free', 'vip', 'admin'
    vip_expires_at TIMESTAMPTZ,
    active_session_token TEXT,
    active_device_fp TEXT,
    registered_devices JSONB DEFAULT '[]'::jsonb,
    last_login_ip TEXT,
    created_at TEXT DEFAULT to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS')
);

-- 2. Apartado de SEÑALES (Baccarat Dynasty VIP - Enviadas únicamente por el Bot)
CREATE TABLE IF NOT EXISTS public.dynasty_signals (
    id BIGSERIAL PRIMARY KEY,
    table_name TEXT NOT NULL,
    sequence JSONB NOT NULL, -- Ej: ["P", "B", "B", "B", "B", "P"]
    probability INTEGER DEFAULT 92,
    strategy_name TEXT DEFAULT 'DYNASTY_VIP',
    reference_image_b64 TEXT, -- Captura real tomada por el Bot (Resultado anterior)
    base_hand_count INTEGER DEFAULT 0,
    current_attempt INTEGER DEFAULT 1,
    status TEXT DEFAULT 'active', -- 'active', 'win', 'loss', 'finished'
    created_ts DOUBLE PRECISION DEFAULT extract(epoch from now()),
    created_at TEXT DEFAULT to_char(NOW(), 'HH24:MI:SS')
);

-- 3. Apartado de RUSH — Resultados Oficiales (100% Gratis, Historial Infinito sin borrarse nunca)
CREATE TABLE IF NOT EXISTS public.dynasty_results (
    id BIGSERIAL PRIMARY KEY,
    table_name TEXT NOT NULL,
    result_type TEXT NOT NULL, -- 'win' o 'loss'
    attempt_number INTEGER DEFAULT 1,
    strategy_name TEXT DEFAULT 'DYNASTY_VIP',
    screenshot_b64 TEXT, -- Captura real tomada por el Bot al finalizar la jugada
    created_at TEXT DEFAULT to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS')
);

-- 4. Tabla de Pagos en USDT (Para aprobar desde el Panel Admin con 1 clic)
CREATE TABLE IF NOT EXISTS public.dynasty_payments (
    id BIGSERIAL PRIMARY KEY,
    user_email TEXT NOT NULL,
    plan_name TEXT NOT NULL, -- 'VIP_30_DIAS' o 'VIP_7_DIAS'
    amount_usdt NUMERIC(10, 2) NOT NULL,
    txid TEXT NOT NULL,
    status TEXT DEFAULT 'pending', -- 'pending', 'approved', 'rejected'
    created_at TEXT DEFAULT to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS')
);

-- 5. Filtro Automático de Imágenes (Conserva 100% de todos los resultados Rush para siempre,
--    pero limpia las imágenes antiguas dejando solo las últimas 15 capturas reales del Bot)
CREATE OR REPLACE FUNCTION public.prune_old_bot_images()
RETURNS TRIGGER AS $$
BEGIN
    UPDATE public.dynasty_results
    SET screenshot_b64 = NULL
    WHERE screenshot_b64 IS NOT NULL
      AND id NOT IN (
          SELECT id FROM public.dynasty_results
          ORDER BY id DESC
          LIMIT 15
      );

    UPDATE public.dynasty_signals
    SET reference_image_b64 = NULL
    WHERE reference_image_b64 IS NOT NULL
      AND id NOT IN (
          SELECT id FROM public.dynasty_signals
          ORDER BY id DESC
          LIMIT 15
      );

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_prune_results_images ON public.dynasty_results;
CREATE TRIGGER trg_prune_results_images
AFTER INSERT ON public.dynasty_results
FOR EACH ROW EXECUTE FUNCTION public.prune_old_bot_images();

DROP TRIGGER IF EXISTS trg_prune_signals_images ON public.dynasty_signals;
CREATE TRIGGER trg_prune_signals_images
AFTER INSERT ON public.dynasty_signals
FOR EACH ROW EXECUTE FUNCTION public.prune_old_bot_images();

-- 6. Crear cuenta de Administrador por defecto (admin@baccaratdynasty.com / admin1234)
INSERT INTO public.dynasty_users (
    email, password_hash, is_verified, verification_code, role, vip_expires_at, registered_devices
) VALUES (
    'admin@baccaratdynasty.com',
    '3ad6f065e69f73896e4083a5b05f4616a468c897d22a6e391b74b8c3f41a5c1f',
    TRUE,
    '000000',
    'admin',
    NOW() + INTERVAL '10 years',
    '[]'::jsonb
) ON CONFLICT (email) DO NOTHING;

-- 7. Habilitar políticas de acceso para la API del Bot y la Web
ALTER TABLE public.dynasty_users ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.dynasty_signals ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.dynasty_results ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.dynasty_payments ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Acceso API Backend Users" ON public.dynasty_users;
DROP POLICY IF EXISTS "Acceso API Backend Signals" ON public.dynasty_signals;
DROP POLICY IF EXISTS "Acceso API Backend Results" ON public.dynasty_results;
DROP POLICY IF EXISTS "Acceso API Backend Payments" ON public.dynasty_payments;

CREATE POLICY "Acceso API Backend Users" ON public.dynasty_users FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Acceso API Backend Signals" ON public.dynasty_signals FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Acceso API Backend Results" ON public.dynasty_results FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Acceso API Backend Payments" ON public.dynasty_payments FOR ALL USING (true) WITH CHECK (true);
