from sqlalchemy import create_engine, Column, String, Date, Time, Text, Integer, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime, date, timedelta
import os
from dotenv import load_dotenv
import pytz
import logging
import re
from constants import DEFAULT_TIMEZONE

# Load environment variables
load_dotenv()

# Get database URL from environment
DATABASE_URL = os.getenv("DATABASE_URL")

# Create database engine
engine = create_engine(DATABASE_URL)

# Create declarative base
Base = declarative_base()

class DailyData(Base):
    """Table for storing daily ChatGPT responses"""
    __tablename__ = 'daily_data'

    # Using composite primary key of date and time
    date = Column(Date, primary_key=True)
    time = Column(Time, primary_key=True)
    username = Column(String)
    gpt_response = Column(String)
    calories = Column(Float)  # Add calories column

    def __repr__(self):
        return f"<DailyData(date={self.date}, time={self.time}, username={self.username}, calories={self.calories})>"

class NutritionGoals(Base):
    """Table for storing user nutrition goals"""
    __tablename__ = 'nutrition_goals'

    username = Column(String, primary_key=True)
    goals = Column(Text)
    updated_at = Column(Date)

    def __repr__(self):
        return f"<NutritionGoals(username={self.username})>"

class WeightGoal(Base):
    """Table for storing user's target weight"""
    __tablename__ = 'weight_goals'

    username = Column(String, primary_key=True)
    target_weight = Column(Float)
    updated_at = Column(Date)

    def __repr__(self):
        return f"<WeightGoal(username={self.username}, target_weight={self.target_weight})>"

class WeightHistory(Base):
    """Table for storing user's weight measurements"""
    __tablename__ = 'weight_history'

    id = Column(Integer, primary_key=True)
    username = Column(String)
    weight = Column(Float)
    measured_at = Column(Date)

    def __repr__(self):
        return f"<WeightHistory(username={self.username}, weight={self.weight}, date={self.measured_at})>"

# Create all tables
Base.metadata.create_all(engine)

# Create session factory
SessionLocal = sessionmaker(bind=engine)

def extract_calories(gpt_response: str) -> float:
    """
    Extract total calories from GPT response
    Args:
        gpt_response: GPT response text
    Returns:
        float: Total calories or 0 if not found
    """
    try:
        # Ищем строки с упоминанием калорий
        matches = re.findall(r'(\d+(?:\.\d+)?)\s*(?:к?кал|ккал|калори[йя])', gpt_response.lower())
        if matches:
            # Берем последнее число (обычно это общая сумма)
            return float(matches[-1])
        return 0
    except Exception as e:
        logging.error(f"Error extracting calories: {str(e)}")
        return 0

def save_gpt_response(response: str, username: str):
    """
    Save ChatGPT response to database with current date and time
    Args:
        response: GPT response text
        username: Telegram username of the user
    """
    # Get current date and time in user's timezone
    tz = pytz.timezone(DEFAULT_TIMEZONE)
    now = datetime.now(tz)
    
    # Extract calories from response
    calories = extract_calories(response)
    
    session = SessionLocal()
    try:
        daily_data = DailyData(
            date=now.date(),
            time=now.time(),
            username=username,
            gpt_response=response,
            calories=calories
        )
        session.add(daily_data)
        session.commit()
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()

def get_daily_calories(username: str, target_date: date = None) -> float:
    """
    Get total calories for a specific date
    Args:
        username: Telegram username of the user
        target_date: Date to get calories for (defaults to today)
    Returns:
        float: Total calories for the day
    """
    if target_date is None:
        target_date = datetime.now(pytz.timezone(DEFAULT_TIMEZONE)).date()
    
    session = SessionLocal()
    try:
        daily_records = session.query(DailyData)\
            .filter(DailyData.username == username)\
            .filter(DailyData.date == target_date)\
            .all()
        
        total_calories = sum(record.calories for record in daily_records if record.calories is not None)
        return total_calories
    except Exception as e:
        logging.error(f"Error getting daily calories: {str(e)}")
        return 0
    finally:
        session.close()

def save_nutrition_goals(username: str, goals: str) -> bool:
    """
    Save or update user's nutrition goals
    Args:
        username: Telegram username of the user
        goals: Nutrition goals text
    Returns:
        bool: True if successful, False if error occurred
    """
    session = SessionLocal()
    try:
        # Check if goals already exist for this user
        existing_goals = session.query(NutritionGoals).filter_by(username=username).first()
        
        if existing_goals:
            # Update existing goals
            existing_goals.goals = goals
            existing_goals.updated_at = datetime.now().date()
        else:
            # Create new goals
            new_goals = NutritionGoals(
                username=username,
                goals=goals,
                updated_at=datetime.now().date()
            )
            session.add(new_goals)
        
        session.commit()
        return True
    except Exception as e:
        session.rollback()
        logging.error(f"Error saving nutrition goals: {str(e)}")
        return False
    finally:
        session.close()

