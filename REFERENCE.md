# Prediction Provider - Decentralized AAA Prediction Marketplace Documentation

## 1. System Architecture and Workflow

The Prediction Provider is a comprehensive, enterprise-grade API service designed for **decentralized machine learning prediction processing** with a fully-implemented AAA (Authentication, Authorization, Accounting) marketplace architecture. The system enables secure, auditable, and scalable prediction services for financial time series data through a distributed computing ecosystem.

### 1.1. Core Principles

#### 1.1.1. Decentralized Marketplace Architecture
- **Request-Response Decoupling**: Prediction requests are never processed synchronously. Instead, they enter a queue-based system where independent evaluators can claim and process requests, enabling horizontal scaling and fault tolerance.
- **Economic Incentive Model**: The system supports a marketplace where evaluators are compensated for processing requests, creating economic incentives for distributed computation.
- **Geographic Distribution**: Evaluators can be located globally, providing redundancy and reducing latency through geographic distribution.
- **Competition-Based Quality**: Multiple evaluators can compete for requests, potentially improving prediction quality through market mechanisms.

#### 1.1.2. Enterprise-Grade AAA System
- **Authentication**: Multi-factor authentication support with API keys, JWT tokens, and optional OAuth2 integration
- **Authorization**: Granular role-based access control (RBAC) with hierarchical permissions and resource-level restrictions
- **Accounting**: Comprehensive audit logging, billing integration, and compliance reporting for financial and regulatory requirements

#### 1.1.3. Plugin-Based Extensibility
- **Five Plugin Types**: `core`, `endpoints`, `feeder`, `predictor`, and `pipeline` plugins provide complete modularity
- **Runtime Discovery**: Plugins are discovered and loaded dynamically without system restarts
- **Version Management**: Plugin versioning and dependency management for production stability
- **Custom Extensions**: Third-party plugin development supported through well-defined interfaces

#### 1.1.4. Enterprise Security and Compliance
- **Data Encryption**: End-to-end encryption for sensitive financial data
- **Audit Trail**: Immutable audit logs for regulatory compliance (SOX, GDPR, PCI-DSS)
- **Access Controls**: Fine-grained permissions with principle of least privilege
- **Rate Limiting**: DDoS protection and fair usage policies
- **Data Retention**: Configurable data retention policies with automatic cleanup

### 1.2. User Roles and Permissions

#### 1.2.1. Client Role (Prediction Requesters)
**Primary Function**: Submit prediction requests and retrieve results
**Permissions**:
- Create new prediction requests with specified parameters
- View and manage only their own prediction requests
- Download results for completed predictions
- Access account management features
- View personal usage statistics and billing information

**Restrictions**:
- Cannot access other users' requests or data
- Cannot claim or process prediction requests
- No administrative or system management capabilities
- Limited to configured rate limits and quotas

**Billing Model**:
- Pay-per-prediction pricing
- Usage-based billing with detailed itemization
- Credit system with pre-payment options
- Volume discounts for high-frequency users

#### 1.2.2. Evaluator Role (Prediction Processors)
**Primary Function**: Claim and process pending prediction requests
**Permissions**:
- View available pending prediction requests
- Claim requests for processing (with timeout enforcement)
- Submit prediction results and processing metadata
- View their own processing history and performance metrics
- Access specialized evaluator tools and dashboards

**Restrictions**:
- Cannot create new prediction requests
- Cannot access other evaluators' processing data
- No administrative capabilities
- Cannot modify system configuration

**Economic Model**:
- Earn credits/payment for completed predictions
- Performance-based bonuses for quality and speed
- Reputation system affecting request assignment priority
- Penalty system for failed or abandoned requests

#### 1.2.3. Administrator Role (System Management)
**Primary Function**: Complete system administration and oversight
**Permissions**:
- Full user account management (create, modify, deactivate)
- Access all prediction requests and user data
- View comprehensive system statistics and health metrics
- Access and analyze complete audit logs
- Manage system configuration and plugin settings
- Override user permissions in emergency situations
- Export data for compliance and reporting

**Responsibilities**:
- Monitor system health and performance
- Manage compliance and regulatory requirements
- Handle dispute resolution between clients and evaluators
- Maintain system security and data integrity
- Generate financial and usage reports

#### 1.2.4. Guest Role (Limited Access)
**Primary Function**: System evaluation and demonstration
**Permissions**:
- Access public API documentation
- View system health status
- Submit limited demo prediction requests (if enabled)
- Access general system information

**Restrictions**:
- No persistent data storage
- Limited request quotas
- Cannot access user-specific features
- No billing or payment capabilities

### 1.3. Decentralized Processing Workflow

#### 1.3.1. Client Prediction Request Lifecycle
1. **Authentication & Authorization**
   - Client authenticates using API key or JWT token
   - System validates client role and active status
   - Rate limiting and quota checks applied
   - Account billing status verified

2. **Request Validation & Submission**
   - Request parameters validated against schema
   - Required plugins availability confirmed
   - Resource requirements estimated
   - Cost calculation provided to client
   - Request stored with "pending" status and unique task_id

3. **Queue Management**
   - Request enters priority queue based on:
     - Client tier/subscription level
     - Request urgency/priority setting
     - Historical client behavior
     - Current system load

4. **Status Monitoring**
   - Client polls status via `/api/v1/predictions/{id}`
   - Real-time notifications available via WebSocket
   - Progress updates provided during processing
   - Estimated completion time updated dynamically

5. **Result Delivery & Cleanup**
   - Results delivered via secure download link
   - Client charged according to billing model
   - Request marked as "delivered"
   - Automatic cleanup after retention period

#### 1.3.2. Evaluator Processing Workflow
1. **Discovery & Selection**
   - Evaluator queries available requests via `/api/v1/evaluator/pending`
   - Filtering by prediction type, difficulty, and payment
   - Request priority and urgency indicators displayed
   - Estimated processing time and complexity provided

2. **Claim & Lock Mechanism**
   - Evaluator claims request via `/api/v1/evaluator/claim/{id}`
   - Request locked with configurable timeout (default: 30 minutes)
   - Processing resources reserved
   - Other evaluators blocked from claiming same request

3. **Data Acquisition**
   - Feeder plugin retrieves historical data per request specification
   - Data quality validation performed
   - Missing data handling and gap filling
   - Normalization parameters applied

4. **Model Processing**
   - Predictor plugin loads appropriate model
   - Feature engineering pipeline executed
   - Prediction generation with uncertainty quantification
   - Model performance metrics collected

5. **Result Submission & Validation**
   - Results submitted via `/api/v1/evaluator/submit/{id}`
   - Automatic validation of result format and quality
   - Processing metadata and logs attached
   - Payment/credit issued upon successful completion

6. **Quality Assurance**
   - Optional peer review for high-value requests
   - Automated quality checks and anomaly detection
   - Performance metrics updated in evaluator profile
   - Feedback provided for continuous improvement

#### 1.3.3. Administrative Oversight Workflow
1. **System Monitoring**
   - Real-time dashboards for system health
   - Queue depth and processing velocity tracking
   - Resource utilization and performance metrics
   - Alert system for anomalies and failures

2. **User Management**
   - Account creation, modification, and deactivation
   - Role assignment and permission management
   - Compliance verification and KYC processes
   - Dispute resolution and customer support

3. **Financial Management**
   - Billing cycle management and invoice generation
   - Payment processing and credit management
   - Evaluator compensation and payout processing
   - Financial reporting and audit trail maintenance

4. **Compliance & Audit**
   - Regulatory compliance monitoring
   - Audit log analysis and reporting
   - Data retention policy enforcement
   - Security incident response and investigation

### 1.4. Comprehensive Authorization Matrix

#### 1.4.1. API Endpoint Permissions

