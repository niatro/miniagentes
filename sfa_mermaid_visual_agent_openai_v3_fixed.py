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
ainstein_mermaid_visual_agent_v3_fixed.py - AInstein Optimized Agent

Mejoras implementadas:
1. Compatibilidad total con restricciones de Kroki.io
2. Sistema de relaciones claras con diferentes tipos de líneas
3. Nodos representan procesos y recursos específicamente  
4. Agrupaciones inteligentes obligatorias (3+ elementos)
5. Jerarquía visual clara (flujo principal vs secundario)
6. Presupuesto máximo de $0.15
7. Sanitización ultra-estricta basada en issues conocidos de Kroki
8. Templates especializados para contextos de AInstein
9. Validación completa anti-errores HTTP 400
10. Diseño optimizado para informes ejecutivos
"""

import os
import sys
import json
import argparse
import base64
import uuid
import re
import time
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from dotenv import load_dotenv
import requests
import openai
from pydantic import BaseModel, Field
from openai import pydantic_function_tool
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

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
IMAGE_DIR = "./ainstein_mermaid_images"
os.makedirs(IMAGE_DIR, exist_ok=True)

# Configuración de modelos especializada
DEFAULT_CODE_MODEL = "o4-mini"  # Modelo más estable para generación de código
DEFAULT_VISION_MODEL = "gpt-4o"  # Para análisis visual
DETAIL_LEVEL = "high"
COST_PER_TOKEN = 0.0000025  # $2.50 per 1M tokens
TOKENS_PER_IMAGE = 765  # Aproximado para 1024x1024 en high detail
COST_PER_IMAGE_ANALYSIS = TOKENS_PER_IMAGE * COST_PER_TOKEN

# Límites optimizados
MAX_REFINEMENT_ITERATIONS = 2
IMPROVEMENT_THRESHOLD = 0.25  # 25% de mejora mínima para continuar
DEFAULT_MAX_BUDGET = 0.15  # Presupuesto máximo por defecto

@dataclass
class AgentMetrics:
    total_cost: float = 0.0
    iterations_count: int = 0
    render_attempts: int = 0
    kroki_errors: int = 0
    start_time: float = 0.0
    
    def add_analysis_cost(self):
        self.total_cost += COST_PER_IMAGE_ANALYSIS
    
    def get_duration(self) -> float:
        return time.time() - self.start_time if self.start_time > 0 else 0

# ---------------------------------------------------
# TEMPLATES ESPECIALIZADOS PARA AINSTEIN
# ---------------------------------------------------

AINSTEIN_TEMPLATES = {
    "tech-troubleshooting": {
        "name": "Technical Problem Solving",
        "description": "Debugging, análisis de fallos, optimización de sistemas",
        "focus": "Flujos de diagnóstico técnico con validación y contingencias"
    },
    "env-impact": {
        "name": "Environmental Impact Analysis", 
        "description": "Evaluación de sostenibilidad, análisis de ciclo de vida",
        "focus": "Análisis de impacto ambiental con métricas de sostenibilidad"
    },
    "eng-innovation": {
        "name": "Engineering Innovation Flow",
        "description": "Desarrollo de productos, I+D, prototipado",
        "focus": "Gates de validación técnica y comercial en innovación"
    },
    "proposal-dev": {
        "name": "Proposal Development",
        "description": "Estructuración de propuestas, metodologías de consultoría",
        "focus": "Desarrollo de propuestas con stakeholder mapping"
    },
    "tech-architecture": {
        "name": "Tech Stack Architecture",
        "description": "Diseño de sistemas, selección tecnológica",
        "focus": "Arquitectura de sistemas con dependencies y performance"
    },
    "methodology-impl": {
        "name": "Methodology Implementation",
        "description": "Implementación de frameworks, mejora continua",
        "focus": "Implementación de metodologías con change management"
    },
    "sustainable-tech": {
        "name": "Sustainable Tech Solution",
        "description": "Soluciones técnicas con criterios ambientales",
        "focus": "Trade-offs técnicos vs sostenibilidad integrados"
    },
    "innovation-proposal": {
        "name": "Innovation Proposal",
        "description": "From concept to market con validación integrada",
        "focus": "Propuesta de innovación con feasibility y business case"
    },
    "custom": {
        "name": "Custom Diagram",
        "description": "Diagrama personalizado",
        "focus": "Diagrama general con mejores prácticas de AInstein"
    }
}

# ---------------------------------------------------
# SISTEMA DE VALIDACIÓN Y SANITIZACIÓN PARA KROKI
# ---------------------------------------------------

class MermaidValidator:
    """Validador y sanitizador especializado para compatibilidad total con Kroki.io"""
    
    @staticmethod
    def sanitize_text(text: str) -> str:
        """Sanitiza texto específicamente para compatibilidad con Kroki.io"""
        
        # PASO 1: Mapeo de caracteres especiales (basado en limitaciones de Kroki)
        char_map = {
            # Acentos (causan errores de parsing en Kroki)
            'á': 'a', 'é': 'e', 'í': 'i', 'ó': 'o', 'ú': 'u',
            'Á': 'A', 'É': 'E', 'Í': 'I', 'Ó': 'O', 'Ú': 'U',
            'à': 'a', 'è': 'e', 'ì': 'i', 'ò': 'o', 'ù': 'u',
            'À': 'A', 'È': 'E', 'Ì': 'I', 'Ò': 'O', 'Ù': 'U',
            'â': 'a', 'ê': 'e', 'î': 'i', 'ô': 'o', 'û': 'u',
            'Â': 'A', 'Ê': 'E', 'Î': 'I', 'Ô': 'O', 'Û': 'U',
            'ä': 'a', 'ë': 'e', 'ï': 'i', 'ö': 'o', 'ü': 'u',
            'Ä': 'A', 'Ë': 'E', 'Ï': 'I', 'Ö': 'O', 'Ü': 'U',
            # Eñes (problemáticas en Kroki)
            'ñ': 'n', 'Ñ': 'N',
            # Otros caracteres latinos
            'ç': 'c', 'Ç': 'C',
            # Comillas especiales (causan problemas de parsing)
            '"': '"', '"': '"', ''': "'", ''': "'", '`': "'",
            # Guiones especiales
            '–': '-', '—': '-', 
            # Caracteres que rompen el parsing de Kroki
            '…': '...', '©': '(c)', '®': '(r)', '™': '(tm)',
            # Símbolos matemáticos problemáticos
            '°': 'deg', '±': 'mas-menos', '×': 'x', '÷': 'div',
            # CARACTERES CRÍTICOS QUE CAUSAN HTTP 400 EN KROKI
            '(': '', ')': '', '[': '', ']': '',  # Paréntesis y corchetes en texto
            '{': '', '}': '', '<': '', '>': '',  # Llaves y menor/mayor
            '|': ' ', '\\': ' ', '/': ' ',       # Barras
            '&': 'y', '%': 'pct', '$': 'USD',    # Símbolos especiales
            '@': 'at', '#': 'num', '*': 'x',     # Más símbolos
            '+': 'mas', '=': 'igual', '^': '',   # Operadores
            '~': '', '!': '', '?': '',           # Puntuación problemática
            ';': '', ':': ' ', ',': ' ', '.': ' ' # Puntuación
        }
        
        # PASO 2: Aplicar mapeo
        for char, replacement in char_map.items():
            text = text.replace(char, replacement)
        
        # PASO 3: Eliminar TODOS los caracteres no ASCII (restricción de Kroki)
        text = ''.join(char for char in text if ord(char) < 128)
        
        # PASO 4: Solo permitir caracteres muy seguros para Kroki
        # Basado en la documentación: solo letras, números, espacios y guiones
        text = re.sub(r'[^a-zA-Z0-9\s\-_]', '', text)
        
        # PASO 5: Limpiar espacios múltiples y normalizar
        text = re.sub(r'\s+', ' ', text).strip()
        
        # PASO 6: Limitar longitud (Kroki reporta cortes en textos largos)
        if len(text) > 25:  # Reducido para evitar cortes reportados en GitHub
            text = text[:22] + '...'
        
        # PASO 7: Verificar que no esté vacío
        if not text or text.isspace():
            text = "Elemento"
            
        return text
    
    @staticmethod
    def validate_syntax(mermaid_code: str) -> tuple[bool, str]:
        """Validación básica de sintaxis Mermaid"""
        lines = mermaid_code.strip().split('\n')
        errors = []
        
        # Verificar que empiece con graph
        if not any(line.strip().startswith('graph ') for line in lines[:3]):
            errors.append("Código debe empezar con 'graph TD' o similar")
        
        # Verificar balance de corchetes y paréntesis
        brackets = 0
        parentheses = 0
        for i, line in enumerate(lines, 1):
            brackets += line.count('[') - line.count(']')
            parentheses += line.count('(') - line.count(')')
            
            # Verificar caracteres problemáticos
            if re.search(r'[^\x00-\x7F]', line):
                errors.append(f"Línea {i}: Contiene caracteres no ASCII")
        
        if brackets != 0:
            errors.append("Corchetes desbalanceados")
        if parentheses != 0:
            errors.append("Paréntesis desbalanceados")
        
        return len(errors) == 0, "; ".join(errors)
    
    @staticmethod
    def sanitize_mermaid_code(mermaid_code: str) -> str:
        """Sanitización completa específica para restricciones de Kroki"""
        lines = mermaid_code.strip().split('\n')
        sanitized_lines = []
        
        for line in lines:
            # Eliminar líneas que causan problemas conocidos en Kroki
            line_clean = line.strip()
            
            # Filtrar líneas problemáticas documentadas
            if any(problematic in line_clean.lower() for problematic in [
                'break',  # Causa HTTP 400 según GitHub issue #1366
                '\\n',    # Problemas con saltos de línea según issue #1632
                '<br>',   # También problemático según documentación
                '%%{',    # Configuraciones deshabilitadas por seguridad
                'securityLevel', 'maxTextSize', 'secure', 'startOnLoad'  # Opciones deshabilitadas
            ]):
                continue
            
            # Sanitizar texto en la línea
            if line_clean:
                # Aplicar sanitización de texto a contenido de nodos
                sanitized_line = MermaidValidator.sanitize_text(line_clean)
                
                # Reconstruir sintaxis básica si es necesario
                if '[' in line and ']' in line:
                    # Es un nodo, asegurar formato correcto
                    parts = line.split('[')
                    if len(parts) >= 2:
                        node_id = parts[0].strip()
                        content_part = '['.join(parts[1:])
                        if ']' in content_part:
                            content = content_part.split(']')[0]
                            content_clean = MermaidValidator.sanitize_text(content)
                            sanitized_line = f"{node_id}[{content_clean}]"
                
                if sanitized_line and not sanitized_line.isspace():
                    sanitized_lines.append(sanitized_line)
        
        result = '\n'.join(sanitized_lines)
        
        # Asegurar que empiece con graph TD
        if not result.strip().startswith('graph '):
            result = 'graph TD\n' + result
            
        return result.strip()

# ---------------------------------------------------
# FUNCIÓN DE LIMPIEZA DE CÓDIGO
# ---------------------------------------------------

def clean_mermaid_code(raw_code: str) -> str:
    """Limpia agresivamente el código Mermaid de configuraciones problemáticas para Kroki"""
    lines = raw_code.strip().split('\n')
    clean_lines = []
    
    skip_until_end = False
    
    for line in lines:
        line = line.strip()
        
        # Saltar bloques de código markdown
        if line.startswith('```'):
            if '```' in line[3:]:  # Línea completa con ```mermaid código ```
                content = line[3:]
                if content.startswith('mermaid'):
                    content = content[7:]
                if content.endswith('```'):
                    content = content[:-3]
                if content.strip():
                    clean_lines.append(content.strip())
            else:
                skip_until_end = not skip_until_end
            continue
            
        if skip_until_end:
            continue
            
        # Eliminar configuraciones problemáticas conocidas de Kroki
        if any(problematic in line for problematic in [
            '%%{init', 'init:', 'theme:', 'themeVariables', 
            'flowchart TD', 'flowchart LR', 'break',
            'securityLevel', 'maxTextSize', 'secure', 'startOnLoad'
        ]):
            continue
            
        # Convertir flowchart a graph
        if line.startswith('flowchart '):
            line = line.replace('flowchart ', 'graph ')
            
        # Limpiar y agregar línea válida
        if line and not line.startswith('%%'):
            clean_lines.append(line)
    
    result = '\n'.join(clean_lines)
    
    # Asegurar que empiece con graph TD
    if not result.strip().startswith('graph '):
        result = 'graph TD\n' + result
        
    return result.strip()

# ---------------------------------------------------
# PROMPT PRINCIPAL OPTIMIZADO PARA KROKI
# ---------------------------------------------------

AINSTEIN_MERMAID_GENERATION_PROMPT_TEMPLATE = """
Eres un experto en crear diagramas Mermaid compatibles al 100% con la API de Kroki, enfocándote en representar RELACIONES CLARAS entre PROCESOS y RECURSOS.

