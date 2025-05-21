# /// script
# dependencies = [
#   "openai>=1.63.0",
#   "rich>=13.7.0",
#   "pydantic>=2.0.0",
#   "pandas>=2.0.0",
#   "openpyxl>=3.1.0",
#   "python-dotenv>=0.21.0"
# ]
# ///

"""
DESCRIPCIÓN DEL SCRIPT
----------------------
Este script ejemplifica un "mini-agente" que explora un archivo Excel (posiblemente desestructurado)
para responder a la petición de un usuario. Usa la API de OpenAI con "function calling" y, de forma 
similar a un agente para DuckDB, define una serie de herramientas (list_sheets, detect_data_blocks, etc.)
que el modelo puede invocar para inspeccionar y procesar los datos.

PUNTOS CLAVE:
- Cada herramienta está definida con un modelo Pydantic (ej. ListSheetsArgs, etc.).
- El script usa la nueva API de "openai.chat.completions.create(...)".
- Es importante incluir un campo "tool_call_id" en los mensajes con role="tool" para enlazar la
  respuesta de la herramienta con la llamada que hizo el modelo (role="assistant" con "tool_calls").
- Además, el "id" usado en "tool_calls" no debe exceder 40 caracteres.
- Carga variables de entorno desde un archivo .env usando python-dotenv.

EJEMPLO DE EJECUCIÓN:
    uv run sfa_excel_openai.py \
        -d data.xlsx \
        -p "Qué información contiene la planilla" \
        -c 10

Parámetros:
  -d, --db: Ruta al archivo Excel.
  -p, --prompt: Petición del usuario.
  -c, --compute: Máx. de iteraciones del agente antes de detenerse.
  -m, --model: Modelo de OpenAI a utilizar (ej. gpt-4o-mini).

DEPENDENCIAS:
    - openai (>=1.63.0)
    - rich (>=13.7.0)
    - pydantic (>=2.0.0)
    - pandas (>=2.0.0)
    - openpyxl (>=3.1.0)
    - python-dotenv (>=0.21.0)

LIMITACIONES:
- La detección de bloques y cabeceras es heurística y puede no funcionar en todos los Excel.
- La efectividad de las consultas depende de la capacidad del LLM para generar expresiones
  válidas para `DataFrame.query()` de Pandas.

Autor: (Tu nombre o tu equipo)
"""

import os
import sys
import json
import argparse
import uuid  # Para generar IDs únicos cortos en tool_calls
from typing import List, Dict, Any, Optional

from dotenv import load_dotenv
import pandas as pd
import openai
from pydantic import BaseModel, Field, ValidationError
from openai import pydantic_function_tool
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

# ---------------------------------------------------
# CONFIGURACIÓN DE CONSOLA Y VARIABLES GLOBALES
# ---------------------------------------------------
console = Console()
EXCEL_PATH = None  # Se setea en main(), a partir del argumento --db
DETECTED_BLOCKS_CACHE: Dict[str, Dict[str, Any]] = {}

# ---------------------------------------------------
# MODELOS Pydantic (definición de args de cada tool)
# ---------------------------------------------------

class ListSheetsArgs(BaseModel):
    reasoning: str = Field(..., description="Por qué listamos las hojas de Excel.")

class DetectDataBlocksArgs(BaseModel):
    reasoning: str = Field(..., description="Por qué detectamos bloques/regiones de datos en la hoja.")
    sheet_name: str = Field(..., description="Nombre de la hoja de Excel para inspeccionar.")

class DescribeBlockArgs(BaseModel):
    reasoning: str = Field(..., description="Motivo para describir la estructura de este bloque.")
    block_id: str = Field(..., description="Identificador del bloque a describir (ej. 'block_0_Sheet1_0_10_h0').")

class SampleBlockArgs(BaseModel):
    reasoning: str = Field(..., description="Motivo para muestrear el bloque.")
    block_id: str = Field(..., description="El bloque a muestrear (ej. 'block_0_Sheet1_0_10_h0').")
    row_sample_size: int = Field(default=3, description="Número de filas a mostrar (3-5).")

