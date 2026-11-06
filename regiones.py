"""
Configuración de las regiones que se pueden consultar en la app.

Cada región tiene:
- caja:          rectángulo geográfico (lat_min, lat_max, lon_min, lon_max) que se le
                 pide a la API del USGS. Es un rectángulo, así que también trae
                 sismos de países vecinos.
- patron_pais:   expresión regular que se busca en el texto "place" del USGS para
                 quedarse solo con los sismos del país (ej. "... of Bucaramanga, Colombia").
- zona_horaria:  para mostrar las fechas en hora local.
- centro, zoom:  cómo se centra el mapa al abrir.
- ciudades:      ciudades principales con su (latitud, longitud) para la pestaña "Mi ciudad".
"""

REGIONES = {
    "Colombia": {
        "caja": (-4.3, 13.5, -82.0, -66.8),
        "patron_pais": r"Colombia",
        "zona_horaria": "America/Bogota",
        "centro": (4.6, -74.0),
        "zoom": 4.3,
        "ciudades": {
            "Bogotá": (4.7110, -74.0721),
            "Medellín": (6.2442, -75.5812),
            "Cali": (3.4516, -76.5320),
            "Barranquilla": (10.9685, -74.7813),
            "Cartagena": (10.3910, -75.4794),
            "Bucaramanga": (7.1193, -73.1227),
            "Cúcuta": (7.8939, -72.5078),
            "Pereira": (4.8133, -75.6961),
            "Manizales": (5.0703, -75.5138),
            "Armenia": (4.5339, -75.6811),
            "Ibagué": (4.4389, -75.2322),
            "Pasto": (1.2136, -77.2811),
            "Popayán": (2.4448, -76.6147),
            "Villavicencio": (4.1420, -73.6266),
            "Neiva": (2.9273, -75.2819),
            "Santa Marta": (11.2408, -74.1990),
            "Tunja": (5.5353, -73.3678),
            "Quibdó": (5.6947, -76.6611),
        },
    },
    "California (EE. UU.)": {
        "caja": (32.4, 42.1, -124.6, -114.1),
        "patron_pais": r", CA$|California",
        "zona_horaria": "America/Los_Angeles",
        "centro": (37.0, -119.5),
        "zoom": 4.8,
        "ciudades": {
            "Los Ángeles": (34.0522, -118.2437),
            "San Francisco": (37.7749, -122.4194),
            "San Diego": (32.7157, -117.1611),
            "San José": (37.3382, -121.8863),
            "Sacramento": (38.5816, -121.4944),
            "Fresno": (36.7378, -119.7871),
            "Ridgecrest": (35.6225, -117.6709),
        },
    },
    "Alaska (EE. UU.)": {
        "caja": (51.0, 71.5, -180.0, -129.0),
        "patron_pais": r"Alaska",
        "zona_horaria": "America/Anchorage",
        "centro": (60.0, -152.0),
        "zoom": 3.3,
        "ciudades": {
            "Anchorage": (61.2181, -149.9003),
            "Fairbanks": (64.8378, -147.7164),
            "Juneau": (58.3019, -134.4197),
            "Kodiak": (57.7900, -152.4072),
        },
    },
    "Puerto Rico": {
        "caja": (17.5, 18.8, -68.0, -65.0),
        "patron_pais": r"Puerto Rico",
        "zona_horaria": "America/Puerto_Rico",
        "centro": (18.2, -66.5),
        "zoom": 7.3,
        "ciudades": {
            "San Juan": (18.4655, -66.1057),
            "Ponce": (18.0111, -66.6141),
            "Mayagüez": (18.2013, -67.1397),
            "Arecibo": (18.4724, -66.7157),
            "Guánica": (17.9716, -66.9079),
        },
    },
    "México": {
        "caja": (14.5, 32.8, -118.5, -86.5),
        "patron_pais": r"Mexico|MX$",
        "zona_horaria": "America/Mexico_City",
        "centro": (22.5, -102.0),
        "zoom": 3.9,
        "ciudades": {
            "Ciudad de México": (19.4326, -99.1332),
            "Guadalajara": (20.6597, -103.3496),
            "Monterrey": (25.6866, -100.3161),
            "Puebla": (19.0414, -98.2063),
            "Oaxaca": (17.0732, -96.7266),
            "Acapulco": (16.8531, -99.8237),
            "Tijuana": (32.5149, -117.0382),
            "Mexicali": (32.6245, -115.4523),
        },
    },
    "Chile": {
        "caja": (-56.0, -17.5, -76.0, -66.0),
        "patron_pais": r"Chile",
        "zona_horaria": "America/Santiago",
        "centro": (-35.0, -71.0),
        "zoom": 3.0,
        "ciudades": {
            "Santiago": (-33.4489, -70.6693),
            "Valparaíso": (-33.0472, -71.6127),
            "Concepción": (-36.8270, -73.0503),
            "Antofagasta": (-23.6509, -70.3975),
            "Iquique": (-20.2307, -70.1357),
            "La Serena": (-29.9027, -71.2519),
            "Valdivia": (-39.8142, -73.2459),
        },
    },
    "Perú": {
        "caja": (-18.5, 0.0, -81.5, -68.5),
        "patron_pais": r"Peru",
        "zona_horaria": "America/Lima",
        "centro": (-9.5, -75.0),
        "zoom": 4.2,
        "ciudades": {
            "Lima": (-12.0464, -77.0428),
            "Arequipa": (-16.4090, -71.5375),
            "Trujillo": (-8.1116, -79.0288),
            "Cusco": (-13.5320, -71.9675),
            "Piura": (-5.1945, -80.6328),
            "Tacna": (-18.0066, -70.2463),
            "Ica": (-14.0678, -75.7286),
        },
    },
    "Japón": {
        "caja": (24.0, 46.0, 122.0, 146.0),
        "patron_pais": r"Japan",
        "zona_horaria": "Asia/Tokyo",
        "centro": (36.5, 137.5),
        "zoom": 4.0,
        "ciudades": {
            "Tokio": (35.6762, 139.6503),
            "Osaka": (34.6937, 135.5023),
            "Sendai": (38.2682, 140.8694),
            "Sapporo": (43.0618, 141.3545),
            "Nagoya": (35.1815, 136.9066),
            "Fukuoka": (33.5904, 130.4017),
            "Kobe": (34.6901, 135.1955),
        },
    },
}
