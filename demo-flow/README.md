# Ejemplo de análisis profundo

Selecciona esta carpeta, elige **Profundo** y pulsa **Analizar**.

Recorrido de ejemplo: `orders.html` → `OrdersComponent.save` → `OrdersService.create` → `OrdersController.Create` → `OrdersService.Save` (C#).

`syntax-error.ts` contiene intencionalmente un error de sintaxis para demostrar el nodo rojo. `exceptions.ts` contiene un `throw` válido: debe mostrar una advertencia, no un nodo rojo por fallo de ejecución.

Estos archivos son ejemplos estáticos para el mapa. No constituyen una aplicación Angular/ASP.NET ejecutable. Las conexiones de eventos y HTTP son inferidas.
