"""Pallet dashboard: read-only Sheet view with honest refresh.

Reads tab `Pallets exportados` plus the campaign tabs through sheet_reader
only. The refresh endpoints drop the in-process cache and re-read the
Sheet; they never reach any other system. UI copy is Spanish (es-419
domain vocabulary).
"""
import os

from flask import Flask, jsonify, request, Response

import analytics
import campaign_analytics
import campaign_reader
import sheet_reader

app = Flask(__name__)

DATE_KEY = "fecha_salida"

PAGE = """<!DOCTYPE html><html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Dashboard PCP</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
<style>
:root{--green:#14532d;--gold:#c9a227;--bg:#f4f6f3}
body{font-family:Segoe UI,Arial,sans-serif;background:var(--bg);margin:0;color:#222}
header{background:var(--green);color:#fff;padding:14px 22px;display:flex;gap:16px;align-items:center;flex-wrap:wrap}
header h1{margin:0;font-size:22px}header small{opacity:.85}
.tabs{margin-left:auto;display:flex;gap:6px}
.tabs button{background:#ffffff22;color:#fff;border:1px solid #ffffff55;border-radius:6px;padding:7px 14px;cursor:pointer;font-weight:600}
.tabs button.on{background:var(--gold);color:#222;border-color:var(--gold)}
.filters{background:#fff;border-bottom:3px solid var(--gold);padding:10px 22px;display:flex;gap:12px;flex-wrap:wrap;align-items:end}
[hidden]{display:none!important}
.toolbar{display:flex;gap:10px;align-items:end;margin-bottom:8px}
.toolbar label{font-size:12px;font-weight:600;color:var(--green)}
.toolbar select{padding:5px 8px;border:1px solid #bbb;border-radius:6px}
.pctbar{display:flex;align-items:center;gap:8px;width:132px;margin:0 auto}
.bar{flex:0 0 80px;height:10px;background:#e3e7e1;border-radius:5px;overflow:hidden}
.bar span{display:block;height:100%;background:var(--green);border-radius:5px}
.pctbar em{flex:0 0 44px;font-style:normal;text-align:right;font-variant-numeric:tabular-nums}
tr.subtotal td{font-weight:600;background:#f7f9f5;border-top:1px solid #cfd8cb}
.filters label{font-size:12px;font-weight:600;color:var(--green)}
.filters select,.filters input{padding:6px 8px;border:1px solid #bbb;border-radius:6px}
.filters button{background:var(--green);color:#fff;border:0;border-radius:6px;padding:8px 18px;cursor:pointer;font-weight:600}
main{padding:16px 22px}
.stamp{font-size:13px;color:#444;margin:0 0 2px}
.note{font-size:12px;color:#777;margin:0 0 12px}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px;margin-bottom:16px}
.card{background:#fff;border-radius:10px;padding:10px 12px;border-top:4px solid var(--gold);box-shadow:0 1px 3px #0002}
.card b{display:block;font-size:19px;color:var(--green)}.card span{font-size:12px;color:#666}
.panel{background:#fff;border-radius:10px;padding:12px;box-shadow:0 1px 3px #0002;overflow:auto;margin-bottom:14px}
.pies{display:grid;grid-template-columns:repeat(auto-fill,minmax(170px,1fr));gap:12px}
.pie{background:#fff;border:1px solid #e3e7e1;border-radius:10px;padding:10px;text-align:center}
.pie b{display:block;font-size:13px;color:var(--green);margin-bottom:4px}
.pie canvas{width:100%}
tr.total td{font-weight:700;background:#f2f5ef;border-top:2px solid var(--green)}
.panel h2{margin:0 0 10px;font-size:16px;color:var(--green)}
table{border-collapse:collapse;width:100%;font-size:13px}
th,td{border:1px solid #d8d8d8;padding:5px 8px;text-align:right;white-space:nowrap}
th{background:var(--green);color:#fff;position:sticky;top:0}
td:first-child,th:first-child{text-align:left}
canvas{max-height:320px}
#loader{position:fixed;inset:0;background:#000a;display:flex;flex-direction:column;gap:12px;align-items:center;justify-content:center;color:#fff;z-index:99;font-size:15px}
#loader[hidden]{display:none}
#loader .spin{width:44px;height:44px;border:5px solid #ffffff55;border-top-color:#fff;border-radius:50%;animation:giro 1s linear infinite}
@keyframes giro{to{transform:rotate(360deg)}}
</style></head><body>
<div id="loader"><div class="spin"></div><p>Cargando datos del Sheet...</p></div>
<header><h1>Dashboard PCP</h1><small>Despachos y campaña</small>
<nav class="tabs"><button class="on" id="tabPallets" onclick="showTab('pallets')">Pallets</button><button id="tabCampania" onclick="showTab('campania')">Campaña</button></nav></header>
<div class="filters" id="filtersPallets">
<label>Desde<br><input type="date" id="fDesde"></label>
<label>Hasta<br><input type="date" id="fHasta"></label>
<label>Planta<br><select id="fPlanta"><option value="">Todas</option></select></label>
<label>Variedad<br><select id="fVar"><option value="">Todas</option></select></label>
<button onclick="load()">Aplicar</button>
<button onclick="refresh()">Actualizar</button>
</div>
<div class="filters" id="filtersCampania" hidden>
<label>Fecha<br><input type="date" id="cFecha" min="2026-09-21"></label>
<label>Planta<br><select id="cPlanta"><option value="">Todas</option></select></label>
<label>Variedad<br><select id="cVariedad"><option value="">Todas</option></select></label>
<button onclick="loadCampania()">Aplicar</button>
<button onclick="refreshCampania()">Actualizar</button>
</div><main id="viewPallets">
<p class="stamp">Última actualización: <b id="stamp">—</b></p>
<p class="note">Los datos se guardan en memoria hasta 1 hora: cambiar filtros no recarga el Sheet. La actualización es diaria a las 7:00 am (hora Perú) o manual con el botón Actualizar.</p>
<div class="cards" id="kpis"></div>
<div class="panel"><h2>Despachos por día</h2><canvas id="cDay"></canvas></div>
<div class="panel"><h2>Top países con más despachos</h2><canvas id="cPais"></canvas><div id="tPaises"></div></div>
<div class="panel"><h2>Resumen por fecha</h2><div id="tFecha"></div></div>
<div class="panel"><h2>Despacho por país y puerto</h2><div id="tPuerto"></div></div>
<div class="panel"><h2>Presentación más despachada</h2><div id="tFormato"></div></div>
<div class="panel"><h2>Detalle</h2><div id="tbl"></div></div>
</main>
<main id="viewCampania" hidden>
<p class="stamp">Última lectura del Sheet: <b id="cStamp">—</b></p>
<p class="note">Faltantes = recepcionadas − abastecidas; un valor negativo significa que se abasteció con stock de días anteriores.</p>
<div class="cards" id="cKpis"></div>
<div class="panel"><h2>Jabas por hora</h2><div class="toolbar"><label>Vista<br><select id="cModo" onchange="drawCamp(CAMP_DATA?CAMP_DATA.por_hora:[],this.value)"><option value="hora">Hora a hora</option><option value="acum">Acumulado</option></select></label></div><canvas id="cHora"></canvas></div>
<div class="panel"><h2>Resumen por packing y variedad</h2><div id="cPacking"></div></div>
<div class="panel"><h2>Avance por variedad</h2><div class="pies" id="cPies"></div></div>
<div class="panel"><h2>Producción por variedad (cajas reales y equivalentes)</h2><div id="cProd"></div></div>
<div class="panel"><h2>Detalle por hora</h2><div id="cHoraTab"></div></div>
</main>
<script>
let CH={};
let PIES=[];
const pieLabels={id:'pieLabels',afterDatasetsDraw(chart){
 const meta=chart.getDatasetMeta(0),data=chart.data.datasets[0].data;
 const total=data.reduce((a,b)=>a+(Number(b)||0),0)||1;
 const ctx=chart.ctx;ctx.save();ctx.font='700 12px Segoe UI,Arial';
 ctx.textAlign='center';ctx.textBaseline='middle';
 meta.data.forEach((arc,i)=>{const v=Number(data[i])||0;
  if(!v||v/total<0.08)return;
  const p=arc.tooltipPosition();ctx.fillStyle=i===0?'#fff':'#14532d';
  ctx.fillText(fmt(v),p.x,p.y);});
 ctx.restore();
}};
function dropPies(){PIES.forEach(c=>{try{c.destroy();}catch(e){}});PIES=[];}
function dropCharts(){dropPies();for(const k of Object.keys(CH)){try{CH[k].destroy();}catch(e){}delete CH[k];}}
async function api(p,o){const r=await fetch(p,o);return r.json();}
let META=null;
let loaderTimer=null;
function showLoaderSoon(){
 const L=document.getElementById('loader');
 L.querySelector('p').textContent='Cargando...';
 loaderTimer=setTimeout(()=>{L.hidden=false;},400);
}
function hideLoader(){clearTimeout(loaderTimer);document.getElementById('loader').hidden=true;}
async function load(){
 showLoaderSoon();
 try{
  const q=new URLSearchParams({desde:fDesde.value,hasta:fHasta.value,planta:fPlanta.value,variedad:fVar.value});
  if(!META){META=await api('/api/meta');}
  const [a,b]=await Promise.all([api('/api/analytics?'+q),api('/api/pallets?'+q)]);
  fillFilters(META);
  document.getElementById('stamp').textContent=a.ultima_actualizacion||'—';
  kpis(a.kpis);drawDaily(a.por_fecha);drawCountries(a.top_paises);
  tabFecha(a.por_fecha);tabPaises(a.top_paises);tabPuerto(a.por_puerto);tabFormato(a.top_formatos);
  grid(b);
  hideLoader();
 }catch(err){
  clearTimeout(loaderTimer);
  const L=document.getElementById('loader');L.hidden=false;
  L.querySelector('p').textContent='No se pudo cargar el Sheet. Revisa tu conexion y pulsa Aplicar.';
 }
}
function fillFilters(meta){
 if(fPlanta.options.length<2)meta.plantas.forEach(p=>fPlanta.add(new Option(p,p)));
 if(fVar.options.length<2)meta.variedades.forEach(v=>fVar.add(new Option(v,v)));
 if(!fDesde.value&&meta.fechas.length){fDesde.value=meta.fechas[0];fHasta.value=meta.fechas[meta.fechas.length-1];}
}
function fmt(x){return Number(x||0).toLocaleString();}
function kpis(k){
 const rango=(k.fecha_desde||k.fecha_hasta)?(k.fecha_desde+' → '+k.fecha_hasta):'—';
 const c=[['Contenedores',fmt(k.contenedores)],['Pallets',fmt(k.pallets)],
  ['Cajas producción',fmt(k.cajas_produccion)],['Cajas equivalentes',fmt(k.cajas_equivalentes)],
  ['Rango de fechas',rango],['Última salida',k.ultima_salida||'—']];
 document.getElementById('kpis').innerHTML=c.map(x=>`<div class=card><b>${x[1]}</b><span>${x[0]}</span></div>`).join('');
}
function drawDaily(dias){
 dropCharts();
 const fs=dias.map(d=>d.fecha);
 CH.day=new Chart(document.getElementById('cDay'),{data:{labels:fs,
  datasets:[{type:'bar',label:'Contenedores',data:dias.map(d=>d.contenedores),backgroundColor:'#14532d',yAxisID:'y'},
   {type:'line',label:'Cajas equivalentes',data:dias.map(d=>d.cajas_equivalentes),borderColor:'#c9a227',backgroundColor:'#c9a227',tension:.25,yAxisID:'y1'}]},
  options:{responsive:true,interaction:{mode:'index',intersect:false},
   plugins:{title:{display:true,text:'Contenedores y cajas equivalentes por fecha de salida'}},
   scales:{y:{type:'linear',position:'left',title:{display:true,text:'Contenedores'}},
    y1:{type:'linear',position:'right',grid:{drawOnChartArea:false},title:{display:true,text:'Cajas equiv.'}}}}});
}
function drawCountries(top){
 const t=top.slice(0,10);
 CH.pais=new Chart(document.getElementById('cPais'),{type:'bar',
  data:{labels:t.map(p=>p.pais),datasets:[{label:'Contenedores',data:t.map(p=>p.contenedores),backgroundColor:'#14532d'}]},
  options:{indexAxis:'y',responsive:true,plugins:{title:{display:true,text:'Top 10 países por contenedores'}}}});
}
function tabFecha(dias){
 let h='<table><tr><th>Fecha salida</th><th>Contenedores</th><th>Pallets</th><th>Cajas prod.</th><th>Cajas equiv.</th><th>Países</th></tr>';
 dias.forEach(d=>{h+=`<tr><td>${d.fecha||'—'}</td><td>${fmt(d.contenedores)}</td><td>${fmt(d.pallets)}</td><td>${fmt(d.cajas_produccion)}</td><td>${fmt(d.cajas_equivalentes)}</td><td>${(d.paises||[]).join(', ')}</td></tr>`;});
 document.getElementById('tFecha').innerHTML=h+'</table>';
}
function tabPaises(top){
 let h='<table><tr><th>País destino</th><th>Contenedores</th><th>Pallets</th><th>Cajas prod.</th><th>Cajas equiv.</th></tr>';
 top.forEach(p=>{h+=`<tr><td>${p.pais||'—'}</td><td>${fmt(p.contenedores)}</td><td>${fmt(p.pallets)}</td><td>${fmt(p.cajas_produccion)}</td><td>${fmt(p.cajas_equivalentes)}</td></tr>`;});
 document.getElementById('tPaises').innerHTML=h+'</table>';
}
function tabPuerto(rows){
 let h='<table><tr><th>País destino</th><th>Puerto destino</th><th>Contenedores</th><th>Pallets</th><th>Cajas prod.</th><th>Cajas equiv.</th></tr>';
 rows.forEach(p=>{h+=`<tr><td>${p.pais||'—'}</td><td>${p.puerto||'—'}</td><td>${fmt(p.contenedores)}</td><td>${fmt(p.pallets)}</td><td>${fmt(p.cajas_produccion)}</td><td>${fmt(p.cajas_equivalentes)}</td></tr>`;});
 document.getElementById('tPuerto').innerHTML=h+'</table>';
}
function tabFormato(rows){
 let h='<table><tr><th>Presentación (formato)</th><th>Contenedores</th><th>Pallets</th><th>Cajas prod.</th><th>Cajas equiv.</th></tr>';
 rows.forEach(f=>{h+=`<tr><td>${f.formato||'—'}</td><td>${fmt(f.contenedores)}</td><td>${fmt(f.pallets)}</td><td>${fmt(f.cajas_produccion)}</td><td>${fmt(f.cajas_equivalentes)}</td></tr>`;});
 document.getElementById('tFormato').innerHTML=h+'</table>';
}
const DETALLE_MAX=500;
function grid(b){
 const total=b.rows.length, rows=b.rows.slice(0,DETALLE_MAX);
 let h='<table><tr>'+b.headers.map(x=>`<th>${x}</th>`).join('')+'</tr>';
 rows.forEach(r=>{h+='<tr>'+b.headers.map(x=>`<td>${r[x]??''}</td>`).join('')+'</tr>';});
 document.getElementById('tbl').innerHTML=h+'</table>'
  +(total>rows.length?`<p class=note>Mostrando ${rows.length} de ${total} filas — ajustá los filtros para ver menos.</p>`:'');
}
let CAMP_LOADED=false;
let CAMP_DATA=null;
function showTab(name){
 const pallets=name==='pallets';
 document.getElementById('viewPallets').hidden=!pallets;
 document.getElementById('filtersPallets').hidden=!pallets;
 document.getElementById('viewCampania').hidden=pallets;
 document.getElementById('filtersCampania').hidden=pallets;
 document.getElementById('tabPallets').classList.toggle('on',pallets);
 document.getElementById('tabCampania').classList.toggle('on',!pallets);
 if(!pallets){
  if(!CAMP_LOADED){loadCampania();}
  else if(CAMP_DATA){drawCamp(CAMP_DATA.por_hora,document.getElementById('cModo').value);drawPies(CAMP_DATA.por_variedad);}
 }
}
function fillCampFilters(a){
 if(cPlanta.options.length<2)(a.plantas||[]).forEach(p=>cPlanta.add(new Option(p,p)));
 if(cVariedad.options.length<2)(a.variedades||[]).forEach(v=>cVariedad.add(new Option(v,v)));
 if(!cFecha.value&&a.fecha){cFecha.value=a.fecha;}
}
function campKpis(k){
 const c=[['Jabas recepcionadas',fmt(k.jabas_recepcion)],['Jabas abastecidas',fmt(k.jabas_abastecimiento)],
  ['Jabas faltantes',fmt(k.faltantes)],['% abastecido',fmt(k.pct_abastecido)+'%'],['Cajas producción',fmt(k.cajas_produccion)],
  ['Cajas equivalentes',fmt(k.cajas_equivalentes)],['Kilos reales',fmt(k.kilos)]];
 document.getElementById('cKpis').innerHTML=c.map(x=>`<div class=card><b>${x[1]}</b><span>${x[0]}</span></div>`).join('');
}
function bar(pct){
 const w=Math.max(0,Math.min(100,Number(pct)||0));
 return `<div class="pctbar"><div class="bar"><span style="width:${w}%"></span></div><em>${fmt(pct)}%</em></div>`;
}
function drawCamp(horas,mode){
 if(CH.camp){try{CH.camp.destroy();}catch(e){}delete CH.camp;}
 const acum=mode==='acum';
 CH.camp=new Chart(document.getElementById('cHora'),{type:'bar',
  data:{labels:horas.map(h=>h.hora),
   datasets:[{label:'Jabas recepcionadas',
    data:horas.map(h=>acum?h.recepcion_acum:h.recepcion),backgroundColor:'#14532d'},
    {label:'Jabas abastecidas',
     data:horas.map(h=>acum?h.abastecimiento_acum:h.abastecimiento),backgroundColor:'#c9a227'}]},
  options:{responsive:true,interaction:{mode:'index',intersect:false},
   scales:{y:{beginAtZero:true}},
   plugins:{title:{display:true,text:acum?'Jabas acumuladas (fecha seleccionada)':'Jabas por hora (fecha seleccionada)'}}}});
}
function sumRow(label,s,cls){
 return `<tr class="${cls}"><td>${label}</td><td></td><td>${fmt(s.jabas_recepcion)}</td><td>${fmt(s.jabas_abastecimiento)}</td><td>${fmt(s.faltantes)}</td><td>${bar(s.avance_pct)}</td><td>${fmt(s.cajas_produccion)}</td><td>${fmt(s.cajas_equivalentes)}</td></tr>`;
}
function tabCampPacking(rows,subs,t){
 const byP={};(subs||[]).forEach(s=>{byP[s.planta]=s;});
 let h='<table><tr><th>Packing</th><th>Variedad</th><th>Jabas recepcionadas</th><th>Jabas abastecidas</th><th>Jabas faltantes</th><th>% avance</th><th>Cajas reales</th><th>Cajas equivalentes</th></tr>';
 let last=null;
 rows.forEach(r=>{
  if(last!==null&&last!==r.planta&&byP[last]){h+=sumRow('Subtotal '+last,byP[last],'subtotal');}
  last=r.planta;
  h+=`<tr><td>${r.planta||'—'}</td><td>${r.variedad||'—'}</td><td>${fmt(r.jabas_recepcion)}</td><td>${fmt(r.jabas_abastecimiento)}</td><td>${fmt(r.faltantes)}</td><td>${bar(r.avance_pct)}</td><td>${fmt(r.cajas_produccion)}</td><td>${fmt(r.cajas_equivalentes)}</td></tr>`;
 });
 if(last!==null&&byP[last]){h+=sumRow('Subtotal '+last,byP[last],'subtotal');}
 h+=sumRow('Total',t,'total');
 document.getElementById('cPacking').innerHTML=h+'</table>';
}
function drawPies(rows){
 dropPies();
 const box=document.getElementById('cPies');
 box.innerHTML='';
 const shown=rows.filter(r=>Number(r.jabas_recepcion)>0);
 if(!shown.length){box.innerHTML='<p class="note">Sin jabas recepcionadas para la fecha seleccionada.</p>';return;}
 shown.forEach(r=>{
  const rec=Number(r.jabas_recepcion)||0,aba=Number(r.jabas_abastecimiento)||0;
  const done=Math.min(aba,rec),missing=Math.max(rec-aba,0);
  const div=document.createElement('div');div.className='pie';
  const title=document.createElement('b');title.textContent=`${r.variedad||'—'} · ${fmt(r.avance_pct)}%`;
  const canvas=document.createElement('canvas');
  const cap=document.createElement('span');cap.className='note';
  cap.textContent=`${fmt(rec)} jabas · faltan ${fmt(r.faltantes)}`;
  div.append(title,canvas,cap);box.append(div);
  PIES.push(new Chart(canvas,{type:'doughnut',
   data:{labels:['Abastecidas','Faltantes'],
    datasets:[{data:[done,missing],backgroundColor:['#14532d','#e3e7e1'],borderWidth:0}]},
   options:{plugins:{legend:{display:false},
    tooltip:{callbacks:{label:x=>`${x.label}: ${fmt(x.raw)}`}}}},
   plugins:[pieLabels]}));
 });
}
function tabCampProd(rows,t){
 let h='<table><tr><th>Variedad</th><th>Cajas reales</th><th>Cajas equivalentes</th><th>Kilos reales</th></tr>';
 rows.forEach(r=>{h+=`<tr><td>${r.variedad||'—'}</td><td>${fmt(r.cajas_produccion)}</td><td>${fmt(r.cajas_equivalentes)}</td><td>${fmt(r.kilos)}</td></tr>`;});
 h+=`<tr class="total"><td>Total</td><td>${fmt(t.cajas_produccion)}</td><td>${fmt(t.cajas_equivalentes)}</td><td>${fmt(t.kilos)}</td></tr>`;
 document.getElementById('cProd').innerHTML=h+'</table>';
}
function tabCampHora(rows,k){
 let h='<table><tr><th>Hora</th><th>Jabas recepcionadas</th><th>Jabas abastecidas</th><th>Recepcionadas acumuladas</th><th>Abastecidas acumuladas</th></tr>';
   rows.forEach(r=>{h+=`<tr><td>${r.hora.includes('+')?r.hora:r.hora+':00'}</td><td>${fmt(r.recepcion)}</td><td>${fmt(r.abastecimiento)}</td><td>${fmt(r.recepcion_acum)}</td><td>${fmt(r.abastecimiento_acum)}</td></tr>`;});
 h+=`<tr class="total"><td>Total</td><td>${fmt(k.jabas_recepcion)}</td><td>${fmt(k.jabas_abastecimiento)}</td><td>—</td><td>—</td></tr>`;
 document.getElementById('cHoraTab').innerHTML=h+'</table>';
}
async function loadCampania(){
 showLoaderSoon();
 try{
  const q=new URLSearchParams({fecha:cFecha.value,planta:cPlanta.value,variedad:cVariedad.value});
  const a=await api('/api/campania?'+q);
  CAMP_LOADED=true;
  CAMP_DATA=a;
  fillCampFilters(a);
  document.getElementById('cStamp').textContent=a.ultima_actualizacion||'—';
  campKpis(a.kpis);drawCamp(a.por_hora,cModo.value);tabCampPacking(a.por_packing,a.subtotales_packing,a.totales);drawPies(a.por_variedad);tabCampProd(a.produccion,a.produccion_totales);tabCampHora(a.por_hora,a.kpis);
  hideLoader();
 }catch(err){
  clearTimeout(loaderTimer);
  const L=document.getElementById('loader');L.hidden=false;
  L.querySelector('p').textContent='No se pudo cargar la campaña. Revisa tu conexion y pulsa Aplicar.';
 }
}
async function refreshCampania(){await api('/api/campania/refresh',{method:'POST'});await loadCampania();}
async function refresh(){await api('/api/refresh',{method:'POST'});await load();}
load();
</script></body></html>"""


