
const $ = id => document.getElementById(id);
const money = n => new Intl.NumberFormat('es-EC',{style:'currency',currency:'USD'}).format(Number(n||0));
let ultimaDiferencia = 0;
let workbookData = [];

function num(id){ return parseFloat($(id).value) || 0; }
function setMetric(id, value){
  const el=$(id); el.textContent=money(value);
  el.classList.remove('ok','bad','warn');
  if(Math.abs(value)<0.005) el.classList.add('ok');
  else el.classList.add('bad');
}
function calcular(){
  const fondo=num('fondoFijo'), sistema=num('saldoSistema'), rep=num('reposicion');
  const efectivo=num('efectivo'), vales=num('vales'), otros=num('otros');
  const teorico=+(fondo-rep).toFixed(2);
  const difSistema=+(sistema-teorico).toFixed(2);
  const fisico=+(efectivo+vales+otros).toFixed(2);
  const difFisica=+(fisico-teorico).toFixed(2);
  ultimaDiferencia=Math.abs(difSistema);

  $('saldoTeorico').textContent=money(teorico);
  setMetric('difSistema',difSistema);
  $('disponibleFisico').textContent=money(fisico);
  setMetric('difFisica',difFisica);

  let diag=[];
  if(Math.abs(difSistema)<0.005){
    diag.push('✅ El saldo de Contífico coincide con el saldo teórico del fondo.');
  }else{
    const sentido=difSistema<0?'MENOR':'MAYOR';
    diag.push(`❌ El saldo de Contífico está ${sentido} que el saldo teórico en ${money(Math.abs(difSistema))}.`);
    diag.push(`Debe revisarse un asiento, egreso, reposición, reverso o ajuste por aproximadamente ${money(Math.abs(difSistema))}.`);
  }
  if(vales>0) diag.push(`🧾 Existen ${money(vales)} en vales no registrados. Se muestran aparte y no deben usarse para ocultar una diferencia contable.`);
  if(Math.abs(difFisica)<0.005) diag.push('✅ El efectivo + vales + otros soportes cuadra con el saldo teórico.');
  else diag.push(`⚠️ El soporte físico presenta una diferencia de ${money(difFisica)} frente al saldo teórico.`);
  $('diagnostico').innerHTML=diag.join('<br><br>');

  const nombre=$('nombreCaja').value || 'Caja';
  $('conclusion').value =
`${nombre}
Fondo fijo: ${money(fondo)}
Reposición pendiente/actual: ${money(rep)}
Saldo teórico: ${money(teorico)}
Saldo Contífico: ${money(sistema)}
Diferencia contable: ${money(difSistema)}

Efectivo físico: ${money(efectivo)}
Vales no registrados: ${money(vales)}
Otros comprobantes pendientes: ${money(otros)}
Disponible físico: ${money(fisico)}
Diferencia física: ${money(difFisica)}

Diagnóstico: ${Math.abs(difSistema)<0.005 ? 'CUADRADO' : 'REVISAR MOVIMIENTO(S) POR ' + money(Math.abs(difSistema))}.`;
}