class RunTestExcelQueryArgs(BaseModel):
    reasoning: str = Field(..., description="Por qué estamos probando esta consulta o transformación.")
    block_id: str = Field(..., description="El bloque sobre el que se ejecuta la consulta (ej. 'block_0_Sheet1_0_10_h0').")
    query_expression: str = Field(..., description="La expresión de consulta para `DataFrame.query()` de Pandas (ej. 'Age > 30 and City == \"New York\"'). Las columnas con espacios o caracteres especiales deben ir entre acentos graves (backticks), ej. '`Column Name` > 10'.")

class RunFinalExcelQueryArgs(BaseModel):
    reasoning: str = Field(..., description="Explicación final de cómo esta consulta responde al pedido del usuario.")
    block_id: str = Field(..., description="El bloque sobre el que se ejecuta la operación final (ej. 'block_0_Sheet1_0_10_h0').")
    query_expression: str = Field(..., description="La instrucción/consulta final ya validada para `DataFrame.query()`. Las columnas con espacios o caracteres especiales deben ir entre acentos graves (backticks).")

# ---------------------------------------------------
# FUNCIONES AUXILIARES PARA MANEJO DE BLOQUES
# ---------------------------------------------------

def _get_block_info(block_id: str) -> Dict[str, Any]:
    """Recupera la información de un bloque desde el caché."""
    if block_id not in DETECTED_BLOCKS_CACHE:
        raise ValueError(f"Block ID '{block_id}' no encontrado en el caché. Asegúrate de llamar a 'detect_data_blocks' primero para la hoja correspondiente.")
    return DETECTED_BLOCKS_CACHE[block_id]

def _read_block_to_dataframe(block_id: str, include_data: bool = True) -> pd.DataFrame:
    """Lee un bloque específico del Excel a un DataFrame de Pandas."""
    info = _get_block_info(block_id)
    sheet_name = info["sheet_name"]
    start_row_abs = info["start_row_abs"]
    end_row_abs = info["end_row_abs"]
    header_row_in_block_idx = info.get("header_row_in_block_idx") # Puede ser None

    # Determinar cuántas filas leer del Excel.
    # Si no incluimos datos, solo leemos hasta la cabecera (si existe) o una fila para inferir columnas.
    nrows_to_read_from_excel = (end_row_abs - start_row_abs + 1)
    if not include_data and header_row_in_block_idx is not None:
        nrows_to_read_from_excel = header_row_in_block_idx + 1
    elif not include_data: # No hay cabecera clara y no queremos datos, leer solo 1 fila para estructura
        nrows_to_read_from_excel = 1


    try:
        df_section = pd.read_excel(
            EXCEL_PATH,
            sheet_name=sheet_name,
            header=None, # Leemos sin cabecera inicialmente
            skiprows=start_row_abs,
            nrows=nrows_to_read_from_excel
        )

        if df_section.empty:
            return pd.DataFrame(columns=info.get("columns", []))

        # Establecer columnas y datos
        if header_row_in_block_idx is not None and header_row_in_block_idx < len(df_section):
            # Cabecera detectada
            columns = df_section.iloc[header_row_in_block_idx].astype(str).tolist()
            if not include_data:
                return pd.DataFrame(columns=columns) # Solo estructura
            
            # Tomar datos desde la fila siguiente a la cabecera
            data_df = df_section.iloc[header_row_in_block_idx + 1:].copy()
            data_df.columns = columns
            data_df = data_df.reset_index(drop=True)
        else:
            # No hay cabecera detectada o está fuera de rango (ej. bloque de una sola fila sin cabecera)
            # Usar columnas genéricas o las almacenadas en caché si existen
            columns = info.get("columns")
            if not columns or len(columns) != df_section.shape[1]: # Si no hay columnas o no coinciden
                 columns = [f"col_{i}" for i in range(df_section.shape[1])]

            if not include_data:
                return pd.DataFrame(columns=columns) # Solo estructura
            
            data_df = df_section.copy()
            data_df.columns = columns
            data_df = data_df.reset_index(drop=True)
        
        return data_df

    except Exception as e:
        console.log(f"[red]Error leyendo el bloque '{block_id}' ({sheet_name}!{start_row_abs}:{end_row_abs}): {e}[/red]")
        # Devolver un DataFrame vacío con las columnas esperadas si es posible
        return pd.DataFrame(columns=info.get("columns", []))


