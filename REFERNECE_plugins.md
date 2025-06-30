# REFERENCE_plugins.md
**Prediction Provider - Detailed Plugin Design Document**

Este documento describe de forma extensa, precisa y estructurada los **tipos de plugins requeridos en el sistema prediction_provider**, especificando para cada tipo de plugin su funcionalidad exacta, los métodos clave y los parámetros a utilizar. Todas las clases de plugins deben inicializarse con un parámetro obligatorio `config` (tipo `dict`), el cual se obtiene desde el módulo central `app/config.py` y es sobreescrito por parámetros de CLI, archivos JSON locales o configuraciones remotas.

---

## 1. pipeline plugins

### 1.1 Objetivo
Orquestan el flujo de procesamiento dentro del prediction_provider desde la recepción de los datos hasta la entrega de la predicción, permitiendo realizar transformaciones previas y posteriores a la predicción.

### 1.2 Métodos mínimos
- `__init__(self, config: dict)`: inicializa el plugin con la configuración global de la aplicación.
- `run(self, data: pd.DataFrame) -> pd.DataFrame`: ejecuta la secuencia definida del pipeline sobre el dataframe de entrada, devolviendo el dataframe procesado.

### 1.3 Parámetros relevantes en config
- `pipeline.steps`: lista ordenada de operaciones a realizar, por ejemplo: `["normalize", "impute", "feature_selection", "post_processing"]`.
- `pipeline.logging`: nivel de log deseado para el pipeline (e.g., `INFO`, `DEBUG`).

---

## 2. data_feeder plugins

### 2.1 Objetivo
Obtener y preparar los últimos `n_batches * batch_size` registros de todas las características requeridas por el predictor o el pipeline. Cada feeder define cómo y desde dónde obtiene los datos de entrada (live, histórico, sintético).

### 2.2 Métodos mínimos
- `__init__(self, config: dict)`: inicializa el plugin con la configuración global.
- `fetch(self) -> pd.DataFrame`: obtiene y retorna un dataframe con los registros actualizados.

### 2.3 Parámetros relevantes en config
- `data_feeder.instrument`: identificador del activo o instrumento financiero a alimentar.
- `data_feeder.api_url`: URL del proveedor de datos si aplica.
- `data_feeder.batch_size`: número de registros a traer por lote.
- `data_feeder.n_batches`: número de lotes a acumular.
- `data_feeder.lookback`: número de ticks/hora/días hacia atrás a considerar para cada predicción.

---

## 3. predictor plugins

### 3.1 Objetivo
Cargar modelos pre-entrenados y generar predicciones. Estos plugins permiten soportar múltiples formatos de modelos (e.g., Keras, ONNX) o servicios externos.

### 3.2 Métodos mínimos
- `__init__(self, config: dict)`: inicializa el plugin con la configuración global.
- `load_model(self)`: carga el modelo desde disco, almacenamiento remoto o servicio externo.
- `predict(self, data: pd.DataFrame) -> np.ndarray`: realiza la inferencia sobre el dataframe y devuelve las predicciones como arreglo numpy.

### 3.3 Parámetros relevantes en config
- `predictor.model_type`: tipo de modelo (`keras`, `onnx`, `remote`, etc.).
- `predictor.model_path`: ruta local o URL del modelo a cargar.
- `predictor.device`: dispositivo para inferencia (e.g., `cpu`, `cuda`).
- `predictor.scaling`: configuración opcional para normalización inversa tras la predicción (e.g., `z-score`, `min-max`).

---

## 4. api_endpoints plugins

### 4.1 Objetivo
Definir endpoints RESTful individuales de la API Flask para exponer funcionalidad externa del prediction_provider como predicciones, status o métricas.

### 4.2 Métodos mínimos
- `__init__(self, config: dict)`: inicializa el plugin con la configuración global.
- `register(self, app: Flask)`: registra el endpoint en la instancia de Flask pasada como parámetro.

### 4.3 Parámetros relevantes en config
- `api_endpoints.route`: ruta específica del endpoint (e.g., `/predict`, `/health`, `/info`).
- `api_endpoints.methods`: lista de métodos HTTP permitidos (e.g., `["GET", "POST"]`).
- `api_endpoints.auth_required`: flag booleano que indica si el endpoint requiere autenticación.

---

## 5. api_core plugins

### 5.1 Objetivo
Gestionar la configuración central del servidor Flask API, incluyendo autenticación, CORS, middleware y opciones globales de seguridad.

### 5.2 Métodos mínimos
- `__init__(self, config: dict)`: inicializa el plugin con la configuración global.
- `init_app(self, app: Flask)`: aplica configuraciones globales sobre la instancia de Flask, como middlewares de autenticación o manejo de CORS.

### 5.3 Parámetros relevantes en config
- `api_core.auth_type`: tipo de autenticación global (`none`, `basic`, `jwt`).
- `api_core.jwt_secret`: clave secreta para autenticación JWT si aplica.
- `api_core.allowed_origins`: lista de dominios permitidos para CORS.
- `api_core.port`: puerto en el que se expondrá el servidor Flask.
- `api_core.debug`: habilita o desactiva modo debug del servidor Flask.

---

## 6. Consideraciones generales

- Todos los plugins deben manejar de forma robusta el parámetro `config` y documentar los parámetros específicos que utilizan.
- La coherencia en la definición de métodos mínimos entre plugins es clave para mantener compatibilidad con el sistema actual de carga dinámica.
- La arquitectura debe permitir la ejecución de varios plugins del mismo tipo (por ejemplo, múltiples `data_feeder`) en paralelo, para soportar la alimentación de varios instrumentos en un solo servidor prediction_provider.
- Se recomienda implementar validación exhaustiva de configuraciones en el `__init__` de cada plugin para evitar errores silenciosos durante la ejecución.

---

**Fin del documento**
