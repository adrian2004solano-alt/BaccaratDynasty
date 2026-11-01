import cv2
import numpy as np

img = cv2.imread(r'C:\Users\raulr\.gemini\antigravity\brain\c092e343-e253-44fd-8235-e2dee78d8ff5\.user_uploaded\media_1789602878899.jpg')
H, W, _ = img.shape

# Bottom row has chips around y in [600, 640]
# Chip '0,2' has a bright red/salmon ring around it
bottom_strip = img[590:644, :]
cv2.imwrite('bottom_strip.png', bottom_strip)

# Find circular contours or red ring in bottom strip
red_ring = (img[590:644, :, 2] > 200) & (img[590:644, :, 0] > 100) & (img[590:644, :, 1] < 150)
y_idxs, x_idxs = np.where(red_ring)
if len(x_idxs) > 0:
    print(f'Chip 0,2 ring center: X={int(x_idxs.mean())}, Y={int(y_idxs.mean()) + 590}')
else:
    print('Red ring not found with simple filter')

# Let us check chip positions:
# In bottom_strip, chips are in the middle: x ~ 350 to 650
# Let us crop the chips area and save it
cv2.imwrite('chips_area.png', img[590:644, 340:650])
print('Saved chips_area.png')
