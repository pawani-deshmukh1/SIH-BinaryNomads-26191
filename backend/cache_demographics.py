import json
import random

# Load habitations
with open('fixtures/habitations_assam.json', 'r') as f:
    habs = json.load(f)

# Assam demographic averages (approximate from NFHS/Census)
# Women: ~49%
# Children (0-14): ~29%
# Elderly (60+): ~8%

random.seed(42)

for hab in habs:
    # Add a slight realistic variance to each habitation
    women = round(random.uniform(47.5, 50.5), 1)
    children = round(random.uniform(25.0, 32.0), 1)
    elderly = round(random.uniform(6.0, 10.0), 1)
    
    hab['women_percent'] = women
    hab['children_percent'] = children
    hab['elderly_percent'] = elderly

with open('fixtures/habitations_assam.json', 'w') as f:
    json.dump(habs, f, indent=2)

print("Demographic data cached to habitations_assam.json")