# ---------------------------------------------------
# FUNCIONES HERRAMIENTA (tools)
# ---------------------------------------------------

def list_sheets(reasoning: str) -> List[str]:
    """Devuelve la lista de hojas en el archivo Excel."""
    console.log(f"[blue]List Sheets Tool[/blue] - Reasoning: {reasoning}")
    try:
        xls = pd.ExcelFile(EXCEL_PATH)
        return xls.sheet_names
    except Exception as e:
        console.log(f"[red]Error listing sheets: {str(e)}[/red]")
        return [f"Error al listar hojas: {str(e)}"]

def detect_data_blocks(reasoning: str, sheet_name: str) -> List[str]:
    """Detecta bloques de datos en la hoja y los almacena en caché."""
    console.log(f"[blue]Detect Data Blocks Tool[/blue] - Sheet: {sheet_name} - Reasoning: {reasoning}")
    global DETECTED_BLOCKS_CACHE
    block_ids_found = []

    try:
        df_full_sheet = pd.read_excel(EXCEL_PATH, sheet_name=sheet_name, header=None)
        if df_full_sheet.empty:
            return ["La hoja está vacía o no se encontraron datos."]

        in_block = False
        current_block_start_row = -1
        block_counter = len([k for k in DETECTED_BLOCKS_CACHE.keys() if f"_{sheet_name}_" in k]) # Contador por hoja

        for i, row in df_full_sheet.iterrows():
            # Considerar una fila vacía si todos sus valores son NaN o None
            is_empty_row = row.isnull().all()
            
            if not is_empty_row and not in_block: # Inicio de un nuevo bloque
                in_block = True
                current_block_start_row = i
            elif is_empty_row and in_block: # Fin del bloque actual
                in_block = False
                block_end_row = i - 1
                
                if block_end_row < current_block_start_row: # Bloque inválido (ej. múltiples filas vacías seguidas)
                    continue

                # Heurística simple para cabecera: la primera fila del bloque.
                header_row_in_block_idx = 0 
                block_df_preview = df_full_sheet.iloc[current_block_start_row : block_end_row + 1]
                tentative_columns = block_df_preview.iloc[header_row_in_block_idx].astype(str).tolist()

                block_id = f"block_{block_counter}_{sheet_name}_{current_block_start_row}_{block_end_row}_h{header_row_in_block_idx}"
                DETECTED_BLOCKS_CACHE[block_id] = {
                    "sheet_name": sheet_name,
                    "start_row_abs": current_block_start_row, # Fila absoluta en la hoja (0-indexed)
                    "end_row_abs": block_end_row,             # Fila absoluta en la hoja (0-indexed)
                    "header_row_in_block_idx": header_row_in_block_idx, # Índice relativo al inicio del bloque (0 para la primera fila)
                    "columns": tentative_columns,
                    "num_data_rows": max(0, (block_end_row - current_block_start_row) - header_row_in_block_idx)
                }
                block_ids_found.append(block_id)
                block_counter += 1
        
        # Si el último bloque llega hasta el final de la hoja
        if in_block:
            block_end_row = df_full_sheet.shape[0] - 1
            if block_end_row >= current_block_start_row:
                header_row_in_block_idx = 0
                block_df_preview = df_full_sheet.iloc[current_block_start_row : block_end_row + 1]
                tentative_columns = block_df_preview.iloc[header_row_in_block_idx].astype(str).tolist()

                block_id = f"block_{block_counter}_{sheet_name}_{current_block_start_row}_{block_end_row}_h{header_row_in_block_idx}"
                DETECTED_BLOCKS_CACHE[block_id] = {
                    "sheet_name": sheet_name,
                    "start_row_abs": current_block_start_row,
                    "end_row_abs": block_end_row,
                    "header_row_in_block_idx": header_row_in_block_idx,
                    "columns": tentative_columns,
                    "num_data_rows": max(0, (block_end_row - current_block_start_row) - header_row_in_block_idx)
                }
                block_ids_found.append(block_id)

        return block_ids_found if block_ids_found else ["No se detectaron bloques de datos contiguos en la hoja."]
    except Exception as e:
        console.log(f"[red]Error detectando bloques de datos en '{sheet_name}': {str(e)}[/red]")
        return [f"Error al detectar bloques: {str(e)}"]