def _num(value):
    try:
        return float(str(value).replace(",", ""))
    except (ValueError, TypeError):
        return 0.0


def filter_rows(rows, desde=None, hasta=None, planta=None, variedad=None):
    """Keep rows inside the requested window and label picks (pure)."""
    out = []
    for row in rows:
        fecha = str(row.get(DATE_KEY) or "")[:10]
        if desde and fecha < desde:
            continue
        if hasta and fecha > hasta:
            continue
        if planta and str(row.get("planta_despacho") or "") != planta:
            continue
        if variedad and str(row.get("variedad") or "") != variedad:
            continue
        out.append(row)
    return out


def headers_of(rows):
    """Verbatim column names in first-seen order (pure)."""
    headers = []
    for row in rows:
        for key in row:
            if key not in headers:
                headers.append(key)
    return headers


def summarize(rows):
    """Totals for the visible rows (pure)."""
    return {
        "filas": len(rows),
        "cajas_produccion": sum(
            _num(r.get("cantidad_cajas_produccion")) for r in rows),
        "cajas_equivalentes": sum(
            _num(r.get("cantidad_cajas_equivalentes")) for r in rows),
        "cantidad_pallets": sum(
            _num(r.get("cantidad_pallets")) for r in rows),
    }


def describe(rows):
    """Filter options derived from the rows (pure)."""
    fechas = sorted({str(r.get(DATE_KEY) or "")[:10] for r in rows} - {""})
    plantas = sorted({str(r.get("planta_despacho") or "").strip()
                      for r in rows if str(r.get("planta_despacho") or "")})
    variedades = sorted({str(r.get("variedad") or "").strip()
                         for r in rows if str(r.get("variedad") or "")})
    return {"fechas": fechas, "plantas": plantas, "variedades": variedades}


