# app/utils/pdf_processing.py
import pdfplumber

#FUNCIONES DE LIMPIEZA
def str_a_num(x):
    if x is None or x == "":
      return 0.0
    x = x.replace(".", "")
    x = x.replace(",", ".")
    return float(x)

def us_a_num(x):
  return str_a_num(x[4:])

def cpl_a_num(x):
  return str_a_num(x[1:])


def extract_stocks_etf_1(pdf):
    compra_venta = True #TRUE SI ESTOY EN COMPRAVENTA Y FALSE EN DIVIDENDOS
    rows_compraventa =[]
    rows_dividendos =[]
    for page in pdf.pages:
        tables = page.extract_tables()
        for table in tables:
            for row in table:
                if not row or row[0] == "":
                    continue

                # Limpiar \n
                cleaned_row = []
                for casilla in row:
                    if casilla is not None:
                        casilla = casilla.strip().replace("\n", "")
                    else:
                        casilla = ""
                    cleaned_row.append(casilla)

                # ver si cambio a dividendos
                if cleaned_row[0] == "Fecha" and cleaned_row[6] == "Montoneto":
                    compra_venta = False
                    continue
                if cleaned_row[0] == "Fecha":
                    continue


                if compra_venta:
                    fecha = cleaned_row[0] #string
                    nombre_activo = cleaned_row[1]
                    simbolo = cleaned_row[2]  #string
                    categoria = cleaned_row[3] #string
                    aporte = us_a_num(cleaned_row[4]) #float
                    acciones_compradas = str_a_num(cleaned_row[5]) #float
                    rescate = us_a_num(cleaned_row[6])  #float
                    acciones_vendidas = str_a_num(cleaned_row[7])
                    #print("compra/venta", fecha, nombre_activo,  simbolo, categoria, aporte, acciones_compradas, rescate,acciones_vendidas)
                    rows_compraventa.append([ fecha, nombre_activo,  simbolo, categoria, aporte, acciones_compradas, rescate,acciones_vendidas])
                else:
                    fecha = cleaned_row[0]
                    nombre_activo = cleaned_row[1]
                    simbolo = cleaned_row[2]
                    categoria = cleaned_row[3]
                    monto_bruto = us_a_num(cleaned_row[4])
                    monto_impuestos = us_a_num(cleaned_row[5])
                    monto_neto = us_a_num(cleaned_row[6])
                    #print("dividendos", fecha, nombre_activo, simbolo, categoria, monto_bruto, monto_impuestos, monto_neto)
                    rows_dividendos.append([ fecha, nombre_activo, simbolo, categoria, monto_bruto, monto_impuestos, monto_neto])
    return [rows_compraventa, rows_dividendos]

def extract_mutual_funds(pdf):
    rows = []
    for page in pdf.pages:
        tables = page.extract_tables()
        for table in tables:
            for row in table:
                if not row or row[0] == "":
                    continue

                cleaned_row = []
                for casilla in row:
                    if casilla is not None:
                        casilla = casilla.strip().replace("\n", "")
                    else:
                        casilla = ""
                    cleaned_row.append(casilla)

                if cleaned_row[0] == "Fecha":
                    continue

                fecha = cleaned_row[0]
                nombre_inversion = cleaned_row[1]
                nombre_fondo = cleaned_row[2]
                serie_fondo = cleaned_row[3]

                # idx4=Aporte Cuotas, idx5=Rescate Cuotas (UNIDADES);
                # idx6=Valor Cuota (precio unitario en CLP);
                # idx8=Aporte Pesos, idx9=Rescate Pesos (MONTO en CLP, con "$").
                aporte_cuotas = str_a_num(cleaned_row[4])
                rescate_cuotas = str_a_num(cleaned_row[5])
                valor_cuota = str_a_num(cleaned_row[6])
                aporte_pesos = cpl_a_num(cleaned_row[8])
                rescate_pesos = cpl_a_num(cleaned_row[9])

                # quantity = cuotas, price = valor_cuota → quantity*price = monto.
                # Se conservan los montos en pesos al final para validación.
                rows.append([
                    fecha, nombre_inversion, nombre_fondo, serie_fondo,
                    aporte_cuotas, rescate_cuotas, valor_cuota,
                    aporte_pesos, rescate_pesos,
                ])
    return rows 

def extract_stocks_etf_2(pdf):
    rows = []
    for page in pdf.pages:
        tables = page.extract_tables()
        for table in tables:
            for row in table:
                if not row or row[0] == "":
                    continue

                cleaned_row = []
                for casilla in row:
                    if casilla is not None:
                        casilla = casilla.strip().replace("\n", "")
                    else:
                        casilla = ""
                    cleaned_row.append(casilla)

                if cleaned_row[0] == "Activo" or cleaned_row[0] == "Total":
                    continue

                nombre_activo = cleaned_row[0]
                num_acciones = float(cleaned_row[1])
                balance = us_a_num(cleaned_row[2])


                #print(nombre_activo, num_acciones, balance)
                rows.append([nombre_activo, num_acciones, balance])
    return rows