| Endpoint | Client | Evaluator | Administrator | Guest |
|----------|--------|-----------|---------------|-------|
| **Authentication & Session Management** |
| `POST /api/v1/auth/login` | ✅ | ✅ | ✅ | ✅ |
| `POST /api/v1/auth/refresh` | ✅ | ✅ | ✅ | ❌ |
| `POST /api/v1/auth/logout` | ✅ | ✅ | ✅ | ❌ |
| `POST /api/v1/auth/reset-password` | ✅ | ✅ | ✅ | ❌ |
| **Client Prediction Management** |
| `POST /api/v1/predict` | ✅ | ❌ | ✅* | ⚠️** |
| `GET /api/v1/predictions/{id}` | ✅*** | ❌ | ✅ | ❌ |
| `GET /api/v1/predictions/` | ✅*** | ❌ | ✅ | ❌ |
| `PUT /api/v1/predictions/{id}` | ✅*** | ❌ | ✅ | ❌ |
| `DELETE /api/v1/predictions/{id}` | ✅*** | ❌ | ✅ | ❌ |
| **Evaluator Workflow** |
| `GET /api/v1/evaluator/pending` | ❌ | ✅ | ✅ | ❌ |
| `POST /api/v1/evaluator/claim/{id}` | ❌ | ✅ | ✅ | ❌ |
| `POST /api/v1/evaluator/submit/{id}` | ❌ | ✅ | ✅ | ❌ |
| `GET /api/v1/evaluator/assigned` | ❌ | ✅*** | ✅ | ❌ |
| `POST /api/v1/evaluator/release/{id}` | ❌ | ✅*** | ✅ | ❌ |
| `GET /api/v1/evaluator/stats` | ❌ | ✅*** | ✅ | ❌ |
| **User Account Management** |
| `GET /api/v1/account/profile` | ✅ | ✅ | ✅ | ❌ |
| `PUT /api/v1/account/profile` | ✅ | ✅ | ✅ | ❌ |
| `GET /api/v1/account/billing` | ✅ | ✅ | ✅ | ❌ |
| `GET /api/v1/account/usage` | ✅ | ✅ | ✅ | ❌ |
| `POST /api/v1/account/api-key/regenerate` | ✅ | ✅ | ✅ | ❌ |
| **Administrative Functions** |
| `POST /api/v1/admin/users` | ❌ | ❌ | ✅ | ❌ |
| `GET /api/v1/admin/users` | ❌ | ❌ | ✅ | ❌ |
| `PUT /api/v1/admin/users/{id}` | ❌ | ❌ | ✅ | ❌ |
| `DELETE /api/v1/admin/users/{id}` | ❌ | ❌ | ✅ | ❌ |
| `GET /api/v1/admin/audit` | ❌ | ❌ | ✅ | ❌ |
| `GET /api/v1/admin/stats` | ❌ | ❌ | ✅ | ❌ |
| `POST /api/v1/admin/config` | ❌ | ❌ | ✅ | ❌ |
| `GET /api/v1/admin/system/health` | ❌ | ❌ | ✅ | ❌ |
| **Billing & Payment** |
| `GET /api/v1/billing/invoices` | ✅ | ✅ | ✅ | ❌ |
| `POST /api/v1/billing/payment` | ✅ | ❌ | ✅ | ❌ |
| `GET /api/v1/billing/credits` | ✅ | ✅ | ✅ | ❌ |
| **System Information** |
| `GET /health` | ✅ | ✅ | ✅ | ✅ |
| `GET /api/v1/system/info` | ✅ | ✅ | ✅ | ✅ |
| `GET /api/v1/system/status` | ✅ | ✅ | ✅ | ✅ |

**Legend:**
- ✅ = Full access granted
- ❌ = Access denied
- ⚠️ = Limited access (demo/trial mode)
- \* = Admin can impersonate other roles for testing
- \*\* = Guest access limited to demo requests only
- \*\*\* = User can only access their own resources

#### 1.4.2. Data Access Permissions

| Data Type | Client | Evaluator | Administrator |
|-----------|--------|-----------|---------------|
| **Own prediction requests** | Full CRUD | Read-only | Full CRUD |
| **Other users' predictions** | None | None | Full CRUD |
| **Processing queue** | None | Read pending | Full access |
| **User profiles** | Own only | Own only | All users |
| **Audit logs** | Own actions | Own actions | All logs |
| **System metrics** | Basic | Processing stats | Complete |
| **Financial data** | Own billing | Own earnings | All financial |
| **Configuration** | None | None | Full access |

#### 1.4.3. Rate Limiting and Quotas

| Resource | Client | Evaluator | Administrator |
|----------|--------|-----------|---------------|
| **API requests per minute** | 60 | 120 | 300 |
| **Concurrent predictions** | 5 | N/A | Unlimited |
| **Pending requests** | 10 | N/A | Unlimited |
| **Data download per day** | 1GB | 5GB | Unlimited |
| **Historical data access** | 30 days | 90 days | Unlimited |

### 1.5. Comprehensive Database Schema

#### 1.5.1. Core User Management Tables

##### Users Table
- `id`: Primary key (UUID)
- `username`: Unique username (VARCHAR 50)
- `email`: User email address (VARCHAR 255, unique)
- `password_hash`: Bcrypt hashed password (VARCHAR 255)
- `role`: Enum('client', 'evaluator', 'administrator', 'guest')
- `api_key`: Unique API key for authentication (VARCHAR 64)
- `api_key_expires_at`: API key expiration timestamp
- `is_active`: Boolean flag for account status
- `is_verified`: Email verification status
- `subscription_tier`: Enum('free', 'basic', 'premium', 'enterprise')
- `billing_address`: JSON blob containing billing information
- `tax_id`: VAT/Tax identification number
- `created_at`: Account creation timestamp
- `updated_at`: Last profile update timestamp
- `last_login`: Last successful login timestamp
- `failed_login_attempts`: Counter for security monitoring
- `account_locked_until`: Temporary account lock timestamp
- `two_factor_enabled`: 2FA activation status
- `two_factor_secret`: TOTP secret key (encrypted)

##### UserSessions Table
- `id`: Primary key (UUID)
- `user_id`: Foreign key to Users table
- `session_token`: JWT token hash
- `ip_address`: Client IP address
- `user_agent`: Client user agent string
- `created_at`: Session creation timestamp
- `expires_at`: Session expiration timestamp
- `last_activity`: Last activity timestamp
- `is_active`: Session validity flag

#### 1.5.2. Prediction Request Management Tables

##### Predictions Table
- `id`: Primary key (UUID)
- `task_id`: External reference UUID for clients
- `user_id`: Foreign key to Users table (requesting client)
- `evaluator_id`: Foreign key to Users table (processing evaluator, nullable)
- `status`: Enum('pending', 'processing', 'completed', 'failed', 'timeout', 'cancelled')
- `priority`: Integer priority level (1-10)
- `symbol`: Financial instrument symbol (VARCHAR 20)
- `prediction_type`: Enum('short_term', 'long_term', 'custom')
- `datetime_requested`: Target prediction timestamp
- `lookback_ticks`: Historical data points required
- `predictor_plugin`: Plugin name for model inference
- `feeder_plugin`: Plugin name for data fetching
- `pipeline_plugin`: Plugin name for processing coordination
- `interval`: Time interval ('1h', '1d', '1w', '1M')
- `prediction_horizon`: Number of future predictions
- `request_params`: JSON blob of additional parameters
- `result`: JSON blob containing prediction results
- `result_hash`: SHA-256 hash of result for integrity
- `result_confidence`: Overall confidence score (0.0-1.0)
- `processing_metadata`: JSON blob with processing details
- `cost_estimate`: Estimated processing cost
- `actual_cost`: Final billing amount
- `claimed_at`: When evaluator claimed the request
- `started_processing_at`: Actual processing start time
- `completed_at`: Processing completion timestamp
- `delivered_at`: Result delivery timestamp
- `created_at`: Request creation timestamp
- `expires_at`: Request expiration timestamp
- `timeout_at`: Processing timeout timestamp

##### PredictionFiles Table
- `id`: Primary key (UUID)
- `prediction_id`: Foreign key to Predictions table
- `file_type`: Enum('input_data', 'result_csv', 'metadata', 'plot', 'log')
- `file_name`: Original file name
- `file_path`: Secure file storage path
- `file_size`: File size in bytes
- `file_hash`: SHA-256 hash for integrity
- `mime_type`: File MIME type
- `encryption_key`: File encryption key (encrypted)
- `created_at`: File creation timestamp
- `expires_at`: File retention expiration

#### 1.5.3. Financial and Billing Tables

##### Transactions Table
- `id`: Primary key (UUID)
- `user_id`: Foreign key to Users table
- `prediction_id`: Foreign key to Predictions table (nullable)
- `transaction_type`: Enum('charge', 'payment', 'refund', 'credit', 'payout')
- `amount`: Transaction amount (Decimal 10,2)
- `currency`: Currency code (VARCHAR 3)
- `description`: Transaction description
- `payment_method`: Payment method used
- `payment_reference`: External payment system reference
- `status`: Enum('pending', 'completed', 'failed', 'cancelled')
- `processing_fee`: Platform processing fee
- `tax_amount`: Tax/VAT amount
- `created_at`: Transaction timestamp
- `completed_at`: Completion timestamp

##### Credits Table
- `id`: Primary key (UUID)
- `user_id`: Foreign key to Users table
- `credit_type`: Enum('purchased', 'earned', 'bonus', 'refund')
- `amount`: Credit amount (Decimal 10,2)
- `currency`: Currency code
- `source_transaction_id`: Source transaction reference
- `expires_at`: Credit expiration timestamp
- `used_amount`: Amount already consumed
- `created_at`: Credit issuance timestamp

