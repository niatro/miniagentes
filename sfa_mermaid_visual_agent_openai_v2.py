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
sfa_mermaid_visual_agent_openai_v2.py - Versión Mejorada Completa

Mejoras implementadas:
1. Modelo por defecto: gpt-4o-mini
2. Mejor manejo de entrada de texto (archivos y texto multilínea)
3. Validación de modelos
4. Plantillas de diagramas predefinidas
"""

import os
import sys
import json
import argparse
import base64
import uuid
import re
from typing import List, Dict, Any, Optional

from dotenv import load_dotenv
import requests
import openai
from pydantic import BaseModel, Field
from openai import pydantic_function_tool
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
IMAGE_DIR = "./mermaid_images"
os.makedirs(IMAGE_DIR, exist_ok=True)

# Plantillas de diagramas predefinidas
DIAGRAM_TEMPLATES = {
    "meeting": "Diagrama de reunión con decisiones y acciones",
    "process": "Diagrama de proceso o flujo de trabajo",
    "architecture": "Diagrama de arquitectura de sistema",
    "timeline": "Línea de tiempo con hitos",
    "mindmap": "Mapa mental de conceptos",
    "custom": "Diagrama personalizado"
}

# Prompt base proporcionado por el usuario para la generación inicial de Mermaid
USER_PROVIDED_MERMAID_GENERATION_PROMPT_TEMPLATE = """
# OBJETIVO
Generar un diagrama Mermaid que capture exclusivamente los temas clave y acciones concretas de una reunión, manteniendo una orientación principalmente vertical con ramificaciones laterales cuando sea necesario. El diagrama debe ser altamente autoexplicativo y didáctico.

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
   - Optimice el espacio para formato carta (21.59 x 27.94 cm), asegurando legibilidad.
   - Considere el uso de colores, tipos de línea y agrupaciones (subgrafos) para mejorar la claridad y el impacto visual.

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
%% Puedes proponer variaciones o adiciones a estos estilos si mejora la didáctica del diagrama.
```

# ESTRUCTURA BASE CON RAMIFICACIONES
```mermaid
graph TD
    A[Tema Principal] -->|"requiere"| B[Decisión Principal]
    B -->|"genera"| C[Acción Principal]
    
    subgraph "Tema Secundario Relacionado"
        D[Decisión Secundaria]
        E[Acción Paralela]
    end
    B -.->|"relacionado con"| D
    D -->|"requiere"| E
    E -->|"contribuye a"| C
```

# EJEMPLO COMPLETO
```mermaid
graph TD
    classDef tema fill:#f9f9f9,stroke:#333,stroke-width:2px
    classDef accion fill:#e1f5fe,stroke:#0288d1,stroke-width:2px
    classDef decision fill:#f3e5f5,stroke:#7b1fa2,stroke-width:2px

    A[Reunion Estrategica Q2] -->|"requiere"| B[Aprobar Presupuesto]
    B -->|"permite"| C[Actualizar Forecast]
    
    subgraph "Iniciativas Tecnologicas"
        D[Migracion Tech Stack]
        E[Implementar Cloud AWS]
        F[Capacitar Equipo]
    end
    B -.->|"habilita"| D
    D -->|"requiere"| E
    E -->|"soporta"| C
    D -.->|"implica"| F
    F -->|"facilita"| E

    class A tema
    class C,E,F accion
    class B,D decision
