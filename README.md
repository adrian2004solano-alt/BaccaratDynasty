# 👑 Baccarat Dynasty VIP — Plataforma Web de Señales en Vivo

Plataforma SaaS oficial conectada al Bot Automatizado de Baccarat y sincronizada con **Supabase**.

## 🛡️ Características Principales
1. **Señales en Tiempo Real (Exclusivo VIP):**
   - Muestra la mesa seleccionada, la **captura de referencia previa** (resultado de la jugada anterior), el plan de 6 tiros (Jugador/Banca) y el temporizador de 15 segundos con alerta sonora.
2. **Resultados Oficiales 100% Gratuitos:**
   - Todos los visitantes ven los resultados en vivo (`WIN` / `LOSS`) como embudo de conversión hacia la membresía VIP.
3. **Seguridad Anti-Cuentas Compartidas ("La Vieja Confiable"):**
   - **Verificación de correo electrónico** con código de 6 dígitos (OTP) en base de datos.
   - **Device Fingerprinting:** Reconoce el equipo físico del usuario aunque viaje o cambie de IP (máximo 2 dispositivos por cuenta).
   - **Sesión Única Simultánea:** Si una segunda persona entra con la misma cuenta, el servidor cierra en vivo la pantalla del primer dispositivo.
4. **Pagos en USDT + Panel de Administrador:**
   - Los usuarios reportan su pago USDT (TRC20) y el Administrador activa sus 30 días o 7 días VIP con un solo clic.

## 🚀 Cómo Iniciar
1. Ejecuta `INICIAR_PLATAFORMA.bat` o corre:
   ```bash
   python server.py
   ```
2. Abre `http://localhost:5000` en tu navegador.
3. En Supabase (`https://fevrpdoitikbosvrezxi.supabase.co`), abre el **SQL Editor** y ejecuta el contenido de `supabase_schema.sql`.