# OBJETIVO PRINCIPAL
Crear código Mermaid que funcione perfectamente en Kroki.io, donde las FLECHAS indican relaciones específicas, los NODOS representan procesos o recursos, y las AGRUPACIONES muestran elementos relacionados con diferentes tipos de líneas según la fuerza de la relación.

# RESTRICCIONES CRÍTICAS DE KROKI (OBLIGATORIO CUMPLIR)
1. **NO usar saltos de línea**: Ni \\n ni <br> en texto de nodos
2. **NO usar break**: La palabra break causa error HTTP 400
3. **NO usar círculos**: Evitar (( )) que causan problemas de renderizado
4. **Texto corto**: Máximo 25 caracteres por nodo para evitar cortes
5. **NO caracteres especiales**: Solo ASCII básico (a-z, A-Z, 0-9, espacios, guiones)

# REPRESENTACIÓN DE NODOS: PROCESOS Y RECURSOS
- **[Proceso Core]** - Rectángulos para procesos principales/actividades críticas
- **[/Recurso Input/]** - Paralelogramos para recursos de entrada (datos, materiales, personas)
- **[Recurso Output/]** - Hexágonos para recursos de salida (productos, informes, resultados)
- **{Decision Process}** - Rombos para procesos de decisión/evaluación
- **[[Proceso Validacion]]** - Rectángulos dobles para procesos de validación/verificación
- **>Resultado Final]** - Banderas para outcomes/resultados críticos

# SISTEMA DE RELACIONES CON DIFERENTES TIPOS DE LÍNEAS
## RELACIONES FUERTES (Dependencias críticas, flujo principal)
- **-->** Relación directa fuerte (stroke-width:4px, color intenso)
- **==>** Relación crítica/obligatoria (stroke-width:5px)

## RELACIONES MEDIAS (Flujo secundario, dependencias moderadas)  
- **-.->** Relación indirecta/condicional (stroke-width:2px, punteado)
- **--->** Relación de soporte (stroke-width:3px)

## RELACIONES DÉBILES (Información, opcional, feedback)
- **..->** Relación informativa (stroke-width:1px, puntos)
- **<-->** Relación bidireccional/feedback (stroke-width:2px)

# SISTEMA DE AGRUPACIÓN INTELIGENTE
Crear subgrafos cuando hay 3+ elementos relacionados:
- **Agrupación por FUNCIÓN**: Procesos del mismo dominio
- **Agrupación por FASE**: Elementos de la misma etapa temporal
- **Agrupación por TIPO**: Recursos similares o procesos equivalentes
- **Agrupación por SISTEMA**: Componentes del mismo sistema técnico

# COLORES PARA AGRUPACIÓN Y TIPO (PASTELES PROFESIONALES)
- **AZUL PASTEL**: #E3F2FD - Procesos core/principales
- **VERDE PASTEL**: #E8F5E8 - Recursos y validaciones
- **NARANJA PASTEL**: #FFF3E0 - Decisiones y bifurcaciones
- **PÚRPURA PASTEL**: #F3E5F5 - Innovación y desarrollo
- **ROSA PASTEL**: #FCE4EC - Resultados y métricas
- **GRIS PASTEL**: #F5F5F5 - Recursos de soporte

