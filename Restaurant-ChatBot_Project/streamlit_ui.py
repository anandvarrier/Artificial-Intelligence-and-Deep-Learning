import streamlit as st
import requests

API_BASE = "http://127.0.0.1:8000"

st.title("Restaurant Chatbot 🍕")

user_id = st.text_input("Enter your Name:", "Guest")
query = st.text_input("Ask about the menu:")
if st.button("Search Menu"):
    response = requests.get(f"{API_BASE}/menu", params={"query": query}).json()
    for item in response['results']:
        st.write(f"**{item['name']}** - {item['description']} - ${item['price']}")
        if st.button(f"Order {item['name']}"):
            requests.post(f"{API_BASE}/order", json={"user_id": user_id, "item": item})

if st.button("Show My Order"):
    order = requests.get(f"{API_BASE}/order", params={"user_id": user_id}).json()
    st.write("Your Order:", order)