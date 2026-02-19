# Acceptance Criteria — As Built

## AC-1: Health Check
- **Criterion**: `GET /health` returns `{"status": "ok"}` with HTTP 200
- **Status**: ✅ Implemented

## AC-2: Prediction Creation (Public)
- **Criterion**: `POST /api/v1/predict` with `{"symbol": "AAPL", "prediction_type": "short_term"}` creates a prediction with status "pending" and returns HTTP 201
- **Status**: ✅ Implemented
- **Note**: Public when `REQUIRE_AUTH=false` (default); validated when API key provided

## AC-3: Prediction Retrieval
- **Criterion**: `GET /api/v1/predictions/{id}` returns the prediction with status, result, and metadata
- **Status**: ✅ Implemented

## AC-4: Prediction Listing
- **Criterion**: `GET /api/v1/predictions/` returns all predictions (public) or user's predictions (authenticated)
- **Status**: ✅ Implemented

## AC-5: Prediction Deletion
- **Criterion**: `DELETE /api/v1/predictions/{id}` removes the prediction
- **Status**: ✅ Implemented

## AC-6: User Authentication
- **Criterion**: `POST /api/v1/auth/login` with valid credentials returns JWT token; `POST /api/v1/auth/api-key` returns API key
- **Status**: ✅ Implemented

## AC-7: User Creation (Admin)
- **Criterion**: Admin can create users with specified role; new users start inactive
- **Status**: ✅ Implemented

## AC-8: User Activation
- **Criterion**: Admin can activate/deactivate users; inactive users cannot authenticate
- **Status**: ✅ Implemented

## AC-9: Role-Based Access Control
- **Criterion**: Admin-only endpoints reject non-admin users with 403; clients can only access own predictions
- **Status**: ✅ Implemented

## AC-10: Input Validation
- **Criterion**: Invalid prediction_type rejected; XSS payloads sanitized; empty API keys rejected with 403
- **Status**: ✅ Implemented

## AC-11: Rate Limiting
- **Criterion**: Login endpoint limited to 3 attempts per 60 seconds per IP
- **Status**: ✅ Implemented (disabled via `SKIP_RATE_LIMITING` in tests)

## AC-12: Concurrent Prediction Limits
- **Criterion**: Authenticated users limited to 10 concurrent predictions; returns 429 when exceeded
- **Status**: ✅ Implemented

## AC-13: Audit Logging
- **Criterion**: All API requests logged to `api_logs` table; logs cannot be deleted or modified (405)
- **Status**: ✅ Implemented

## AC-14: Background Prediction Processing
- **Criterion**: Prediction moves from "pending" → "processing" → "completed" via background task
- **Status**: ✅ Implemented

## AC-15: Plugin System
- **Criterion**: Plugins loaded via entry points; `GET /api/v1/plugins/` lists available plugins
- **Status**: ✅ Implemented

## AC-16: Provider Pricing
- **Criterion**: Providers can set per-model pricing; admin can view all pricing
- **Status**: ✅ Implemented

## AC-17: Billing Records
- **Criterion**: Client spend and provider earnings trackable via API
- **Status**: ✅ Implemented (billing records must be created manually; not auto-generated on prediction completion)

## AC-18: Client Marketplace Workflow
- **Criterion**: Client submits prediction request → gets cost estimate → prediction processed → results available
- **Status**: ✅ Partially (cost estimation works; actual processing goes through evaluator claim/submit flow which is endpoint-complete but not integrated with billing)

## AC-19: Evaluator Workflow
- **Criterion**: Evaluator browses pending → claims → submits results → gets payment
- **Status**: ✅ Implemented (endpoints complete; payment is calculated but not recorded in billing_records)

## AC-20: Password Management
- **Criterion**: Users can change passwords; old password verified before change
- **Status**: ✅ Implemented

## AC-21: Profile Management
- **Criterion**: Users can view/update profile; cannot change own role
- **Status**: ✅ Implemented

## AC-22: Legacy Endpoints
- **Criterion**: `POST /predict` and `GET /status/{id}` work for backward compatibility
- **Status**: ✅ Implemented

## AC-23: Noisy Ideal Predictor
- **Criterion**: `noisy_ideal_predictor` plugin generates predictions with configurable Gaussian noise from CSV data
- **Status**: ✅ Implemented
