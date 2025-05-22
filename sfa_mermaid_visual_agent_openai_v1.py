# /// script
# dependencies = [
#   "openai>=1.63.0",
#   "rich>=13.7.0",
#   "pydantic>=2.0.0",
#   "requests>=2.20.0",
#   "python-dotenv>=0.21.0"
# ]
# ///

"""
sfa_mermaid_visual_agent_openai_v1.py

Este agente Single File Agent (SFA) genera diagramas Mermaid basados en la descripción
del usuario, utilizando un modelo LLM de OpenAI con capacidades de visión (como gpt-4o-mini)
para un ciclo de revisión y refinamiento visual.

Flujo de Trabajo:
1. El LLM (texto) genera un primer borrador del código Mermaid basado en el prompt del usuario.
2. El código Mermaid se renderiza a una imagen PNG usando la API de Kroki.
3. El LLM (visión) analiza la imagen PNG generada, comparándola con el prompt original
   y el código Mermaid que la produjo.
4. El LLM proporciona feedback para mejorar el código Mermaid.
5. Si hay feedback y no se ha alcanzado el límite de iteraciones, se genera una nueva
   versión del código Mermaid incorporando el feedback. Se repite desde el paso 2.
6. Una vez que el diagrama se considera satisfactorio o se alcanza el límite de iteraciones,
   la tarea se completa.
"""

import os
import sys
import json
import argparse
import base64
import uuid
from typing import List, Dict, Any, Optional

from dotenv import load_dotenv
import requests
import openai
from pydantic import BaseModel, Field
from openai import pydantic_function_tool # type: ignore
from rich.console import Console
from rich.panel import Panel

# ---------------------------------------------------
# CONFIGURACIÓN
# ---------------------------------------------------
console = Console()
load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    console.print("[red]Error: OPENAI_API_KEY no configurada.[/red]")
    sys.exit(1)

client = openai.OpenAI(api_key=OPENAI_API_KEY)

KROKI_URL = "https://kroki.io/mermaid/png"
IMAGE_DIR = "./mermaid_images" # Directorio para guardar las imágenes generadas
os.makedirs(IMAGE_DIR, exist_ok=True)

