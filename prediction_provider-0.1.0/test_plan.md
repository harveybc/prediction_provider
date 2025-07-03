# Test-Driven Development (TDD) Plan: Prediction Provider

This document outlines the comprehensive TDD strategy for developing and validating the Prediction Provider system. The process follows a strict, hierarchical approach, starting from high-level requirements and progressively moving to low-level implementation details. No tests will be executed until all tests at all levels (Acceptance, System, Integration, Unit) have been defined and the corresponding implementation code has been written.

## TDD Philosophy

The core principle is "Test-First, Code-Later." We define the criteria for success before writing the code to meet those criteria. This ensures that the final system is built precisely to specification, is robust, and is maintainable.

**The Order of Operations:**
1.  **Phase 1: Requirements & Documentation (Done)**: Solidify all requirements in the `REFERENCE.md`, `REFERENCE_files.md`, and `REFERNECE_plugins.md` documents. This is the foundation for all tests.
2.  **Phase 2: Test Design (Current Phase)**:
    *   **Acceptance Tests**: Define end-to-end user stories.
    *   **System Tests**: Define tests for major component interactions and non-functional requirements (e.g., security, logging).
    *   **Integration Tests**: Define tests for direct module/plugin collaborations.
    *   **Unit Tests**: Define tests for individual functions and classes.
3.  **Phase 3: Implementation**: Write the application code required to pass all defined tests.
4.  **Phase 4: Test Execution & Refactoring**: Run tests in order from lowest to highest level (Unit → Integration → System → Acceptance), fixing any issues and refactoring as needed.

---

## Phase 1: Requirements & Documentation (Completed)

The requirements are captured in the following documents, which serve as the single source of truth for all development and testing:

*   `REFERENCE.md`: Defines the system architecture, workflow, and the strict 45-column data contract for the model.
*   `REFERENCE_files.md`: Maps the system's functionality to the project's file structure.
*   `REFERNECE_plugins.md`: Details the specific roles, methods, and configurations for each of the five plugin types (`feeder`, `predictor`, `pipeline`, `core`, `endpoints`).

---

## Phase 2: Test Design

### 1. Acceptance Tests (High-Level User Stories)

**Objective**: To verify that the complete, running system meets the primary business requirements from the perspective of a remote client, such as the Live Trading System (LTS).

**Acceptance Test Files:**
*   **`test_acceptance.py`**: Contains the core test for the asynchronous prediction workflow.
*   **`test_lts_workflow.py`**: Contains tests specifically simulating the complex, concurrent workflow of the LTS client.

**Test Case 1: `test_lts_full_workflow`**
*   **User Story**: "As the LTS, I need to get both short-term and long-term predictions for a specific datetime to make trading decisions. I will make two consecutive requests and poll for their results asynchronously."
*   **Test Steps**:
    1.  **Health Check**: Send a `GET` request to a `/health` or `/status` endpoint. Assert a `200 OK` response to ensure the service is available.
    2.  **Request Short-Term Prediction**: Send a `POST` request to `/api/v1/predictions/` with parameters specifying a short-term model (`"prediction_type": "short_term"`, `window_size: 128`).
    3.  Assert a `201 Created` response and store the returned `prediction_id_short`.
    4.  **Request Long-Term Prediction**: Immediately send another `POST` request to `/api/v1/predictions/` for a long-term model (`"prediction_type": "long_term"`, `window_size: 288`).
    5.  Assert a `201 Created` response and store the returned `prediction_id_long`.
    6.  **Asynchronous Polling**:
        *   Start a polling loop for both `prediction_id_short` and `prediction_id_long` by sending `GET` requests to `/api/v1/predictions/{id}`.
        *   Initially, assert that the `status` for both is `pending`.
        *   Continue polling until the `status` for both is `completed`.
    7.  **Verify Results**:
        *   Assert that the final result for the short-term prediction contains 6 prediction points.
        *   Assert that the final result for the long-term prediction contains 6 prediction points.
        *   Assert that both results contain `prediction` and `uncertainty` keys.

**Test Case 2: `test_lts_partial_failure`**
*   **User Story**: "As the LTS, if one of my prediction requests fails, I need to be notified correctly for that request while my other valid request continues to process normally."
*   **Test Steps**:
    1.  **Request Valid Prediction**: Send a valid `POST` request for a short-term prediction. Store the `prediction_id_valid`.
    2.  **Request Invalid Prediction**: Send a `POST` request with invalid parameters (e.g., a non-existent model type). Store the `prediction_id_invalid`.
    3.  **Asynchronous Polling**:
        *   Poll for the valid request and assert its `status` eventually becomes `completed`.
        *   Poll for the invalid request and assert its `status` becomes `failed` and includes a descriptive error message.