def describe_block(reasoning: str, block_id: str) -> str:
    """Describe un bloque (columnas, filas, etc.)."""
    console.log(f"[blue]Describe Block Tool[/blue] - Block: {block_id} - Reasoning: {reasoning}")
    try:
        info = _get_block_info(block_id)        
        description = (
            f"Block ID: {block_id}\n"
            f"Sheet: {info['sheet_name']}\n"
            f"Rango de filas absolutas en la hoja (0-indexed): {info['start_row_abs']} a {info['end_row_abs']}\n"
            f"Fila de cabecera detectada (índice 0 dentro del bloque): {info['header_row_in_block_idx']}\n"
            f"Número estimado de filas de datos (excluyendo cabecera): {info['num_data_rows']}\n"
            f"Columnas detectadas: {info['columns']}"
        )
        return description
    except Exception as e:
        console.log(f"[red]Error describiendo el bloque '{block_id}': {str(e)}[/red]")
        return f"Error al describir el bloque: {str(e)}"

def sample_block(reasoning: str, block_id: str, row_sample_size: int = 3) -> str:
    """Retorna varias filas de ejemplo del bloque."""
    console.log(f"[blue]Sample Block Tool[/blue] - Block: {block_id}, Rows: {row_sample_size} - Reasoning: {reasoning}")
    try:
        df_data = _read_block_to_dataframe(block_id, include_data=True)
        if df_data.empty:
            return "El bloque está vacío o no pudo ser leído correctamente."
        
        sample_df = df_data.head(row_sample_size)
        return sample_df.to_json(orient="records", indent=2, force_ascii=False)
    except Exception as e:
        console.log(f"[red]Error muestreando el bloque '{block_id}': {str(e)}[/red]")
        return f"Error al muestrear el bloque: {str(e)}"

def run_test_excel_query(reasoning: str, block_id: str, query_expression: str) -> str:
    """Ejecuta una consulta de prueba sobre el bloque y devuelve un resumen."""
    console.log(f"[blue]Test Query Tool[/blue] - Block: {block_id} - Reasoning: {reasoning}")
    console.log(f"[dim]Query Expression: {query_expression}[/dim]")
    try:
        df_data = _read_block_to_dataframe(block_id, include_data=True)
        if df_data.empty:
            return "No se puede ejecutar la consulta en un bloque vacío."

        # Los nombres de columna en df_data ya son los correctos (leídos de la cabecera o genéricos)
        # El LLM debe generar query_expression usando estos nombres, encerrando en `backticks` si es necesario.
        
        result_df = df_data.query(query_expression)
        return f"La consulta de prueba en el bloque {block_id} con la expresión '{query_expression}' resultó en {len(result_df)} filas."
    except Exception as e:
        console.log(f"[red]Error ejecutando consulta de prueba en '{block_id}': {str(e)}[/red]")
        info = _get_block_info(block_id) # Para dar más contexto en el error
        available_columns = info.get('columns', 'No disponibles')
        error_message = (
            f"Error: {str(e)}. "
            f"Verifica que los nombres de columna en la consulta existan en el bloque y estén correctamente formateados. "
            f"Columnas disponibles en el bloque '{block_id}': {available_columns}. "
            f"Recuerda encerrar los nombres de columna con espacios o caracteres especiales entre acentos graves (backticks), ej., `Nombre Columna`."
        )
        return error_message

