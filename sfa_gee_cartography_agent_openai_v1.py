# /// script
# dependencies = [
#   "openai>=1.63.0",
#   "rich>=13.7.0",
#   "pydantic>=2.0.0",
#   "python-dotenv>=0.21.0",
#   "google-api-python-client", # GEE Python client library
#   "earthengine-api",        # GEE API
#   "requests>=2.20.0"        # For downloading thumbnails
# ]
# ///

"""
DESCRIPCIÓN DEL SCRIPT
----------------------
Este script es un mini-agente cartográfico que utiliza Google Earth Engine (GEE)
para generar imágenes geoespaciales (NDBI, RGB Color Verdadero) basadas en las
peticiones de un usuario. Interactúa con la API de OpenAI (u otro LLM) para
interpretar las solicitudes y utiliza un conjunto de herramientas para realizar
operaciones en GEE.

PUNTOS CLAVE:
- Utiliza la autenticación de usuario estándar de GEE (requiere `earthengine authenticate`).
- Puede generar imágenes NDBI y RGB.
- Guarda miniaturas (thumbnails) localmente en la carpeta `./map_previews/`.
- Exporta imágenes finales a una carpeta específica en Google Drive (por defecto "GEE_images").
- Las operaciones de GEE se encapsulan en herramientas que el LLM puede invocar.
- Los objetos de GEE (Image, ImageCollection) se almacenan en caché entre llamadas.

EJEMPLO DE EJECUCIÓN:
    uv run sfa_gee_cartography_agent_openai_v1.py \
        -p "Genera una imagen NDBI para Santiago de Chile, usando Sentinel-2 para el año 2023. Exporta a Drive y muéstrame una miniatura." \
        -m "gpt-4o-mini"

Parámetros:
  -p, --prompt: Petición del usuario para la generación cartográfica.
  -m, --model: Modelo de OpenAI a utilizar (ej. gpt-4o-mini).
  -c, --compute: Máx. de iteraciones del agente.
  --drive-folder: Carpeta en Google Drive para exportar imágenes (def: "GEE_images").

DEPENDENCIAS:
    - openai, rich, pydantic, python-dotenv
    - google-api-python-client, earthengine-api
    - requests

LIMITACIONES:
- La definición del Área de Interés (AOI) a partir de descripciones textuales complejas
  puede requerir que el LLM genere un GeoJSON o que el usuario provea coordenadas.
- La selección de bandas y parámetros de visualización depende de la capacidad del LLM.
- Las exportaciones a Drive son asíncronas; el script solo inicia la tarea.
"""

import os
import sys
import json
import argparse
import uuid
from typing import List, Dict, Any, Optional, Tuple, Union

from dotenv import load_dotenv
import openai
from pydantic import BaseModel, Field, ValidationError
from openai import pydantic_function_tool # type: ignore
from rich.console import Console
from rich.panel import Panel
import requests

# Intentar importar Earth Engine y manejar si no está disponible o autenticado
try:
    import ee
except ImportError:
    print("La librería 'earthengine-api' no está instalada. Por favor, instálala: pip install earthengine-api")
    sys.exit(1)

# ---------------------------------------------------
# CONFIGURACIÓN DE CONSOLA Y VARIABLES GLOBALES
# ---------------------------------------------------
console = Console()
OPENAI_API_KEY = None
GEE_INITIALIZED = False
# Caché para almacenar objetos GEE entre llamadas de herramientas (Image, ImageCollection)
# Las claves serán strings (ej. "last_collection", "ndvi_image_2023"), los valores objetos ee.
GEE_ASSETS_CACHE: Dict[str, Any] = {}
DEFAULT_DRIVE_FOLDER = "GEE_images"
THUMBNAIL_DIR = "./map_previews"
GEE_PROJECT_ID = "industrious-eye-384414" # ID del proyecto GEE/GCP

# ---------------------------------------------------
# MODELOS Pydantic (definición de args de cada tool)
# ---------------------------------------------------

class VisParamsBase(BaseModel):
    min: Optional[Union[float, int]] = None
    max: Optional[Union[float, int]] = None
    gamma: Optional[float] = None
    bands: Optional[List[str]] = None
    palette: Optional[List[str]] = None

class InitializeGeeArgs(BaseModel):
    reasoning: str = Field(..., description="Razón para inicializar Google Earth Engine.")

class DefineAoiFromGeoJSONArgs(BaseModel):
    reasoning: str = Field(..., description="Razón para definir el Área de Interés (AOI).")
    geojson_string: str = Field(..., description="String GeoJSON que define el polígono o punto del AOI. Ejemplo para un punto: '{\"type\": \"Point\", \"coordinates\": [-70.6, -33.4]}'. Ejemplo para un polígono: '{\"type\": \"Polygon\", \"coordinates\": [[[-70.0, -33.0], [-71.0, -33.0], [-71.0, -34.0], [-70.0, -34.0], [-70.0, -33.0]]]}'")
    aoi_id: str = Field(default="current_aoi", description="ID para referenciar este AOI en el caché.")