# Prompt base proporcionado por el usuario para la generación inicial de Mermaid
USER_PROVIDED_MERMAID_GENERATION_PROMPT_TEMPLATE = """
# OBJETIVO
Generar un diagrama Mermaid que capture exclusivamente los temas clave y acciones concretas de una reunión, manteniendo una orientación principalmente vertical con ramificaciones laterales cuando sea necesario.

# INSTRUCCIONES
1. Analiza el contenido de la reunión e identifica:
   - Temas principales discutidos (máximo 5)
   - Decisiones concretas tomadas
   - Acciones específicas acordadas que sean medibles y verificables
   - Dependencias entre acciones y decisiones

2. Crea un diagrama que:
   - Use orientación vertical predominante (graph TD)
   - Permita ramificaciones laterales para temas relacionados
   - Mantenga la jerarquía visual clara
   - Utilice verbos activos y específicos en las relaciones
   - Evite términos ambiguos o generales
   - Optimice el espacio para formato carta (21.59 x 27.94 cm)

# FORMATO DEL DIAGRAMA
- Nodo inicial: tema de reunión
- Decisiones:
- Acciones concretas:

# SINTAXIS DE RELACIONES Y CONEXIONES
Usar texto descriptivo en las flechas para indicar la relación:
- Vertical descendente: A -->|"requiere"| B
- Ramificación lateral: A -.->|"relacionado con"| C
- Reconexión al flujo principal: C -->|"contribuye a"| D

Tipos de relaciones comunes:
- Verticales principales:
  - "resulta en"
  - "requiere"
  - "genera"
  - "implementa"
  - "conduce a"
- Laterales y reconexiones:
  - "relacionado con"
  - "contribuye a"
  - "complementa"
  - "apoya a"
  - "influye en"

# ESTILO
```mermaid
classDef tema fill:#f9f9f9,stroke:#333,stroke-width:2px
classDef accion fill:#e1f5fe,stroke:#0288d1,stroke-width:2px
classDef decision fill:#f3e5f5,stroke:#7b1fa2,stroke-width:2px
```

# ESTRUCTURA BASE CON RAMIFICACIONES
```mermaid
graph TD
    A[Tema Principal] -->|"requiere"| B[Decisión Principal]
    B -->|"genera"| C[Acción Principal]
    
    B -.->|"relacionado con"| D[Decisión Secundaria]
    D -->|"requiere"| E[Acción Paralela]
    E -->|"contribuye a"| C
```

# EJEMPLO COMPLETO
```mermaid
graph TD
    classDef tema fill:#f9f9f9,stroke:#333,stroke-width:2px
    classDef accion fill:#e1f5fe,stroke:#0288d1,stroke-width:2px
    classDef decision fill:#f3e5f5,stroke:#7b1fa2,stroke-width:2px

    A[Reunión Estratégica Q2] -->|"requiere"| B[Aprobar Presupuesto]
    B -->|"permite"| C[Actualizar Forecast]
    
    B -.->|"habilita"| D[Migración Tech Stack]
    D -->|"requiere"| E[Implementar Cloud AWS]
    E -->|"soporta"| C
    
    D -.->|"implica"| F[Capacitar Equipo]
    F -->|"facilita"| E

    class A tema
    class C,E,F accion
    class B,D decision
```

# REGLAS IMPORTANTES
1. Mantener la dirección principal vertical
2. Permitir ramificaciones laterales cuando aporten claridad
3. No exceder 10 nodos en total
4. Usar verbos específicos y accionables
5. Cada acción debe ser concreta y medible
6. SIEMPRE incluir texto descriptivo en las flechas
7. Optimizar el espacio visual para formato carta
8. Asegurar que las ramificaciones laterales reconecten al flujo principal cuando sea posible

# NO INCLUIR
- Personas o roles asignados
- Fechas o plazos
- Conversaciones tangenciales
- Detalles de implementación
- Discusiones sin resolución
- Flujos desconectados
- Ciclos o bucles en el diagrama
- Relaciones sin texto descriptivo
- Ramificaciones que no aporten valor al flujo principal
- Acciones no medibles o verificables

# SALIDA ESPERADA
- El diagrama debe mantener una clara orientación vertical mientras permite ramificaciones laterales estratégicas
- Debe ser legible en formato carta
- Debe contar una historia coherente con un flujo principal claro
- Las ramificaciones deben aportar contexto sin comprometer la claridad del flujo principal
- Debe optimizar el uso del espacio vertical mientras mantiene la legibilidad
- Cada nodo debe representar una acción o decisión concreta y verificable
- El diagrama debe poder leerse como una secuencia lógica de decisiones y acciones
- La salida debe tener **SOLAMENTE EL CÓDIGO MERMAID** para que la pueda leer un visualizador de mermaid, por lo tanto, no debe estar envuelto en triple comillas y etiquetas de código (```mermaid), lo cual es INCORRECTO para mmdc.

Basado en la siguiente descripción de la reunión o tarea del usuario:
<user_task_description>
{{user_task_content}}
</user_task_description>
"""

# ---------------------------------------------------
# MODELOS Pydantic para Herramientas
# ---------------------------------------------------
class GenerateMermaidCodeArgs(BaseModel):
    reasoning: str = Field(..., description="Razón para generar o refinar el código Mermaid.")
    user_task_content: str = Field(..., description="El contenido o descripción de la reunión/tarea proporcionada por el usuario para generar el diagrama.")
    previous_mermaid_code: Optional[str] = Field(None, description="Código Mermaid de la iteración anterior (si aplica).")
    visual_feedback_from_llm: Optional[str] = Field(None, description="Feedback del análisis visual del LLM para refinar el código (si aplica).")
    iteration_count: int = Field(..., description="Número de la iteración actual (empieza en 1).")

