# MapaLocal

Proyecto **Grapho Ma**, versión local registrada en `VERSION`. La interfaz conserva el nombre MapaLocal. Consulta `CHANGELOG.md` para el historial de versiones. El repositorio Git local utiliza la rama `main` y etiquetas `vX.Y.Z` para identificar cada versión completada.

Aplicación local en Python para recorrer repositorios Angular/TypeScript y ASP.NET/C# y explorar sus archivos como puntos conectados. Interfaz en español. Solo necesita **Python 3.10 o superior** y un navegador moderno; no requiere pip, Node, .NET, cuentas ni conexión a Internet.

## Inicio rápido

Abre una terminal en esta carpeta y ejecuta:

```powershell
python app.py
```

Se abre http://127.0.0.1:8765. Pega la ruta de tu repositorio y pulsa **Analizar repositorio**. Si Windows no reconoce `python`, usa `py`.

Para probar el ejemplo incluido:

```powershell
python app.py demo
```

Para analizar directamente tu proyecto:

```powershell
python app.py "C:\proyectos\mi-sistema"
```

Otra opción de puerto y sin apertura automática del navegador:

```powershell
python app.py "C:\proyectos\mi-sistema" --port 9000 --no-browser
```

Abre la dirección mostrada en la terminal. Detén el servidor con **Ctrl+C**. En macOS/Linux puedes usar `python3`. La carpeta demo contiene archivos ilustrativos para el analizador, no aplicaciones Angular/.NET compilables.

## Explorar el mapa

- Cada punto representa un archivo `.ts`, `.tsx`, `.js`, `.jsx`, `.cs`, `.css`, `.scss`, `.sass` o `.less`. Las hojas de estilo tienen colores propios y filtros por lenguaje.
- Arrastra el fondo para desplazarte, usa la rueda o los botones para zoom y **Centrar** para encuadrar los resultados filtrados. Puedes arrastrar nodos.
- Selecciona un nodo o un archivo de la lista. El inspector muestra símbolos, dependencias salientes y archivos que lo utilizan. Las flechas de la selección apuntan hacia la dependencia.
- Pulsa una clase o método para ver el código en su línea. El visor es de solo lectura.
- Busca por ruta, archivo, clase o método; filtra por lenguaje, carpeta, tipo de enlace o vecinos de la selección.
- Los enlaces continuos son imports resueltos; los discontinuos son referencias de tipos C# inferidas.
- **Exportar JSON** descarga un documento versionado con `graph` (rutas, símbolos, enlaces, métricas y avisos) y `view` (posiciones, zoom, filtros y recorrido). No incluye el contenido de los archivos. La exportación incluye la ruta absoluta del repositorio.
- Vuelve a analizar para recoger cambios. La aplicación no vigila archivos automáticamente.

## Qué analiza

TypeScript/JavaScript: imports estáticos, exports/reexports, imports dinámicos con texto literal, `require` literal, rutas relativas, archivos `index`, sustitución `.js` → `.ts` y alias `compilerOptions.paths`. Lee el `tsconfig.json` más cercano e interpreta comentarios, comas finales y `extends` relativo. Conserva las rutas de alias con respecto al archivo que las declara. Admite `baseUrl` como compatibilidad para repositorios existentes.

C#: indexa clases, interfaces, records, structs, enums, métodos y constructores habituales. Busca coincidencias de nombres de tipos en el código, considerando el primer namespace del archivo, `using`, tipos cualificados y `global using` del mismo proyecto detectado por carpeta `.csproj`. Un `using` por sí solo **no crea una dependencia de archivo**.

Los símbolos se extraen mediante un analizador ligero basado en patrones y enmascarado de comentarios/cadenas. **No es un compilador, un AST completo ni un análisis semántico**. El mapa es una ayuda de exploración, no una prueba de que el proyecto compila ni un grafo exacto de ejecución.

## Límites conocidos

