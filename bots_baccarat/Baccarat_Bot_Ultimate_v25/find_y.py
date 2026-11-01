import cv2
import numpy as np

img = cv2.imread(r'C:\Users\raulr\.gemini\antigravity\brain\c092e343-e253-44fd-8235-e2dee78d8ff5\.user_uploaded\media_1789602878899.jpg')
H, W, _ = img.shape

# Let us find top and bottom Y of the 4 cards
# In card 1 (x in 10..240):
c1_rows = img[50:240, 20:230].mean(axis=(1,2))
# Print where it transitions from outer background to card
for y in range(50, 70):
    print(f'y={y}: {img[y, 100]}')
for y in range(210, 230):
    print(f'y={y}: {img[y, 100]}')