class RenderMermaidToImageArgs(BaseModel):
    reasoning: str = Field(..., description="Razón para renderizar el código Mermaid a una imagen.")
    mermaid_code: str = Field(..., description="El código Mermaid a renderizar.")
    output_filename_prefix: str = Field(default="diagram_iteration", description="Prefijo para el nombre del archivo de imagen.")
    iteration_count: int = Field(..., description="Número de la iteración actual, usado para el nombre del archivo.")

class AnalyzeMermaidImageArgs(BaseModel):
    reasoning: str = Field(..., description="Razón para analizar la imagen Mermaid generada.")
    image_path: str = Field(..., description="Ruta al archivo de imagen local a analizar.")
    original_user_task_content: str = Field(..., description="El contenido original de la tarea del usuario.")
    current_mermaid_code: str = Field(..., description="El código Mermaid que generó esta imagen.")
    iteration_count: int = Field(..., description="Número de la iteración actual.")

class CompleteTaskArgs(BaseModel):
    reasoning: str = Field(..., description="Razón para completar la tarea.")
    final_mermaid_code: str = Field(..., description="El código Mermaid final y aprobado.")
    final_image_path: str = Field(..., description="Ruta a la imagen final generada.")
    summary_of_process: str = Field(..., description="Breve resumen del proceso de generación y refinamiento.")

# ---------------------------------------------------
# FUNCIONES HERRAMIENTA
# ---------------------------------------------------

def generate_mermaid_code(
    user_task_content: str,
    iteration_count: int,
    previous_mermaid_code: Optional[str] = None,
    visual_feedback_from_llm: Optional[str] = None
) -> str:
    """Genera o refina código Mermaid usando el LLM."""
    console.log(f"[blue]Tool: generate_mermaid_code (Iteración {iteration_count})[/blue]")

    if iteration_count == 1:
        # Primera generación
        prompt_content = USER_PROVIDED_MERMAID_GENERATION_PROMPT_TEMPLATE.replace("{{user_task_content}}", user_task_content)
        system_message = "Eres un experto generando código Mermaid siguiendo instrucciones detalladas. Tu objetivo es producir el código Mermaid inicial."
    else:
        # Refinamiento basado en feedback visual
        system_message = (
            "Eres un experto refinando código Mermaid basado en feedback visual y manteniendo las directrices originales. "
            "Analiza el código previo y el feedback visual para producir una versión mejorada."
        )
        prompt_content = (
            f"El objetivo original del usuario es:\n<user_task_description>\n{user_task_content}\n</user_task_description>\n\n"
            f"El código Mermaid de la iteración anterior fue:\n<previous_mermaid_code>\n{previous_mermaid_code}\n</previous_mermaid_code>\n\n"
            f"El feedback del análisis visual de la imagen generada por ese código es:\n<visual_feedback>\n{visual_feedback_from_llm}\n</visual_feedback>\n\n"
            "Por favor, proporciona una NUEVA versión completa del código Mermaid que incorpore este feedback, "
            "manteniendo todas las reglas y el estilo del objetivo original del usuario. "
            "Asegúrate de que la salida sea SOLAMENTE el código Mermaid."
        )

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini", # Podría ser un parámetro del agente
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": prompt_content}
            ],
            temperature=0.2, # Un poco más determinista para código
        )
        generated_code = response.choices[0].message.content
        if not generated_code:
            return "Error: El LLM no generó código Mermaid."
        
        # Asegurarse de que no esté envuelto en ```mermaid ... ```
        if generated_code.strip().startswith("```mermaid"):
            generated_code = generated_code.split("```mermaid", 1)[1]
            if "```" in generated_code:
                 generated_code = generated_code.rsplit("```", 1)[0]
        elif generated_code.strip().startswith("```"): # Manejar si solo usa ```
            generated_code = generated_code.strip()[3:]
            if generated_code.strip().endswith("```"):
                generated_code = generated_code.strip()[:-3]

        console.log(f"Código Mermaid generado (Iteración {iteration_count}):\n{generated_code.strip()}")
        return generated_code.strip()
    except Exception as e:
        console.log(f"[red]Error en generate_mermaid_code: {e}[/red]")
        return f"Error al generar código Mermaid: {str(e)}"