##### Invoices Table
- `id`: Primary key (UUID)
- `user_id`: Foreign key to Users table
- `invoice_number`: Unique invoice identifier
- `billing_period_start`: Billing period start date
- `billing_period_end`: Billing period end date
- `subtotal`: Pre-tax amount
- `tax_amount`: Tax/VAT amount
- `total_amount`: Final invoice amount
- `currency`: Currency code
- `status`: Enum('draft', 'sent', 'paid', 'overdue', 'cancelled')
- `payment_due_date`: Payment deadline
- `pdf_path`: Generated PDF file path
- `created_at`: Invoice generation timestamp
- `paid_at`: Payment completion timestamp

#### 1.5.4. Audit and Compliance Tables

##### AuditLog Table
- `id`: Primary key (UUID)
- `user_id`: Foreign key to Users table (nullable for system actions)
- `session_id`: Foreign key to UserSessions table (nullable)
- `action`: Action performed (VARCHAR 100)
- `resource_type`: Type of resource accessed
- `resource_id`: ID of specific resource
- `endpoint`: API endpoint called
- `method`: HTTP method
- `parameters`: JSON blob of request parameters
- `request_body_hash`: SHA-256 hash of request body
- `response_status`: HTTP response status code
- `response_body_hash`: SHA-256 hash of response body
- `ip_address`: Client IP address
- `user_agent`: Client user agent
- `processing_time`: Request processing duration (ms)
- `success`: Boolean success indicator
- `error_message`: Error details if applicable
- `risk_score`: Automated risk assessment score
- `compliance_flags`: JSON array of compliance markers
- `timestamp`: Action timestamp
- `correlation_id`: Request correlation identifier

##### SecurityEvents Table
- `id`: Primary key (UUID)
- `user_id`: Foreign key to Users table (nullable)
- `event_type`: Enum('login_failure', 'suspicious_activity', 'rate_limit', 'unauthorized_access')
- `severity`: Enum('low', 'medium', 'high', 'critical')
- `description`: Event description
- `details`: JSON blob with event details
- `ip_address`: Source IP address
- `user_agent`: User agent string
- `action_taken`: Automated response taken
- `investigated`: Manual investigation flag
- `resolved`: Resolution status
- `created_at`: Event timestamp

##### ComplianceReports Table
- `id`: Primary key (UUID)
- `report_type`: Enum('sox', 'gdpr', 'pci_dss', 'custom')
- `period_start`: Report period start date
- `period_end`: Report period end date
- `generated_by`: Administrator user ID
- `report_data`: JSON blob with report content
- `file_path`: Generated report file path
- `status`: Enum('generating', 'completed', 'failed')
- `created_at`: Report generation timestamp

#### 1.5.5. System Monitoring Tables

##### SystemMetrics Table
- `id`: Primary key (UUID)
- `metric_name`: Metric identifier
- `metric_value`: Numeric value
- `metric_unit`: Unit of measurement
- `tags`: JSON blob with metric tags
- `timestamp`: Measurement timestamp

##### PerformanceMetrics Table
- `id`: Primary key (UUID)
- `user_id`: Foreign key to Users table (for evaluators)
- `prediction_id`: Foreign key to Predictions table
- `processing_time`: Total processing duration
- `data_fetch_time`: Data retrieval duration
- `model_inference_time`: Model execution duration
- `result_quality_score`: Quality assessment score
- `resource_usage`: JSON blob with CPU/memory usage
- `timestamp`: Measurement timestamp
- `action`: Action performed (e.g., 'create_prediction', 'claim_request')
- `endpoint`: API endpoint called
### 1.6. System Architecture Components

#### 1.6.1. Core System Initialization
1. **Bootstrap Phase**:
   - Application starts via `app/main.py` with command-line argument parsing
   - Environment variable validation and security checks
   - Logging system initialization with structured logging
   - Configuration loading from multiple sources (default, file, environment, CLI)

2. **Database Initialization**:
   - SQLAlchemy engine creation with connection pooling
   - Database schema migration and validation
   - Audit table initialization and integrity checks
   - Performance optimization (indexing, query caching)

3. **Plugin Discovery and Loading**:
   - Dynamic plugin discovery from configured directories
   - Plugin dependency resolution and compatibility checking
   - Plugin initialization in dependency order
   - Plugin health checks and validation

4. **Security Initialization**:
   - JWT secret key validation and rotation
   - Encryption key management for sensitive data
   - TLS certificate validation and loading
   - Security middleware registration (CORS, rate limiting, authentication)

5. **Service Registration**:
   - FastAPI application configuration and middleware registration
   - API route registration with OpenAPI documentation
   - WebSocket endpoint configuration for real-time updates
   - Health check and monitoring endpoint activation

#### 1.6.2. Request Processing Pipeline
1. **Request Reception and Validation**:
   - HTTP request parsing and security validation
   - Authentication token verification (JWT/API key)
   - Role-based authorization checking
   - Rate limiting and quota validation
   - Request parameter validation against JSON schema

2. **Business Logic Processing**:
   - Plugin-based processing delegation
   - Database transaction management
   - Audit logging for all operations
   - Error handling and recovery mechanisms

3. **Response Generation**:
   - Result serialization and formatting
   - Security header injection
   - Response compression and optimization
   - Audit trail completion

#### 1.6.3. Background Processing Services
1. **Queue Management Service**:
   - Prediction request queue monitoring
   - Priority-based request ordering
   - Timeout detection and cleanup
   - Load balancing across evaluators

2. **Notification Service**:
   - Real-time status updates via WebSocket
   - Email notifications for important events
   - SMS alerts for critical system issues
   - Push notifications for mobile applications

3. **Cleanup and Maintenance Service**:
   - Expired request cleanup
   - File system maintenance
   - Database optimization and archiving
   - Log rotation and compression

4. **Monitoring and Alerting Service**:
   - System health monitoring
   - Performance metrics collection
   - Anomaly detection and alerting
   - Compliance monitoring and reporting

---

## 2. Comprehensive API Endpoints Specification

### 2.1. Authentication and Session Management

#### POST /api/v1/auth/login
**Description**: Authenticate user and receive JWT token  
**Access**: Public  
**Request Body**:
```json
{
  "username": "string",
  "password": "string",
  "remember_me": false,
  "two_factor_code": "123456"
}
```
**Response**:
```json
{
  "access_token": "jwt_token_string",
  "refresh_token": "refresh_token_string",
  "token_type": "bearer",
  "expires_in": 3600,
  "user_id": "user_uuid",
  "role": "client|evaluator|administrator",
  "session_id": "session_uuid",
  "last_login": "2024-01-15T09:30:00Z"
}
```

#### POST /api/v1/auth/refresh
**Description**: Refresh expired JWT token  
**Access**: Authenticated users  
**Headers**: `Authorization: Bearer <refresh_token>`  
**Response**: New JWT token with extended expiration

#### POST /api/v1/auth/logout
**Description**: Invalidate current session and tokens  
**Access**: Authenticated users  
**Headers**: `Authorization: Bearer <token>`  
**Response**: Session termination confirmation

#### POST /api/v1/auth/reset-password
**Description**: Initiate password reset process  
**Access**: Public  
**Request Body**:
```json
{
  "email": "user@example.com"
}
```

### 2.2. Client Prediction Management

#### POST /api/v1/predict
**Description**: Submit new prediction request with comprehensive validation  
**Access**: Clients only  
**Request Body**:
```json
{
  "symbol": "EURUSD",
  "prediction_type": "short_term|long_term|custom",
  "datetime_requested": "2024-01-15T10:00:00Z",
  "lookback_ticks": 1000,
  "predictor_plugin": "cnn_predictor|transformer_predictor",
  "feeder_plugin": "default_feeder|premium_feeder",
  "pipeline_plugin": "default_pipeline|fast_pipeline",
  "interval": "1h|1d|1w",
  "prediction_horizon": 6,
  "priority": 1,
  "max_cost": 10.00,
  "notification_webhook": "https://client.example.com/webhook",
  "custom_parameters": {
    "confidence_level": 0.95,
    "include_uncertainties": true,
    "include_plots": false
  }
}
```
**Response**:
```json
{
  "id": 123,
  "task_id": "uuid_string",
  "status": "pending",
  "estimated_completion": "2024-01-15T10:05:00Z",
  "estimated_cost": 8.50,
  "queue_position": 3,
  "priority": 1,
  "created_at": "2024-01-15T09:55:00Z"
}
```

