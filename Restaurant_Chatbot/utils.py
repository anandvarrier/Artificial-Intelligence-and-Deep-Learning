import re
import datetime
from typing import Dict, Any, List, Tuple


# Helper function to analyze user intent based on keywords
def analyze_intent(user_input: str, session_state: Any) -> str:
    user_input_lower = user_input.lower()

    # General greetings and farewells
    if "hello" in user_input_lower or "hi" in user_input_lower or "hey" in user_input_lower:
        return "greet"
    elif "bye" in user_input_lower or "goodbye" in user_input_lower or "see you" in user_input_lower:
        return "farewell"

    # Menu and Offers
    elif "menu" in user_input_lower:
        return "show_menu"
    elif "offers" in user_input_lower or "deals" in user_input_lower or "special" in user_input_lower or "happy hour" in user_input_lower:
        return "show_offers"
    elif "describe" in user_input_lower or "tell me about" in user_input_lower or "what is" in user_input_lower:
        # Check if a menu item name is explicitly mentioned (simplified)
        menu_keywords = ["pizza", "burger", "pasta", "salad", "soup", "sushi", "sandwich", "steak", "chicken", "fries",
                         "coke", "water"]
        if any(item_keyword in user_input_lower for item_keyword in menu_keywords):
            return "describe_menu_item"
        return "general_query"  # If no specific item, treat as general

    elif "filter" in user_input_lower or "vegetarian" in user_input_lower or "vegan" in user_input_lower or "gluten-free" in user_input_lower or "under $" in user_input_lower or "price" in user_input_lower:
        return "filter_menu"

    # Ordering
    # Check for words indicating an order, but prioritize confirmation/cancellation if those states are active
    if session_state.get("awaiting_order_confirmation"):
        if "confirm" in user_input_lower or "yes" in user_input_lower or "place order" in user_input_lower:
            return "confirm_order"
        elif "cancel" in user_input_lower or "no" in user_input_lower and "order" in user_input_lower:
            return "cancel_order"

    if "order" in user_input_lower or "i want to order" in user_input_lower or "get me" in user_input_lower or "buy" in user_input_lower:
        return "place_order"
    elif "add to my order" in user_input_lower or "change my order" in user_input_lower or "modify order" in user_input_lower or "remove from order" in user_input_lower or "cancel my order" in user_input_lower:
        return "modify_order"

    # Reservations
    # Prioritize confirmation/cancellation if those states are active
    if session_state.get("awaiting_reservation_confirmation"):
        if "confirm" in user_input_lower or "yes" in user_input_lower or "book it" in user_input_lower:
            return "confirm_reservation"
        elif "cancel" in user_input_lower or "no" in user_input_lower and "reservation" in user_input_lower:
            return "cancel_reservation"

    if "reservation" in user_input_lower or "book a table" in user_input_lower or "reserve a table" in user_input_lower:
        return "make_reservation"
    elif "modify reservation" in user_input_lower or "change reservation" in user_input_lower or "cancel my reservation" in user_input_lower:
        return "modify_reservation"

    # Restaurant Information
    elif "address" in user_input_lower or "location" in user_input_lower or "where are you" in user_input_lower:
        return "get_address"
    elif "phone" in user_input_lower or "contact number" in user_input_lower or "call" in user_input_lower:
        return "get_phone"
    elif "hours" in user_input_lower or "open" in user_input_lower or "close" in user_input_lower:
        return "get_hours"

    # User feedback
    elif "feedback" in user_input_lower or "rate your service" in user_input_lower or "comments" in user_input_lower:
        return "give_feedback"

    # Contact Info Provision (proactive input, not prompted - or in response to prompt)
    # These intents are checked broadly here, and handled specifically by _process_X_input functions
    if validate_phone_number(user_input):
        return "provide_phone_number"
    if validate_email(user_input):
        return "provide_email"
    if "my name is" in user_input_lower or "i'm" in user_input_lower or "i am" in user_input_lower and len(
            user_input_lower.split()) < 5:  # Simple name pattern
        return "provide_name"

    # Refusing information - moved to a more general intent
    elif "no thanks" in user_input_lower or "no thank you" in user_input_lower or "skip" in user_input_lower or "don't want to provide" in user_input_lower or (
            "no" in user_input_lower and session_state.get("conversation_state") in ["AWAITING_USER_PHONE",
                                                                                     "AWAITING_USER_EMAIL",
                                                                                     "AWAITING_USER_NAME"]):
        return "refuse_info"

    # Default if no specific intent is detected
    return "general_query"


