# Digital Twin — Restaurante Guadalajara

Base arquitectónica en USD del Restaurante Guadalajara, ubicado en Fontibón, Bogotá. El proyecto documenta el estado actual del inmueble y servirá como punto de partida para revisar espacios, circulación y futuras configuraciones operativas.

## Contenido

- `usd/guadalajara_base.usda`: escena compuesta principal; este es el archivo que se debe abrir.
- `usd/layers/`: manifiestos legibles y capas geométricas por arquitectura, área y estación.
- `usd/textures/`: texturas compartidas por la biblioteca de materiales USD.
- `blend/guadalajara_base.blend`: escena editable canónica de Blender.
- `blend/assets/furniture/comedor_bench_table.blend`: fuente editable del conjunto reutilizable de mesa y bancas.
- `usd/assets/furniture/comedor_bench_table/comedor_bench_table.usdc`: componente portátil de mesa y bancas para Isaac Sim.
- `scripts/export_layered_usd.py`: exportador y validador canónico.
- `scripts/export_base.py`: entrada compatible que llama al exportador por capas.
- `docs/usd_pipeline.md`: jerarquía, reglas de composición y flujo para ingredientes.
- `scripts/build_despacho.py`: reconstruye las tres vitrinas provisionales del despacho.
- `scripts/build_floor_levels.py`: reconstruye el piso bajo del despacho, el comedor elevado y sus frentes de escalón.
- `scripts/build_client_arrival_floor.py`: extiende el nivel bajo al área de llegada de clientes.
- `scripts/build_bebidas_openings.py`: genera la puerta y ventana provisionales de `WALL_011`.
- `scripts/build_despacho_windows.py`: genera las dos ventanas provisionales del despacho.

La carpeta `usd/` debe conservar su estructura relativa para que la composición y
las texturas se resuelvan correctamente.

## Abrir en Isaac Sim desde Linux

Clone el repositorio completo y mantenga intacta la estructura de `usd/`. En
Isaac Sim abra `usd/guadalajara_base.usda`; todas sus capas y texturas usan rutas
relativas al repositorio. El conjunto reutilizable de mesa y bancas se puede
referenciar por separado desde
`usd/assets/furniture/comedor_bench_table/comedor_bench_table.usdc`.

Para verificar el paquete con el Python incluido en Isaac Sim:

```bash
./python.sh scripts/validate_usd_package.py
```

La validación comprueba dependencias, `defaultPrim`, metros, eje Z y el componente
de la mesa. No requiere las fotografías fuente ni la carpeta local `Medidas/`.

## Script de exportación

El exportador genera hojas `.usdc` compactas, manifiestos `.usda` por área,
una biblioteca compartida de materiales, capas separadas de cámaras y luces, y
la escena principal con unidades en metros y eje Z vertical. Blender continúa
siendo la fuente editable; las capas generadas se regeneran desde el `.blend`.

Se ejecuta desde la raíz del proyecto con Blender:

```bash
blender --background blend/guadalajara_base.blend --python scripts/export_layered_usd.py
```

El archivo fuente `.blend` forma parte de esta entrega. Las copias automáticas de
Blender (`*.blend1`, `*.blend2`) permanecen locales y no se publican.

Los generadores son idempotentes y deben ejecutarse antes de `export_base.py`. Para reconstruir todas las adiciones de esta fase sobre el archivo fuente:

```bash
blender --background blend/guadalajara_base.blend --python scripts/build_despacho.py
blender --background blend/guadalajara_base.blend --python scripts/build_floor_levels.py
blender --background blend/guadalajara_base.blend --python scripts/build_client_arrival_floor.py
blender --background blend/guadalajara_base.blend --python scripts/build_bebidas_openings.py
blender --background blend/guadalajara_base.blend --python scripts/build_despacho_windows.py
blender --background blend/guadalajara_base.blend --python scripts/build_soup_station.py
blender --background blend/guadalajara_base.blend --python scripts/build_domicilios_station.py
blender --background blend/guadalajara_base.blend --python scripts/export_base.py
```

## Estado actual

La primera fase incluye la distribución arquitectónica provisional, muros de 2,20 m, columnas, piso común con zonas a distinta cota, vitrinas del despacho, aperturas provisionales de puertas y ventanas, y una escalera metálica provisional en L basada en la referencia fotográfica y su cilindro guía. Las alturas y dimensiones definitivas, las carpinterías detalladas, los cielos y el segundo piso todavía están pendientes.

## Objetivos

- Mantener una base digital clara del inmueble tal como existe actualmente.
- Consolidar progresivamente la geometría y las medidas verificadas.
- Preparar el modelo para futuras revisiones espaciales y operativas.

> Este modelo es provisional y no sustituye planos arquitectónicos, estructurales, constructivos ni de licencia.

## Base operativa

El paquete Python `operations/` inicia el siguiente hito sin modificar la
arquitectura. Define entidades operativas, un contrato de eventos validado y
persistencia SQLite transaccional. El estado y las limitaciones están en
`docs/operations/progress.md`.