class GetImageCollectionArgs(BaseModel):
    reasoning: str = Field(..., description="Razón para obtener esta colección de imágenes.")
    collection_name: str = Field(..., description="Nombre de la colección de GEE (ej. 'COPERNICUS/S2_SR_HARMONIZED', 'LANDSAT/LC08/C02/T1_L2').")
    start_date: str = Field(..., description="Fecha de inicio (YYYY-MM-DD).")
    end_date: str = Field(..., description="Fecha de fin (YYYY-MM-DD).")
    aoi_id: str = Field(..., description="ID del AOI previamente definido en el caché (ej. 'current_aoi').")
    cloud_cover_max_percent: Optional[int] = Field(default=20, description="Máximo porcentaje de cobertura de nubes permitido (0-100).")
    collection_cache_id: str = Field(default="last_filtered_collection", description="ID para guardar esta colección filtrada en el caché.")

class CalculateNdIndexArgs(BaseModel):
    reasoning: str = Field(..., description="Razón para calcular este índice de diferencia normalizada.")
    input_collection_cache_id: str = Field(..., description="ID de la colección de imágenes filtrada en el caché.")
    band1_name: str = Field(..., description="Nombre de la primera banda para el índice (ej. 'B8' para NIR en Sentinel-2 para NDVI, o 'B11' para SWIR1 en Sentinel-2 para NDBI).")
    band2_name: str = Field(..., description="Nombre de la segunda banda para el índice (ej. 'B4' para RED en Sentinel-2 para NDVI, o 'B8' para NIR en Sentinel-2 para NDBI).")
    output_image_cache_id: str = Field(..., description="ID para guardar la imagen resultante del índice en el caché.")

class GenerateRgbCompositeArgs(BaseModel):
    reasoning: str = Field(..., description="Razón para generar esta composición RGB.")
    input_collection_cache_id: str = Field(..., description="ID de la colección de imágenes filtrada en el caché.")
    red_band: str = Field(..., description="Nombre de la banda Roja (ej. 'B4' para Sentinel-2).")
    green_band: str = Field(..., description="Nombre de la banda Verde (ej. 'B3' para Sentinel-2).")
    blue_band: str = Field(..., description="Nombre de la banda Azul (ej. 'B2' para Sentinel-2).")
    vis_params_rgb: Optional[VisParamsBase] = Field(default_factory=lambda: VisParamsBase(min=0.0, max=3000, gamma=1.4), description="Parámetros de visualización para RGB (min, max, gamma, etc.). Ejemplo: {\"min\": 0, \"max\": 3000, \"bands\": [\"B4\", \"B3\", \"B2\"]}. Las bandas se infieren de los parámetros red_band, green_band, blue_band.")
    output_image_cache_id: str = Field(..., description="ID para guardar la imagen RGB resultante en el caché.")

class GetAndSaveThumbnailArgs(BaseModel):
    reasoning: str = Field(..., description="Razón para obtener y guardar esta miniatura.")
    image_cache_id: str = Field(..., description="ID de la imagen procesada (NDBI, RGB) en el caché.")
    vis_params: VisParamsBase = Field(..., description="Parámetros de visualización (min, max, palette, bands). Ejemplo NDBI: {\"min\": -0.5, \"max\": 0.5, \"palette\": [\"blue\", \"white\", \"brown\"], \"bands\": [\"nd_index\"]}. Ejemplo RGB: {\"min\": 0, \"max\": 3000, \"bands\": [\"B4\", \"B3\", \"B2\"], \"gamma\": 1.4}.")
    dimensions: str = Field(default="768x768", description="Dimensiones de la miniatura (ancho x alto en píxeles).")
    local_filename_prefix: str = Field(default="thumbnail", description="Prefijo para el nombre del archivo local de la miniatura (se añadirá un UUID y .png).")

class ExportImageToDriveArgs(BaseModel):
    reasoning: str = Field(..., description="Razón para exportar esta imagen a Google Drive.")
    image_cache_id: str = Field(..., description="ID de la imagen procesada en el caché a exportar.")
    description: str = Field(..., description="Descripción de la tarea de exportación (será el nombre del archivo .tif).")
    drive_folder: str = Field(default=DEFAULT_DRIVE_FOLDER, description="Nombre de la carpeta en Google Drive donde se guardará la imagen.")
    scale: int = Field(default=30, description="Resolución de la exportación en metros por píxel.")
    crs: Optional[str] = Field(default=None, description="Sistema de Coordenadas de Referencia (ej. 'EPSG:4326'). Si es None, usa la proyección de la imagen.")
    vis_params_for_export: Optional[VisParamsBase] = Field(default=None, description="Parámetros de visualización para aplicar a la imagen antes de exportar (ej. para exportar una imagen RGB estilizada o un índice coloreado). Si es None, se exportan los datos crudos (ej. para un índice). Ejemplo para NDBI coloreado: {\"min\": -0.5, \"max\": 0.5, \"palette\": [\"blue\", \"white\", \"brown\"], \"bands\": [\"nd_index\"]}")

