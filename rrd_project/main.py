from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from functools import wraps
import pandas as pd
import uuid
import os
from werkzeug.utils import secure_filename
import pickle

app = Flask(__name__)
app.secret_key = "your_secret_key"  # Replace with a random secret key

UPLOAD_FOLDER = "static/uploads"
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif"}

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER


# Load user data from pickle file
def load_users():
    try:
        with open("users.pkl", "rb") as f:
            return pickle.load(f)
    except FileNotFoundError:
        return []


# Save user data to pickle file
def save_users(users):
    with open("users.pkl", "wb") as f:
        pickle.dump(users, f)


# Login required decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)

    return decorated_function


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route("/")
def home():
    return render_template("login.html")


@app.route("/buy_pro")
@login_required
def buy_pro():
    # Read the Excel file
    excel_file_path = "sell_products.xlsx"  # Update with your actual file path
    df = pd.read_excel(excel_file_path)

    # Convert DataFrame to a list of dictionaries
    products = df.to_dict(orient="records")

    return render_template("buy.html", products=products)


@app.route("/view")
@login_required
def view():
    # Read the Excel file
    excel_file_path = "sell_products.xlsx"  # Update with your actual file path
    df = pd.read_excel(excel_file_path)

    # Convert DataFrame to a list of dictionaries
    products = df.to_dict(orient="records")

    return render_template("view.html", products=products)


@app.route("/add_to_cart", methods=["POST"])
@login_required
def add_to_cart():
    product_name = request.json.get("product_name")
    quantity = int(request.json.get("quantity"))
    user_id = session["user_id"]

    # Fetch the product details including the cost
    excel_file_path = "sell_products.xlsx"  # Update with your actual file path
    df_products = pd.read_excel(excel_file_path)
    product = df_products.loc[df_products["Product Name"] == product_name]

    if product.empty:
        return jsonify({"success": False, "message": "Product not found"}), 404

    cost = product["Product Price"].values[0]

    cart_file_path = "cart.xlsx"  # Update with your actual file path
    df_cart = (
        pd.read_excel(cart_file_path)
        if os.path.exists(cart_file_path)
        else pd.DataFrame(columns=["Product Name", "Quantity", "Cost", "User ID"])
    )

    existing_item = df_cart.loc[
        (df_cart["Product Name"] == product_name) & (df_cart["User ID"] == user_id)
    ]

    if not existing_item.empty:
        df_cart.loc[
            (df_cart["Product Name"] == product_name) & (df_cart["User ID"] == user_id),
            "Quantity",
        ] += quantity
    else:
        new_cart_item = {
            "Product Name": product_name,
            "Quantity": quantity,
            "Cost": cost,
            "User ID": user_id,
        }
        df_cart = pd.concat([df_cart, pd.DataFrame([new_cart_item])], ignore_index=True)

    df_cart.to_excel(cart_file_path, index=False)

    return jsonify({"success": True}), 200


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    if request.method == "POST":
        product_name = request.form["product-name"]
        product_price = request.form["product-price"]
        product_quantity = request.form["product-quantity"]
        product_image = request.files["product-image"]

        if product_image and allowed_file(product_image.filename):
            filename = secure_filename(product_image.filename)
            unique_filename = str(uuid.uuid4()) + os.path.splitext(filename)[1]
            product_image.save(
                os.path.join(app.config["UPLOAD_FOLDER"], unique_filename)
            )

        added_by = session["username"]  # Use username for Added By
        seller_id = session["user_id"]  # Use user ID for Seller ID

        new_product = {
            "Product Name": product_name,
            "Product Price": product_price,
            "Product Quantity": product_quantity,
            "Product Image": unique_filename,
            "Added By": added_by,
            "Seller ID": seller_id,
        }

        excel_file_path = "sell_products.xlsx"  # Update with your actual file path
        df = pd.read_excel(excel_file_path)
        df = pd.concat([df, pd.DataFrame([new_product])], ignore_index=True)
        df.to_excel(excel_file_path, index=False)

        return render_template(
            "sell.html", product_added=True, product_name=product_name
        )

    return render_template("sell.html", product_added=False)


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        users = load_users()

        for user in users:
            if user["username"] == username and user["password"] == password:
                session["user_id"] = user["id"]  # Store user ID in session
                session["username"] = user["username"]  # Store username in session
                return redirect(url_for("dashboard"))  # Redirect to dashboard

        return "Invalid credentials", 403  # Handle invalid login attempt

    return render_template("login.html")


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        users = load_users()

        if any(user["username"] == username for user in users):
            return "Username already exists", 400

        user_id = str(uuid.uuid4())
        new_user = {"id": user_id, "username": username, "password": password}

        users.append(new_user)
        save_users(users)

        return redirect(url_for("login"))

    return render_template("signup.html")


