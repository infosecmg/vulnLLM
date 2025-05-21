# main.py for Google Cloud Function (Python 3.9+ recommended)

import functions_framework
import requests # For making HTTP requests
import os # For accessing environment variables
import json

# --- Environment Variables (to be set in Cloud Function deployment) ---
# These should be set when you deploy the Cloud Function.
# Example: API_GATEWAY_URL = "https://your-actual-api-gateway-url.nw.gateway.dev/chat"
# Example: API_GATEWAY_API_KEY = "your-actual-api-key-for-api-gateway"
TARGET_API_GATEWAY_URL = os.environ.get('API_GATEWAY_URL')
TARGET_API_KEY = os.environ.get('API_GATEWAY_API_KEY')

# --- CORS Configuration ---
# You'll need to replace 'https://YOUR_GITHUB_USERNAME.github.io' with your actual GitHub Pages URL
# This is the origin that will be allowed to call this Cloud Function.
ALLOWED_ORIGIN = os.environ.get('ALLOWED_CORS_ORIGIN', 'https://YOUR_GITHUB_USERNAME.github.io')


@functions_framework.http
def chat_proxy(request):
    """
    HTTP Cloud Function to proxy chat requests to a secured API Gateway.
    It adds an API key to the outgoing request.
    """

    # --- Set CORS headers for preflight and actual requests ---
    # This allows requests from your GitHub Pages front-end.
    headers = {
        'Access-Control-Allow-Origin': ALLOWED_ORIGIN,
        'Access-Control-Allow-Methods': 'POST, OPTIONS', # Allow POST for chat, OPTIONS for preflight
        'Access-Control-Allow-Headers': 'Content-Type',
        'Access-Control-Max-Age': '3600', # Cache preflight response for 1 hour
        'Content-Type': 'application/json' # Default response content type
    }

    # Handle CORS preflight requests (OPTIONS method)
    if request.method == 'OPTIONS':
        return ('', 204, headers) # 204 No Content for preflight

    # --- Check for required environment variables ---
    if not TARGET_API_GATEWAY_URL or not TARGET_API_KEY:
        print("Error: API_GATEWAY_URL or API_GATEWAY_API_KEY environment variable not set.")
        return (json.dumps({"error": "Server configuration error. Please contact admin."}), 500, headers)

    # --- Ensure it's a POST request for actual chat ---
    if request.method != 'POST':
        return (json.dumps({"error": "Method not allowed. Only POST is accepted."}), 405, headers)

    # --- Get JSON payload from the incoming request ---
    try:
        incoming_payload = request.get_json(silent=True)
        if incoming_payload is None:
            return (json.dumps({"error": "Invalid JSON payload or missing Content-Type header."}), 400, headers)
    except Exception as e:
        print(f"Error parsing incoming JSON: {e}")
        return (json.dumps({"error": "Could not parse request body as JSON."}), 400, headers)

    # --- Prepare headers for the request to API Gateway ---
    outgoing_headers = {
        'Content-Type': 'application/json',
        'x-api-key': TARGET_API_KEY
    }

    # --- Forward the request to the actual API Gateway ---
    try:
        print(f"Forwarding request to: {TARGET_API_GATEWAY_URL}")
        response_from_gateway = requests.post(
            TARGET_API_GATEWAY_URL,
            json=incoming_payload, # Send the same payload received
            headers=outgoing_headers,
            timeout=290 # Slightly less than Cloud Function timeout (default 300s for HTTP gen2)
        )
        response_from_gateway.raise_for_status() # Raise an exception for HTTP error codes (4xx or 5xx)

        # Return the response from API Gateway back to the client
        # Ensure the Content-Type from the gateway is preserved if it's JSON, otherwise default
        gateway_content_type = response_from_gateway.headers.get('Content-Type', 'application/json')
        headers['Content-Type'] = gateway_content_type # Update response header with gateway's content type
        
        # It's safer to parse and re-serialize if you expect JSON,
        # or return raw bytes if it could be something else.
        # Assuming API Gateway returns JSON:
        try:
            response_json = response_from_gateway.json()
            return (json.dumps(response_json), response_from_gateway.status_code, headers)
        except ValueError: # If response is not JSON
            print("Warning: Response from API Gateway was not valid JSON. Returning raw text.")
            # Ensure headers reflect text/plain if not JSON
            if 'application/json' in headers['Content-Type']:
                 headers['Content-Type'] = 'text/plain'
            return (response_from_gateway.text, response_from_gateway.status_code, headers)


    except requests.exceptions.HTTPError as e:
        print(f"HTTP error calling API Gateway: {e.response.status_code} - {e.response.text}")
        # Try to return the error from the gateway if possible
        error_payload = {"error": f"Error from backend service: Status {e.response.status_code}"}
        try:
            error_payload = e.response.json() # If gateway returns JSON error
        except ValueError:
            error_payload["detail"] = e.response.text # If not JSON

        return (json.dumps(error_payload), e.response.status_code, headers)

    except requests.exceptions.RequestException as e:
        print(f"Error calling API Gateway: {e}")
        return (json.dumps({"error": f"Could not connect to backend service: {e}"}), 503, headers) # 503 Service Unavailable

    except Exception as e:
        print(f"An unexpected error occurred in the proxy function: {e}")
        return (json.dumps({"error": "An internal server error occurred in the proxy."}), 500, headers)

```
# requirements.txt for the Cloud Function

functions-framework==3.*
requests==2.*