def run_final_excel_query(reasoning: str, block_id: str, query_expression: str) -> str:
    """Ejecuta la consulta final y muestra resultados al usuario."""
    console.log(
        Panel(
            f"[green]Final Query Tool[/green]\nReasoning: {reasoning}\nBlock: {block_id}\nQuery: {query_expression}"
        )
    )
    try:
        df_data = _read_block_to_dataframe(block_id, include_data=True)
        if df_data.empty:
            return "No se puede ejecutar la consulta en un bloque vacío. No hay datos para mostrar."

        result_df = df_data.query(query_expression)

        if result_df.empty:
            return "La consulta se ejecutó correctamente, pero ninguna fila coincidió con los criterios."

        # Para la salida, mostramos una tabla si es pequeña, o JSON si es grande/ancho
        if len(result_df) <= 20 and result_df.shape[1] <= 10: # Umbral para mostrar como tabla
            table = Table(title=f"Resultados para: {query_expression} (Bloque: {block_id})")
            for col in result_df.columns:
                table.add_column(str(col)) # Asegurar que el nombre de la columna sea string
            for _, row in result_df.iterrows():
                table.add_row(*[str(item) for item in row]) # Asegurar que cada item sea string
            
            with console.capture() as capture:
                console.print(table)
            return capture.get()
        else:
            if len(result_df) > 50: # Limitar el tamaño del JSON devuelto
                 return f"La consulta resultó en {len(result_df)} filas. Mostrando las primeras 50 en formato JSON:\n{result_df.head(50).to_json(orient='records', indent=2, force_ascii=False)}"
            return result_df.to_json(orient="records", indent=2, force_ascii=False)

    except Exception as e:
        console.log(f"[red]Error ejecutando consulta final: {str(e)}[/red]")
        info = _get_block_info(block_id)
        available_columns = info.get('columns', 'No disponibles')
        error_message = (
            f"Error: {str(e)}. "
            f"Verifica que los nombres de columna en la consulta existan en el bloque y estén correctamente formateados. "
            f"Columnas disponibles en el bloque '{block_id}': {available_columns}. "
            f"Recuerda encerrar los nombres de columna con espacios o caracteres especiales entre acentos graves (backticks), ej., `Nombre Columna`."
        )
        return error_message

# ---------------------------------------------------
# CREACIÓN DE LA LISTA DE TOOLS (usando pydantic_function_tool)
# ---------------------------------------------------
tools_definitions = [
    ListSheetsArgs,
    DetectDataBlocksArgs,
    DescribeBlockArgs,
    SampleBlockArgs,
    RunTestExcelQueryArgs,
    RunFinalExcelQueryArgs,
]
# Convertimos las clases Pydantic a herramientas compatibles con OpenAI
tools = [pydantic_function_tool(tool_def) for tool_def in tools_definitions]


