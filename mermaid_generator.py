import os
import unicodedata
import requests
import subprocess
import tempfile
from anthropic import Anthropic
from .llm_handler import LLMHandler
class MermaidGenerator:
    def __init__(self, config):
        self.config = config
        self.llm_handler = LLMHandler(config)

    def generate_mermaid_diagram(self):
        # Leer el archivo de la minuta final
        tipo_transcripcion_norm = unicodedata.normalize('NFKD', self.config.tipo_transcripcion)\
            .encode('ASCII', 'ignore').decode('utf-8').lower()
        analysis_path = os.path.join(self.config.output_path, 'destilados', f"minuta_{tipo_transcripcion_norm}.md")
        
        if not os.path.exists(analysis_path):
            print(f"Error: El archivo {analysis_path} no existe. Asegúrese de que la minuta fue generada correctamente.")
            return False
            
        try:
            # Leer el contenido del análisis
            with open(analysis_path, 'r', encoding='utf-8') as f:
                analysis_text = f.read()
            
            # Leer el prompt de Mermaid
            prompt_path = os.path.join(
                os.path.dirname(os.path.dirname(__file__)),
                'prompts',
                'producir_mermaid.md'
            )
            with open(prompt_path, 'r', encoding='utf-8') as f:
                prompt_template = f.read()
            
            # Generar el código Mermaid usando el nuevo formato de Messages API
            messages = [
                {
                    "role": "user",
                    "content": f"{prompt_template}\n\nINPUT:\n{analysis_text}"
                }
            ]
            
            # Guardar el modelo actual
            original_model = self.config.selected_model
            
            # Forzar el uso del modelo específico para Mermaid
            self.config.selected_model = "anthropic/claude-3-5-sonnet-20241022"
            self.config.llm_options = {'force_model': True}
            
            # Usar el LLM handler actualizado para hacer la llamada
            mermaid_code = self.llm_handler.try_llm_messages(messages)
            
            # Restablecer configuración original
            self.config.selected_model = original_model
            self.config.llm_options = {}
            
            if mermaid_code:
                # Guardar el código Mermaid
                mermaid_path = os.path.join(self.config.output_path, 'destilados', 'diagram.mmd')
                with open(mermaid_path, 'w', encoding='utf-8') as f:
                    f.write(mermaid_code)
        
                # Convertir a PNG usando la API de Kroki
                png_path = os.path.join(self.config.output_path, 'destilados', 'diagram.png')
                self.mermaid_to_png(mermaid_code, png_path)
        
                return png_path
            return None
            
        except Exception as e:
            print(f"Error al generar el diagrama Mermaid: {str(e)}")
            return False
    
    def mermaid_to_png(self, mermaid_code: str, output_file: str):
        url = "https://kroki.io/mermaid/png"
        try:
            # Prepend a font directive for emoji support if no direct initialization is provided
            font_directive = "%%{init: {'theme': 'default', 'themeVariables': { 'fontFamily': '\"Segoe UI Emoji\", \"Apple Color Emoji\", \"Noto Color Emoji\", sans-serif' }}}%%\n"
            if "init:" not in mermaid_code:
                mermaid_code = font_directive + mermaid_code

            headers = {'Content-Type': 'text/plain; charset=utf-8'}
            response = requests.post(url, data=mermaid_code.encode('utf-8'), headers=headers)
            if response.status_code == 200:
                with open(output_file, "wb") as f:
                    f.write(response.content)
                print(f"Diagrama guardado como {output_file}")
            else:
                print(f"Error {response.status_code} al convertir Mermaid: {response.text}")
        except Exception as e:
            print(f"Error al convertir el diagrama: {str(e)}")
