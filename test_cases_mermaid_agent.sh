#!/bin/bash

# -----------------------------------------------------------------------------
# Archivo de Casos de Prueba para sfa_mermaid_visual_agent_openai_v1.py
# -----------------------------------------------------------------------------
# Instrucciones:
# 1. Asegúrate de tener configurada tu OPENAI_API_KEY en un archivo .env
#    o como variable de entorno.
# 2. Puedes ejecutar este script completo con `bash test_cases_mermaid_agent.sh`
#    o copiar y pegar cada comando individualmente en tu terminal.
# 3. Revisa la carpeta `mermaid_images` para ver los resultados (imágenes .png y código .mmd).
# -----------------------------------------------------------------------------

echo "======================================================================"
echo "Iniciando Casos de Prueba para el Agente Mermaid Visual"
echo "Modelo por defecto: gpt-4o-mini (a menos que se especifique -m)"
echo "======================================================================"

# ---
# Caso 1: Diagrama de Flujo Muy Simple
# Objetivo: Probar la generación básica con pocas entidades y relaciones directas.
# Iteraciones de refinamiento: 1
# ---
echo -e "\n--- Caso 1: Diagrama de Flujo Muy Simple ---"
uv run sfa_mermaid_visual_agent_openai_v1.py \
-p "Proceso de login: Usuario ingresa credenciales -> Sistema valida credenciales -> Usuario accede al dashboard principal." \
-i 1

# ---
# Caso 2: Estructura Organizacional Simple
# Objetivo: Probar ramificaciones y una jerarquía simple.
# Iteraciones de refinamiento: 2
# ---
echo -e "\n--- Caso 2: Estructura Organizacional Simple ---"
uv run sfa_mermaid_visual_agent_openai_v1.py \
-p "Organigrama básico de una startup: CEO es el nodo principal. Del CEO dependen tres roles: CTO, CMO, y COO. El CTO gestiona al Equipo de Desarrollo. El CMO gestiona al Equipo de Marketing Digital." \
-i 2

# ---
# Caso 3: Plan de Proyecto con Decisiones y Acciones (Complejidad Media)
# Objetivo: Probar la correcta identificación y representación de nodos 'decision' y 'accion' y sus flujos.
# Iteraciones de refinamiento: 3
# ---
echo -e "\n--- Caso 3: Plan de Proyecto (Complejidad Media) ---"
uv run sfa_mermaid_visual_agent_openai_v1.py \
-p "Plan para lanzar una nueva app móvil: La decisión inicial es 'Investigar el Mercado'. Esto genera dos acciones: 'Realizar Encuestas a Usuarios' y 'Analizar Competencia Directa'. Ambas acciones contribuyen a la decisión 'Definir Características Clave'. A partir de esta definición, se realizan las acciones 'Desarrollar Prototipo Interactivo' y 'Diseñar UI/UX'. Estas dos acciones alimentan la acción 'Pruebas de Usuario con Prototipo'. El resultado de las pruebas lleva a la decisión final 'Lanzar Versión Beta' o 'Iterar Diseño'." \
-i 3

# ---
# Caso 4: Desafío al Límite de Nodos (solicitando más de 10 nodos)
# Objetivo: Observar cómo el LLM maneja la restricción interna de "No exceder 10 nodos en total".
# Iteraciones de refinamiento: 1 (para ver el intento inicial y un posible ajuste)
# ---
echo -e "\n--- Caso 4: Desafío al Límite de Nodos ---"
uv run sfa_mermaid_visual_agent_openai_v1.py \
-p "Flujo de trabajo de aprobación de documentos con 12 pasos explícitos: 1. Creación Borrador -> 2. Revisión Pares -> 3. Corrección Borrador -> 4. Envío a Supervisor -> 5. Revisión Supervisor -> 6. Ajustes Supervisor -> 7. Envío a Legal -> 8. Revisión Legal -> 9. Ajustes Legales -> 10. Aprobación Final -> 11. Archivado -> 12. Notificación." \
-i 1

# ---
# Caso 5: Solicitud con Elementos "NO INCLUIR" (personas, fechas)
# Objetivo: Verificar si el LLM filtra la información que el prompt interno le indica ignorar.
# Iteraciones de refinamiento: 2
# ---
echo -e "\n--- Caso 5: Solicitud con Elementos 'NO INCLUIR' ---"
uv run sfa_mermaid_visual_agent_openai_v1.py \
-p "Minuta de reunión del equipo Alfa del 20 de Julio: Juan Pérez (Desarrollador Principal) debe completar la Tarea_XYZ para el 15 de Agosto. María López (Diseñadora UX) revisará el diseño de la interfaz. Se tomó la decisión de usar el color corporativo #00A4EF para los botones principales. La acción concreta es implementar el nuevo flujo de registro de usuarios." \
-i 2

