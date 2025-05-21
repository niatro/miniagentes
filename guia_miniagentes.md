# Guía Rápida de Miniagentes de IA

Estos scripts son "miniagentes" de Inteligencia Artificial, cada uno diseñado para una tarea específica. Para usarlos, necesitarás tener `uv` (un gestor de paquetes de Python) instalado y las claves API correspondientes configuradas como variables de entorno.

### 1. Agente Editor de Archivos y Terminal (Bash)

*   **Nombre del archivo:** `sfa_bash_editor_agent_anthropic.py`
*   **Objetivo Principal:** Este agente actúa como un asistente de IA capaz de entender tus instrucciones para realizar cambios en archivos (crear, ver, modificar texto) y ejecutar comandos directamente en la terminal de tu sistema (como listar archivos, correr scripts, etc.). Es útil para automatizar tareas de desarrollo o administración de sistemas mediante lenguaje natural.
*   **Requisitos Previos:**
    *   Tener configurada la variable de entorno `ANTHROPIC_API_KEY` con tu clave API de Anthropic.
    *   Ejemplo: `export ANTHROPIC_API_KEY='tu_clave_api_aqui'`
*   **Cómo ejecutarlo:**
    ```bash
    uv run sfa_bash_editor_agent_anthropic.py --prompt "TU_INSTRUCCIÓN_AQUÍ"
    ```
*   **Parámetros importantes:**
    *   `--prompt "TU_INSTRUCCIÓN_AQUÍ"` (o `-p`): Describe la tarea que quieres que el agente realice. Por ejemplo, "Crea un archivo llamado 'notas.txt' con el texto 'Recordatorio importante'". (Obligatorio)
    *   `--compute <NÚMERO>` (o `-c`): Opcionalmente, puedes especificar el número máximo de pasos o interacciones que el agente puede realizar. Por defecto es 10.
*   **Ejemplos de uso:**
    *   Para crear un archivo:
        ```bash
        uv run sfa_bash_editor_agent_anthropic.py --prompt "Crea un archivo llamado 'saludo.txt' con el texto 'Hola desde el agente IA'"
        ```
    *   Para listar los archivos Python en el directorio actual:
        ```bash
        uv run sfa_bash_editor_agent_anthropic.py --prompt "Lista todos los archivos Python en el directorio actual"
        ```
    *   Para ver el contenido de un archivo:
        ```bash
        uv run sfa_bash_editor_agent_anthropic.py --prompt "Muéstrame el contenido del archivo README.md"
        ```

---

### 2. Agente Extractor de Contenido Web (Scraper)

*   **Nombre del archivo:** `sfa_scrapper_agent_openai.py`
*   **Objetivo Principal:** Este agente está diseñado para visitar páginas web, extraer su contenido y luego procesarlo o filtrarlo según tus indicaciones. Puede, por ejemplo, resumir un artículo, extraer datos específicos o guardar el contenido limpio de una web en un archivo.
*   **Requisitos Previos:**
    *   Tener configurada la variable de entorno `OPENAI_API_KEY` con tu clave API de OpenAI.
        *   Ejemplo: `export OPENAI_API_KEY='tu_clave_api_aqui'`
    *   Tener configurada la variable de entorno `FIRECRAWL_API_KEY` con tu clave API de Firecrawl (servicio utilizado para la extracción web inicial).
        *   Ejemplo: `export FIRECRAWL_API_KEY='tu_clave_api_aqui'`
*   **Cómo ejecutarlo:**
    ```bash
    uv run sfa_scrapper_agent_openai.py --url "URL_DE_LA_PAGINA" --prompt "QUÉ_HACER_CON_EL_CONTENIDO" --output-file-path "ARCHIVO_DE_SALIDA.md"
    ```
