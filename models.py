"""
EduTasker Models

This file contains data models and database schemas for the EduTasker application.
"""

from datetime import datetime
from typing import Dict, List, Optional

class User:
    """User model for authentication and profile management"""
    
    def __init__(self, username: str, password_hash: str, email: str = None):
        self.username = username
        self.password_hash = password_hash
        self.email = email
        self.created_at = datetime.utcnow()
        self.is_active = True
    
    def to_dict(self) -> Dict:
        """Convert user to dictionary for database storage"""
        return {
            "username": self.username,
            "password": self.password_hash,
            "email": self.email,
            "created_at": self.created_at,
            "is_active": self.is_active
        }

class Task:
    """Task model for educational tasks"""
    
    def __init__(self, title: str, description: str, username: str, 
                 difficulty: str = "medium", category: str = "general"):
        self.title = title
        self.description = description
        self.username = username
        self.difficulty = difficulty
        self.category = category
        self.created_at = datetime.utcnow()
        self.completed = False
        self.completed_at = None
    
    def to_dict(self) -> Dict:
        """Convert task to dictionary for database storage"""
        return {
            "title": self.title,
            "description": self.description,
            "username": self.username,
            "difficulty": self.difficulty,
            "category": self.category,
            "created_at": self.created_at,
            "completed": self.completed,
            "completed_at": self.completed_at
        }
    
    def mark_completed(self):
        """Mark task as completed"""
        self.completed = True
        self.completed_at = datetime.utcnow()

class Progress:
    """Progress tracking model"""
    
    def __init__(self, username: str):
        self.username = username
        self.total_tasks = 0
        self.completed_tasks = 0
        self.streak_days = 0
        self.last_activity = datetime.utcnow()
        self.points = 0
    
    def to_dict(self) -> Dict:
        """Convert progress to dictionary for database storage"""
        return {
            "username": self.username,
            "total_tasks": self.total_tasks,
            "completed_tasks": self.completed_tasks,
            "streak_days": self.streak_days,
            "last_activity": self.last_activity,
            "points": self.points
        }
    
    def update_progress(self, task_completed: bool = True):
        """Update user progress"""
        self.last_activity = datetime.utcnow()
        if task_completed:
            self.completed_tasks += 1
            self.points += 10
    
    def add_task(self):
        """Increment total tasks count"""
        self.total_tasks += 1

# Database collection schemas
USER_SCHEMA = {
    "username": str,
    "password": str,  # Hashed password
    "email": str,
    "created_at": datetime,
    "is_active": bool
}

TASK_SCHEMA = {
    "title": str,
    "description": str,
    "username": str,
    "difficulty": str,  # "easy", "medium", "hard"
    "category": str,
    "created_at": datetime,
    "completed": bool,
    "completed_at": datetime
}

PROGRESS_SCHEMA = {
    "username": str,
    "total_tasks": int,
    "completed_tasks": int,
    "streak_days": int,
    "last_activity": datetime,
    "points": int
}