- En C# las referencias son inferidas: pueden existir falsos positivos por nombres ambiguos o variables y falsos negativos con aliases, namespaces múltiples/anidados, reflexión, DI y código generado. No evalúa referencias `.csproj`, condiciones de compilación, implicit usings ni Roslyn. Dos proyectos con tipos del mismo nombre pueden producir enlaces ambiguos.
- La extracción de métodos es aproximada: sintaxis compleja, cuerpos de expresión, strings raw/interpolados, regex de JavaScript y algunas firmas pueden clasificarse incorrectamente u omitirse. No produce un grafo de llamadas entre métodos.
- Angular se representa a través de archivos e imports; no se resuelven selectores HTML, bindings de plantillas, providers DI ni relaciones dinámicas. No se infieren peticiones HTTP Angular → endpoints ASP.NET.
- No replica la resolución completa del compilador TypeScript: no interpreta `package.json exports`, workspaces, referencias de proyecto, `extends` de paquetes o arrays, `rootDirs` ni configuraciones nombradas `tsconfig.app.json` salvo que se hereden desde un `tsconfig.json`. Imports externos o bare no resueltos se muestran como tales sin inventar nodos.
- Omite enlaces simbólicos, archivos mayores de 2 MB y carpetas habituales de dependencias/build (`node_modules`, `bin`, `obj`, `.git`, etc.). Puedes excluir más carpetas por nombre, separadas por comas. Respeta `.gitignore` mediante Git cuando está instalado; las exclusiones propias y manuales siguen teniendo prioridad.
- Límite de 12.000 archivos. Para proyectos grandes selecciona una subcarpeta y usa filtros. El diseño agrupa nodos por lenguaje/carpeta; no usa una simulación física. El navegador puede ralentizarse con muchos enlaces. La lista muestra hasta 500 resultados; la búsqueda cubre todo el índice.
- Un único repositorio activo por servidor; analizar otro sustituye el índice activo. El historial conserva análisis y vistas guardadas en archivos JSON locales. Las lecturas del visor reflejan el archivo actual: vuelve a analizar si cambió para actualizar líneas/símbolos.

## Privacidad

El servidor escucha únicamente en `127.0.0.1`. Todos los recursos web vienen incluidos; no hay CDN, telemetría, servicios de IA, subida de código ni ejecución de scripts del repositorio. El repositorio se lee sin modificarlo. Los análisis y vistas se escriben en la carpeta local `analyses/` junto a `app.py`. Las peticiones de análisis y lectura requieren un token de sesión; se validan Host y origen y no se habilita CORS. No publiques este servidor mediante proxies o túneles: está diseñado para uso personal local.

## Verificación y estructura

```powershell
python -m unittest discover -s tests -v
```

Las pruebas cubren imports/alias, herencia de configuración, exclusiones, referencias C#, símbolos, errores de ruta y flujo HTTP de análisis/visor y controles de acceso.

- `app.py`: servidor HTTP y CLI, biblioteca estándar de Python.
- `analyzer.py`: recorrido, resolución e índice.
- `static/`: interfaz, dibujo Canvas y visor, sin dependencias externas.
- `tests/`: pruebas con repositorios temporales y servidor real en puerto efímero.
- `demo/`: ejemplo mixto con ocho archivos y seis dependencias, incluyendo hojas de estilo.

## Consultas, recorridos y conteos

Pulsa **Consultar grafo** para abrir el panel. El diseño original del mapa se conserva.

### Cómo llegar de A a B

1. Selecciona un nodo y pulsa **Usar como punto A** en el inspector.
2. Selecciona otro nodo y pulsa **Usar como punto B y consultar**.
3. Elige seguir las dependencias en su dirección original o permitir ambos sentidos.
4. Pulsa **Buscar recorrido**. Se obtiene una ruta mínima por número de saltos mediante BFS. Los ciclos no provocan bucles infinitos. Si no existe una ruta se informa explícitamente; A = B tiene cero saltos.
5. **Ver recorrido en el grafo** resalta la ruta en naranja, numera sus nodos y encuadra el recorrido. Restablece los filtros visuales para que se vean todos sus pasos. **Quitar recorrido** elimina el resaltado.

Se devuelve una ruta mínima, no todas las rutas alternativas. Un salto siempre cuesta 1; el peso no representa latencia, tráfico ni distancia. Las referencias inferidas C# conservan su carácter aproximado durante los recorridos. El panel permite limitar el recorrido por tipo de enlace.

