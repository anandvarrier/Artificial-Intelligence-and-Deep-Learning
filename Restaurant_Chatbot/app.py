import streamlit as st
from chatbot_agent import RestaurantChatbot # Import the chatbot agent

# --- Streamlit Session State Initialization ---
# Initialize session state variables if they don't exist
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# Customer-related information (will be populated from DB, or defaults)
if "customer_id" not in st.session_state:
    st.session_state.customer_id = None # Set by chatbot on first interaction
if "customer_name" not in st.session_state:
    st.session_state.customer_name = None
if "customer_phone" not in st.session_state:
    st.session_state.customer_phone = None
if "customer_email" not in st.session_state:
    st.session_state.customer_email = None

# Order-related information
if "current_order_id" not in st.session_state:
    st.session_state.current_order_id = None
if "current_order_items" not in st.session_state:
    st.session_state.current_order_items = [] # Stores items for current pending order

# Reservation-related information
if "reservation_details" not in st.session_state: # Stores extracted reservation details
    st.session_state.reservation_details = None

# Flags for specific conversational steps (managed within chatbot_agent)
if "awaiting_order_confirmation" not in st.session_state:
    st.session_state.awaiting_order_confirmation = False
if "awaiting_reservation_confirmation" not in st.session_state:
    st.session_state.awaiting_reservation_confirmation = False

# Overall conversation state to manage flow
if "conversation_state" not in st.session_state:
    st.session_state.conversation_state = "INITIAL" # Possible states: INITIAL, AWAITING_USER_NAME, AWAITING_USER_PHONE, AWAITING_USER_EMAIL, READY_FOR_TASK, AWAITING_ORDER_DETAILS, AWAITING_RESERVATION_DETAILS, AWAITING_ORDER_CONFIRMATION, AWAITING_RESERVATION_CONFIRMATION, CONCLUDING

# To store the original intent if contact info collection interrupts a task
if "current_intent_after_contact" not in st.session_state:
    st.session_state.current_intent_after_contact = None

# Initialize the chatbot only once, passing the session_state
if "chatbot" not in st.session_state:
    try:
        st.session_state.chatbot = RestaurantChatbot(st.session_state)
    except ValueError as e:
        st.error(f"Error initializing chatbot: {e}. Please ensure GROQ_API_KEY is set in your environment variables.")
        st.stop()


st.set_page_config(page_title="The Culinary Hub Chatbot")
st.title("🍽️ The Culinary Hub Chatbot")
st.caption("Ask me about our menu, offers, make an order or reservation, and more!")

# Display chat history
for message in st.session_state.chat_history:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# User input
if user_prompt := st.chat_input("Ask me anything..."):
    # Add user message to chat history
    st.session_state.chat_history.append({"role": "user", "content": user_prompt})
    with st.chat_message("user"):
        st.markdown(user_prompt)

    # Get chatbot response
    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            # The chatbot.process_user_input now handles all logic and state updates
            response = st.session_state.chatbot.process_user_input(user_prompt)
            st.markdown(response)
            st.session_state.chat_history.append({"role": "assistant", "content": response})