```

# REGLAS IMPORTANTES
1. Mantener la dirección principal vertical (graph TD).
2. Permitir ramificaciones laterales y subgrafos cuando aporten claridad y estructura.
3. No exceder 10-12 nodos principales para mantener la legibilidad en una página.
4. Usar verbos específicos y accionables.
5. Cada acción debe ser concreta y medible.
6. SIEMPRE incluir texto descriptivo en las flechas.
7. Optimizar el espacio visual para formato carta.
8. Asegurar que las ramificaciones laterales y subgrafos se integren lógicamente al flujo principal.
9. El diagrama debe ser lo más autoexplicativo y didáctico posible.

# RESTRICCIONES DE SINTAXIS PARA KROKI (MUY IMPORTANTE)
1.  **SOLO CARACTERES ASCII:** Utiliza ÚNICAMENTE caracteres ASCII estándar (a-z, A-Z, 0-9, espacios y símbolos básicos de puntuación como -, _, ., |, :, ?, !).
2.  **NO ACENTOS NI CARACTERES ESPECIALES:** NO utilices acentos (á, é, í, ó, ú), eñes (ñ, Ñ), diéresis (ü), ni otros caracteres especiales o diacríticos (ç, å, ø, etc.) en el texto de los nodos, etiquetas de flechas, o nombres de subgrafos. Reemplázalos por sus equivalentes ASCII simples (ej. "accion" en lugar de "acción", "reunion" en lugar de "reunión", "diseno" en lugar de "diseño").
3.  **SALTOS DE LÍNEA:** Para saltos de línea DENTRO del texto de un nodo, utiliza `\\n` (doble barra invertida seguida de n). Ejemplo: `A[Texto Largo\\nSegunda Linea]`. Si el renderizado con `\\n` falla, intenta eliminar los saltos de línea por completo y usar frases más cortas o dividir en múltiples nodos. NO uses `<br>`.
4.  **PARÉNTESIS Y COMILLAS:** Evita el uso de paréntesis `()` o comillas especiales (", ', «, ») dentro del texto de los nodos si es posible. Si son absolutamente necesarios, asegúrate de que no causen conflictos. Las comillas dobles `"` SÍ se usan para encerrar el texto de los nodos si este contiene caracteres que Mermaid podría interpretar de otra manera (ej. `A["Nodo con ( paréntesis )"]`), pero es preferible evitarlo.
5.  **SIMPLICIDAD DEL TEXTO:** El texto dentro de los nodos (ej. `A[Texto del Nodo]`) y en las etiquetas de las flechas (ej. `A -->|"Etiqueta aquí"| B`) debe ser lo más simple y directo posible para asegurar la máxima compatibilidad con el renderizador de Kroki.
6.  **NOMBRES DE SUBGRAFOS:** Los nombres de los subgrafos también deben seguir estas restricciones de caracteres. Si un nombre de subgrafo necesita espacios, enciérralo entre comillas dobles: `subgraph "Nombre del Subgrafo con Espacios"`.

# NO INCLUIR
- Personas o roles asignados (a menos que sea crucial para la estructura y se pida explícitamente).
- Fechas o plazos (a menos que sea el foco del diagrama, como un timeline).
- Conversaciones tangenciales.
- Detalles de implementación excesivamente granulares.
- Discusiones sin resolución.
- Flujos desconectados.
- Ciclos o bucles en el diagrama (a menos que representen un proceso iterativo claro y solicitado).
- Relaciones sin texto descriptivo.
- Ramificaciones que no aporten valor al flujo principal.
- Acciones no medibles o verificables.