*   **Parámetros importantes:**
    *   `--url "URL_DE_LA_PAGINA"` (o `-u`): La dirección completa de la página web que quieres analizar. (Obligatorio)
    *   `--prompt "QUÉ_HACER_CON_EL_CONTENIDO"` (o `-p`): Describe qué información quieres extraer o cómo quieres que se procese el contenido de la página. Por ejemplo, "Extrae los títulos principales y guárdalos en una lista". (Obligatorio)
    *   `--output-file-path "ARCHIVO_DE_SALIDA.md"` (o `-o`): El nombre del archivo donde se guardará el resultado. Si no se especifica, por defecto será `scraped_content.md`. (Opcional)
    *   `--compute-limit <NÚMERO>` (o `-c`): Opcionalmente, el número máximo de pasos o interacciones. Por defecto es 10.
*   **Ejemplos de uso:**
    *   Para extraer los encabezados de una página y guardarlos:
        ```bash
        uv run sfa_scrapper_agent_openai.py --url "https://www.wikipedia.org" --prompt "Extrae todos los encabezados H2 del contenido principal" --output-file-path "encabezados_wiki.md"
        ```
    *   Para obtener un resumen de un artículo:
        ```bash
        uv run sfa_scrapper_agent_openai.py --url "https://www.ejemplo.com/articulo-interesante" --prompt "Resume este artículo en tres párrafos" -o "resumen_articulo.txt"
        ```

---

### 3. Agente Analista de Datos Excel

*   **Nombre del archivo:** `sfa_excel_openai.py`
*   **Objetivo Principal:** Este agente está especializado en interactuar con archivos de Microsoft Excel (.xlsx, .xls). Puede explorar el contenido de las hojas, identificar tablas o bloques de datos (incluso si no están perfectamente estructurados), describir su contenido y columnas, mostrar ejemplos de filas, y ejecutar consultas sobre los datos utilizando expresiones de Pandas (una librería de Python para análisis de datos). Es ideal para entender y extraer información de planillas de cálculo.
*   **Requisitos Previos:**
    *   Tener configurada la variable de entorno `OPENAI_API_KEY` con tu clave API de OpenAI.
        *   Ejemplo: `export OPENAI_API_KEY='tu_clave_api_aqui'`
*   **Cómo ejecutarlo:**
    ```bash
    uv run sfa_excel_openai.py --db "RUTA_AL_ARCHIVO_EXCEL" --prompt "TU_PREGUNTA_O_INSTRUCCIÓN"
    ```
*   **Parámetros importantes:**
    *   `--db "RUTA_AL_ARCHIVO_EXCEL"` (o `-d`): La ruta completa a tu archivo Excel. (Obligatorio)
    *   `--prompt "TU_PREGUNTA_O_INSTRUCCIÓN"` (o `-p`): Describe qué quieres saber o hacer con el archivo Excel. Por ejemplo, "Explícame de qué trata esta planilla" o "En la hoja 'Ventas', ¿cuál es el promedio de la columna 'Total'?". (Obligatorio)
    *   `--compute <NÚMERO>` (o `-c`): Opcionalmente, el número máximo de pasos o interacciones que el agente puede realizar. Por defecto es 15.
    *   `--model <NOMBRE_MODELO>` (o `-m`): Opcionalmente, puedes especificar el modelo de OpenAI a utilizar (ej. `gpt-4o-mini`, `gpt-4-turbo`). Por defecto es `gpt-4o-mini`.
*   **Ejemplos de uso:**
    *   Para obtener una descripción general del contenido de un archivo Excel:
        ```bash
        uv run sfa_excel_openai.py --db "MiReporte.xlsx" --prompt "Dime qué tipo de información contiene este archivo"
        ```
    *   Para encontrar el valor máximo en una columna específica de una hoja:
        ```bash
        uv run sfa_excel_openai.py --db "datos_financieros.xlsx" --prompt "En la hoja 'Balance', ¿cuál es el valor más alto en la columna 'Activos'?"
        ```
    *   Para filtrar datos:
        ```bash
        uv run sfa_excel_openai.py --db "inventario.xlsx" --prompt "Muéstrame los productos de la hoja 'Stock' donde la cantidad sea menor a 10"
        ```

---