### 2. System Tests (Major Component Interaction & Security)

**Objective**: To verify that major components work together and that non-functional requirements like security and logging are met.

**Test Case 1: `test_concurrent_processing`**
*   **Goal**: Ensure the system can process multiple prediction requests concurrently without race conditions or data corruption.
*   **Test Steps**:
    1.  Use threading or `asyncio` to send two prediction requests (short-term and long-term) nearly simultaneously.
    2.  Query the database directly to assert that two separate records were created in the `predictions` table immediately, both with a `pending` status.
    3.  Wait for processing to finish.
    4.  Query the database again to assert that both records are now `completed` and have distinct result data.

**Test Case 2: `test_api_security`**
*   **Goal**: Verify that the API is protected against common vulnerabilities.
*   **Test Steps**:
    1.  **Authentication**: Send a request to a protected endpoint without an API key/token. Assert a `401 Unauthorized` or `403 Forbidden` response.
    2.  **Authorization**: Send a request with a valid API key but for a resource the key is not authorized to access (e.g., a premium model). Assert a `403 Forbidden` response.
    3.  **Rate Limiting**: Send a burst of requests exceeding the configured limit. Assert that subsequent requests receive a `429 Too Many Requests` response.

**Test Case 3: `test_request_and_event_logging`**
*   **Goal**: Ensure that all significant events are logged for accounting and debugging.
*   **Test Steps**:
    1.  Send a valid API request.
    2.  Send an invalid API request.
    3.  Inspect the system's log files or output.
    4.  Assert that both requests were logged with key information (e.g., timestamp, source IP, endpoint, HTTP status, user agent).
    5.  Trigger a prediction process and assert that key stages (`processing`, `completed`, `failed`) are logged against the prediction ID.

### 3. Integration Tests (Module-to-Module)

**Objective**: To verify that directly connected modules and plugins interact correctly according to the new requirements.

**Database Schema and Models**:
To support authentication, authorization, and logging, a comprehensive database schema has been defined in `app/database_models.py`. It includes the following tables:
*   `users`: Stores user profiles, hashed API keys, and role assignments.
*   `roles`: Defines roles (e.g., "admin", "user") and their permissions in a JSON field.
*   `prediction_jobs`: Tracks the status and results of every prediction request, linked to a user.
*   `api_logs`: Provides a detailed audit trail of all API requests, including user, endpoint, and performance metrics.
*   `time_series_data`: Stores the raw time series data used for predictions, preventing redundant fetches.

**Integration Test Files:**
*   **`test_database_schema.py`**: Verifies that the SQLAlchemy models in `app/database_models.py` are correctly defined and that the tables and columns match the specification.
*   **`test_plugin_loading.py`**: Ensures the `PluginLoader` can correctly discover, import, and instantiate all five types of plugins (`feeder`, `predictor`, `pipeline`, `core`, `endpoints`).
*   **`test_database_interaction.py`**: Tests the complete lifecycle of a prediction job in the database, from creation (`pending`) to completion (`completed`/`failed`), including result storage and status updates.
*   **`test_prediction_pipeline.py`**: Validates the end-to-end data flow through the default pipeline, ensuring the `DefaultFeeder` fetches data, the `DefaultPipeline` processes it, and the `DefaultPredictor` generates a result.

### 4. Unit Tests (Individual Components)

**Objective**: To test the smallest parts of the application in complete isolation, using mocks to substitute external dependencies. This ensures that each component's internal logic is correct.

*   **`test_unit_endpoints.py`**: Verifies the FastAPI endpoint logic. Mocks the core system to ensure endpoints correctly handle incoming requests, validate parameters, and format responses without engaging the full prediction workflow.
*   **`test_unit_predictor.py`**: Tests the `DefaultPredictor` plugin. Verifies its internal data validation, preprocessing, and model-calling logic using sample `pd.DataFrame` objects, mocking the ML model itself.
*   **`test_unit_core.py`**: Focuses on the `CoreSystem`'s logic for managing plugins, orchestrating the prediction workflow, and handling configuration, with all external plugins and database interactions mocked.
*   **`test_unit_feeder.py`**: Isolates and tests the `DefaultFeeder` plugin. Mocks the `yfinance` API to validate its data-fetching methods and error handling for various API responses (success, failure, empty data).
*   **`test_unit_database.py`**: Tests the database utility functions (`get_db_session`, `create_all_tables`). Mocks the database engine and session objects to confirm that the utilities perform the correct SQLAlchemy calls without touching a real database.

---

## Phase 3 & 4: Implementation and Execution

With all tests now fully defined and documented, the next step is to implement the application code required to make these tests pass, followed by the execution of the test suite in the prescribed order (Unit → Integration → System → Acceptance).