# SALIDA ESPERADA
- El diagrama debe mantener una clara orientación vertical mientras permite ramificaciones y subgrafos estratégicos.
- Debe ser legible en formato carta.
- Debe contar una historia coherente con un flujo principal claro.
- Las ramificaciones y subgrafos deben aportar contexto sin comprometer la claridad del flujo principal.
- Debe optimizar el uso del espacio vertical mientras mantiene la legibilidad.
- Cada nodo debe representar una acción o decisión concreta y verificable.
- El diagrama debe poder leerse como una secuencia lógica de decisiones y acciones.
- La salida debe tener **SOLAMENTE EL CÓDIGO MERMAID** para que la pueda leer un visualizador de mermaid, por lo tanto, no debe estar envuelto en triple comillas y etiquetas de código (```mermaid), lo cual es INCORRECTO para mmdc.

Basado en la siguiente descripción de la reunión o tarea del usuario:
<user_task_description>
{{user_task_content}}
</user_task_description>
"""

# Extensiones de plantilla específicas por tipo
TEMPLATE_EXTENSIONS = {
    "architecture": """
# INSTRUCCIONES ADICIONALES PARA DIAGRAMAS DE ARQUITECTURA
- Usar subgrafos para agrupar componentes relacionados (Frontend, Backend, Data Layer, etc.)
- Mostrar flujo de datos entre componentes con flechas etiquetadas
- Indicar tecnologías/protocolos en las conexiones (HTTP, gRPC, WebSocket, etc.)
- Diferenciar tipos de componentes con estilos (servicios, bases de datos, colas, etc.)
- Incluir componentes externos claramente diferenciados
""",
    "process": """
# INSTRUCCIONES ADICIONALES PARA DIAGRAMAS DE PROCESO
- Usar formas apropiadas: rectángulos para actividades, rombos para decisiones
- Incluir puntos de inicio y fin claramente marcados
- Mostrar flujos alternativos y excepciones
- Numerar los pasos si es relevante
- Indicar actores o sistemas responsables cuando sea crítico
""",
    "timeline": """
# INSTRUCCIONES ADICIONALES PARA LÍNEAS DE TIEMPO
- Organizar eventos cronológicamente de arriba a abajo
- Incluir fechas o períodos cuando estén disponibles
- Agrupar eventos relacionados
- Usar estilos diferentes para tipos de hitos
- Mostrar dependencias temporales entre eventos
""",
    "mindmap": """
# INSTRUCCIONES ADICIONALES PARA MAPAS MENTALES
- Concepto central en el medio con ramificaciones
- Usar orientación radial si es posible
- Agrupar conceptos relacionados con colores
- Mantener texto conciso en cada nodo
- Mostrar jerarquías de conceptos claramente
"""
}

# ---------------------------------------------------
# MODELOS Pydantic para Herramientas
# ---------------------------------------------------
class GenerateMermaidCodeArgs(BaseModel):
    reasoning: str = Field(..., description="Razón para generar o refinar el código Mermaid.")
    user_task_content: str = Field(..., description="El contenido o descripción de la reunión/tarea proporcionada por el usuario para generar el diagrama.")
    previous_mermaid_code: Optional[str] = Field(None, description="Código Mermaid de la iteración anterior (si aplica).")
    visual_feedback_from_llm: Optional[str] = Field(None, description="Feedback del análisis visual del LLM o error de renderizado para refinar el código (si aplica).")
    iteration_count: int = Field(..., description="Número de la iteración actual (empieza en 1).")

class RenderMermaidToImageArgs(BaseModel):
    reasoning: str = Field(..., description="Razón para renderizar el código Mermaid a una imagen.")
    mermaid_code: str = Field(..., description="El código Mermaid a renderizar.")
    output_filename_prefix: str = Field(default="diagram_iteration", description="Prefijo para el nombre del archivo de imagen.")
    iteration_count: int = Field(..., description="Número de la iteración actual, usado para el nombre del archivo.")

class AnalyzeMermaidImageArgs(BaseModel):
    reasoning: str = Field(..., description="Razón para analizar la imagen Mermaid generada.")
    current_image_path: str = Field(..., description="Ruta al archivo de imagen actual a analizar.")
    previous_image_path: Optional[str] = Field(None, description="Ruta a la imagen de la iteración anterior, si existe, para comparación.")
    original_user_task_content: str = Field(..., description="El contenido original de la tarea del usuario.")
    current_mermaid_code: str = Field(..., description="El código Mermaid que generó la imagen actual.")
    iteration_count: int = Field(..., description="Número de la iteración actual.")

class CompleteTaskArgs(BaseModel):
    reasoning: str = Field(..., description="Razón para completar la tarea.")
    final_mermaid_code: str = Field(..., description="El código Mermaid final y aprobado.")
    final_image_path: str = Field(..., description="Ruta a la imagen final generada.")
    summary_of_process: str = Field(..., description="Breve resumen del proceso de generación y refinamiento.")

# ---------------------------------------------------
# FUNCIONES HERRAMIENTA
# ---------------------------------------------------

def process_user_input(prompt: str) -> str:
    """Procesa el input del usuario (texto o archivo)."""
    if os.path.isfile(prompt):
        console.print(f"[blue]📄 Leyendo contenido desde: {prompt}[/blue]")
        try:
            with open(prompt, 'r', encoding='utf-8') as f:
                content = f.read()
            console.print(f"[green]✓ Archivo leído exitosamente ({len(content)} caracteres)[/green]")
            return content
        except Exception as e:
            console.print(f"[red]Error leyendo archivo: {e}[/red]")
            return prompt
    return prompt.strip()

def generate_mermaid_code(
    user_task_content: str,
    iteration_count: int,
    model_to_use: str,
    template_type: str = "custom",
    previous_mermaid_code: Optional[str] = None,
    visual_feedback_from_llm: Optional[str] = None
) -> str:
    """Genera o refina código Mermaid usando el LLM."""
    console.log(f"[blue]Tool: generate_mermaid_code (Iteración {iteration_count}, Modelo: {model_to_use})[/blue]")

    if iteration_count == 1:
        base_prompt = USER_PROVIDED_MERMAID_GENERATION_PROMPT_TEMPLATE
        if template_type in TEMPLATE_EXTENSIONS:
            base_prompt += TEMPLATE_EXTENSIONS[template_type]
        prompt_content = base_prompt.replace("{{user_task_content}}", user_task_content)
        system_message = "Eres un experto generando código Mermaid siguiendo instrucciones detalladas. Tu objetivo es producir el código Mermaid inicial, que sea lo más autoexplicativo y didáctico posible. Presta MUCHA ATENCIÓN a las RESTRICCIONES DE SINTAXIS PARA KROKI, especialmente sobre el uso exclusivo de caracteres ASCII y cómo manejar saltos de línea y caracteres especiales."
    else:
        system_message = (
            "Eres un experto refinando código Mermaid basado en feedback visual o errores de renderizado, manteniendo las directrices originales. "
            "Analiza el código previo y el feedback para producir una versión mejorada que sea significativamente más clara, didáctica y estéticamente agradable, Y QUE CUMPLA ESTRICTAMENTE CON LAS RESTRICCIONES DE SINTAXIS PARA KROKI. "
            "Si el feedback es un error de renderizado, prioriza corregir la sintaxis, especialmente revisando caracteres no ASCII, acentos, paréntesis o saltos de línea problemáticos en el texto de los nodos o etiquetas. Simplifica el texto si es necesario para asegurar la compatibilidad."
            "Considera cambios en colores (classDef), tipos de línea, agrupaciones (subgraph) y layout general solo DESPUÉS de asegurar la validez sintáctica."
        )
        prompt_content = (
            f"El objetivo original del usuario es:\n<user_task_description>\n{user_task_content}\n</user_task_description>\n\n"
            f"El código Mermaid de la iteración anterior fue:\n<previous_mermaid_code>\n{previous_mermaid_code}\n</previous_mermaid_code>\n\n"
            f"El feedback (puede ser análisis visual o un error de renderizado) es:\n<visual_feedback>\n{visual_feedback_from_llm}\n</visual_feedback>\n\n"
            "Por favor, proporciona una NUEVA versión completa del código Mermaid que incorpore este feedback de manera sustancial, "
            "manteniendo todas las reglas y el estilo del objetivo original del usuario, y CUMPLIENDO ESTRICTAMENTE las RESTRICCIONES DE SINTAXIS PARA KROKI. "
            "Asegúrate de que la salida sea SOLAMENTE el código Mermaid."
        )

    try:
        response = client.chat.completions.create(
            model=model_to_use,
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": prompt_content}
            ],
            temperature=0.2,
        )
        generated_code = response.choices[0].message.content
        if not generated_code:
            return "Error: El LLM no generó código Mermaid."
        
        if generated_code.strip().startswith("```mermaid"):
            generated_code = generated_code.split("```mermaid", 1)[1]
            if "```" in generated_code:
                 generated_code = generated_code.rsplit("```", 1)[0]
        elif generated_code.strip().startswith("```"):
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
    
    mermaid_code_to_render = mermaid_code

    try:
        response = requests.post(KROKI_URL, data=mermaid_code_to_render.encode('utf-8'), headers={'Content-Type': 'text/plain; charset=utf-8'})
        if response.status_code == 200:
            filename = f"{output_filename_prefix}_{iteration_count}_{uuid.uuid4().hex[:8]}.png"
            image_path = os.path.join(IMAGE_DIR, filename)
            with open(image_path, "wb") as f:
                f.write(response.content)
            console.log(f"Imagen guardada en: {image_path}")
            return image_path
        else:
            kroki_error_text = response.text
            error_line_match = re.search(r"on line (\d+):", kroki_error_text)
            error_line_number = None
            code_snippet = ""
            if error_line_match:
                try:
                    error_line_number = int(error_line_match.group(1))
                    lines = mermaid_code_to_render.splitlines()
                    start = max(0, error_line_number - 2)
                    end = min(len(lines), error_line_number + 1)
                    snippet_lines = []
                    for i in range(start, end):
                        prefix = ">> " if i == error_line_number - 1 else "   "
                        snippet_lines.append(f"{prefix}L{i+1}: {lines[i]}")
                    code_snippet = "\n".join(snippet_lines)
                except Exception:
                    code_snippet = "(No se pudo extraer el fragmento de código)"

            error_msg = (
                f"Error {response.status_code} de Kroki. Mensaje: {kroki_error_text[:500]}\n"
                f"POSIBLE ERROR DE SINTAXIS MERMAID. "
                f"Revisa las RESTRICCIONES DE SINTAXIS PARA KROKI (ASCII, no acentos, etc.).\n"
            )
            if error_line_number:
                error_msg += (
                    f"Kroki reportó un error cerca de la línea {error_line_number} del código Mermaid.\n"
                    f"Fragmento de código problemático (líneas {start+1}-{end}):\n{code_snippet}\n"
                    f"Por favor, revisa esta sección cuidadosamente en el código Mermaid completo y corrige la sintaxis."
                )
            else:
                error_msg += "No se pudo determinar la línea exacta del error. Revisa todo el código Mermaid."

            console.log(f"[red]{error_msg}[/red]")
            return f"Error al renderizar con Kroki: {error_msg}"
    except Exception as e:
        console.log(f"[red]Error en render_mermaid_to_image: {e}[/red]")
        return f"Error al renderizar imagen: {str(e)}"

def _encode_image_to_base64(image_path: str) -> Optional[str]:
    try:
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')
    except Exception as e:
        console.log(f"[red]Error codificando imagen {image_path} a base64: {e}[/red]")
        return None

def analyze_mermaid_image(
    current_image_path: str,
    original_user_task_content: str,
    current_mermaid_code: str,
    iteration_count: int,
    model_to_use: str,
    previous_image_path: Optional[str] = None
) -> str:
    """Analiza la imagen Mermaid generada usando el LLM con capacidad de visión."""
    console.log(f"[blue]Tool: analyze_mermaid_image (Iteración {iteration_count}, Modelo: {model_to_use})[/blue]")
    
    if not os.path.exists(current_image_path):
        return "Error: El archivo de imagen actual no existe."

    current_base64_image = _encode_image_to_base64(current_image_path)
    if not current_base64_image:
        return "Error: No se pudo codificar la imagen actual."

    vision_prompt_content = []
    vision_prompt_text = (
        "Eres un asistente experto en diseño y análisis visual de diagramas Mermaid. "
        "Tu tarea es evaluar la calidad y efectividad de la 'imagen_actual' del diagrama y, si se proporciona una 'imagen_previa', "
        "compararlas para determinar si los cambios recientes fueron significativos.\n\n"
        f"**Objetivo Original del Usuario:**\n<user_task_description>\n{original_user_task_content}\n</user_task_description>\n\n"
        f"**Código Mermaid Actual (que generó 'imagen_actual'):**\n<current_mermaid_code>\n{current_mermaid_code}\n</current_mermaid_code>\n\n"
        "**Instrucciones para tu análisis:**\n"
        "1.  **Evaluación de 'imagen_actual':**\n"
        "    a.  Compara 'imagen_actual' con el objetivo del usuario. ¿Representa la información de manera clara, precisa, completa y didáctica?\n"
        "    b.  Evalúa la legibilidad, el layout (distribución, espaciado), la claridad de las conexiones y la estética general. ¿Se ajusta bien a un formato de página vertical?\n"
        "    c.  Considera si los colores de nodos (classDef), tipos de línea/flecha, y el uso (o ausencia) de agrupaciones (`subgraph`) son óptimos para la comprensión.\n"
        "2.  **Comparación con 'imagen_previa' (si se proporciona):**\n"
        "    a.  Si hay una 'imagen_previa', compárala con 'imagen_actual'. ¿Los cambios entre ellas representan una mejora *apreciable* y *sustancial*?\n"
        "    b.  Si la mejora es mínima o los cambios son triviales, o si el diagrama parece haber alcanzado un buen nivel de calidad, indícalo.\n"
        "3.  **Feedback y Sugerencias (siempre sobre el `current_mermaid_code`):**\n"
        "    a.  Si identificas áreas de mejora en 'imagen_actual' (ej. nodos superpuestos, texto cortado, conexiones confusas, colores poco efectivos, falta de agrupaciones lógicas, incumplimiento de reglas del prompt original), describe el problema específico.\n"
        "    b.  Propón cambios concretos y detallados al **`current_mermaid_code`** para solucionar estos problemas. Sé específico sobre qué cambiar (ej. 'modificar classDef accion a fill:#D0E7F8', 'agrupar nodos X,Y en un subgraph \"Proceso Principal\"', 'cambiar flecha de A a B a -->|conduce a|').\n"
        "4.  **Conclusión de tu análisis (elige UNA de estas etiquetas al inicio de tu respuesta):**\n"
        "    *   `OPTIMO`: Si 'imagen_actual' es excelente, cumple todos los requisitos, es altamente didáctica y no requiere más cambios significativos.\n"
        "    *   `MINIMA_MEJORA`: Si 'imagen_actual' es buena, pero los cambios respecto a 'imagen_previa' (si existe) fueron menores, o si cualquier mejora adicional sería trivial o no justificaría otra iteración.\n"
        "    *   `REFINAR`: Si 'imagen_actual' tiene áreas claras de mejora sustancial y crees que otra iteración produciría un diagrama notablemente mejor. En este caso, proporciona un feedback detallado y accionable.\n\n"
        "Tu respuesta debe ser concisa, comenzar con una de las etiquetas (`OPTIMO`, `MINIMA_MEJORA`, `REFINAR`), y luego, si es `REFINAR`, el feedback detallado."
    )
    vision_prompt_content.append({"type": "text", "text": vision_prompt_text})
    vision_prompt_content.append({"type": "image_url", "image_url": {"url": f"data:image/png;base64,{current_base64_image}", "detail": "high"}})

    if previous_image_path and os.path.exists(previous_image_path):
        previous_base64_image = _encode_image_to_base64(previous_image_path)
        if previous_base64_image:
            vision_prompt_content.insert(1, {"type": "text", "text": "\n\n**Imagen Previa (para comparación):**"}) 
            vision_prompt_content.insert(2, {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{previous_base64_image}", "detail": "high"}})
            vision_prompt_content.insert(1, {"type": "text", "text": "\n\n**Imagen Actual:**"}) 

    try:
        response = client.chat.completions.create(
            model=model_to_use,
            messages=[{"role": "user", "content": vision_prompt_content}], # type: ignore
            max_tokens=800 
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
Eres un agente de IA avanzado especializado en la creación de diagramas Mermaid de alta calidad.
Tu objetivo es generar un diagrama Mermaid que sea claro, didáctico, estéticamente agradable y que
represente fielmente la solicitud del usuario. Utilizas un ciclo iterativo de generación de código,
renderizado a imagen y análisis visual (comparando con la imagen previa si existe) para refinar el resultado.
Presta EXTREMA atención a los errores de renderizado de Kroki y a las RESTRICCIONES DE SINTAXIS PARA KROKI.

Sigue este flujo de trabajo:
1.  **GenerateMermaidCode**: Llama a esta herramienta primero para generar el borrador inicial del código Mermaid.
    Usa el `user_task_content` proporcionado por el usuario. `iteration_count` será 1.
2.  **RenderMermaidToImage**: Una vez que tengas el código Mermaid, usa esta herramienta para renderizarlo
    a una imagen PNG. Guarda la ruta de esta imagen. Si esta herramienta devuelve un error de Kroki,
    el feedback para la siguiente llamada a `GenerateMermaidCode` será este error.
3.  **AnalyzeMermaidImage**: Si `RenderMermaidToImage` fue exitoso, con la `current_image_path`
    (y `previous_image_path` si no es la primera iteración de análisis), llama a esta herramienta.
    El LLM (con visión) analizará la imagen actual, la comparará con la previa si existe,
    y evaluará si se necesitan más refinamientos o si el diagrama es óptimo o la mejora es mínima.
    El feedback comenzará con `OPTIMO`, `MINIMA_MEJORA`, o `REFINAR`.
4.  **Bucle de Refinamiento**:
    *   Si el resultado de `RenderMermaidToImage` fue un error, o si el feedback de `AnalyzeMermaidImage`
        comienza con `REFINAR`, Y el `iteration_count` (del análisis o el número de intentos de corrección de renderizado)
        es menor que el máximo permitido:
        *   Incrementa el contador de iteración para la generación de código.
        *   Vuelve a llamar a `GenerateMermaidCode`, proporcionando el `previous_mermaid_code` (que es el `current_mermaid_code`
          de la etapa de análisis o el código que falló al renderizar) y el `visual_feedback_from_llm` (que puede ser
          el análisis visual o el mensaje de error de Kroki formateado).
        *   Actualiza el `previous_image_path` con el `current_image_path` (si se generó una imagen) antes de renderizar la nueva imagen.
        *   Repite desde el paso 2 (RenderMermaidToImage).
    *   Si el feedback de `AnalyzeMermaidImage` comienza con `OPTIMO` o `MINIMA_MEJORA`, o si se alcanza el límite de iteraciones de refinamiento:
        *   Procede al paso 5.
5.  **CompleteTask**: Una vez que el diagrama es satisfactorio o el proceso de refinamiento concluye,
    llama a esta herramienta para finalizar, proporcionando el código Mermaid final (`current_mermaid_code`),
    la ruta a la imagen final (`current_image_path`) y un resumen del proceso.

Asegúrate de pasar los argumentos correctos a cada herramienta. Presta atención al `iteration_count` para cada etapa.
El `user_task_content` u `original_user_task_content` debe ser el prompt original del usuario en todas las llamadas relevantes.
Gestiona correctamente `current_image_path` y `previous_image_path`.
Si `RenderMermaidToImage` falla, el siguiente paso debe ser `GenerateMermaidCode` para corregir el error, usando el mensaje de error como `visual_feedback_from_llm`.
"""

# ---------------------------------------------------
# FUNCIÓN PRINCIPAL (main)
# ---------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="Agente SFA para generar diagramas Mermaid con revisión visual.")
    parser.add_argument("-p", "--prompt", required=True, help="Texto o archivo con el contenido a convertir en diagrama Mermaid.")
    parser.add_argument("-m", "--model", type=str, default="gpt-4o", help="Modelo de OpenAI a utilizar (default: gpt-4o).")
    parser.add_argument("-i", "--max_refinement_iterations", type=int, default=3, help="Máximo número de ciclos de refinamiento visual (además de la generación inicial).")
    parser.add_argument("-t", "--template", choices=list(DIAGRAM_TEMPLATES.keys()), default="custom", help="Tipo de diagrama predefinido.")
    
    args = parser.parse_args()

    console.rule(f"[bold green]🎨 Generador de Diagramas Mermaid con IA[/bold green]")
    
    # Procesar el input del usuario
    user_content = process_user_input(args.prompt)
    
    console.print(f"\n[green]Configuración:[/green]")
    console.print(f"  • Modelo: {args.model}")
    console.print(f"  • Tipo de diagrama: {DIAGRAM_TEMPLATES[args.template]}")
    console.print(f"  • Iteraciones máximas: {args.max_refinement_iterations}")
    console.print(f"  • Análisis visual: Sí")
    console.print(f"  • Longitud del texto: {len(user_content)} caracteres")
    
    console.print("\n[bold cyan]Iniciando generación del diagrama...[/bold cyan]")

    current_mermaid_code: Optional[str] = None
    current_image_path: Optional[str] = None
    previous_image_path_for_analysis: Optional[str] = None
    template_type = args.template
    
    messages: List[Dict[str, Any]] = [
        {"role": "system", "content": AGENT_SYSTEM_PROMPT},
        {"role": "user", "content": f"Por favor, genera un diagrama Mermaid para la siguiente tarea: {user_content}. Inicia el proceso con la iteración de generación de código 1. Usa el template tipo '{template_type}'."}
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
    
    total_agent_loops = args.max_refinement_iterations * 3 + 5 
    refinement_cycles_done = 0
    
    code_generation_iteration_counter = 0
    render_iteration_counter = 0
    analysis_iteration_counter = 0

    for agent_loop_num in range(1, total_agent_loops + 1):
        console.rule(f"[yellow]Ciclo de Agente {agent_loop_num}/{total_agent_loops} (Refinamientos: {refinement_cycles_done}/{args.max_refinement_iterations})[/yellow]")

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

                    console.print(f"[blue]Llamada a Herramienta => {tool_name}[/blue]")

                    if tool_name not in tool_map:
                        console.print(f"[red]Error: Herramienta desconocida '{tool_name}'[/red]")
                        result_content = json.dumps({"error": f"Herramienta desconocida: {tool_name}"})
                    else:
                        pydantic_class = tool_map[tool_name]
                        actual_function = function_map[tool_name]
                        try:
                            parsed_args = pydantic_class.model_validate_json(tool_args_str)
                            
                            func_kwargs = parsed_args.model_dump()
                            if 'reasoning' in func_kwargs:
                                del func_kwargs['reasoning']

                            if tool_name == "GenerateMermaidCodeArgs":
                                func_kwargs['model_to_use'] = args.model
                                func_kwargs['template_type'] = template_type
                                code_generation_iteration_counter = parsed_args.iteration_count
                            elif tool_name == "RenderMermaidToImageArgs":
                                render_iteration_counter = parsed_args.iteration_count
                            elif tool_name == "AnalyzeMermaidImageArgs":
                                func_kwargs['model_to_use'] = args.model
                                analysis_iteration_counter = parsed_args.iteration_count
                                func_kwargs['previous_image_path'] = previous_image_path_for_analysis

                            function_result = actual_function(**func_kwargs)
                            
                            if tool_name == "GenerateMermaidCodeArgs":
                                current_mermaid_code = function_result
                                if "Error al generar código Mermaid:" in current_mermaid_code:
                                    console.print(f"[red]Error crítico en GenerateMermaidCode: {current_mermaid_code}. Finalizando agente.[/red]")
                                    complete_task(current_mermaid_code or "Error", current_image_path or "N/A", "Finalizado debido a error en generación de código.")
                                    return
                            elif tool_name == "RenderMermaidToImageArgs":
                                if "Error al renderizar con Kroki:" not in function_result:
                                    previous_image_path_for_analysis = current_image_path 
                                    current_image_path = function_result
                                else:
                                    current_image_path = None
                            elif tool_name == "AnalyzeMermaidImageArgs":
                                visual_feedback = function_result
                                if visual_feedback:
                                    feedback_upper = visual_feedback.upper()
                                    if feedback_upper.startswith("OPTIMO") or feedback_upper.startswith("MINIMA_MEJORA"):
                                        console.print(f"[green]Análisis visual indica: {visual_feedback.splitlines()[0]}. Finalizando refinamiento.[/green]")
                                        if current_mermaid_code and current_image_path:
                                            summary = f"Diagrama finalizado. Feedback visual: {visual_feedback.splitlines()[0]}"
                                            complete_task(current_mermaid_code, current_image_path, summary)
                                            console.print("[bold green]Agente finalizado.[/bold green]")
                                            return
                                        else: 
                                            console.print("[red]Error: Feedback óptimo/mínimo pero falta código o imagen.[/red]")
                                    elif feedback_upper.startswith("REFINAR"):
                                        refinement_cycles_done +=1 
                                        console.print(f"[yellow]Feedback visual indica REFINAR. Ciclos de refinamiento: {refinement_cycles_done}.[/yellow]")

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

            if refinement_cycles_done >= args.max_refinement_iterations:
                 console.print(f"[yellow]Límite de {args.max_refinement_iterations} iteraciones de refinamiento alcanzado.[/yellow]")
                 if current_mermaid_code and current_image_path:
                    summary = f"Proceso finalizado tras alcanzar el límite de {args.max_refinement_iterations} iteraciones de refinamiento."
                    complete_task(current_mermaid_code, current_image_path, summary)
                 elif current_mermaid_code:
                    summary = f"Proceso finalizado tras alcanzar el límite de {args.max_refinement_iterations} iteraciones. El último renderizado pudo haber fallado."
                    complete_task(current_mermaid_code, current_image_path or "Último render fallido", summary)
                 else:
                    console.print("[red]No se pudo completar la tarea al alcanzar el límite de iteraciones de refinamiento.[/red]")
                 break
        
        except Exception as e:
            console.print(f"[bold red]Error crítico en el ciclo del agente: {e}[/bold red]")
            break
            
    console.print("[bold yellow]Agente finalizado.[/bold yellow]")

if __name__ == "__main__":
    main()