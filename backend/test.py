import cv2
from cv2 import dnn_superres

sr = dnn_superres.DnnSuperResImpl_create()
print("Loaded superres:", sr)
