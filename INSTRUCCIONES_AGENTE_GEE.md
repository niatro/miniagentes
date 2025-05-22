# Guía para Probar el Agente Cartográfico de Google Earth Engine

Este documento te guiará para probar y utilizar el script `sfa_gee_cartography_agent_openai_v1.py`.

## 1. Objetivo del Código

El script `sfa_gee_cartography_agent_openai_v1.py` es un **agente de IA especializado en cartografía** que utiliza Google Earth Engine (GEE). Su propósito es interpretar tus solicitudes (en lenguaje natural) para generar imágenes geoespaciales. Para ello, se comunica con un modelo de lenguaje grande (LLM) como GPT de OpenAI (por ejemplo, `gpt-4o-mini`), el cual decide qué "herramientas" (funciones predefinidas en el script) usar para realizar diversas tareas en GEE.

Las principales capacidades del agente incluyen:

*   **Inicializar GEE**: Establecer la conexión necesaria con los servicios de Google Earth Engine.
*   **Definir Áreas de Interés (AOI)**: Puede crear un AOI a partir de un GeoJSON que el LLM genera basado en tu descripción (ej. "Valparaíso, Chile").
*   **Obtener Imágenes Satelitales**: Busca y filtra colecciones de imágenes (como Sentinel-2 o Landsat) por fecha, el AOI definido y el porcentaje de nubes.
*   **Calcular Índices**: Genera productos como el NDVI (Índice de Vegetación de Diferencia Normalizada) o NDBI (Índice de Edificación de Diferencia Normalizada).
*   **Crear Compuestos RGB**: Genera imágenes de color natural (lo que vería el ojo humano).
*   **Generar Miniaturas (Thumbnails)**: Guarda una vista previa de la imagen resultante en una carpeta local (`./map_previews/`).
*   **Exportar a Google Drive**: Guarda la imagen final en formato GeoTIFF en una carpeta de tu Google Drive.

El agente opera en ciclos: recibe tu instrucción, el LLM elige una herramienta, la ejecuta, obtiene un resultado, y el LLM decide el siguiente paso hasta completar tu solicitud.

## 2. Ejecución en Terminal

Para usar el agente, abres tu terminal y utilizas el comando `uv run` de la siguiente manera:

```bash
uv run sfa_gee_cartography_agent_openai_v1.py -p "TU_INSTRUCCIÓN_AQUÍ" [OPCIONES]
```

**Parámetros principales:**

*   `-p "TU_INSTRUCCIÓN_AQUÍ"` o `--prompt "TU_INSTRUCCIÓN_AQUÍ"`: **Este es el más importante.** Aquí escribes en lenguaje natural lo que quieres que el agente haga.
    *   *Ejemplo*: `"Genera una imagen de color natural para Valparaíso de Chile, usando imágenes Sentinel-2 para el año 2023. Exporta el resultado a Google Drive y muéstrame una miniatura local."`
*   `-m "MODELO_LLM"` o `--model "MODELO_LLM"`: (Opcional) Especifica el modelo de OpenAI a usar. Por defecto es `"gpt-4o-mini"`. Se recomienda usar modelos capaces como `gpt-4o-mini` o `gpt-4` para obtener los mejores resultados en la interpretación de instrucciones y selección de herramientas.
*   `-c NUMERO_CICLOS` o `--compute NUMERO_CICLOS`: (Opcional) Número máximo de "pasos" o interacciones que el agente puede realizar. Por defecto es `10`. Si la tarea es compleja, podrías necesitar aumentarlo (ej. `15` o `20`).
*   `--drive-folder "CARPETA_DRIVE"`: (Opcional) Nombre de la carpeta en tu Google Drive donde se guardarán las imágenes. Por defecto es `"GEE_images"`.

**Ejemplo de comando completo:**

```bash
uv run sfa_gee_cartography_agent_openai_v1.py -p "Crea una imagen NDVI para la región del Maule en Chile para la temporada de verano de 2023 (enero a marzo), usando Sentinel-2. Exporta a Drive y genera una miniatura." -m "gpt-4o-mini" -c 15
```

## 3. Consideraciones para dar Instrucciones (Prompts) Efectivas

Para que el agente entienda bien y haga exactamente lo que necesitas, tus instrucciones deben ser lo más claras y detalladas posible:

*   **Lugar Específico (AOI)**:
    *   Menciona claramente la ciudad, región, país.
    *   Si es un área muy específica y conoces las coordenadas o tienes un GeoJSON, considera mencionarlo (aunque el agente intentará generar un GeoJSON a partir del nombre).
    *   El agente está instruido para crear un AOI de un tamaño razonable para una ciudad (ej. no solo una manzana).
*   **Fuente de Datos**:
    *   **Satélite**: "Sentinel-2", "Landsat 8", etc. El agente conoce los nombres de colección comunes (ej. `'COPERNICUS/S2_SR_HARMONIZED'` para Sentinel-2).
    *   **Tipo de dato**: "imágenes de reflectancia superficial" (SR), si es relevante.
*   **Fechas**:
    *   **Año**: "para el año 2023".
    *   **Rango de fechas**: "de enero a marzo de 2023", "entre 2022-05-01 y 2022-08-31".
*   **Producto Deseado**:
    *   **Tipo de imagen**: "imagen NDVI", "imagen NDBI", "imagen de color natural", "composición RGB".
    *   **Bandas (avanzado)**: Si necesitas una combinación de bandas específica para un falso color, puedes indicarlo.
*   **Parámetros de Visualización (Opcional, pero ayuda a la consistencia)**:
    *   Para **índices** (como NDVI): Puedes sugerir `min`, `max` y una `palette` de colores. Ejemplo: `vis_params {"min": -0.2, "max": 0.8, "palette": ["red", "yellow", "green"]}`.
    *   Para **RGB**: Puedes sugerir `min`, `max` y `gamma`. Ejemplo: `vis_params {"min": 0, "max": 3000, "gamma": 1.4}`.
    *   El agente tiene valores por defecto para RGB y el LLM intentará usar parámetros lógicos, pero especificarlos da más control.
*   **Acciones de Salida**:
    *   Indica si quieres una **miniatura local**: "y muéstrame una miniatura local".
    *   Indica si quieres **exportar a Google Drive**: "Exporta el resultado a Google Drive".
    *   **Resolución de exportación (`scale`)**: Por defecto, el agente usa 10m para Sentinel-2 o 30m para Landsat. Puedes pedir otra, ej: "exporta a 20 metros de resolución". El agente intentará reducir la resolución si el archivo estimado es mayor a 50MB.
*   **Claridad General**:
    *   Sé lo más explícito posible. Evita frases ambiguas.
    *   Detalla todos los componentes de tu solicitud.

**Ejemplo de una instrucción bien detallada:**

```
"Genera una imagen de color natural (RGB) para el Parque Nacional Torres del Paine en Chile, usando imágenes Sentinel-2 de reflectancia superficial, para el período comprendido entre el 15 de diciembre de 2023 y el 15 de febrero de 2024. Asegúrate de que la cobertura de nubes sea inferior al 10%. Quiero que la imagen se exporte a mi carpeta 'Imagenes_Satelitales/Chile' en Google Drive con una resolución de 10 metros. Además, genera una miniatura local de 768x768 píxeles usando los parámetros de visualización RGB por defecto."
```

## 4. Consideraciones Adicionales Importantes

*   **Autenticación GEE**: Es fundamental que hayas autenticado Google Earth Engine en tu máquina. Si no lo has hecho, o si el script da errores de autenticación, ejecuta `earthengine authenticate` en tu terminal y sigue los pasos.
*   **API Key de OpenAI**: Asegúrate de que la variable de entorno `OPENAI_API_KEY` esté configurada con tu clave.
*   **Proyecto GEE**: El script usa un ID de proyecto GEE por defecto (`industrious-eye-384414`). Si necesitas usar uno diferente, puedes configurarlo con la variable de entorno `GEE_PROJECT_ID`.
*   **Logs de Consola**: El script muestra mucha información mientras se ejecuta: qué herramienta usa el LLM, con qué argumentos, y cuál es el resultado. Esto es muy útil para entender el proceso y para depurar si algo no sale como esperas.
*   **Miniaturas Grises/En Blanco**: Si las miniaturas salen grises o en blanco, a menudo se debe a que los parámetros de visualización (`vis_params`) no se están aplicando correctamente o la región no está bien definida para la miniatura. Intenta ser explícito con los `vis_params` en tu prompt.
*   **Errores de Exportación**: Si la exportación a Drive falla, revisa los logs. A veces puede ser por nombres de archivo inválidos, problemas con el AOI, o (como se ha observado en pruebas anteriores) opciones de formato no soportadas por la API de GEE.

¡Mucha suerte con las pruebas!
