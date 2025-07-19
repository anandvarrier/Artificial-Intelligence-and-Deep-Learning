import sqlite3
import json
from datetime import datetime


class RestaurantDatabase:
    def __init__(self, db_name="restaurant.db"):
        self.db_name = db_name
        self.conn = None
        self.cursor = None
        self.connect()
        self.create_tables()
        self.populate_dummy_data()

    def connect(self):
        try:
            self.conn = sqlite3.connect(self.db_name, check_same_thread=False)
            self.cursor = self.conn.cursor()
        except sqlite3.Error as e:
            print(f"Error connecting to database: {e}")

    def close(self):
        if self.conn:
            self.conn.close()

    def create_tables(self):
        try:
            # Menu Table
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS menu (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    description TEXT,
                    category TEXT,
                    price REAL NOT NULL,
                    ingredients TEXT,
                    nutrition TEXT,
                    how_its_made TEXT
                )
            """)
            # Offers Table
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS offers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    description TEXT,
                    discount REAL,
                    valid_from TEXT,
                    valid_to TEXT,
                    is_happy_hour BOOLEAN DEFAULT 0
                )
            """)
            # Restaurant Info Table
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS restaurant_info (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT,
                    address TEXT,
                    phone TEXT,
                    opening_hours TEXT
                )
            """)
            # Customers Table
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS customers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    phone TEXT UNIQUE,
                    email TEXT UNIQUE
                )
            """)
            # Restaurant Tables Table
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS restaurant_tables (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    table_number TEXT NOT NULL UNIQUE,
                    capacity INTEGER NOT NULL
                )
            """)
            # Reservations Table
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS reservations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    customer_id INTEGER,
                    table_id INTEGER,
                    reservation_date TEXT NOT NULL,
                    reservation_time TEXT NOT NULL,
                    party_size INTEGER NOT NULL,
                    status TEXT DEFAULT 'confirmed',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (customer_id) REFERENCES customers(id),
                    FOREIGN KEY (table_id) REFERENCES restaurant_tables(id)
                )
            """)
            # Orders Table
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS orders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    customer_id INTEGER,
                    order_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    total_amount REAL,
                    status TEXT DEFAULT 'pending', -- pending, confirmed, cancelled, delivered
                    FOREIGN KEY (customer_id) REFERENCES customers(id)
                )
            """)
            # Order Items Table
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS order_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    order_id INTEGER,
                    menu_item_id INTEGER,
                    quantity INTEGER NOT NULL,
                    price_at_order REAL NOT NULL,
                    FOREIGN KEY (order_id) REFERENCES orders(id),
                    FOREIGN KEY (menu_item_id) REFERENCES menu(id)
                )
            """)
            # Feedback Table
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS feedback (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    customer_id INTEGER,
                    rating INTEGER,
                    comments TEXT,
                    feedback_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (customer_id) REFERENCES customers(id)
                )
            """)
            self.conn.commit()
        except sqlite3.Error as e:
            print(f"Error creating tables: {e}")

    def populate_dummy_data(self):
        try:
            # Check if menu is empty
            self.cursor.execute("SELECT COUNT(*) FROM menu")
            if self.cursor.fetchone()[0] == 0:
                menu_items = [
                    ("Margherita Pizza", "Classic pizza with tomato sauce, mozzarella, and basil.", "Pizza", 12.99,
                     "dough, tomato sauce, mozzarella, basil", "Calories: 300, Protein: 15g, Carbs: 40g",
                     "Hand-tossed dough, fresh ingredients, baked in wood-fired oven."),
                    ("Chicken Alfredo", "Fettuccine pasta in a creamy Alfredo sauce with grilled chicken.", "Pasta",
                     15.99, "fettuccine, cream, butter, parmesan, chicken", "Calories: 450, Protein: 25g, Carbs: 50g",
                     "Fresh pasta, homemade creamy sauce, grilled chicken breast."),
                    (
                    "Veggie Burger", "Plant based patty with lettuce, tomato, onion and special sauce", "Burger", 10.99,
                    "Bun, Plant based patty, Lettuce, Tomato, Onion, Special sauce",
                    "Calories: 350, Protein: 20g, Carbs: 45g",
                    "Grilled plant-based patty, fresh veggies, toasted bun."),
                    ("Caesar Salad", "Crisp romaine lettuce, croutons, parmesan cheese, and Caesar dressing.", "Salad",
                     8.50, "romaine lettuce, croutons, parmesan, Caesar dressing",
                     "Calories: 200, Protein: 8g, Carbs: 15g",
                     "Freshly chopped romaine, homemade dressing, crunchy croutons."),
                    ("Chocolate Lava Cake",
                     "Warm chocolate cake with a molten chocolate center, served with vanilla ice cream.", "Dessert",
                     7.00, "chocolate, flour, sugar, eggs, butter, vanilla ice cream",
                     "Calories: 400, Protein: 5g, Carbs: 60g",
                     "Baked to perfection, rich chocolate, served hot with a scoop of ice cream."),
                    ("Iced Tea", "Refreshing iced black tea.", "Drinks", 3.00, "black tea, water, sugar (optional)",
                     "Calories: 50, Sugar: 12g", "Freshly brewed and chilled."),
                    ("Espresso", "Strong, concentrated coffee.", "Drinks", 3.50, "coffee beans, water",
                     "Calories: 5, Caffeine: 75mg", "Finely ground beans, pressure brewed for rich flavor.")
                ]
                self.cursor.executemany(
                    "INSERT INTO menu (name, description, category, price, ingredients, nutrition, how_its_made) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    menu_items)

            # Check if offers are empty
            self.cursor.execute("SELECT COUNT(*) FROM offers")
            if self.cursor.fetchone()[0] == 0:
                offers = [
                    ("Lunch Combo", "Any sandwich + soup for $10.00", 0.0, "10:00", "15:00", 0),  # Not happy hour
                    ("Happy Hour Drinks", "50% off all draft beers and house wines", 0.50, "16:00", "18:00", 1),
                    # Happy hour
                    ("Family Meal Deal", "2 large pizzas, 1 salad, 4 soft drinks for $40.00", 0.0, "00:00", "23:59", 0)
                    # Not happy hour, all day
                ]
                self.cursor.executemany(
                    "INSERT INTO offers (name, description, discount, valid_from, valid_to, is_happy_hour) VALUES (?, ?, ?, ?, ?, ?)",
                    offers)

            # Check if restaurant info is empty
            self.cursor.execute("SELECT COUNT(*) FROM restaurant_info")
            if self.cursor.fetchone()[0] == 0:
                restaurant_info = [
                    ("The Culinary Hub", "123 Main St, Anytown, USA", "555-123-4567",
                     "Mon-Sat: 10:00-22:00, Sun: 11:00-21:00")
                ]
                self.cursor.executemany(
                    "INSERT INTO restaurant_info (name, address, phone, opening_hours) VALUES (?, ?, ?, ?)",
                    restaurant_info)

            # Check if tables are empty
            self.cursor.execute("SELECT COUNT(*) FROM restaurant_tables")
            if self.cursor.fetchone()[0] == 0:
                tables = [
                    ("Table 1", 2), ("Table 2", 4), ("Table 3", 6),
                    ("Table 4", 2), ("Table 5", 4)
                ]
                self.cursor.executemany("INSERT INTO restaurant_tables (table_number, capacity) VALUES (?, ?)", tables)

            self.conn.commit()
            print("Dummy data populated successfully.")
        except sqlite3.Error as e:
            print(f"Error populating dummy data: {e}")

    def get_menu_by_category(self, category):
        self.cursor.execute("SELECT name, description, price FROM menu WHERE category LIKE ?", ('%' + category + '%',))
        return self.cursor.fetchall()

    def get_menu_item_by_name(self, name):
        self.cursor.execute(
            "SELECT id, name, description, category, price, ingredients, nutrition, how_its_made FROM menu WHERE name LIKE ?",
            ('%' + name + '%',))
        return self.cursor.fetchone()

    def get_all_menu_items(self):
        self.cursor.execute("SELECT name, description, price, category FROM menu")
        return self.cursor.fetchall()

    def get_filtered_menu(self, criteria):
        query = "SELECT name, description, price, category FROM menu WHERE 1=1"
        params = []
        if 'category' in criteria:
            query += " AND category LIKE ?"
            params.append(f"%{criteria['category']}%")
        if 'max_price' in criteria:
            query += " AND price <= ?"
            params.append(criteria['max_price'])
        if 'ingredients_exclude' in criteria:
            for ingredient in criteria['ingredients_exclude']:
                query += " AND ingredients NOT LIKE ?"
                params.append(f"%{ingredient}%")
        self.cursor.execute(query, tuple(params))
        return self.cursor.fetchall()

    def get_offers(self):
        self.cursor.execute("SELECT name, description, discount, valid_from, valid_to, is_happy_hour FROM offers")
        return self.cursor.fetchall()

    def get_offer_by_name(self, name):
        self.cursor.execute(
            "SELECT name, description, discount, valid_from, valid_to, is_happy_hour FROM offers WHERE name LIKE ?",
            ('%' + name + '%',))
        return self.cursor.fetchone()

    def get_restaurant_info(self):
        self.cursor.execute("SELECT name, address, phone, opening_hours FROM restaurant_info LIMIT 1")
        return self.cursor.fetchone()

    def add_customer(self, name, phone=None, email=None):
        try:
            # Attempt to insert the customer. If it's a duplicate, it will be ignored.
            self.cursor.execute("INSERT OR IGNORE INTO customers (name, phone, email) VALUES (?, ?, ?)",
                                (name, phone, email))
            self.conn.commit()

            # Now, retrieve the ID. We need to handle cases where phone/email might be None.
            # If phone and email are both None, we'll try to find by name.
            # Otherwise, prioritize phone or email if they exist.
            customer_id = None
            if phone or email:
                self.cursor.execute("SELECT id FROM customers WHERE name = ? AND (phone = ? OR email = ?)",
                                    (name, phone, email))
                result = self.cursor.fetchone()
                if result:
                    customer_id = result[0]

            if customer_id is None and name:  # If not found by phone/email or if both are None, try by name alone
                self.cursor.execute("SELECT id FROM customers WHERE name = ? ORDER BY id DESC LIMIT 1", (name,))
                result = self.cursor.fetchone()
                if result:
                    customer_id = result[0]

            if customer_id is None:  # Fallback if for some reason it's still not found (shouldn't happen often)
                print(
                    f"Warning: Could not find customer ID after add_customer for name='{name}', phone='{phone}', email='{email}'")
                # As a last resort, if INSERT OR IGNORE just happened and lastrowid is available, use it.
                # This is less reliable if an IGNORE occurred because lastrowid would be 0 or -1
                # But if it's a true insert, it will give the new ID.
                if self.cursor.lastrowid and self.cursor.lastrowid > 0:
                    customer_id = self.cursor.lastrowid

            return customer_id
        except sqlite3.Error as e:
            print(f"Error adding customer: {e}")
            return None

    def create_order(self, customer_id, total_amount=0.0):
        try:
            self.cursor.execute("INSERT INTO orders (customer_id, total_amount, status) VALUES (?, ?, ?)",
                                (customer_id, total_amount, 'pending'))
            self.conn.commit()
            return self.cursor.lastrowid
        except sqlite3.Error as e:
            print(f"Error creating order: {e}")
            return None

    def add_order_item(self, order_id, menu_item_id, quantity, price_at_order):
        try:
            # Check if item already exists in order
            self.cursor.execute("SELECT quantity FROM order_items WHERE order_id = ? AND menu_item_id = ?",
                                (order_id, menu_item_id))
            existing_quantity = self.cursor.fetchone()

            if existing_quantity:
                new_quantity = existing_quantity[0] + quantity
                self.cursor.execute("UPDATE order_items SET quantity = ? WHERE order_id = ? AND menu_item_id = ?",
                                    (new_quantity, order_id, menu_item_id))
            else:
                self.cursor.execute(
                    "INSERT INTO order_items (order_id, menu_item_id, quantity, price_at_order) VALUES (?, ?, ?, ?)",
                    (order_id, menu_item_id, quantity, price_at_order))

            # Update total amount in orders table
            self.cursor.execute(
                "UPDATE orders SET total_amount = (SELECT SUM(quantity * price_at_order) FROM order_items WHERE order_id = ?) WHERE id = ?",
                (order_id, order_id))
            self.conn.commit()
            return True
        except sqlite3.Error as e:
            print(f"Error adding order item: {e}")
            return False

    def get_order_details(self, order_id):
        """Fetches details of an order including its creation timestamp."""
        self.cursor.execute("SELECT id, customer_id, order_date, total_amount, status FROM orders WHERE id = ?",
                            (order_id,))
        order_row = self.cursor.fetchone()
        if order_row:
            return {
                "id": order_row[0],
                "customer_id": order_row[1],
                "order_date": order_row[2],  # This will be a string, convert to datetime if needed
                "total_amount": order_row[3],
                "status": order_row[4]
            }
        return None

    def get_order_items(self, order_id):
        """Fetches all items for a given order ID."""
        self.cursor.execute("""
            SELECT oi.id, m.name, oi.quantity, oi.price_at_order
            FROM order_items oi
            JOIN menu m ON oi.menu_item_id = m.id
            WHERE oi.order_id = ?
        """, (order_id,))
        return self.cursor.fetchall()

    def get_order_item_details(self, order_id, item_name):
        """Fetches details of a specific item within an order by its name."""
        self.cursor.execute("""
            SELECT oi.id, m.id, m.name, oi.quantity, oi.price_at_order
            FROM order_items oi
            JOIN menu m ON oi.menu_item_id = m.id
            WHERE oi.order_id = ? AND m.name LIKE ?
        """, (order_id, f'%{item_name}%'))
        return self.cursor.fetchone()  # Returns (order_item_id, menu_item_id, name, quantity, price_at_order)

    def update_order_item_quantity(self, order_id, menu_item_id, new_quantity):
        """Updates the quantity of a specific item in an order."""
        try:
            if new_quantity <= 0:
                return self.remove_order_item(order_id, menu_item_id)

            self.cursor.execute("UPDATE order_items SET quantity = ? WHERE order_id = ? AND menu_item_id = ?",
                                (new_quantity, order_id, menu_item_id))
            self.cursor.execute(
                "UPDATE orders SET total_amount = (SELECT SUM(quantity * price_at_order) FROM order_items WHERE order_id = ?) WHERE id = ?",
                (order_id, order_id))
            self.conn.commit()
            return True
        except sqlite3.Error as e:
            print(f"Error updating order item quantity: {e}")
            return False

    def remove_order_item(self, order_id, menu_item_id):
        """Removes a specific item from an order."""
        try:
            self.cursor.execute("DELETE FROM order_items WHERE order_id = ? AND menu_item_id = ?",
                                (order_id, menu_item_id))
            # Update total amount in orders table, handle case if no items left
            self.cursor.execute(
                "UPDATE orders SET total_amount = (SELECT COALESCE(SUM(quantity * price_at_order), 0) FROM order_items WHERE order_id = ?) WHERE id = ?",
                (order_id, order_id))
            self.conn.commit()
            return True
        except sqlite3.Error as e:
            print(f"Error removing order item: {e}")
            return False

    def update_order_status(self, order_id, new_status):
        """Updates the status of an order."""
        try:
            self.cursor.execute("UPDATE orders SET status = ? WHERE id = ?", (new_status, order_id))
            self.conn.commit()
            return True
        except sqlite3.Error as e:
            print(f"Error updating order status: {e}")
            return False

    def get_available_tables(self, party_size, reservation_date, reservation_time):
        self.cursor.execute("""
            SELECT rt.table_number, rt.capacity
            FROM restaurant_tables rt
            LEFT JOIN reservations r ON rt.id = r.table_id
            AND r.reservation_date = ? AND r.reservation_time = ?
            WHERE r.table_id IS NULL AND rt.capacity >= ?
            ORDER BY rt.capacity ASC
        """, (reservation_date, reservation_time, party_size))
        return self.cursor.fetchall()

    def create_reservation(self, customer_id, table_id, reservation_date, reservation_time, party_size):
        try:
            self.cursor.execute(
                "INSERT INTO reservations (customer_id, table_id, reservation_date, reservation_time, party_size, status) VALUES (?, ?, ?, ?, ?, ?)",
                (customer_id, table_id, reservation_date, reservation_time, party_size, 'confirmed'))
            self.conn.commit()
            return self.cursor.lastrowid
        except sqlite3.IntegrityError:
            print("Error: Table already booked at this time.")
            return None
        except sqlite3.Error as e:
            print(f"Error creating reservation: {e}")
            return None

    def get_reservation_details(self, booking_id):
        """Fetches details of a reservation."""
        self.cursor.execute("""
            SELECT r.id, c.name, rt.table_number, r.reservation_date, r.reservation_time, r.party_size, r.status, r.created_at
            FROM reservations r
            JOIN customers c ON r.customer_id = c.id
            JOIN restaurant_tables rt ON r.table_id = rt.id
            WHERE r.id = ?
        """, (booking_id,))
        reservation_row = self.cursor.fetchone()
        if reservation_row:
            return {
                "id": reservation_row[0],
                "customer_name": reservation_row[1],
                "table_number": reservation_row[2],
                "reservation_date": reservation_row[3],
                "reservation_time": reservation_row[4],
                "party_size": reservation_row[5],
                "status": reservation_row[6],
                "created_at": reservation_row[7]  # Will be string, convert if needed
            }
        return None

    def get_customer_reservations(self, customer_id):
        """Fetches all reservations for a given customer ID."""
        self.cursor.execute("""
            SELECT r.id, rt.table_number, r.reservation_date, r.reservation_time, r.party_size, r.status
            FROM reservations r
            JOIN restaurant_tables rt ON r.table_id = rt.id
            WHERE r.customer_id = ?
            ORDER BY r.reservation_date ASC, r.reservation_time ASC
        """, (customer_id,))
        return self.cursor.fetchall()

    def update_reservation(self, booking_id, new_date=None, new_time=None, new_party_size=None, new_table_id=None):
        """Updates specific fields of a reservation."""
        try:
            updates = []
            params = []
            if new_date:
                updates.append("reservation_date = ?")
                params.append(new_date)
            if new_time:
                updates.append("reservation_time = ?")
                params.append(new_time)
            if new_party_size:
                updates.append("party_size = ?")
                params.append(new_party_size)
            if new_table_id:
                updates.append("table_id = ?")
                params.append(new_table_id)

            if not updates:
                return False  # No updates specified

            query = f"UPDATE reservations SET {', '.join(updates)} WHERE id = ?"
            params.append(booking_id)

            self.cursor.execute(query, tuple(params))
            self.conn.commit()
            return True
        except sqlite3.Error as e:
            print(f"Error updating reservation: {e}")
            return False

    def cancel_reservation(self, booking_id):
        """Cancels a reservation."""
        try:
            self.cursor.execute("UPDATE reservations SET status = 'cancelled' WHERE id = ?", (booking_id,))
            self.conn.commit()
            return True
        except sqlite3.Error as e:
            print(f"Error cancelling reservation: {e}")
            return False

    def store_feedback(self, customer_id, rating, comments):
        try:
            self.cursor.execute("INSERT INTO feedback (customer_id, rating, comments) VALUES (?, ?, ?)",
                                (customer_id, rating, comments))
            self.conn.commit()
            return True
        except sqlite3.Error as e:
            print(f"Error storing feedback: {e}")
            return False

    def get_menu_item_id_by_name(self, item_name):
        """Helper to get menu item ID by name."""
        self.cursor.execute("SELECT id FROM menu WHERE name LIKE ?", (f'%{item_name}%',))
        result = self.cursor.fetchone()
        return result[0] if result else None

    def update_customer(self, customer_id, name=None, phone=None, email=None):
        """Updates an existing customer's details."""
        try:
            updates = []
            params = []
            if name is not None:
                updates.append("name = ?")
                params.append(name)
            if phone is not None:
                updates.append("phone = ?")
                params.append(phone)
            if email is not None:
                updates.append("email = ?")
                params.append(email)

            if not updates:  # No updates provided
                return False

            query = f"UPDATE customers SET {', '.join(updates)} WHERE id = ?"
            params.append(customer_id)

            self.cursor.execute(query, tuple(params))
            self.conn.commit()
            return True
        except sqlite3.IntegrityError as e:
            print(f"Error updating customer: Duplicate phone or email. {e}")
            return False
        except sqlite3.Error as e:
            print(f"Error updating customer: {e}")
            return False

    def get_customer_details(self, customer_id):
        """Fetches customer details by ID."""
        self.cursor.execute("SELECT id, name, phone, email FROM customers WHERE id = ?", (customer_id,))
        return self.cursor.fetchone()
