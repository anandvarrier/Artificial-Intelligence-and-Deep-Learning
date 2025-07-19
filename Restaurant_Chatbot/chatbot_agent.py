import os
import json
import random
import datetime
import re

from langchain.chains import LLMChain
from langchain_core.prompts import (
    ChatPromptTemplate,
    HumanMessagePromptTemplate,
    MessagesPlaceholder,
)
from langchain_core.messages import SystemMessage
from langchain.chains.conversation.memory import ConversationBufferWindowMemory
from langchain_groq import ChatGroq

from database import RestaurantDatabase
from utils import analyze_intent, extract_reservation_details, extract_order_items, validate_phone_number, \
    validate_email


class RestaurantChatbot:
    def __init__(self, session_state):
        self.db = RestaurantDatabase()
        self.groq_api_key = os.environ.get('GROQ_API_KEY')
        if not self.groq_api_key:
            raise ValueError("GROQ_API_KEY environment variable is required")

        self.model = 'llama3-8b-8192'
        self.groq_chat = ChatGroq(groq_api_key=self.groq_api_key, model_name=self.model,
                                  temperature=0.2)  # Set temperature to 0.2

        # Streamlit's session_state is passed directly and will hold all conversational state
        self.session_state = session_state

        self.system_prompt = """You are a friendly and helpful restaurant chatbot for The Culinary Hub.
        You help customers who may be:
        1. At home inquiring about the restaurant and wanting to make reservations
        2. In the restaurant wanting to place orders

        Your capabilities include:
        - Greeting and welcoming customers.
        - **Retrieving and explaining menu items**.
        - **Providing information about current offers and deals**. Note: Happy hour is from 4 PM to 6 PM.
        - **Filtering menu items** based on criteria (e.g., "vegetarian options", "dishes under $15").
        - **Taking food orders**: Collect items and quantities.
        - **Modifying existing orders**: Update quantity, remove items, or cancel full order (within 2 minutes of placement).
        - **Making table reservations**: Collect date, time, party size, and customer contact information (phone is required, email is optional).
        - **Modifying reservations**: Change date, time, party size, or cancel reservation (at least 2 hours prior to reservation time).
        - **Providing restaurant information**: Address, phone number, opening hours.
        - **Collecting customer feedback and ratings**.

        **Important Instructions for Data Retrieval:**
        You DO NOT have the menu, offers, or restaurant information hardcoded. Your responses should reflect that you are querying a database or using a tool to get this information. For example, instead of listing the menu directly, say "Here is our current menu:" and then list it as retrieved from the database.

        **When asked about menu, offers, or restaurant information, assume you have a way to look it up.**

        **Current User Session Information:**
        - Always ensure you collect the user's name and phone number (required for orders/reservations). Email is optional. If not known, ask for them before proceeding with tasks.
        - If a customer_id is set in the session, you can assume you are interacting with that customer.
        - If the user asks about topics unrelated to the restaurant (e.g., politics, news, personal questions), politely state that you can only assist with inquiries related to The Culinary Hub's menu, offers, orders, and reservations. Do not engage in off-topic conversations. Keep your responses concise and directly address the user's intent.
        """

        self.prompt = ChatPromptTemplate.from_messages(
            [
                SystemMessage(content=self.system_prompt),
                MessagesPlaceholder(variable_name="chat_history"),
                HumanMessagePromptTemplate.from_template("{input}"),
            ]
        )

        # Memory should also be part of session state if you want it to persist across full Streamlit reruns
        # However, ConversationBufferWindowMemory manages its own internal buffer which is typically fine
        # for single turn processing within the same chatbot instance. If the chatbot instance
        # itself is recreated, this memory resets.
        # For full persistence, you'd save/load chat_history from st.session_state.
        self.memory = ConversationBufferWindowMemory(k=5, memory_key="chat_history", return_messages=True)
        self.conversation = LLMChain(llm=self.groq_chat, prompt=self.prompt, memory=self.memory)

    def process_user_input(self, user_input: str) -> str:
        # 1. Initialize customer_id and populate basic customer details from DB if not already in session
        if self.session_state.customer_id is None:
            self.session_state.customer_id = self.db.add_customer(name="Guest Customer", phone=None, email=None)
            if self.session_state.customer_id is None:
                return "I apologize, but I'm having trouble initializing your session. Please try again later."

        # Always attempt to load customer details from DB into session state on each turn
        # This ensures consistency if the DB is updated directly or across different sessions (though session_state is per user browser session)
        customer_details = self.db.get_customer_details(self.session_state.customer_id)
        if customer_details:
            # Update session_state with latest customer info from DB
            self.session_state.customer_name = customer_details[1]
            self.session_state.customer_phone = customer_details[2]
            self.session_state.customer_email = customer_details[3]

        # 2. Analyze User Intent
        # Pass relevant session state data to analyze_intent if it needs context
        intent = analyze_intent(user_input, self.session_state)

        # Add current user prompt to memory before processing
        self.memory.chat_memory.add_user_message(user_input)

        response = ""

        # --- State-based Conversation Flow ---

        # Handles name collection
        if self.session_state.conversation_state == "AWAITING_USER_NAME":
            return self._process_name_input(user_input, self.session_state.customer_id)
        # Handles phone collection
        elif self.session_state.conversation_state == "AWAITING_USER_PHONE":
            return self._process_phone_input(user_input, self.session_state.customer_id)
        # Handles email collection
        elif self.session_state.conversation_state == "AWAITING_USER_EMAIL":
            return self._process_email_input(user_input, self.session_state.customer_id)
        # Handles reservation confirmation
        elif self.session_state.conversation_state == "AWAITING_RESERVATION_CONFIRMATION":
            if intent == "confirm_reservation":
                return self.confirm_reservation_final(user_input)
            elif intent == "cancel_reservation":
                self.session_state.awaiting_reservation_confirmation = False
                self.session_state.reservation_details = None
                self.session_state.conversation_state = "READY_FOR_TASK"
                return "Okay, I've cancelled the reservation confirmation process. Is there anything else I can help you with?"
            else:
                return "I'm currently waiting for you to confirm or cancel the reservation. Please say 'yes' or 'confirm' to book, or 'no' or 'cancel' to disregard."
        # Handles order confirmation
        elif self.session_state.conversation_state == "AWAITING_ORDER_CONFIRMATION":
            if intent == "confirm_order":
                return self.confirm_order_final(user_input)
            elif intent == "cancel_order":
                self.session_state.awaiting_order_confirmation = False
                self.session_state.current_order_id = None
                self.session_state.current_order_items = []
                self.session_state.conversation_state = "READY_FOR_TASK"
                return "Okay, I've cancelled the order confirmation process. Is there anything else I can help you with?"
            else:
                return "I'm currently waiting for you to confirm or modify your order. Please say 'confirm' to finalize, or specify what you'd like to add/remove."

        # Initial greeting or after a task
        if self.session_state.conversation_state == "INITIAL" or self.session_state.conversation_state == "READY_FOR_TASK":
            if self.session_state.customer_name is None or self.session_state.customer_name == "Guest Customer":
                self.session_state.conversation_state = "AWAITING_USER_NAME"
                return "Hello! Welcome to The Culinary Hub. Before we proceed, could I please get your name?"
            elif self.session_state.customer_phone is None:
                self.session_state.conversation_state = "AWAITING_USER_PHONE"
                return f"Thank you, {self.session_state.customer_name}! To assist you better with orders and reservations, could I please get your phone number?"
            elif self.session_state.customer_email is None:
                self.session_state.conversation_state = "AWAITING_USER_EMAIL"
                return f"Thanks, {self.session_state.customer_name}! Would you like to provide your email as well? (Optional)"
            else:
                # If all contact info collected, set to READY_FOR_TASK and proceed with intent
                self.session_state.conversation_state = "READY_FOR_TASK"
                # If the current intent is 'greet' and we're ready for task, give a standard greeting
                if intent == "greet":
                    return f"Hello {self.session_state.customer_name}! How can I assist you today?"

        # Process intents when READY_FOR_TASK or if an immediate task is implied
        if self.session_state.conversation_state == "READY_FOR_TASK" or intent in ["place_order", "make_reservation"]:
            if intent == "greet":
                response = f"Hello {self.session_state.customer_name}! Welcome to The Culinary Hub. How can I assist you today?"
            elif intent == "show_menu":
                response = self.show_menu(user_input)
            elif intent == "show_offers":
                response = self.show_offers()
            elif intent == "place_order":
                # Ensure phone is collected before placing order
                if not self.session_state.customer_phone:
                    self.session_state.current_intent_after_contact = "place_order"
                    self.session_state.conversation_state = "AWAITING_USER_PHONE"
                    return "To place an order, I'll need your phone number. Could you please provide it?"
                response = self.place_order_flow(user_input)
            elif intent == "modify_order":
                response = self.modify_order_flow(user_input)
            elif intent == "make_reservation":
                # Ensure phone is collected before making reservation
                if not self.session_state.customer_phone:
                    self.session_state.current_intent_after_contact = "make_reservation"
                    self.session_state.conversation_state = "AWAITING_USER_PHONE"
                    return "To make a reservation, I'll need your phone number. Could you please provide it?"
                response = self.make_reservation_flow(user_input)
            elif intent == "modify_reservation":
                response = self.modify_reservation_flow(user_input)
            elif intent == "get_address":
                response = self.get_restaurant_info_address()
            elif intent == "get_phone":
                response = self.get_restaurant_info_phone()
            elif intent == "get_hours":
                response = self.get_restaurant_info_hours()
            elif intent == "give_feedback":
                response = self.give_feedback_flow(user_input)
            elif intent == "describe_menu_item":
                response = self.describe_menu_item(user_input)
            elif intent == "filter_menu":
                response = self.filter_menu_items(user_input)
            elif intent == "refuse_info":  # Catch refusal if not in awaiting state
                return "Understood. No problem at all. How else may I assist you?"
            elif intent == "farewell":
                self.session_state.conversation_state = "CONCLUDING"
                response = "Thank you for visiting The Culinary Hub! Have a wonderful day! 👋"
            else:  # General query or unhandled intent, let LLM decide
                llm_response = self.conversation.predict(input=user_input)
                response = llm_response
        else:
            # Fallback for unexpected states
            response = "I'm sorry, I'm currently expecting some specific information from you or I'm in an unexpected state. Could you please clarify your request, or state 'start over' to reset?"

        # Add chatbot's response to memory
        self.memory.chat_memory.add_ai_message(response)
        return response

    # Helper methods for processing contact info inputs
    def _process_name_input(self, user_input: str, customer_id: int) -> str:
        name = user_input.strip()
        user_input_lower = name.lower()

        if "no thanks" in user_input_lower or "skip" in user_input_lower or "n/a" in user_input_lower:
            # If they don't give a name, keep them as "Guest Customer" and move to phone
            # We already set them as Guest Customer on init, so no update needed unless they gave a name
            self.session_state.customer_name = "Guest Customer"
            self.session_state.conversation_state = "AWAITING_USER_PHONE"
            return "No problem. Let's proceed. Could I please get your phone number? This is required for orders and reservations."

        # Basic name validation (e.g., not just numbers, not too short)
        if len(name) < 2 or re.fullmatch(r'\d+', name):
            return "That doesn't seem like a valid name. Could you please provide your name, or say 'no thanks' to skip?"

        if self.db.update_customer(customer_id, name=name):
            self.session_state.customer_name = name
            self.session_state.conversation_state = "AWAITING_USER_PHONE"  # Next state
            return f"Thank you, {name}! Now, to assist you better, could I please get your phone number? This is required for orders and reservations."
        else:
            return "There was an error saving your name. Could you please try again?"

    def _process_phone_input(self, user_input: str, customer_id: int) -> str:
        user_input_lower = user_input.lower()
        if "no" in user_input_lower and (
                "thanks" in user_input_lower or "thank you" in user_input_lower or "skip" in user_input_lower):
            self.session_state.customer_phone = None  # Explicitly set to None if refused
            self.session_state.conversation_state = "AWAITING_USER_EMAIL"  # Move to email
            return "Understood. No problem. Would you like to provide your email as well? (Optional)"
        else:
            collected_phone = validate_phone_number(user_input)
            if collected_phone:
                if self.db.update_customer(customer_id, phone=collected_phone):
                    self.session_state.customer_phone = collected_phone  # Update session state
                    response = f"Thank you, I've noted your phone number: {collected_phone}."

                    # Transition to email collection state
                    self.session_state.conversation_state = "AWAITING_USER_EMAIL"
                    response += "\nWould you like to provide your email as well? (Optional)"
                    return response
                else:
                    return "There was an error saving your phone number. Please try again."
            else:
                # Keep awaiting if input was invalid
                self.session_state.conversation_state = "AWAITING_USER_PHONE"  # Stay in this state
                return "That doesn't look like a valid phone number. Could you please try again (e.g., 123-456-7890), or say 'no thanks' to skip?"

    def _process_email_input(self, user_input: str, customer_id: int) -> str:
        user_input_lower = user_input.lower()
        if "no" in user_input_lower and (
                "thanks" in user_input_lower or "thank you" in user_input_lower or "skip" in user_input_lower):
            self.session_state.customer_email = None  # Explicitly set to None if refused
            self.session_state.conversation_state = "READY_FOR_TASK"  # Move to ready for tasks
            # If there was a pending intent (like place_order or make_reservation) after collecting contact info,
            # activate it
            if self.session_state.current_intent_after_contact:
                next_intent = self.session_state.current_intent_after_contact
                self.session_state.current_intent_after_contact = None  # Clear it
                if next_intent == "place_order":
                    return "Understood. No problem with the email.\n" + self.place_order_flow(
                        user_input="initiate order")  # Use a dummy input to trigger the flow
                elif next_intent == "make_reservation":
                    return "Understood. No problem with the email.\n" + self.make_reservation_flow(
                        user_input="initiate reservation")  # Use a dummy input to trigger the flow
            return "Understood. No problem. How else may I assist you today?"
        else:
            collected_email = validate_email(user_input)
            if collected_email:
                try:
                    if self.db.update_customer(customer_id, email=collected_email):
                        self.session_state.customer_email = collected_email  # Update session state
                        response = f"Thank you, I've noted your email: {collected_email}."
                        self.session_state.conversation_state = "READY_FOR_TASK"  # Move to ready for tasks
                        # If there was a pending intent (like place_order or make_reservation) after collecting
                        # contact info, activate it
                        if self.session_state.current_intent_after_contact:
                            next_intent = self.session_state.current_intent_after_contact
                            self.session_state.current_intent_after_contact = None  # Clear it
                            if next_intent == "place_order":
                                return response + "\n" + self.place_order_flow(user_input="initiate order")
                            elif next_intent == "make_reservation":
                                return response + "\n" + self.make_reservation_flow(user_input="initiate reservation")
                        return response + "\nHow else may I assist you today?"
                    else:
                        return "There was an error saving your email. Please try again."
                except Exception as e:
                    if "UNIQUE constraint failed" in str(e):
                        return ("It seems that email is already registered with another customer. Could you try a "
                                "different one?")
                    else:
                        return "There was an unexpected error saving your email. Please try again."
            else:
                # Keep awaiting if input was invalid
                self.session_state.conversation_state = "AWAITING_USER_EMAIL"  # Stay in this state
                return ("That doesn't look like a valid email. Could you please try again (e.g., example@domain.com), "
                        "or say 'no thanks' to skip?")

    def show_menu(self, user_input: str) -> str:
        # LLM will decide if it needs to filter or show all
        # For now, we'll assume it means all, or extract category
        menu_items = self.db.get_all_menu_items()
        if menu_items:
            response = "Here is our current menu:\n"
            categories = {}
            for item in menu_items:
                name, description, price, category = item[1], item[2], item[4], item[
                    3]  # Adjusted indexing based on database.py's get_all_menu_items
                if category not in categories:
                    categories[category] = []
                categories[category].append(f"- {name}: ${price:.2f} - {description}")

            for category, items in categories.items():
                response += f"\n**{category.upper()}**\n" + "\n".join(items)
            return response
        else:
            return "I apologize, the menu is not currently available. Please check back later."

    def describe_menu_item(self, user_input: str) -> str:
        # This will be more robust with LLM's entity extraction in a tool call
        menu_items = self.db.get_all_menu_items()
        item_name_to_find = None
        for item_id, item_name_db, _, _, _, _, _, _ in menu_items:  # Adjusted for full menu item details
            if item_name_db.lower() in user_input.lower():
                item_name_to_find = item_name_db
                break

        if item_name_to_find:
            item = self.db.get_menu_item_by_name(item_name_to_find)
            if item:
                _, name, description, category, price, ingredients, nutrition, how_its_made = item
                response = f"**{name}** ({category}): ${price:.2f}\n" \
                           f"Description: {description}\n" \
                           f"Ingredients: {ingredients}\n" \
                           f"Nutrition Info: {nutrition}\n" \
                           f"How it's made: {how_its_made}"
                return response
            else:
                return f"I couldn't find details for '{item_name_to_find}'."
        else:
            return "Could you please specify which menu item you'd like to know more about?"

    def filter_menu_items(self, user_input: str) -> str:
        criteria = {}
        user_input_lower = user_input.lower()

        if "vegetarian" in user_input_lower:
            criteria['category'] = 'Vegetarian'  # Assuming category in DB is 'Vegetarian'
        elif "vegan" in user_input_lower:
            criteria['category'] = 'Vegan'  # Assuming a 'Vegan' category or filter
        elif "gluten-free" in user_input_lower:
            criteria['category'] = 'Gluten-Free'  # Assuming a 'Gluten-Free' category or tag

        price_match = re.search(r'under\s*\$?(\d+\.?\d*)', user_input_lower)
        if price_match:
            criteria['max_price'] = float(price_match.group(1))

        filtered_items = self.db.get_filtered_menu(criteria)  # Make sure get_filtered_menu handles these
        if filtered_items:
            response = "Here are some menu items matching your criteria:\n"
            for item in filtered_items:
                name, description, price, category = item[1], item[2], item[4], item[3]  # Adjusted indexing
                response += f"- {name} ({category}): ${price:.2f} - {description}\n"
            return response
        else:
            return "I couldn't find any menu items matching your criteria. Please try different filters."

    def show_offers(self) -> str:
        offers = self.db.get_offers()
        if offers:
            response = "Here are our current offers:\n"
            for offer in offers:
                name, description, discount, valid_from, valid_to, is_happy_hour = offer
                offer_text = f"- **{name}**: {description}"
                if discount > 0:
                    offer_text += f" ({int(discount * 100)}% off)"

                # Check happy hour validity based on current time
                current_time = datetime.datetime.now().time()
                try:
                    # Convert valid_from and valid_to from string "HH:MM" to time objects
                    from_time = datetime.datetime.strptime(valid_from, "%H:%M").time()
                    to_time = datetime.datetime.strptime(valid_to, "%H:%M").time()

                    if is_happy_hour and from_time <= current_time <= to_time:
                        offer_text += " (Currently ON for Happy Hour! 🥳)"
                    elif is_happy_hour:
                        offer_text += f" (Happy Hour from {valid_from} to {valid_to})"
                    else:  # Non-happy hour offers, show valid times if not all day
                        if valid_from != "00:00" or valid_to != "23:59":
                            offer_text += f" (Valid from {valid_from} to {valid_to})"

                except ValueError:
                    offer_text += " (Times unavailable)"  # Handle parsing errors
                response += offer_text + "\n"
            return response
        else:
            return "We currently don't have any special offers. Please check back soon!"

    def get_restaurant_info_address(self) -> str:
        info = self.db.get_restaurant_info()
        if info:
            return f"We are located at: {info[1]}"
        return "I'm sorry, I don't have the address information at the moment."

    def get_restaurant_info_phone(self) -> str:
        info = self.db.get_restaurant_info()
        if info:
            return f"You can reach us at: {info[2]}"
        return "I'm sorry, I don't have the phone number at the moment."

    def get_restaurant_info_hours(self) -> str:
        info = self.db.get_restaurant_info()
        if info:
            return f"Our opening hours are: {info[3]}"
        return "I'm sorry, I don't have the opening hours at the moment."

    def place_order_flow(self, user_input: str) -> str:
        # Use session_state for current order tracking
        menu_items_db = self.db.get_all_menu_items()  # Get current menu items from DB
        order_items_extracted = extract_order_items(user_input, menu_items_db)

        # If no items detected, ask user for clarity
        if not order_items_extracted and user_input != "initiate order":  # Allow "initiate order" to start the flow
            return "I couldn't understand which items you'd like to order. Could you please specify the item names and quantities?"

        # Proceed with order creation or adding to existing order
        if self.session_state.current_order_id is None:
            self.session_state.current_order_id = self.db.create_order(self.session_state.customer_id)
            if self.session_state.current_order_id is None:
                return "I apologize, I couldn't start a new order. Please try again later."
            self.session_state.current_order_items = []  # Initialize for a new order

        # Add items to the order
        items_added_count = 0
        response_messages = []
        for item_name, quantity in order_items_extracted:
            menu_item_details = self.db.get_menu_item_by_name(item_name)
            if menu_item_details:
                menu_item_id = menu_item_details[0]
                price_at_order = menu_item_details[4]  # Use price from DB at time of order
                if self.db.add_order_item(self.session_state.current_order_id, menu_item_id, quantity, price_at_order):
                    items_added_count += 1
                else:
                    response_messages.append(f"There was an issue adding '{item_name}' to your order.")
            else:
                response_messages.append(
                    f"I couldn't find '{item_name}' on the menu. Please check the spelling or ask to see the menu.")

        if items_added_count == 0 and not response_messages and user_input != "initiate order":
            return "I couldn't add any items to your order. Please specify items from the menu clearly."
        elif items_added_count == 0 and user_input == "initiate order":
            return "What items would you like to order today? Please tell me the item name and quantity."

        # Display current order items and ask for confirmation
        current_order_summary = ""
        total_amount = 0
        order_items_to_display = self.db.get_order_items(self.session_state.current_order_id)
        if order_items_to_display:
            current_order_summary = "Your current order:\n"
            for _, name, qty, price in order_items_to_display:
                current_order_summary += f"- {qty}x {name} (${qty * price:.2f})\n"
                total_amount += qty * price
            current_order_summary += f"Total: ${total_amount:.2f}\n"

        final_response = ""
        if response_messages:
            final_response += "Please note: " + " ".join(response_messages) + "\n\n"

        final_response += current_order_summary + "\nWould you like to confirm this order and proceed to payment, or add more items?"
        self.session_state.awaiting_order_confirmation = True
        self.session_state.conversation_state = "AWAITING_ORDER_CONFIRMATION"  # Set state for confirmation
        return final_response

    def confirm_order_final(self, user_input: str) -> str:
        if self.session_state.awaiting_order_confirmation and self.session_state.current_order_id:
            self.db.update_order_status(self.session_state.current_order_id, 'confirmed')
            order_details = self.db.get_order_details(self.session_state.current_order_id)

            confirmation_message = f"Great {self.session_state.customer_name}! Your order #{self.session_state.current_order_id} has been confirmed for a total of ${order_details['total_amount']:.2f}."

            contact_info_provided = False
            if self.session_state.customer_phone:
                confirmation_message += f" We will send you an SMS confirmation to {self.session_state.customer_phone} shortly."
                contact_info_provided = True
            if self.session_state.customer_email:
                confirmation_message += f" You will also receive an email confirmation at {self.session_state.customer_email}."
                contact_info_provided = True

            if not contact_info_provided:
                confirmation_message += " We recommend providing a phone number or email for order updates."

            confirmation_message += "\nIs there anything else I can help you with?"

            # Clear order-related session state variables
            self.session_state.current_order_id = None
            self.session_state.current_order_items = []
            self.session_state.awaiting_order_confirmation = False
            self.session_state.conversation_state = "READY_FOR_TASK"  # Back to general tasks
            return confirmation_message
        else:
            return "There is no pending order to confirm."

    def modify_order_flow(self, user_input: str) -> str:
        # This is a placeholder. A full implementation would involve:
        # 1. Checking if there's an active order (self.session_state.current_order_id)
        # 2. Parsing user input to determine: add item, remove item, change quantity, or cancel.
        # 3. Calling appropriate database methods (update_order_item_quantity, remove_order_item, update_order_status).
        # 4. Confirming changes to the user.
        return "Order modification is not yet fully implemented, but I can cancel your last order if it was placed recently (within 2 minutes)."

    def make_reservation_flow(self, user_input: str) -> str:
        # reservation_details stored in session_state persists across turns for follow-up questions
        extracted_details = extract_reservation_details(user_input)

        # Merge newly extracted details with existing (partial) details in session_state
        if not self.session_state.reservation_details:
            self.session_state.reservation_details = {}

        # Only update with non-None values from new extraction
        for key, value in extracted_details.items():
            if value is not None:
                self.session_state.reservation_details[key] = value

        reservation_date_str = self.session_state.reservation_details.get("date")
        reservation_time_str = self.session_state.reservation_details.get("time")
        party_size = self.session_state.reservation_details.get("party_size")

        # If it's an initial call (dummy input) and details aren't already pending, ask for them
        if user_input == "initiate reservation" and not (reservation_date_str and reservation_time_str and party_size):
            self.session_state.conversation_state = "AWAITING_RESERVATION_DETAILS"  # Could add this specific state if needed
            return "I can help you with a reservation! Please tell me the date, time, and how many people will be in your party."

        # If details are still missing after attempting extraction
        if not (reservation_date_str and reservation_time_str and party_size):
            missing_info = []
            if not reservation_date_str: missing_info.append("date")
            if not reservation_time_str: missing_info.append("time")
            if not party_size: missing_info.append("party size")

            self.session_state.conversation_state = "AWAITING_RESERVATION_DETAILS"  # Keep in or set to this state
            return f"I need a bit more information for your reservation. Could you please provide the {', '.join(missing_info)}?"

        # If all details are extracted, proceed
        # Check for available tables
        available_tables = self.db.get_available_tables(party_size, reservation_date_str, reservation_time_str)

        if available_tables:
            # For simplicity, pick the first available table that fits
            table_number = available_tables[0][0]
            table_capacity = available_tables[0][1]
            # Fetch table_id from table_number for the create_reservation call
            table_id_result = self.db.cursor.execute("SELECT id FROM restaurant_tables WHERE table_number = ?",
                                                     (table_number,)).fetchone()
            table_id = table_id_result[0] if table_id_result else None

            if table_id is None:
                self.session_state.reservation_details = None  # Clear any partial details
                self.session_state.conversation_state = "READY_FOR_TASK"
                return "An internal error occurred while finding the table ID. Please try again or contact staff directly."

            self.session_state.reservation_details.update({  # Update existing dict
                "customer_id": self.session_state.customer_id,
                "table_id": table_id,
                "reservation_date": reservation_date_str,
                "reservation_time": reservation_time_str,
                "party_size": party_size,
                "table_number": table_number,  # For display purposes
                "table_capacity": table_capacity  # For display purposes
            })

            response = (f"I found a table ({table_number}, capacity {table_capacity}) for {party_size} people "
                        f"on {reservation_date_str} at {reservation_time_str}. "
                        f"Would you like to confirm this reservation?")
            self.session_state.awaiting_reservation_confirmation = True
            self.session_state.conversation_state = "AWAITING_RESERVATION_CONFIRMATION"
            return response
        else:
            self.session_state.reservation_details = None  # Clear any partial details
            self.session_state.conversation_state = "READY_FOR_TASK"  # Back to general tasks
            return f"I apologize, but we don't have any tables available for {party_size} people on {reservation_date_str} at {reservation_time_str}. Please try a different time or date."

    def confirm_reservation_final(self, user_input: str) -> str:
        if self.session_state.awaiting_reservation_confirmation and self.session_state.reservation_details:
            details = self.session_state.reservation_details
            booking_id = self.db.create_reservation(
                details["customer_id"],
                details["table_id"],
                details["reservation_date"],
                details["reservation_time"],
                details["party_size"]
            )

            if booking_id:
                confirmation_message = (
                    f"Great {self.session_state.customer_name}! Your reservation #{booking_id} for {details['party_size']} people "
                    f"on {details['reservation_date']} at {details['reservation_time']} "
                    f"at Table {details['table_number']} has been confirmed."
                )
                contact_info_provided = False
                if self.session_state.customer_phone:
                    confirmation_message += f" A confirmation will be sent to your phone at {self.session_state.customer_phone}."
                    contact_info_provided = True
                if self.session_state.customer_email:
                    confirmation_message += f" You will also receive an email confirmation at {self.session_state.customer_email}."
                    contact_info_provided = True

                if not contact_info_provided:
                    confirmation_message += " We recommend providing a phone number or email for reservation updates."

                confirmation_message += "\nWe look forward to seeing you! Is there anything else I can help you with?"

                self.session_state.reservation_details = None
                self.session_state.awaiting_reservation_confirmation = False
                self.session_state.conversation_state = "READY_FOR_TASK"  # Back to general tasks
                return confirmation_message
            else:
                self.session_state.awaiting_reservation_confirmation = False
                self.session_state.reservation_details = None
                self.session_state.conversation_state = "READY_FOR_TASK"
                return "I'm sorry, I couldn't finalize your reservation. It might be already booked or an error occurred. Please try again."
        else:
            return "There is no pending reservation to confirm."

    def modify_reservation_flow(self, user_input: str) -> str:
        # Placeholder for modification logic
        # This would require asking for the booking ID, new details, and calling db.update_reservation
        return "Reservation modification is not yet fully implemented. You can cancel your reservation by stating 'cancel my reservation' if you know your booking ID."

    def give_feedback_flow(self, user_input: str) -> str:
        # Placeholder for feedback collection
        # This would involve extracting rating and comments, and calling db.store_feedback
        return "Thank you for wanting to give feedback! Please tell me your rating (1-5) and any comments you have."