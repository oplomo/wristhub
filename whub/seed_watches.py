
import os, sys, uuid
from decimal import Decimal

sys.path.insert(0, r"C:\Users\Square\uni\projects\wrist-hub")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "whub.settings")

import django
django.setup()

from wshop.models import Brand, Category, Watch


BRANDS = [
    "Omega", "Rolex", "Seiko", "Citizen", "Tag Heuer",
    "Tissot", "Longines", "Cartier", "Breitling", "Hamilton",
    "Casio", "Fossil", "Movado", "Rado", "Mido",
    "Oris", "Breguet", "Zenith", "Grand Seiko", "Nomos",
]

CATEGORIES = [
    "Classic", "Sport", "Luxury", "Dress", "Diver", "Chronograph", "Vandross",
]


def slugify(name):
    return name.lower().replace(" ", "-").replace(",", "").replace("'", "")


def sku(brand, name):
    return f"{brand[:3].upper()}-{name[:3].upper()}-{str(uuid.uuid4())[:8].upper()}"


for name in BRANDS:
    Brand.objects.get_or_create(
        name=name, defaults={"slug": slugify(name), "is_active": True}
    )
    print(f"Brand: {name}")

for name in CATEGORIES:
    Category.objects.get_or_create(
        name=name, defaults={"slug": slugify(name), "is_active": True}
    )
    print(f"Category: {name}")


