# Respaldo Completo de Bots Baccarat (Bot Logro + Bot Version Final)

Este directorio contiene **toda la lógica, calibraciones (1366x768), plantillas OCR, credenciales de Telegram/Supabase y lanzadores** de todos tus bots de Baccarat:

1. **`Bot_Logro/`**:
   - Inteligencia táctica tiro a tiro (1 sola jugada por mano, cero secuencias fijas de 6 colores).
   - **Autoridad Única de Mesa en Vivo**: Cierra procesos duplicados al iniciar, descarta mesas abandonadas (`abandoned_tables`) cuando cambia de mesa, y solo evalúa/marca `WIN` en la última mesa enviada en vivo.
   - **Tiempo Completo Garantizado (15s)**: Sincroniza cada disparo (tanto Intento 1 como Cambios de Mesa) con el cierre exacto de la mano previa.
   - **Espera Estricta de 4, 5 o 6 Cartas (incluyendo cartas acostadas)**: Solo decide cuando aparece el Listón Oficial sobre el centro del Road.
   - **Modo Automático (`--con-apuestas --usd`)**: Apuesta inicial de `$0.20` (primera moneda a la izquierda `x=511, y=734`), progresión de **8 Tiros** donde los Tiros 1 al 7 doblan (`$0.20 -> $0.40 -> $0.80 -> $1.60 -> $3.20 -> $6.40 -> $12.80`) y el **Tiro 8 juega la misma cantidad del Tiro 7 (`$12.80`)** como tiro de recuperación. Si gana el 8 sigue jugando (Sin Stop-Profit); si pierde el 8 se detiene automáticamente.
2. **`Bot_Version_Final/`**:
   - Versión clásica con secuencias de 6 colores y apuestas automáticas.
3. **`Baccarat_Bot_Ultimate_v25/`** y **`Baccarat_Bot_Pensante_Venta/`**:
   - Versiones previas de respaldo.
4. **`Accesos_Escritorio/`**:
   - Copias de todos los `.bat` del escritorio.

---

## 🚀 Cómo desplegar en tu nueva computadora

1. Instala **Python 3.11 o 3.12** en la nueva computadora (marcando la casilla *"Add Python to PATH"*).
2. Clona el repositorio:
   ```bash
   git clone https://github.com/adrian2004solano-alt/BaccaratDynasty.git
   ```
3. Entra a la carpeta `BaccaratDynasty\bots_baccarat` y haz doble clic en:
   - **`INSTALAR_EN_NUEVA_PC.bat`**
4. El instalador copiará automáticamente `Bot_Logro` y `Bot_Version_Final` a tu carpeta `Downloads`, instalará las librerías necesarias y creará todos los accesos directos en tu Escritorio listos para usar.
