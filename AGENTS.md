# Grapho Ma — instrucciones del proyecto

Estas instrucciones se aplican a toda esta carpeta. El producto usa actualmente el nombre MapaLocal en la interfaz.

- El usuario autorizó mantener un repositorio Git local y hacer un commit después de cada cambio solicitado que esté terminado y verificado. No hace falta volver a pedir permiso para esos commits.
- Un commit debe representar un cambio lógico completo, no cada edición intermedia. Revisa el diff y ejecuta las comprobaciones pertinentes antes de confirmar.
- No incluyas modificaciones ajenas al trabajo actual sin revisarlas. No generes commits vacíos.
- Mantén `VERSION` y `CHANGELOG.md`: parte de 0.1.0; aumenta patch para correcciones/documentación y minor para funciones compatibles. Reserva major para cambios incompatibles.
- Cada cambio terminado incrementa la versión, describe el resultado y su validación en CHANGELOG y crea una etiqueta local `vX.Y.Z` sobre el commit. No sobrescribas etiquetas existentes.
- Usa mensajes descriptivos, por ejemplo `feat: añadir filtros por proyecto` o `fix: corregir búsqueda de recorridos`.
- Informa al usuario de la versión y el hash corto del commit al terminar.
- No hagas push, crees remotos ni publiques el código sin una petición específica.
- Mantén el diseño del grafo que el usuario aprobó. No reorganices sus nodos ni cambies su estilo por iniciativa propia.
- Nunca versiones `analyses/`, cachés, entornos, secretos ni exportaciones generadas.
- Si actualizas el ZIP de distribución, excluye `.git/`, `analyses/`, cachés y archivos temporales. Incluye VERSION y CHANGELOG. El ZIP se guarda fuera de este repositorio.
- Pruebas: `python -m unittest discover -s tests -v`. Para cambios en JavaScript, comprueba la sintaxis y el flujo afectado en el navegador cuando corresponda.