@app.get("/")
def index():
    return Response(PAGE, mimetype="text/html")


@app.get("/api/meta")
def api_meta():
    rows = sheet_reader.read_all()
    body = describe(rows)
    body["ultima_actualizacion"] = sheet_reader.last_updated()
    return jsonify(body)


@app.get("/api/pallets")
def api_pallets():
    rows = sheet_reader.read_all()
    shown = filter_rows(
        rows,
        desde=request.args.get("desde") or None,
        hasta=request.args.get("hasta") or None,
        planta=request.args.get("planta") or None,
        variedad=request.args.get("variedad") or None)
    return jsonify({"headers": headers_of(rows),
                    "rows": shown,
                    "summary": summarize(shown),
                    "ultima_actualizacion": sheet_reader.last_updated()})


@app.get("/api/analytics")
def api_analytics():
    rows = sheet_reader.read_all()
    shown = filter_rows(
        rows,
        desde=request.args.get("desde") or None,
        hasta=request.args.get("hasta") or None,
        planta=request.args.get("planta") or None,
        variedad=request.args.get("variedad") or None)
    body = analytics.compute_analytics(shown)
    body["ultima_actualizacion"] = sheet_reader.last_updated()
    return jsonify(body)


@app.post("/api/refresh")
def api_refresh():
    rows = sheet_reader.refresh()
    return jsonify({"filas": len(rows),
                    "ultima_actualizacion": sheet_reader.last_updated()})


def _campania_body(data):
    body = campaign_analytics.collect(
        data,
        fecha=request.args.get("fecha") or None,
        planta=request.args.get("planta") or None,
        variedad=request.args.get("variedad") or None)
    body["ultima_actualizacion"] = campaign_reader.last_updated()
    return body


@app.get("/api/campania")
def api_campania():
    return jsonify(_campania_body(campaign_reader.read()))


@app.post("/api/campania/refresh")
def api_campania_refresh():
    return jsonify(_campania_body(campaign_reader.refresh()))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)),
            threaded=True)
