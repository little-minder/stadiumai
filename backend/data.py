"""
StadiumAI - mock data layer.

In production this would be backed by MongoDB/Firebase + live IoT/CCTV feeds.
For this demo everything lives in memory so the whole stack runs with zero
external dependencies (no DB, no API keys, no internet required).
"""
import random

ZONES = ["A", "B", "C", "D", "E", "F", "G", "H"]

GATES = [
    {"id": f"GATE-{z}", "zone": z, "name": f"Gate {z}", "x": i, "y": 0}
    for i, z in enumerate(ZONES)
]

FACILITIES = [
    {"id": "R1", "type": "restroom", "name": "Restroom - North Concourse", "zone": "A", "x": 1, "y": 2},
    {"id": "R2", "type": "restroom", "name": "Restroom - South Concourse", "zone": "E", "x": 5, "y": 6},
    {"id": "R3", "type": "restroom", "name": "Restroom - East Wing", "zone": "C", "x": 7, "y": 3},
    {"id": "W1", "type": "water", "name": "Water Station 1", "zone": "B", "x": 2, "y": 1},
    {"id": "W2", "type": "water", "name": "Water Station 2", "zone": "F", "x": 6, "y": 5},
    {"id": "M1", "type": "medical", "name": "Medical Room - Level 1", "zone": "D", "x": 4, "y": 4, "team": "Team Alpha", "available": True},
    {"id": "M2", "type": "medical", "name": "Medical Room - Level 2", "zone": "G", "x": 6, "y": 2, "team": "Team Bravo", "available": True},
    {"id": "X1", "type": "exit", "name": "Exit Gate North", "zone": "A", "x": 0, "y": 0},
    {"id": "X2", "type": "exit", "name": "Exit Gate South", "zone": "E", "x": 5, "y": 7},
    {"id": "X3", "type": "exit", "name": "Exit Gate East", "zone": "H", "x": 7, "y": 0},
    {"id": "S1", "type": "shop", "name": "Official Merch Store", "zone": "C", "x": 3, "y": 3},
    {"id": "S2", "type": "shop", "name": "Fan Jersey Kiosk", "zone": "F", "x": 6, "y": 4},
]

FOOD_STALLS = [
    {"id": "F1", "name": "World Cup Burgers", "zone": "A", "base_wait": 6, "menu": [
        {"id": "F1-1", "name": "Cheeseburger", "price": 220},
        {"id": "F1-2", "name": "Fries", "price": 120},
        {"id": "F1-3", "name": "Cola", "price": 80},
    ]},
    {"id": "F2", "name": "Pizza Corner", "zone": "B", "base_wait": 8, "menu": [
        {"id": "F2-1", "name": "Margherita Slice", "price": 150},
        {"id": "F2-2", "name": "Pepperoni Slice", "price": 180},
        {"id": "F2-3", "name": "Garlic Bread", "price": 110},
    ]},
    {"id": "F3", "name": "Noodle Bar", "zone": "C", "base_wait": 5, "menu": [
        {"id": "F3-1", "name": "Stir-fry Noodles", "price": 190},
        {"id": "F3-2", "name": "Spring Rolls", "price": 130},
        {"id": "F3-3", "name": "Iced Tea", "price": 70},
    ]},
    {"id": "F4", "name": "Taco Fiesta", "zone": "D", "base_wait": 7, "menu": [
        {"id": "F4-1", "name": "Beef Taco", "price": 160},
        {"id": "F4-2", "name": "Nachos", "price": 170},
        {"id": "F4-3", "name": "Lemonade", "price": 75},
    ]},
    {"id": "F5", "name": "Healthy Bowls", "zone": "E", "base_wait": 4, "menu": [
        {"id": "F5-1", "name": "Grain Bowl", "price": 210},
        {"id": "F5-2", "name": "Fruit Cup", "price": 100},
        {"id": "F5-3", "name": "Protein Shake", "price": 140},
    ]},
    {"id": "F6", "name": "Curry House", "zone": "F", "base_wait": 9, "menu": [
        {"id": "F6-1", "name": "Chicken Curry", "price": 260},
        {"id": "F6-2", "name": "Rice", "price": 90},
        {"id": "F6-3", "name": "Masala Chai", "price": 60},
    ]},
]

PARKING_ZONES = [
    {"id": "P1", "name": "Parking Zone North", "capacity": 400},
    {"id": "P2", "name": "Parking Zone South", "capacity": 350},
    {"id": "P3", "name": "Parking Zone East", "capacity": 300},
    {"id": "P4", "name": "Parking Zone West", "capacity": 250},
]

SCHEDULE = [
    {"id": "M1", "teams": "Brazil vs Argentina", "time": "2026-07-10T18:00:00", "stadium_gate_open": "16:00"},
    {"id": "M2", "teams": "France vs Germany", "time": "2026-07-11T15:00:00", "stadium_gate_open": "13:00"},
    {"id": "M3", "teams": "Spain vs Portugal", "time": "2026-07-12T20:00:00", "stadium_gate_open": "18:00"},
]

# Lightweight knowledge base for the RAG-lite fan assistant.
STADIUM_DOCS = [
    {
        "id": "doc-seating",
        "title": "Seat Directions",
        "text": "Sections 100-199 are lower bowl, accessible from Gates A-D. "
                "Sections 200-299 are club level, accessible from Gates C-F via escalators. "
                "Sections 300-399 are upper bowl, accessible from Gates E-H.",
    },
    {
        "id": "doc-parking",
        "title": "Parking Guidance",
        "text": "Parking Zone North (P1) is closest to Gates A-B. Parking Zone South (P2) "
                "serves Gates D-E. Zone East (P3) serves Gates F-G. Zone West (P4) serves Gate H. "
                "Arrive 2 hours before kickoff to avoid congestion.",
    },
    {
        "id": "doc-food",
        "title": "Food & Beverage",
        "text": "Food stalls are located in every concourse zone A-F. Healthy Bowls and Noodle Bar "
                "typically have the shortest wait times. Mobile ordering is available to skip lines.",
    },
    {
        "id": "doc-facilities",
        "title": "Facilities",
        "text": "Restrooms are located near Gates A, C and E. Water stations are free and located "
                "near Gates B and F. Medical rooms are on Level 1 (Zone D) and Level 2 (Zone G).",
    },
    {
        "id": "doc-emergency",
        "title": "Emergency Procedures",
        "text": "In case of emergency, proceed calmly to the nearest marked Exit (X1 North, X2 South, "
                "X3 East). Medical teams are stationed at M1 and M2. Staff wear high-visibility vests "
                "and can guide you.",
    },
    {
        "id": "doc-schedule",
        "title": "Match Schedule",
        "text": "Brazil vs Argentina kicks off July 10 at 18:00, gates open 16:00. France vs Germany "
                "plays July 11 at 15:00, gates open 13:00. Spain vs Portugal plays July 12 at 20:00, "
                "gates open 18:00.",
    },
    {
        "id": "doc-language",
        "title": "Multi-language Support",
        "text": "The fan assistant supports English, Spanish, French, Portuguese and Arabic. "
                "Use the language selector or simply type your question in your preferred language.",
    },
]


def random_wait_multiplier():
    return round(random.uniform(0.7, 2.2), 2)
