from flask import Flask, render_template, request, redirect, session, url_for, jsonify, flash, send_from_directory
from flask_pymongo import PyMongo
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
import os
import logging
import threading
import datetime
from functools import wraps
import json
import uuid
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import schedule
import time
import atexit

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()
app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "devkey")
app.config["MONGO_URI"] = os.getenv("MONGO_URI")
app.config["PERMANENT_SESSION_LIFETIME"] = datetime.timedelta(hours=2)
app.config["UPLOAD_FOLDER"] = "uploads"
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16MB max file size
app.config["ALLOWED_EXTENSIONS"] = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif', 'doc', 'docx', 'ppt', 'pptx', 'xls', 'xlsx', 'zip', 'rar'}

# Enable CORS for API endpoints
CORS(app)

# Initialize rate limiter
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"]
)

# Ensure upload folder exists
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
os.makedirs(os.path.join(app.config["UPLOAD_FOLDER"], "avatars"), exist_ok=True)
os.makedirs(os.path.join(app.config["UPLOAD_FOLDER"], "materials"), exist_ok=True)

# Allowed file types
ALLOWED_EXTENSIONS = app.config["ALLOWED_EXTENSIONS"]

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# MongoDB
try:
    mongo = PyMongo(app)
    # Test the connection
    mongo.db.command('ping')
    logger.info("MongoDB connection established successfully")
except Exception as e:
    logger.error(f"Failed to connect to MongoDB: {e}")
    logger.warning("Application will run in demo mode without database persistence")
    mongo = None

# In-memory storage for demo mode (when MongoDB is not available)
demo_users = {}
demo_tasks = {}
demo_user_progress = {}
demo_files = {}
demo_notifications = {}
demo_reminders = {}
demo_study_groups = {}
demo_time_sessions = {}
demo_group_memberships = {}

# Decorators and utilities
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "username" not in session:
            return redirect("/")
        return f(*args, **kwargs)
    return decorated_function

def validate_input(text):
    """Sanitize and validate user input"""
    if not text:
        return ""
    # Basic sanitization
    dangerous_chars = ['<', '>', '"', "'", '&', 'script', 'javascript']
    sanitized = text
    for char in dangerous_chars:
        sanitized = sanitized.replace(char, '')
    return sanitized.strip()

def get_user_tasks(username):
    """Get tasks for a user"""
    if mongo:
        return list(mongo.db.tasks.find({"username": username}))
    else:
        return [task for task in demo_tasks.values() if task["username"] == username]

def get_user_progress(username):
    """Get user progress data"""
    if mongo:
        progress = mongo.db.progress.find_one({"username": username})
        if not progress:
            # Create initial progress
            initial_progress = {
                "username": username,
                "total_tasks": 0,
                "completed_tasks": 0,
                "points": 0,
                "level": "Beginner",
                "achievements": []
            }
            mongo.db.progress.insert_one(initial_progress)
            return initial_progress
        return progress
    else:
        if username not in demo_user_progress:
            demo_user_progress[username] = {
                "total_tasks": 0,
                "completed_tasks": 0,
                "points": 0,
                "level": "Beginner",
                "achievements": []
            }
        return demo_user_progress[username]

# Home/Login Page
@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = validate_input(request.form["username"])
        password = request.form["password"]
        
        if not username or len(username) < 3:
            flash("Username must be at least 3 characters long")
            return render_template("login.html")
        
        if mongo:
            # Use MongoDB if available
            user = mongo.db.users.find_one({"username": username})
            if user and check_password_hash(user["password"], password):
                session.permanent = True
                session["username"] = user["username"]
                return redirect("/dashboard")
        else:
            # Use demo mode (in-memory)
            if username in demo_users and check_password_hash(demo_users[username]["password"], password):
                session.permanent = True
                session["username"] = username
                return redirect("/dashboard")
            elif username == "demo" and password == "demo":
                # Quick demo login
                session.permanent = True
                session["username"] = "demo"
                return redirect("/dashboard")
        
        flash("❌ Invalid credentials")
    return render_template("login.html")