class CompleteTaskArgs(BaseModel):
    reasoning: str = Field(..., description="Razón por la cual la tarea se considera completada.")
    final_message_to_user: str = Field(..., description="Mensaje final para mostrar al usuario resumiendo el resultado.")

# ---------------------------------------------------
# FUNCIONES HERRAMIENTA (tools)
# ---------------------------------------------------

def _ensure_gee_initialized() -> Tuple[bool, Optional[str]]:
    global GEE_INITIALIZED
    if not GEE_INITIALIZED:
        console.print(f"[yellow]GEE no inicializado. Intentando ee.Initialize() con el proyecto '{GEE_PROJECT_ID}'...[/yellow]")
        try:
            ee.Initialize(project=GEE_PROJECT_ID, opt_url='https://earthengine-highvolume.googleapis.com')
            GEE_INITIALIZED = True
            console.print(f"[green]GEE inicializado correctamente con el proyecto '{GEE_PROJECT_ID}'.[/green]")
            return True, None
        except Exception as e:
            error_msg = f"Error al inicializar GEE: {e}"
            console.print(f"[red]{error_msg}[/red]")
            if "no project found" in str(e).lower() or "project_id" in str(e).lower():
                 console.print(f"[yellow]Asegúrate de que el ID del proyecto '{GEE_PROJECT_ID}' es correcto y que la API de Earth Engine está habilitada para él en Google Cloud Console. También puedes necesitar configurar el proyecto con 'gcloud config set project {GEE_PROJECT_ID}'.[/yellow]")
            elif "authenticate" in str(e).lower() or "authentication" in str(e).lower():
                console.print("[yellow]Por favor, asegúrate de haber autenticado GEE ejecutando 'earthengine authenticate' en tu terminal.[/yellow]")
            GEE_INITIALIZED = False
            return False, error_msg
    return True, None

def initialize_gee(reasoning: str) -> str:
    console.log(f"[blue]Tool: initialize_gee[/blue] - Reasoning: {reasoning}")
    success, error_message = _ensure_gee_initialized()
    if success:
        return f"Google Earth Engine inicializado exitosamente (o ya estaba inicializado) con el proyecto '{GEE_PROJECT_ID}'."
    else:
        response_message = "Fallo al inicializar Google Earth Engine."
        if error_message: response_message += f" Detalle: {error_message}."
        if error_message and ("no project found" in error_message.lower() or "project_id" in error_message.lower()):
            response_message += f" Verifica que el ID del proyecto '{GEE_PROJECT_ID}' sea correcto y que la API de Earth Engine esté habilitada. Considera ejecutar 'gcloud config set project {GEE_PROJECT_ID}'."
        elif error_message and ("authenticate" in error_message.lower() or "authentication" in error_message.lower()):
            response_message += " El usuario debe ejecutar 'earthengine authenticate' en su terminal."
        else:
            response_message += " Revisa los logs para más detalles."
        return response_message

def define_aoi_from_geojson(reasoning: str, geojson_string: str, aoi_id: str) -> str:
    console.log(f"[blue]Tool: define_aoi_from_geojson[/blue] - AOI ID: {aoi_id} - Reasoning: {reasoning}")
    initialized, error_detail = _ensure_gee_initialized()
    if not initialized: return f"Error: GEE no inicializado. {error_detail if error_detail else 'Causa desconocida.'}"
    try:
        geojson_obj = json.loads(geojson_string)
        if geojson_obj['type'] == 'Point': aoi = ee.Geometry.Point(geojson_obj['coordinates'])
        elif geojson_obj['type'] == 'Polygon': aoi = ee.Geometry.Polygon(geojson_obj['coordinates'])
        else: return f"Error: Tipo de GeoJSON no soportado: {geojson_obj['type']}. Usar Point o Polygon."
        GEE_ASSETS_CACHE[aoi_id] = aoi
        return f"AOI '{aoi_id}' definido y guardado en caché desde GeoJSON: {geojson_string}."
    except json.JSONDecodeError: return "Error: El string GeoJSON proporcionado no es válido."
    except Exception as e: return f"Error al definir AOI desde GeoJSON: {str(e)}"

