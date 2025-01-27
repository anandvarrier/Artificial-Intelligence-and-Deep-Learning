from fastapi import FastAPI
from app.database import search_menu
from app.order_manager import add_to_order, get_order
# from app.model import get_response

app = FastAPI()


@app.get("/menu")
def search(query: str):
    """Search menu items."""
    return search_menu(query)


@app.post("/order")
def add_order(user_id: str, item: dict):
    """Add item to order."""
    add_to_order(user_id, item)
    return {"status": "success", "message": f"{item['name']} added to order."}


@app.get("/order")
def get_user_order(user_id: str):
    """Retrieve current order."""
    return get_order(user_id)