def render_mermaid_to_image(mermaid_code: str, output_filename_prefix: str, iteration_count: int) -> str:
    """Renderiza código Mermaid a una imagen PNG usando Kroki y la guarda localmente."""
    console.log(f"[blue]Tool: render_mermaid_to_image (Iteración {iteration_count})[/blue]")
    
    # Añadir directiva de inicialización para mejor soporte de fuentes/emojis si no está
    font_directive = "%%{init: {'theme': 'default', 'themeVariables': { 'fontFamily': '\"Segoe UI Emoji\", \"Apple Color Emoji\", \"Noto Color Emoji\", sans-serif' }}}%%\n"
    if "%%{init:" not in mermaid_code and "graph " in mermaid_code: # Solo añadir si es un grafo y no tiene init
        # Encontrar la primera línea de definición del grafo (ej. "graph TD")
        lines = mermaid_code.splitlines()
        insert_idx = 0
        for i, line in enumerate(lines):
            if line.strip().startswith("graph"):
                insert_idx = i
                break
        lines.insert(insert_idx, font_directive.strip())
        mermaid_code_to_render = "\n".join(lines)
    else:
        mermaid_code_to_render = mermaid_code

    try:
        response = requests.post(KROKI_URL, data=mermaid_code_to_render.encode('utf-8'), headers={'Content-Type': 'text/plain; charset=utf-8'})
        if response.status_code == 200:
            filename = f"{output_filename_prefix}_{iteration_count}.png"
            image_path = os.path.join(IMAGE_DIR, filename)
            with open(image_path, "wb") as f:
                f.write(response.content)
            console.log(f"Imagen guardada en: {image_path}")
            return image_path
        else:
            error_msg = f"Error {response.status_code} de Kroki: {response.text[:200]}"
            console.log(f"[red]{error_msg}[/red]")
            return f"Error al renderizar con Kroki: {error_msg}"
    except Exception as e:
        console.log(f"[red]Error en render_mermaid_to_image: {e}[/red]")
        return f"Error al renderizar imagen: {str(e)}"

def _encode_image_to_base64(image_path: str) -> str:
    try:
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')
    except Exception as e:
        console.log(f"[red]Error codificando imagen {image_path} a base64: {e}[/red]")
        raise

