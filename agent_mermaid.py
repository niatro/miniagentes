import sys
import os
import subprocess
from dotenv import load_dotenv
from anthropic import Anthropic, HUMAN_PROMPT, AI_PROMPT
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Image, Paragraph
from reportlab.lib.styles import getSampleStyleSheet

# Cargar variables de entorno desde el archivo .env
load_dotenv()

def leer_conversacion(archivo):
    try:
        with open(archivo, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        print(f"Error: No se pudo encontrar el archivo '{archivo}'")
        sys.exit(1)

def generar_grafo_mermaid(texto):
    try:
        # Obtener la clave API de las variables de entorno
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("No se encontró la clave API de Anthropic en el archivo .env")
        
        anthropic = Anthropic(api_key=api_key)
        
        prompt = f"{HUMAN_PROMPT} Genera un grafo Mermaid basado en el siguiente texto de conversación. \n"
        prompt += "El grafo debe seguir el formato del ejemplo proporcionado, incluyendo:\n"
        prompt += "- Nodos con información de entradas (E), salidas (S), total (T) y relevancia (R)\n"
        prompt += "- Relaciones entre nodos\n"
        prompt += "- Estilos para diferentes tipos de nodos (centralConcept, keyFigures, eventsDates, studyEvaluation)\n"
        prompt += "- Subgrafos para agrupar conceptos relacionados\n\n"
        prompt += f"Texto de la conversación:\n{texto}\n\n"
        prompt += "Ejemplo de formato:\n"
        prompt += "graph TD\n\n"
        prompt += "%% Definición de estilos\n"
        prompt += "classDef centralConcept fill:#ff9999,stroke:#ff0000,stroke-width:4px,color:#000000;\n"
        prompt += "classDef keyFigures fill:#99ccff,stroke:#0066cc,stroke-width:2px,color:#000000;\n"
        prompt += "classDef eventsDates fill:#99ff99,stroke:#009900,stroke-width:2px,color:#000000;\n"
        prompt += "classDef studyEvaluation fill:#ffff99,stroke:#cccc00,stroke-width:2px,color:#000000;\n\n"
        prompt += "%% Nodos principales con entradas (E), salidas (S), total (T), y relevancia (R)\n"
        prompt += "A[ Segunda Guerra Mundial\\nE: 2, S: 4, T: 6, R: 5]:::centralConcept\n"
        prompt += "B[ Examen de historia\\nE: 0, S: 1, T: 1, R: 1]:::studyEvaluation\n\n"
        prompt += "%% Relaciones\n"
        prompt += "A -->|incluye| B\n\n"
        prompt += "%% Subgrafos para agrupar conceptos relacionados\n"
        prompt += "subgraph Estudio y Evaluación\n"
        prompt += "B\n"
        prompt += "end\n\n"
        prompt += "Genera un grafo similar basado en el texto proporcionado.\n"
        prompt += f"{AI_PROMPT}"

        response = anthropic.completions.create(
            model="claude-2.1",
            max_tokens_to_sample=4000,
            prompt=prompt
        )

        # Extraer solo el contenido del diagrama Mermaid
        start_index = response.completion.find("```mermaid")
        end_index = response.completion.find("```", start_index + 1)
        if start_index != -1 and end_index != -1:
            diagram_content = response.completion[start_index + len("```mermaid"):end_index].strip()
            # Validar el contenido del diagrama Mermaid
            if "graph" in diagram_content:
                return diagram_content
            else:
                print("Error: El contenido del diagrama Mermaid no es válido.")
                sys.exit(1)
        else:
            print("Error: No se pudo encontrar el contenido del diagrama Mermaid en la respuesta.")
            sys.exit(1)

    except Exception as e:
        print(f"Error al generar el grafo Mermaid: {str(e)}")
        sys.exit(1)

def guardar_grafo_mermaid(grafo, archivo):
    try:
        with open(archivo, 'w', encoding='utf-8') as f:
            f.write(grafo)
    except Exception as e:
        print(f"Error al guardar el grafo Mermaid: {str(e)}")
        sys.exit(1)

def convertir_mermaid_a_png(archivo_mmd, archivo_png):
    import requests  # Si aún no está importado en el archivo
    try:
        # Leer el código Mermaid del archivo generado
        with open(archivo_mmd, 'r', encoding='utf-8') as f:
            mermaid_code = f.read()

        # Realizar la petición POST a la API de Kroki para obtener la imagen PNG
        url = "https://kroki.io/mermaid/png"
        response = requests.post(url, data=mermaid_code.encode('utf-8'))

        if response.status_code == 200:
            with open(archivo_png, "wb") as f:
                f.write(response.content)
            print(f"Grafo Mermaid convertido a PNG: {archivo_png}")
        else:
            print(f"Error {response.status_code} al convertir Mermaid a PNG: {response.text}")
            sys.exit(1)
    except Exception as e:
        print(f"Error al convertir Mermaid a PNG: {str(e)}")
        sys.exit(1)

def generar_informe_pdf(archivo_png, archivo_pdf):
    doc = SimpleDocTemplate(archivo_pdf, pagesize=letter)
    styles = getSampleStyleSheet()
    story = []

    # Agregar título
    story.append(Paragraph("Informe de Análisis de Conversación", styles['Title']))

    # Agregar imagen del grafo
    img = Image(archivo_png, width=500, height=300)
    story.append(img)

    # Agregar descripción
    story.append(Paragraph("Este grafo representa el análisis de la conversación.", styles['Normal']))

    # Generar el PDF
    doc.build(story)
    print(f"Informe PDF generado: {archivo_pdf}")

def main():
    if len(sys.argv) < 2:
        print("Uso: python agent_mermaid.py <nombre_archivo>")
        sys.exit(1)
    
    archivo_entrada = sys.argv[1]
    texto = leer_conversacion(archivo_entrada)
    grafo = generar_grafo_mermaid(texto)
    archivo_mmd = 'grafo_conversacion.mmd'
    archivo_png = 'grafo_conversacion.png'
    archivo_pdf = 'informe_conversacion.pdf'

    guardar_grafo_mermaid(grafo, archivo_mmd)
    convertir_mermaid_a_png(archivo_mmd, archivo_png)
    generar_informe_pdf(archivo_png, archivo_pdf)

if __name__ == "__main__":
    main()