# ESTRUCTURA VISUAL PROFESIONAL CON RELACIONES CLARAS
```
graph TD
    %% RECURSOS DE ENTRADA
    A[/Concepto Inicial/]
    B[/Team Resources/]
    
    %% PROCESOS CORE
    C[Proceso Evaluacion]
    D{Decision Gate}
    E[Desarrollo MVP]
    F[[Validacion Tecnica]]
    
    %% RECURSOS DE SALIDA
    G[Producto Final/]
    H>Metricas Impacto]
    
    %% RELACIONES FUERTES (dependencias críticas)
    A ==> C
    C --> D
    D ==> E
    E --> F
    F ==> G
    
    %% RELACIONES MEDIAS (flujo de soporte)
    B -.-> C
    B -.-> E
    
    %% RELACIONES DÉBILES (información/feedback)
    F ..-> C
    G <--> H
    
    %% AGRUPACIÓN INTELIGENTE POR FUNCIÓN
    subgraph Fase_Conceptual
        A
        C
        D
    end
    
    subgraph Fase_Desarrollo
        E
        F
        B
    end
    
    subgraph Fase_Resultados
        G
        H
    end
    
    %% ESTILOS POR TIPO DE ELEMENTO
    classDef procesoCore fill:#E3F2FD,stroke:#1976D2,stroke-width:3px
    classDef recursoInput fill:#E8F5E8,stroke:#388E3C,stroke-width:2px
    classDef recursoOutput fill:#FCE4EC,stroke:#C2185B,stroke-width:2px
    classDef decision fill:#FFF3E0,stroke:#F57C00,stroke-width:3px
    classDef validacion fill:#F3E5F5,stroke:#7B1FA2,stroke-width:3px
    
    class C,E procesoCore
    class A,B recursoInput
    class G,H recursoOutput
    class D decision
    class F validacion
    
    %% ESTILOS DE LÍNEAS POR FUERZA DE RELACIÓN
    linkStyle 0 stroke-width:5px,stroke:#1976D2
    linkStyle 1 stroke-width:4px,stroke:#1976D2
    linkStyle 2 stroke-width:5px,stroke:#1976D2
    linkStyle 3 stroke-width:4px,stroke:#1976D2
    linkStyle 4 stroke-width:5px,stroke:#1976D2
    linkStyle 5 stroke-width:2px,stroke:#757575,stroke-dasharray: 5 5
    linkStyle 6 stroke-width:2px,stroke:#757575,stroke-dasharray: 5 5
    linkStyle 7 stroke-width:1px,stroke:#9E9E9E,stroke-dasharray: 2 2
    linkStyle 8 stroke-width:2px,stroke:#FF5722
```

# REGLAS DE AGRUPACIÓN INTELIGENTE
1. **Agrupación TEMPORAL**: Elementos de la misma fase/etapa del proceso
2. **Agrupación FUNCIONAL**: Procesos que realizan funciones similares
3. **Agrupación por SISTEMA**: Recursos o procesos del mismo sistema técnico
4. **Agrupación por DEPENDENCIA**: Elementos que dependen fuertemente entre sí
5. **Crear subgrafo si hay 3+ elementos relacionados en el mismo contexto**

# SEMÁNTICA DE RELACIONES (Flechas indican tipo de relación)
- **Dependencia crítica**: A ==> B (B no puede existir sin A)
- **Flujo principal**: A --> B (secuencia natural del proceso)
- **Soporte/Habilitador**: A -.-> B (A facilita o soporta B)
- **Información/Referencia**: A ..-> B (A informa o influye B)
- **Bidireccional/Feedback**: A <--> B (relación mutual o iterativa)

# PLANTILLA ESPECÍFICA
{{template_specific_instructions}}

# RESTRICCIONES SINTÁCTICAS ABSOLUTAS
1. Empezar con "graph TD"
2. Texto simple: solo letras, números, espacios, guiones
3. Sin paréntesis dobles (( )) - usar otras formas
4. Sin saltos de línea en texto de nodos
5. Nombres de subgrafos con guiones bajos
6. Máximo 25 caracteres por nodo
7. OBLIGATORIO: Incluir agrupaciones (subgrafos) cuando haya 3+ elementos relacionados
8. OBLIGATORIO: Usar diferentes tipos de líneas según fuerza de relación

# TAREA
Convierte este contenido en un diagrama Mermaid profesional con RELACIONES CLARAS, AGRUPACIONES INTELIGENTES y TIPOS DE LÍNEAS diferenciados:

{{user_task_content}}

# CRITERIOS DE ÉXITO
- Sintaxis 100% compatible con Kroki
- Nodos representan claramente PROCESOS o RECURSOS
- Flechas indican RELACIONES específicas con diferentes intensidades
- Agrupaciones (subgrafos) para elementos relacionados (3+ elementos)
- Colores agrupan por tipo de elemento (proceso/recurso/decisión)
- Tipos de líneas diferenciados por fuerza de relación
- Layout vertical optimizado con jerarquía visual clara

# RESPUESTA
Genera SOLO el código Mermaid sin explicaciones ni bloques de código.
"""

# ---------------------------------------------------
# EXTENSIONES ESPECÍFICAS POR TEMPLATE
# ---------------------------------------------------

TEMPLATE_EXTENSIONS = {
    "tech-troubleshooting": """
# INSTRUCCIONES ADICIONALES: TECHNICAL TROUBLESHOOTING
## NODOS - PROCESOS Y RECURSOS:
- [Proceso Diagnostico] para actividades de análisis técnico
- [/Sintoma Input/] para inputs de problemas reportados
- {Decision Problema} para bifurcaciones de diagnóstico
- [[Proceso Verificacion]] para checkpoints de validación
- [Solucion Aplicada/] para recursos de solución
- >Fix Implementado] para resultados finales

## RELACIONES POR TIPO:
- **Dependencia crítica (==>)**: Síntoma → Diagnóstico → Solución
- **Flujo principal (--->)**: Secuencia de troubleshooting
- **Soporte (-.->)**: Herramientas y recursos de apoyo
- **Feedback (<-->)**: Verificación de fixes
- **Información (..->)**: Logs, métricas, documentación

## AGRUPACIONES OBLIGATORIAS:
- **Fase_Deteccion**: Síntomas + Diagnóstico inicial
- **Fase_Analisis**: Procesos de investigación + herramientas
- **Fase_Resolucion**: Soluciones + validación + deployment

## COLORES: Azul para diagnóstico, naranja para decisiones, verde para soluciones, rosa para resultados
""",
    
    "env-impact": """
# INSTRUCCIONES ADICIONALES: ENVIRONMENTAL IMPACT
## NODOS - PROCESOS Y RECURSOS:
- [/Recurso Natural/] para entradas de materiales/energía
- [Proceso Transformacion] para actividades de manufactura/uso
- {Decision Impacto} para evaluaciones ambientales
- [[Proceso Medicion]] para validación de métricas
- [Residuo Output/] para outputs ambientales
- >Resultado Sostenible] para outcomes verdes

## RELACIONES POR TIPO:
- **Dependencia crítica (==>)**: Recursos → Procesos → Impactos
- **Flujo material (--->)**: Cadena de transformación
- **Influencia (-.->)**: Factores que afectan impacto
- **Ciclo (<-->)**: Procesos circulares, reciclaje
- **Monitoreo (..->)**: Medición y tracking

## AGRUPACIONES OBLIGATORIAS:
- **Entrada_Recursos**: Materiales + energía + agua
- **Proceso_Principal**: Transformación + manufactura
- **Evaluacion_Impacto**: Medición + análisis + decisiones
- **Salida_Ambiental**: Residuos + emisiones + productos

## COLORES: Verde para procesos sostenibles, azul para transformación, rosa para métricas
""",
    
    "eng-innovation": """
# INSTRUCCIONES ADICIONALES: ENGINEERING INNOVATION
## NODOS - PROCESOS Y RECURSOS:
- [/Concepto Inicial/] para ideas y conceptos
- [Proceso Desarrollo] para actividades de I+D
- {Gate Evaluacion} para puntos de decisión técnica/comercial
- [[Proceso Testing]] para testing y validación
- [Prototipo/] para recursos de desarrollo
- >Producto Innovador] para resultados finales

## RELACIONES POR TIPO:
- **Dependencia crítica (==>)**: Concepto → Gates → Desarrollo → Producto
- **Desarrollo (--->)**: Secuencia de innovación
- **Soporte técnico (-.->)**: Recursos, herramientas, expertise
- **Iteración (<-->)**: Feedback loops de mejora
- **Validación (..->)**: Testing y verificación

## AGRUPACIONES OBLIGATORIAS:
- **Conceptualizacion**: Ideas + análisis inicial + feasibility
- **Desarrollo_Tecnico**: I+D + prototipado + testing
- **Validacion_Comercial**: Gates + validación + go-to-market
- **Recursos_Soporte**: Team + herramientas + infraestructura

## COLORES: Púrpura para innovación, azul para desarrollo, verde para validación
""",
    
    "proposal-dev": """
# INSTRUCCIONES ADICIONALES: PROPOSAL DEVELOPMENT
## NODOS - PROCESOS Y RECURSOS:
- [/Requerimiento Cliente/] para inputs de stakeholders
- [Proceso Desarrollo] para actividades de creación de propuesta
- {Decision Aprobacion} para puntos de aprobación
- [[Proceso Revision]] para checkpoints de calidad
- [Propuesta Draft/] para deliverables intermedios
- >Propuesta Aprobada] para resultado final

