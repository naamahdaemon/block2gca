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
    Returns block_start, slot, epoch, and globalSlot.
    """
    current_epoch = int(time.time() * 1000)  # Current epoch time in milliseconds
    GRAPHQL_URL = config["GRAPHQL_URL"]
    OUTPUT_FILE = config["OUTPUT_FILE"]
    CONSENSUS_FILE = config["CONSENSUS_FILE"]

    # GraphQL query
    QUERY = {
        "query": "query{daemonStatus{nextBlockProduction{times{blockStart:startTime slot epoch globalSlot}} blockchainLength consensusTimeNow {slot epoch globalSlot}}}"
    }

    # Send GraphQL query
    try:
        response = requests.post(GRAPHQL_URL, json=QUERY, headers={"Content-Type": "application/json"})
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"Error while making the GraphQL request: {e}")
        return None, None, None, None, None, None, None, None

    # Parse the response
    try:
        result = response.json()
    except json.JSONDecodeError:
        print("Error decoding the JSON response.")
        return None, None, None, None, None, None, None, None

    print(json.dumps(result, indent=2))  # Optional: Debug response

    # Extract blockStart, slot, epoch, globalSlot
    try:
        block_start = int(result["data"]["daemonStatus"]["nextBlockProduction"]["times"][0]["blockStart"])
    except (KeyError, IndexError, TypeError):
        print("Error extracting blockStart from the response.")
        block_start = None

    try:
        slot = int(result["data"]["daemonStatus"]["nextBlockProduction"]["times"][0]["slot"])
    except (KeyError, IndexError, TypeError):
        print("Error extracting slot from the response.")
        slot = None

    try:
        epoch = int(result["data"]["daemonStatus"]["nextBlockProduction"]["times"][0]["epoch"])
    except (KeyError, IndexError, TypeError):
        print("Error extracting epoch from the response.")
        epoch = None

    try:
        globalSlot = int(result["data"]["daemonStatus"]["nextBlockProduction"]["times"][0]["globalSlot"])
        
    except (KeyError, IndexError, TypeError):
        print("Error extracting globalSlot from the response.")
        globalSlot = None
        
    try:
        cslot = int(result["data"]["daemonStatus"]["consensusTimeNow"]["slot"])
    except (KeyError, IndexError, TypeError):
        print("Error extracting consensus slot from the response.")
        cslot = None

    try:
        cepoch = int(result["data"]["daemonStatus"]["consensusTimeNow"]["epoch"])
    except (KeyError, IndexError, TypeError):
        print("Error extracting consensus epoch from the response.")
        cepoch = None

    try:
        cglobalSlot = int(result["data"]["daemonStatus"]["consensusTimeNow"]["globalSlot"])      
    except (KeyError, IndexError, TypeError):
        print("Error extracting consensus globalSlot from the response.")
        cglobalSlot = None
        
    try: 
        blockchainLength = int(result["data"]["daemonStatus"]["blockchainLength"])
        
    except (KeyError, IndexError, TypeError):
        print("Error extracting blockchainLength from the response.")
        blockchainLength = None
        
    # Save blockStart to file
    try:
        with open(OUTPUT_FILE, "w") as f:
            f.write(str(block_start))
    except IOError as e:
        print(f"Error writing to file {OUTPUT_FILE}: {e}")

    # Save consensus to file
    try:
        # Save results to the consensus file for future use
        with open(CONSENSUS_FILE, "w") as consensus:
           consensus_data = response.json()
           consensus.write(json.dumps(consensus_data, indent=2))
           print(f"Consensus data written to {CONSENSUS_FILE}: \n{json.dumps(consensus_data, indent=2)}")
    except IOError as e:
        print(f"Error writing to file {CONSENSUS_FILE}: {e}")

    return block_start, slot, epoch, globalSlot, blockchainLength, cepoch, cslot, cglobalSlot


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
    
    GRAPHQL_URL = config["GRAPHQL_URL"]

    # Fetch block_start, slot, epoch, globalSlot
    block_start, slot, epoch, globalSlot, blockchainLength, cepoch, cslot, cglobalSlot = fetch_and_process_block_start(config)

    if block_start is None or slot is None or epoch is None or globalSlot is None or blockchainLength is None or cslot is None or cepoch is None or cglobalSlot is None:
        print("Error: Failed to fetch required data. Exiting.")
        return

    # OAuth2 Authentication
    creds = None
    TOKEN_FILE = config["TOKEN_FILE"]
    CREDENTIALS_FILE = config["CREDENTIALS_FILE"]
    SCOPES = config["SCOPES"]
    BLOCK_HEIGHT = config["BLOCK_HEIGHT"]
    PUBLIC_ADDRESS = config["PUBLIC_ADDRESS"]
    BLOCK_WINNER_FILE = config["BLOCK_WINNER_FILE"]
    
    # Get Block details if cglobalSlot=globalSlot
    if cglobalSlot == globalSlot or True:
        # GraphQL query
        QUERY2 = {
            "query": "query{block(height: " + str(blockchainLength) + "){creator stateHash protocolState{consensusState{blockHeight epoch slot blockchainLength}}}}"
        }

        # Send GraphQL query
        try:
            response2 = requests.post(GRAPHQL_URL, json=QUERY2, headers={"Content-Type": "application/json"})
            response2.raise_for_status()
        except requests.RequestException as e:
            print(f"Error while making the GraphQL request: {e}")
            return    
            
        try:
            result2 = response2.json()
        except json.JSONDecodeError:
            print("Error decoding the JSON response.")
            return

        print(f"Current Block : \n{json.dumps(result2, indent=2)}")  # Optional: Debug response    

        try:
            block_height = int(blockchainLength)
        except (KeyError, IndexError, TypeError):
            print("Error extracting blockchainLength from the response.")
            block_height = None        

        # Get Latest block height from file
        try:
            # Open the file in read mode
            with open(BLOCK_HEIGHT, "r") as file:
                # Read the content and strip any extra whitespace
                content = file.read().strip()
                # Convert the content to an integer
                latest_block_height = int(content)

            # Print or use the block_height variable
            print(f"Block height is: {latest_block_height}")

        except FileNotFoundError:
            print(f"Error: The file {BLOCK_HEIGHT} does not exist.")
        except ValueError:
            print(f"Error: The file {BLOCK_HEIGHT} does not contain a valid integer.")
        except Exception as e:
            print(f"An unexpected error occurred: {e}")

        # Save current blockHeight to file
        try:
            with open(BLOCK_HEIGHT, "w") as f:
                f.write(str(block_height))
        except IOError as e:
            print(f"Error writing to file {BLOCK_HEIGHT}: {e}")

        try:
            creator = result2["data"]["block"]["creator"]
            print(f"creator : {creator}")
        except (KeyError, IndexError, TypeError):
            print("Error extracting creator from the response.")
            creator = None

        try:
            stateHash = result2["data"]["block"]["stateHash"]
            block_url = "https://minascan.io/mainnet/block/"+stateHash+"/txs"
            print(f"stateHash : {stateHash}")
            print(f"block Url : {block_url}")
        except (KeyError, IndexError, TypeError):
            print("Error extracting stateHash from the response.")
            stateHash = None
            
        # Save block winner to file
        try:
            # Save results to the block winner file for future use
            if latest_block_height != block_height:
                with open(BLOCK_WINNER_FILE, "a") as block_winner:
                   block_winner_data = result2
                   block_winner.write(json.dumps(block_winner_data, indent=2))
                   print(f"Block Winner data written to {BLOCK_WINNER_FILE}: \n{json.dumps(block_winner_data, indent=2)}")
        except IOError as e:
            print(f"Error writing to file {BLOCK_WINNER_FILE}: {e}")

    
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                print("Refreshing expired access token...")
                creds.refresh(Request())
                print("Access token refreshed successfully.")
            except Exception as e:
                print(f"Error refreshing token: {e}")
                print("Attempting re-authentication...")
                flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
                creds = flow.run_local_server(port=0)
        else:
            print("No valid credentials found. Starting authentication flow...")
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)

    # Save the credentials to the token file for future use
    with open(TOKEN_FILE, "w") as token:
       token_data = creds.to_json()
       token.write(token_data)
       print(f"Token data written to {TOKEN_FILE}: {token_data}")

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
    if last_processed is None:
        iso_dates2 = None
    else:        
        iso_dates2 = convert_to_iso8601(last_processed / 1000)

    # Create event details
    event = {
        "summary": f"Epoch {epoch}, Slot {slot}/{globalSlot} Block Production",
        "location": "Paris, France",
        "description": f"Block Production Slot",
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

    calendar_id = config["CALENDAR_ID"]

    # Create event details
    if creator == PUBLIC_ADDRESS: 
        block_status = "You won this block"
    else:
        block_status = "You lost this block"
    if iso_dates2 is not None:   
        event2 = {
            "summary": f"Epoch {cepoch}, Slot {cslot}/{cglobalSlot}/"+str(block_height)+f" {block_status}",
            "location": "Paris, France",
            "description": f"Block Details\n{block_url}",
            "start": {
                "dateTime": iso_dates2["start"],
                "timeZone": "UTC",
            },
            "end": {
                "dateTime": iso_dates2["end"],
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
        event_result2 = service.events().insert(calendarId=calendar_id, body=event2).execute()

    # Add event to Google Calendar
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