def get_image_collection(reasoning: str, collection_name: str, start_date: str, end_date: str, aoi_id: str, cloud_cover_max_percent: Optional[int], collection_cache_id: str) -> str:
    console.log(f"[blue]Tool: get_image_collection[/blue] - Collection: {collection_name} - Cache ID: {collection_cache_id} - Reasoning: {reasoning}")
    initialized, error_detail = _ensure_gee_initialized()
    if not initialized: return f"Error: GEE no inicializado. {error_detail if error_detail else 'Causa desconocida.'}"
    if aoi_id not in GEE_ASSETS_CACHE or not isinstance(GEE_ASSETS_CACHE[aoi_id], ee.Geometry):
        return f"Error: AOI con ID '{aoi_id}' no encontrado en caché o no es una geometría válida."
    aoi = GEE_ASSETS_CACHE[aoi_id]
    try:
        collection = ee.ImageCollection(collection_name).filterBounds(aoi).filterDate(ee.Date(start_date), ee.Date(end_date))
        if cloud_cover_max_percent is not None:
            cloud_filter_prop = 'CLOUDY_PIXEL_PERCENTAGE' # Default for S2
            if "LANDSAT" in collection_name and ("C02/T1_L2" in collection_name or "C02/T2_L2" in collection_name):
                cloud_filter_prop = 'CLOUD_COVER_LAND'
            elif "LANDSAT" in collection_name: # Older Landsat or other collections
                cloud_filter_prop = 'CLOUD_COVER'
            collection = collection.filter(ee.Filter.lte(cloud_filter_prop, cloud_cover_max_percent))
        
        # Verificar el tamaño de la colección
        num_images = collection.size().getInfo()
        if num_images == 0:
            return (f"Error: No se encontraron imágenes en la colección '{collection_name}' para los filtros aplicados "
                    f"(AOI: {aoi_id}, Fechas: {start_date}-{end_date}, Nubes <= {cloud_cover_max_percent}%). "
                    f"No se puede continuar. Considera ampliar el rango de fechas o el AOI, o aumentar el umbral de nubes.")

        GEE_ASSETS_CACHE[collection_cache_id] = collection
        return (f"ImageCollection '{collection_name}' filtrada ({num_images} imágenes encontradas, AOI: {aoi_id}, "
                f"Fechas: {start_date}-{end_date}, Nubes <= {cloud_cover_max_percent}%) y guardada como '{collection_cache_id}'.")
    except Exception as e: return f"Error al obtener ImageCollection '{collection_name}': {str(e)}"

def calculate_nd_index(reasoning: str, input_collection_cache_id: str, band1_name: str, band2_name: str, output_image_cache_id: str) -> str:
    console.log(f"[blue]Tool: calculate_nd_index[/blue] - Output ID: {output_image_cache_id} - Bands: ({band1_name}, {band2_name}) - Reasoning: {reasoning}")
    initialized, error_detail = _ensure_gee_initialized()
    if not initialized: return f"Error: GEE no inicializado. {error_detail if error_detail else 'Causa desconocida.'}"
    if input_collection_cache_id not in GEE_ASSETS_CACHE or not isinstance(GEE_ASSETS_CACHE[input_collection_cache_id], ee.ImageCollection):
        return f"Error: Colección '{input_collection_cache_id}' no encontrada o no es ImageCollection."
    collection = GEE_ASSETS_CACHE[input_collection_cache_id]
    try:
        image_composite = collection.median()
        nd_image = image_composite.normalizedDifference([band1_name, band2_name]).rename('nd_index')
        GEE_ASSETS_CACHE[output_image_cache_id] = nd_image
        return f"Índice normalizado calculado ({band1_name}, {band2_name}) de '{input_collection_cache_id}', guardado como '{output_image_cache_id}'."
    except Exception as e: return f"Error al calcular índice: {str(e)}"

def generate_rgb_composite(reasoning: str, input_collection_cache_id: str, red_band: str, green_band: str, blue_band: str, vis_params_rgb: Optional[Union[VisParamsBase, dict]], output_image_cache_id: str) -> str:
    console.log(f"[blue]Tool: generate_rgb_composite[/blue] - Output ID: {output_image_cache_id} - Bands R:{red_band},G:{green_band},B:{blue_band} - Reasoning: {reasoning}")
    initialized, error_detail = _ensure_gee_initialized()
    if not initialized: return f"Error: GEE no inicializado. {error_detail if error_detail else 'Causa desconocida.'}"
    if input_collection_cache_id not in GEE_ASSETS_CACHE or not isinstance(GEE_ASSETS_CACHE[input_collection_cache_id], ee.ImageCollection):
        return f"Error: Colección '{input_collection_cache_id}' no encontrada o no es ImageCollection."
    collection = GEE_ASSETS_CACHE[input_collection_cache_id]
    try:
        image_composite = collection.median()
        rgb_image = image_composite.select([red_band, green_band, blue_band])
        GEE_ASSETS_CACHE[output_image_cache_id] = rgb_image

        vis_params_rgb_model: Optional[VisParamsBase] = None
        if isinstance(vis_params_rgb, dict):
            try:
                vis_params_rgb_model = VisParamsBase.model_validate(vis_params_rgb)
            except ValidationError as ve:
                return f"Error al validar vis_params_rgb para RGB: {ve}."
        elif isinstance(vis_params_rgb, VisParamsBase):
            vis_params_rgb_model = vis_params_rgb
        elif vis_params_rgb is not None: # Not a dict, not VisParamsBase, but not None
             return f"Error: Tipo de vis_params_rgb inesperado: {type(vis_params_rgb)}."

        vis_params_rgb_dict = vis_params_rgb_model.model_dump(exclude_none=True) if vis_params_rgb_model else {}
        return f"RGB generado (R:{red_band},G:{green_band},B:{blue_band}) de '{input_collection_cache_id}', guardado como '{output_image_cache_id}'. VisParams: {vis_params_rgb_dict}"
    except Exception as e: return f"Error al generar RGB: {str(e)}"

