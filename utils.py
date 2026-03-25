"""
EduTasker Utility Functions

This file contains helper functions and utilities for the EduTasker application.
"""

import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional

def validate_username(username: str) -> bool:
    """
    Validate username format
    - Must be 3-20 characters long
    - Can only contain letters, numbers, and underscores
    """
    if not username or len(username) < 3 or len(username) > 20:
        return False
    return re.match(r'^[a-zA-Z0-9_]+$', username) is not None

def validate_password(password: str) -> Dict[str, bool]:
    """
    Validate password strength
    Returns dictionary with validation results
    """
    result = {
        'is_valid': True,
        'min_length': len(password) >= 8,
        'has_upper': any(c.isupper() for c in password),
        'has_lower': any(c.islower() for c in password),
        'has_digit': any(c.isdigit() for c in password),
        'has_special': any(c in '!@#$%^&*()_+-=[]{}|;:,.<>?' for c in password)
    }
    
    # Password is valid if it meets minimum requirements
    result['is_valid'] = (result['min_length'] and 
                         (result['has_upper'] or result['has_lower']) and 
                         result['has_digit'])
    
    return result

def format_date(date_obj: datetime) -> str:
    """Format datetime object for display"""
    if not date_obj:
        return "N/A"
    return date_obj.strftime("%B %d, %Y at %I:%M %p")

def calculate_completion_rate(completed_tasks: int, total_tasks: int) -> float:
    """Calculate task completion rate as percentage"""
    if total_tasks == 0:
        return 0.0
    return round((completed_tasks / total_tasks) * 100, 1)

def get_streak_days(last_activity: datetime) -> int:
    """Calculate streak days based on last activity"""
    if not last_activity:
        return 0
    
    today = datetime.utcnow()
    days_diff = (today - last_activity).days
    
    if days_diff == 0:
        return 1  # Active today
    elif days_diff == 1:
        return 2  # Active yesterday and today
    else:
        return 1  # Only active today

def sanitize_input(text: str) -> str:
    """Sanitize user input to prevent XSS"""
    if not text:
        return ""
    
    # Remove potentially dangerous characters
    dangerous_chars = ['<', '>', '"', "'", '&', 'script', 'javascript']
    sanitized = text
    
    for char in dangerous_chars:
        sanitized = sanitized.replace(char, '')
    
    return sanitized.strip()

def generate_task_suggestions(difficulty: str, category: str) -> List[str]:
    """Generate task suggestions based on difficulty and category"""
    suggestions = {
        'easy': {
            'math': ['Practice basic arithmetic', 'Solve 5 simple equations', 'Complete a math worksheet'],
            'science': ['Read a science article', 'Watch an educational video', 'Complete a simple experiment'],
            'general': ['Read for 15 minutes', 'Write a short summary', 'Complete a quick quiz']
        },
        'medium': {
            'math': ['Solve 10 algebra problems', 'Complete a geometry exercise', 'Practice word problems'],
            'science': ['Write a lab report', 'Research a scientific topic', 'Complete a medium experiment'],
            'general': ['Write a 500-word essay', 'Create a study guide', 'Complete a chapter review']
        },
        'hard': {
            'math': ['Solve complex calculus problems', 'Complete advanced proofs', 'Work on challenging equations'],
            'science': ['Design an experiment', 'Write a research paper', 'Analyze complex data'],
            'general': ['Complete a project', 'Write a detailed analysis', 'Create comprehensive notes']
        }
    }
    
    return suggestions.get(difficulty, {}).get(category, ['Complete your assigned task'])

def calculate_points(difficulty: str, completed: bool = True) -> int:
    """Calculate points based on task difficulty and completion"""
    if not completed:
        return 0
    
    points_map = {
        'easy': 5,
        'medium': 10,
        'hard': 20
    }
    
    return points_map.get(difficulty, 10)

def get_level_from_points(points: int) -> Dict[str, str]:
    """Determine user level based on points"""
    if points < 50:
        return {'level': 'Beginner', 'badge': '🌱'}
    elif points < 150:
        return {'level': 'Intermediate', 'badge': '🌿'}
    elif points < 300:
        return {'level': 'Advanced', 'badge': '🌳'}
    elif points < 500:
        return {'level': 'Expert', 'badge': '🌲'}
    else:
        return {'level': 'Master', 'badge': '🏆'}

def format_time_spent(minutes: int) -> str:
    """Format time spent in human readable format"""
    if minutes < 60:
        return f"{minutes} minutes"
    elif minutes < 1440:  # Less than 24 hours
        hours = minutes // 60
        remaining_minutes = minutes % 60
        return f"{hours}h {remaining_minutes}m" if remaining_minutes else f"{hours} hours"
    else:
        days = minutes // 1440
        remaining_hours = (minutes % 1440) // 60
        return f"{days}d {remaining_hours}h" if remaining_hours else f"{days} days"