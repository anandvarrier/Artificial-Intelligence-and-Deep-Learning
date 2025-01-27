import chromadb
from sentence_transformers import SentenceTransformer
import json

# Initialize ChromaDB client
client = chromadb.Client()


# collection = client.get_collection("restaurant_menu")

def initialize_menu_data():
    """Loads menu data into ChromaDB."""
    collection = client.get_collection("restaurant_menu")

    # Load menu data
    with open("data/menu.json", "r") as f:
        menu_data = json.load(f)

    # Initialize sentence transformer model for embeddings
    model = SentenceTransformer('all-mpnet-base-v2')

    # Add menu items to ChromaDB
    for item in menu_data:
        embedding = model.encode(item["description"])
        collection.add(
            documents=[item["description"]],
            metadatas=[item],
            ids=[item["name"]]
        )

    print("Menu data loaded into ChromaDB.")


def search_menu(query):
    """Search menu items based on user query."""
    menu_collection = client.get_collection("restaurant_menu")
    results = menu_collection.query(
        query_texts=[query],
        n_results=3  # Top 3 results
    )
    return results
