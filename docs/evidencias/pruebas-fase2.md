# Evidencia: corrida de las pruebas deterministas (Fase 2)

Generada automaticamente por `src/pruebas_fase2.py` con el comando
`python src/pruebas_fase2.py --reporte`.

- **Fecha de la corrida:** 2026-11-01 05:58:25
- **Reloj simulado usado por las herramientas:** 2026-09-17 (fecha_base del corpus de data/pedidos.json)
- **Entorno:** Python 3.13.5 en Windows 11
- **Resultado: 39/39 casos PASAN.**

## Router

| Resultado | Caso | Detalle |
|---|---|---|
| PASA | "Quiero devolver la vela del pedido ECO-10007, llegó defectuosa" -> accion | [orden con tracking; router: consenso de orden de devolucion sin forma de pregunta] |
| PASA | "Mi shampoo llegó dañado, necesito devolverlo" -> accion | [orden con defecto, sin tracking; router: consenso de orden de devolucion sin forma de pregunta] |
| PASA | "Devuelve mi pedido ECO-10005" -> accion | [imperativo con tracking; router: consenso de orden de devolucion sin forma de pregunta] |
| PASA | "Me llegó roto el bálsamo del pedido ECO-10012, quiero la etiqueta de devolución" -> accion | [orden con defecto y etiqueta; router: consenso de orden de devolucion sin forma de pregunta] |
| PASA | "¿Cuál es el estado del pedido ECO-10003?" -> informativa | [pregunta de estado; router: forma de pregunta o consulta sobre la politica] |
| PASA | "¿Cómo solicito una devolución?" -> informativa | [pregunta sobre el proceso; router: forma de pregunta o consulta sobre la politica] |
| PASA | "¿Qué productos no se pueden devolver?" -> informativa | [pregunta sobre la política; router: forma de pregunta o consulta sobre la politica] |
| PASA | "¿Puedo devolver mi shampoo del pedido ECO-10004?" -> informativa | [pregunta condicional (no ejecuta); router: forma de pregunta o consulta sobre la politica] |
| PASA | "¿Cuál es el plazo de devolución?" -> informativa | [pregunta sobre el plazo; router: forma de pregunta o consulta sobre la politica] |
| PASA | "Necesito una devolución del pedido ECO-10009" -> accion | [primera persona + sustantivo; router: consenso de orden de devolucion sin forma de pregunta] |
| PASA | "Hola, ¿qué tal?" -> informativa | [saludo sin orden; router: forma de pregunta o consulta sobre la politica] |
## Router con historial (continuacion de una orden en curso)

| Resultado | Caso | Detalle |
|---|---|---|
| PASA | con orden en curso, "llegaron defectuosos" -> accion | [respuesta del cliente que reanuda el flujo; router: consenso de orden de devolucion sin forma de pregunta] |
| PASA | con orden en curso, "está dañado" -> accion | [respuesta del cliente que reanuda el flujo; router: continuacion de la devolucion en curso: el agente espera un dato del cliente] |
| PASA | con orden en curso, "¿Y cuál es el plazo de devolución?" -> informativa | [una pregunta sigue informativa aun con la orden en curso; router: forma de pregunta o consulta sobre la politica] |
## buscar_pedido

