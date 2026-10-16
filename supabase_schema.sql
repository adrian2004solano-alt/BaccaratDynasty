-- ============================================================================
-- BACCARAT DYNASTY VIP — ESQUEMA DE BASE DE DATOS PARA SUPABASE (PostgreSQL)
-- Proyecto: https://fevrpdoitikbosvrezxi.supabase.co
-- Instrucciones: Copia y pega este script en el "SQL Editor" de tu Supabase
-- y presiona "RUN" para crear todas las tablas y activar Tiempo Real.
-- ============================================================================

-- 1. Tabla de Usuarios y Membresías
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
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 2. Tabla de Señales en Vivo (Enviadas desde el Bot de PC)
CREATE TABLE IF NOT EXISTS public.dynasty_signals (
    id BIGSERIAL PRIMARY KEY,
    table_name TEXT NOT NULL,
    sequence JSONB NOT NULL, -- Ej: ["P", "B", "B", "B", "B", "P"]
    probability INTEGER DEFAULT 92,
    strategy_name TEXT DEFAULT 'DYNASTY_VIP',
    reference_image_b64 TEXT, -- Captura del resultado anterior (Referencia)
    base_hand_count INTEGER DEFAULT 0,
    current_attempt INTEGER DEFAULT 1,
    status TEXT DEFAULT 'active', -- 'active', 'win', 'loss'
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 3. Tabla de Resultados Oficiales (100% Gratis para todos los usuarios)
CREATE TABLE IF NOT EXISTS public.dynasty_results (
    id BIGSERIAL PRIMARY KEY,
    table_name TEXT NOT NULL,
    result_type TEXT NOT NULL, -- 'win' o 'loss'
    attempt_number INTEGER DEFAULT 1,
    strategy_name TEXT,
    screenshot_b64 TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 4. Tabla de Pagos en USDT (Para aprobar desde el Panel Admin)
CREATE TABLE IF NOT EXISTS public.dynasty_payments (
    id BIGSERIAL PRIMARY KEY,
    user_email TEXT NOT NULL,
    plan_name TEXT NOT NULL, -- 'VIP_30_DIAS' o 'VIP_7_DIAS'
    amount_usdt NUMERIC(10, 2) NOT NULL,
    txid TEXT NOT NULL,
    status TEXT DEFAULT 'pending', -- 'pending', 'approved', 'rejected'
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Habilitar acceso desde la API de Supabase
ALTER TABLE public.dynasty_users ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.dynasty_signals ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.dynasty_results ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.dynasty_payments ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Acceso API Backend Users" ON public.dynasty_users FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Acceso API Backend Signals" ON public.dynasty_signals FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Acceso API Backend Results" ON public.dynasty_results FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Acceso API Backend Payments" ON public.dynasty_payments FOR ALL USING (true) WITH CHECK (true);