## RELACIONES POR TIPO:
- **Dependencia crítica (==>)**: Requerimientos → Desarrollo → Aprobación
- **Proceso creativo (--->)**: Flujo de desarrollo de propuesta
- **Input de stakeholders (-.->)**: Feedback y requerimientos
- **Revisión iterativa (<-->)**: Ciclos de mejora
- **Validación (..->)**: Reviews y checkpoints

## AGRUPACIONES OBLIGATORIAS:
- **Captura_Requerimientos**: Stakeholders + necesidades + contexto
- **Desarrollo_Propuesta**: Creación + estructuración + contenido
- **Validacion_Calidad**: Revisión + aprobación + refinamiento
- **Recursos_Soporte**: Team + templates + herramientas

## COLORES: Azul para desarrollo, naranja para decisiones, verde para validación, rosa para resultados
""",
    
    "tech-architecture": """
# INSTRUCCIONES ADICIONALES: TECH ARCHITECTURE
## NODOS - PROCESOS Y RECURSOS:
- [/Requerimiento Sistema/] para inputs funcionales/no-funcionales
- [Proceso Diseño] para actividades de arquitectura
- {Decision Tecnologia} para selección de tech stack
- [[Proceso Validacion]] para tests de rendimiento/integración
- [Componente Sistema/] para elementos arquitectónicos
- >Sistema Desplegado] para resultado operacional

## RELACIONES POR TIPO:
- **Dependencia crítica (==>)**: Requerimientos → Diseño → Componentes → Sistema
- **Flujo arquitectónico (--->)**: Secuencia de construcción
- **Integración (-.->)**: APIs, interfaces, conectores
- **Comunicación (<-->)**: Intercambio de datos bidireccional
- **Monitoreo (..->)**: Observabilidad y métricas

## AGRUPACIONES OBLIGATORIAS:
- **Frontend_Layer**: UI + UX + client-side components
- **Backend_Services**: APIs + business logic + microservices
- **Data_Layer**: Databases + cache + storage + analytics
- **Infrastructure_Layer**: Networking + security + deployment + monitoring

## COLORES: Azul para componentes core, verde para interfaces, púrpura para servicios, gris para infraestructura
""",
    
    "methodology-impl": """
# INSTRUCCIONES ADICIONALES: METHODOLOGY IMPLEMENTATION
## NODOS - PROCESOS Y RECURSOS:
- [/Situacion Actual/] para estado inicial de la organización
- [Proceso Implementacion] para etapas de adopción
- {Decision Adopcion} para puntos de evaluación de progreso
- [[Proceso Training]] para actividades de capacitación
- [Metodologia/] para frameworks y prácticas
- >Cultura Adoptada] para resultado organizacional

## RELACIONES POR TIPO:
- **Dependencia crítica (==>)**: Situación → Implementación → Adopción → Cultura
- **Flujo de cambio (--->)**: Secuencia de transformación
- **Soporte (-.->)**: Training, herramientas, coaching
- **Feedback (<-->)**: Ciclos de mejora continua
- **Medición (..->)**: KPIs y métricas de adopción

## AGRUPACIONES OBLIGATORIAS:
- **Evaluacion_Inicial**: Situación actual + gap analysis + planning
- **Implementacion_Gradual**: Fases + training + herramientas
- **Adopcion_Cultural**: Change management + coaching + medición
- **Recursos_Soporte**: Team + herramientas + documentación

## COLORES: Azul para implementación, verde para adopción, púrpura para cultura, rosa para resultados
""",
    
    "sustainable-tech": """
# INSTRUCCIONES ADICIONALES: SUSTAINABLE TECH SOLUTION
## NODOS - PROCESOS Y RECURSOS:
- [/Necesidad Tecnica/] para requerimientos técnicos
- [Proceso Desarrollo] para desarrollo tecnológico
- {Decision Sostenibilidad} para evaluación de trade-offs duales
- [[Proceso Validacion]] para checkpoints ambientales y técnicos
- [Solucion Dual/] para tecnología con criterios ambientales
- >Impacto Balanceado] para resultado sostenible

## RELACIONES POR TIPO:
- **Dependencia crítica (==>)**: Necesidad → Desarrollo → Validación → Impacto
- **Desarrollo tecnológico (--->)**: Flujo de innovación técnica
- **Consideración ambiental (-.->)**: Factores de sostenibilidad
- **Balance dual (<-->)**: Trade-offs técnico vs ambiental
- **Medición (..->)**: KPIs duales (técnicos + ambientales)

## AGRUPACIONES OBLIGATORIAS:
- **Desarrollo_Tecnico**: Innovación + implementación + testing técnico
- **Evaluacion_Ambiental**: Impacto + sostenibilidad + métricas verdes
- **Integracion_Dual**: Balance + trade-offs + optimización
- **Validacion_Total**: Testing técnico + validación ambiental

## COLORES: Púrpura para tecnología, verde para sostenibilidad, azul para integración, rosa para métricas duales
""",
    
    "innovation-proposal": """
# INSTRUCCIONES ADICIONALES: INNOVATION PROPOSAL
## NODOS - PROCESOS Y RECURSOS:
- [/Concepto Innovador/] para idea inicial
- [Proceso Feasibility] para evaluación técnica/comercial
- {Gate Validacion} para puntos de decisión críticos
- [[Proceso MVP]] para desarrollo de producto mínimo viable
- [Validacion Mercado/] para testing comercial
- [/Timeline Proyecto/] para planificación de implementación
- >Propuesta Aprobada] para resultado final

## RELACIONES POR TIPO:
- **Dependencia crítica (==>)**: Concepto → Feasibility → MVP → Validación → Implementación
- **Flujo de innovación (--->)**: Secuencia from concept to market
- **Soporte (-.->)**: Recursos, team, herramientas
- **Feedback de mercado (<-->)**: Iteración basada en validación
- **Informes (..->)**: Business case y documentación

## AGRUPACIONES OBLIGATORIAS:
- **Conceptualizacion**: Idea + análisis inicial + opportunity assessment
- **Desarrollo_MVP**: Prototipo + testing + validación técnica
- **Validacion_Comercial**: Market testing + business case + ROI
- **Implementacion_Plan**: Timeline + recursos + go-to-market

## COLORES: Púrpura para concepto, azul para desarrollo, verde para validación, rosa para implementación
"""
}

# ---------------------------------------------------
# MODELOS PYDANTIC PARA HERRAMIENTAS
# ---------------------------------------------------

class GenerateMermaidCodeArgs(BaseModel):
    reasoning: str = Field(..., description="Razón para generar o refinar el código Mermaid")
    user_task_content: str = Field(..., description="Contenido de la tarea del usuario")
    template_type: str = Field(..., description="Tipo de template AInstein a usar")
    previous_mermaid_code: Optional[str] = Field(None, description="Código anterior para refinamiento")
    visual_feedback: Optional[str] = Field(None, description="Feedback del análisis visual")
    iteration_count: int = Field(..., description="Número de iteración actual")

class RenderMermaidToImageArgs(BaseModel):
    reasoning: str = Field(..., description="Razón para renderizar")
    mermaid_code: str = Field(..., description="Código Mermaid a renderizar")
    iteration_count: int = Field(..., description="Número de iteración")

class AnalyzeMermaidImageArgs(BaseModel):
    reasoning: str = Field(..., description="Razón para analizar imagen")
    current_image_path: str = Field(..., description="Ruta de imagen actual")
    previous_image_path: Optional[str] = Field(None, description="Ruta imagen anterior")
    original_task_content: str = Field(..., description="Contenido original de la tarea")
    current_mermaid_code: str = Field(..., description="Código actual")
    iteration_count: int = Field(..., description="Número de iteración")

class CompleteTaskArgs(BaseModel):
    reasoning: str = Field(..., description="Razón para completar")
    final_mermaid_code: str = Field(..., description="Código Mermaid final")
    final_image_path: str = Field(..., description="Ruta imagen final")
    metrics_summary: str = Field(..., description="Resumen de métricas del proceso")

# ---------------------------------------------------
# FUNCIONES HERRAMIENTA OPTIMIZADAS
# ---------------------------------------------------

def auto_detect_template(content: str) -> str:
    """Detecta automáticamente el template más apropiado basado en el contenido"""
    content_lower = content.lower()
    
    # Palabras clave por template
    keywords = {
        "tech-troubleshooting": ["error", "bug", "debug", "troubleshoot", "fix", "issue", "performance", "crash"],
        "env-impact": ["environment", "sustainability", "carbon", "emission", "green", "eco", "lifecycle", "impact", "lca"],
        "eng-innovation": ["innovation", "prototype", "r&d", "research", "development", "product", "design"],
        "proposal-dev": ["proposal", "methodology", "framework", "stakeholder", "business case", "strategy"],
        "tech-architecture": ["architecture", "system", "component", "api", "database", "microservice", "integration"],
        "methodology-impl": ["implementation", "process", "methodology", "framework", "change management", "adoption"],
        "sustainable-tech": ["sustainable technology", "green tech", "environmental technology"],
        "innovation-proposal": ["innovation proposal", "concept to market", "feasibility study"]
    }
    
    scores = {}
    for template, words in keywords.items():
        score = sum(1 for word in words if word in content_lower)
        scores[template] = score
    
    # Retornar el template con mayor score, o custom si no hay coincidencias claras
    best_template = max(scores, key=scores.get)
    return best_template if scores[best_template] > 0 else "custom"

def generate_mermaid_code(
    user_task_content: str,
    template_type: str,
    iteration_count: int,
    code_model: str = DEFAULT_CODE_MODEL,
    previous_mermaid_code: Optional[str] = None,
    visual_feedback: Optional[str] = None,
    metrics: Optional[AgentMetrics] = None
) -> str:
    """Genera código Mermaid optimizado para Kroki usando el modelo especializado"""
    console.log(f"[blue]Generando código Mermaid (Iteración {iteration_count}, Modelo: {code_model})[/blue]")
    
    # Preparar prompt según iteración
    if iteration_count == 1:
        # Primera iteración: prompt completo con template
        template_instructions = TEMPLATE_EXTENSIONS.get(template_type, "")
        prompt_content = AINSTEIN_MERMAID_GENERATION_PROMPT_TEMPLATE.replace(
            "{{template_specific_instructions}}", template_instructions
        ).replace("{{user_task_content}}", user_task_content)
        
    else:
        # Iteración de refinamiento con enfoque en corrección sintáctica
        prompt_content = f"""