| Resultado | Caso | Detalle |
|---|---|---|
| PASA | pedido existente devuelve exito con estado ENTREGADO | {"exito": true, "pedido": {"tracking": "ECO-10005", "cliente": "Paola S.", "productos": ["Envases de vidrio reutilizables (set 3)"], "total": "$58.000", "estado": "ENTREGADO", "fec |
| PASA | acepta texto alrededor del patron (rescata ECO-10005) | {"exito": true, "pedido": {"tracking": "ECO-10005", "cliente": "Paola S.", "productos": ["Envases de vidrio reutilizables (set 3)"], "total": "$58.000", "estado": "ENTREGADO", "fec |
| PASA | formato invalido da error explicito formato_invalido | {"exito": false, "error": "formato_invalido", "mensaje": "El numero de seguimiento de EcoMarket tiene el formato ECO-XXXXX (por ejemplo ECO-10005). Pidelo al cliente en lugar de ad |
| PASA | pedido inexistente da error explicito pedido_no_encontrado | {"exito": false, "error": "pedido_no_encontrado", "mensaje": "No existe un pedido con el numero de seguimiento ECO-99999 en el registro de EcoMarket. Pide al cliente revisar el num |
| PASA | argumento vacio da formato_invalido (no crash) | {"exito": false, "error": "formato_invalido", "mensaje": "El numero de seguimiento de EcoMarket tiene el formato ECO-XXXXX (por ejemplo ECO-10005). Pidelo al cliente en lugar de ad |
## verificar_elegibilidad_devolucion

| Resultado | Caso | Detalle |
|---|---|---|
| PASA | ECO-10005 envases de vidrio + cambio de opinion -> elegible (via estandar, costo cliente) | {"exito": true, "dictamen": {"tracking": "ECO-10005", "producto": "Envases de vidrio reutilizables (set 3)", "dias_desde_entrega": 0, "tipo_motivo": "cambio_opinion", "requiere_acl |
| PASA | ECO-10001 cepillos defectuosos (6 dias de entrega) -> elegible por excepcion de defecto | {"exito": true, "dictamen": {"tracking": "ECO-10001", "producto": "Kit de cepillos de bambú (3 uds.)", "dias_desde_entrega": 6, "tipo_motivo": "defecto", "requiere_aclaracion": fal |
| PASA | ECO-10006 cafe (alimentos, no devoluble) defectuoso en 4 dias -> elegible por la excepcion | {"exito": true, "dictamen": {"tracking": "ECO-10006", "producto": "Café orgánico molido 500g (suscripción mensual)", "dias_desde_entrega": 4, "tipo_motivo": "defecto", "requiere_ac |
| PASA | ECO-10006 cafe + no me gusto -> NO elegible (categoria_no_devoluble) | {"exito": true, "dictamen": {"tracking": "ECO-10006", "producto": "Café orgánico molido 500g (suscripción mensual)", "dias_desde_entrega": 4, "tipo_motivo": "cambio_opinion", "requ |
| PASA | ECO-10004 shampoo no me funciono -> NO elegible y NO entregado (pedido_no_entregado) | {"exito": true, "dictamen": {"elegible": false, "regla_aplicable": "pedido_no_entregado", "detalle": "El pedido aun no ha sido entregado (estado EN PREPARACION); la politica de dev |
| PASA | ECO-10007 vela defectuosa -> NO elegible (devolucion_ya_en_proceso) | {"exito": true, "dictamen": {"elegible": false, "regla_aplicable": "devolucion_ya_en_proceso", "detalle": "Este pedido ya tiene una devolucion en proceso: la etiqueta de retorno ya |
| PASA | ECO-10011 semillas + cambio de opinion -> NO elegible (semillas y plantas) | {"exito": true, "dictamen": {"tracking": "ECO-10011", "producto": "Bolsas de semillas de albahaca", "dias_desde_entrega": 7, "tipo_motivo": "cambio_opinion", "requiere_aclaracion": |
| PASA | motivo ambiguo -> dictamen requiere_aclaracion (el agente debe preguntar) | {"exito": true, "dictamen": {"tracking": "ECO-10005", "producto": "Envases de vidrio reutilizables (set 3)", "dias_desde_entrega": 0, "tipo_motivo": "ambiguo", "requiere_aclaracion |
| PASA | producto que no esta en el pedido -> producto_no_encontrado_en_pedido | {"exito": false, "error": "producto_no_encontrado_en_pedido", "mensaje": "El pedido contiene: Envases de vidrio reutilizables (set 3). Pide al cliente confirmar el producto exacto; |
| PASA | producto vacio -> producto_requerido | {"exito": false, "error": "producto_requerido", "mensaje": "Falta el nombre del producto a devolver. Con base en buscar_pedido, pide al cliente elegir entre sus productos: Envases  |
| PASA | motivo vacio -> motivo_requerido | {"exito": false, "error": "motivo_requerido", "mensaje": "Falta el motivo de la devolucion (por ejemplo: llego defectuoso, no me gusto, quiero otro producto). Pidelo al cliente ant |
| PASA | texto coincidente con varios productos del pedido -> producto_ambiguo | {"exito": false, "error": "producto_ambiguo", "mensaje": "El texto del cliente coincide con varios productos del pedido: pide al cliente elegir uno: Shampoo sólido de avena, Acondi |
| PASA | cambio de opinion a 31 dias de la entrega -> NO elegible (fuera_de_plazo) | {"exito": true, "dictamen": {"tracking": "ECO-10005", "producto": "Envases de vidrio reutilizables (set 3)", "dias_desde_entrega": 31, "tipo_motivo": "cambio_opinion", "requiere_ac |
| PASA | defecto a 37 dias de la entrega -> NO elegible (excepcion_defecto_fuera_de_plazo) | {"exito": true, "dictamen": {"tracking": "ECO-10001", "producto": "Kit de cepillos de bambú (3 uds.)", "dias_desde_entrega": 37, "tipo_motivo": "defecto", "requiere_aclaracion": fa |
## generar_etiqueta_devolucion

| Resultado | Caso | Detalle |
|---|---|---|
| PASA | dictamen elegible -> emite etiqueta con numero y guia | {"exito": true, "etiqueta": {"numero_etiqueta": "EL-001", "numero_guia": "DEV-10005-01", "transportadora": "EcoEnvíos", "direccion_recepcion": "Bodega 7, Parque Industrial Sabana N |
| PASA | segunda emision del mismo pedido -> no duplica (devuelve la ya emitida) | {"exito": true, "duplicado": true, "mensaje": "Esta etiqueta ya fue emitida en esta sesion: no se emite de nuevo.", "etiqueta": {"numero_etiqueta": "EL-001", "numero_guia": "DEV-10 |
| PASA | dictamen improvisado por el agente (sin verificacion) -> dictamen_invalido o no elegible | {"exito": false, "error": "elegibilidad_no_reproducible", "mensaje": "La re-verificacion interna de elegibilidad no coincide con el dictamen: no se emite la etiqueta. Explica al cl |
| PASA | dictamen con elegible=false -> no emite (no_elegible_o_dictamen_incoherente) | {"exito": false, "error": "no_elegible_o_dictamen_incoherente", "mensaje": "No se emite etiqueta: el dictamen no declara este pedido como elegible. Nunca generes etiqueta sin un di |
| PASA | tracking inexistente -> pedido_no_encontrado | {"exito": false, "error": "formato_invalido", "mensaje": "El numero de seguimiento de EcoMarket tiene el formato ECO-XXXXX (por ejemplo ECO-10005). Pidelo al cliente en lugar de ad |
| PASA | la etiqueta emitida quedo registrada en data/etiquetas_emitidas.json | {"tracking": "ECO-10005", "producto": "Envases de vidrio reutilizables (set 3)", "regla_aplicable": "devolucion_estandar", "etiqueta": {"numero_etiqueta": "EL-001", "numero_guia":  |

*La corrida restablecio el registro de etiquetas de prueba al estado vacio (partida limpia para la siguiente ejecucion).*