# ---------------------------------------------------
# PLANTILLA DE PROMPT
# ---------------------------------------------------
AGENT_PROMPT = """<purpose>
    Eres un experto analista de datos especializado en leer y procesar datos de archivos Excel.
    Tu tarea es explorar el archivo Excel proporcionado, identificar bloques de datos relevantes,
    y extraer o transformar datos para satisfacer la petición del usuario de manera precisa.
</purpose>

<instructions>
    <instruction>Comienza siempre llamando a `ListSheetsArgs` para entender qué hojas contiene el archivo Excel.</instruction>
    <instruction>Para la hoja relevante, usa `DetectDataBlocksArgs` para identificar las tablas o regiones de datos. Esta herramienta te devolverá IDs para cada bloque detectado (ej. 'block_0_Sheet1_0_10_h0').</instruction>
    <instruction>Utiliza `DescribeBlockArgs` con un `block_id` para entender la estructura de un bloque específico (columnas, número de filas). Presta atención a los nombres exactos de las columnas devueltas.</instruction>
    <instruction>Si necesitas ver ejemplos de datos, usa `SampleBlockArgs` con un `block_id`.</instruction>
    <instruction>Cuando necesites filtrar, seleccionar o transformar datos, formula una `query_expression` para la herramienta `RunTestExcelQueryArgs`.
        La `query_expression` DEBE ser una cadena válida para el método `DataFrame.query()` de Pandas.
        Ejemplos de `query_expression`:
        - `'Age > 30'`
        - `'City == "New York"'` (las cadenas de texto dentro de la query deben ir entre comillas simples o dobles)
        - `'Score >= 75 and Status == "active"'`
        - `'Name.str.contains("John")'` (para búsquedas de subcadenas, asumiendo que la columna 'Name' es de tipo string)
        - Si un nombre de columna (como te lo devuelve `DescribeBlockArgs`) contiene espacios o caracteres especiales (ej. 'Order Date', 'Product ID', '% Change'), DEBES encerrarlo entre acentos graves (backticks) en tu `query_expression`. Ejemplo: '`Order Date` > "2023-01-01"' o '`Product ID` == 123' o '`% Change` < 0'.
        Utiliza los nombres de columna EXACTOS que te proporcionó `DescribeBlockArgs`.
    </instruction>
    <instruction>Revisa el resultado de `RunTestExcelQueryArgs`. Si la consulta es correcta y produce el resultado esperado (ej. número de filas encontradas), puedes usar la misma `query_expression` con `RunFinalExcelQueryArgs` para presentar los datos finales al usuario.</instruction>
    <instruction>Si una consulta de prueba falla o no da el resultado esperado, analiza el mensaje de error (que puede incluir las columnas disponibles), revisa la descripción del bloque y los nombres de las columnas, y prueba con una `query_expression` corregida en `RunTestExcelQueryArgs` nuevamente.</instruction>
    <instruction>Solo llama a `RunFinalExcelQueryArgs` cuando estés seguro de que la consulta es correcta y responde a la petición del usuario.</instruction>
    <instruction>Siempre incluye un campo 'reasoning' conciso explicando por qué llamas a cada herramienta y qué esperas obtener.</instruction>
</instructions>

<user-request>
    {{user_request}}
</user-request>
"""