# Helper function to validate and extract phone number
def validate_phone_number(text: str) -> str | None:
    # Relaxed regex to capture common phone number formats (10-15 digits, with optional hyphens/spaces)
    match = re.search(r'(\+?\d{1,3}[-.\s]?)?(\(?\d{3}\)?[-.\s]?)?(\d{3}[-.\s]?\d{4})', text)
    if match:
        # Reconstruct the number to a consistent format (digits only)
        phone_number = ''.join(filter(str.isdigit, match.group(0)))
        # Basic length check for validity (e.g., 10 for US, or more for international)
        if 10 <= len(phone_number) <= 15:
            return phone_number
    return None


# Helper function to validate and extract email address
def validate_email(text: str) -> str | None:
    match = re.search(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", text)
    if match:
        return match.group(0)
    return None


# Helper function to extract reservation details from user input
def extract_reservation_details(user_input: str) -> Dict[str, Any]:
    details = {
        "date": None,
        "time": None,
        "party_size": None
    }
    user_input_lower = user_input.lower()

    # Extract date
    today = datetime.date.today()
    if "today" in user_input_lower:
        details["date"] = today.strftime("%Y-%m-%d")
    elif "tomorrow" in user_input_lower:
        details["date"] = (today + datetime.timedelta(days=1)).strftime("%Y-%m-%d")
    else:
        # Regex for "DDth Month" or "Month DD" or "Month DDth"
        date_match = re.search(
            r'(\d{1,2})(?:st|nd|rd|th)?\s+(january|february|march|april|may|june|july|august|september|october|november|december)',
            user_input_lower)
        if date_match:
            day = int(date_match.group(1))
            month_name = date_match.group(2)
            month_num = datetime.datetime.strptime(month_name, "%B").month
            year = today.year  # Assume current year
            # If the date is in the past for the current year, assume next year
            try:
                if datetime.date(year, month_num, day) < today:
                    year += 1
                details["date"] = f"{year}-{month_num:02d}-{day:02d}"
            except ValueError:  # Handles invalid day for month (e.g., Feb 30)
                details["date"] = None
        else:
            date_match = re.search(
                r'(january|february|march|april|may|june|july|august|september|october|november|december)\s+(\d{1,2})(?:st|nd|rd|th)?',
                user_input_lower)
            if date_match:
                month_name = date_match.group(1)
                day = int(date_match.group(2))
                month_num = datetime.datetime.strptime(month_name, "%B").month
                year = today.year  # Assume current year
                try:
                    if datetime.date(year, month_num, day) < today:
                        year += 1
                    details["date"] = f"{year}-{month_num:02d}-{day:02d}"
                except ValueError:  # Handles invalid day for month
                    details["date"] = None

    # Extract time
    # Handles 7pm, 7:00pm, 19:00, 7 o'clock, half past 7, etc.
    time_match = re.search(r'(\d{1,2}(:\d{2})?\s*(?:am|pm)?)|(half past \d{1,2})|(\d{1,2}\s+o\'clock)',
                           user_input_lower)
    if time_match:
        time_str_raw = time_match.group(0)
        try:
            if "half past" in time_str_raw:
                hour = int(re.search(r'(\d{1,2})', time_str_raw).group(1))
                # Assuming "half past X" means X:30. Need to consider AM/PM context if present.
                # For simplicity, if no AM/PM, assume 24-hour conversion or common meal times.
                # Here, a simple conversion, but a full LLM parsing would be better.
                if "pm" in user_input_lower and hour < 12: hour += 12
                if "am" in user_input_lower and hour == 12: hour = 0  # 12 AM is 00:00
                details["time"] = f"{hour:02d}:30"
            elif "o'clock" in time_str_raw:
                hour = int(re.search(r'(\d{1,2})', time_str_raw).group(1))
                if "pm" in user_input_lower and hour < 12: hour += 12
                if "am" in user_input_lower and hour == 12: hour = 0  # 12 AM is 00:00
                details["time"] = f"{hour:02d}:00"
            else:
                # Standard H:MM AM/PM or 24-hour
                time_str_clean = time_str_raw.replace(" ", "").replace(".", "")
                if "am" in time_str_clean or "pm" in time_str_clean:
                    details["time"] = datetime.datetime.strptime(time_str_clean, "%I%M%p").strftime("%H:%M")
                elif ":" in time_str_clean:
                    details["time"] = datetime.datetime.strptime(time_str_clean, "%H:%M").strftime("%H:%M")
                else:  # Assume H and add :00, or HMM
                    if len(time_str_clean) <= 2:  # e.g., "7" or "10"
                        hour = int(time_str_clean)
                        if "pm" in user_input_lower and hour < 12: hour += 12  # Heuristic for pm
                        if "am" in user_input_lower and hour == 12: hour = 0  # 12 AM is 00:00
                        details["time"] = f"{hour:02d}:00"
                    else:  # e.g., "730"
                        details["time"] = datetime.datetime.strptime(time_str_clean, "%H%M").strftime("%H:%M")
        except ValueError:
            details["time"] = None

    # Extract party size
    party_size_match = re.search(r'(\d+)\s+(people|person|pax|members|of us)\b', user_input_lower)
    if party_size_match:
        details["party_size"] = int(party_size_match.group(1))
    else:
        # Also check for single digit numbers or number words
        num_word_map = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8,
                        "nine": 9, "ten": 10}
        # Look for standalone numbers/words that could imply party size
        standalone_num_match = re.search(r'\b(one|two|three|four|five|six|seven|eight|nine|ten|\d+)\b',
                                         user_input_lower)
        if standalone_num_match and not any(word in standalone_num_match.group(0) for word in
                                            ["item", "minute", "hour", "dollar", "pm",
                                             "am"]):  # Avoid misinterpreting numbers from other contexts
            try:
                details["party_size"] = int(
                    num_word_map.get(standalone_num_match.group(1), standalone_num_match.group(1)))
                # Add a heuristic: if party size is very large (e.g., > 10) and not explicitly "X people", it might be wrong.
                if details["party_size"] > 10 and "people" not in user_input_lower:
                    details["party_size"] = None  # Consider it a misidentification
            except ValueError:
                pass

    return details


