# Cuadre Automático de Caja

Aplicación web sin servidor para conciliar caja chica.

## Funciones
- Fondo fijo.
- Saldo de Contífico.
- Reposición actual o pendiente.
- Efectivo físico.
- Vales no registrados.
- Otros comprobantes pendientes.
- Cálculo automático de saldo teórico.
- Diferencia contable contra Contífico.
- Diferencia física.
- Carga de Excel/CSV de movimientos para buscar partidas que coincidan con la diferencia.
- Generación de conclusión de cuadre.

## Uso
1. Abrir `index.html` en Chrome o Edge.
2. Ingresar los saldos.
3. Pulsar `Calcular cuadre`.
4. Opcional: cargar el reporte Excel del mayor o detalle de caja y pulsar `Analizar archivo`.

Nota: la lectura de Excel usa SheetJS desde CDN, por lo que el navegador debe tener acceso a Internet para leer XLS/XLSX. Los cálculos manuales funcionan sin Internet.