#### GET /api/v1/predictions/{id}
**Description**: Get detailed prediction status and results  
**Access**: Clients (own requests only), Administrators (all)  
**Response**:
```json
{
  "id": 123,
  "task_id": "uuid_string",
  "status": "pending|processing|completed|failed|timeout|cancelled",
  "symbol": "EURUSD",
  "prediction_type": "short_term",
  "datetime_requested": "2024-01-15T10:00:00Z",
  "priority": 1,
  "progress": {
    "percentage": 75,
    "current_step": "model_inference",
    "estimated_remaining": 30
  },
  "evaluator_info": {
    "evaluator_id": "evaluator_uuid",
    "username": "evaluator_name",
    "reputation_score": 4.8
  },
  "cost_info": {
    "estimated_cost": 8.50,
    "actual_cost": 8.25,
    "currency": "USD"
  },
  "result": {
    "predictions": [1.0921, 1.0923, 1.0925, 1.0927, 1.0929, 1.0931],
    "uncertainties": [0.001, 0.002, 0.003, 0.004, 0.005, 0.006],
    "confidence_intervals": {
      "lower": [1.0911, 1.0913, 1.0915, 1.0917, 1.0919, 1.0921],
      "upper": [1.0931, 1.0933, 1.0935, 1.0937, 1.0939, 1.0941]
    },
    "model_metadata": {
      "model_version": "1.2.3",
      "processing_time": 45.2,
      "data_quality_score": 0.95,
      "confidence_score": 0.87
    },
    "download_links": {
      "csv_results": "/api/v1/predictions/123/download/results.csv",
      "plot_image": "/api/v1/predictions/123/download/plot.png",
      "metadata": "/api/v1/predictions/123/download/metadata.json"
    }
  },
  "created_at": "2024-01-15T09:55:00Z",
  "claimed_at": "2024-01-15T09:57:00Z",
  "completed_at": "2024-01-15T10:02:00Z",
  "expires_at": "2024-01-22T10:02:00Z"
}
```

#### GET /api/v1/predictions/
**Description**: List user's prediction requests with filtering and pagination  
**Access**: Clients (own requests only), Administrators (all)  
**Query Parameters**: 
- `?status=pending,processing`
- `&symbol=EURUSD`
- `&prediction_type=short_term`
- `&start_date=2024-01-01`
- `&end_date=2024-01-31`
- `&limit=50&offset=0`
- `&sort=created_at&order=desc`
**Response**: 
```json
{
  "predictions": [
    {
      "id": 123,
      "task_id": "uuid_string",
      "status": "completed",
      "symbol": "EURUSD",
      "prediction_type": "short_term",
      "estimated_cost": 8.50,
      "actual_cost": 8.25,
      "created_at": "2024-01-15T09:55:00Z",
      "completed_at": "2024-01-15T10:02:00Z"
    }
  ],
  "total_count": 156,
  "page": 1,
  "pages": 4,
  "has_next": true,
  "has_prev": false
}
```

#### PUT /api/v1/predictions/{id}
**Description**: Update prediction request (limited fields)  
**Access**: Clients (own requests only), Administrators (all)  
**Request Body**:
```json
{
  "priority": 2,
  "max_cost": 15.00,
  "notification_webhook": "https://newclient.example.com/webhook"
}
```

#### DELETE /api/v1/predictions/{id}
**Description**: Cancel pending prediction request  
**Access**: Clients (own requests only), Administrators (all)  
**Response**: Cancellation confirmation and refund information

#### GET /api/v1/predictions/{id}/download/{file_type}
**Description**: Download prediction result files  
**Access**: Clients (own requests only), Administrators (all)  
**Path Parameters**: `file_type` = `results.csv|plot.png|metadata.json|logs.txt`
**Response**: File download stream with appropriate MIME type
### 2.3. Evaluator Workflow Endpoints

#### GET /api/v1/evaluator/pending
**Description**: Get list of pending prediction requests available for processing  
**Access**: Evaluators, Administrators  
**Query Parameters**: 
- `?prediction_type=short_term,long_term`
- `&symbol=EURUSD,GBPUSD`
- `&min_priority=1&max_priority=10`
- `&min_payment=5.00&max_payment=50.00`
- `&predictor_plugin=cnn_predictor`
- `&sort=priority&order=desc`
- `&limit=20`
**Response**:
```json
{
  "pending_requests": [
    {
      "id": 123,
      "task_id": "uuid_string",
      "symbol": "EURUSD",
      "prediction_type": "short_term",
      "datetime_requested": "2024-01-15T10:00:00Z",
      "lookback_ticks": 1000,
      "predictor_plugin": "cnn_predictor",
      "feeder_plugin": "default_feeder",
      "pipeline_plugin": "default_pipeline",
      "interval": "1h",
      "prediction_horizon": 6,
      "priority": 5,
      "estimated_payment": 8.50,
      "estimated_effort": "medium",
      "data_complexity": "standard",
      "client_tier": "premium",
      "created_at": "2024-01-15T09:55:00Z",
      "expires_at": "2024-01-15T12:00:00Z",
      "requirements": {
        "gpu_required": true,
        "memory_gb": 8,
        "processing_timeout": 300
      }
    }
  ],
  "total_pending": 12,
  "estimated_queue_time": "2-5 minutes",
  "payment_range": {
    "min": 3.50,
    "max": 25.00,
    "average": 12.75
  }
}
```

#### POST /api/v1/evaluator/claim/{id}
**Description**: Claim a pending prediction request for processing  
**Access**: Evaluators, Administrators  
**Request Body**:
```json
{
  "estimated_completion": "2024-01-15T10:05:00Z",
  "processing_node_info": {
    "cpu_cores": 8,
    "memory_gb": 16,
    "gpu_available": true,
    "gpu_memory_gb": 8
  }
}
```
**Response**:
```json
{
  "success": true,
  "request_id": 123,
  "task_id": "uuid_string",
  "claimed_at": "2024-01-15T10:00:00Z",
  "timeout_at": "2024-01-15T10:30:00Z",
  "expected_payment": 8.50,
  "processing_details": {
    "symbol": "EURUSD",
    "datetime_requested": "2024-01-15T10:00:00Z",
    "lookback_ticks": 1000,
    "interval": "1h",
    "prediction_horizon": 6,
    "data_source_config": {
      "provider": "alpha_vantage",
      "api_key_required": false,
      "rate_limit": "5 calls/minute"
    },
    "model_config": {
      "model_path": "/models/cnn_eurusd_1h_v1.2.3.h5",
      "normalization_params": "/config/eurusd_1h_norm.json",
      "feature_columns": 45,
      "sequence_length": 144
    },
    "output_requirements": {
      "format": "json",
      "include_uncertainties": true,
      "include_confidence_intervals": true,
      "include_plots": false
    }
  }
}
```

#### POST /api/v1/evaluator/submit/{id}
**Description**: Submit results for a claimed prediction request  
**Access**: Evaluators, Administrators  
**Request Body**:
```json
{
  "predictions": [1.0921, 1.0923, 1.0925, 1.0927, 1.0929, 1.0931],
  "uncertainties": [0.001, 0.002, 0.003, 0.004, 0.005, 0.006],
  "confidence_intervals": {
    "lower": [1.0911, 1.0913, 1.0915, 1.0917, 1.0919, 1.0921],
    "upper": [1.0931, 1.0933, 1.0935, 1.0937, 1.0939, 1.0941]
  },
  "model_metadata": {
    "model_version": "1.2.3",
    "processing_time": 45.2,
    "data_quality_score": 0.95,
    "confidence_score": 0.87,
    "feature_importance": [0.12, 0.08, 0.15, ...],
    "data_points_used": 1000,
    "missing_data_percentage": 0.02
  },
  "processing_log": "Data fetched successfully. Model loaded. Predictions generated.",
  "resource_usage": {
    "cpu_usage_percent": 85.3,
    "memory_usage_gb": 12.4,
    "gpu_usage_percent": 92.1,
    "processing_duration": 42.8
  },
  "quality_metrics": {
    "prediction_variance": 0.00015,
    "model_confidence": 0.87,
    "data_freshness_score": 0.98
  }
}
```
**Response**:
```json
{
  "success": true,
  "request_id": 123,
  "status": "completed",
  "result_hash": "sha256_hash_string",
  "completed_at": "2024-01-15T10:02:00Z",
  "quality_score": 0.92,
  "payment_amount": 8.50,
  "bonus_amount": 0.85,
  "performance_rating": 4.8
}
```

#### GET /api/v1/evaluator/assigned
**Description**: Get list of requests currently assigned to evaluator  
**Access**: Evaluators (own assignments only), Administrators (all)  
**Query Parameters**: `?status=processing&include_expired=false`
**Response**: 
```json
{
  "assigned_requests": [
    {
      "id": 123,
      "task_id": "uuid_string",
      "symbol": "EURUSD",
      "status": "processing",
      "claimed_at": "2024-01-15T10:00:00Z",
      "timeout_at": "2024-01-15T10:30:00Z",
      "progress_percentage": 65,
      "expected_payment": 8.50,
      "time_remaining": 780
    }
  ],
  "total_assigned": 3,
  "total_processing": 2,
  "total_overdue": 0
}
```