### Qué cuenta cada métrica

- **Aristas:** referencias distintas detectadas, identificadas por origen, destino, tipo y detalle. No son el número de veces que aparece un símbolo en el texto.
- **Conexiones:** pares dirigidos únicos de archivos. Varias aristas pueden formar una conexión. A → B y B → A cuentan como dos conexiones.
- **neighbors:** número de archivos vecinos distintos en ambos sentidos.
- **in_degree / out_degree:** conexiones entrantes / salientes. **degree** suma ambas.
- **references_in / references_out:** aristas entrantes / salientes.
- **weight** de un nodo: suma de aristas entrantes y salientes. Es el criterio predeterminado de «mayor peso».
- **weight** de una conexión: cantidad de aristas que unen ese par dirigido.

El panel muestra los totales del repositorio y los de la vista filtrada por separado. Los recorridos y SQL consultan siempre el repositorio completo. Los conteos se basan en los archivos y dependencias que el analizador logró indexar, sujetos a las exclusiones y límites descritos arriba.

### SQL de lectura

SQLite en memoria, sin instalar dependencias. Hay consultas preparadas para mayor peso, más conexiones entrantes/salientes, archivos aislados, totales, conteo por lenguaje y hojas de estilo. Puedes editar el SQL, usar WHERE, JOIN, GROUP BY, ORDER BY y LIMIT.

```sql
SELECT id, weight, neighbors
FROM nodes
ORDER BY weight DESC
LIMIT 20;

SELECT COUNT(*) AS aristas FROM edges;

SELECT source, target, weight
FROM connections
WHERE weight > 1
ORDER BY weight DESC;

SELECT language, COUNT(*) AS archivos
FROM nodes
GROUP BY language;
```

Ejecuta una sentencia a la vez. Las tablas disponibles son:

- `nodes(id, name, language, folder, lines, in_degree, out_degree, neighbors, degree, references_in, references_out, weight)`
- `edges(source, target, kind, detail)`
- `connections(source, target, weight)`

La ejecución está limitada a dos segundos y 500 filas devueltas; se indica si el resultado está truncado. Solo se permiten lecturas y funciones SQL habituales: no se admiten modificaciones, ATTACH, PRAGMA ni extensiones. No se incluye el contenido del código fuente en las tablas SQL. Haz clic en una ruta de archivo de los resultados para seleccionarla en el mapa.

### Referencias a estilos

Se indexan hojas CSS/SCSS/Sass/Less y referencias locales literales desde `styleUrl` / `styleUrls` de componentes Angular, imports JS/TS y `@import`, `@use`, `@forward` de estilos. Se resuelven rutas relativas, extensiones habituales y parciales Sass como `_palette.scss`. Los estilos se pueden abrir en el visor.

No se ejecuta Sass ni se reproduce su resolución completa: no se interpretan interpolaciones, load paths, configuración global de estilos de `angular.json`, links HTML/Razor, paquetes de estilos o assets dentro de `url()` de propiedades. Los estilos remotos no se descargan. Los archivos locales se incluyen aunque no se detecte quién los utiliza.

Si actualizas una copia que ya estaba ejecutándose, detén el servidor con Ctrl+C, vuelve a ejecutar `python app.py` y recarga el navegador. Vuelve a analizar el repositorio para generar los nodos de estilos y las métricas nuevas.

