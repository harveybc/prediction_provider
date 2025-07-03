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

**Test Case 1: `test_model_selection_pipeline`**
*   **Goal**: Ensure the pipeline correctly selects the model and parameters based on the request.
*   **Test Steps**:
    1.  Instantiate the `default_pipeline` plugin.
    2.  Mock the `default_feeder` and `default_predictor`.
    3.  Call the pipeline's `run` method with `"prediction_type": "long_term"`.
    4.  Assert that the feeder was called with the correct `window_size` (288).
    5.  Assert that the predictor was instructed to load the long-term Keras model.

**Test Case 2: `test_database_prediction_lifecycle`**
*   **Goal**: Verify the database record correctly reflects the state of a prediction job.
*   **Test Steps**:
    1.  Directly invoke the function that creates a new prediction job.
    2.  Assert that a new row exists in the `predictions` table with `status: "pending"`.
    3.  Directly invoke the function that updates the job status.
    4.  Assert the row's `status` is now `"processing"`.
    5.  Directly invoke the function that finalizes the job with a result.
    6.  Assert the row's `status` is `"completed"` and the `result` column is populated.

### 4. Unit Tests (Single Component)

**Objective**: To test individual functions and classes in isolation.

**Test Case 1: `test_api_endpoint_validation`**
*   **Goal**: Verify the `/api/v1/predictions/` endpoint validation logic.
*   **Test Steps**:
    1.  Test the endpoint with a missing `prediction_type`. Assert a `422 Unprocessable Entity` error.
    2.  Test with an invalid `prediction_type` (e.g., "medium_term"). Assert a `422` error.
    3.  Test with a missing `datetime`. Assert a `422` error.

**Test Case 2: `test_model_loader`**
*   **Goal**: Verify the logic that maps a `prediction_type` to a model file path.
*   **Test Steps**:
    1.  Call the model loading utility with `"short_term"`. Assert it returns the correct path for the short-term model.
    2.  Call it with `"long_term"`. Assert it returns the correct path for the long-term model.

**Test Case 3: `test_auth_middleware`**
*   **Goal**: Test the API authentication middleware in isolation.
*   **Test Steps**:
    1.  Simulate a request with a valid token. Assert the request is passed through.
    2.  Simulate a request with an invalid token. Assert an HTTP exception is raised.
    3.  Simulate a request with a missing token. Assert an HTTP exception is raised.

---

## Phase 3 & 4: Implementation and Execution Plan

1.  **Code Review**: Review all existing application code (`app/`, `plugins_*`) and test code (`tests/`) to ensure they align with the designs specified above.
2.  **Run Unit Tests**: Execute `pytest tests/unit_tests/`. Fix any failures until all unit tests pass. These must pass before proceeding.
3.  **Run Integration Tests**: Execute `pytest tests/integration_tests/`. Fix any failures.
4.  **Run System Tests**: Execute `pytest tests/system_tests/`. Fix any failures.
5.  **Run Acceptance Tests**: Execute `pytest tests/acceptance_tests/`. This is the final validation.

This structured approach ensures that we build the system from the ground up on a foundation of verified components, leading to a robust and reliable final product.

- [x] Create the new test directory structure: `tests/acceptance_tests/`, `tests/system_tests/`, `tests/integration_tests/`, `tests/unit_tests/`.
- [x] Write acceptance tests based strictly on the requirements and user stories from the documentation.
- [x] Write system tests to verify orchestration, security, and database integrity.
- [x] Write integration tests for plugin interactions.
- [x] Write unit tests for each module and plugin.
- [ ] Only after all tests are defined, begin implementing code to make the tests pass, starting with unit tests and moving up the hierarchy.
- [x] Update `test_plan.md` as needed to reflect any changes or clarifications in requirements or test order.
