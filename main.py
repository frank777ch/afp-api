from fastapi import FastAPI, HTTPException
from curl_cffi import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime, timedelta

app = FastAPI()

def clean_float(text):
    try:
        clean = text.replace('%', '').strip()
        clean = clean.replace(' ', '')
        clean = re.sub(r'[^\d.]', '', clean.replace(',', '.'))
        return float(clean) if clean else 0.0
    except:
        return 0.0

def consultar_sbs_por_fecha(session, fecha_str):
    url = "https://www.sbs.gob.pe/app/spp/empleadores/comisiones_spp/Paginas/comision_prima.aspx"
    try:
        response_get = session.get(url, timeout=20)
        soup = BeautifulSoup(response_get.content, 'lxml')
        
        viewstate_input = soup.find('input', {'id': '__VIEWSTATE'})
        if not viewstate_input:
            return []

        viewstate = viewstate_input['value']
        gen = soup.find('input', {'id': '__VIEWSTATEGENERATOR'})
        val = soup.find('input', {'id': '__EVENTVALIDATION'})
        
        viewstate_gen = gen['value'] if gen else ""
        eventvalidation = val['value'] if val else ""
        
        payload = {
            '__VIEWSTATE': viewstate,
            '__VIEWSTATEGENERATOR': viewstate_gen,
            '__EVENTVALIDATION': eventvalidation,
            'cboPeriodo': fecha_str,
            'btnConsultar': 'Buscar Datos'
        }
        
        response_post = session.post(url, data=payload, timeout=20)
        soup_post = BeautifulSoup(response_post.content, 'lxml')
        filas = soup_post.find_all('tr', class_='JER_filaContenido')
        return filas

    except:
        return []

@app.get("/tasas")
def obtener_tasas_sbs():
    session = requests.Session(impersonate="chrome120")
    
    try:
        today = datetime.now()
        periodo_actual = f"{today.year}-{today.month:02d}"
        
        first_current = today.replace(day=1)
        prev_date = first_current - timedelta(days=1)
        periodo_anterior = f"{prev_date.year}-{prev_date.month:02d}"

        filas = consultar_sbs_por_fecha(session, periodo_actual)
        
        if not filas:
            filas = consultar_sbs_por_fecha(session, periodo_anterior)
            
            if not filas:
                return {"data": [], "message": "No data found"}
        
        data_afp = {}
        
        for fila in filas:
            cols = fila.find_all('td')
            if not cols: continue
            
            nombre = cols[0].text.strip().lower()
            
            vals = {
                "comi_sobreflujo": clean_float(cols[1].text) if len(cols) > 1 else 0.0,
                "comi_sobresaldo": clean_float(cols[2].text) if len(cols) > 2 else 0.0,
                "prima_seguro":    clean_float(cols[3].text) if len(cols) > 3 else 0.0,
                "aporte_obligatorio": clean_float(cols[4].text) if len(cols) > 4 else 0.0,
                "remu_asegurable": clean_float(cols[5].text) if len(cols) > 5 else 0.0
            }

            if "habitat" in nombre: data_afp["habitat"] = vals
            elif "integra" in nombre: data_afp["integra"] = vals
            elif "prima" in nombre: data_afp["prima"] = vals
            elif "profuturo" in nombre: data_afp["profuturo"] = vals

        return {"data": [data_afp]}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))