Eres un experto corrigiendo código Mermaid con base en feedback específico. 
PRIORIDAD #1: Corregir errores de sintaxis para Kroki.
PRIORIDAD #2: Mejorar diseño visual según feedback.

NUNCA uses:
- %%{{init}}%% configuraciones
- flowchart (solo graph TD)
- Caracteres especiales en texto de nodos
- Espacios en nombres de subgrafos
- Círculos (( )) que causan problemas

TAREA ORIGINAL: {user_task_content}

CÓDIGO ANTERIOR (con problemas):
{previous_mermaid_code}

FEEDBACK/ERROR:
{visual_feedback}

CORRECCIONES REQUERIDAS:
1. Si hay error de Kroki, corregir sintaxis PRIORITARIAMENTE
2. Usar SOLO "graph TD" (no flowchart)
3. NO usar configuraciones %%{{init}}%%
4. Texto de nodos sin caracteres especiales (sin acentos, paréntesis, símbolos)
5. Subgrafos con nombres simples (sin espacios)
6. Texto muy corto en nodos (máximo 25 caracteres)
7. Evitar círculos (( )) - usar formas estándar de flowchart

Genera código Mermaid corregido y limpio:
"""

    try:
        # Configurar mensajes según el modelo
        if code_model.startswith("o1"):
            # o1 models no soportan system role
            messages = [{"role": "user", "content": prompt_content}]
        else:
            # Otros modelos sí soportan system role
            system_message = """Eres un experto en generar código Mermaid técnico y VISUALMENTE ATRACTIVO para informes ejecutivos. 
            Tu código debe ser sintácticamente perfecto para Kroki y usar formas diferenciadas, colores agrupados, 
            y flechas de distinto tipo para crear diagramas profesionales y estéticamente impactantes."""
            messages = [
                {"role": "system", "content": system_message},
                {"role": "user", "content": prompt_content}
            ]
        
        response = client.chat.completions.create(
            model=code_model,
            messages=messages,
            # temperature=0.1,  # Muy baja para consistencia
        )
        
        generated_code = response.choices[0].message.content
        if not generated_code:
            return "Error: No se generó código Mermaid."
        
        # Limpiar formato agresivamente
        clean_code = clean_mermaid_code(generated_code)
        
        # Sanitizar y validar
        sanitized_code = MermaidValidator.sanitize_mermaid_code(clean_code)
        
        # Validación final
        is_valid, error_msg = MermaidValidator.validate_syntax(sanitized_code)
        if not is_valid:
            console.log(f"[yellow]Advertencia: {error_msg}[/yellow]")
        
        console.log(f"[green]Código generado y limpiado (Iteración {iteration_count})[/green]")
        console.log(f"[cyan]Primeras 300 chars:[/cyan]")
        print(f"  {sanitized_code[:300]}...")
        return sanitized_code
        
    except Exception as e:
        error_msg = f"Error al generar código Mermaid: {str(e)}"
        console.log("[red]Error en generación:[/red]")
        print(f"  {error_msg}")
        return error_msg

def render_mermaid_to_image(
    mermaid_code: str, 
    iteration_count: int,
    metrics: Optional[AgentMetrics] = None
) -> str:
    """Renderiza código Mermaid a imagen con manejo robusto de errores específicos de Kroki"""
    console.log(f"[blue]Renderizando imagen (Iteración {iteration_count})[/blue]")
    console.log(f"[cyan]Código a renderizar (primeras 200 chars):[/cyan]")
    print(f"  {mermaid_code[:200]}...")
    
    if metrics:
        metrics.render_attempts += 1
    
    try:
        response = requests.post(
            KROKI_URL, 
            data=mermaid_code.encode('utf-8'), 
            headers={'Content-Type': 'text/plain; charset=utf-8'},
            timeout=30
        )
        
        if response.status_code == 200:
            filename = f"ainstein_diagram_v{iteration_count}_{uuid.uuid4().hex[:8]}.png"
            image_path = os.path.join(IMAGE_DIR, filename)
            
            with open(image_path, "wb") as f:
                f.write(response.content)
            
            console.log(f"[green]Imagen guardada: {image_path}[/green]")
            return image_path
            
        else:
            if metrics:
                metrics.kroki_errors += 1
            
            error_text = response.text
            console.log(f"[red]Error {response.status_code} de Kroki:[/red]")
            print(f"  {error_text[:300]}")
            
            # Parsear error para feedback específico basado en problemas conocidos de Kroki
            error_feedback = f"""ERROR DE RENDERIZADO KROKI:
Status: {response.status_code}
Mensaje: {error_text[:500]}

CODIGO PROBLEMATICO (primeras 300 chars):
{mermaid_code[:300]}

PROBLEMAS CONOCIDOS DE KROKI A VERIFICAR:
1. CARACTERES NO ASCII: acentos (áéíóú), eñes (ñ), símbolos especiales
2. SENTENCIAS PROBLEMÁTICAS: break, \\n, <br> en texto de nodos
3. CONFIGURACIONES DESHABILITADAS: init, securityLevel, maxTextSize
4. CÍRCULOS PROBLEMÁTICOS: paréntesis dobles causan errores de renderizado
5. TEXTO LARGO: nodos con más de 25 caracteres pueden ser cortados
6. CARACTERES ESPECIALES: paréntesis, corchetes, barras en texto de nodos

ACCIONES CORRECTIVAS PRIORITARIAS:
1. Reemplazar TODOS los acentos por letras básicas
2. Eliminar palabras 'break' si existen
3. Simplificar texto de nodos a máximo 25 caracteres ASCII
4. Cambiar círculos por rectángulos o rombos
5. Remover configuraciones init si existen
6. Usar solo caracteres a-z, A-Z, 0-9, espacios, guiones

Este error debe ser corregido antes de continuar."""
            
            return f"RENDER_ERROR: {error_feedback}"
            
    except Exception as e:
        if metrics:
            metrics.kroki_errors += 1
        error_msg = f"Error de conexión con Kroki: {str(e)}"
        console.log("[red]Error de conexión:[/red]")
        print(f"  {error_msg}")
        return f"CONNECTION_ERROR: {error_msg}"

def analyze_mermaid_image(
    current_image_path: str,
    original_task_content: str,
    current_mermaid_code: str,
    iteration_count: int,
    vision_model: str = DEFAULT_VISION_MODEL,
    previous_image_path: Optional[str] = None,
    metrics: Optional[AgentMetrics] = None
) -> str:
    """Analiza imagen con enfoque en convenciones de flowchart y diseño profesional"""
    console.log(f"[blue]Analizando imagen (Iteración {iteration_count}, Modelo: {vision_model})[/blue]")
    
    if not os.path.exists(current_image_path):
        return "ERROR: Archivo de imagen no encontrado"
    
    # Codificar imagen actual
    try:
        with open(current_image_path, "rb") as img_file:
            current_base64 = base64.b64encode(img_file.read()).decode('utf-8')
    except Exception as e:
        return f"ERROR: No se pudo leer imagen actual: {e}"
    
    # Preparar contenido para análisis visual
    vision_content = []
    
    # Prompt optimizado para calidad visual y convenciones de flowchart
    analysis_prompt = f"""Eres un experto en análisis visual de diagramas de flujo técnicos para informes ejecutivos de AInstein, enfocándote en CLARIDAD DE RELACIONES y AGRUPACIONES INTELIGENTES.