#### POST /api/v1/evaluator/release/{id}
**Description**: Release a claimed request back to the queue  
**Access**: Evaluators (own assignments only), Administrators (all)  
**Request Body**:
```json
{
  "reason": "insufficient_resources|technical_issue|other",
  "details": "GPU memory insufficient for model requirements"
}
```

#### GET /api/v1/evaluator/stats
**Description**: Get evaluator performance statistics  
**Access**: Evaluators (own stats only), Administrators (all)  
**Query Parameters**: `?period=7d&include_rankings=true`
**Response**:
```json
{
  "performance_summary": {
    "total_completed": 156,
    "success_rate": 0.98,
    "average_processing_time": 42.5,
    "average_quality_score": 4.7,
    "total_earnings": 1245.50,
    "current_reputation": 4.8
  },
  "recent_activity": {
    "last_7_days": {
      "requests_completed": 23,
      "average_daily_earnings": 45.20,
      "quality_trend": "improving"
    }
  },
  "rankings": {
    "quality_rank": 15,
    "speed_rank": 8,
    "reliability_rank": 12,
    "total_evaluators": 247
  }
}
```
### 2.4. Account Management Endpoints

#### GET /api/v1/account/profile
**Description**: Get current user's profile information  
**Access**: All authenticated users  
**Response**:
```json
{
  "id": "user_uuid",
  "username": "john_doe",
  "email": "john@example.com",
  "role": "client",
  "subscription_tier": "premium",
  "is_active": true,
  "is_verified": true,
  "two_factor_enabled": false,
  "created_at": "2024-01-01T00:00:00Z",
  "last_login": "2024-01-15T09:30:00Z",
  "profile_settings": {
    "timezone": "UTC",
    "notifications_email": true,
    "notifications_webhook": false,
    "default_currency": "USD"
  }
}
```

#### PUT /api/v1/account/profile
**Description**: Update user profile information  
**Access**: All authenticated users  
**Request Body**:
```json
{
  "email": "newemail@example.com",
  "profile_settings": {
    "timezone": "America/New_York",
    "notifications_email": false,
    "default_currency": "EUR"
  }
}
```

#### GET /api/v1/account/billing
**Description**: Get billing information and payment methods  
**Access**: Clients, Evaluators  
**Response**:
```json
{
  "current_balance": 125.50,
  "currency": "USD",
  "subscription": {
    "tier": "premium",
    "monthly_cost": 29.99,
    "next_billing_date": "2024-02-01T00:00:00Z",
    "auto_renewal": true
  },
  "payment_methods": [
    {
      "id": "pm_12345",
      "type": "credit_card",
      "last_four": "4242",
      "expires": "12/25",
      "is_default": true
    }
  ],
  "usage_summary": {
    "current_month": {
      "predictions_requested": 45,
      "total_cost": 234.50,
      "remaining_credits": 125.50
    }
  }
}
```

#### GET /api/v1/account/usage
**Description**: Get detailed usage statistics  
**Access**: All authenticated users  
**Query Parameters**: `?period=30d&include_details=true`
**Response**:
```json
{
  "summary": {
    "period": "30d",
    "total_requests": 156,
    "successful_requests": 152,
    "failed_requests": 4,
    "total_cost": 1245.50,
    "average_cost_per_request": 8.19
  },
  "daily_breakdown": [
    {
      "date": "2024-01-15",
      "requests": 8,
      "cost": 65.20,
      "success_rate": 1.0
    }
  ],
  "by_prediction_type": {
    "short_term": {
      "count": 120,
      "cost": 980.00,
      "average_processing_time": 42.5
    },
    "long_term": {
      "count": 36,
      "cost": 265.50,
      "average_processing_time": 78.2
    }
  }
}
```

#### POST /api/v1/account/api-key/regenerate
**Description**: Generate new API key and invalidate old one  
**Access**: All authenticated users  
**Response**:
```json
{
  "new_api_key": "ak_1234567890abcdef",
  "expires_at": "2024-04-15T00:00:00Z",
  "old_key_invalidated_at": "2024-01-15T10:00:00Z"
}
```

### 2.5. Administrative Endpoints

#### POST /api/v1/admin/users
**Description**: Create new user account  
**Access**: Administrators only  
**Request Body**:
```json
{
  "username": "new_user",
  "email": "user@example.com",
  "password": "secure_password",
  "role": "client|evaluator|administrator",
  "subscription_tier": "basic|premium|enterprise",
  "is_active": true,
  "initial_credits": 100.00,
  "billing_address": {
    "street": "123 Main St",
    "city": "New York",
    "state": "NY",
    "zip": "10001",
    "country": "US"
  }
}
```
**Response**:
```json
{
  "id": "user_uuid",
  "username": "new_user",
  "email": "user@example.com",
  "role": "client",
  "api_key": "ak_generated_key",
  "created_at": "2024-01-15T10:00:00Z"
}
```

#### GET /api/v1/admin/users
**Description**: List all user accounts with filtering  
**Access**: Administrators only  
**Query Parameters**: 
- `?role=client&is_active=true`
- `&subscription_tier=premium`
- `&created_after=2024-01-01`
- `&search=john@example.com`
- `&limit=50&offset=0`
**Response**:
```json
{
  "users": [
    {
      "id": "user_uuid",
      "username": "john_doe",
      "email": "john@example.com",
      "role": "client",
      "subscription_tier": "premium",
      "is_active": true,
      "created_at": "2024-01-01T00:00:00Z",
      "last_login": "2024-01-15T09:30:00Z",
      "total_predictions": 156,
      "total_spent": 1245.50
    }
  ],
  "total_count": 1247,
  "active_users": 1189,
  "new_users_this_month": 45
}
```

#### PUT /api/v1/admin/users/{id}
**Description**: Update user account details  
**Access**: Administrators only  
**Request Body**:
```json
{
  "is_active": false,
  "subscription_tier": "basic",
  "role": "evaluator",
  "notes": "Downgraded due to payment issues"
}
```

#### DELETE /api/v1/admin/users/{id}
**Description**: Deactivate or delete user account  
**Access**: Administrators only  
**Query Parameters**: `?action=deactivate|delete&notify_user=true`

#### GET /api/v1/admin/audit
**Description**: Access comprehensive audit logs  
**Access**: Administrators only  
**Query Parameters**: 
- `?user_id=uuid&action=create_prediction`
- `&start_date=2024-01-01&end_date=2024-01-31`
- `&endpoint=/api/v1/predict&method=POST`
- `&status_code=200,201&risk_score_min=0.7`
- `&limit=100&offset=0`
**Response**:
```json
{
  "audit_logs": [
    {
      "id": "audit_uuid",
      "user_id": "user_uuid",
      "username": "john_doe",
      "action": "create_prediction",
      "endpoint": "/api/v1/predict",
      "method": "POST",
      "status_code": 201,
      "processing_time": 245,
      "ip_address": "192.168.1.100",
      "user_agent": "PredictionClient/1.0",
      "risk_score": 0.1,
      "timestamp": "2024-01-15T10:00:00Z"
    }
  ],
  "total_count": 15678,
  "high_risk_events": 3,
  "failed_requests": 12
}
```

#### GET /api/v1/admin/stats
**Description**: Get comprehensive system statistics  
**Access**: Administrators only  
**Query Parameters**: `?period=7d&include_forecasts=true`
**Response**:
```json
{
  "system_overview": {
    "active_users": 1189,
    "total_users": 1247,
    "pending_requests": 12,
    "processing_requests": 8,
    "completed_today": 245,
    "failed_today": 3,
    "system_health": "healthy",
    "uptime_percentage": 99.97
  },
  "financial_metrics": {
    "revenue_today": 2450.75,
    "revenue_month": 45623.20,
    "pending_payouts": 8934.50,
    "average_request_value": 12.45
  },
  "performance_metrics": {
    "average_processing_time": 120.5,
    "queue_wait_time": 45.2,
    "success_rate": 0.987,
    "customer_satisfaction": 4.7
  },
  "evaluator_performance": [
    {
      "evaluator_id": "eval_uuid",
      "username": "top_evaluator",
      "completed_today": 15,
      "success_rate": 1.0,
      "average_quality": 4.9,
      "earnings_today": 187.50
    }
  ],
  "predictions": {
    "by_type": {
      "short_term": 180,
      "long_term": 65
    },
    "by_status": {
      "pending": 12,
      "processing": 8,
      "completed": 245,
      "failed": 3
    }
  },
  "resource_utilization": {
    "cpu_usage": 67.3,
    "memory_usage": 72.1,
    "storage_usage": 45.8,
    "network_throughput": "125 Mbps"
  }
}
```

