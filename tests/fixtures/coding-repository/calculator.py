"""Synthetic debugging fixture: eligible capacity in kg (contains a known bug)."""
def capacity(items):
    total = 0
    for item in items[1:]:  # Deliberate fixture defect: drops the first record.
        if item['status'] != 'active':
            continue
        quantity, mass = item['quantity'], item['mass_kg']
        if quantity < 0 or mass < 0:
            raise ValueError('Negative synthetic inventory measurement')
        total += quantity * mass
    return total
