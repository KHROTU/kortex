import re
import pyautogui
import random
import requests
from datetime import datetime, timedelta
from dateutil.parser import parse as parse_datetime
from asteval import Interpreter as SafeEvaluator
from pint import UnitRegistry
from kortex import database


# --- Fun & Entertainment ---

def tell_joke():
    """
    Tells a random joke.
    Parameters: {}
    """
    try:
        response = requests.get("https://official-joke-api.appspot.com/random_joke", timeout=5)
        response.raise_for_status()
        joke = response.json()
        return f"Here's a joke for you. {joke['setup']} ... {joke['punchline']}"
    except requests.exceptions.RequestException as e:
        return f"Sorry, I couldn't fetch a joke right now. Error: {e}"

def flip_coin():
    """
    Flips a virtual coin.
    Parameters: {}
    """
    result = random.choice(["Heads", "Tails"])
    return f"It's {result}."


# --- Persistence & Memory ---

def create_note(content):
    """
    Creates and saves a persistent note.
    Parameters: {"content": "The text content of the note."}
    """
    try:
        database.add_note(content)
        return "Note saved."
    except Exception as e:
        return f"Sorry, I couldn't save the note. Error: {e}"

def read_notes(limit=1):
    """
    Reads the most recent note(s).
    Parameters: {"limit": "The number of recent notes to read. Defaults to 1."}
    """
    try:
        notes = database.get_notes(limit=int(limit))
        if not notes:
            return "You don't have any notes."
        if len(notes) == 1:
            return f"Your last note says: {notes[0]}"
        response = "Here are your latest notes: " + "; ".join(notes)
        return response
    except Exception as e:
        return f"Sorry, I couldn't read your notes. Error: {e}"


# --- Timers, Alarms & Reminders ---

def _parse_natural_time(time_str):
    """Helper to parse various natural time expressions into datetime objects."""
    now = datetime.now()
    
    in_match = re.search(r'in\s+(\d+)\s+(minute|hour)s?', time_str, re.IGNORECASE)
    if in_match:
        val = int(in_match.group(1))
        unit = in_match.group(2).lower()
        if unit == "minute":
            return now + timedelta(minutes=val)
        elif unit == "hour":
            return now + timedelta(hours=val)

    try:
        due_time = parse_datetime(time_str, default=now)

        # If user specifies a time like "8 PM" without minutes, set minutes and seconds to 0.
        if ":" not in time_str and "minute" not in time_str.lower():
            due_time = due_time.replace(minute=0, second=0, microsecond=0)
        
        if due_time < now: # If time is in the past, assume it's for the next day
             due_time += timedelta(days=1)
        return due_time
    except ValueError:
        return None

def set_reminder(reminder_text, time_str):
    """
    Sets a reminder for a future time.
    Parameters: {"reminder_text": "The text of the reminder.", "time_str": "When to be reminded, e.g., 'in 10 minutes', 'at 8 PM', 'tomorrow morning'."}
    """
    due_at = _parse_natural_time(time_str)
    if not due_at:
        return f"Sorry, I couldn't understand the time '{time_str}'."
    try:
        database.add_reminder(reminder_text, due_at)
        return f"Okay, I'll remind you to '{reminder_text}' at {due_at.strftime('%I:%M %p')}."
    except Exception as e:
        return f"Error setting reminder: {e}"

def set_alarm(time_str):
    """
    Sets an alarm for a future time.
    Parameters: {"time_str": "When to set the alarm, e.g., 'for 7 AM', 'in 1 hour'."}
    """
    due_at = _parse_natural_time(time_str)
    if not due_at:
        return f"Sorry, I couldn't understand the time '{time_str}'."
    try:
        database.add_alarm(due_at)
        return f"Alarm set for {due_at.strftime('%I:%M %p')}."
    except Exception as e:
        return f"Error setting alarm: {e}"