def analyze_mermaid_image(image_path: str, original_user_task_content: str, current_mermaid_code: str, iteration_count: int) -> str:
    """Analiza la imagen Mermaid generada usando el LLM con capacidad de visión."""
    console.log(f"[blue]Tool: analyze_mermaid_image (Iteración {iteration_count})[/blue]")
    
    if not os.path.exists(image_path):
        return "Error: El archivo de imagen no existe en la ruta especificada."

    try:
        base64_image = _encode_image_to_base64(image_path)
        
        vision_prompt = [
            {
                "type": "text",
                "text": (
                    "Eres un asistente experto en análisis visual de diagramas Mermaid. "
                    "Tu tarea es evaluar la imagen proporcionada y sugerir mejoras al código Mermaid que la generó, "
                    "basándote en el objetivo original del usuario.\n\n"
                    f"**Objetivo Original del Usuario:**\n<user_task_description>\n{original_user_task_content}\n</user_task_description>\n\n"
                    f"**Código Mermaid Actual que generó esta imagen:**\n<current_mermaid_code>\n{current_mermaid_code}\n</current_mermaid_code>\n\n"
                    "**Instrucciones para tu análisis:**\n"
                    "1. Compara la imagen con el objetivo del usuario. ¿Representa la información de manera clara, precisa y completa según lo solicitado?\n"
                    "2. Evalúa la legibilidad, el layout, la claridad de las conexiones y la estética general.\n"
                    "3. Si identificas áreas de mejora (ej. nodos superpuestos, texto cortado, conexiones confusas, incumplimiento de alguna regla del prompt original), describe el problema específico.\n"
                    "4. Propón cambios concretos al **código Mermaid** para solucionar estos problemas. No sugieras editar la imagen directamente.\n"
                    "5. Si consideras que el diagrama es óptimo y cumple todos los requisitos, indica 'OPTIMO'.\n"
                    "Tu respuesta debe ser concisa y enfocada en el feedback accionable para el código Mermaid."
                )
            },
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/png;base64,{base64_image}"
                }
            }
        ]

        response = client.chat.completions.create(
            model="gpt-4o-mini", # Asegúrate que este modelo tiene capacidad de visión y está disponible
            messages=[{"role": "user", "content": vision_prompt}], # type: ignore
            max_tokens=500 
        )
        feedback = response.choices[0].message.content
        console.log(f"Feedback del Análisis Visual (Iteración {iteration_count}):\n{feedback}")
        return feedback if feedback else "No se recibió feedback del análisis visual."
    except Exception as e:
        console.log(f"[red]Error en analyze_mermaid_image: {e}[/red]")
        return f"Error al analizar imagen: {str(e)}"

def complete_task(final_mermaid_code: str, final_image_path: str, summary_of_process: str) -> str:
    """Finaliza la tarea del agente."""
    console.log(Panel(f"[green]Tarea Completada[/green]\n{summary_of_process}", title="Resultado Final", expand=False))
    console.print(f"\nCódigo Mermaid Final:\n{final_mermaid_code}")
    console.print(f"Imagen Final guardada en: {final_image_path}")
    # Aquí podrías añadir lógica para guardar el código Mermaid en un archivo .mmd si se desea.
    mermaid_code_filename = os.path.splitext(os.path.basename(final_image_path))[0] + ".mmd"
    mermaid_code_path = os.path.join(IMAGE_DIR, mermaid_code_filename)
    try:
        with open(mermaid_code_path, "w", encoding="utf-8") as f:
            f.write(final_mermaid_code)
        console.print(f"Código Mermaid guardado en: {mermaid_code_path}")
    except Exception as e:
        console.print(f"[yellow]Advertencia: No se pudo guardar el archivo .mmd: {e}[/yellow]")
        
    return "Proceso finalizado exitosamente."

# ---------------------------------------------------
# LISTA DE HERRAMIENTAS
# ---------------------------------------------------
tools_definitions = [
    GenerateMermaidCodeArgs,
    RenderMermaidToImageArgs,
    AnalyzeMermaidImageArgs,
    CompleteTaskArgs,
]
tools = [pydantic_function_tool(tool_def) for tool_def in tools_definitions] # type: ignore

