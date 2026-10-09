# Digital Twin — Restaurante Guadalajara

Base arquitectónica en USD del Restaurante Guadalajara, ubicado en Fontibón, Bogotá. El proyecto documenta el estado actual del inmueble y servirá como punto de partida para revisar espacios, circulación y futuras configuraciones operativas.

## Contenido

- `usd/guadalajara_base.usda`: escena compuesta principal; este es el archivo que se debe abrir.
- `usd/layers/`: manifiestos legibles y capas geométricas por arquitectura, área y estación.
- `usd/textures/`: texturas compartidas por la biblioteca de materiales USD.
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

## Script de exportación

El exportador genera hojas `.usdc` compactas, manifiestos `.usda` por área,
una biblioteca compartida de materiales, capas separadas de cámaras y luces, y
la escena principal con unidades en metros y eje Z vertical. Blender continúa
siendo la fuente editable; las capas generadas se regeneran desde el `.blend`.

Se ejecuta desde la raíz del proyecto con Blender:

```bash
blender --background blend/guadalajara_base.blend --python scripts/export_layered_usd.py
```

El archivo fuente `.blend` no forma parte de esta entrega. El script se incluye como referencia técnica y puede utilizarse cuando se tenga acceso al archivo fuente.

Los generadores son idempotentes y deben ejecutarse antes de `export_base.py`. Para reconstruir todas las adiciones de esta fase sobre el archivo fuente:

```bash
blender --background blend/guadalajara_base.blend --python scripts/build_despacho.py
blender --background blend/guadalajara_base.blend --python scripts/build_floor_levels.py
blender --background blend/guadalajara_base.blend --python scripts/build_client_arrival_floor.py
blender --background blend/guadalajara_base.blend --python scripts/build_bebidas_openings.py
blender --background blend/guadalajara_base.blend --python scripts/build_despacho_windows.py
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
(o `null` cuando no se conoce), procedencia del precio y tiempos sintéticos
reemplazables de preparación de selección. Cada corrida conserva una copia
efectiva del catálogo dentro de su configuración para no reinterpretar el
historial cuando el catálogo cambie.

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
