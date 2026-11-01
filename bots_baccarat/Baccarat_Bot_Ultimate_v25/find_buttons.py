import cv2

img = cv2.imread(r'C:\Users\raulr\.gemini\antigravity\brain\c092e343-e253-44fd-8235-e2dee78d8ff5\.user_uploaded\media_1789602878899.jpg')

tables = [
    ('Baccarat 2', 2, 253),
    ('Baccarat 1', 256, 507),
    ('Baccarat 3', 510, 761),
    ('Baccarat 5', 764, 1015),
]

for name, x1, x2 in tables:
    jugador_cx = x1 + 70
    jugador_cy = 173
    banca_cx = x1 + 178
    banca_cy = 173
    print(name + ':')
    print('  Card Box: x=' + str(x1) + ', y=60, w=' + str(x2-x1) + ', h=163')
    print('  Jugador Center: (' + str(jugador_cx) + ', ' + str(jugador_cy) + ')')
    print('  Banca   Center: (' + str(banca_cx) + ', ' + str(banca_cy) + ')')