# ---------------------------------------------------
# AGENT_PROMPT PRINCIPAL
# ---------------------------------------------------
AGENT_SYSTEM_PROMPT = """
Eres un agente de IA avanzado especializado en la creación de diagramas Mermaid.
Tu objetivo es generar un diagrama Mermaid de alta calidad basado en la solicitud del usuario,
utilizando un ciclo iterativo de generación de código, renderizado a imagen y análisis visual
para refinar el resultado.

Sigue este flujo de trabajo:
1.  **GenerateMermaidCode**: Llama a esta herramienta primero para generar el borrador inicial del código Mermaid.
    Usa el `user_task_content` proporcionado por el usuario. `iteration_count` será 1.
2.  **RenderMermaidToImage**: Una vez que tengas el código Mermaid, usa esta herramienta para renderizarlo
    a una imagen PNG.
3.  **AnalyzeMermaidImage**: Con la imagen PNG generada, llama a esta herramienta para que el LLM (con visión)
    analice la imagen. El LLM debe comparar la imagen con el `original_user_task_content` y el
    `current_mermaid_code` para identificar áreas de mejora.
4.  **Bucle de Refinamiento**:
    *   Si el feedback de `AnalyzeMermaidImage` NO es "OPTIMO" (o similar) y el `iteration_count` es menor
        que el máximo permitido (ej. 3 iteraciones):
        *   Vuelve a llamar a `GenerateMermaidCode`, esta vez proporcionando el `previous_mermaid_code`
          y el `visual_feedback_from_llm`. Incrementa el `iteration_count`.
        *   Repite desde el paso 2 (RenderMermaidToImage).
    *   Si el feedback es "OPTIMO" o se alcanza el límite de iteraciones:
        *   Procede al paso 5.
5.  **CompleteTask**: Una vez que el diagrama es satisfactorio, llama a esta herramienta para finalizar,
    proporcionando el código Mermaid final, la ruta a la imagen final y un resumen del proceso.

Asegúrate de pasar los argumentos correctos a cada herramienta. Presta atención al `iteration_count`.
El `user_task_content` u `original_user_task_content` debe ser el prompt original del usuario en todas las llamadas relevantes.
"""