#### POST /api/v1/admin/config
**Description**: Update system configuration  
**Access**: Administrators only  
**Request Body**:
```json
{
  "prediction_timeout": 600,
  "max_concurrent_predictions": 20,
  "rate_limits": {
    "client": 60,
    "evaluator": 120
  },
  "default_plugins": {
    "feeder": "premium_feeder",
    "predictor": "ensemble_predictor"
  }
}
```

#### GET /api/v1/admin/system/health
**Description**: Detailed system health and monitoring  
**Access**: Administrators only  
**Response**:
```json
{
  "overall_status": "healthy",
  "components": {
    "database": {
      "status": "healthy",
      "response_time": 12.3,
      "connections": 45,
      "max_connections": 100
    },
    "redis_cache": {
      "status": "healthy",
      "memory_usage": "2.1GB",
      "hit_rate": 0.87
    },
    "plugin_system": {
      "status": "healthy",
      "loaded_plugins": 12,
      "failed_plugins": 0
    }
  },
  "alerts": [],
  "last_backup": "2024-01-15T02:00:00Z",
  "disk_space": {
    "used": "125GB",
    "available": "875GB",
    "usage_percentage": 12.5
  }
}
```

---

## 3. Main Configuration Parameters

The following are the key global configuration parameters, primarily defined in `app/config.py`. Default values are shown below.

| Parameter | Default Value | Description |
| --- | --- | --- |
| **Server & Database** | | |
| `host` | `'127.0.0.1'` | The host address for the FastAPI server. |
| `port` | `8000` | The port for the FastAPI server. |
| `workers` | `1` | Number of worker processes for the server. |
| `database_url` | `'sqlite:///predictions.db'` | The connection string for the SQLAlchemy database. |
| `database_echo` | `False` | Enable SQL query logging for debugging. |
| `database_pool_size` | `10` | Connection pool size for database. |
| **Security & Authentication** | | |
| `secret_key` | `'your-secret-key-here'` | JWT signing key (MUST be changed in production). |
| `algorithm` | `'HS256'` | JWT algorithm for token signing. |
| `access_token_expire_minutes` | `30` | JWT token expiration time in minutes. |
| `api_key_expire_days` | `90` | API key expiration time in days. |
| `require_activation` | `True` | Whether new accounts require admin activation. |
| **Plugins** | | |
| `core_plugin` | `'default_core'` | The default core plugin for FastAPI app management. |
| `endpoints_plugin` | `'default_endpoints'` | The default endpoints plugin. |
| `pipeline_plugin` | `'default_pipeline'` | The default pipeline plugin for request coordination. |
| `feeder_plugin` | `'default_feeder'` | The default data feeder plugin to use. |
| `predictor_plugin`| `'default_predictor'` | The default predictor plugin to use. |
| **Request Processing** | | |
| `prediction_timeout` | `300` | Maximum time (seconds) for prediction processing. |
| `max_concurrent_predictions` | `10` | Maximum concurrent predictions per user. |
| `prediction_history_days` | `30` | Days to retain completed prediction records. |
| `prediction_confidence_level` | `0.95` | Confidence level for uncertainty estimation. |
| **Data Requirements** | | |
| `instrument` | `'MSFT'` | Default financial instrument for testing. |
| `n_batches` | `1` | Number of data batches to retrieve. |
| `batch_size` | `256` | Number of time steps per batch. |
| `window_size` | `256` | Model input window size (must match batch_size). |
| `target_column` | `'Close'` | Target variable column name. |
| `use_normalization_json` | `None` | Path to normalization parameters JSON file. |
| **Model Configuration** | | |
| `model_path` | `None` | Path to trained model file. |
| `model_type` | `'keras'` | Type of model framework. |
| `prediction_horizon` | `6` | Number of future predictions to generate. |
| `mc_samples` | `100` | Monte Carlo samples for uncertainty estimation. |
| `use_gpu` | `True` | Enable GPU acceleration if available. |

### 3.1. Model-Specific Configurations

#### Short-term Prediction Models (1h interval)
- **Recommended Model**: CNN-based architecture
- **Plugin**: `cnn_predictor` 
- **Window Size**: 144 time steps (6 days of hourly data)
- **Prediction Horizon**: 6 hours
- **Features**: 45 normalized technical and price features
- **Lookback Ticks**: 1000 (configurable based on model requirements)

#### Long-term Prediction Models (1d interval)  
- **Recommended Model**: Transformer architecture
- **Plugin**: `transformer_predictor`
- **Window Size**: 256 time steps (256 days of daily data)
- **Prediction Horizon**: 6 days
- **Features**: 45 normalized technical and price features
- **Lookback Ticks**: 1000 (configurable based on model requirements)

---

## 4. Required Feature Set and Data Format

The prediction system requires a precise set of input features that must be generated by the feeder plugin and normalized according to training specifications. All models expect the same feature schema but may use different time intervals.

### 4.1. Data Normalization Requirements
- **Method**: Min-max normalization to [0, 1] range
- **Source**: Normalization parameters stored in JSON configuration file
- **Consistency**: Must use identical min/max values as used during model training
- **Validation**: Feature ranges validated before model inference

### 4.2. Temporal Data Requirements
- **Historical Context**: Minimum 1000 previous time steps (configurable)
- **Data Continuity**: No gaps in time series data
- **Timezone**: All timestamps in UTC
- **Frequency**: Consistent with requested interval (1h or 1d)

### 4.3. Required Feature Schema
The DataFrame fed to the model must contain the following 45 columns:

| # | Column Name | Data Source / Calculation |
|---|---|---|
| 1 | `DATE_TIME` | Primary timestamp (e.g., hourly). |
| 2 | `RSI` | Calculated from `CLOSE` prices. |
| 3 | `MACD` | Calculated from `CLOSE` prices. |
| 4 | `MACD_Histogram` | Calculated from `MACD` and `MACD_Signal`. |
| 5 | `MACD_Signal` | Calculated from `MACD`. |
| 6 | `EMA` | Calculated from `CLOSE` prices. |
| 7 | `Stochastic_%K` | Calculated from `HIGH`, `LOW`, `CLOSE`. |
| 8 | `Stochastic_%D` | Calculated from `Stochastic_%K`. |
| 9 | `ADX` | Calculated from `HIGH`, `LOW`, `CLOSE`. |
| 10 | `DI+` | Component of ADX. |
| 11 | `DI-` | Component of ADX. |
| 12 | `ATR` | Calculated from `HIGH`, `LOW`, `CLOSE`. |
| 13 | `CCI` | Calculated from `HIGH`, `LOW`, `CLOSE`. |
| 14 | `WilliamsR` | Calculated from `HIGH`, `LOW`, `CLOSE`. |
| 15 | `Momentum` | Calculated from `CLOSE` prices. |
| 16 | `ROC` | Calculated from `CLOSE` prices. |
| 17 | `OPEN` | Sourced directly (e.g., EUR/USD hourly). |
| 18 | `HIGH` | Sourced directly (e.g., EUR/USD hourly). |
| 19 | `LOW` | Sourced directly (e.g., EUR/USD hourly). |
| 20 | `CLOSE` | Sourced directly (e.g., EUR/USD hourly). |
| 21 | `BC-BO` | `CLOSE` - `OPEN` of the previous bar. |
| 22 | `BH-BL` | `HIGH` - `LOW` of the previous bar. |
| 23 | `BH-BO` | `HIGH` - `OPEN` of the previous bar. |
| 24 | `BO-BL` | `OPEN` - `LOW` of the previous bar. |
| 25 | `S&P500_Close` | Sourced from external API (daily or hourly). |
| 26 | `vix_close` | Sourced from external API (daily or hourly). |
| 27 | `CLOSE_15m_tick_1` | Close price from 15 minutes ago. |
| 28 | `CLOSE_15m_tick_2` | Close price from 30 minutes ago. |
| 29 | `CLOSE_15m_tick_3` | Close price from 45 minutes ago. |
| 30 | `CLOSE_15m_tick_4` | Close price from 60 minutes ago. |
| 31 | `CLOSE_15m_tick_5` | Close price from 75 minutes ago. |
| 32 | `CLOSE_15m_tick_6` | Close price from 90 minutes ago. |
| 33 | `CLOSE_15m_tick_7` | Close price from 105 minutes ago. |
| 34 | `CLOSE_15m_tick_8` | Close price from 120 minutes ago. |
| 35 | `CLOSE_30m_tick_1` | Close price from 30 minutes ago. |
| 36 | `CLOSE_30m_tick_2` | Close price from 60 minutes ago. |
| 37 | `CLOSE_30m_tick_3` | Close price from 90 minutes ago. |
| 38 | `CLOSE_30m_tick_4` | Close price from 120 minutes ago. |
| 39 | `CLOSE_30m_tick_5` | Close price from 150 minutes ago. |
| 40 | `CLOSE_30m_tick_6` | Close price from 180 minutes ago. |
| 41 | `CLOSE_30m_tick_7` | Close price from 210 minutes ago. |
| 42 | `CLOSE_30m_tick_8` | Close price from 240 minutes ago. |
| 43 | `day_of_month` | Calculated from `DATE_TIME`. |
| 44 | `hour_of_day` | Calculated from `DATE_TIME`. |
| 45 | `day_of_week` | Calculated from `DATE_TIME`. |