# Helper function to extract order items from user input
def extract_order_items(user_input: str, menu_items_db: List[Tuple]) -> List[Tuple[str, int]]:
    order_items = []
    user_input_lower = user_input.lower()

    # Create a mapping from lowercased menu item names to their original names
    # Assuming menu_items_db format is (id, name, description, category, price, ...)
    menu_name_map = {item[1].lower(): item[1] for item in menu_items_db}

    # Regex to find quantities (number or word) followed by potential item names
    # This pattern tries to be flexible and capture "X [item name]" or "[item name]"
    # It looks for a number/word-number, optionally followed by 'x' or 'of', then potential item name
    # Or just an item name.
    pattern = r'(\d+|one|two|three|four|five|six|seven|eight|nine|ten)?\s*(?:x|of)?\s*([a-zA-Z\s]+?(?:pizza|burger|pasta|salad|soup|sushi|sandwich|steak|chicken|fries|coke|water|soda))'

    # Broader pattern if specific menu items aren't always explicitly listed
    # This might catch more, but also more false positives.
    # We will iterate through potential matches and then check against menu_name_map
    possible_items_pattern = r'(\d+|one|two|three|four|five|six|seven|eight|nine|ten)\s*(?:x|of)?\s*([\w\s-]+(?:\b|$))|\b([\w\s-]+(?:\b|$))'

    matches = re.findall(possible_items_pattern, user_input_lower)

    for match_group in matches:
        qty_str = match_group[0] if match_group[0] else None  # Numeric quantity or word
        item_name_raw = match_group[1] if match_group[1] else match_group[2]  # Item name from either group

        if not item_name_raw: continue

        item_name_cleaned = item_name_raw.strip()

        found_menu_item = None
        # Prioritize exact matches first, then partial matches for menu items
        for menu_lower, original_menu_name in menu_name_map.items():
            if menu_lower == item_name_cleaned:  # Exact match
                found_menu_item = original_menu_name
                break
            elif menu_lower in item_name_cleaned:  # Substring match (e.g., "chicken" in "grilled chicken")
                found_menu_item = original_menu_name
                # Continue searching for a more specific match, or refine this later
                # For now, take the first match.
                break
            elif item_name_cleaned in menu_lower:  # User input is part of a longer menu item (e.g., "pizza" for "Pepperoni Pizza")
                found_menu_item = original_menu_name
                break

        if found_menu_item:
            quantity = 1  # Default quantity if not specified
            if qty_str:
                if qty_str.isdigit():
                    quantity = int(qty_str)
                else:
                    # Convert word numbers to int
                    word_to_int = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
                                   "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10}
                    quantity = word_to_int.get(qty_str, 1)  # Default to 1 if word not recognized

            order_items.append((found_menu_item, quantity))

    return order_items