WATCHES = [
    {
        "name": "Seamaster Planet Ocean",
        "brand": "Omega",
        "category": "Diver",
        "model": "diver",
        "gender": "men",
        "movement": "automatic",
        "strap_material": "metal",
        "strap_color": "silver",
        "case_size_mm": 43,
        "water_resistance_m": 600,
        "price": "5200.00",
        "stock": 12,
    },
    {
        "name": "Submariner Date",
        "brand": "Rolex",
        "category": "Diver",
        "model": "diver",
        "gender": "men",
        "movement": "automatic",
        "strap_material": "metal",
        "strap_color": "black",
        "case_size_mm": 41,
        "water_resistance_m": 300,
        "price": "10500.00",
        "stock": 5,
    },
    {
        "name": "Presage Cocktail Time",
        "brand": "Seiko",
        "category": "Classic",
        "model": "classic",
        "gender": "unisex",
        "movement": "automatic",
        "strap_material": "leather",
        "strap_color": "brown",
        "case_size_mm": 40,
        "water_resistance_m": 50,
        "price": "425.00",
        "stock": 20,
    },
    {
        "name": "Eco-Drive Promaster",
        "brand": "Citizen",
        "category": "Sport",
        "model": "sport",
        "gender": "men",
        "movement": "solar",
        "strap_material": "rubber",
        "strap_color": "black",
        "case_size_mm": 44,
        "water_resistance_m": 200,
        "price": "295.00",
        "stock": 35,
    },
    {
        "name": "Carrera Chronograph",
        "brand": "Tag Heuer",
        "category": "Chronograph",
        "model": "chronograph",
        "gender": "men",
        "movement": "automatic",
        "strap_material": "leather",
        "strap_color": "brown",
        "case_size_mm": 41,
        "water_resistance_m": 100,
        "price": "3200.00",
        "stock": 8,
    },
    {
        "name": "Le Locle Automatic",
        "brand": "Tissot",
        "category": "Dress",
        "model": "dress",
        "gender": "unisex",
        "movement": "automatic",
        "strap_material": "leather",
        "strap_color": "black",
        "case_size_mm": 39,
        "water_resistance_m": 30,
        "price": "675.00",
        "stock": 15,
    },
    {
        "name": "Master Collection",
        "brand": "Longines",
        "category": "Classic",
        "model": "classic",
        "gender": "men",
        "movement": "automatic",
        "strap_material": "metal",
        "strap_color": "silver",
        "case_size_mm": 42,
        "water_resistance_m": 50,
        "price": "1850.00",
        "stock": 10,
    },
    {
        "name": "Ballon Bleu de Cartier",
        "brand": "Cartier",
        "category": "Luxury",
        "model": "luxury",
        "gender": "unisex",
        "movement": "quartz",
        "strap_material": "leather",
        "strap_color": "black",
        "case_size_mm": 36,
        "water_resistance_m": 30,
        "price": "6500.00",
        "stock": 4,
    },
    {
        "name": "Navitimer Chrono",
        "brand": "Breitling",
        "category": "Chronograph",
        "model": "chronograph",
        "gender": "men",
        "movement": "automatic",
        "strap_material": "metal",
        "strap_color": "silver",
        "case_size_mm": 43,
        "water_resistance_m": 200,
        "price": "8900.00",
        "stock": 6,
    },
    {
        "name": "Khaki Field Mechanical",
        "brand": "Hamilton",
        "category": "Classic",
        "model": "classic",
        "gender": "unisex",
        "movement": "mechanical",
        "strap_material": "leather",
        "strap_color": "brown",
        "case_size_mm": 38,
        "water_resistance_m": 50,
        "price": "575.00",
        "stock": 18,
    },
    {
        "name": "G-Shock Mudmaster",
        "brand": "Casio",
        "category": "Sport",
        "model": "sport",
        "gender": "men",
        "movement": "quartz",
        "strap_material": "rubber",
        "strap_color": "black",
        "case_size_mm": 54,
        "water_resistance_m": 200,
        "price": "350.00",
        "stock": 40,
    },
    {
        "name": "Neutra Chronograph",
        "brand": "Fossil",
        "category": "Dress",
        "model": "dress",
        "gender": "women",
        "movement": "quartz",
        "strap_material": "leather",
        "strap_color": "white",
        "case_size_mm": 38,
        "water_resistance_m": 30,
        "price": "145.00",
        "stock": 25,
    },
    {
        "name": "Museum Classic Dial",
        "brand": "Movado",
        "category": "Luxury",
        "model": "luxury",
        "gender": "women",
        "movement": "quartz",
        "strap_material": "leather",
        "strap_color": "black",
        "case_size_mm": 28,
        "water_resistance_m": 30,
        "price": "695.00",
        "stock": 12,
    },
    {
        "name": "True Automatic",
        "brand": "Rado",
        "category": "Classic",
        "model": "classic",
        "gender": "men",
        "movement": "automatic",
        "strap_material": "metal",
        "strap_color": "silver",
        "case_size_mm": 39,
        "water_resistance_m": 50,
        "price": "1450.00",
        "stock": 7,
    },
    {
        "name": "Multifort Patrimony",
        "brand": "Mido",
        "category": "Chronograph",
        "model": "chronograph",
        "gender": "men",
        "movement": "automatic",
        "strap_material": "leather",
        "strap_color": "black",
        "case_size_mm": 42,
        "water_resistance_m": 100,
        "price": "1300.00",
        "stock": 9,
    },
    {
        "name": "Aquis Date Diver",
        "brand": "Oris",
        "category": "Diver",
        "model": "diver",
        "gender": "men",
        "movement": "automatic",
        "strap_material": "metal",
        "strap_color": "silver",
        "case_size_mm": 43,
        "water_resistance_m": 300,
        "price": "2250.00",
        "stock": 11,
    },
    {
        "name": "Reine de Naples",
        "brand": "Breguet",
        "category": "Luxury",
        "model": "luxury",
        "gender": "women",
        "movement": "quartz",
        "strap_material": "leather",
        "strap_color": "gold",
        "case_size_mm": 35,
        "water_resistance_m": 30,
        "price": "12800.00",
        "stock": 3,
    },
    {
        "name": "Chronomaster Open",
        "brand": "Zenith",
        "category": "Chronograph",
        "model": "chronograph",
        "gender": "men",
        "movement": "automatic",
        "strap_material": "leather",
        "strap_color": "brown",
        "case_size_mm": 41,
        "water_resistance_m": 60,
        "price": "7600.00",
        "stock": 4,
    },
    {
        "name": "Spring Drive Snowflake",
        "brand": "Grand Seiko",
        "category": "Classic",
        "model": "classic",
        "gender": "unisex",
        "movement": "automatic",
        "strap_material": "leather",
        "strap_color": "blue",
        "case_size_mm": 41,
        "water_resistance_m": 100,
        "price": "6200.00",
        "stock": 5,
    },
    {
        "name": "Tangente neomatik",
        "brand": "Nomos",
        "category": "Dress",
        "model": "dress",
        "gender": "unisex",
        "movement": "automatic",
        "strap_material": "leather",
        "strap_color": "black",
        "case_size_mm": 35,
        "water_resistance_m": 50,
        "price": "1780.00",
        "stock": 8,
    },
    {
        "name": "Heritage Series 174",
        "brand": "Vandross",
        "category": "Vandross",
        "model": "vandross",
        "gender": "men",
        "movement": "automatic",
        "strap_material": "metal",
        "strap_color": "rose_gold",
        "case_size_mm": 42,
        "water_resistance_m": 50,
        "price": "850.00",
        "stock": 14,
    },
]

created = 0
for w in WATCHES:
    brand_obj, _ = Brand.objects.get_or_create(name=w["brand"], defaults={"slug": slugify(w["brand"]), "is_active": True})
    category_obj, _ = Category.objects.get_or_create(name=w["category"], defaults={"slug": slugify(w["category"]), "is_active": True})

    watch = Watch(
        name=w["name"],
        slug=slugify(w["name"]),
        brand=brand_obj,
        category=category_obj,
        model=w["model"],
        gender=w["gender"],
        movement=w["movement"],
        strap_material=w["strap_material"],
        strap_color=w["strap_color"],
        case_size_mm=w["case_size_mm"],
        water_resistance_m=w["water_resistance_m"],
        price=Decimal(w["price"]),
        stock=w["stock"],
        sku=sku(w["brand"], w["name"]),
        is_active=True,
    )
    watch.save()
    created += 1
    print(f"Created: {watch.name} ({watch.brand.name})")

print(f"\nTotal watches created: {created}")
print(f"Total watches in DB: {Watch.objects.count()}")