---

## 5. AAA System Architecture and Security Framework

### 5.1. Authentication System

#### 5.1.1. Multi-Factor Authentication (MFA)
- **Primary Authentication**: Username/password with bcrypt hashing (cost factor 12)
- **API Key Authentication**: 64-character cryptographically secure keys with expiration
- **JWT Token System**: RS256 signed tokens with 30-minute expiration and refresh capability
- **Two-Factor Authentication**: TOTP-based (Google Authenticator compatible) for enhanced security
- **OAuth2 Integration**: Support for third-party authentication providers (Google, GitHub, Microsoft)

#### 5.1.2. Session Management
- **Session Tracking**: Each login creates a tracked session with unique identifier
- **Concurrent Session Limits**: Configurable per user role (clients: 3, evaluators: 5, admins: 10)
- **Session Invalidation**: Automatic logout on suspicious activity or password changes
- **Device Fingerprinting**: Track device characteristics for anomaly detection
- **IP Whitelisting**: Optional IP restriction for high-security accounts

#### 5.1.3. Password Security
- **Complexity Requirements**: Minimum 12 characters, mixed case, numbers, symbols
- **Password History**: Prevent reuse of last 12 passwords
- **Breach Checking**: Integration with HaveIBeenPwned API for compromised password detection
- **Automatic Expiration**: Password expiration policies (90 days for admins, 180 days for others)
- **Account Lockout**: Progressive delays after failed attempts (5 attempts = 15 minutes)

### 5.2. Authorization System

#### 5.2.1. Role-Based Access Control (RBAC)
- **Hierarchical Roles**: Guest < Client < Evaluator < Administrator with inheritance
- **Resource-Level Permissions**: Fine-grained access control on individual resources
- **Temporal Permissions**: Time-based access restrictions (e.g., business hours only)
- **Conditional Access**: Dynamic permissions based on user behavior and risk assessment
- **Delegation**: Administrators can temporarily delegate permissions to other users

#### 5.2.2. Permission Matrix Implementation
```python
PERMISSIONS = {
    'prediction.create': ['client', 'admin'],
    'prediction.read.own': ['client', 'evaluator', 'admin'],
    'prediction.read.all': ['admin'],
    'prediction.update.own': ['client', 'admin'],
    'prediction.delete.own': ['client', 'admin'],
    'evaluator.view_queue': ['evaluator', 'admin'],
    'evaluator.claim_request': ['evaluator', 'admin'],
    'evaluator.submit_result': ['evaluator', 'admin'],
    'admin.user_management': ['admin'],
    'admin.system_config': ['admin'],
    'admin.audit_access': ['admin']
}
```

#### 5.2.3. Resource Ownership and Scoping
- **Owner-Based Access**: Users can only access their own resources unless explicitly permitted
- **Organizational Scoping**: Support for multi-tenant organizations with shared resources
- **Project-Based Access**: Group predictions into projects with shared access controls
- **API Scoping**: API keys can be scoped to specific endpoints and operations
- **Time-Limited Access**: Temporary permissions with automatic expiration

### 5.3. Accounting and Audit System

#### 5.3.1. Comprehensive Audit Logging
- **Complete Request Logging**: Every API call logged with full request/response details
- **User Action Tracking**: All user interactions logged with context and metadata
- **System Event Logging**: Database changes, configuration updates, security events
- **File Access Logging**: All file uploads, downloads, and modifications tracked
- **Performance Metrics**: Response times, resource usage, and system performance data

#### 5.3.2. Audit Log Structure
```json
{
  "id": "audit_uuid",
  "timestamp": "2024-01-15T10:00:00.123456Z",
  "user_id": "user_uuid",
  "session_id": "session_uuid",
  "correlation_id": "request_uuid",
  "event_type": "api_request",
  "action": "create_prediction",
  "resource_type": "prediction",
  "resource_id": "prediction_uuid",
  "endpoint": "/api/v1/predict",
  "method": "POST",
  "status_code": 201,
  "request_size": 1024,
  "response_size": 512,
  "processing_time": 245.67,
  "ip_address": "192.168.1.100",
  "user_agent": "PredictionClient/1.0",
  "geolocation": {
    "country": "US",
    "region": "CA",
    "city": "San Francisco"
  },
  "request_hash": "sha256_hash",
  "response_hash": "sha256_hash",
  "risk_score": 0.15,
  "compliance_flags": ["pci_dss", "gdpr"],
  "custom_fields": {}
}
```

#### 5.3.3. Compliance and Reporting
- **Regulatory Compliance**: SOX, GDPR, PCI-DSS, HIPAA compliance features
- **Automated Reports**: Daily, weekly, monthly compliance and usage reports
- **Real-Time Monitoring**: Continuous compliance monitoring with alert system
- **Data Retention**: Configurable retention policies with automatic archival and deletion
- **Export Capabilities**: CSV, JSON, and PDF export for audit reports and investigations

#### 5.3.4. Financial Accounting
- **Transaction Tracking**: All financial transactions logged with full audit trail
- **Revenue Recognition**: Automated revenue tracking and reporting
- **Tax Calculation**: Automatic tax calculation based on user location and transaction type
- **Billing Integration**: Integration with external billing systems (Stripe, PayPal)
- **Chargeback Handling**: Automated chargeback detection and dispute management

### 5.4. Security Architecture

#### 5.4.1. Data Encryption
- **Encryption at Rest**: AES-256 encryption for all sensitive data in database
- **Encryption in Transit**: TLS 1.3 for all API communications
- **Key Management**: Hardware Security Module (HSM) or AWS KMS integration
- **Field-Level Encryption**: Sensitive fields encrypted with separate keys
- **Backup Encryption**: All backups encrypted with rotating keys

#### 5.4.2. Network Security
- **API Gateway**: Centralized API management with rate limiting and DDoS protection
- **WAF Integration**: Web Application Firewall with OWASP Top 10 protection
- **IP Filtering**: Whitelist/blacklist capabilities with geographic restrictions
- **Load Balancing**: Distributed load balancing with health checks and failover
- **VPN Access**: Secure VPN access for administrative functions

#### 5.4.3. Application Security
- **Input Validation**: Strict input validation and sanitization for all endpoints
- **SQL Injection Prevention**: Parameterized queries and ORM usage
- **XSS Protection**: Content Security Policy and output encoding
- **CSRF Protection**: Token-based CSRF protection for state-changing operations
- **Dependency Scanning**: Automated vulnerability scanning of third-party dependencies

#### 5.4.4. Infrastructure Security
- **Container Security**: Docker image scanning and runtime protection
- **Secrets Management**: Secure storage and rotation of API keys and passwords
- **Monitoring and Alerting**: 24/7 security monitoring with automated incident response
- **Backup and Recovery**: Encrypted, geographically distributed backups
- **Disaster Recovery**: Comprehensive disaster recovery plan with RTO < 4 hours

### 5.5. Privacy and Data Protection

#### 5.5.1. GDPR Compliance
- **Data Minimization**: Collect only necessary data for service operation
- **Purpose Limitation**: Use data only for stated purposes
- **Right to Access**: Users can download all their personal data
- **Right to Rectification**: Users can correct inaccurate personal data
- **Right to Erasure**: Complete data deletion upon request (with legal exceptions)
- **Data Portability**: Export user data in machine-readable format
- **Consent Management**: Granular consent tracking and management

#### 5.5.2. Data Classification and Handling
- **Data Categories**: Public, Internal, Confidential, and Restricted classifications
- **Handling Procedures**: Specific procedures for each data classification level
- **Data Loss Prevention**: Automated DLP scanning and protection
- **Geographic Restrictions**: Data residency requirements and cross-border transfer controls
- **Third-Party Sharing**: Strict controls on data sharing with third parties

---

## 6. Implementation Requirements and Technical Specifications

### 6.1. Plugin Architecture Implementation

