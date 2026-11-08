from PIL import Image

img = Image.open("backend/uploads/handwritten/10/source/bf52e322cce0a39def5e858e7c70a25d.jpg")
print(f"Doc 10 image: size={img.size}, format={img.format}")

# Let's also check Doc 13
img13 = Image.open("backend/uploads/handwritten/13/source/Complete-PYhton-Handwritten-Notes-28-11.webp")
print(f"Doc 13 image: size={img13.size}, format={img13.format}")

