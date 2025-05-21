# /// script
# dependencies = [
#   "openai>=1.63.0",
#   "rich>=13.7.0",
#   "pydantic>=2.0.0",
#   "pandas>=2.0.0",
#   "openpyxl>=3.1.0"
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

EJEMPLO DE EJECUCIÓN:
    uv run sfa_excel_openai.py \
        -d data.xlsx \
        -p "Qué información contiene la planilla" \
        -c 10

Parámetros:
  -d, --db: Ruta al archivo Excel.
  -p, --prompt: Petición del usuario.
  -c, --compute: Máx. de iteraciones del agente antes de detenerse.

DEPENDENCIAS:
    - openai (>=1.63.0)
    - rich (>=13.7.0)
    - pydantic (>=2.0.0)
    - pandas (>=2.0.0)
    - openpyxl (>=3.1.0)

LIMITACIONES:
- Esta implementación es un ejemplo simplificado. Funciones como detect_data_blocks()
  devuelven valores ficticios (["block_1", "block_2"]) en lugar de detectar realmente
  secciones de datos. En un entorno real, tendrías que añadir la lógica que analice celdas,
  filas vacías, etc.

Autor: (Tu nombre o tu equipo)
"""

import os
import sys
import json
import argparse
import uuid  # Para generar IDs únicos cortos en tool_calls
from typing import List

import pandas as pd
import openai
from pydantic import BaseModel, Field, ValidationError
from openai import pydantic_function_tool
from rich.console import Console
from rich.panel import Panel

# ---------------------------------------------------
# CONFIGURACIÓN DE CONSOLA Y VARIABLE GLOBAL EXCEL
# ---------------------------------------------------
console = Console()
EXCEL_PATH = None  # Se setea en main(), a partir del argumento --db

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
    block_id: str = Field(..., description="Identificador del bloque a describir (por ejemplo, 'block_1').")

class SampleBlockArgs(BaseModel):
    reasoning: str = Field(..., description="Motivo para muestrear el bloque.")
    block_id: str = Field(..., description="El bloque a muestrear ('block_1', etc.).")
    row_sample_size: int = Field(..., description="Número de filas a mostrar (3-5).")

class RunTestExcelQueryArgs(BaseModel):
    reasoning: str = Field(..., description="Por qué estamos probando esta consulta o transformación.")
    block_id: str = Field(..., description="El bloque (o bloques) sobre los que se ejecuta la consulta.")
    query_expression: str = Field(..., description="La expresión (p. ej. un pseudo-SQL, o lógica de filtrado).")

class RunFinalExcelQueryArgs(BaseModel):
    reasoning: str = Field(..., description="Explicación final de cómo esta consulta responde al pedido del usuario.")
    block_id: str = Field(..., description="El bloque (o bloques) sobre los que se ejecuta la operación final.")
    query_expression: str = Field(..., description="La instrucción/consulta final ya validada.")

# ---------------------------------------------------
# FUNCIONES HERRAMIENTA (tools) - placeholder
# ---------------------------------------------------

def list_sheets(reasoning: str) -> List[str]:
    """
    Devuelve la lista de hojas en el archivo Excel.
    """
    console.log(f"[blue]List Sheets Tool[/blue] - Reasoning: {reasoning}")
    try:
        xls = pd.ExcelFile(EXCEL_PATH)
        return xls.sheet_names
    except Exception as e:
        console.log(f"[red]Error listing sheets: {str(e)}[/red]")
        return []

def detect_data_blocks(reasoning: str, sheet_name: str) -> List[str]:
    """
    Retorna IDs de "bloques de datos" en la hoja. En este ejemplo, solo retorna 2.
    """
    console.log(f"[blue]Detect Data Blocks Tool[/blue] - Sheet: {sheet_name} - Reasoning: {reasoning}")
    try:
        # Ejemplo ficticio
        return ["block_1", "block_2"]
    except Exception as e:
        console.log(f"[red]Error detecting data blocks in '{sheet_name}': {str(e)}[/red]")
        return []

def describe_block(reasoning: str, block_id: str) -> str:
    """
    Describe un bloque (columnas, filas, etc.). Placeholder.
    """
    console.log(f"[blue]Describe Block Tool[/blue] - Block: {block_id} - Reasoning: {reasoning}")
    try:
        return f"Block {block_id} con 5 columnas y 100 filas, encabezados: ['Nombre','Edad','Ciudad']..."
    except Exception as e:
        console.log(f"[red]Error describing block '{block_id}': {str(e)}[/red]")
        return ""

def sample_block(reasoning: str, block_id: str, row_sample_size: int) -> str:
    """
    Retorna varias filas de ejemplo del bloque. Placeholder con datos simulados.
    """
    console.log(f"[blue]Sample Block Tool[/blue] - Block: {block_id}, Rows: {row_sample_size} - Reasoning: {reasoning}")
    try:
        sample_rows = [
            {"Nombre": "Ana", "Edad": 28, "Ciudad": "Lima"},
            {"Nombre": "Luis", "Edad": 35, "Ciudad": "Quito"}
        ]
        return json.dumps(sample_rows[:row_sample_size], indent=2, ensure_ascii=False)
    except Exception as e:
        console.log(f"[red]Error sampling block '{block_id}': {str(e)}[/red]")
        return ""

def run_test_excel_query(reasoning: str, block_id: str, query_expression: str) -> str:
    """
    Ejecuta una "consulta de prueba" sobre el bloque y devuelve los resultados
    solo para el agente (no al usuario final).
    """
    console.log(f"[blue]Test Query Tool[/blue] - Block: {block_id} - Reasoning: {reasoning}")
    console.log(f"[dim]Query Expression: {query_expression}[/dim]")
    try:
        return f"Test query on {block_id}: 3 rows found for '{query_expression}'."
    except Exception as e:
        console.log(f"[red]Error running test query on '{block_id}': {str(e)}[/red]")
        return str(e)

def run_final_excel_query(reasoning: str, block_id: str, query_expression: str) -> str:
    """
    Ejecuta la consulta final y muestra resultados al usuario.
    """
    console.log(
        Panel(
            f"[green]Final Query Tool[/green]\nReasoning: {reasoning}\nBlock: {block_id}\nQuery: {query_expression}"
        )
    )
    try:
        final_result = f"Consulta final en {block_id} con '{query_expression}'. 10 filas resultantes."
        return final_result
    except Exception as e:
        console.log(f"[red]Error running final query: {str(e)}[/red]")
        return str(e)

# ---------------------------------------------------
# CREACIÓN DE LA LISTA DE TOOLS (usando pydantic_function_tool)
# ---------------------------------------------------
tools = [
    pydantic_function_tool(ListSheetsArgs),
    pydantic_function_tool(DetectDataBlocksArgs),
    pydantic_function_tool(DescribeBlockArgs),
    pydantic_function_tool(SampleBlockArgs),
    pydantic_function_tool(RunTestExcelQueryArgs),
    pydantic_function_tool(RunFinalExcelQueryArgs),
]

# ---------------------------------------------------
# PLANTILLA DE PROMPT
# ---------------------------------------------------
AGENT_PROMPT = """<purpose>
    Eres un experto leyendo y procesando datos en Excel.
    Tu tarea es explorar el archivo, detectar bloques, y extraer datos que satisfagan la petición del usuario.
