Deploying TinyLlama with FastAPI on Cloud Run (Private) & Connecting via API GatewayThis guide details the steps to deploy your custom TinyLlama FastAPI application as a private service on Google Cloud Run (CPU-based) and then securely expose it to your remote front-end (e.g., hosted on GitHub Pages) using API Gateway and an API Key.Overall Architecture:Front-end (GitHub Pages): User interacts with your chat interface. JavaScript makes API calls.API Gateway: Public-facing entry point. Authenticates requests using an API Key. Routes valid requests to your private Cloud Run service.Cloud Run (Private LLM Backend): Runs your FastAPI application with the TinyLlama model. Only callable by authenticated identities (in this case, API Gateway's service account).Phase 1: Prepare Your TinyLlama Backend ApplicationFile Structure:Ensure you have a directory (e.g., tinyllama-backend) with the following files:main.py: Your FastAPI application code using the Hugging Face pipeline for TinyLlama. This should be the version from the immersive main_py_llm_backend_for_cr_frontend (or the latest refactored version), with CORS configured to allow your GitHub Pages origin (e.g., https://YOUR_GITHUB_USERNAME.github.io).Dockerfile: Defines how to build the container image for your FastAPI application (installs Python, dependencies, copies code, and runs Uvicorn).requirements.txt: Lists all Python dependencies (fastapi, uvicorn, torch, transformers, python-dotenv, psutil, sentencepiece, accelerate).Key main.py Configuration (CORS):In your main.py, ensure the CORSMiddleware is configured. Even though API Gateway will be the primary entry, if it passes the Origin header, this CORS setting in your backend is a good secondary measure.# Inside main.py
origins = [
    "https://YOUR_GITHUB_USERNAME.github.io", # Replace with your actual GitHub Pages URL
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-API-Key"], # X-API-Key for the API Key
)
Replace YOUR_GITHUB_USERNAME.github.io with your actual GitHub Pages URL.Phase 2: Deploy TinyLlama Backend as a Private Cloud Run ServiceSetup Google Cloud CLI (gcloud):Install gcloud if you haven't: Install gcloud CLIAuthenticate and configure your project:gcloud auth login
gcloud auth application-default login
export PROJECT_ID=your-gcp-project-id # Replace with your Project ID
gcloud config set project $PROJECT_ID
Enable necessary APIs:gcloud services enable run.googleapis.com \
    cloudbuild.googleapis.com \
    iam.googleapis.com \
    iamcredentials.googleapis.com \
    apigateway.googleapis.com \
    servicecontrol.googleapis.com \
    servicemanagement.googleapis.com
Build Your Docker Image using Cloud Build:Navigate to your tinyllama-backend directory in your terminal.# Make sure you are in the directory containing your Dockerfile, main.py, etc.
gcloud builds submit --tag gcr.io/$PROJECT_ID/tinylama-llm-backend:v1
This builds the image and pushes it to Google Container Registry (GCR).Deploy to Cloud Run as a Private Service:export REGION=us-central1 # Or your preferred region
export CLOUD_RUN_SERVICE_NAME=tinylama-llm-backend-private

gcloud run deploy $CLOUD_RUN_SERVICE_NAME \
    --image=gcr.io/$PROJECT_ID/tinylama-llm-backend:v1 \
    --platform=managed \
    --region=$REGION \
    --cpu=1 \
    --memory=2Gi \
    --port=8080 \
    --no-allow-unauthenticated \
    --min-instances=0 \
    --timeout=300s
--no-allow-unauthenticated: This is critical. It makes your service private.Note the service URL output by this command. You'll need it for the API Gateway config. It will look like https://[SERVICE_NAME]-[PROJECT_HASH]-[REGION_CODE].a.run.app.Phase 3: Set Up API GatewayCreate a Service Account for API Gateway:This service account will be used by API Gateway to securely invoke your private Cloud Run service.export APIGW_INVOKER_SA_NAME=tinylama-apigw-invoker
export APIGW_INVOKER_SA_EMAIL=$APIGW_INVOKER_SA_NAME@$PROJECT_ID.iam.gserviceaccount.com

gcloud iam service-accounts create $APIGW_INVOKER_SA_NAME \
    --display-name="TinyLlama API Gateway Invoker"
Grant "Cloud Run Invoker" Role to the Service Account:Allow the new service account to call your private Cloud Run service.gcloud run services add-iam-policy-binding $CLOUD_RUN_SERVICE_NAME \
    --member="serviceAccount:$APIGW_INVOKER_SA_EMAIL" \
    --role="roles/run.invoker" \
    --region=$REGION
Create an API Gateway OpenAPI Specification:This YAML file defines your API's structure and how it maps to your backend.Create a file named tinylama-openapi-spec.yaml with the following content.Replace YOUR_PRIVATE_CLOUD_RUN_SERVICE_URL with the URL of your deployed private Cloud Run service (from Phase 2, Step 3).Replace YOUR_GCP_PROJECT_ID with your actual project ID.# tinylama-openapi-spec.yaml
swagger: '2.0'
info:
  title: TinyLlama Chat API
  description: API Gateway for TinyLlama Chatbot on Cloud Run
  version: '1.0.0'
schemes:
  - https
produces:
  - application/json
paths:
  /chat: # This is the public path your front-end will call
    post:
      summary: Proxy to TinyLlama chat backend
      operationId: chatProxy
      x-google-backend:
        address: YOUR_PRIVATE_CLOUD_RUN_SERVICE_URL # e.g., https://tinylama-llm-backend-private-xyz.a.run.app
        path_translation: APPEND_PATH_TO_ADDRESS # Appends /chat to the backend address
        jwt_audience: YOUR_PRIVATE_CLOUD_RUN_SERVICE_URL # Should be the same as address for Cloud Run
        # Use the service account created for API Gateway to call the private Cloud Run service
        # This assumes API Gateway will generate an ID token for this service account.
        # For more explicit control, you might need to set `disable_auth: true` here
        # and handle token generation if API Gateway is calling another Google service.
        # However, for Cloud Run to Cloud Run via API Gateway, this is often sufficient
        # if the API Gateway itself is configured with the invoker SA.
        # Let's assume API Gateway handles this by being configured with the SA.
        # If not, we might need `x-google-identity-token: GENERATE_FOR_SERVICE_ACCOUNT`
        # and specify the service account email.
        # For Cloud Run as a backend, the service account associated with the API Gateway
        # (configured later) will be used to generate the token.
      security:
        - api_key: [] # Indicates this path requires an API key
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              properties:
                user_prompt:
                  type: string
                conversation_history:
                  type: array
                  items:
                    type: object
                    properties:
                      role:
                        type: string
                      content:
                        type: string
      responses:
        '200':
          description: A successful response
          schema:
            type: object # Define your expected response structure
        # Add other responses like 400, 403, 500 etc.
securityDefinitions:
  api_key:
    type: apiKey
    name: x-api-key # Standard header name for API keys
    in: header
Important: The x-google-backend.address should be the full HTTPS URL of your private Cloud Run service.The x-google-backend.jwt_audience should also be this same URL for Cloud Run backends.Create an API Config from the OpenAPI Specification:export API_ID=tinylama-chat-api
export API_CONFIG_ID=tinylama-chat-api-config-v1

gcloud api-gateway api-configs create $API_CONFIG_ID \
  --api=$API_ID \
  --openapi-spec=tinylama-openapi-spec.yaml \
  --project=$PROJECT_ID \
  --backend-auth-service-account=$APIGW_INVOKER_SA_EMAIL
--backend-auth-service-account: This tells API Gateway to use the specified service account to authenticate to your backend Cloud Run service.Create the API Gateway:export GATEWAY_ID=tinylama-chat-gateway

gcloud api-gateway gateways create $GATEWAY_ID \
  --api=$API_ID \
  --api-config=$API_CONFIG_ID \
  --location=$REGION \
  --project=$PROJECT_ID
This step can take a few minutes. After it's complete, it will output a Gateway URL (e.g., https://tinylama-chat-gateway-xxxx.nw.gateway.dev). This is the URL your front-end will use.Phase 4: Secure API Gateway with an API KeyEnable API Key Usage on Your API Config (if not implicitly done by securityDefinitions):While the OpenAPI spec defines security, ensure your API is managed by Service Control. Usually, creating an API config for an API managed by API Gateway handles this.Create an API Key:Go to Google Cloud Console -> "APIs & Services" -> "Credentials".Click "+ CREATE CREDENTIALS" -> "API key".Copy the generated API key immediately and store it securely. Let's call it YOUR_GENERATED_API_KEY.Restrict the API Key:Find the API key you just created in the list. Click on its name (or the pencil icon) to edit it.Under "API restrictions":Select "Restrict key".In the "Select APIs" dropdown, find and select your API Gateway API (e.g., "TinyLlama Chat API" or the service name associated with tinylama-chat-api.apigateway.YOUR_PROJECT_ID.cloud.goog).Under "Application restrictions":Select "HTTP referrers (web sites)".Click "+ ADD AN ITEM".Enter your GitHub Pages URL (e.g., https://YOUR_GITHUB_USERNAME.github.io/*). The /* at the end acts as a wildcard for paths within that domain.Click "Save".Phase 5: Connect Your Remote Front-end (GitHub Pages) to API GatewayUpdate Front-end JavaScript (index.html):API URL: Change the backendUrl in your JavaScript to the API Gateway URL (from Phase 3, Step 5), appending the /chat path.// In your index.html script
const gatewayApiUrl = 'https://tinylama-chat-gateway-xxxx.nw.gateway.dev/chat'; // Replace with your actual Gateway URL + /chat
const apiKey = 'YOUR_GENERATED_API_KEY'; // Replace with the API key you created
API Key Header: Modify your fetch call to include the API key in the x-api-key header.// Inside your sendMessageToBackend function (or similar)
// ...
try {
    const response = await fetch(gatewayApiUrl, { // Use gatewayApiUrl
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'x-api-key': apiKey // Add the API key header
        },
        body: JSON.stringify(payload)
    });
// ...
}
Commit and Push Front-end Changes:Save your index.html, commit, and push to GitHub to update your GitHub Pages site.Phase 6: TestingOpen your GitHub Pages site.Try sending messages.Check browser developer console for errors (Network tab, Console tab).Check API Gateway logs and Cloud Run logs in GCP if issues arise.Phase 7: Resource Clean Up (Optional)If you want to remove the resources to avoid costs:Delete API Gateway:gcloud api-gateway gateways delete $GATEWAY_ID --location=$REGION --project=$PROJECT_ID --quiet
Delete API Config:gcloud api-gateway api-configs delete $API_CONFIG_ID --api=$API_ID --project=$PROJECT_ID --quiet
Delete API Definition (Optional, if you don't need the API definition anymore):gcloud api-gateway apis delete $API_ID --project=$PROJECT_ID --quiet
Delete API Key:Go to GCP Console -> APIs & Services -> Credentials. Find your API key and delete it.Delete Cloud Run Service:gcloud run services delete $CLOUD_RUN_SERVICE_NAME --region=$REGION --project=$PROJECT_ID --quiet
Delete Container Image:gcloud container images delete gcr.io/$PROJECT_ID/tinylama-llm-backend:v1 --force-delete-tags --quiet
Delete Service Account:gcloud iam service-accounts delete $APIGW_INVOKER_SA_EMAIL --project=$PROJECT_ID --quiet
This comprehensive set of steps outlines deploying TinyLlama with a custom FastAPI backend as a private Cloud Run service, fronted by a secure API Gateway using an API key, which your GitHub Pages site can then call. This is a much more robust and secure setup for your lab.