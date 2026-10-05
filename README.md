# Digital Twin — Restaurante Guadalajara

Base arquitectónica en USD del Restaurante Guadalajara, ubicado en Fontibón, Bogotá. El proyecto documenta el estado actual del inmueble y servirá como punto de partida para revisar espacios, circulación y futuras configuraciones operativas.

## Contenido

- `usd/guadalajara_base.usda`: escena principal; este es el archivo que se debe abrir.
- `usd/assets/guadalajara_architecture.usdc`: geometría referenciada por la escena principal.
- `scripts/export_base.py`: script de Blender usado para exportar y validar la base USD.

Los dos archivos deben conservar su ubicación relativa para que la escena cargue correctamente.

## Script de exportación

El script selecciona la geometría arquitectónica y el equipamiento organizado para exportación, genera el asset `.usdc` y crea la escena principal `.usda` con unidades en metros y eje Z vertical.

Se ejecuta desde la raíz del proyecto con Blender:

```bash
blender --background blend/guadalajara_base.blend --python scripts/export_base.py
```

El archivo fuente `.blend` no forma parte de esta entrega. El script se incluye como referencia técnica y puede utilizarse cuando se tenga acceso al archivo fuente.

## Estado actual

La primera fase incluye la distribución general, 39 muros con una altura provisional uniforme de 2,20 m, columnas, piso común, acabado blanco mate, seis aperturas provisionales de puertas y una escalera metálica provisional en L basada en la referencia fotográfica y su cilindro guía. Las alturas y dimensiones definitivas, las puertas detalladas, los cielos y el segundo piso todavía están pendientes.

## Objetivos

- Mantener una base digital clara del inmueble tal como existe actualmente.
- Consolidar progresivamente la geometría y las medidas verificadas.
- Preparar el modelo para futuras revisiones espaciales y operativas.

> Este modelo es provisional y no sustituye planos arquitectónicos, estructurales, constructivos ni de licencia.