# ---
# Caso 6: Diagrama con Múltiples Ramificaciones y Reconexiones
# Objetivo: Probar la capacidad de manejar flujos más complejos y la correcta aplicación de tipos de flechas y relaciones.
# Iteraciones de refinamiento: 3
# ---
echo -e "\n--- Caso 6: Múltiples Ramificaciones y Reconexiones ---"
uv run sfa_mermaid_visual_agent_openai_v1.py \
-p "Proceso de desarrollo de una nueva funcionalidad de software: Inicia con 'Análisis de Requisitos del Cliente'. De aquí surgen dos ramas paralelas: 'Diseño de la Interfaz de Usuario (UI/UX)' y 'Diseño de la Arquitectura del Backend'. El 'Diseño UI/UX' lleva a la acción 'Desarrollo del Frontend'. El 'Diseño de la Arquitectura del Backend' lleva a la acción 'Desarrollo de Microservicios'. Ambas ramas de desarrollo, Frontend y Backend, convergen en la acción 'Integración de Componentes'. Tras la integración, se procede a 'Pruebas de Calidad (QA)'. Si las pruebas son exitosas, se toma la decisión 'Aprobar para Despliegue', que resulta en la acción 'Despliegue en Producción'. Si las pruebas fallan, se vuelve a la acción 'Corrección de Errores', que luego requiere nuevas 'Pruebas de Calidad (QA)'." \
-i 3

# ---
# Caso 7: Ejemplo Complejo de Planificación de Proyecto (Proyecto Fénix)
# Objetivo: Utilizar el prompt complejo previamente discutido para una prueba robusta.
# Iteraciones de refinamiento: 3 (o 4 para ver si sigue mejorando)
# ---
echo -e "\n--- Caso 7: Ejemplo Complejo (Proyecto Fénix) ---"
uv run sfa_mermaid_visual_agent_openai_v1.py \
-p "Resumen de la reunión de lanzamiento del Proyecto Fénix: El objetivo principal es rediseñar la plataforma de e-commerce. Se tomó la decisión de adoptar una arquitectura de microservicios. Las acciones clave son: 1. Definir el API Gateway (requiere aprobación del equipo de arquitectura). 2. Desarrollar el microservicio de Usuarios (depende de la definición del API Gateway). 3. Diseñar la nueva interfaz de usuario (puede iniciar en paralelo). Una decisión secundaria fue investigar soluciones de búsqueda semántica, lo que genera la acción de evaluar dos proveedores de búsqueda. Esta evaluación contribuirá a la selección final de tecnología para el microservicio de Catálogo, que es otra acción principal. Finalmente, se acordó establecer sprints quincenales para el seguimiento." \
-m gpt-4o \
-i 3

# ---
# Caso 8: Solicitud muy ambigua o poco clara
# Objetivo: Observar cómo reacciona el agente a un prompt vago.
# Iteraciones de refinamiento: 1
# ---
echo -e "\n--- Caso 8: Solicitud Ambigua ---"
uv run sfa_mermaid_visual_agent_openai_v1.py \
-p "Necesito un diagrama de mis ideas sobre el futuro. Es importante." \
-i 1

# ---
# Caso 9: Mínimas iteraciones de refinamiento (casi solo generación inicial)
# Objetivo: Ver el resultado con el mínimo ciclo de feedback visual.
# Iteraciones de refinamiento: 0
# ---
echo -e "\n--- Caso 9: Mínimas Iteraciones de Refinamiento ---"
uv run sfa_mermaid_visual_agent_openai_v1.py \
-p "Diagrama simple de tres pasos: A resulta en B, y B resulta en C." \
-i 0

# ---
# Caso 10: Solicitud que podría interpretarse con ciclos (aunque el prompt interno los desaconseja)
# Objetivo: Ver si el LLM evita los ciclos o cómo los representa si intenta incluirlos.
# Iteraciones de refinamiento: 2
# ---
echo -e "\n--- Caso 10: Posible Ciclo ---"
uv run sfa_mermaid_visual_agent_openai_v1.py \
-p "Proceso de mejora continua: Planificar -> Hacer -> Verificar. Si Verificar no es OK, volver a Planificar. Si Verificar es OK -> Actuar. Actuar puede llevar a un nuevo Planificar." \
-i 2


echo -e "\n======================================================================"
echo "Casos de Prueba Finalizados."
echo "Revisa la carpeta 'mermaid_images' para los diagramas generados."
echo "======================================================================"
