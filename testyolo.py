from ultralytics import YOLO
import cv2

#model de comparaison
model = YOLO("yolov8n.pt")

#image à analyser
image_path = "tuture.jpg"
image = cv2.imread(image_path)

#si ya pas l'image
if image is None:
    print("Erreur")
    exit()

#faire la comparaison entre l'image à analyser et le model de comparaison
results = model(image)

#annoter l'image
annotated_image = results[0].plot()

#redimensionner l'image en /2
height, width = annotated_image.shape[:2]

scale = 0.5  # réduire à 50%
new_width = int(width * scale)
new_height = int(height * scale)

resized_image = cv2.resize(annotated_image, (new_width, new_height))
#affichge
cv2.imshow("YOLO Detection", resized_image)

cv2.waitKey(0)
cv2.destroyAllWindows()
import cv2