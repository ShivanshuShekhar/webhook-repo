from flask import Flask, request, jsonify, render_template
from pymongo import MongoClient
from urllib.parse import quote_plus
import json
from datetime import datetime
import os
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

# MongoDB connection with proper URL encoding
def get_mongo_client():
    """Create MongoDB client with proper URL encoding"""
    try:
        # Option 1: If using MongoDB Atlas with username/password
        username = os.getenv('shivanshushekhar786')
        password = os.getenv('Shivanshu@0109')
        cluster = os.getenv('webhook-db')
        
        if username and password and cluster:
            # URL encode username and password to handle special characters
            encoded_username = quote_plus(username)
            encoded_password = quote_plus(password)
            MONGO_URI = f"mongodb+srv://{encoded_username}:{encoded_password}@{cluster}.ivgd3ul.mongodb.net/"
        else:
            # Option 2: Use direct connection string from environment
            MONGO_URI = os.getenv('MONGO_URI', 'mongodb://localhost:27017/')
        
        print(f"Connecting to MongoDB...")
        client = MongoClient(MONGO_URI)
        
        # Test the connection
        client.admin.command('ping')
        print("MongoDB connection successful!")
        return client
        
    except Exception as e:
        print(f"MongoDB connection error: {e}")
        print("Please check your MongoDB configuration in .env file")
        return None

# Initialize MongoDB client
client = get_mongo_client()
if client:
    db = client.webhook_db
    events_collection = db.events
else:
    print("Warning: MongoDB not connected. App will start but won't store events.")
    db = None
    events_collection = None

@app.route('/')
def index():
    """Main page displaying the webhook events"""
    return render_template('index.html')

@app.route('/webhook', methods=['POST'])
def webhook():
    """Webhook endpoint to receive GitHub events"""
    try:
        if not events_collection:
            return jsonify({'status': 'error', 'message': 'Database not connected'}), 500
            
        payload = request.json
        headers = request.headers
        
        # Extract event type from GitHub headers
        event_type = headers.get('X-GitHub-Event')
        
        print(f"Received webhook event: {event_type}")
        
        if event_type == 'push':
            handle_push_event(payload)
        elif event_type == 'pull_request':
            handle_pull_request_event(payload)
        
        return jsonify({'status': 'success', 'event_type': event_type}), 200
    
    except Exception as e:
        print(f"Error processing webhook: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

def handle_push_event(payload):
    """Handle push events from GitHub"""
    try:
        if not events_collection:
            return
            
        # Extract relevant information from push payload
        author = payload['head_commit']['author']['name']
        branch = payload['ref'].split('/')[-1]  # Extract branch name from refs/heads/branch
        commit_id = payload['head_commit']['id']
        
        event_data = {
            'id': commit_id,
            'request_id': commit_id,
            'author': author,
            'action': 'push',
            'from_branch': None,
            'to_branch': branch,
            'timestamp': datetime.utcnow()
        }
        
        events_collection.insert_one(event_data)
        print(f"Stored push event: {author} -> {branch}")
        
    except Exception as e:
        print(f"Error handling push event: {e}")

def handle_pull_request_event(payload):
    """Handle pull request events from GitHub"""
    try:
        if not events_collection:
            return
            
        action = payload['action']
        
        if action == 'opened':
            # Handle pull request creation
            author = payload['pull_request']['user']['login']
            from_branch = payload['pull_request']['head']['ref']
            to_branch = payload['pull_request']['base']['ref']
            pr_id = str(payload['pull_request']['id'])
            
            event_data = {
                'id': pr_id,
                'request_id': pr_id,
                'author': author,
                'action': 'pull_request',
                'from_branch': from_branch,
                'to_branch': to_branch,
                'timestamp': datetime.utcnow()
            }
            
            events_collection.insert_one(event_data)
            print(f"Stored pull request event: {author} {from_branch} -> {to_branch}")
            
        elif action == 'closed' and payload['pull_request']['merged']:
            # Handle merge event (when PR is closed and merged)
            author = payload['pull_request']['merged_by']['login']
            from_branch = payload['pull_request']['head']['ref']
            to_branch = payload['pull_request']['base']['ref']
            pr_id = str(payload['pull_request']['id'])
            
            event_data = {
                'id': pr_id + '_merge',
                'request_id': pr_id,
                'author': author,
                'action': 'merge',
                'from_branch': from_branch,
                'to_branch': to_branch,
                'timestamp': datetime.utcnow()
            }
            
            events_collection.insert_one(event_data)
            print(f"Stored merge event: {author} {from_branch} -> {to_branch}")
            
    except Exception as e:
        print(f"Error handling pull request event: {e}")

@app.route('/api/events')
def get_events():
    """API endpoint to fetch latest events for the UI"""
    try:
        if not events_collection:
            return jsonify([])
            
        # Get latest 20 events sorted by timestamp
        events = list(events_collection.find().sort('timestamp', -1).limit(20))
        
        # Convert ObjectId to string and format timestamp
        for event in events:
            event['_id'] = str(event['_id'])
            event['timestamp'] = event['timestamp'].isoformat()
        
        return jsonify(events)
    
    except Exception as e:
        print(f"Error fetching events: {e}")
        return jsonify([]), 500

@app.route('/health')
def health_check():
    """Health check endpoint"""
    mongo_status = "connected" if client else "disconnected"
    return jsonify({
        'status': 'healthy', 
        'timestamp': datetime.utcnow().isoformat(),
        'mongodb': mongo_status
    })

@app.route('/test-db')
def test_db():
    """Test database connection endpoint"""
    try:
        if not client:
            return jsonify({'status': 'error', 'message': 'MongoDB client not initialized'})
        
        # Test connection
        client.admin.command('ping')
        
        # Test insertion
        if events_collection:
            test_event = {
                'id': 'test_' + str(datetime.now().timestamp()),
                'request_id': 'test_request',
                'author': 'Test User',
                'action': 'test',
                'from_branch': 'test_branch',
                'to_branch': 'main',
                'timestamp': datetime.utcnow()
            }
            events_collection.insert_one(test_event)
            return jsonify({'status': 'success', 'message': 'Database connection and insertion test passed'})
        else:
            return jsonify({'status': 'error', 'message': 'Events collection not initialized'})
            
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)