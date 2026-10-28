# Datos maestros: lo que va antes que cualquier pipeline

Nada de lo demás funciona sobre maestros que mienten. Y una migración a la nube es el
momento natural para corregirlos: los datos se van a mover de todas formas.

## Lo que suele estar mal

| Maestro | Problema típico | Efecto |
|---|---|---|
| Artículos: sistema de reaprovisionamiento | Todo "contra stock" por defecto; los "contra pedido" sin cambiar | El planificador propone fabricar lo que no toca |
| Artículos: ubicaciones | Ubicaciones que no se actualizan | Se preparan pedidos con información falsa |
| Artículos: campos en general | Campos sin rellenar | Cada automatización tropieza con un campo vacío |
| Clientes: referencias y tarifas | Sin catálogo ni tarifa por cliente | Ni portal de pedidos ni resolución automática |
| Clientes y proveedores: cómo llaman ellos a las cosas | Cada pedido llega con la descripción del cliente, no con el código | La resolución depende de tener cargadas las "referencias de artículo" por tercero |

## Qué se hace

1. **Inventario de los campos que importan** para pedidos, recepciones y
   planificación. No todos los campos de Business Central: los que usan los flujos
   de la empresa.
2. **Reglas de obligatoriedad** en Business Central para esos campos al crear un
   artículo. Business Central no obliga por defecto, pero se puede. Es lo que evita
   que el problema vuelva.
3. **Limpieza de lo existente**: exportar, revisar con quien sabe (producción,
   almacén), corregir. Es trabajo de personas con una hoja, no de IA, y puede ir en
   el mismo paquete que la migración.
4. **Referencias de artículo por cliente y proveedor**: cargar cómo llama cada
   tercero a cada artículo. Alimenta directamente la resolución del pipeline y se
   puede ir construyendo desde la cola de revisión: cada corrección humana es una
   referencia nueva.
5. **Unidades de medida alternativas** (palé, caja, saco) con su factor. Sin ellas,
   "medio palé" no se resuelve.

## Quién y cuándo

No lo hace solo quien construye el pipeline: hace falta alguien de producción o
almacén que sepa qué artículo es contra pedido y cuál no. Antes o durante la
migración, no después de montar el pipeline.