def get_and_save_thumbnail(reasoning: str, image_cache_id: str, vis_params: Union[VisParamsBase, dict], dimensions: str, local_filename_prefix: str) -> str:
    console.log(f"[blue]Tool: get_and_save_thumbnail[/blue] - Image ID: {image_cache_id} - Prefix: {local_filename_prefix} - Reasoning: {reasoning}")
    initialized, error_detail = _ensure_gee_initialized()
    if not initialized: return f"Error: GEE no inicializado. {error_detail if error_detail else 'Causa desconocida.'}"
    if image_cache_id not in GEE_ASSETS_CACHE or not isinstance(GEE_ASSETS_CACHE[image_cache_id], ee.Image):
        return f"Error: Imagen '{image_cache_id}' no encontrada o no es ee.Image."
    image_to_thumb = GEE_ASSETS_CACHE[image_cache_id]
    vis_params_model: VisParamsBase
    if isinstance(vis_params, dict):
        try: vis_params_model = VisParamsBase.model_validate(vis_params)
        except ValidationError as ve: return f"Error al validar vis_params: {ve}."
    elif isinstance(vis_params, VisParamsBase): vis_params_model = vis_params
    else: return f"Error: Tipo de vis_params inesperado: {type(vis_params)}."
    try:
        if not os.path.exists(THUMBNAIL_DIR): os.makedirs(THUMBNAIL_DIR)
        vis_params_dict = vis_params_model.model_dump(exclude_none=True)
        
        # Asegurarse de que 'bands' esté presente si es un índice y se espera una paleta
        # La imagen de índice se guarda con una sola banda llamada 'nd_index'
        if 'palette' in vis_params_dict and 'bands' not in vis_params_dict and image_to_thumb.bandNames().getInfo() == ['nd_index']:
            vis_params_dict['bands'] = ['nd_index']
        
        thumb_params = {**vis_params_dict, 'dimensions': dimensions, 'format': 'png'}
        thumb_url = image_to_thumb.getThumbURL(thumb_params)
        response = requests.get(thumb_url); response.raise_for_status()

        # Clean the prefix to be just the base name, removing any directory parts
        cleaned_prefix = os.path.basename(local_filename_prefix)
        filename = f"{cleaned_prefix.replace(' ', '_')}_{uuid.uuid4().hex[:8]}.png"
        filepath = os.path.join(THUMBNAIL_DIR, filename) # Now THUMBNAIL_DIR is prepended to a clean name

        with open(filepath, 'wb') as f: f.write(response.content)
        return f"Miniatura guardada: {filepath}. VisParams: {thumb_params}"
    except Exception as e:
        console.print(f"[bold red]Detalle error thumbnail: {e}[/bold red]")
        return f"Error al guardar miniatura para '{image_cache_id}': {str(e)}."

def export_image_to_drive(reasoning: str, image_cache_id: str, description: str, drive_folder: str, scale: int, crs: Optional[str], vis_params_for_export: Optional[VisParamsBase]) -> str:
    console.log(f"[blue]Tool: export_image_to_drive[/blue] - Desc: {description} - Folder: {drive_folder} - Reasoning: {reasoning}")
    initialized, error_detail = _ensure_gee_initialized()
    if not initialized: return f"Error: GEE no inicializado. {error_detail if error_detail else 'Causa desconocida.'}"
    if image_cache_id not in GEE_ASSETS_CACHE or not isinstance(GEE_ASSETS_CACHE[image_cache_id], ee.Image):
        return f"Error: Imagen '{image_cache_id}' no encontrada o no es ee.Image."
    image_to_export_orig = GEE_ASSETS_CACHE[image_cache_id]
    aoi_for_export = GEE_ASSETS_CACHE.get("current_aoi")
    if not aoi_for_export or not isinstance(aoi_for_export, ee.Geometry):
        try: aoi_for_export = image_to_export_orig.geometry()
        except Exception as e_geom: return f"Error: No se pudo obtener AOI para exportar '{image_cache_id}': {e_geom}."
    try:
        image_to_export = image_to_export_orig
        vis_params_export_dict = {}
        if vis_params_for_export:
            vis_model: Optional[VisParamsBase] = None
            if isinstance(vis_params_for_export, dict):
                try: vis_model = VisParamsBase.model_validate(vis_params_for_export)
                except ValidationError as ve: return f"Error al validar vis_params_for_export: {ve}"
            elif isinstance(vis_params_for_export, VisParamsBase):
                vis_model = vis_params_for_export
            
            if vis_model:
                vis_params_export_dict = vis_model.model_dump(exclude_none=True)
                # Asegurar 'bands' para índices con paleta
                if 'palette' in vis_params_export_dict and 'bands' not in vis_params_export_dict and image_to_export_orig.bandNames().getInfo() == ['nd_index']:
                    vis_params_export_dict['bands'] = ['nd_index']
                image_to_export = image_to_export_orig.visualize(**vis_params_export_dict)

        export_params: Dict[str, Any] = {'image': image_to_export, 'description': description.replace(" ", "_"), 'folder': drive_folder, 'scale': scale, 'region': aoi_for_export.bounds().getInfo()['coordinates'], 'fileFormat': 'GeoTIFF', 'maxPixels': 1e13}
        if crs: export_params['crs'] = crs
        task = ee.batch.Export.image.toDrive(**export_params); task.start()
        return f"Exportación a Drive iniciada: '{description}', Tarea ID: {task.id}. VisParams aplicados: {vis_params_export_dict if vis_params_export_dict else 'Ninguno (datos crudos)'}"
    except Exception as e: return f"Error al exportar a Drive '{image_cache_id}': {str(e)}"

