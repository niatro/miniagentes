# Guía para Ejecutar el Agente Generador de Diagramas Mermaid con Revisión Visual (`sfa_mermaid_visual_agent_openai_v1.py`)

## 1. ¿Qué es este Agente y Cuándo Usarlo?

Este agente de IA, llamado `sfa_mermaid_visual_agent_openai_v1.py`, está diseñado para **crear diagramas Mermaid** a partir de una descripción en lenguaje natural que tú le proporciones.

**Características Principales:**

*   **Generación Automática:** Transforma tu descripción de una reunión, proceso o estructura en un código de diagrama Mermaid.
*   **Revisión Visual (¡Importante!):**
    1.  Genera una primera versión del diagrama como imagen.
    2.  Utiliza un modelo de IA con capacidad de "visión" (como GPT-4o mini) para "mirar" la imagen que creó.
    3.  Si la IA detecta que la imagen puede mejorarse (en claridad, precisión, estética, etc.), intentará corregir el código Mermaid original.
    4.  Este ciclo de "generar imagen -> revisar imagen -> mejorar código" puede repetirse varias veces.
*   **Salida:** Produce tanto el código Mermaid (en un archivo `.mmd`) como la imagen final del diagrama (en un archivo `.png`), guardados en una carpeta local llamada `mermaid_images`.

**¿Cuándo deberías invocar este agente?**

*   Cuando necesites visualizar rápidamente la estructura de una reunión (temas, decisiones, acciones).
*   Para crear diagramas de flujo de procesos.
*   Para esquematizar ideas o planes donde las relaciones y jerarquías son importantes.
*   Cuando quieras un diagrama que se beneficie de una "segunda opinión" visual por parte de la IA para mejorar su calidad.

## 2. ¿Cómo Invocar el Agente?

Para ejecutar el agente, utilizarás un comando en la terminal. La estructura general del comando es:

```bash
uv run sfa_mermaid_visual_agent_openai_v1.py -p "TU_DESCRIPCIÓN_DETALLADA_AQUÍ" [OTRAS_OPCIONES]
```

### 2.1. Parámetros del Comando

Estos son los parámetros que puedes y debes usar:

*   **`-p "TU_DESCRIPCIÓN_DETALLADA_AQUÍ"`** o `--prompt "TU_DESCRIPCIÓN_DETALLADA_AQUÍ"`
    *   **Obligatorio.** Este es el parámetro más importante.
    *   Aquí es donde escribes, en lenguaje natural, lo que quieres que el agente diagrame.
    *   **Contenido del Prompt:** Para obtener los mejores resultados, tu descripción debe ser lo más clara y detallada posible. El agente está internamente instruido para buscar y representar:
        *   **Objetivo principal** o tema de la reunión/diagrama.
        *   **Temas principales** discutidos.
        *   **Decisiones concretas** tomadas.
        *   **Acciones específicas** acordadas (idealmente medibles y verificables).
        *   **Dependencias** o relaciones entre estas acciones y decisiones (ej. "esto requiere aquello", "esto genera aquello", "esto contribuye a").
        *   El agente intentará usar una orientación vertical predominante (`graph TD` en Mermaid).
    *   **Ejemplo de un buen prompt para `-p`**:
        `"Resumen de la reunión de planificación del sprint: El objetivo principal es lanzar la nueva funcionalidad de pagos. Se decidió usar Stripe como pasarela. Las acciones clave son: 1. Configurar cuenta de Stripe (requiere datos bancarios). 2. Desarrollar el módulo de integración con Stripe (depende de la configuración de la cuenta). 3. Realizar pruebas de pago. Una decisión secundaria fue ofrecer PayPal más adelante, lo que genera la acción de investigar la API de PayPal para Q4."`

*   **`-m MODELO_OPENAI`** o `--model MODELO_OPENAI`
    *   *Opcional.* Especifica el modelo de OpenAI que se utilizará.
    *   Por defecto, el agente usa `"gpt-4o-mini"`.
    *   Puedes usar otros modelos con capacidad de visión de OpenAI si lo deseas (ej. `"gpt-4o"` para mayor capacidad, aunque podría ser más lento y costoso). Se recomienda `gpt-4o-mini` o `gpt-4o` para el ciclo de revisión visual.
    *   **Ejemplo de uso:** `-m "gpt-4o"`