def parse_duration(duration_str):
    """
    Parses a human-readable duration string into seconds.
    Parameters: {"duration_str": "A string like '5 minutes' or '1 hour and 30 seconds'."}
    """
    total_seconds = 0
    matches = re.findall(r'(\d+)\s*(hour|minute|second)s?', duration_str, re.IGNORECASE)
    for value, unit in matches:
        value = int(value)
        if 'hour' in unit: total_seconds += value * 3600
        elif 'minute' in unit: total_seconds += value * 60
        elif 'second' in unit: total_seconds += value
    return total_seconds

def set_timer(duration_str):
    """
    Sets a countdown timer.
    Parameters: {"duration_str": "The duration of the timer, e.g., '10 minutes' or '1 hour 30 seconds'."}
    """
    return f"Timer logic for '{duration_str}' is handled by the main application."

def cancel_timer():
    """
    Cancels the currently active timer.
    Parameters: {}
    """
    return "Timer cancellation is handled by the main application."

def write_text(text_to_write):
    """
    Types out the given text at the current cursor location.
    Parameters: {"text_to_write": "The text to be typed."}
    """
    try:
        pyautogui.write(text_to_write, interval=0.01)
        return "Text written successfully."
    except Exception as e:
        return f"Error writing text: {e}"

def get_current_time():
    """
    Gets the current time.
    Parameters: {}
    """
    now = datetime.now()
    time_str = now.strftime("%I:%M %p").lstrip('0')
    return f"The current time is {time_str}."

def get_current_date():
    """
    Gets the current date, including the day of the week.
    Parameters: {}
    """
    today = datetime.now()
    day = today.day
    if 4 <= day <= 20 or 24 <= day <= 30:
        suffix = "th"
    else:
        suffix = ["st", "nd", "rd"][day % 10 - 1]
    
    date_str = today.strftime(f"%A, %B {day}{suffix}, %Y")
    return f"Today is {date_str}."

def calculate_future_date(days):
    """
    Calculates the date after a specific number of days from today.
    Parameters: {"days": "The number of days to add to the current date."}
    """
    try:
        num_days = int(days)
        future_date = datetime.now() + timedelta(days=num_days)
        date_str = future_date.strftime("%A, %B %d, %Y")
        return f"In {num_days} days, the date will be {date_str}."
    except ValueError:
        return "Please provide a valid number of days."
    except Exception as e:
        return f"An error occurred: {e}"

def calculate_days_between(start_date, end_date):
    """
    Calculates the number of days between two dates.
    Parameters: {"start_date": "The first date in YYYY-MM-DD format.", "end_date": "The second date in YYYY-MM-DD format."}
    """
    try:
        start = parse_datetime(start_date)
        end = parse_datetime(end_date)
        delta = abs((end - start).days)
        return f"There are {delta} days between {start_date} and {end_date}."
    except ValueError:
        return "Sorry, I couldn't understand one of the dates. Please use the YYYY-MM-DD format."
    except Exception as e:
        return f"An error occurred: {e}"

def calculate(expression):
    """
    Calculates the result of a mathematical expression.
    Parameters: {"expression": "The mathematical string to evaluate, e.g., '5 * (2 + 3)'."}
    """
    try:
        evaluator = SafeEvaluator()
        result = evaluator.eval(expression)
        return f"The result is {result}."
    except Exception as e:
        return f"Sorry, I couldn't calculate that. Error: {e}"

def convert_units(amount, from_unit, to_unit):
    """
    Converts a value from one unit to another (e.g., length, mass, volume).
    Parameters: {"amount": "The numerical value to convert.", "from_unit": "The starting unit (e.g., 'miles', 'kg').", "to_unit": "The target unit (e.g., 'km', 'pounds')."}
    """
    try:
        ureg = UnitRegistry()
        quantity = ureg(f"{amount} {from_unit}")
        converted_quantity = quantity.to(to_unit)
        if isinstance(converted_quantity.magnitude, float):
            return f"{amount} {from_unit} is equal to {converted_quantity.magnitude:.2f} {to_unit}."
        else:
            return f"{amount} {from_unit} is equal to {converted_quantity.magnitude} {to_unit}."
    except Exception as e:
        return f"Sorry, I couldn't perform that conversion. Error: {e}"