</purpose>

<instructions>
    <instruction>Primero, llama a list_sheets() para ver las pestañas.</instruction>
    <instruction>Luego, detecta los bloques de datos en la hoja adecuada con detect_data_blocks().</instruction>
    <instruction>Usa describe_block() y sample_block() para entender mejor cada bloque.</instruction>
    <instruction>Prueba tus transformaciones con run_test_excel_query().</instruction>
    <instruction>Cuando estés seguro, llama a run_final_excel_query() para mostrar los resultados definitivos al usuario.</instruction>
    <instruction>Siempre incluye un campo 'reasoning' explicando brevemente por qué llamas a cada herramienta.</instruction>
</instructions>

<user-request>
    {{user_request}}
</user-request>
"""

# ---------------------------------------------------
# FUNCIÓN PRINCIPAL (main)
# ---------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="Mini-Agente para Excel usando OpenAI API")
    parser.add_argument("-d", "--db", required=True, help="Path al archivo Excel (.xls, .xlsx, etc.)")
    parser.add_argument("-p", "--prompt", required=True, help="Petición o pregunta del usuario")
    parser.add_argument("-c", "--compute", type=int, default=10, help="Máx. iteraciones de razonamiento")
    args = parser.parse_args()

    # Verificamos la existencia de la variable de entorno OPENAI_API_KEY
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    if not OPENAI_API_KEY:
        console.print("[red]Error: OPENAI_API_KEY no está configurada en variables de entorno.[/red]")
        sys.exit(1)

    # Ajustamos la clave y la ruta global de Excel
    openai.api_key = OPENAI_API_KEY
    global EXCEL_PATH
    EXCEL_PATH = args.db

    # Construimos el prompt final para el agente
    completed_prompt = AGENT_PROMPT.replace("{{user_request}}", args.prompt)

    # Mensajes iniciales: 1) del usuario
    messages = [
        {"role": "user", "content": completed_prompt}
    ]

    console.rule("[bold green]INICIO DEL AGENTE[/bold green]")
    console.print(f"Archivo Excel: [yellow]{args.db}[/yellow]")
    console.print(f"Prompt del usuario: [cyan]{args.prompt}[/cyan]")
    console.print(f"Máx. Iteraciones: {args.compute}")

    # Bucle principal
    compute_iterations = 0
    while True:
        compute_iterations += 1
        console.rule(f"[yellow]AGENT LOOP {compute_iterations}/{args.compute}[/yellow]")

        if compute_iterations > args.compute:
            console.print("[red]Se alcanzó el límite de iteraciones sin 'run_final_excel_query'.[/red]")
            break

        try:
            response = openai.chat.completions.create(
                model="o3-mini",         # o "gpt-4o-mini", etc., ajusta según disponibilidad
                messages=messages,
                tools=tools,
                tool_choice="required"   # fuerza al modelo a usar las herramientas cuando corresponda
            )

            if not response.choices:
                console.print("[red]La respuesta no contiene 'choices'.[/red]")
                break

            # Tomamos el primer choice
            message = response.choices[0].message

            # Intentamos extraer la llamada a función (tool_call)
            func_call = None
            if message.function_call:
                func_call = message.function_call
            elif message.tool_calls and len(message.tool_calls) > 0:
                # Si la respuesta viene en "tool_calls"
                tool_call = message.tool_calls[0]
                func_call = tool_call.function

            if func_call:
                func_name = func_call.name
                func_args_str = func_call.arguments

                # Generamos un ID corto (máx. 40 chars)
                tool_call_id = "tc-" + str(uuid.uuid4())  # ~39 chars (ok)

                # Añadimos un mensaje con role="assistant" que registra la intención de la llamada
                messages.append({
                    "role": "assistant",
                    "tool_calls": [
                        {
                            "id": tool_call_id,
                            "type": "function",
                            "function": func_call,
                        }
                    ],
                })

                console.print(
                    f"[blue]Func Call => {func_name}({func_args_str}) | tool_call_id={tool_call_id}[/blue]"
                )

                # Ejecutamos la herramienta localmente
                try:
                    result = None

                    if func_name == "ListSheetsArgs":
                        parsed = ListSheetsArgs.model_validate_json(func_args_str)
                        result = list_sheets(reasoning=parsed.reasoning)

                    elif func_name == "DetectDataBlocksArgs":
                        parsed = DetectDataBlocksArgs.model_validate_json(func_args_str)
                        result = detect_data_blocks(
                            reasoning=parsed.reasoning,
                            sheet_name=parsed.sheet_name
                        )

                    elif func_name == "DescribeBlockArgs":
                        parsed = DescribeBlockArgs.model_validate_json(func_args_str)
                        result = describe_block(
                            reasoning=parsed.reasoning,
                            block_id=parsed.block_id
                        )

                    elif func_name == "SampleBlockArgs":
                        parsed = SampleBlockArgs.model_validate_json(func_args_str)
                        result = sample_block(
                            reasoning=parsed.reasoning,
                            block_id=parsed.block_id,
                            row_sample_size=parsed.row_sample_size,
                        )

                    elif func_name == "RunTestExcelQueryArgs":
                        parsed = RunTestExcelQueryArgs.model_validate_json(func_args_str)
                        result = run_test_excel_query(
                            reasoning=parsed.reasoning,
                            block_id=parsed.block_id,
                            query_expression=parsed.query_expression,
                        )

                    elif func_name == "RunFinalExcelQueryArgs":
                        parsed = RunFinalExcelQueryArgs.model_validate_json(func_args_str)
                        result = run_final_excel_query(
                            reasoning=parsed.reasoning,
                            block_id=parsed.block_id,
                            query_expression=parsed.query_expression,
                        )
                        console.print("[green]Final Results:[/green]")
                        console.print(result)
                        return  # Terminamos la ejecución (consulta final hecha)

                    else:
                        raise Exception(f"Función desconocida: {func_name}")

                    console.print(f"[blue]Tool Result => {func_name}:\n{result}[/blue]")

                    # Añadimos la respuesta de la herramienta con role="tool"
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call_id,  # Usamos el mismo ID
                        "content": json.dumps({"result": str(result)}),
                    })

                except ValidationError as ve:
                    error_msg = f"Error de validación de argumentos en {func_name}: {ve}"
                    console.print(f"[red]{error_msg}[/red]")
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call_id,
                        "content": json.dumps({"error": error_msg}),
                    })
                    continue

                except Exception as e:
                    error_msg = f"Error al ejecutar la herramienta {func_name}: {str(e)}"
                    console.print(f"[red]{error_msg}[/red]")
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call_id,
                        "content": json.dumps({"error": error_msg}),
                    })
                    continue

            else:
                # Si no hay function_call, quizás el modelo dio una respuesta directa
                content = message.get("content", "")
                console.print(f"[magenta]Respuesta directa sin function_call:[/magenta] {content}")
                messages.append({"role": "assistant", "content": content})
                break

        except Exception as e:
            console.print(f"[red]Error en la iteración del agente: {str(e)}[/red]")
            raise e

    console.print("[yellow]Agente finalizado sin run_final_excel_query.[/yellow]")


if __name__ == "__main__":
    main()