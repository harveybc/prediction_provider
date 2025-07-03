# Integration Tests Documentation

## 1. Overview

Integration tests are designed to verify the interactions between different components or modules of the application. These tests ensure that independently developed units work together as expected. For the prediction provider, this involves testing the plugin system, database interactions, and the end-to-end prediction pipeline.

---

## 2. Plugin System Tests (`test_plugin_loading.py`)

### 2.1. Test Case: Core Plugin Loading (`test_core_plugin_loading`)

*   **Objective**: Verify that the main application can correctly discover and load the core `DefaultCore` plugin.
*   **Description**: This test initializes the `App` class and checks if the `DefaultCore` plugin is successfully loaded and registered in the application's plugin manager.
*   **Given**: The `DefaultCore` plugin exists in the `plugins_core` directory.
*   **When**: The application starts.
*   **Then**: The `DefaultCore` plugin instance must be available in the application context.
*   **Rationale**: Ensures the fundamental plugin loading mechanism is functional, as the core plugin is essential for basic operations.

### 2.2. Test Case: All Plugin Types Loading (`test_all_plugin_types_loading`)

*   **Objective**: Ensure the application can load at least one of each type of plugin (Feeder, Predictor, Pipeline, Endpoints).
*   **Description**: This test checks that the application correctly identifies and loads the default plugins for each category: `DefaultFeeder`, `DefaultPredictor`, `DefaultPipeline`, and `DefaultEndpoints`.
*   **Given**: Default plugins for all types are present in their respective directories.
*   **When**: The application initializes.
*   **Then**: An instance of each default plugin must be registered with the application.
*   **Rationale**: Validates the plugin loader's ability to handle all plugin categories, which is critical for a fully functional system.

---

## 3. Database Interaction Tests (`test_database_interaction.py`)

### 3.1. Test Case: Database Creation and Teardown (`test_database_lifecycle`)

*   **Objective**: Verify that the database and its tables can be created and subsequently torn down cleanly.
*   **Description**: This test runs the `create_database.py` script to set up the database schema and then executes a teardown function to ensure all tables are dropped. It uses an in-memory SQLite database for speed and isolation.
*   **Given**: A defined database schema in the application models.
*   **When**: The database setup and teardown procedures are executed.
*   **Then**: The database tables must be created successfully and then completely removed.
*   **Rationale**: Confirms that the database schema is valid and that tests can run in a clean, isolated environment without interfering with each other.

### 3.2. Test Case: Data Persistence and Retrieval (`test_data_persistence_and_retrieval`)

*   **Objective**: Ensure that time series data can be written to and read from the database.
*   **Description**: This test involves the `DefaultFeeder` plugin fetching data for a stock ticker (e.g., `AAPL`) and storing it in the database. A separate component then reads this data back and verifies its integrity.
*   **Given**: A connection to the test database.
*   **When**: The feeder plugin saves time series data, and a data access component retrieves it.
*   **Then**: The retrieved data must exactly match the data that was originally saved.
*   **Rationale**: Validates the entire database interaction layer, from data serialization to storage and retrieval, which is core to the feeder's function.

---

## 4. Database Schema Validation (`test_database_schema.py`)

### 4.1. Test Case: All Tables Creation (`test_all_tables_created`)

*   **Objective**: Verify that all defined SQLAlchemy models are correctly translated into database tables.
*   **Description**: This test connects to a fresh, in-memory SQLite database, runs the `Base.metadata.create_all` command, and then inspects the database to ensure that all expected tables—`users`, `roles`, `prediction_jobs`, `api_logs`, and `time_series_data`—have been created.
*   **Given**: A set of declarative models defined in `app/database_models.py`.
*   **When**: The database schema is created from the models.
*   **Then**: The list of table names in the database must exactly match the expected list of tables.
*   **Rationale**: This is a foundational integration test that validates the correctness of the ORM setup and ensures that the application's view of the database matches the actual schema.

### 4.2. Test Case: Table Column Validation (`test_table_columns`)

*   **Objective**: Ensure that every table in the database has the correct columns and data types as defined in the models.
*   **Description**: This is a parameterized test that iterates through each table (`User`, `Role`, etc.). For each table, it uses the SQLAlchemy `inspect` function to retrieve the list of columns and compares it against a predefined list of expected columns.
*   **Given**: A database with a schema created from the application's models.
*   **When**: Each table's structure is inspected.
*   **Then**: The set of column names for each table must exactly match the expected set.
*   **Rationale**: This test prevents regressions and unintended changes to the database schema. It guarantees that data persistence and retrieval operations will not fail due to missing or mismatched columns.

---

## 5. Prediction Pipeline Tests (`test_prediction_pipeline.py`)

### 5.1. Test Case: End-to-End Prediction Workflow (`test_end_to_end_prediction`)

*   **Objective**: Verify the complete, end-to-end workflow from receiving an API request to returning a prediction.
*   **Description**: This test simulates a client request to the `/predict` endpoint. It traces the request through the `DefaultEndpoints` plugin, which invokes the `DefaultPipeline`. The pipeline, in turn, uses the `DefaultFeeder` to get data and the `DefaultPredictor` to generate a forecast. The final prediction is returned via the API.
*   **Given**: All default plugins are loaded, and the test database is populated with the necessary data.
*   **When**: A POST request is sent to `/predict` with a valid payload (e.g., `{"ticker": "AAPL"}`).
*   **Then**: The API must return a `200 OK` status with a valid prediction in the response body.
*   **Rationale**: This is the most critical integration test, as it validates that all core components (endpoints, pipeline, feeder, and predictor) are correctly integrated and can collaborate to fulfill the primary use case of the application.

### 5.2. Test Case: Model Loading and Caching in Predictor (`test_model_loading_and_caching`)

*   **Objective**: Ensure that the predictor plugin correctly loads a machine learning model and caches it for subsequent requests.
*   **Description**: This test calls the `/predict` endpoint twice for the same model. It verifies that the model is loaded from disk on the first call and served from an in-memory cache on the second call, by checking log outputs or by mocking the file system access.
*   **Given**: A pre-trained model file is available in the predictor plugin's directory.
*   **When**: The prediction endpoint is called multiple times for the same model.
*   **Then**: The model should be loaded from disk only once, and subsequent calls should be faster.
*   **Rationale**: Validates the performance optimization feature of the predictor, ensuring that resource-intensive model loading does not occur on every request, which is key to achieving low latency.
