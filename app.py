from flask import Flask, render_template, request, redirect, session, url_for
from flask_pymongo import PyMongo
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()
app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "devkey")
app.config["MONGO_URI"] = os.getenv("MONGO_URI")

# MongoDB
mongo = PyMongo(app)

# Home/Login Page
@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user = mongo.db.users.find_one({"username": request.form["username"]})
        if user and check_password_hash(user["password"], request.form["password"]):
            session["username"] = user["username"]
            return redirect("/dashboard")
        return "❌ Invalid credentials"
    return render_template("login.html")

# Register Page
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        password = generate_password_hash(request.form["password"])
        if mongo.db.users.find_one({"username": username}):
            return "⚠️ Username already exists"
        mongo.db.users.insert_one({"username": username, "password": password})
        return redirect("/")
    return render_template("register.html")

# Protected Dashboard
@app.route("/dashboard")
def dashboard():
    if "username" in session:
        return f"Welcome {session['username']}! 🧠"
    return redirect("/")

# Logout
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")
