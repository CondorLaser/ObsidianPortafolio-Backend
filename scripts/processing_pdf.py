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



def extract_stocks_etf_1(pdf):
    compra_venta = True #TRUE SI ESTOY EN COMPRAVENTA Y FALSE EN DIVIDENDOS
    rows =[]
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
                    print("compra/venta", fecha, nombre_activo,  simbolo, categoria, aporte, acciones_compradas, rescate,acciones_vendidas)
                    rows.append(["compra_venta", fecha, nombre_activo,  simbolo, categoria, aporte, acciones_compradas, rescate,acciones_vendidas])
                else:
                    fecha = cleaned_row[0]
                    nombre_activo = cleaned_row[1]
                    simbolo = cleaned_row[2]
                    categoria = cleaned_row[3]
                    monto_bruto = us_a_num(cleaned_row[4])
                    monto_impuestos = us_a_num(cleaned_row[5])
                    monto_neto = us_a_num(cleaned_row[6])
                    print("dividendos", fecha, nombre_activo, simbolo, categoria, monto_bruto, monto_impuestos, monto_neto)
                    rows.append(["comdividendospra_venta", fecha, nombre_activo, simbolo, categoria, monto_bruto, monto_impuestos, monto_neto])
    return rows

def extract_mutual_funds(pdf):
    """Tu lógica para type2"""
    return {...} 

def extract_stocks_etf_2(pdf):
    """Tu lógica para type3"""
    return {...}