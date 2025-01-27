import json


def add_to_order(user_id, item):
    """Adds an item to the user's current order."""
    with open('data/user_orders.json', 'r+') as file:
        orders = json.load(file)
        if user_id not in orders:
            orders[user_id] = []
        orders[user_id].append(item)
        file.seek(0)
        json.dump(orders, file)


def get_order(user_id):
    """Retrieves the user's order."""
    with open('data/user_orders.json', 'r') as file:
        orders = json.load(file)
    return orders.get(user_id, [])
