# Protocolo de observación para el servicio

Este protocolo prepara una sesión útil para el gemelo operativo sin convertir
el video en una fuente de datos personales. La sesión del viernes 9 de octubre
de 2026 debe conservarse como evidencia observada; el ejemplo JSONL incluido en
el proyecto está marcado `is_test: true` y no es evidencia del restaurante.

## Resultado mínimo de mañana

Una sesión es suficiente para empezar si permite seguir, aunque sea de forma
parcial, estas transiciones:

`llegada -> cola -> inicio de atención -> selección -> terminado/empaque -> entrega -> pago`

No es necesario que una sola cámara vea todo. El registro permite asociar el
mismo evento con clips de varias cámaras y conservar intervalos ocultos o
faltantes sin inventar datos.

## Antes de abrir

- Confirmar autorización para grabar y la política aplicable del restaurante.
- Encuadrar procesos y manos; evitar primeros planos de caras, pantallas de pago,
  recibos, teléfonos, documentos y conversaciones privadas.
- Asignar una etiqueta física estable a cada cámara: `CAM_ARRIVAL`,
  `CAM_COUNTER`, `CAM_CASHIER` y `CAM_ROUTE`.
- Completar una copia de `config/operations/camera_registry_template.json`.
- Usar la misma resolución y frecuencia de cuadros durante toda la toma cuando
  sea posible; desactivar pausas automáticas y ahorro de batería.
- Verificar batería, alimentación, almacenamiento y que la fecha/hora del equipo
  sean razonables. No confiar solo en el reloj del archivo.
- Grabar durante diez segundos una palmada o una señal visible y audible para
  todas las cámaras. Repetirla al final si es práctico.
- Fotografiar por separado el menú vigente y anotar cuántos trabajadores están
  presentes y sus roles generales, usando códigos como `W01`, nunca nombres.

## Durante el servicio

- Mantener cada cámara fija y no cambiarle el nombre durante la sesión.
- Si una cámara se detiene, anotar la hora aproximada y reiniciarla como un
  archivo/fuente nuevo; no unir archivos y fingir continuidad.
- Anotar cambios de turno, producto agotado, bloqueo de paso, tareas de apoyo y
  cualquier evento excepcional que explique una demora.
- No intervenir en el flujo para producir “mejores” datos.
- Si algo no se ve, registrarlo después como `partial`, `occluded` o `missing`.

## Después de grabar

1. Copiar los originales a una carpeta local de fecha, sin recodificar ni
   sobrescribirlos.
2. Renombrar de forma estable, por ejemplo
   `2026-10-09_CAM_COUNTER_001.mp4`, y actualizar el registro de cámaras.
3. Anotar duración, zona visible y cortes de cobertura. Calcular SHA-256 si es
   posible para poder demostrar qué archivo fue codificado.
4. Encontrar la señal de sincronización en cada video. Para cada cámara B,
   guardar `offset_b_minus_a_s = tiempo_en_B - tiempo_en_CAM_ARRIVAL`.
5. Trabajar siempre con el tiempo local del video (`source_offset_s`). Solo
   agregar `wall_clock_start_utc` si existe un ancla confiable. Bogotá usa
   `America/Bogota` (UTC-05:00).
6. Duplicar `config/operations/observation_example.jsonl`, cambiar el `run_id`,
   marcar `is_test: false`, reemplazar las fuentes y empezar la codificación.

## Reglas de codificación

- Un visitante es `visit:V001`; una orden es `order:O001`; una persona de trabajo
  es `worker:W01`. Los códigos son operativos y no identifican personas reales.
- Cada acción de duración tiene un `activity_id` propio. Repetir una selección
  requiere otro ID, aun para el mismo producto.
- Usar `start` y `complete` solo cuando cada borde se observa. Si solo se ve el
  final, guardar únicamente `complete`; no estimar el inicio.
- `evidence: observed` significa visible/audible en el archivo. Una interpretación
  se marca `evidence: inferred` y `observation_kind: inferred` con confianza baja
  y una nota explícita.
- Cada `source_event_id` debe ser estable. Volver a importar exactamente la misma
  línea no duplica el evento; reutilizar el ID con contenido diferente genera un
  conflicto visible.
- `evidence_refs` guarda uno o varios clips que respaldan el evento. Los tiempos
  de cámaras distintas permanecen separados y solo se comparan mediante una
  alineación explícita.
- Desconocido es `null`; nunca cero. No deducir peso, precio, cantidad, identidad
  o duración cuando no se pueda observar.

## Preguntas prioritarias para la familia

1. ¿En qué momento exacto se considera que empieza y termina la atención de un cliente?
2. ¿Cuándo queda libre la persona que toma el pedido: al terminar la preparación,
   al entregar o después del pago?
3. ¿El pago ocurre antes, durante o después de preparar y entregar, y cambia según
   consumo en mesa o para llevar?
4. ¿Qué productos comparten una sola posición de acceso y cuáles pueden servirse
   al mismo tiempo?
5. ¿Qué incluye exactamente cada picada y cuál es el precio vigente de cada
   producto/oferta? Confirmar especialmente morcilla y tipos de carne.
6. ¿Qué pasos de corte, sal, ají, división y empaque son obligatorios y cuáles
   dependen del pedido?
7. ¿Quién ayuda a caja o resuelve problemas, y durante cuánto tiempo deja su tarea principal?
8. ¿Qué causa con mayor frecuencia esperas, abandonos, productos agotados o retrabajo?

## Importación en macOS

El ejemplo se valida en una base separada con:

```bash
.venv/bin/python -m operations import-observations \
  --input config/operations/observation_example.jsonl \
  --db data/operations/observation_example.sqlite3
```

No usar `--seal` mientras todavía se estén agregando observaciones. Al terminar
la revisión, repetir el comando con `--seal`. Los errores se informan por número
de línea y las líneas válidas se conservan.
