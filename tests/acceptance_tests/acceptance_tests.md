# Acceptance Tests: Prediction Provider

This document provides a detailed definition of the acceptance tests for the Prediction Provider system. These tests are designed to validate the end-to-end functionality from the perspective of the primary client, the Live Trading System (LTS).

**Current Test Coverage:**
- ✅ Core API Workflow (`test_acceptance.py`) - 11 tests
- ✅ LTS Workflow Simulation (`test_lts_workflow.py`) - 2 tests

**Total Acceptance Tests: 13 (100% pass rate)**

## Methodology

These tests are implemented using a black-box approach. The system is treated as a whole, and tests interact with it exclusively through its public API endpoints. The primary tools used are `pytest` for the test framework and `fastapi.testclient.TestClient` for simulating HTTP requests.

Each test case is mapped directly to a user story to ensure that the system meets the specific business requirements.

---

### Test Suite 1: Core API Workflow

*   **File**: `tests/acceptance_tests/test_acceptance.py`
*   **Objective**: To verify the fundamental, synchronous behavior of the API endpoints.

#### Test Case 1.1: Asynchronous Prediction Workflow

*   **User Story**: "As a user, I want to submit a prediction request, monitor its progress, and retrieve the final result once it is complete."
*   **Implementation**: `test_asynchronous_prediction_workflow()`
*   **Test Steps**:
    1.  **Arrange**: Define a valid prediction request payload (e.g., for "NVDA").
    2.  **Act**: Send a `POST` request to `/api/v1/predictions/`.
    3.  **Assert**: Verify the response status code is `201 Created` and the initial job status is `pending`.
    4.  **Act**: Poll the `/api/v1/predictions/{id}` endpoint in a loop with a defined timeout.
    5.  **Assert**: Inside the loop, check that the job status eventually transitions to `completed`. The test fails if the status becomes `failed` or if the timeout is exceeded.
    6.  **Assert**: Once completed, verify the final response payload contains the `result` key with `prediction` and `uncertainty` data.

---

### Test Suite 2: Live Trading System (LTS) Client Simulation

*   **File**: `tests/acceptance_tests/test_lts_workflow.py` (Note: This will be a new file to keep concerns separate)
*   **Objective**: To validate the specific, complex interaction pattern of the LTS client.

#### Test Case 2.1: Full Concurrent Prediction Workflow

*   **User Story**: "As the LTS, I need to get both short-term and long-term predictions for a specific datetime to make trading decisions. I will make two consecutive requests and poll for their results asynchronously and concurrently."
*   **Implementation**: `test_lts_full_workflow()`
*   **Test Steps**:
    1.  **Arrange**: Define two separate prediction request payloads: one for `short_term` and one for `long_term`.
    2.  **Act (Health Check)**: Send a `GET` request to `/health`. Assert a `200 OK` response.
    3.  **Act (Concurrent Requests)**: Send the two `POST` requests to `/api/v1/predictions/` in quick succession.
    4.  **Assert**: Verify both responses are `201 Created` and store their respective prediction IDs.
    5.  **Act (Concurrent Polling)**: Use a `ThreadPoolExecutor` to run two polling functions simultaneously, one for each prediction ID.
    6.  **Assert**: Each polling function must successfully see its respective job status transition to `completed`.
    7.  **Assert**: Verify the final results for both predictions. Each should contain 6 prediction points and have the correct structure.

#### Test Case 2.2: Partial Failure Resilience

*   **User Story**: "As the LTS, if one of my prediction requests fails, I need to be notified correctly for that request while my other valid request continues to process normally."
*   **Implementation**: `test_lts_partial_failure()`
*   **Test Steps**:
    1.  **Arrange**: Define one valid payload (`short_term`) and one invalid payload (e.g., `prediction_type: "invalid_type"`).
    2.  **Act**: Send a `POST` request with the valid payload. Assert a `201 Created` response.
    3.  **Act**: Send a `POST` request with the invalid payload.
    4.  **Assert**: Verify the response for the invalid request is immediately rejected with a `422 Unprocessable Entity` status code, indicating a validation failure.
    5.  **Act**: Poll for the valid prediction's result.
    6.  **Assert**: The valid prediction must successfully transition to `completed`.