TAREA ORIGINAL: {original_task_content}

EVALÚA LA IMAGEN ACTUAL según estos criterios específicos:

1. **CLARIDAD DE NODOS (Procesos vs Recursos)**:
   - ¿Los nodos representan claramente PROCESOS (actividades) o RECURSOS (inputs/outputs)?
   - ¿Usa formas apropiadas? (rectángulos=procesos, paralelogramos=recursos, rombos=decisiones)
   - ¿EVITA círculos que causan problemas de renderizado?
   - ¿Los textos son descriptivos del tipo de elemento?

2. **CLARIDAD DE RELACIONES (Flechas indican tipo específico)**:
   - ¿Las flechas indican RELACIONES específicas (dependencia, flujo, soporte, feedback)?
   - ¿Usa tipos de líneas diferenciados por fuerza de relación?
   - ¿Las líneas críticas son más gruesas que las de soporte?
   - ¿Se distingue visualmente el flujo principal vs secundario?

3. **AGRUPACIONES INTELIGENTES**:
   - ¿Agrupa elementos relacionados en subgrafos cuando hay 3+ elementos?
   - ¿Las agrupaciones son lógicas (por función, fase, sistema)?
   - ¿Los subgrafos tienen nombres descriptivos?
   - ¿Facilita la comprensión del diagrama?

4. **JERARQUÍA VISUAL DE RELACIONES**:
   - ¿Los tipos de línea reflejan importancia (crítica vs informativa)?
   - ¿Las dependencias críticas usan líneas más gruesas/intensas?
   - ¿Las relaciones de soporte están claramente diferenciadas?
   - ¿Los feedback loops son visualmente distintos?

5. **SISTEMA DE COLORES PROFESIONAL**:
   - ¿Usa colores pasteles para agrupar por tipo de elemento?
   - ¿Procesos, recursos y decisiones tienen colores coherentes?
   - ¿Evita colores muy intensos para informes ejecutivos?

6. **NARRATIVA COHERENTE**:
   - ¿El diagrama cuenta una historia clara de transformación?
   - ¿Se entiende el flujo de inputs → procesos → outputs?
   - ¿Las agrupaciones apoyan la comprensión del proceso general?

UMBRAL DE MEJORA: Solo recomendar cambios que aporten >25% de mejora en CLARIDAD RELACIONAL o AGRUPACIÓN.

ANÁLISIS COMPARATIVO:"""

    if previous_image_path and os.path.exists(previous_image_path):
        try:
            with open(previous_image_path, "rb") as img_file:
                previous_base64 = base64.b64encode(img_file.read()).decode('utf-8')
            
            analysis_prompt += """
- Compara IMAGEN_ACTUAL vs IMAGEN_ANTERIOR
- ¿Los cambios representan una mejora sustancial en convenciones de flowchart (>25%)?
- ¿Mejora la agrupación de colores y jerarquía visual?
- ¿Justifican el costo de otra iteración?"""
            
            vision_content.extend([
                {"type": "text", "text": "IMAGEN_ANTERIOR (para comparación):"},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{previous_base64}", "detail": DETAIL_LEVEL}}
            ])
        except Exception:
            analysis_prompt += "\n- No se pudo cargar imagen anterior para comparación"
    
    analysis_prompt += f"""

RESPUESTA REQUERIDA - Comenzar con UNA de estas etiquetas:

- **EXCELLENT**: Diagrama óptimo con nodos claramente definidos (procesos/recursos), relaciones específicas con tipos de líneas diferenciados, agrupaciones lógicas para elementos relacionados, y narrativa coherente. NO requiere cambios.

- **MINOR_IMPROVEMENT**: Cambios posibles pero <25% de mejora en claridad relacional. El diagrama ya tiene buena claridad de nodos, relaciones y agrupaciones. NO justifica otra iteración.

- **SIGNIFICANT_IMPROVEMENT**: Cambios >25% de mejora identificados en claridad relacional/agrupación. Especificar problemas específicos:
  * NODOS: Si no está claro qué son procesos vs recursos, especificar formas correctas
  * RELACIONES: Si faltan tipos de líneas diferenciados, especificar qué relaciones necesitan líneas más gruesas/punteadas
  * AGRUPACIONES: Si faltan subgrafos para elementos relacionados (3+), especificar agrupaciones lógicas
  * JERARQUÍA: Si no se distingue flujo principal vs secundario, especificar cambios de líneas
  * NARRATIVA: Si no se entiende la transformación input→proceso→output

Si es SIGNIFICANT_IMPROVEMENT, proporcionar feedback específico sobre:
1. Problemas exactos en claridad de nodos (proceso vs recurso)
2. Tipos de relaciones que necesitan líneas diferenciadas
3. Agrupaciones específicas que faltan (subgrafos para 3+ elementos)
4. Cambios concretos para mejorar jerarquía visual de relaciones
5. Justificación clara de por qué la mejora es >25% en claridad relacional

IMAGEN_ACTUAL a evaluar:"""

    vision_content.extend([
        {"type": "text", "text": analysis_prompt},
        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{current_base64}", "detail": DETAIL_LEVEL}}
    ])
    
    try:
        if metrics:
            metrics.add_analysis_cost()
        
        response = client.chat.completions.create(
            model=vision_model,
            messages=[{"role": "user", "content": vision_content}],
            max_tokens=600,
            temperature=0.1
        )
        
        feedback = response.choices[0].message.content
        console.log(f"[green]Análisis visual completado (Costo: ${COST_PER_IMAGE_ANALYSIS:.4f})[/green]")
        return feedback if feedback else "No se recibió feedback del análisis"
        
    except Exception as e:
        error_msg = f"Error en análisis visual: {str(e)}"
        console.log("[red]Error en análisis visual:[/red]") 
        print(f"  {error_msg}")
        return error_msg

def complete_task(
    final_mermaid_code: str, 
    final_image_path: str, 
    metrics_summary: str,
    metrics: Optional[AgentMetrics] = None
) -> str:
    """Finaliza la tarea con resumen de métricas"""
    if metrics:
        duration = metrics.get_duration()
        
        # Crear resumen completo de métricas
        complete_metrics_summary = f"""