# Register Page
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = validate_input(request.form["username"])
        password = request.form["password"]
        
        # Input validation
        if not username or len(username) < 3:
            flash("Username must be at least 3 characters long")
            return render_template("register.html")
        
        if len(password) < 6:
            flash("Password must be at least 6 characters long")
            return render_template("register.html")
        
        password_hash = generate_password_hash(password)
        
        if mongo:
            # Use MongoDB if available
            if mongo.db.users.find_one({"username": username}):
                flash("⚠️ Username already exists")
                return render_template("register.html")
            mongo.db.users.insert_one({"username": username, "password": password_hash})
        else:
            # Use demo mode (in-memory)
            if username in demo_users:
                flash("⚠️ Username already exists")
                return render_template("register.html")
            demo_users[username] = {"username": username, "password": password_hash}
        
        flash("✅ Registration successful! Please login.")
        return redirect("/")
    return render_template("register.html")

# Protected Dashboard
@app.route("/dashboard")
@login_required
def dashboard():
    username = session['username']
    tasks = get_user_tasks(username)
    progress = get_user_progress(username)
    
    # Calculate statistics
    total_tasks = len(tasks)
    completed_tasks = len([t for t in tasks if t.get("completed", False)])
    completion_rate = (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0
    
    return render_template("dashboard.html", 
                         username=username, 
                         tasks=tasks, 
                         progress=progress,
                         total_tasks=total_tasks,
                         completed_tasks=completed_tasks,
                         completion_rate=completion_rate)

# Task Management Routes
@app.route("/tasks")
@login_required
def task_list():
    username = session['username']
    tasks = get_user_tasks(username)
    category_filter = request.args.get('category', 'all')
    difficulty_filter = request.args.get('difficulty', 'all')
    
    # Apply filters
    if category_filter != 'all':
        tasks = [t for t in tasks if t.get('category') == category_filter]
    if difficulty_filter != 'all':
        tasks = [t for t in tasks if t.get('difficulty') == difficulty_filter]
    
    return render_template("tasks.html", tasks=tasks, 
                         category_filter=category_filter,
                         difficulty_filter=difficulty_filter)

@app.route("/tasks/new", methods=["GET", "POST"])
@login_required
def create_task():
    if request.method == "POST":
        title = validate_input(request.form["title"])
        description = validate_input(request.form["description"])
        category = validate_input(request.form["category"])
        difficulty = validate_input(request.form["difficulty"])
        due_date = request.form.get("due_date")
        
        if not title:
            flash("Task title is required")
            return render_template("task_form.html")
        
        username = session['username']
        task_id = f"{username}_{datetime.datetime.now().timestamp()}"
        
        new_task = {
            "id": task_id,
            "title": title,
            "description": description,
            "category": category,
            "difficulty": difficulty,
            "due_date": due_date,
            "username": username,
            "completed": False,
            "created_at": datetime.datetime.now(),
            "points": {"easy": 5, "medium": 10, "hard": 20}.get(difficulty, 10)
        }
        
        if mongo:
            mongo.db.tasks.insert_one(new_task)
        else:
            demo_tasks[task_id] = new_task
        
        # Update progress
        update_user_progress(username, "task_added")
        flash("✅ Task created successfully!")
        return redirect("/tasks")
    
    return render_template("task_form.html")

@app.route("/tasks/<task_id>/edit", methods=["GET", "POST"])
@login_required
def edit_task(task_id):
    username = session['username']
    
    if mongo:
        task = mongo.db.tasks.find_one({"id": task_id, "username": username})
    else:
        task = demo_tasks.get(task_id)
    
    if not task:
        flash("Task not found")
        return redirect("/tasks")
    
    if request.method == "POST":
        title = validate_input(request.form["title"])
        description = validate_input(request.form["description"])
        category = validate_input(request.form["category"])
        difficulty = validate_input(request.form["difficulty"])
        due_date = request.form.get("due_date")
        
        if not title:
            flash("Task title is required")
            return render_template("task_form.html", task=task)
        
        updated_task = {
            "title": title,
            "description": description,
            "category": category,
            "difficulty": difficulty,
            "due_date": due_date,
            "points": {"easy": 5, "medium": 10, "hard": 20}.get(difficulty, 10)
        }
        
        if mongo:
            mongo.db.tasks.update_one(
                {"id": task_id, "username": username},
                {"$set": updated_task}
            )
        else:
            demo_tasks[task_id].update(updated_task)
        
        flash("✅ Task updated successfully!")
        return redirect("/tasks")
    
    return render_template("task_form.html", task=task)

@app.route("/tasks/<task_id>/complete")
@login_required
def complete_task(task_id):
    username = session['username']
    
    if mongo:
        task = mongo.db.tasks.find_one({"id": task_id, "username": username})
        if task:
            mongo.db.tasks.update_one(
                {"id": task_id, "username": username},
                {"$set": {"completed": True, "completed_at": datetime.datetime.now()}}
            )
            update_user_progress(username, "task_completed", task.get("points", 10))
    else:
        task = demo_tasks.get(task_id)
        if task and task["username"] == username:
            task["completed"] = True
            task["completed_at"] = datetime.datetime.now()
            update_user_progress(username, "task_completed", task.get("points", 10))
    
    flash("✅ Task completed! Great job!")
    return redirect("/tasks")

@app.route("/tasks/<task_id>/delete")
@login_required
def delete_task(task_id):
    username = session['username']
    
    if mongo:
        result = mongo.db.tasks.delete_one({"id": task_id, "username": username})
    else:
        if task_id in demo_tasks and demo_tasks[task_id]["username"] == username:
            del demo_tasks[task_id]
            result = True
        else:
            result = False
    
    if result:
        flash("✅ Task deleted successfully")
    else:
        flash("❌ Task not found")
    
    return redirect("/tasks")

def update_user_progress(username, action, points=0):
    """Update user progress based on actions"""
    progress = get_user_progress(username)
    
    if action == "task_added":
        progress["total_tasks"] += 1
    elif action == "task_completed":
        progress["completed_tasks"] += 1
        progress["points"] += points
        
        # Update level based on points
        if progress["points"] >= 500:
            progress["level"] = "Master"
        elif progress["points"] >= 300:
            progress["level"] = "Expert"
        elif progress["points"] >= 150:
            progress["level"] = "Advanced"
        elif progress["points"] >= 50:
            progress["level"] = "Intermediate"
    
    if mongo:
        mongo.db.progress.update_one(
            {"username": username},
            {"$set": progress},
            upsert=True
        )
    else:
        demo_user_progress[username] = progress

# File Upload Routes
@app.route("/upload", methods=["POST"])
@login_required
@limiter.limit("10 per minute")
def upload_file():
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400
    
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        # Add timestamp to avoid conflicts
        timestamp = str(int(time.time()))
        filename = f"{timestamp}_{filename}"
        
        # Determine upload subfolder
        file_type = request.form.get('file_type', 'materials')
        if file_type not in ['avatars', 'materials']:
            file_type = 'materials'
        
        upload_path = os.path.join(app.config["UPLOAD_FOLDER"], file_type)
        file_path = os.path.join(upload_path, filename)
        
        file.save(file_path)
        
        # Save file info to database
        username = session['username']
        file_info = {
            "id": str(uuid.uuid4()),
            "username": username,
            "original_filename": file.filename,
            "filename": filename,
            "file_type": file_type,
            "file_size": os.path.getsize(file_path),
            "upload_date": datetime.datetime.now(),
            "task_id": request.form.get('task_id')
        }
        
        if mongo:
            mongo.db.files.insert_one(file_info)
        else:
            demo_files[username] = demo_files.get(username, [])
            demo_files[username].append(file_info)
        
        return jsonify({
            "success": True,
            "file_id": file_info["id"],
            "filename": file_info["original_filename"],
            "file_size": file_info["file_size"]
        })
    
    return jsonify({"error": "File type not allowed"}), 400

@app.route("/uploads/<path:filename>")
@login_required
def uploaded_file(filename):
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)