#### 6.1.1. Plugin Interface Specifications
```python
class CorePlugin(ABC):
    @abstractmethod
    def initialize(self, config: Dict) -> bool:
        """Initialize the core plugin with configuration"""
        pass
    
    @abstractmethod
    def create_app(self) -> FastAPI:
        """Create and configure the FastAPI application"""
        pass
    
    @abstractmethod
    def shutdown(self) -> None:
        """Clean shutdown of the plugin"""
        pass

class FeederPlugin(ABC):
    @abstractmethod
    def fetch_data(self, symbol: str, start_time: datetime, 
                   end_time: datetime, interval: str) -> pd.DataFrame:
        """Fetch historical market data"""
        pass
    
    @abstractmethod
    def validate_data(self, data: pd.DataFrame) -> bool:
        """Validate data quality and completeness"""
        pass

class PredictorPlugin(ABC):
    @abstractmethod
    def load_model(self, model_path: str) -> Any:
        """Load the prediction model"""
        pass
    
    @abstractmethod
    def predict(self, features: np.ndarray) -> Dict:
        """Generate predictions with uncertainty quantification"""
        pass
```

#### 6.1.2. Plugin Discovery and Loading
- **Plugin Registry**: Central registry of available plugins with metadata
- **Dependency Resolution**: Automatic resolution of plugin dependencies
- **Version Compatibility**: Semantic versioning with compatibility checking
- **Hot Reloading**: Dynamic plugin reloading without system restart
- **Plugin Isolation**: Separate namespaces and resource allocation per plugin

### 6.2. Database Implementation Requirements

#### 6.2.1. Database Schema Migrations
- **Migration Framework**: Alembic-based migrations with rollback capabilities
- **Schema Versioning**: Version-controlled database schema changes
- **Data Migration**: Automated data transformation during schema updates
- **Backup Before Migration**: Automatic backup before each migration
- **Zero-Downtime Migrations**: Blue-green deployment for critical updates

#### 6.2.2. Performance Optimization
- **Indexing Strategy**: Optimized indexes for frequently queried columns
- **Query Optimization**: Query plan analysis and optimization
- **Connection Pooling**: Efficient database connection management
- **Read Replicas**: Read-only replicas for reporting and analytics
- **Caching Strategy**: Redis-based caching for frequently accessed data

#### 6.2.3. Data Integrity and Consistency
- **ACID Compliance**: Full ACID transaction support
- **Foreign Key Constraints**: Enforced referential integrity
- **Check Constraints**: Data validation at database level
- **Triggers**: Audit logging and data consistency triggers
- **Backup and Recovery**: Point-in-time recovery capabilities

### 6.3. API Implementation Standards

#### 6.3.1. RESTful API Design
- **HTTP Status Codes**: Proper use of HTTP status codes for all responses
- **Resource Naming**: Consistent resource naming conventions
- **Pagination**: Cursor-based pagination for large datasets
- **Filtering and Sorting**: Standardized query parameters for data filtering
- **Content Negotiation**: Support for JSON, XML, and CSV responses

#### 6.3.2. Error Handling and Responses
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Request validation failed",
    "details": [
      {
        "field": "symbol",
        "error": "Invalid currency pair format"
      }
    ],
    "request_id": "req_12345",
    "timestamp": "2024-01-15T10:00:00Z",
    "documentation_url": "https://docs.api.example.com/errors/validation"
  }
}
```

#### 6.3.3. Rate Limiting Implementation
- **Token Bucket Algorithm**: Configurable rate limiting per user and endpoint
- **Burst Handling**: Allow short bursts while maintaining overall limits
- **Rate Limit Headers**: Standard HTTP headers for rate limit status
- **Graceful Degradation**: Queuing system for rate-limited requests
- **Premium Limits**: Higher limits for premium subscription tiers

### 6.4. Testing Requirements

#### 6.4.1. Test Coverage Requirements
- **Unit Tests**: Minimum 90% code coverage for all modules
- **Integration Tests**: End-to-end testing of all API endpoints
- **Load Testing**: Performance testing with realistic load patterns
- **Security Testing**: Automated security scanning and penetration testing
- **Compliance Testing**: Automated compliance validation for regulatory requirements

#### 6.4.2. Test Environment Setup
- **Test Isolation**: Separate test databases and environments
- **Mock Services**: Mock external dependencies for reliable testing
- **Test Data Management**: Automated test data generation and cleanup
- **Continuous Testing**: Automated testing in CI/CD pipeline
- **Performance Baselines**: Automated performance regression detection

### 6.5. Deployment and Operations

#### 6.5.1. Container and Orchestration
- **Docker Containers**: Multi-stage builds with security scanning
- **Kubernetes Deployment**: Scalable orchestration with auto-scaling
- **Service Mesh**: Istio or similar for service-to-service communication
- **Health Checks**: Comprehensive health checking for all services
- **Resource Management**: CPU and memory limits with monitoring

#### 6.5.2. Monitoring and Observability
- **Metrics Collection**: Prometheus metrics for all system components
- **Log Aggregation**: Centralized logging with Elasticsearch and Kibana
- **Distributed Tracing**: OpenTelemetry for request tracing
- **Alert Management**: Intelligent alerting with escalation policies
- **Dashboard Creation**: Real-time dashboards for operations and business metrics

#### 6.5.3. Backup and Disaster Recovery
- **Automated Backups**: Daily encrypted backups with retention policies
- **Cross-Region Replication**: Geographic distribution of data
- **Recovery Testing**: Regular testing of backup and recovery procedures
- **RTO/RPO Targets**: Recovery Time Objective < 4 hours, Recovery Point Objective < 1 hour
- **Failover Procedures**: Automated failover for critical system components

---

## 7. Quality Assurance and Testing Framework

### 7.1. Comprehensive Testing Strategy

#### 7.1.1. Test Level Definitions
- **Unit Tests**: Individual function and class testing with 90%+ coverage
- **Integration Tests**: API endpoint testing with real database interactions
- **System Tests**: End-to-end workflow testing across all components
- **Acceptance Tests**: Business requirement validation and user story testing
- **Security Tests**: Vulnerability scanning, penetration testing, and compliance validation
- **Performance Tests**: Load testing, stress testing, and scalability validation
- **Behavioral Tests**: User behavior simulation and edge case testing

#### 7.1.2. Test Automation Framework
- **Continuous Integration**: Automated testing on every commit
- **Test Parallelization**: Parallel test execution for faster feedback
- **Test Data Management**: Automated test data generation and cleanup
- **Environment Management**: Automated test environment provisioning
- **Reporting and Analytics**: Comprehensive test results and trend analysis

### 7.2. LTS Integration Requirements

#### 7.2.1. Integration Architecture
- **API Compatibility**: RESTful API interface for seamless LTS integration
- **Message Queue**: Asynchronous communication for high-volume prediction requests
- **Webhook Support**: Real-time notifications for prediction completion
- **Bulk Operations**: Batch prediction submission and result retrieval
- **Error Handling**: Robust error handling and retry mechanisms

#### 7.2.2. LTS Workflow Integration
1. **Request Submission**: LTS submits prediction requests via API
2. **Queue Management**: Requests enter priority queue for evaluator processing
3. **Processing Updates**: Real-time status updates via webhooks or polling
4. **Result Delivery**: Automated result delivery upon completion
5. **Billing Integration**: Automatic billing and usage tracking

#### 7.2.3. Performance Requirements
- **Throughput**: Support for 1000+ concurrent prediction requests
- **Latency**: Average response time < 2 seconds for API calls
- **Availability**: 99.9% uptime with automated failover
- **Scalability**: Horizontal scaling to handle increased load
- **Data Consistency**: Strong consistency for financial data and transactions

---

## 8. Conclusion and Next Steps

This comprehensive design documentation establishes the foundation for a robust, scalable, and secure decentralized prediction marketplace. The system implements enterprise-grade AAA (Authentication, Authorization, Accounting) controls while maintaining the flexibility and extensibility required for a growing marketplace.

### 8.1. Implementation Priority
1. **Phase 1**: Core API endpoints and basic AAA system
2. **Phase 2**: Evaluator workflow and queue management
3. **Phase 3**: Billing and payment integration
4. **Phase 4**: Advanced security and compliance features
5. **Phase 5**: LTS integration and production deployment

### 8.2. Success Criteria
- **Functional**: All API endpoints operational with proper AAA controls
- **Performance**: System handles target load with acceptable response times
- **Security**: All security requirements implemented and tested
- **Compliance**: Full regulatory compliance with audit trail
- **Integration**: Seamless LTS integration with end-to-end testing

### 8.3. Ongoing Maintenance
- **Security Updates**: Regular security patches and vulnerability assessments
- **Performance Monitoring**: Continuous monitoring and optimization
- **Compliance Reviews**: Regular compliance audits and updates
- **Feature Updates**: Iterative feature development based on user feedback
- **Documentation**: Continuous documentation updates and improvements

This design provides the blueprint for a production-ready decentralized prediction marketplace that meets enterprise requirements for security, scalability, and regulatory compliance.
