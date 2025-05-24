# Ejemplo de Prueba para sfa_mermaid_visual_agent_openai_v3_fixed.py

Este archivo contiene un ejemplo de prompt y el comando para probar el agente `sfa_mermaid_visual_agent_openai_v3_fixed.py`. Está diseñado para evaluar varias características clave del agente, como la interpretación de componentes, relaciones, agrupaciones y el uso de templates especializados.

## Prompt de Ejemplo (para Arquitectura Técnica)

El siguiente prompt describe un "Sistema de Gestión de Flotas Inteligente" y está diseñado para ser utilizado con el template `tech-architecture`.

```text
Sistema de Gestión de Flotas Inteligente para "Logística Óptima S.A.":

Componentes Principales:
1.  Dispositivos IoT en Vehículos: Sensores GPS, OBD-II para telemetría (velocidad, consumo, fallos), comunicación LTE. Recurso de entrada.
2.  Plataforma de Ingesta de Datos: Recibe datos de IoT vía MQTT, valida y normaliza. Proceso Core.
3.  Motor de Procesamiento de Eventos: Analiza datos en tiempo real (ej. geofencing, alertas de velocidad, mantenimiento predictivo) usando Apache Flink. Proceso Core.
4.  Almacenamiento de Datos Históricos: Series temporales en InfluxDB para telemetría, datos relacionales en PostgreSQL para vehículos, conductores y rutas. Recurso.
5.  API Backend: Expone funcionalidades a aplicaciones cliente (RESTful, GraphQL) construida con Python/FastAPI. Proceso Core.
6.  Aplicación Web de Administración: Dashboard para gestores de flota (visualización de mapas, informes, gestión de alertas) desarrollada en React. Proceso.
7.  Aplicación Móvil para Conductores: Notificaciones, optimización de rutas, comunicación con central, desarrollada en Flutter. Proceso.
8.  Módulo de Optimización de Rutas: Algoritmo que calcula rutas eficientes basado en tráfico, entregas y restricciones vehiculares. Proceso de Decisión.
9.  Servicio de Notificaciones: Envía alertas (email, SMS, push) a gestores y conductores. Proceso de Soporte.
10. Integración con Sistemas Externos: API de Mapas (ej. Mapbox), API de Tráfico en tiempo real. Recurso Externo.

Flujos Clave y Relaciones:
-   IoT (crítico) ==> Plataforma Ingesta
-   Plataforma Ingesta (crítico) --> Motor Procesamiento
-   Motor Procesamiento (crítico) --> Almacenamiento Histórico
-   Motor Procesamiento (soporte) -.-> Servicio Notificaciones
-   Motor Procesamiento (info) ..-> API Backend (para estado en tiempo real)
-   API Backend (crítico) <--> Almacenamiento Histórico (lectura/escritura)
-   API Backend (crítico) --> Aplicación Web
-   API Backend (crítico) --> Aplicación Móvil
-   API Backend (soporte) -.-> Módulo Optimización Rutas
-   Módulo Optimización Rutas (decisión) --> API Backend (para actualizar rutas)
-   API Backend (soporte) -.-> Integración Sistemas Externos

Agrupaciones Sugeridas:
-   Capa_IoT_Ingesta: Dispositivos IoT, Plataforma Ingesta
-   Capa_Procesamiento_Almacenamiento: Motor Procesamiento, Almacenamiento Histórico
-   Capa_Aplicaciones_API: API Backend, App Web, App Móvil, Módulo Optimización, Servicio Notificaciones
-   Servicios_Externos: Integración Sistemas Externos

Consideraciones: Escalabilidad, seguridad de datos, baja latencia para alertas.
```

## Comando para Ejecutar la Prueba

Asegúrate de reemplazar `'TU_OPENAI_API_KEY_AQUI'` con tu clave de API de OpenAI real antes de ejecutar el comando.

