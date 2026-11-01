import cv2
import numpy as np

img = cv2.imread(r'C:\Users\raulr\.gemini\antigravity\brain\c092e343-e253-44fd-8235-e2dee78d8ff5\.user_uploaded\media_1789602878899.jpg')
H, W, _ = img.shape
print(f'Original dimensions: W={W}, H={H}')

# Let us find the card bounding boxes.
# Each card has a top border at y around 60 and bottom around 220.
# Let's inspect horizontal line at y=60:
# Cards have a distinctive dark border / background.
# Let's check columns:
# Card 1: Baccarat 2
# Card 2: Baccarat 1
# Card 3: Baccarat 3
# Card 4: Baccarat 5

# Let's find the card container boundaries by checking brightness/edges
# In the y range [60, 220], the cards have dark background (RGB ~ 18, 18, 18) with a 1px border.
gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

# Check vertical profiles:
col_sums = gray[65:215, :].mean(axis=0)
# Cards are visible between x=2 and x=1014
# There are 3 gaps between the 4 cards.
# Let's print the card columns:
for col_idx in [0, 1, 2, 250, 251, 252, 253, 254, 255, 256, 504, 505, 506, 507, 508, 509, 510, 758, 759, 760, 761, 762, 763, 764, 1012, 1013, 1014, 1015]:
    if col_idx < W:
        print(f'x={col_idx}: mean={col_sums[col_idx]:.1f}')