MÉTRICAS DEL PROCESO:
- Duración total: {duration:.1f} segundos
- Iteraciones de refinamiento: {metrics.iterations_count}
- Intentos de renderizado: {metrics.render_attempts}
- Errores de Kroki: {metrics.kroki_errors}
- Costo total estimado: ${metrics.total_cost:.4f}
- Eficiencia: {metrics.render_attempts - metrics.kroki_errors}/{metrics.render_attempts} renders exitosos
"""
    else:
        complete_metrics_summary = metrics_summary
    
    # Mostrar resumen en consola
    table = Table(title="🎯 Tarea Completada - AInstein Mermaid Agent")
    table.add_column("Métrica", style="cyan")
    table.add_column("Valor", style="green")
    
    if metrics:
        duration = metrics.get_duration()
        table.add_row("Duración", f"{duration:.1f}s")
        table.add_row("Iteraciones", str(metrics.iterations_count))
        table.add_row("Renders", f"{metrics.render_attempts - metrics.kroki_errors}/{metrics.render_attempts}")
        table.add_row("Costo", f"${metrics.total_cost:.4f}")
    
    console.print(table)
    
    # Guardar código Mermaid final
    mermaid_filename = os.path.splitext(os.path.basename(final_image_path))[0] + ".mmd"
    mermaid_path = os.path.join(IMAGE_DIR, mermaid_filename)
    
    try:
        with open(mermaid_path, "w", encoding="utf-8") as f:
            f.write(final_mermaid_code)
        console.print(f"\n[green]📄 Código guardado en: {mermaid_path}[/green]")
    except Exception as e:
        console.print("[yellow]⚠️  No se pudo guardar archivo .mmd:[/yellow]")
        print(f"  {e}")
    
    console.print(f"[green]🖼️  Imagen final: {final_image_path}[/green]")
    
    return "Proceso completado exitosamente."

# ---------------------------------------------------
# FUNCIONES AUXILIARES
# ---------------------------------------------------

def process_user_input(prompt: str) -> str:
    """Procesa input del usuario (texto o archivo)"""
    if os.path.isfile(prompt):
        console.print(f"[blue]📄 Leyendo archivo: {prompt}[/blue]")
        try:
            with open(prompt, 'r', encoding='utf-8') as f:
                content = f.read()
            console.print(f"[green]✓ Archivo leído ({len(content)} caracteres)[/green]")
            return content
        except Exception as e:
            console.print("[red]Error leyendo archivo:[/red]")
            print(f"  {e}")
            return prompt
    return prompt.strip()

def display_template_info():
    """Muestra información de templates disponibles"""
    table = Table(title="🔧 Templates Especializados AInstein")
    table.add_column("Template", style="cyan")
    table.add_column("Descripción", style="white")
    table.add_column("Enfoque", style="green")
    
    for key, info in AINSTEIN_TEMPLATES.items():
        table.add_row(key, info["description"], info["focus"])
    
    console.print(table)

# ---------------------------------------------------
# HERRAMIENTAS PARA EL AGENTE
# ---------------------------------------------------

tools_definitions = [
    GenerateMermaidCodeArgs,
    RenderMermaidToImageArgs, 
    AnalyzeMermaidImageArgs,
    CompleteTaskArgs,
]

tools = [pydantic_function_tool(tool_def) for tool_def in tools_definitions]

# ---------------------------------------------------
# PROMPT DEL SISTEMA PARA EL AGENTE
# ---------------------------------------------------

AINSTEIN_AGENT_SYSTEM_PROMPT = """
Eres el AInstein Mermaid Visual Agent, especializado en crear diagramas Mermaid donde las RELACIONES son claras, los NODOS representan procesos/recursos específicos, y las AGRUPACIONES muestran elementos relacionados.

OBJETIVOS PRINCIPALES:
1. Generar diagramas compatibles 100% con Kroki.io (sin errores HTTP 400)
2. NODOS representan claramente PROCESOS (actividades) o RECURSOS (inputs/outputs)
3. FLECHAS indican RELACIONES específicas con tipos diferenciados por importancia
4. AGRUPACIONES (subgrafos) obligatorias cuando hay 3+ elementos relacionados
5. Jerarquía visual clara con diferentes tipos de líneas según fuerza de relación
6. Optimizar para informes ejecutivos verticales con máxima claridad

TIPOS DE NODOS OBLIGATORIOS:
- **[Proceso]**: Actividades, transformaciones, operaciones
- **[/Recurso Input/]**: Entradas, materiales, datos, personas
- **[Recurso Output/]**: Salidas, productos, resultados
- **{Decision}**: Puntos de evaluación o bifurcación
- **[[Validacion]]**: Checkpoints, verificaciones, gates
- **>Resultado]**: Outcomes finales, impactos

TIPOS DE RELACIONES OBLIGATORIAS:
- **==>**: Dependencia crítica (stroke-width:5px, color intenso)
- **-->**: Flujo principal (stroke-width:4px)
- **-.->**: Flujo de soporte/condicional (stroke-width:2px, punteado)
- **..->**: Información/influencia (stroke-width:1px, puntos)
- **<-->**: Bidireccional/feedback (stroke-width:2px)

AGRUPACIONES OBLIGATORIAS:
- Crear subgrafos cuando hay 3+ elementos relacionados
- Agrupar por: función, fase temporal, tipo de sistema, dependencias
- Nombres descriptivos con guiones bajos (ej: Fase_Desarrollo)

FLUJO DE TRABAJO OPTIMIZADO:
1. **GenerateMermaidCode**: Enfoque en relaciones claras y agrupaciones
2. **RenderMermaidToImage**: Manejo específico de errores de Kroki
3. **AnalyzeMermaidImage**: Validar claridad de relaciones y agrupaciones
4. **Refinamiento**: Priorizar mejoras >25% en claridad relacional
5. **CompleteTask**: Finalización con métricas de calidad

CRITERIOS DE DECISIÓN MEJORADOS:
- **EXCELLENT**: Relaciones claras, agrupaciones lógicas, tipos de líneas diferenciados
- **MINOR_IMPROVEMENT**: Mejoras <25% en claridad relacional
- **SIGNIFICANT_IMPROVEMENT**: Falta claridad en relaciones, agrupaciones o tipos de líneas
- **RENDER_ERROR**: Priorizar corrección de sintaxis Kroki

VALIDACIÓN DE CALIDAD:
- ¿Cada nodo representa claramente un proceso o recurso?
- ¿Las flechas indican relaciones específicas con tipos diferenciados?
- ¿Hay agrupaciones lógicas para elementos relacionados (3+)?
- ¿Los tipos de líneas reflejan la fuerza/importancia de cada relación?
- ¿El diagrama cuenta una historia coherente de transformación?

Mantén enfoque en CLARIDAD RELACIONAL y AGRUPACIÓN INTELIGENTE por encima de todo.
"""

# ---------------------------------------------------
# FUNCIÓN PRINCIPAL
# ---------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="AInstein Mermaid Visual Agent - Optimized para Kroki")
    parser.add_argument("-p", "--prompt", required=True, 
                       help="Texto o archivo con contenido a diagramar")
    parser.add_argument("-t", "--template", choices=list(AINSTEIN_TEMPLATES.keys()), 
                       default=None, help="Template específico (auto-detect si no se especifica)")
    parser.add_argument("-m", "--model", type=str, default=DEFAULT_CODE_MODEL,
                       help=f"Modelo OpenAI para generación de código (default: {DEFAULT_CODE_MODEL})")
    parser.add_argument("--vision-model", type=str, default=DEFAULT_VISION_MODEL,
                       help=f"Modelo OpenAI para análisis visual (default: {DEFAULT_VISION_MODEL})")
    parser.add_argument("--show-templates", action="store_true",
                       help="Mostrar templates disponibles y salir")
    parser.add_argument("--max-cost", type=float, default=DEFAULT_MAX_BUDGET,
                       help=f"Costo máximo permitido en USD (default: ${DEFAULT_MAX_BUDGET:.2f})")
    parser.add_argument("-i", "--max-iterations", type=int, default=MAX_REFINEMENT_ITERATIONS,
                       help=f"Máximo número de iteraciones de refinamiento (default: {MAX_REFINEMENT_ITERATIONS})")
    parser.add_argument("-v", "--verbose", action="store_true",
                       help="Mostrar información detallada del proceso")
    
    args = parser.parse_args()
    
    if args.show_templates:
        display_template_info()
        return
    
    # Inicializar métricas
    metrics = AgentMetrics()
    metrics.start_time = time.time()
    
    console.rule("[bold green]🚀 AInstein Mermaid Visual Agent v3 - Kroki Optimized[/bold green]")
    
    # Procesar input
    user_content = process_user_input(args.prompt)
    
    # Auto-detectar template si no se especifica
    template_type = args.template or auto_detect_template(user_content)
    
    # Mostrar configuración
    config_table = Table(title="⚙️ Configuración")
    config_table.add_column("Parámetro", style="cyan")
    config_table.add_column("Valor", style="white")
    
    config_table.add_row("Modelo Código", args.model)
    config_table.add_row("Modelo Visión", args.vision_model)
    config_table.add_row("Template", f"{template_type} ({'auto-detectado' if not args.template else 'especificado'})")
    config_table.add_row("Template Info", AINSTEIN_TEMPLATES[template_type]["description"])
    config_table.add_row("Detalle Visual", DETAIL_LEVEL)
    config_table.add_row("Max Iteraciones", str(args.max_iterations))
    config_table.add_row("Max Costo", f"${args.max_cost:.3f}")
    config_table.add_row("Caracteres", str(len(user_content)))
    
    console.print(config_table)
    console.print(f"\n[bold cyan]🎯 Iniciando generación compatible con Kroki...[/bold cyan]")
    
    # Variables de estado
    current_mermaid_code = None
    current_image_path = None
    previous_image_path = None
    iteration_count = 0
    
    # Mensajes para el agente
    messages = [
        {"role": "system", "content": AINSTEIN_AGENT_SYSTEM_PROMPT},
        {"role": "user", "content": f"""
Genera un diagrama Mermaid COMPATIBLE CON KROKI para AInstein con esta configuración:

CONTENIDO: {user_content}
TEMPLATE: {template_type}
MODELO_CÓDIGO: {args.model} (para generación de código)
MODELO_VISIÓN: {args.vision_model} (para análisis visual)
MAX_COSTO: ${args.max_cost}
MAX_ITERACIONES: {args.max_iterations}

PRIORIDADES KROKI:
1. Sintaxis 100% compatible (sin errores HTTP 400)
2. Formas estándar de flowchart (NO círculos problemáticos)
3. Colores pasteles para agrupación visual
4. Texto ultra-corto y ASCII (máx 25 chars por nodo)
5. Layout vertical para informes ejecutivos

Inicia con GenerateMermaidCode usando iteration_count=1.
"""}]
    
    # Mapeo de herramientas
    function_map = {
        "GenerateMermaidCodeArgs": lambda **kwargs: generate_mermaid_code(
            code_model=args.model, metrics=metrics, **kwargs
        ),
        "RenderMermaidToImageArgs": lambda **kwargs: render_mermaid_to_image(
            metrics=metrics, **kwargs
        ),
        "AnalyzeMermaidImageArgs": lambda **kwargs: analyze_mermaid_image(
            vision_model=args.vision_model, metrics=metrics, **kwargs
        ),
        "CompleteTaskArgs": lambda **kwargs: complete_task(
            metrics=metrics, **kwargs
        ),
    }
    
    # Límite de loops del agente (basado en iteraciones configuradas)
    max_loops = args.max_iterations * 4 + 5
    refinement_cycles_done = 0
    
    for loop_num in range(1, max_loops + 1):
        if args.verbose:
            console.rule(f"[yellow]Loop {loop_num}/{max_loops} (Costo: ${metrics.total_cost:.4f})[/yellow]")
        
        # Verificar límite de costo
        if metrics.total_cost >= args.max_cost:
            console.print(f"[red]⚠️  Límite de costo alcanzado: ${metrics.total_cost:.4f}[/red]")
            if current_mermaid_code and current_image_path:
                complete_task(current_mermaid_code, current_image_path, f"Límite de costo alcanzado", metrics)
            break
        
        try:
            response = client.chat.completions.create(
                model=args.vision_model,  # Usar modelo de visión para coordinación
                messages=messages,
                tools=tools,
                tool_choice="auto",
                temperature=0.1
            )
            
            message = response.choices[0].message
            messages.append(message)
            
            if message.tool_calls:
                for tool_call in message.tool_calls:
                    tool_name = tool_call.function.name
                    tool_args = json.loads(tool_call.function.arguments)
                    
                    if args.verbose:
                        console.print(f"[blue]🔧 {tool_name}[/blue]")
                    
                    # Ejecutar herramienta
                    if tool_name in function_map:
                        try:
                            # Preparar argumentos
                            func_kwargs = {k: v for k, v in tool_args.items() if k != 'reasoning'}
                            
                            if tool_name == "GenerateMermaidCodeArgs":
                                func_kwargs.update({
                                    'template_type': template_type,
                                    'previous_mermaid_code': current_mermaid_code,
                                })
                                iteration_count = tool_args.get('iteration_count', iteration_count + 1)
                                metrics.iterations_count = max(metrics.iterations_count, iteration_count)
                                
                            elif tool_name == "RenderMermaidToImageArgs":
                                # Asegurar que se pase el código Mermaid actual
                                if 'mermaid_code' not in func_kwargs and current_mermaid_code:
                                    func_kwargs['mermaid_code'] = current_mermaid_code
                                
                            elif tool_name == "AnalyzeMermaidImageArgs":
                                func_kwargs['previous_image_path'] = previous_image_path
                                if 'current_mermaid_code' not in func_kwargs and current_mermaid_code:
                                    func_kwargs['current_mermaid_code'] = current_mermaid_code
                                    
                            elif tool_name == "CompleteTaskArgs":
                                # Agregar metrics_summary si no está en los argumentos
                                if 'metrics_summary' not in func_kwargs:
                                    duration = metrics.get_duration()
                                    func_kwargs['metrics_summary'] = f"""Duración: {duration:.1f}s, Iteraciones: {metrics.iterations_count}, Costo: ${metrics.total_cost:.4f}"""
                                
                                result = function_map[tool_name](**func_kwargs)
                                console.print("[bold green]✅ Proceso completado por el agente[/bold green]")
                                return
                            
                            # Ejecutar función
                            result = function_map[tool_name](**func_kwargs)
                            
                            # Procesar resultado según el tipo de herramienta
                            if tool_name == "GenerateMermaidCodeArgs":
                                current_mermaid_code = result
                                result_content = f"Código Mermaid generado exitosamente (Iteración {iteration_count})"
                                
                            elif tool_name == "RenderMermaidToImageArgs":
                                if result.startswith("RENDER_ERROR:") or result.startswith("CONNECTION_ERROR:"):
                                    # Error de renderizado - usar como feedback para refinamiento
                                    result_content = result
                                else:
                                    previous_image_path = current_image_path
                                    current_image_path = result
                                    result_content = f"Imagen renderizada exitosamente: {result}"
                                    
                            elif tool_name == "AnalyzeMermaidImageArgs":
                                result_content = str(result)
                                # Procesar feedback visual
                                if result:
                                    feedback_upper = result.upper()
                                    if feedback_upper.startswith("EXCELLENT") or feedback_upper.startswith("MINOR_IMPROVEMENT"):
                                        console.print(f"[green]Análisis visual indica: {result.split('.')[0]}. Finalizando refinamiento.[/green]")
                                        if current_mermaid_code and current_image_path:
                                            summary = f"Diagrama finalizado. Feedback visual: {result.split('.')[0]}"
                                            complete_task(current_mermaid_code, current_image_path, summary, metrics)
                                            console.print("[bold green]Agente finalizado.[/bold green]")
                                            return
                                    elif feedback_upper.startswith("SIGNIFICANT_IMPROVEMENT"):
                                        refinement_cycles_done += 1
                                        console.print(f"[yellow]Feedback visual indica SIGNIFICANT_IMPROVEMENT. Ciclos de refinamiento: {refinement_cycles_done}.[/yellow]")
                                
                            else:
                                result_content = str(result)
                            
                            # Agregar resultado a mensajes
                            messages.append({
                                "role": "tool",
                                "tool_call_id": tool_call.id,
                                "name": tool_name,
                                "content": result_content[:1000] + ("..." if len(str(result)) > 1000 else "")
                            })
                            
                        except Exception as e:
                            error_msg = f"Error ejecutando {tool_name}: {str(e)}"
                            console.print("[red]Error ejecutando herramienta:[/red]")
                            print(f"  {error_msg}")
                            messages.append({
                                "role": "tool",
                                "tool_call_id": tool_call.id,
                                "name": tool_name,
                                "content": error_msg
                            })
                    else:
                        console.print(f"[red]Herramienta desconocida: {tool_name}[/red]")
            
            elif message.content:
                console.print("[magenta]Respuesta del agente:[/magenta]")
                print(f"  {message.content}")
                break
            else:
                console.print("[yellow]Respuesta vacía del agente[/yellow]")
                break
            
            # Verificar límite de iteraciones
            if refinement_cycles_done >= args.max_iterations:
                console.print(f"[yellow]Límite de {args.max_iterations} iteraciones de refinamiento alcanzado.[/yellow]")
                if current_mermaid_code and current_image_path:
                    summary = f"Proceso finalizado tras alcanzar el límite de {args.max_iterations} iteraciones de refinamiento."
                    complete_task(current_mermaid_code, current_image_path, summary, metrics)
                elif current_mermaid_code:
                    summary = f"Proceso finalizado tras alcanzar el límite de {args.max_iterations} iteraciones. El último renderizado pudo haber fallado."
                    complete_task(current_mermaid_code, current_image_path or "Ultimo render fallido", summary, metrics)
                else:
                    console.print(f"[red]No se pudo completar la tarea al alcanzar el límite de {args.max_iterations} iteraciones de refinamiento.[/red]")
                break
                
        except Exception as e:
            console.print("[red]Error crítico en loop[/red]", f"{loop_num}: {str(e)}")
            break
    
    # Finalización de emergencia si no se completó normalmente
    if current_mermaid_code and current_image_path:
        console.print("[yellow]⚠️  Finalizando proceso por límite de loops[/yellow]")
        complete_task(current_mermaid_code, current_image_path, "Finalizado por límite de loops", metrics)
    else:
        console.print("[red]❌ Proceso terminado sin resultado exitoso[/red]")
        console.print(f"Costo total: ${metrics.total_cost:.4f}")

if __name__ == "__main__":
    main()