Prepare un entorno local e instale la única dependencia de ejecución declarada
en `pyproject.toml`:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e .
```

Luego ejecute las pruebas:

```bash
.venv/bin/python -m unittest discover -s tests/operations -v
```

El escenario integrado de prueba es completamente sintético. Para ejecutarlo:

```bash
.venv/bin/python -m operations demo \
  --scenario config/operations/synthetic_test.json \
  --db data/operations/demo.sqlite3 \
  --seed 42
```

El catálogo editable de productos está en
`config/operations/product_catalog.json`. Cada producto tiene precio COP
(actualmente `null`) y tiempos sintéticos reemplazables de preparación de
selección. Los precios y presentaciones comerciales tienen una única fuente
editable: `config/operations/menu_prices.json`. Cada corrida conserva copias de
ambos catálogos dentro de su configuración para no reinterpretar el historial
cuando los archivos cambien.

Para confirmar un precio en `menu_prices.json`, asigne `price_cop` como entero,
cambie `price_status` a `confirmed` y escriba una referencia verificable en
`price_source_ref`. Mientras un artículo permanezca sin confirmar, la simulación
guarda el precio y el total como desconocidos; `null` nunca significa gratis.

## Preparación de observaciones

La captura manual local ya dispone de un importador JSONL para preparar la
sesión de cámaras. El protocolo está en
`docs/operations/observation_protocol_es.md`; el registro editable de cámaras,
en `config/operations/camera_registry_template.json`; y el ejemplo ejecutable,
en `config/operations/observation_example.jsonl`.

```bash
.venv/bin/python -m operations import-observations \
  --input config/operations/observation_example.jsonl \
  --db data/operations/observation_example.sqlite3
```

El ejemplo está marcado como prueba y no representa observaciones reales. Una
reimportación idéntica no duplica eventos. Los conflictos y líneas mal formadas
se reportan con su número de línea; una importación con errores no se sella. Use
`--seal` únicamente después de revisar la sesión completa. La primera apertura
de una base v1 crea una copia `*.pre_v2_from_v1.sqlite3` antes de migrarla.

Los reportes, el servicio HTTP/monitor y la conexión USD/Isaac corresponden a
los hitos siguientes y no se presentan todavía como implementados.

## Experimento visual 2D

La simulación guardada puede reproducirse en un esquema 2D autocontenido, sin
Blender, Isaac Sim, servidor web ni dependencias JavaScript. El esquema se basa
en el dibujo del flujo del 9 de octubre de 2026 y está marcado explícitamente
como no medido.

```bash
.venv/bin/python -m operations visualize-2d \
  --db data/operations/demo.sqlite3 \
  --run-id <RUN_ID> \
  --layout config/operations/layout_2d_schematic.json \
  --out outputs/operations/flow_2d.html
```

Al abrir el HTML se puede reproducir o recorrer el reloj lógico, ver clientes y
trabajadores, la cola, abandono, órdenes listas, pagos, ocupación y espera de
recursos. El archivo lee solamente la corrida elegida y no modifica la base.

Para la demostración de tres clientes use el escenario visual separado. Los
tres clientes permanecen: el primero hace un pedido grande, el segundo uno
pequeño y el tercero uno mediano. El layout conserva coordenadas XY en metros
extraídas de `blend/guadalajara_base.blend`; esto describe la escala de la
escena, pero continúa siendo geometría provisional hasta contrastarla con el
registro de mediciones.

```bash
.venv/bin/python -m operations demo \
  --scenario config/operations/three_order_visual_test.json \
  --db data/operations/demo.sqlite3 \
  --seed 42

.venv/bin/python -m operations visualize-2d \
  --db data/operations/demo.sqlite3 \
  --run-id <RUN_ID_ANTERIOR> \
  --layout config/operations/layout_2d_blender.json \
  --out outputs/operations/flow_2d_three_orders.html
```

Las bandejas pequeñas Arepas, Plátanos, Envueltos, Chicharrón cocho y Yuca tienen
actualmente los mismos límites en Blender, por lo que el experimento las trata
como un grupo compartido y no inventa posiciones distintas. La separación
visual de trabajadores se resuelve en cada cuadro para evitar marcadores
superpuestos.

### Sincronizar la geometría de Blender

La geometría operacional se extrae sin modificar el `.blend`. Cuando cambien
las dimensiones o posiciones en la escena, regenere el snapshot y después
vuelva a crear el HTML:

```bash
/Applications/Blender.app/Contents/MacOS/Blender --background \
  blend/guadalajara_base.blend \
  --python scripts/export_operations_scene.py -- \
  --mapping config/operations/blender_scene_mapping.json \
  --out config/operations/despacho_geometry_from_blender.json
```

`layout_2d_blender.json` consume ese snapshot y valida que los puntos de acceso
de trabajadores sigan dentro del Despacho y fuera de los rectángulos de los
equipos. El perfil `staffing_profile.json` representa cinco servidores para la
prueba visual, además de cajero, sopas y frituras constantes; el rango reportado
de servidores es de cinco a ocho.

El visor acumula metros recorridos por trabajador sobre su grafo de rutas y los
muestra también en kilómetros. Por ahora son distancias de la simulación actual,
no una estimación diaria validada: para llegar a kilómetros por jornada todavía
faltan la duración real del turno, el volumen de clientes por hora y las rutas
observadas. El diámetro corporal de 0.55 m y 0.10 m de separación son parámetros
sintéticos reemplazables.
