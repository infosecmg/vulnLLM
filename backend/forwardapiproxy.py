Python
# main.py (Proxy Cloud Function - simplified for streaming)
import functions_framework
import httpx # Using httpx for async streaming
import os
import json

TARGET_API_GATEWAY_URL = os.environ.get('API_GATEWAY_URL')
TARGET_API_KEY = os.environ.get('API_GATEWAY_API_KEY')
ALLOWED_CORS_ORIGIN = os.environ.get('ALLOWED_CORS_ORIGIN')

@functions_framework.http
async def chat_proxy(request): # Make the function async
    headers = {
        'Access-Control-Allow-Origin': ALLOWED_CORS_ORIGIN if ALLOWED_CORS_ORIGIN else '*',
        'Access-Control-Allow-Methods': 'POST, OPTIONS',
        'Access-Control-Allow-Headers': 'Content-Type',
        'Access-Control-Max-Age': '3600',
        'Content-Type': 'text/plain' # Set for streaming plain text
    }
    if request.method == 'OPTIONS':
        return ('', 204, headers)

    if not TARGET_API_GATEWAY_URL or not TARGET_API_KEY:
        return (json.dumps({"error": "Server configuration error."}), 500, headers)
    if request.method != 'POST':
        return (json.dumps({"error": "Method not allowed."}), 405, headers)

    try:
        incoming_payload = request.get_json(silent=True)
        if incoming_payload is None:
            return (json.dumps({"error": "Invalid JSON payload."}), 400, headers)
    except Exception:
        return (json.dumps({"error": "Could not parse request body."}), 400, headers)

    outgoing_headers = {
        'Content-Type': 'application/json',
        'x-api-key': TARGET_API_KEY,
        'Accept': 'text/plain' # Tell the backend we prefer plain text stream
    }

    async def stream_generator():
        try:
            async with httpx.AsyncClient(timeout=300.0) as client:
                async with client.stream(
                    "POST",
                    TARGET_API_GATEWAY_URL,
                    json=incoming_payload,
                    headers=outgoing_headers
                ) as response_from_gateway:
                    # Check initial response status before streaming
                    if response_from_gateway.status_code != 200:
                        error_content = await response_from_gateway.aread()
                        # Yield an error message if the gateway itself fails early
                        yield f"Error from backend service: Status {response_from_gateway.status_code} - {error_content.decode()}"
                        return
                    
                    # Stream the content
                    async for chunk in response_from_gateway.aiter_bytes(): # Get bytes
                        if chunk:
                            yield chunk.decode('utf-8') # Decode to string and yield
        except httpx.HTTPStatusError as e:
            yield f"Backend service error: {e.response.status_code} - {e.response.text}"
        except Exception as e:
            yield f"Proxy streaming error: {str(e)}"

    # For Google Cloud Functions (2nd Gen), returning an async generator
    # with appropriate headers should enable streaming.
    # The functions-framework might require a specific way to return StreamingResponse.
    # This is a common pattern, but consult functions-framework docs if issues arise.
    # The explicit Content-Type in `headers` is important.
    return (stream_generator(), 200, headers)