@app.route("/files")
@login_required
def list_files():
    username = session['username']
    
    if mongo:
        files = list(mongo.db.files.find({"username": username}))
    else:
        files = demo_files.get(username, [])
    
    return render_template("files.html", files=files)

@app.route("/files/<file_id>/delete")
@login_required
def delete_file(file_id):
    username = session['username']
    
    if mongo:
        file_info = mongo.db.files.find_one({"id": file_id, "username": username})
        if file_info:
            # Delete physical file
            file_path = os.path.join(app.config["UPLOAD_FOLDER"], 
                                  file_info["file_type"], file_info["filename"])
            if os.path.exists(file_path):
                os.remove(file_path)
            # Delete database record
            mongo.db.files.delete_one({"id": file_id})
    else:
        files = demo_files.get(username, [])
        demo_files[username] = [f for f in files if f["id"] != file_id]
    
    flash("File deleted successfully")
    return redirect("/files")

# Notification System
def create_notification(username, title, message, notification_type="info"):
    """Create a notification for a user"""
    notification = {
        "id": str(uuid.uuid4()),
        "username": username,
        "title": title,
        "message": message,
        "type": notification_type,
        "read": False,
        "created_at": datetime.datetime.now()
    }
    
    if mongo:
        mongo.db.notifications.insert_one(notification)
    else:
        if username not in demo_notifications:
            demo_notifications[username] = []
        demo_notifications[username].append(notification)

