from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from datetime import datetime, timezone, timedelta
import os.path
import json
import requests
import time
import argparse


# Load configuration from the specified config file
def load_config(config_file="config.json"):
    try:
        with open(config_file, "r") as file:
            return json.load(file)
    except FileNotFoundError:
        print(f"Error: Configuration file '{config_file}' not found.")
        exit(1)
    except json.JSONDecodeError:
        print("Error: Failed to decode the configuration file.")
        exit(1)


# Fetch and process the block start time
def fetch_and_process_block_start(config):
    """
    Fetches the next block production start time from a GraphQL endpoint,
    calculates the time difference, and saves the block start time to a file.
    """
    current_epoch = int(time.time() * 1000)  # Current epoch time in milliseconds
    GRAPHQL_URL = config["GRAPHQL_URL"]
    OUTPUT_FILE = config["OUTPUT_FILE"]

    # GraphQL query
    QUERY = {
        "query": "query{daemonStatus{nextBlockProduction{times{blockStart:startTime}}}}"
    }

    # Send GraphQL query
    try:
        response = requests.post(GRAPHQL_URL, json=QUERY, headers={"Content-Type": "application/json"})
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"Error while making the GraphQL request: {e}")
        return

    # Parse the response
    try:
        result = response.json()
    except json.JSONDecodeError:
        print("Error decoding the JSON response.")
        return

    print(json.dumps(result, indent=2))  # Optional: Debug response

    # Extract blockStart
    try:
        block_start = int(result["data"]["daemonStatus"]["nextBlockProduction"]["times"][0]["blockStart"])
    except (KeyError, IndexError, TypeError):
        print("Error extracting blockStart from the response.")
        return

    # Calculate time difference
    difference_ms = block_start - current_epoch
    seconds = difference_ms // 1000
    minutes = seconds // 60
    hours = minutes // 60
    days = hours // 24
    seconds %= 60
    minutes %= 60
    hours %= 24

    print(f"Current Epoch: {current_epoch}")
    print(f"Block Start: {block_start}")
    print(f"Difference (ms): {difference_ms}")
    print(f"Days: {days}, Hours: {hours}, Minutes: {minutes}, Seconds: {seconds}")

    # Save blockStart to file
    try:
        with open(OUTPUT_FILE, "w") as f:
            f.write(str(block_start))
    except IOError as e:
        print(f"Error writing to file {OUTPUT_FILE}: {e}")


# Main function
def main():
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description="Process GraphQL queries and create Google Calendar events.")
    parser.add_argument(
        "--config",
        type=str,
        default="config.json",
        help="Path to the configuration file (default: config.json)",
    )
    args = parser.parse_args()

    # Load configuration
    config = load_config(args.config)

    fetch_and_process_block_start(config)  # Process block start

    # OAuth2 Authentication
    creds = None
    TOKEN_FILE = config["TOKEN_FILE"]
    CREDENTIALS_FILE = config["CREDENTIALS_FILE"]
    SCOPES = config["SCOPES"]

    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_FILE, "w") as token:
            token.write(creds.to_json())

    # Initialize Google Calendar API
    service = build("calendar", "v3", credentials=creds)

    # Read timestamp from file
    file_path = config["OUTPUT_FILE"]
    timestamp = get_timestamp_from_file(file_path)

    # Get last processed timestamp
    LAST_PROCESSED_FILE = config["LAST_PROCESSED_FILE"]
    last_processed = get_last_processed_timestamp(LAST_PROCESSED_FILE)
    if last_processed == timestamp:
        print("Timestamp has not changed. No event created.")
        return

    # Convert timestamp to ISO 8601
    iso_dates = convert_to_iso8601(timestamp / 1000)

    # Create event details
    event = {
        "summary": "Block Production",
        "location": "Paris, France",
        "description": "Block Production Slot",
        "start": {
            "dateTime": iso_dates["start"],
            "timeZone": "UTC",
        },
        "end": {
            "dateTime": iso_dates["end"],
            "timeZone": "UTC",
        },
        "attendees": [],
        "reminders": {
            "useDefault": False,
            "overrides": [
                {"method": "email", "minutes": 24 * 60},
                {"method": "popup", "minutes": 10},
            ],
        },
    }

    # Add event to Google Calendar
    calendar_id = config["CALENDAR_ID"]
    event_result = service.events().insert(calendarId=calendar_id, body=event).execute()
    print(f"Événement créé : {event_result.get('htmlLink')}")

    # Save last processed timestamp
    save_last_processed_timestamp(timestamp, LAST_PROCESSED_FILE)


def get_timestamp_from_file(file_path):
    """Read the Unix timestamp from the specified file."""
    try:
        with open(file_path, "r") as file:
            return int(file.read().strip())
    except FileNotFoundError:
        print(f"Error: File '{file_path}' not found.")
        exit(1)
    except ValueError:
        print("Error: The file does not contain a valid Unix timestamp.")
        exit(1)


def save_last_processed_timestamp(timestamp, file_path):
    """Save the last processed timestamp to a file."""
    with open(file_path, "w") as file:
        file.write(str(timestamp))


def get_last_processed_timestamp(file_path):
    """Retrieve the last processed timestamp from a file."""
    if os.path.exists(file_path):
        with open(file_path, "r") as file:
            try:
                return int(file.read().strip())
            except ValueError:
                return None
    return None


def convert_to_iso8601(timestamp, duration_hours=1 / 20):
    """Convert Unix timestamp to ISO 8601 format and compute end time."""
    start_datetime = datetime.fromtimestamp(timestamp, tz=timezone.utc)
    end_datetime = start_datetime + timedelta(hours=duration_hours)
    return {
        "start": start_datetime.isoformat(),
        "end": end_datetime.isoformat(),
    }


if __name__ == "__main__":
    main()