def complete_task(reasoning: str, final_message_to_user: str) -> str:
    """Indica que el agente ha completado la tarea del usuario y proporciona un mensaje final."""
    console.log(f"[blue]Tool: complete_task[/blue] - Reasoning: {reasoning}")
    # El mensaje final ya lo habrá generado el LLM como parte de los args.
    # Esta función principalmente señala la finalización.
    return f"Tarea marcada como completada por el LLM. Mensaje para el usuario: {final_message_to_user}"

# ---------------------------------------------------
# LISTA DE HERRAMIENTAS Y PROMPT DEL AGENTE
# ---------------------------------------------------
tools_definitions = [
    InitializeGeeArgs, DefineAoiFromGeoJSONArgs, GetImageCollectionArgs,
    CalculateNdIndexArgs, GenerateRgbCompositeArgs, GetAndSaveThumbnailArgs,
    ExportImageToDriveArgs, CompleteTaskArgs # CompleteTaskArgs añadida
]
tools = [pydantic_function_tool(tool_def) for tool_def in tools_definitions]

AGENT_PROMPT = """<purpose>
    Eres un agente experto en cartografía y Google Earth Engine (GEE). Tu objetivo es ayudar a los usuarios a generar imágenes geoespaciales (NDBI, RGB Color Verdadero) basadas en sus descripciones.
    Debes interpretar la solicitud del usuario, utilizar las herramientas GEE proporcionadas para procesar los datos y luego exportar los resultados o generar miniaturas.
    Cuando hayas completado todos los pasos de la solicitud del usuario, DEBES llamar a `CompleteTaskArgs` con un resumen final para el usuario.
</purpose>
<instructions>
    <instruction>Comienza siempre llamando a `InitializeGeeArgs`.</instruction>
    <instruction>Si `InitializeGeeArgs` falla, informa al usuario el error exacto y cómo solucionarlo (ej. `earthengine authenticate` o verificar proyecto '{GEE_PROJECT_ID}'). NO llames a otras herramientas GEE. Tu siguiente respuesta debe ser solo para el usuario. El agente finalizará.</instruction>
    <instruction>Para definir el AOI, usa `DefineAoiFromGeoJSONArgs`. Genera un GeoJSON válido. Si el usuario especifica una ciudad o una región amplia, el GeoJSON debe cubrir un área representativa de esa entidad geográfica (por ejemplo, un polígono de al menos 5km x 5km o un radio de varios kilómetros si es un punto bufferizado) para asegurar un análisis visual útil y evitar áreas demasiado pequeñas. No definas un polígono de solo unos cientos de metros si se nombra una ciudad. Guarda con `aoi_id` (ej. 'current_aoi').</instruction>
    <instruction>Usa `GetImageCollectionArgs` para obtener imágenes (ej. Sentinel-2: 'COPERNICUS/S2_SR_HARMONIZED'). Filtra por fechas, `aoi_id`, y nubes. Guarda con `collection_cache_id`.</instruction>
    <instruction>Para NDBI (Sentinel-2: B11, B8; Landsat 8: SR_B6, SR_B5), usa `CalculateNdIndexArgs`. Guarda con `output_image_cache_id`. La imagen resultante tendrá una banda llamada 'nd_index'.</instruction>
    <instruction>Para RGB (Sentinel-2: B4,B3,B2; Landsat 8: SR_B4,SR_B3,SR_B2), usa `GenerateRgbCompositeArgs`. Proporciona `vis_params_rgb`. Guarda con `output_image_cache_id`.</instruction>
    <instruction>Para miniaturas, usa `GetAndSaveThumbnailArgs`. Especifica `image_cache_id` y `vis_params`. Para índices de una sola banda (como NDVI o NDBI, que se guardan con el nombre de banda 'nd_index'), usa `vis_params` como `{"min": -0.3, "max": 0.5, "palette": ["0000FF", "FFFFFF", "A52A2A"], "bands": ["nd_index"]}`. Para RGB, usa algo como `{"min": 0.0, "max": 0.3, "bands": ["B4","B3","B2"]}` (asegúrate que las bandas RGB coincidan con las usadas en `GenerateRgbCompositeArgs`). Guarda en '{THUMBNAIL_DIR}'. El `local_filename_prefix` debe ser solo un nombre de archivo, sin ruta de directorio.</instruction>
    <instruction>Para exportar a Drive, usa `ExportImageToDriveArgs`. `description` es nombre de archivo. `drive_folder` (def: '{DEFAULT_DRIVE_FOLDER}'). `scale` en metros (para Sentinel-2, usa 10 para la resolución nativa de bandas como NDVI o RGB; para Landsat, 30 es apropiado).
        Si el objetivo es una imagen visual coloreada para el índice (similar a la miniatura), DEBES proporcionar `vis_params_for_export` con la paleta y banda adecuadas (ej. para NDVI: `{"min": -0.3, "max": 0.5, "palette": ["0000FF", "FFFFFF", "A52A2A"], "bands": ["nd_index"]}`).
        Si explícitamente se piden datos crudos del índice (para análisis numérico, lo que resultará en una imagen en escala de grises por defecto), entonces omite `vis_params_for_export`.
        Para exportar una imagen RGB visual, también usa `vis_params_for_export` (ej. `{"min": 0.0, "max": 0.3, "bands": ["B4","B3","B2"]}`).</instruction>
    <instruction>Proporciona razonamiento conciso para cada llamada. Usa IDs de caché para referenciar objetos.</instruction>
    <instruction>Una vez que todas las acciones solicitadas (ej. cálculo de índice, miniatura, exportación) se hayan completado exitosamente, llama a la herramienta `CompleteTaskArgs` para finalizar la interacción, proporcionando un `final_message_to_user` que resuma lo que se hizo y dónde encontrar los resultados.</instruction>
</instructions>
<user-request>
    {{user_request}}
</user-request>
"""