*   **`-i NUMERO_ITERACIONES`** o `--max_iterations NUMERO_ITERACIONES`
    *   *Opcional.* Define el número máximo de **ciclos de refinamiento visual**.
    *   El agente siempre realiza una generación inicial. Este parámetro controla cuántas veces *adicionales* puede intentar mejorar el diagrama basándose en el análisis visual.
    *   Por defecto es `3`. Esto significa: 1 generación inicial + hasta 3 intentos de refinamiento.
    *   Si la tarea es muy compleja, podrías aumentarlo (ej. `-i 4` o `-i 5`). Si quieres un resultado más rápido y confías en la primera generación, puedes reducirlo (ej. `-i 1` o `-i 0` para desactivar el refinamiento visual).
    *   **Ejemplo de uso:** `-i 2`

### 2.2. Construyendo el Comando Completo

Uniendo todo, un comando completo podría verse así:

```bash
uv run sfa_mermaid_visual_agent_openai_v1.py -p "Descripción detallada de lo que quiero diagramar, incluyendo temas, decisiones, acciones y sus relaciones." -m "gpt-4o-mini" -i 3
```

## 3. Ejemplos de Invocación

Aquí tienes algunos ejemplos para ilustrar cómo usar el agente:

*   **Ejemplo 1: Diagrama de flujo simple**
    ```bash
    uv run sfa_mermaid_visual_agent_openai_v1.py -p "Proceso para solicitar vacaciones: 1. Empleado envía solicitud. 2. Mánager revisa solicitud. 3. Si se aprueba, RRHH actualiza sistema. Si se rechaza, Mánager notifica al empleado." -i 2
    ```

*   **Ejemplo 2: Resumen de una reunión de proyecto (más complejo)**
    ```bash
    uv run sfa_mermaid_visual_agent_openai_v1.py -p "Minuta de la reunión del Proyecto Alfa: El objetivo es mejorar la retención de usuarios. Se decidió implementar un nuevo programa de onboarding. Las acciones son: A. Diseñar el flujo de onboarding (responsable: Equipo UX). B. Desarrollar los tutoriales interactivos (responsable: Equipo Dev, depende de A). C. Medir el impacto en la retención a 30 días. Una idea secundaria fue añadir gamificación, lo que genera la acción de investigar plataformas de gamificación para el próximo trimestre." -m "gpt-4o" -i 3
    ```

*   **Ejemplo 3: Estructura simple con pocas iteraciones**
    ```bash
    uv run sfa_mermaid_visual_agent_openai_v1.py -p "Organigrama básico: Dirección General. Dependen de ella: Departamento Comercial y Departamento Técnico. Del Departamento Técnico depende el Equipo de Soporte." -i 1
    ```

## 4. Consideraciones Adicionales

*   **API Key de OpenAI**: Asegúrate de que tu clave `OPENAI_API_KEY` esté correctamente configurada como una variable de entorno o en un archivo `.env` en el mismo directorio que el script. Sin esto, el agente no funcionará.
*   **Salida de Archivos**: Los diagramas generados (archivos `.mmd` con el código y `.png` con la imagen) se guardarán en una carpeta llamada `mermaid_images` que se creará en el directorio desde donde ejecutes el comando.
*   **Logs en Consola**: El agente mostrará mucha información en la terminal mientras trabaja. Esto incluye:
    *   A qué herramienta llama la IA (ej. `GenerateMermaidCodeArgs`, `AnalyzeMermaidImageArgs`).
    *   Los argumentos que usa para esa herramienta.
    *   El resultado de la herramienta (ej. el código Mermaid generado, el feedback del análisis visual).
    *   Esto es útil para entender qué está haciendo el agente y para depurar si algo no sale como esperas.
*   **Tiempo de Ejecución**: Dado que el agente puede realizar múltiples llamadas a la IA (incluyendo el análisis de imágenes), puede tardar unos minutos en completar tareas complejas, especialmente si aumentas el número de iteraciones.

Siguiendo estas instrucciones, deberías ser capaz de invocar el agente `sfa_mermaid_visual_agent_openai_v1.py` de manera efectiva para generar tus diagramas Mermaid. ¡Presta especial atención a la calidad y detalle de tu prompt (`-p`)!
