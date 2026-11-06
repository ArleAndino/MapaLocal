export function validateOrder(valid: boolean) {
  if (!valid) throw new Error('Pedido inválido');
}