@app.route("/cart")
@login_required
def cart():
    user_id = session["user_id"]
    cart_file_path = "cart.xlsx"  # Update with your actual file path
    df = (
        pd.read_excel(cart_file_path)
        if os.path.exists(cart_file_path)
        else pd.DataFrame(columns=["Product Name", "Quantity", "Cost", "User ID"])
    )

    cart_items = df.loc[df["User ID"] == user_id]

    return render_template("cart.html", cart_items=cart_items.to_dict(orient="records"))


@app.route("/dashboard")
@login_required
def dashboard():
    return render_template("dashboard.html")


@app.route("/logout")
def logout():
    session.pop("user_id", None)
    session.pop("username", None)
    return redirect(url_for("login"))


@app.route("/bill")
@login_required
def bill():
    user_id = session["user_id"]
    cart_file_path = "cart.xlsx"  # Update with your actual file path
    df = (
        pd.read_excel(cart_file_path)
        if os.path.exists(cart_file_path)
        else pd.DataFrame(columns=["Product Name", "Quantity", "Cost", "User ID"])
    )

    # Filter cart items for the current user
    cart_items = df.loc[df["User ID"] == user_id]

    # Convert DataFrame to a list of dictionaries
    cart_items_list = cart_items.to_dict(orient="records")

    # Debugging: Print cart items to console
    print(cart_items_list)

    return render_template("bill.html", cart_items=cart_items_list)


@app.route("/confirm_order", methods=["POST", "GET"])
@login_required
def confirm_order():
    if request.method == "POST":
        user_id = session["user_id"]
        name = request.form.get("name")
        email = request.form.get("email")

        cart_file_path = "cart.xlsx"  # Update with your actual file path
        df = (
            pd.read_excel(cart_file_path)
            if os.path.exists(cart_file_path)
            else pd.DataFrame(columns=["Product Name", "Quantity", "Cost", "User ID"])
        )

        # Store user details and cart items in session
        session["user_details"] = {"name": name, "email": email}
        session["cart_items"] = df.loc[df["User ID"] == user_id].to_dict(
            orient="records"
        )

        # Clear the user's cart
        df = df.loc[df["User ID"] != user_id]
        df.to_excel(cart_file_path, index=False)

        return redirect(url_for("receipt"))

    return redirect(url_for("cart"))


@app.route("/receipt")
@login_required
def receipt():
    user_details = session.get("user_details", {})
    cart_items = session.get("cart_items", [])

    return render_template(
        "receipt.html", user_details=user_details, cart_items=cart_items
    )


@app.route("/order_confirmation")
@login_required
def order_confirmation():
    return render_template("order_confirmation.html")


@app.route("/clear_cart", methods=["POST"])
@login_required
def clear_cart():
    user_id = session["user_id"]

    cart_file_path = "cart.xlsx"  # Update with your actual file path
    df = (
        pd.read_excel(cart_file_path)
        if os.path.exists(cart_file_path)
        else pd.DataFrame(columns=["Product Name", "Quantity", "Cost", "User ID"])
    )

    df = df.loc[df["User ID"] != user_id]

    df.to_excel(cart_file_path, index=False)

    return jsonify({"success": True}), 200


@app.route("/check_availability", methods=["POST"])
@login_required
def check_availability():
    product_name = request.json.get("product_name")
    quantity = int(request.json.get("quantity"))

    excel_file_path = "sell_products.xlsx"  # Update with your actual file path
    df = pd.read_excel(excel_file_path)

    product = df.loc[df["Product Name"] == product_name]

    if not product.empty:
        available_quantity = product["Product Quantity"].values[0]
        if available_quantity >= quantity:
            return jsonify({"available": True}), 200
        else:
            return (
                jsonify(
                    {"available": False, "message": "Not enough quantity available"}
                ),
                400,
            )
    else:
        return jsonify({"available": False, "message": "Product not found"}), 404


if __name__ == "__main__":
    app.run(debug=True)