```bash
export OPENAI_API_KEY='TU_OPENAI_API_KEY_AQUI'

uv run sfa_mermaid_visual_agent_openai_v3_fixed.py \
    -p "Sistema de Gestión de Flotas Inteligente para \"Logística Óptima S.A.\": Componentes Principales: 1. Dispositivos IoT en Vehículos: Sensores GPS, OBD-II para telemetría (velocidad, consumo, fallos), comunicación LTE. Recurso de entrada. 2. Plataforma de Ingesta de Datos: Recibe datos de IoT vía MQTT, valida y normaliza. Proceso Core. 3. Motor de Procesamiento de Eventos: Analiza datos en tiempo real (ej. geofencing, alertas de velocidad, mantenimiento predictivo) usando Apache Flink. Proceso Core. 4. Almacenamiento de Datos Históricos: Series temporales en InfluxDB para telemetría, datos relacionales en PostgreSQL para vehículos, conductores y rutas. Recurso. 5. API Backend: Expone funcionalidades a aplicaciones cliente (RESTful, GraphQL) construida con Python/FastAPI. Proceso Core. 6. Aplicación Web de Administración: Dashboard para gestores de flota (visualización de mapas, informes, gestión de alertas) desarrollada en React. Proceso. 7. Aplicación Móvil para Conductores: Notificaciones, optimización de rutas, comunicación con central, desarrollada en Flutter. Proceso. 8. Módulo de Optimización de Rutas: Algoritmo que calcula rutas eficientes basado en tráfico, entregas y restricciones vehiculares. Proceso de Decisión. 9. Servicio de Notificaciones: Envía alertas (email, SMS, push) a gestores y conductores. Proceso de Soporte. 10. Integración con Sistemas Externos: API de Mapas (ej. Mapbox), API de Tráfico en tiempo real. Recurso Externo. Flujos Clave y Relaciones: - IoT (crítico) ==> Plataforma Ingesta - Plataforma Ingesta (crítico) --> Motor Procesamiento - Motor Procesamiento (crítico) --> Almacenamiento Histórico - Motor Procesamiento (soporte) -.-> Servicio Notificaciones - Motor Procesamiento (info) ..-> API Backend (para estado en tiempo real) - API Backend (crítico) <--> Almacenamiento Histórico (lectura/escritura) - API Backend (crítico) --> Aplicación Web - API Backend (crítico) --> Aplicación Móvil - API Backend (soporte) -.-> Módulo Optimización Rutas - Módulo Optimización Rutas (decisión) --> API Backend (para actualizar rutas) - API Backend (soporte) -.-> Integración Sistemas Externos. Agrupaciones Sugeridas: - Capa_IoT_Ingesta: Dispositivos IoT, Plataforma Ingesta - Capa_Procesamiento_Almacenamiento: Motor Procesamiento, Almacenamiento Histórico - Capa_Aplicaciones_API: API Backend, App Web, App Móvil, Módulo Optimización, Servicio Notificaciones - Servicios_Externos: Integración Sistemas Externos. Consideraciones: Escalabilidad, seguridad de datos, baja latencia para alertas." \
    -t tech-architecture \
    -m gpt-4o-mini \
    --vision-model gpt-4o \
    -i 2 \
    --max-cost 0.07 \
    -v
```

## ¿Por qué este es un buen ejemplo de prueba?

1.  **Template Específico:** Utiliza `-t tech-architecture`, lo que activará las instrucciones adicionales para ese template dentro del agente.
2.  **Complejidad:** Describe un sistema con múltiples componentes, lo que da pie a un diagrama no trivial y permite evaluar la capacidad del agente para manejar información detallada.
3.  **Tipos de Nodos:** El prompt menciona explícitamente tipos de componentes como "Recurso de entrada", "Proceso Core", "Proceso de Decisión", que el LLM debe interpretar según las directrices del prompt del sistema del agente para la forma de los nodos.
4.  **Tipos de Relaciones:** Se sugieren explícitamente diferentes tipos de flechas (`==>`, `-->`, `-.->`, `..->`, `<-->`), lo que probará la capacidad del agente para utilizar el "Sistema de Relaciones con Diferentes Tipos de Líneas" definido en sus instrucciones.
5.  **Agrupaciones (Subgrafos):** El prompt sugiere explícitamente `subgraph`s, lo que probará el "Sistema de Agrupación Inteligente" del agente.
6.  **Caracteres y Nombres:** Incluye nombres como "Logística Óptima S.A.", "OBD-II", "Python/FastAPI", "Mapbox". Esto pondrá a prueba la robustez de la sanitización de texto implementada en el agente. Las comillas en el nombre de la empresa dentro del prompt de línea de comandos están escapadas (`\"`) para que el shell las interprete correctamente.
7.  **Parámetros de Ejecución Variados:**
    *   `-v` (verbose): Permite observar los pasos intermedios y el razonamiento del agente durante la ejecución.
    *   `-i 2`: Configura el agente para permitir hasta dos ciclos de refinamiento visual después de la generación inicial.
    *   `--max-cost 0.07`: Establece un presupuesto para la ejecución, útil para controlar los costos de API.
    *   Se especifican explícitamente los modelos de OpenAI a utilizar para la generación de código y el análisis visual.

Al ejecutar este ejemplo, se espera que el agente:
*   Identifique los componentes descritos y los represente como nodos con las formas adecuadas según su tipo (proceso, recurso, decisión).
*   Conecte los nodos utilizando los tipos de flechas especificados para reflejar la naturaleza de sus relaciones.
*   Cree los subgrafos sugeridos para agrupar componentes relacionados.
*   Aplique los estilos y colores definidos en el prompt del sistema del agente y las extensiones del template `tech-architecture`.
*   Siga el ciclo iterativo de generación de código, renderizado a imagen y análisis visual para refinar el diagrama.

Este caso de prueba proporciona una evaluación comprensiva de las capacidades del agente `sfa_mermaid_visual_agent_openai_v3_fixed.py`.
```