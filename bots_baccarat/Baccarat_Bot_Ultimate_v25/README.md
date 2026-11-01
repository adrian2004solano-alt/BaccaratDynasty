# ?? Bot de Se?ales Baccarat (Stake -> Telegram)

Bot inteligente desarrollado en **Python** para monitorear mesas de Baccarat en **Stake** (*Baccarat 1, Baccarat 2, Baccarat 3, Baccarat 5 y Baccarat 6*), analizar patrones de juego y enviar alertas de **6 intentos (?? Jugador / ?? Banca)** directamente a tu canal de Telegram.

---

## ?? Gu?a R?pida de Uso

### 1. Probar Conexi?n con Telegram
Para verificar que las se?ales lleguen a tu canal o bot:
```cmd
python test_signal.py
```

### 2. Calibrar o Diagnosticar Mesas
Para comprobar la conexi?n y el estado de las mesas configuradas:
```cmd
calibrate.bat
```
*(O ejecuta `python calibrate.py`)*

### 3. Iniciar el Monitoreo en Vivo
Para abrir Chrome listo para el bot:
1. Haz doble clic en `start_chrome_debug.bat` (abrir? Chrome y Stake).
2. Haz doble clic en `start_bot.bat` (o ejecuta `python main.py`).

---

## ?? Configuraci?n (`.env` y `config.py`)

- **`TELEGRAM_BOT_TOKEN`**: Token del bot de Telegram.
- **`TELEGRAM_CHAT_ID`**: ID del chat o canal receptor (`-1004429971176`).
- **`MIN_SIGNAL_DELAY`**: Tiempo m?nimo entre se?ales (45 segundos por defecto).
- **`MAX_SIGNAL_DELAY`**: Tiempo m?ximo de enfriamiento (60 segundos).
- **`TARGET_TABLES`**: Lista de mesas a monitorear (`Baccarat 1`, `2`, `3`, `5`, `6`).

---

## ?? Formato de la Se?al en Telegram

```text
?? SE?AL CONFIRMADA | BACCARAT VIP ??
???????????????????????????
?? Mesa: Baccarat 5
?? An?lisis: Patr?n Alternado Activo (Ping-Pong 1x1)
?? Asertividad Estimada: 96%
? Entrada: V?lido por 6 intentos
???????????????????????????
?? SECUENCIA RECOMENDADA:
?? ?? ?? ?? ?? ??

1?? ?? JUGADOR
2?? ?? BANCA
3?? ?? JUGADOR
4?? ?? JUGADOR
5?? ?? BANCA
6?? ?? JUGADOR
???????????????????????????
?? INSTRUCCIONES DE JUEGO:
? Sigue la secuencia paso a paso.
? ?Al ganar en cualquier intento, para y espera nueva se?al!
? Gesti?n sugerida: Martingala moderada o apuesta fija.
???????????????????????????
?? Hora: 15:40:00 | ?? Bot Stake Live
```