Referencias de diseño: [paths de TypeScript](https://www.typescriptlang.org/tsconfig/paths.html) y [directiva using de C#](https://learn.microsoft.com/en-us/dotnet/csharp/language-reference/keywords/using-directive). Para precisión semántica de producción, una siguiente versión puede integrar TypeScript Compiler API y Roslyn como procesos locales, conservando esta interfaz.


## Selección interactiva, progreso e historial

**Buscar recorrido A → B** activa la selección: haz clic en el origen y después en el destino, directamente en el grafo o en la lista de archivos. El diálogo se abre con los dos puntos completos. Puedes intercambiarlos con **Intercambiar A ↔ B**. Pulsa Escape o **Cancelar selección** para salir de ese modo. La búsqueda por nombre de la barra lateral te ayuda a encontrar cada punto.

El análisis se ejecuta en segundo plano. La barra indica fases reales: descubrimiento (0%, total aún desconocido), lectura de símbolos (10–45%), tipos (45–55%), dependencias (55–95%), métricas (95%), guardado (98%), preparación visual (99%) y finalización (100%). Es un porcentaje de trabajo por fases, no una predicción del tiempo restante. Durante el análisis no se puede iniciar otro ni sustituir el índice desde el historial. Si falla el análisis o el guardado, se muestra el error y no se indica éxito.

Cada análisis completado desde la interfaz se guarda automáticamente en `analyses/<identificador>.json`. Los JSON contienen nodos, aristas, símbolos, métricas, avisos y ruta del repositorio, pero no el contenido de los archivos. Se guardan con escritura atómica. Si la carpeta no tiene permiso de escritura, se informa del fallo.

- **Historial:** lista los análisis anteriores con fecha local y conteos; permite abrirlos sin volver a escanear, incluso después de reiniciar el servidor.
- **Guardar vista:** crea una nueva entrada JSON que conserva posiciones, zoom, filtros, nodo seleccionado, recorrido y el texto SQL actual. Las posiciones no se guardan automáticamente después de cada movimiento: pulsa el botón cuando quieras conservar la vista.
- **Exportar JSON:** descarga una copia del análisis y la vista actual al navegador. No hay importador de archivos descargados en esta versión; la reapertura integrada usa las entradas locales del historial.
- **Descargar PNG:** descarga una imagen del grafo con el encuadre, filtros y resaltado actuales. Para incluir todos los nodos, limpia los filtros y pulsa **Centrar** antes de descargar. No incluye paneles ni controles.

Las consultas SQL y recorridos funcionan sobre los datos históricos al abrir una entrada. El visor de código lee los archivos actuales: no es una copia histórica del código, y puede no estar disponible si el repositorio se movió o eliminó. El historial no se borra automáticamente ni tiene una política de retención. Para respaldarlo, copia la carpeta `analyses` junto con la aplicación. El ZIP de distribución no incluye historiales de uso.


## Git y tema visual

El análisis aplica las reglas nativas de **`.gitignore`**: patrones, excepciones con `!`, archivos anidados, `.git/info/exclude` y las exclusiones globales del usuario. Los archivos ya versionados se incluyen aunque coincidan con `.gitignore`, igual que en Git; las carpetas excluidas por MapaLocal o por el campo «Excluir carpetas» siguen omitiéndose. Se usa [git ls-files](https://git-scm.com/docs/git-ls-files) en modo de lectura, sin cambiar archivos, ramas, índice ni configuración del repositorio.

Necesitas Git instalado y accesible en PATH para esta función. Si falta, el análisis continúa con un aviso y las exclusiones habituales, sin afirmar que aplicó `.gitignore`. Si Git encuentra un error de permisos/configuración o supera 30 segundos por comando, se informa del error. En carpetas sin repositorio se usa un índice Git temporal externo para interpretar `.gitignore`, sin crear `.git` en tu proyecto. Los repositorios anidados se recorren con sus propias reglas.

La cabecera muestra la **rama detectada al iniciar el análisis**, o el commit abreviado si HEAD está separado. También distingue «Sin repositorio Git» y «Git no disponible». El JSON y el historial conservan ese estado; al abrir un análisis anterior se muestra su rama histórica. La cabecera corresponde al repositorio de la carpeta seleccionada; la información de repositorios anidados queda en `git.nested_repositories` dentro del JSON. No se cambian ramas desde la aplicación. Si cambias de rama externamente, vuelve a analizar para actualizar el mapa y la cabecera.

El botón **Tema claro / Tema oscuro**, arriba, cambia los paneles, diálogos, fondo, etiquetas y colores del grafo, sin mover los nodos. La preferencia se guarda en este navegador. Las imágenes PNG usan el tema activo. El tema inicial es oscuro y los colores originales se conservan en ese modo.