# ---------------------------------------------------
# FUNCIÓN PRINCIPAL (main)
# ---------------------------------------------------
def main():
    global OPENAI_API_KEY, DEFAULT_DRIVE_FOLDER, GEE_PROJECT_ID
    load_dotenv()
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    if not OPENAI_API_KEY:
        console.print("[red]Error: OPENAI_API_KEY no configurada.[/red]"); sys.exit(1)
    
    env_gee_project_id = os.getenv("GEE_PROJECT_ID")
    if env_gee_project_id: GEE_PROJECT_ID = env_gee_project_id
    
    parser = argparse.ArgumentParser(description="Agente Cartográfico GEE")
    parser.add_argument("-p", "--prompt", required=True, help="Petición del usuario.")
    parser.add_argument("-m", "--model", type=str, default="gpt-4o-mini", help="Modelo OpenAI.")
    parser.add_argument("-c", "--compute", type=int, default=10, help="Máx. iteraciones.")
    parser.add_argument("--drive-folder", type=str, default=DEFAULT_DRIVE_FOLDER, help=f"Carpeta Drive (def: {DEFAULT_DRIVE_FOLDER}).")
    args = parser.parse_args()

    if args.drive_folder != DEFAULT_DRIVE_FOLDER:
        console.print(f"[info]Usando carpeta de Drive: {args.drive_folder}[/info]")

    client = openai.OpenAI(api_key=OPENAI_API_KEY)
    if not os.path.exists(THUMBNAIL_DIR):
        try: os.makedirs(THUMBNAIL_DIR); console.print(f"Directorio miniaturas creado: {THUMBNAIL_DIR}")
        except OSError as e: console.print(f"[red]Error creando dir miniaturas {THUMBNAIL_DIR}: {e}[/red]")

    final_agent_prompt = AGENT_PROMPT.replace("{{user_request}}", args.prompt)\
                                     .replace("{DEFAULT_DRIVE_FOLDER}", args.drive_folder)\
                                     .replace("{THUMBNAIL_DIR}", THUMBNAIL_DIR)\
                                     .replace("{GEE_PROJECT_ID}", GEE_PROJECT_ID)
                                     
    messages: List[Dict[str, Any]] = [{"role": "user", "content": final_agent_prompt}]

    console.rule(f"[bold green]INICIO AGENTE GEE ({args.model})[/bold green]")
    console.print(f"Prompt: [cyan]{args.prompt}[/cyan]")
    console.print(f"Drive Folder: [yellow]{args.drive_folder}[/yellow], GEE Project: [yellow]{GEE_PROJECT_ID}[/yellow]")

    tool_map = {
        "InitializeGeeArgs": (InitializeGeeArgs, initialize_gee),
        "DefineAoiFromGeoJSONArgs": (DefineAoiFromGeoJSONArgs, define_aoi_from_geojson),
        "GetImageCollectionArgs": (GetImageCollectionArgs, get_image_collection),
        "CalculateNdIndexArgs": (CalculateNdIndexArgs, calculate_nd_index),
        "GenerateRgbCompositeArgs": (GenerateRgbCompositeArgs, generate_rgb_composite),
        "GetAndSaveThumbnailArgs": (GetAndSaveThumbnailArgs, get_and_save_thumbnail),
        "ExportImageToDriveArgs": (ExportImageToDriveArgs, export_image_to_drive),
        "CompleteTaskArgs": (CompleteTaskArgs, complete_task),
    }

    for i in range(args.compute):
        console.rule(f"[yellow]CICLO {i + 1}/{args.compute}[/yellow]")
        try:
            response = client.chat.completions.create(model=args.model, messages=messages, tools=tools, tool_choice="auto") # type: ignore
            message_obj = response.choices[0].message 

            if message_obj.tool_calls:
                messages.append(message_obj.model_dump()) # Guardar solicitud de herramienta como dict
                
                task_completed_by_tool_call = False
                for tool_call in message_obj.tool_calls:
                    func_name = tool_call.function.name
                    func_args_str = tool_call.function.arguments
                    tool_call_id = tool_call.id
                    console.print(Panel(f"[blue]LLM -> ToolCall[/blue]\nTool: {func_name}\nArgs: {func_args_str}", expand=False))

                    if func_name in tool_map:
                        pydantic_class, function_to_call = tool_map[func_name]
                        try:
                            parsed_args_dict = json.loads(func_args_str)
                            if func_name == "ExportImageToDriveArgs" and 'drive_folder' not in parsed_args_dict:
                                parsed_args_dict['drive_folder'] = args.drive_folder
                            
                            # Para GenerateRgbCompositeArgs, GetAndSaveThumbnailArgs y ExportImageToDriveArgs,
                            # los vis_params pueden venir como dict y necesitan ser pasados como tal
                            # si la función los espera así para validación interna de VisParamsBase.
                            if func_name in ["GenerateRgbCompositeArgs", "GetAndSaveThumbnailArgs", "ExportImageToDriveArgs"]:
                                # La validación principal de los args de la herramienta se hace con pydantic_class.model_validate.
                                # El campo vis_params (o vis_params_rgb, vis_params_for_export) dentro de esos args
                                # será validado como VisParamsBase por Pydantic.
                                # La función herramienta recibirá el objeto Pydantic y lo usará.
                                parsed_args_obj = pydantic_class.model_validate(parsed_args_dict)
                                tool_result = function_to_call(**parsed_args_obj.model_dump())
                            else:
                                parsed_args = pydantic_class.model_validate(parsed_args_dict)
                                tool_result = function_to_call(**parsed_args.model_dump())


                            if func_name == "CompleteTaskArgs":
                                # El mensaje final ya está en parsed_args.final_message_to_user
                                final_user_message = json.loads(func_args_str).get("final_message_to_user", "Tarea completada.")
                                console.print(Panel(f"[magenta]Respuesta Final (vía CompleteTaskArgs):[/magenta]\n{final_user_message}", title="LLM -> User (Task Completed)"))
                                console.print("[bold green]Agente finalizado por CompleteTaskArgs.[/bold green]")
                                task_completed_by_tool_call = True
                                break 

                        except ValidationError as ve: tool_result = f"Error validación args para {func_name}: {ve}"
                        except Exception as e: tool_result = f"Error ejecutando {func_name}: {e}"
                    else: tool_result = f"Error: Herramienta desconocida '{func_name}'."
                    
                    if task_completed_by_tool_call: break 

                    console.print(Panel(f"[green]ToolCall -> LLM[/green]\nTool: {func_name}\nResultado: {tool_result}", expand=False))
                    messages.append({"role": "tool", "tool_call_id": tool_call_id, "name": func_name, "content": tool_result})
                
                if task_completed_by_tool_call: break 

            elif message_obj.content:
                is_reply_to_failed_init = False
                if len(messages) > 1 and messages[-1].get("role") == "tool" and messages[-1].get("name") == "InitializeGeeArgs":
                    if "Fallo al inicializar Google Earth Engine" in str(messages[-1].get("content")):
                        is_reply_to_failed_init = True
                
                messages.append(message_obj.model_dump()) 
                console.print(Panel(f"[magenta]LLM -> User[/magenta]\n{message_obj.content}", expand=False))

                if is_reply_to_failed_init:
                    console.print("[bold red]Fallo inicialización GEE reportado. Agente se detendrá.[/bold red]"); break
                
                if any(k in message_obj.content.lower() for k in ["finalizado", "completado", "tarea completada", "he generado exitosamente", "exportación iniciada"]):
                    if "miniatura" in message_obj.content.lower() and "exportación" in message_obj.content.lower(): 
                         console.print("[bold green]Agente finalizado por respuesta del asistente (texto).[/bold green]"); break
            else:
                messages.append(message_obj.model_dump()) 
                console.print("[yellow]Respuesta LLM sin tool_calls ni contenido. Finalizando.[/yellow]"); break
        
        except Exception as e:
            console.print(f"[bold red]Error crítico en ciclo del agente: {e}[/bold red]"); break
    else: 
        console.print("[yellow]Límite de iteraciones alcanzado.[/yellow]")

    console.print(f"Objetos GEE en caché: {list(GEE_ASSETS_CACHE.keys())}")
    console.rule("[bold red]FIN AGENTE GEE[/bold red]")

if __name__ == "__main__":
    main()