@app.route("/notifications")
@login_required
def get_notifications():
    username = session['username']
    
    if mongo:
        notifications = list(mongo.db.notifications.find(
            {"username": username, "read": False}
        ).sort("created_at", -1).limit(10))
    else:
        notifications = demo_notifications.get(username, [])
        notifications = [n for n in notifications if not n["read"]]
        notifications.sort(key=lambda x: x["created_at"], reverse=True)
        notifications = notifications[:10]
    
    return jsonify({"notifications": notifications})

@app.route("/notifications/<notification_id>/read")
@login_required
def mark_notification_read(notification_id):
    username = session['username']
    
    if mongo:
        mongo.db.notifications.update_one(
            {"id": notification_id, "username": username},
            {"$set": {"read": True}}
        )
    else:
        notifications = demo_notifications.get(username, [])
        for notif in notifications:
            if notif["id"] == notification_id:
                notif["read"] = True
                break
    
    return jsonify({"success": True})

# Task Reminders
def create_reminder(username, task_id, reminder_time):
    """Create a task reminder"""
    reminder = {
        "id": str(uuid.uuid4()),
        "username": username,
        "task_id": task_id,
        "reminder_time": reminder_time,
        "sent": False,
        "created_at": datetime.datetime.now()
    }
    
    if mongo:
        mongo.db.reminders.insert_one(reminder)
    else:
        if username not in demo_reminders:
            demo_reminders[username] = []
        demo_reminders[username].append(reminder)

def check_reminders():
    """Check and send pending reminders"""
    current_time = datetime.datetime.now()
    
    if mongo:
        pending_reminders = mongo.db.reminders.find({
            "sent": False,
            "reminder_time": {"$lte": current_time}
        })
        
        for reminder in pending_reminders:
            task = mongo.db.tasks.find_one({"id": reminder["task_id"]})
            if task:
                create_notification(
                    reminder["username"],
                    "Task Reminder",
                    f"Reminder: '{task['title']}' is due soon!",
                    "reminder"
                )
            
            mongo.db.reminders.update_one(
                {"id": reminder["id"]},
                {"$set": {"sent": True}}
            )
    else:
        # Demo mode reminder check
        for username, reminders in demo_reminders.items():
            for reminder in reminders:
                if not reminder["sent"] and reminder["reminder_time"] <= current_time:
                    # Find task
                    user_tasks = [t for t in demo_tasks.values() if t["username"] == username]
                    task = next((t for t in user_tasks if t["id"] == reminder["task_id"]), None)
                    
                    if task:
                        create_notification(
                            username,
                            "Task Reminder",
                            f"Reminder: '{task['title']}' is due soon!",
                            "reminder"
                        )
                    
                    reminder["sent"] = True

# Background scheduler for reminders
def run_scheduler():
    """Run the reminder scheduler in background"""
    while True:
        schedule.run_pending()
        time.sleep(60)  # Check every minute

# Schedule reminder checking
schedule.every(5).minutes.do(check_reminders)

# Start background scheduler thread
scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
scheduler_thread.start()

