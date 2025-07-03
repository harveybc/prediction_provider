# Test-Driven Development (TDD) Plan: Prediction Provider

This document outlines the comprehensive TDD strategy for developing and validating the Prediction Provider system. The process follows a strict, hierarchical approach, starting from high-level requirements and progressively moving to low-level implementation details. No tests will be executed until all tests at all levels (Acceptance, System, Integration, Unit) have been defined and the corresponding implementation code has been written.

## TDD Philosophy

The core principle is "Test-First, Code-Later." We define the criteria for success before writing the code to meet those criteria. This ensures that the final system is built precisely to specification, is robust, and is maintainable.

**The Order of Operations:**
1.  **Phase 1: Requirements & Documentation (Done)**: Solidify all requirements in the `REFERENCE.md`, `REFERENCE_files.md`, and `REFERNECE_plugins.md` documents. This is the foundation for all tests.
2.  **Phase 2: Test Design (Current Phase)**:
    *   **Acceptance Tests**: Define end-to-end user stories.
    *   **System Tests**: Define tests for major component interactions.
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

**Objective**: To verify that the complete, running system meets the primary business requirements from a user's perspective.

**Implemented Tests: `tests/acceptance_tests/test_acceptance.py`**

These tests cover the basic synchronous functionality of the API endpoints.

*   `test_get_prediction_by_id_not_found`: Verifies that the API returns a `404 Not Found` for non-existent predictions.
*   `test_delete_prediction`: Confirms that a prediction can be successfully created and then deleted.
*   `test_get_all_predictions_empty`: Ensures the API returns an empty list when no predictions exist.
*   `test_create_and_get_all_predictions`: Checks that multiple predictions can be created and then retrieved in a single list.
*   `test_get_plugins`: Validates that the plugin discovery endpoint is operational.

**Pending Test Case: The Asynchronous Prediction Workflow**

This is the primary acceptance test and still needs to be implemented.

*   **User Story**: "As a user, I want to submit a prediction request, monitor its progress, and retrieve the final result once it is complete, with the entire process being tracked in the database."
*   **Test Steps**:
    1.  Send a `POST` request to the `/api/v1/predictions/` endpoint.
    2.  Assert that the HTTP response code is `201 Created` and that the initial status is `pending`.
    3.  Extract the `id` from the response.
    4.  Poll the `/api/v1/predictions/{id}` endpoint until the `status` changes to `completed` or `failed`.
    5.  Assert that the final status is `completed`.
    6.  Assert that the final prediction result contains the expected data fields (e.g., `result`).
    7.  (Optional) Query the database directly to verify that the request and its final result were logged correctly.

### 2. System Tests (Major Component Interaction)

**Objective**: To verify that the main architectural components (`core`, `pipeline`, `database`) work together as a cohesive system, independent of the external API.

**Test Case 1: `test_core_orchestration.py`**
*   **Goal**: Ensure the `default_core` plugin correctly orchestrates the `feeder`, `predictor`, and `pipeline` plugins to produce a prediction.
*   **Test Steps**:
    1.  Instantiate the `default_core` plugin with a test configuration.
    2.  Mock the `data_feeder` to return a pre-defined, correctly formatted DataFrame (45 columns, normalized).
    3.  Mock the `predictor` to return a known, fixed prediction value.
    4.  Invoke the core orchestration logic (simulating what the pipeline would do).
    5.  Assert that the feeder and predictor were called exactly once.
    6.  Assert that the final output matches the mocked predictor's output.

**Test Case 2: `test_database_integrity.py`**
*   **Goal**: Ensure the system can correctly write to and read from the database using the defined SQLAlchemy models.
*   **Test Steps**:
    1.  Initialize an in-memory SQLite database.
    2.  Create a new prediction record and save it to the database.
    3.  Retrieve the record by its ID.
    4.  Assert that the retrieved data matches the initial data.
    5.  Update the record's status (e.g., to `COMPLETED`) and save it.
    6.  Retrieve the record again and assert that the status was updated correctly.

### 3. Integration Tests (Module-to-Module)

**Objective**: To verify that directly connected modules and plugins interact correctly.

**Test Case: `test_prediction_pipeline.py`**
*   **Goal**: Ensure the `default_pipeline` plugin correctly integrates the `default_feeder` and `default_predictor`.
*   **Test Steps**:
    1.  Instantiate the `default_pipeline` plugin.
    2.  Use a real `default_feeder` instance, but configure it to use a small, local dataset instead of hitting a live API (e.g., `yfinance` period of `10d`).
    3.  Use a real `default_predictor` instance with the actual Keras model.
    4.  Execute the pipeline's `run` method.
    5.  Assert that the output is a valid prediction result.
    6.  Assert that the shape and data type of the prediction are correct.

### 4. Unit Tests (Single Component)

**Objective**: To test individual functions, methods, and classes in isolation.

**Test Case 1: `test_feeder_plugin.py`**
*   **Goal**: Verify the `default_feeder`'s internal logic.
*   **Test Steps**:
    1.  **`test_fetch_data`**: Mock the `yfinance.download` call. Provide a sample raw OHLC DataFrame. Assert that the feeder correctly calculates all 44 technical indicators and derived features.
    2.  **`test_normalization`**: Provide a small, known DataFrame. Provide a corresponding normalization JSON file. Assert that the output DataFrame is correctly normalized to the `[0, 1]` range.
    3.  **`test_column_order`**: Assert that the final DataFrame produced by the feeder has the exact 45 columns in the exact order specified in `REFERENCE.md`.

**Test Case 2: `test_predictor_plugin.py`**
*   **Goal**: Verify the `default_predictor`'s internal logic.
*   **Test Steps**:
    1.  **`test_load_model`**: Mock `tensorflow.keras.models.load_model`. Assert that the plugin calls it with the correct model path from the config.
    2.  **`test_predict`**: Provide a correctly shaped and normalized NumPy array `(1, 256, 44)`. Mock the loaded model's `predict` method. Assert that the plugin's `predict` method returns a result with the expected shape and values.

---

## Phase 3 & 4: Implementation and Execution Plan

1.  **Code Review**: Review all existing application code (`app/`, `plugins_*`) and test code (`tests/`) to ensure they align with the designs specified above.
2.  **Run Unit Tests**: Execute `pytest tests/unit_tests/`. Fix any failures until all unit tests pass. These must pass before proceeding.
3.  **Run Integration Tests**: Execute `pytest tests/integration_tests/`. Fix any failures.
4.  **Run System Tests**: Execute `pytest tests/system_tests/`. Fix any failures.
5.  **Run Acceptance Tests**: Execute `pytest tests/acceptance_tests/`. This is the final validation. Debug the known server startup/timeout issues until the test passes reliably.

This structured approach ensures that we build the system from the ground up on a foundation of verified components, leading to a robust and reliable final product.

- [x] Create the new test directory structure: `tests/acceptance_tests/`, `tests/system_tests/`, `tests/integration_tests/`, `tests/unit_tests/`.
- [x] Write acceptance tests based strictly on the requirements and user stories from the documentation, without implementing code to pass them yet.
- [x] Write system tests to verify orchestration and database integrity, again without implementing code to pass them.
- [x] Write integration tests for plugin interactions, mocking dependencies as needed.
- [x] Write unit tests for each module and plugin, ensuring full coverage and compatibility with higher-level tests.
- [ ] Only after all tests are defined, begin implementing code to make the tests pass, starting with unit tests and moving up the hierarchy.
- [ ] Update `test_plan.md` as needed to reflect any changes or clarifications in requirements or test order.
