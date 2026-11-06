# Reglas de transformación · EECC BCP (Telecrédito, cuenta …023)

CON-R4 · H09 · A14 · 23 oct 2026. Son las mismas reglas que aplica el robot (`TransformacionBCP` v0.3.4). La carga manual de la plataforma de contingencia debe dar el mismo resultado que el robot con el mismo archivo.

## 1. Archivo de entrada

- `023_ultimos_movimientos.xlsx`, tal como se exporta desde Telecrédito.
- Fila 2: moneda en la columna B ("Soles").
- Fila 8: títulos. Los datos empiezan en la fila 9.
- El archivo declara mal el tamaño de la hoja: con openpyxl en modo solo lectura solo se ve la celda A1. Abrirlo en modo normal (`openpyxl.load_workbook(p, data_only=True)`) o con pandas (`header=7`).

## 2. Columnas obligatorias

Fecha · Fecha valuta · Descripción operación · Monto · Sucursal - agencia · N° operación · Usuario.

- Se comparan sin tildes ni símbolos ("Descripción" y "N°" pueden llegar con otra codificación).
- Si falta alguna: se rechaza la carga e indica cuál falta.

## 3. Fecha

- Solo se procesan las filas cuya Fecha (`dd/mm/aaaa`) es la fecha del ciclo.
- Filas de otro día: se descartan sin rechazar el archivo, y se informa cuántas.
- Fecha ilegible: se rechaza el archivo (indica cambio de formato).

## 4. Extornos

Si un N° de operación aparece más de una vez y una de esas filas contiene "EXTORNO", se excluyen **todas** las filas con ese número, incluido el abono original.

## 5. PSP TIN

- Se extrae de la descripción con `(2\d{11})(?!\d)`: 12 dígitos que empiezan en 2, sin otro dígito después.
- Filas sin PSP TIN: quedan fuera (depósitos `EFECTIVO` por agencia o agente, `KRE`, `OPE`, `ALO`, `000…`, recaudos con RUC, transferencias de empresas, cargos). Decisión del 22 oct.
- PSP TIN repetido: se queda solo la primera fila.

## 6. Monto y moneda

- Monto: número con 2 decimales, quitando las comas de miles. Monto ilegible: se rechaza el archivo.
- Moneda: "Soles" → `PEN`.

## 7. Registro de salida (uno por PSP TIN)

| Campo | Valor |
|-|-|
| `banco_codigo` | `BCP` |
| `cuenta_origen` | cuenta de pay-ins de BCP |
| `operacion_id` | N° operación |
| `pais` | `PE` |
| `fecha_operacion` | fecha del ciclo (`YYYY-MM-DD`) |
| `monto` | número |
| `moneda` | `PEN` |
| `psptin` | número de 12 dígitos extraído de la descripción |
| `origen_ingesta` | `MANUAL` (el robot envía `RPA`) |

`origin_document` y `target_name` no se envían: BCP no tiene esos datos.

## 8. Archivo sin movimientos

Si después de aplicar las reglas no queda ningún registro, la carga es válida y se envía con la lista vacía. No es un error (decisión del 22 oct).

## 9. Resultado de control (muestra del 06 oct)

| Dato | Valor |
|-|-|
| Filas del día | 9.685 |
| Registros | **7.209** |
| Monto total | **S/ 2.393.085,44** |
| Excluidas por extorno | 330 |
| Sin PSP TIN | 2.146 |
| Repetidos | 0 |

Es el mismo resultado de la conciliación manual de Samuel (`conciliaciononline.py`). Con ese archivo, la plataforma debe dar exactamente estos números.
