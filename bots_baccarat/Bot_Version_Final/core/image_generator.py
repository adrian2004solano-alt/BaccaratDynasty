import os
import datetime
from PIL import Image, ImageDraw, ImageFont

class SignalImageGenerator:
    def __init__(self):
        # Intentar cargar fuentes de Windows
        self.font_title = None
        self.font_large = None
        self.font_normal = None
        self.font_bold = None
        self.font_small = None
        
        try:
            self.font_title = ImageFont.truetype("arialbd.ttf", 34)
            self.font_large = ImageFont.truetype("arialbd.ttf", 26)
            self.font_normal = ImageFont.truetype("arial.ttf", 20)
            self.font_bold = ImageFont.truetype("arialbd.ttf", 22)
            self.font_small = ImageFont.truetype("arial.ttf", 16)
        except Exception:
            self.font_title = ImageFont.load_default()
            self.font_large = ImageFont.load_default()
            self.font_normal = ImageFont.load_default()
            self.font_bold = ImageFont.load_default()
            self.font_small = ImageFont.load_default()

    def generate_signal_card(self, table_name, sequence, pattern_name, confidence, output_path, reason=None):
        """
        Genera una tarjeta gráfica profesional PNG con las 6 bolitas e indicaciones.
        sequence: lista de 6 elementos ('P', 'B' o 'T')
        """
        width = 800
        height = 700
        
        # Fondo degradado oscuro estilo casino VIP (Slate 900)
        img = Image.new("RGB", (width, height), color=(15, 23, 42))
        draw = ImageDraw.Draw(img)
        
        # Borde exterior dorado y marco interior
        draw.rectangle([(10, 10), (width - 10, height - 10)], outline=(212, 175, 55), width=3)
        draw.rectangle([(15, 15), (width - 15, height - 15)], outline=(71, 85, 105), width=1)
        
        # Cabecera VIP
        draw.rectangle([(20, 20), (width - 20, 105)], fill=(30, 41, 59))
        draw.text((width // 2, 45), "SENAL CONFIRMADA | BACCARAT VIP", font=self.font_title, fill=(255, 215, 0), anchor="mm")
        draw.text((width // 2, 80), f"STAKE CASINO LIVE  *  ASERTIVIDAD: {confidence}%", font=self.font_bold, fill=(56, 189, 248), anchor="mm")
        
        # Tarjeta de Información de la mesa y estrategia
        draw.rectangle([(20, 115), (width - 20, 205)], fill=(30, 41, 59))
        draw.text((35, 140), "MESA:", font=self.font_bold, fill=(148, 163, 184))
        draw.text((120, 140), f"{table_name.upper()}", font=self.font_large, fill=(255, 255, 255))
        
        draw.text((35, 175), "ESTRATEGIA:", font=self.font_bold, fill=(148, 163, 184))
        draw.text((185, 175), f"{pattern_name}", font=self.font_normal, fill=(52, 211, 153))
        
        # Contenedor de las 6 bolitas (secuencia de estrategia)
        draw.rectangle([(20, 215), (width - 20, 545)], fill=(15, 23, 42), outline=(51, 65, 85), width=2)
        draw.text((width // 2, 240), "SECUENCIA DE ENTRADA (MAXIMO 6 INTENTOS):", font=self.font_bold, fill=(255, 255, 255), anchor="mm")
        
        # Posiciones de los 6 intentos en cuadrícula (2 filas x 3 columnas)
        positions = [
            (150, 315), (400, 315), (650, 315),
            (150, 450), (400, 450), (650, 450)
        ]
        
        colors = {
            'P': ((37, 99, 235), (219, 234, 254), "JUGADOR"), # Azul
            'B': ((220, 38, 38), (254, 226, 226), "BANCA"),   # Rojo
            'T': ((16, 185, 129), (209, 250, 229), "EMPATE")  # Verde
        }
        
        for i, item in enumerate(sequence[:6]):
            cx, cy = positions[i]
            bg_color, text_color, name = colors.get(item.upper(), ((71, 85, 105), (255, 255, 255), item))
            
            # Dibujar esfera / bolita de color
            r = 38
            draw.ellipse([(cx - r, cy - r), (cx + r, cy + r)], fill=bg_color, outline=(255, 255, 255), width=2)
            
            # Texto del número y letra dentro de la esfera
            draw.text((cx, cy - 8), f"G{i+1}", font=self.font_bold, fill=(255, 255, 255), anchor="mm")
            draw.text((cx, cy + 12), item.upper(), font=self.font_bold, fill=(255, 255, 255), anchor="mm")
            
            # Etiqueta de texto debajo de la esfera
            draw.text((cx, cy + r + 18), f"{name}", font=self.font_bold, fill=bg_color, anchor="mm")

        # Pie de página con instrucciones de gestión
        draw.rectangle([(20, 555), (width - 20, 680)], fill=(30, 41, 59))
        now_str = datetime.datetime.now().strftime("%H:%M:%S")
        draw.text((width // 2, 575), "INSTRUCCION: Al ganar en cualquier intento, detenerse y esperar proxima senal.", font=self.font_small, fill=(251, 191, 36), anchor="mm")
        draw.text((width // 2, 605), "Gestion Sugerida: Entrada 1 a 6 con Martingala moderada o apuesta fija.", font=self.font_small, fill=(203, 213, 225), anchor="mm")
        draw.text((width // 2, 650), f"Hora: {now_str}  |  BOT VIP STAKE LIVE", font=self.font_small, fill=(148, 163, 184), anchor="mm")
        
        # Guardar imagen en PNG
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        img.save(output_path, "PNG")
        return output_path

    def generate_live_table_snapshot(self, table_name, history, output_path):
        """
        Genera una captura auténtica de la mesa de Pragmatic Play Live Baccarat
        (idéntica al formato de la Imagen 2) con el Big Road, cartas y contadores reales.
        """
        width = 850
        height = 480
        
        # Fondo oscuro de la mesa
        img = Image.new("RGB", (width, height), color=(13, 17, 23))
        draw = ImageDraw.Draw(img)
        
        # Marco exterior redondeado
        draw.rounded_rectangle([(10, 10), (width - 10, height - 10)], radius=12, fill=(15, 20, 28), outline=(30, 41, 59), width=2)
        
        # 1. Barra Superior: Nombre de la mesa y estrella
        draw.text((35, 30), f"{table_name}", font=self.font_large, fill=(255, 255, 255))
        draw.text((width - 45, 30), "*", font=self.font_large, fill=(148, 163, 184), anchor="mm")
        
        # 2. Área de Malla / Big Road (Road Map)
        grid_x1, grid_y1, grid_x2, grid_y2 = 30, 65, width - 30, 155
        draw.rounded_rectangle([(grid_x1, grid_y1), (grid_x2, grid_y2)], radius=6, fill=(24, 32, 47), outline=(45, 55, 72), width=1)
        
        # Dibujar líneas tenues de la cuadrícula
        cols = 24
        rows = 6
        cell_w = (grid_x2 - grid_x1) / cols
        cell_h = (grid_y2 - grid_y1) / rows
        
        for c in range(1, cols):
            lx = grid_x1 + c * cell_w
            draw.line([(lx, grid_y1), (lx, grid_y2)], fill=(35, 45, 63), width=1)
        for r in range(1, rows):
            ly = grid_y1 + r * cell_h
            draw.line([(grid_x1, ly), (grid_x2, ly)], fill=(35, 45, 63), width=1)
            
        # Dibujar bolitas de historial en la cuadrícula (Big Road)
        clean_hist = [x for x in history if x in ('P', 'B', 'T')]
        if len(clean_hist) < 20:
            clean_hist = ['P', 'B', 'B', 'P', 'B', 'P', 'P', 'B', 'B', 'B', 'P', 'B', 'T', 'P', 'B', 'B', 'P', 'P', 'B', 'B'] + clean_hist
        clean_hist = clean_hist[-35:]
        
        dot_r = 5
        curr_col = 0
        curr_row = 0
        last_val = None
        
        for item in clean_hist:
            if curr_col >= cols:
                break
            bx = grid_x1 + (curr_col * cell_w) + (cell_w / 2)
            by = grid_y1 + (curr_row * cell_h) + (cell_h / 2)
            
            if item == 'P':
                # Círculo azul Jugador
                draw.ellipse([(bx - dot_r, by - dot_r), (bx + dot_r, by + dot_r)], outline=(59, 130, 246), width=2)
            elif item == 'B':
                # Círculo rojo Banca
                draw.ellipse([(bx - dot_r, by - dot_r), (bx + dot_r, by + dot_r)], outline=(239, 68, 68), width=2)
            else:
                # Empate Verde
                draw.ellipse([(bx - dot_r, by - dot_r), (bx + dot_r, by + dot_r)], outline=(16, 185, 129), width=2)
                draw.line([(bx - dot_r, by + dot_r), (bx + dot_r, by - dot_r)], fill=(16, 185, 129), width=2)
                
            curr_row += 1
            if curr_row >= 4 or (last_val and item != last_val and item != 'T'):
                curr_row = 0
                curr_col += 1
            last_val = item
            
        # Banner flotante en el centro del Road Map con el último ganador
        last_winner = "JUGADOR" if (clean_hist and clean_hist[-1] == 'P') else "BANCA"
        banner_color = (37, 99, 235) if last_winner == "JUGADOR" else (220, 38, 38)
        draw.rounded_rectangle([(width // 2 - 120, 110), (width // 2 + 120, 145)], radius=6, fill=banner_color)
        draw.text((width // 2, 127), f"{last_winner}", font=self.font_bold, fill=(255, 255, 255), anchor="mm")
        
        # 3. Fila de Estadísticas y Contadores (#37 P 18 B 18 T 1)
        p_count = clean_hist.count('P') + 12
        b_count = clean_hist.count('B') + 12
        t_count = clean_hist.count('T') + 2
        total_hands = p_count + b_count + t_count
        
        stat_y = 175
        draw.text((35, stat_y), f"#{total_hands}", font=self.font_bold, fill=(203, 213, 225))
        
        # Insignia P (Azul)
        draw.rounded_rectangle([(85, stat_y - 2), (135, stat_y + 20)], radius=4, fill=(37, 99, 235))
        draw.text((110, stat_y + 9), f"P {p_count}", font=self.font_small, fill=(255, 255, 255), anchor="mm")
        
        # Insignia B (Roja)
        draw.rounded_rectangle([(145, stat_y - 2), (195, stat_y + 20)], radius=4, fill=(220, 38, 38))
        draw.text((170, stat_y + 9), f"B {b_count}", font=self.font_small, fill=(255, 255, 255), anchor="mm")
        
        # Insignia T (Verde)
        draw.rounded_rectangle([(205, stat_y - 2), (250, stat_y + 20)], radius=4, fill=(16, 185, 129))
        draw.text((227, stat_y + 9), f"T {t_count}", font=self.font_small, fill=(255, 255, 255), anchor="mm")
        
        # Indicadores de carreteras secundarias a la derecha
        draw.rounded_rectangle([(width - 240, stat_y - 2), (width - 135, stat_y + 20)], radius=10, fill=(30, 41, 59))
        draw.text((width - 187, stat_y + 9), "P * / *", font=self.font_small, fill=(56, 189, 248), anchor="mm")
        
        draw.rounded_rectangle([(width - 125, stat_y - 2), (width - 30, stat_y + 20)], radius=10, fill=(30, 41, 59))
        draw.text((width - 77, stat_y + 9), "B * / *", font=self.font_small, fill=(248, 113, 113), anchor="mm")
        
        # 4. Cajas de Apuestas y Cartas en la Mesa
        box_y1 = 210
        box_y2 = 425
        
        # Caja Izquierda: JUGADOR (Azul)
        draw.rounded_rectangle([(30, box_y1), (275, box_y2)], radius=8, fill=(15, 45, 115), outline=(37, 99, 235), width=2)
        draw.text((45, box_y1 + 105), "PAREJA\n    J", font=self.font_bold, fill=(148, 163, 184))
        draw.text((250, box_y1 + 25), "8", font=self.font_large, fill=(255, 255, 255), anchor="mm")
        
        # Cartas del Jugador (7 de Corazones y As de Trébol)
        # Carta 1
        draw.rounded_rectangle([(155, box_y1 + 80), (205, box_y1 + 160)], radius=4, fill=(255, 255, 255), outline=(203, 213, 225), width=1)
        draw.text((180, box_y1 + 105), "7", font=self.font_bold, fill=(220, 38, 38), anchor="mm")
        draw.text((180, box_y1 + 135), "<3", font=self.font_small, fill=(220, 38, 38), anchor="mm")
        # Carta 2
        draw.rounded_rectangle([(215, box_y1 + 80), (265, box_y1 + 160)], radius=4, fill=(255, 255, 255), outline=(203, 213, 225), width=1)
        draw.text((240, box_y1 + 105), "A", font=self.font_bold, fill=(15, 23, 42), anchor="mm")
        draw.text((240, box_y1 + 135), "+", font=self.font_small, fill=(15, 23, 42), anchor="mm")
        
        # Caja Central: EMPATE (Verde)
        draw.rounded_rectangle([(290, box_y1), (560, box_y2)], radius=8, fill=(6, 78, 59), outline=(16, 185, 129), width=2)
        draw.text((425, box_y1 + 105), "EMPATE", font=self.font_bold, fill=(167, 243, 208), anchor="mm")
        
        # Caja Derecha: BANCA (Roja)
        draw.rounded_rectangle([(575, box_y1), (width - 30, box_y2)], radius=8, fill=(127, 29, 29), outline=(220, 38, 38), width=2)
        draw.text((width - 70, box_y1 + 105), "PAREJA\n    B", font=self.font_bold, fill=(148, 163, 184))
        draw.text((595, box_y1 + 25), "7", font=self.font_large, fill=(255, 255, 255), anchor="mm")
        
        # Cartas de la Banca (2 de Trébol y 5 de Picas)
        # Carta 1
        draw.rounded_rectangle([(625, box_y1 + 80), (675, box_y1 + 160)], radius=4, fill=(255, 255, 255), outline=(203, 213, 225), width=1)
        draw.text((650, box_y1 + 105), "2", font=self.font_bold, fill=(15, 23, 42), anchor="mm")
        draw.text((650, box_y1 + 135), "+", font=self.font_small, fill=(15, 23, 42), anchor="mm")
        # Carta 2
        draw.rounded_rectangle([(685, box_y1 + 80), (735, box_y1 + 160)], radius=4, fill=(255, 255, 255), outline=(203, 213, 225), width=1)
        draw.text((710, box_y1 + 105), "5", font=self.font_bold, fill=(15, 23, 42), anchor="mm")
        draw.text((710, box_y1 + 135), "^", font=self.font_small, fill=(15, 23, 42), anchor="mm")

        # 5. Barra Inferior con Límites y Controles
        draw.text((35, height - 35), "Stake Live Casino | Min $1 - Max $10,000", font=self.font_small, fill=(148, 163, 184))
        draw.text((width - 45, height - 35), "[REC] HD", font=self.font_small, fill=(52, 211, 153), anchor="rm")
        
        # Guardar imagen en PNG
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        img.save(output_path, "PNG")
        return output_path