# Calendar View
@app.route("/calendar")
@login_required
def calendar_view():
    username = session['username']
    tasks = get_user_tasks(username)
    
    # Convert tasks to calendar events
    events = []
    for task in tasks:
        if task.get('due_date'):
            events.append({
                "title": task['title'],
                "date": task['due_date'],
                "category": task.get('category', 'general'),
                "difficulty": task.get('difficulty', 'medium'),
                "completed": task.get('completed', False),
                "task_id": task['id']
            })
    
    return render_template("calendar.html", events=events)

# API Endpoints
@app.route("/api/tasks")
@login_required
def api_tasks():
    """API endpoint to get tasks"""
    username = session['username']
    tasks = get_user_tasks(username)
    return jsonify({"tasks": tasks})

@app.route("/api/tasks", methods=["POST"])
@login_required
@limiter.limit("20 per minute")
def api_create_task():
    """API endpoint to create task"""
    data = request.get_json()
    username = session['username']
    
    task_id = f"{username}_{datetime.datetime.now().timestamp()}"
    new_task = {
        "id": task_id,
        "title": validate_input(data.get("title", "")),
        "description": validate_input(data.get("description", "")),
        "category": validate_input(data.get("category", "general")),
        "difficulty": validate_input(data.get("difficulty", "medium")),
        "due_date": data.get("due_date"),
        "username": username,
        "completed": False,
        "created_at": datetime.datetime.now(),
        "points": {"easy": 5, "medium": 10, "hard": 20}.get(data.get("difficulty", "medium"), 10)
    }
    
    if mongo:
        mongo.db.tasks.insert_one(new_task)
    else:
        demo_tasks[task_id] = new_task
    
    update_user_progress(username, "task_added")
    return jsonify({"success": True, "task": new_task})

@app.route("/api/tasks/<task_id>", methods=["PUT"])
@login_required
@limiter.limit("20 per minute")
def api_update_task(task_id):
    """API endpoint to update task"""
    data = request.get_json()
    username = session['username']
    
    updated_task = {
        "title": validate_input(data.get("title", "")),
        "description": validate_input(data.get("description", "")),
        "category": validate_input(data.get("category", "general")),
        "difficulty": validate_input(data.get("difficulty", "medium")),
        "due_date": data.get("due_date")
    }
    
    if mongo:
        result = mongo.db.tasks.update_one(
            {"id": task_id, "username": username},
            {"$set": updated_task}
        )
        success = result.modified_count > 0
    else:
        if task_id in demo_tasks and demo_tasks[task_id]["username"] == username:
            demo_tasks[task_id].update(updated_task)
            success = True
        else:
            success = False
    
    return jsonify({"success": success})

@app.route("/api/stats")
@login_required
def api_stats():
    """API endpoint to get user statistics"""
    username = session['username']
    progress = get_user_progress(username)
    tasks = get_user_tasks(username)
    
    stats = {
        "total_tasks": len(tasks),
        "completed_tasks": len([t for t in tasks if t.get("completed", False)]),
        "points": progress["points"],
        "level": progress["level"],
        "completion_rate": (len([t for t in tasks if t.get("completed", False)]) / len(tasks) * 100) if tasks else 0
    }
    
    return jsonify(stats)

# Study Groups Routes
@app.route("/groups")
@login_required
def study_groups():
    username = session['username']
    
    if mongo:
        user_groups = list(mongo.db.study_groups.find({"members": username}))
        all_groups = list(mongo.db.study_groups.find())
    else:
        user_groups = [g for g in demo_study_groups.values() if username in g.get("members", [])]
        all_groups = list(demo_study_groups.values())
    
    return render_template("study_groups.html", user_groups=user_groups, all_groups=all_groups)