# ---------------------------------------------------
# FUNCIÓN PRINCIPAL (main)
# ---------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="Agente SFA para generar diagramas Mermaid con revisión visual.")
    parser.add_argument("-p", "--prompt", required=True, help="Descripción de la tarea o reunión para generar el diagrama Mermaid.")
    parser.add_argument("-m", "--model", type=str, default="gpt-4o-mini", help="Modelo de OpenAI a utilizar (ej. gpt-4o-mini).")
    parser.add_argument("-i", "--max_iterations", type=int, default=3, help="Máximo número de ciclos de refinamiento visual (además de la generación inicial).")
    args = parser.parse_args()

    console.rule(f"[bold green]Inicio del Agente Mermaid Visual (Modelo: {args.model})[/bold green]")
    console.print(f"Prompt del Usuario: [cyan]{args.prompt}[/cyan]")
    console.print(f"Máx. Iteraciones de Refinamiento: {args.max_iterations}")

    # Estado del agente
    current_mermaid_code: Optional[str] = None
    current_image_path: Optional[str] = None
    visual_feedback: Optional[str] = None
    
    messages: List[Dict[str, Any]] = [
        {"role": "system", "content": AGENT_SYSTEM_PROMPT},
        {"role": "user", "content": f"Por favor, genera un diagrama Mermaid para la siguiente tarea: {args.prompt}. Inicia el proceso con la iteración 1."}
    ]

    tool_map = {
        "GenerateMermaidCodeArgs": GenerateMermaidCodeArgs,
        "RenderMermaidToImageArgs": RenderMermaidToImageArgs,
        "AnalyzeMermaidImageArgs": AnalyzeMermaidImageArgs,
        "CompleteTaskArgs": CompleteTaskArgs,
    }
    
    function_map = {
        "GenerateMermaidCodeArgs": generate_mermaid_code,
        "RenderMermaidToImageArgs": render_mermaid_to_image,
        "AnalyzeMermaidImageArgs": analyze_mermaid_image,
        "CompleteTaskArgs": complete_task,
    }

    for iteration_num in range(1, args.max_iterations + 2): # +1 para la inicial, +1 para el bucle
        console.rule(f"[yellow]Ciclo de Agente {iteration_num}[/yellow]")

        try:
            response = client.chat.completions.create(
                model=args.model,
                messages=messages, # type: ignore
                tools=tools,
                tool_choice="auto"
            )
            
            message = response.choices[0].message
            messages.append(message) # type: ignore

            if message.tool_calls:
                for tool_call in message.tool_calls:
                    tool_name = tool_call.function.name
                    tool_args_str = tool_call.function.arguments
                    tool_call_id = tool_call.id

                    console.print(f"[blue]Llamada a Herramienta => {tool_name}({tool_args_str})[/blue]")

                    if tool_name not in tool_map:
                        console.print(f"[red]Error: Herramienta desconocida '{tool_name}'[/red]")
                        result_content = json.dumps({"error": f"Herramienta desconocida: {tool_name}"})
                    else:
                        pydantic_class = tool_map[tool_name]
                        actual_function = function_map[tool_name]
                        try:
                            parsed_args = pydantic_class.model_validate_json(tool_args_str)
                            
                            # Manejo especial de argumentos para funciones
                            func_kwargs = parsed_args.model_dump()
                            if 'reasoning' in func_kwargs: # El 'reasoning' es para el LLM, no para la función Python
                                del func_kwargs['reasoning']

                            function_result = actual_function(**func_kwargs)
                            
                            # Actualizar estado del agente
                            if tool_name == "GenerateMermaidCodeArgs":
                                current_mermaid_code = function_result
                            elif tool_name == "RenderMermaidToImageArgs":
                                current_image_path = function_result
                            elif tool_name == "AnalyzeMermaidImageArgs":
                                visual_feedback = function_result
                                if visual_feedback and ("OPTIMO" in visual_feedback.upper() or "ÓPTIMO" in visual_feedback.upper()) :
                                    console.print("[green]Análisis visual indica que el diagrama es óptimo. Finalizando tarea.[/green]")
                                    if current_mermaid_code and current_image_path:
                                        summary = f"Diagrama considerado óptimo tras {parsed_args.iteration_count} iteraciones de análisis visual."
                                        complete_task(current_mermaid_code, current_image_path, summary)
                                        console.print("[bold green]Agente finalizado.[/bold green]")
                                        return
                                    else: 
                                        console.print("[red]Error: Se indicó óptimo pero falta código o imagen.[/red]")


                            if isinstance(function_result, (list, dict)):
                                result_content = json.dumps(function_result, ensure_ascii=False)
                            else:
                                result_content = str(function_result)

                            console.print(f"Resultado de Herramienta ({tool_name}):\n{result_content[:500]}...")

                            if tool_name == "CompleteTaskArgs":
                                console.print("[bold green]Agente finalizado por llamada a CompleteTask.[/bold green]")
                                return

                        except Exception as e:
                            error_msg = f"Error ejecutando {tool_name}: {str(e)}"
                            console.print(f"[red]{error_msg}[/red]")
                            result_content = json.dumps({"error": error_msg})
                    
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call_id,
                        "name": tool_name,
                        "content": result_content
                    }) # type: ignore
            
            elif message.content:
                console.print(f"[magenta]Respuesta del Asistente:[/magenta] {message.content}")
                console.print("[yellow]Agente finalizado por respuesta directa del asistente.[/yellow]")
                break
            else:
                console.print("[yellow]Respuesta sin tool_calls ni contenido. Finalizando.[/yellow]")
                break

            if iteration_num >= args.max_iterations +1 : 
                 console.print(f"[yellow]Límite de {args.max_iterations} iteraciones de refinamiento alcanzado.[/yellow]")
                 if current_mermaid_code and current_image_path:
                    summary = f"Proceso finalizado tras alcanzar el límite de {args.max_iterations} iteraciones de refinamiento."
                    complete_task(current_mermaid_code, current_image_path, summary)
                 else:
                    console.print("[red]No se pudo completar la tarea al alcanzar el límite de iteraciones, falta código o imagen.[/red]")
                 break


        except Exception as e:
            console.print(f"[bold red]Error crítico en el ciclo del agente: {e}[/bold red]")
            break
            
    console.print("[bold yellow]Agente finalizado.[/bold yellow]")

if __name__ == "__main__":
    main()