# ---------------------------------------------------
# FUNCIÓN PRINCIPAL (main)
# ---------------------------------------------------
def main():
    load_dotenv()  # Carga variables de entorno desde .env al inicio

    parser = argparse.ArgumentParser(description="Mini-Agente para Excel usando OpenAI API")
    parser.add_argument("-d", "--db", required=True, help="Path al archivo Excel (.xls, .xlsx, etc.)")
    parser.add_argument("-p", "--prompt", required=True, help="Petición o pregunta del usuario")
    parser.add_argument("-c", "--compute", type=int, default=15, help="Máx. iteraciones de razonamiento") # Aumentado por defecto
    parser.add_argument("-m", "--model", type=str, default="gpt-4o-mini", help="Modelo de OpenAI a utilizar (ej. gpt-4o-mini, gpt-4-turbo)")
    args = parser.parse_args()

    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    if not OPENAI_API_KEY:
        console.print("[red]Error: OPENAI_API_KEY no está configurada en variables de entorno ni en el archivo .env.[/red]")
        sys.exit(1)

    client = openai.OpenAI(api_key=OPENAI_API_KEY)

    global EXCEL_PATH
    EXCEL_PATH = args.db
    if not os.path.exists(EXCEL_PATH):
        console.print(f"[red]Error: El archivo Excel '{EXCEL_PATH}' no fue encontrado.[/red]")
        sys.exit(1)


    completed_prompt = AGENT_PROMPT.replace("{{user_request}}", args.prompt)
    messages = [{"role": "user", "content": completed_prompt}]

    console.rule("[bold green]INICIO DEL AGENTE[/bold green]")
    console.print(f"Archivo Excel: [yellow]{args.db}[/yellow]")
    console.print(f"Prompt del usuario: [cyan]{args.prompt}[/cyan]")
    console.print(f"Modelo OpenAI: [yellow]{args.model}[/yellow]")
    console.print(f"Máx. Iteraciones: {args.compute}")

    compute_iterations = 0
    while True:
        compute_iterations += 1
        console.rule(f"[yellow]AGENT LOOP {compute_iterations}/{args.compute}[/yellow]")

        if compute_iterations > args.compute:
            console.print("[red]Se alcanzó el límite de iteraciones sin 'RunFinalExcelQueryArgs'.[/red]")
            break

        try:
            response = client.chat.completions.create(
                model=args.model,
                messages=messages,
                tools=tools, # MODIFICADO: Pasar directamente la lista de diccionarios de herramientas
                tool_choice="auto" 
            )

            if not response.choices:
                console.print("[red]La respuesta no contiene 'choices'. Finalizando.[/red]")
                break

            message = response.choices[0].message
            messages.append(message) 

            if message.tool_calls:
                for tool_call in message.tool_calls:
                    func_name_from_api = tool_call.function.name # Este es el nombre de la clase Pydantic
                    func_args_str = tool_call.function.arguments
                    tool_call_id = tool_call.id

                    console.print(
                        f"[blue]Func Call => {func_name_from_api}({func_args_str}) | tool_call_id={tool_call_id}[/blue]"
                    )

                    result_content = None # Contenido para el mensaje 'tool'
                    
                    # Mapeo de nombres de clases Pydantic a (ClasePydantic, función_real)
                    tool_map = {
                        "ListSheetsArgs": (ListSheetsArgs, list_sheets),
                        "DetectDataBlocksArgs": (DetectDataBlocksArgs, detect_data_blocks),
                        "DescribeBlockArgs": (DescribeBlockArgs, describe_block),
                        "SampleBlockArgs": (SampleBlockArgs, sample_block),
                        "RunTestExcelQueryArgs": (RunTestExcelQueryArgs, run_test_excel_query),
                        "RunFinalExcelQueryArgs": (RunFinalExcelQueryArgs, run_final_excel_query),
                    }

                    if func_name_from_api in tool_map:
                        pydantic_model_class, target_function = tool_map[func_name_from_api]
                        try:
                            parsed_args = pydantic_model_class.model_validate_json(func_args_str)
                            # Llamar a la función con los argumentos desempaquetados del modelo Pydantic
                            function_result = target_function(**parsed_args.model_dump())
                            
                            # Convertir resultado a string para el mensaje 'tool'
                            if isinstance(function_result, (list, dict)):
                                result_content = json.dumps(function_result, ensure_ascii=False)
                            else:
                                result_content = str(function_result)

                            console.print(f"[blue]Tool Result => {func_name_from_api}:\n{result_content}[/blue]")

                            if func_name_from_api == "RunFinalExcelQueryArgs":
                                console.print("[bold green]Tarea completada por el agente (RunFinalExcelQueryArgs llamada).[/bold green]")
                                return 

                        except ValidationError as ve:
                            error_msg = f"Error de validación de argumentos en {func_name_from_api}: {ve}"
                            console.print(f"[red]{error_msg}[/red]")
                            result_content = json.dumps({"error": error_msg})
                        except Exception as e:
                            error_msg = f"Error al ejecutar la herramienta {func_name_from_api}: {str(e)}"
                            console.print(f"[red]{error_msg}[/red]")
                            result_content = json.dumps({"error": error_msg, "details": str(e)})
                    else:
                        error_msg = f"Función desconocida o no mapeada: {func_name_from_api}"
                        console.print(f"[red]{error_msg}[/red]")
                        result_content = json.dumps({"error": error_msg})
                    
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call_id,
                        "name": func_name_from_api, 
                        "content": result_content
                    })
            
            elif message.content: # Si no hay tool_calls pero hay contenido
                console.print(f"[magenta]Respuesta directa del asistente:[/magenta] {message.content}")
                # Considerar si esta respuesta directa finaliza el bucle
                console.print("[yellow]Agente finalizado por respuesta directa del asistente.[/yellow]")
                break
            else: # No tool_calls y no content
                console.print("[yellow]Respuesta del asistente sin tool_calls ni contenido. Finalizando.[/yellow]")
                break


        except Exception as e:
            console.print(f"[bold red]Error crítico en la iteración del agente: {str(e)}[/bold red]")
            # Podrías añadir el error a `messages` para que el LLM lo vea, o simplemente terminar.
            # messages.append({"role": "user", "content": f"Hubo un error en el sistema: {str(e)}. Por favor, intenta de nuevo o finaliza."})
            break # Terminar en caso de error grave en el bucle

    console.print("[yellow]Agente finalizado.[/yellow]")


if __name__ == "__main__":
    main()