def get_nutrition_goals(username: str) -> str:
    """
    Get user's nutrition goals
    Args:
        username: Telegram username of the user
    Returns:
        str: User's nutrition goals or None if not found
    """
    session = SessionLocal()
    try:
        goals = session.query(NutritionGoals).filter_by(username=username).first()
        return goals.goals if goals else None
    except Exception as e:
        logging.error(f"Error getting nutrition goals: {str(e)}")
        return None
    finally:
        session.close()

def get_all_active_users() -> list:
    """
    Get list of all users who have used the bot
    Returns:
        list: List of unique usernames
    """
    session = SessionLocal()
    try:
        users = session.query(DailyData.username)\
            .distinct()\
            .filter(DailyData.username.isnot(None))\
            .all()
        return [user[0] for user in users]
    except Exception as e:
        logging.error(f"Error getting active users: {str(e)}")
        return []
    finally:
        session.close()

def get_daily_food_records(username: str, target_date: date = None) -> list:
    """
    Get all food records for a specific date
    Args:
        username: Telegram username of the user
        target_date: Date to get records for (defaults to today)
    Returns:
        list: List of tuples (time, gpt_response) for the day
    """
    if target_date is None:
        target_date = datetime.now(pytz.timezone(DEFAULT_TIMEZONE)).date()
    
    session = SessionLocal()
    try:
        daily_records = session.query(DailyData)\
            .filter(DailyData.username == username)\
            .filter(DailyData.date == target_date)\
            .order_by(DailyData.time)\
            .all()
        
        return [(record.time, record.gpt_response) for record in daily_records]
    except Exception as e:
        logging.error(f"Error getting daily food records: {str(e)}")
        return []
    finally:
        session.close()

def save_weight_goal(username: str, target_weight: float) -> bool:
    """
    Save or update user's target weight
    Args:
        username: Telegram username of the user
        target_weight: Target weight in kg
    Returns:
        bool: True if successful, False if error occurred
    """
    session = SessionLocal()
    try:
        existing_goal = session.query(WeightGoal).filter_by(username=username).first()
        
        if existing_goal:
            existing_goal.target_weight = target_weight
            existing_goal.updated_at = datetime.now().date()
        else:
            new_goal = WeightGoal(
                username=username,
                target_weight=target_weight,
                updated_at=datetime.now().date()
            )
            session.add(new_goal)
        
        session.commit()
        return True
    except Exception as e:
        session.rollback()
        logging.error(f"Error saving weight goal: {str(e)}")
        return False
    finally:
        session.close()

def get_weight_goal(username: str) -> float:
    """
    Get user's target weight
    Args:
        username: Telegram username of the user
    Returns:
        float: Target weight or None if not found
    """
    session = SessionLocal()
    try:
        goal = session.query(WeightGoal).filter_by(username=username).first()
        return goal.target_weight if goal else None
    except Exception as e:
        logging.error(f"Error getting weight goal: {str(e)}")
        return None
    finally:
        session.close()

def save_weight_measurement(username: str, weight: float, measured_at: date = None) -> bool:
    """
    Save user's weight measurement
    Args:
        username: Telegram username of the user
        weight: Weight in kg
        measured_at: Date of measurement (defaults to today)
    Returns:
        bool: True if successful, False if error occurred
    """
    if measured_at is None:
        measured_at = datetime.now(pytz.timezone(DEFAULT_TIMEZONE)).date()
    
    session = SessionLocal()
    try:
        measurement = WeightHistory(
            username=username,
            weight=weight,
            measured_at=measured_at
        )
        session.add(measurement)
        session.commit()
        return True
    except Exception as e:
        session.rollback()
        logging.error(f"Error saving weight measurement: {str(e)}")
        return False
    finally:
        session.close()

def get_weight_history(username: str, limit: int = None) -> list:
    """
    Get user's weight history
    Args:
        username: Telegram username of the user
        limit: Maximum number of records to return (newest first)
    Returns:
        list: List of tuples (date, weight)
    """
    session = SessionLocal()
    try:
        query = session.query(WeightHistory)\
            .filter_by(username=username)\
            .order_by(WeightHistory.measured_at.desc())
        
        if limit:
            query = query.limit(limit)
            
        records = query.all()
        return [(record.measured_at, record.weight) for record in records]
    except Exception as e:
        logging.error(f"Error getting weight history: {str(e)}")
        return []
    finally:
        session.close()

def get_weekly_food_records(username: str, start_date: date) -> list:
    """
    Get all food records for a week starting from start_date
    Args:
        username: Telegram username of the user
        start_date: Start date of the week
    Returns:
        list: List of GPT responses for the week
    """
    end_date = start_date + timedelta(days=7)
    
    session = SessionLocal()
    try:
        daily_records = session.query(DailyData)\
            .filter(DailyData.username == username)\
            .filter(DailyData.date >= start_date)\
            .filter(DailyData.date < end_date)\
            .order_by(DailyData.date, DailyData.time)\
            .all()
        
        return [record.gpt_response for record in daily_records]
    except Exception as e:
        logging.error(f"Error getting weekly food records: {str(e)}")
        return []
    finally:
        session.close() 