@app.route("/groups/new", methods=["GET", "POST"])
@login_required
def create_study_group():
    if request.method == "POST":
        name = validate_input(request.form["name"])
        description = validate_input(request.form["description"])
        is_private = request.form.get("is_private", "off") == "on"
        
        if not name:
            flash("Group name is required")
            return render_template("group_form.html")
        
        username = session['username']
        group_id = str(uuid.uuid4())
        
        new_group = {
            "id": group_id,
            "name": name,
            "description": description,
            "creator": username,
            "members": [username],
            "admins": [username],
            "is_private": is_private,
            "created_at": datetime.datetime.now(),
            "tasks": []
        }
        
        if mongo:
            mongo.db.study_groups.insert_one(new_group)
        else:
            demo_study_groups[group_id] = new_group
        
        flash("Study group created successfully!")
        return redirect("/groups")
    
    return render_template("group_form.html")

@app.route("/groups/<group_id>")
@login_required
def view_study_group(group_id):
    username = session['username']
    
    if mongo:
        group = mongo.db.study_groups.find_one({"id": group_id})
        if group:
            group_tasks = list(mongo.db.tasks.find({"group_id": group_id}))
            group_members = group["members"]
        else:
            group = None
    else:
        group = demo_study_groups.get(group_id)
        if group:
            group_tasks = [t for t in demo_tasks.values() if t.get("group_id") == group_id]
            group_members = group["members"]
        else:
            group = None
    
    if not group:
        flash("Study group not found")
        return redirect("/groups")
    
    if username not in group["members"] and group.get("is_private", False):
        flash("You don't have access to this private group")
        return redirect("/groups")
    
    return render_template("group_detail.html", group=group, group_tasks=group_tasks, is_member=username in group["members"])

@app.route("/groups/<group_id>/join")
@login_required
def join_study_group(group_id):
    username = session['username']
    
    if mongo:
        group = mongo.db.study_groups.find_one({"id": group_id})
        if group and username not in group["members"]:
            mongo.db.study_groups.update_one(
                {"id": group_id},
                {"$push": {"members": username}}
            )
            flash("Joined study group successfully!")
    else:
        group = demo_study_groups.get(group_id)
        if group and username not in group["members"]:
            group["members"].append(username)
            flash("Joined study group successfully!")
    
    return redirect(f"/groups/{group_id}")

@app.route("/groups/<group_id>/leave")
@login_required
def leave_study_group(group_id):
    username = session['username']
    
    if mongo:
        group = mongo.db.study_groups.find_one({"id": group_id})
        if group and username in group["members"]:
            mongo.db.study_groups.update_one(
                {"id": group_id},
                {"$pull": {"members": username}}
            )
            flash("Left study group successfully!")
    else:
        group = demo_study_groups.get(group_id)
        if group and username in group["members"]:
            group["members"].remove(username)
            flash("Left study group successfully!")
    
    return redirect("/groups")

@app.route("/groups/<group_id>/tasks", methods=["POST"])
@login_required
def create_group_task(group_id):
    username = session['username']
    
    # Check if user is a member of the group
    if mongo:
        group = mongo.db.study_groups.find_one({"id": group_id, "members": username})
    else:
        group = demo_study_groups.get(group_id)
        group = group if group and username in group["members"] else None
    
    if not group:
        return jsonify({"error": "Not a member of this group"}), 403
    
    title = validate_input(request.form["title"])
    description = validate_input(request.form["description"])
    category = validate_input(request.form["category"])
    difficulty = validate_input(request.form["difficulty"])
    due_date = request.form.get("due_date")
    
    if not title:
        return jsonify({"error": "Task title is required"}), 400
    
    task_id = f"{username}_{datetime.datetime.now().timestamp()}"
    
    new_task = {
        "id": task_id,
        "title": title,
        "description": description,
        "category": category,
        "difficulty": difficulty,
        "due_date": due_date,
        "username": username,
        "group_id": group_id,
        "completed": False,
        "created_at": datetime.datetime.now(),
        "points": {"easy": 5, "medium": 10, "hard": 20}.get(difficulty, 10)
    }
    
    if mongo:
        mongo.db.tasks.insert_one(new_task)
        mongo.db.study_groups.update_one(
            {"id": group_id},
            {"$push": {"tasks": task_id}}
        )
    else:
        demo_tasks[task_id] = new_task
        group["tasks"].append(task_id)
    
    return jsonify({"success": True, "task": new_task})