function normalizeKey(s){return String(s??'').trim().toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g,"");}
function getVal(row, keys){
  const entries=Object.entries(row);
  for(const k of keys){
    const hit=entries.find(([a])=>normalizeKey(a).includes(k));
    if(hit) return hit[1];
  }
  return '';
}
function parseMoney(v){
  if(typeof v==='number') return v;
  let s=String(v??'').trim().replace(/\$/g,'').replace(/\s/g,'');
  if(!s) return 0;
  if(s.includes(',') && s.includes('.')){
    if(s.lastIndexOf(',')>s.lastIndexOf('.')) s=s.replace(/\./g,'').replace(',','.');
    else s=s.replace(/,/g,'');
  } else if(s.includes(',')) s=s.replace(',','.');
  return parseFloat(s)||0;
}
function analizarDatos(){
  const tbody=$('tablaHallazgos').querySelector('tbody'); tbody.innerHTML='';
  if(!workbookData.length){$('archivoInfo').textContent='Primero selecciona un archivo.';return;}
  const objetivo=ultimaDiferencia || Math.abs(num('saldoSistema')-(num('fondoFijo')-num('reposicion')));
  const hallazgos=[];
  workbookData.forEach((row,i)=>{
    const debe=parseMoney(getVal(row,['debe','debito','débito']));
    const haber=parseMoney(getVal(row,['haber','credito','crédito']));
    const valor=parseMoney(getVal(row,['valor','monto','total','importe','saldo']));
    const candidates=[Math.abs(debe),Math.abs(haber),Math.abs(valor),Math.abs(debe-haber)].filter(x=>x>0);
    const best=Math.min(...candidates.map(x=>Math.abs(x-objetivo)),999999);
    if(best<=0.01 || candidates.some(x=>Math.abs(x-objetivo)<=0.01)){
      hallazgos.push({i,row,debe,haber,valor,match:'Coincide con diferencia'});
    }
  });
  // also find pairs that sum to objective
  if(hallazgos.length===0 && workbookData.length<=1500){
    const vals=workbookData.map((row,i)=>{
      const debe=Math.abs(parseMoney(getVal(row,['debe','debito','débito'])));
      const haber=Math.abs(parseMoney(getVal(row,['haber','credito','crédito'])));
      const valor=Math.abs(parseMoney(getVal(row,['valor','monto','total','importe'])));
      return {i,row,v:Math.max(debe,haber,valor),debe,haber,valor};
    }).filter(x=>x.v>0);
    outer: for(let a=0;a<vals.length;a++){
      for(let b=a+1;b<vals.length;b++){
        if(Math.abs((vals[a].v+vals[b].v)-objetivo)<=0.01){
          hallazgos.push({...vals[a],match:'Parte de combinación'});
          hallazgos.push({...vals[b],match:'Parte de combinación'});
          break outer;
        }
      }
    }
  }
  if(!hallazgos.length){
    $('archivoInfo').textContent=`No encontré un movimiento individual o pareja que coincida exactamente con ${money(objetivo)}. Revisa nombres de columnas o movimientos acumulados.`;
    return;
  }
  $('archivoInfo').textContent=`Se encontraron ${hallazgos.length} movimiento(s) relacionados con una diferencia objetivo de ${money(objetivo)}.`;
  hallazgos.slice(0,50).forEach(h=>{
    const row=h.row;
    const tr=document.createElement('tr');
    const fecha=getVal(row,['fecha']);
    const asiento=getVal(row,['asiento','documento','comprobante','numero','número']);
    const detalle=getVal(row,['detalle','descripcion','descripción','concepto','glosa']);
    tr.innerHTML=`<td>${h.i+2}</td><td>${fecha??''}</td><td>${asiento??''}</td><td>${detalle??''}</td>
      <td>${money(h.debe)}</td><td>${money(h.haber)}</td><td>${money(h.valor)}</td><td><strong>${h.match}</strong></td>`;
    tbody.appendChild(tr);
  });
}

$('archivo').addEventListener('change', async e=>{
  const file=e.target.files[0]; if(!file)return;
  try{
    const data=await file.arrayBuffer();
    const wb=XLSX.read(data,{type:'array',cellDates:true});
    workbookData=[];
    wb.SheetNames.forEach(name=>{
      const rows=XLSX.utils.sheet_to_json(wb.Sheets[name],{defval:''});
      workbookData.push(...rows);
    });
    $('archivoInfo').textContent=`Archivo cargado: ${file.name}. Registros detectados: ${workbookData.length}.`;
  }catch(err){
    $('archivoInfo').textContent='No se pudo leer el archivo: '+err.message;
  }
});
$('calcularBtn').addEventListener('click',calcular);
$('analizarArchivoBtn').addEventListener('click',()=>{calcular();analizarDatos();});
$('copiarBtn').addEventListener('click',async()=>{await navigator.clipboard.writeText($('conclusion').value);$('copiarBtn').textContent='Copiado';setTimeout(()=>$('copiarBtn').textContent='Copiar conclusión',1200);});
$('descargarBtn').addEventListener('click',()=>{
  const blob=new Blob([$('conclusion').value],{type:'text/plain;charset=utf-8'});
  const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download='conclusion_cuadre_caja.txt';a.click();URL.revokeObjectURL(a.href);
});
$('resetBtn').addEventListener('click',()=>location.reload());
calcular();
