Este proyecto, denominado 'Single File Agents (SFA)', se enfoca en la creación de agentes de inteligencia artificial (IA) potentes y especializados, donde cada agente está contenido en un único archivo de Python. La premisa es doble: primero, explorar la viabilidad de empaquetar agentes de IA de propósito único en archivos individuales; segundo, identificar los mejores patrones estructurales para construir agentes cuya capacidad pueda escalar con los avances en computación e inteligencia.

Estos agentes están diseñados para realizar una tarea específica de manera muy eficiente, demostrando el uso de ingeniería de prompts precisa y patrones de IA Generativa para tareas prácticas. El proyecto utiliza `uv` como instalador y gestor de paquetes de Python moderno y eficiente.

El repositorio contiene varios agentes construidos utilizando los servicios de los principales proveedores de IA Generativa (Gemini, OpenAI, Anthropic), abarcando tareas como:
-   Procesamiento de JSON con `jq`.
-   Consultas a bases de datos DuckDB y SQLite.
-   Edición de archivos y ejecución de comandos bash.
-   Transformación de datos CSV con Polars.
-   Extracción de contenido web (web scraping).
-   Generación de meta-prompts.

El objetivo principal es ofrecer ejemplos claros y funcionales de cómo construir agentes de IA modulares, minimalistas y reutilizables, destacando patrones efectivos para el desarrollo de IA.