# Time Tracking Routes
@app.route("/time/start/<task_id>", methods=["POST"])
@login_required
def start_time_session(task_id):
    username = session['username']
    
    # Check if task exists and belongs to user
    if mongo:
        task = mongo.db.tasks.find_one({"id": task_id, "username": username})
    else:
        task = demo_tasks.get(task_id)
        task = task if task and task["username"] == username else None
    
    if not task:
        return jsonify({"error": "Task not found"}), 404
    
    # Check if there's already an active session
    if mongo:
        active_session = mongo.db.time_sessions.find_one({
            "username": username,
            "task_id": task_id,
            "end_time": None
        })
    else:
        active_session = next((s for s in demo_time_sessions.values() 
                             if s["username"] == username and s["task_id"] == task_id and s["end_time"] is None), None)
    
    if active_session:
        return jsonify({"error": "Timer already running for this task"}), 400
    
    session_id = str(uuid.uuid4())
    new_session = {
        "id": session_id,
        "username": username,
        "task_id": task_id,
        "start_time": datetime.datetime.now(),
        "end_time": None,
        "duration": None,
        "created_at": datetime.datetime.now()
    }
    
    if mongo:
        mongo.db.time_sessions.insert_one(new_session)
    else:
        demo_time_sessions[session_id] = new_session
    
    return jsonify({"success": True, "session_id": session_id, "start_time": new_session["start_time"]})

@app.route("/time/stop/<session_id>", methods=["POST"])
@login_required
def stop_time_session(session_id):
    username = session['username']
    
    if mongo:
        time_session = mongo.db.time_sessions.find_one({"id": session_id, "username": username})
    else:
        time_session = demo_time_sessions.get(session_id)
        time_session = time_session if time_session and time_session["username"] == username else None
    
    if not time_session:
        return jsonify({"error": "Time session not found"}), 404
    
    if time_session["end_time"]:
        return jsonify({"error": "Session already ended"}), 400
    
    end_time = datetime.datetime.now()
    duration = (end_time - time_session["start_time"]).total_seconds()
    
    if mongo:
        mongo.db.time_sessions.update_one(
            {"id": session_id},
            {"$set": {"end_time": end_time, "duration": duration}}
        )
    else:
        time_session["end_time"] = end_time
        time_session["duration"] = duration
    
    return jsonify({
        "success": True, 
        "end_time": end_time,
        "duration": duration
    })

@app.route("/time/sessions")
@login_required
def get_time_sessions():
    username = session['username']
    
    if mongo:
        sessions = list(mongo.db.time_sessions.find({"username": username}).sort("start_time", -1))
    else:
        sessions = [s for s in demo_time_sessions.values() if s["username"] == username]
        sessions.sort(key=lambda x: x["start_time"], reverse=True)
    
    return jsonify({"sessions": sessions})

@app.route("/time/stats")
@login_required
def get_time_stats():
    username = session['username']
    
    if mongo:
        sessions = list(mongo.db.time_sessions.find({"username": username, "end_time": {"$ne": None}}))
    else:
        sessions = [s for s in demo_time_sessions.values() 
                   if s["username"] == username and s["end_time"] is not None]
    
    total_time = sum(s["duration"] for s in sessions) if sessions else 0
    total_sessions = len(sessions)
    avg_session_time = total_time / total_sessions if total_sessions > 0 else 0
    
    # Get task details
    task_time_map = {}
    for session in sessions:
        task_id = session["task_id"]
        if task_id not in task_time_map:
            task_time_map[task_id] = 0
        task_time_map[task_id] += session["duration"]
    
    stats = {
        "total_time_seconds": total_time,
        "total_time_formatted": format_duration(total_time),
        "total_sessions": total_sessions,
        "avg_session_time_formatted": format_duration(avg_session_time),
        "task_time_breakdown": task_time_map
    }
    
    return jsonify(stats)

def format_duration(seconds):
    """Format duration in seconds to human readable format"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    
    if hours > 0:
        return f"{hours}h {minutes}m {secs}s"
    elif minutes > 0:
        return f"{minutes}m {secs}s"
    else:
        return f"{secs}s"

# Logout
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

if __name__ == "__main__":
    # Configure threading for better concurrent request handling
    app.run(debug=True, host="0.0.0.0", port=5000, threaded=True)
