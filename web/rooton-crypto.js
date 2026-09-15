/* ROOTON visual adapter: uses the existing ETF, sector and membership data. */
(() => {
 'use strict';
 const ui=RootonUI,E=ui.escape;
 let allSectors=false,period=30;
 document.body.classList.add('rt-app','rt-crypto');
 document.documentElement.dataset.theme='light';
 document.querySelector('.brand').outerHTML='<a class="rt-brand" href="https://mainsaju.shop/">ROOTON<small>자금의 흐름을 읽다</small></a>';
 document.querySelector('.rt-brand').insertAdjacentHTML('afterend','<nav class="rt-brand-nav" aria-label="서비스"><a href="https://theme-board.pages.dev/">국내주식</a><a href="https://theme-board.pages.dev/?market=us">해외주식</a><a href="./" aria-current="page">크립토</a></nav>');
 document.querySelector('#nav [data-v="coin"]').textContent='섹터·코인';
 document.querySelector('#nav [data-v="dash"]').textContent='ETF 자금흐름';
 document.getElementById('home-px').closest('section').classList.add('rt-home-prices');
 document.getElementById('home-hero').closest('section').classList.add('rt-home-flow');
 document.getElementById('home-feed').closest('section').classList.add('rt-home-news');
 const home=document.getElementById('view-home');
 home.insertAdjacentHTML('afterbegin','<section class="rt-hero" id="rt-crypto-hero"><div class="rt-hero-copy"><p class="rt-eyebrow">CRYPTO · MARKET PULSE</p><h1>IBIT · 비트코인 현물 ETF</h1><div class="rt-number" id="rt-crypto-price">—</div><div class="rt-hero-meta" id="rt-crypto-status">시계열을 불러오고 있습니다</div></div><div><div class="rt-hero-tabs"><button data-rt-period="30" aria-pressed="true">30일</button><button data-rt-period="90" aria-pressed="false">90일</button><button data-rt-period="0" aria-pressed="false">전체</button></div><div id="rt-crypto-plot"></div></div></section><div class="rt-crypto-metrics" id="rt-crypto-metrics"></div>');
 const originalHome=drawHome;
 function hero(){
  if(!D)return;
  const series=(D.prices||{}).IBIT||{};
  let days=Object.keys(series).sort();if(period)days=days.slice(-period);
  const last=days.at(-1),first=days[0],change=last&&first&&series[first]?(series[last]/series[first]-1)*100:null;
  document.getElementById('rt-crypto-price').innerHTML=last?E(price(series[last])):'—';
  document.getElementById('rt-crypto-status').innerHTML=(change!=null?'<strong class="'+(change>=0?'up':'dn')+'">'+(change>0?'+':'')+change.toFixed(2)+'%</strong> 기간 등락<br>':'')+(last?E(ymd(last))+' 종가 · BTC 현물 가격과 다릅니다':'가격 데이터 수집 중');
  ui.chart(document.getElementById('rt-crypto-plot'),days.map(d=>({value:series[d],label:ymd(d),shortLabel:d.slice(4,6)+'.'+d.slice(6,8),time:Date.parse(d.slice(0,4)+'-'+d.slice(4,6)+'-'+d.slice(6,8))})),{label:'IBIT 비트코인 현물 ETF 종가 추이',format:v=>price(v),axis:v=>rate()?(v*rate()/10000).toFixed(1)+'만':'$'+v.toFixed(1),note:'저장된 일별 종가 · 기간 버튼으로 범위 변경'});
  const flow=D.flows?.latest,kp=D.coins?.kimchi_pct||D.coins?.kimchi||{};
  const k=typeof kp.BTC==='number'?kp.BTC:null;
  document.getElementById('rt-crypto-metrics').innerHTML=[
   ['BTC 현물',D.coins?.krw?.BTC?.price_krw!=null?priceKRW(D.coins.krw.BTC.price_krw):'—','업비트 · '+(D.ts||'스냅샷'),null],
   ['ETF 최근 순유입',flow?signed(flow.total):'—',flow?ymd(flow.date)+' · BTC + ETH':'수집 중',flow?.total],
   ['BTC 김치프리미엄',k!=null?(k>=0?'+':'')+k.toFixed(2)+'%':'확인 중','동일 집계 시점 가격 · 환율 기준',k]
  ].map(([title,v,n,ch])=>'<article class="rt-raised rt-metric"><span>'+E(title)+'</span><strong style="'+(ch!=null?'color:var(--'+(ch>=0?'up':'down')+')':'')+'">'+E(v)+'</strong><small>'+E(n)+'</small></article>').join('');
 }
 drawHome=function(){originalHome();hero();};
 const tabs=document.getElementById('sec-tabs');
 tabs.insertAdjacentHTML('afterend','<div class="rt-sector-tools"><p class="rt-micro">섹터를 선택하면 구성 코인과 지수를 함께 볼 수 있습니다.</p><button class="btn" id="rt-sector-expand">전체 섹터 보기</button></div><div class="rt-grid" id="rt-sector-grid"></div>');
 const idx=document.getElementById('sec-idx-card');
 idx.insertAdjacentHTML('beforeend','<div id="rt-sector-chart"></div>');
 const originalSector=drawSector;
 function sectorCards(){
  if(!TK)return;
  let sectors=secList(false);
  const count=sectors.length;if(!allSectors)sectors=sectors.slice(0,6);
  document.getElementById('rt-sector-expand').textContent=allSectors?'주요 6개 보기':'전체 '+count+'개 섹터 보기';
  document.getElementById('rt-sector-grid').innerHTML=sectors.map(s=>{
   const st=secStat(s.k),coins=members(s.k,document.getElementById('sec-major').checked).slice(0,3);
   return '<article class="rt-raised rt-sector-card '+(SEC_CUR===s.k?'is-selected':'')+'"><div class="rt-card-top"><span class="rt-emblem">'+ui.icon(ui.kind(s.n))+'</span><div class="rt-card-title"><button data-rt-sector="'+E(s.k)+'">'+E(s.n)+'</button><small>'+(st?st.n:0)+'개 코인 · 동일가중</small></div><strong class="rt-card-pct" style="color:var(--'+(st?upcls(st.ch):'text-muted')+')">'+(st?pct2(st.ch):'—')+'</strong></div><div class="rt-stock-rows">'+(coins.length?coins.map(c=>'<div class="rt-stock-row"><span>'+E(MK[c]?.ko||c)+'</span><span class="rt-row-value">'+E(cprice(TK[c].p))+'</span><span class="rt-row-rate" style="color:var(--'+upcls(TK[c].ch)+')">'+pct2(TK[c].ch)+'</span></div>').join(''):'<p class="rt-micro">조건에 맞는 코인이 없습니다.</p>')+'</div><button class="rt-card-more" data-rt-sector="'+E(s.k)+'">구성 코인 · 지수 보기 →</button></article>';
  }).join('')||'<p class="rt-micro">표시할 섹터가 없습니다. 섹터 설정을 확인하세요.</p>';
 }
 drawSector=function(){if(!secList(false).length)SEC_CUR=null;originalSector();sectorCards();};
 document.getElementById('sec-major').addEventListener('change',sectorCards);
 const oldSpark=drawSpark;
 drawSpark=function(vals,sel){
  oldSpark(vals,sel);
  if(!sel||sel==='#sec-spk'){
   ui.chart(document.getElementById('rt-sector-chart'),(vals||[]).map((v,i)=>({value:v,label:(vals.length-1-i)?(vals.length-1-i)+'시간 전':'최근',shortLabel:i===vals.length-1?'최근':'-'+(vals.length-1-i)+'h'})),{label:'선택 섹터 동일가중 지수 추이',format:v=>v.toFixed(2),axis:v=>v.toFixed(1),emptyTitle:'섹터 지수를 불러오고 있습니다',empty:'구성 코인의 60분봉을 집계합니다. 연결되지 않으면 가격 목록을 먼저 확인할 수 있습니다.',note:'시간별 종가 기반 · 구성 코인 동일가중'});
  }
 };
 document.addEventListener('click',e=>{
  const periodButton=e.target.closest('[data-rt-period]');
  if(periodButton){period=+periodButton.dataset.rtPeriod;document.querySelectorAll('[data-rt-period]').forEach(b=>b.setAttribute('aria-pressed',b===periodButton));hero();}
  const sector=e.target.closest('[data-rt-sector]');
  if(sector){SEC_CUR=sector.dataset.rtSector;drawSector();drawCoinFlow();document.getElementById('sec-idx-card').scrollIntoView({block:'nearest',behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'auto':'smooth'});}
  if(e.target.closest('#rt-sector-expand')){allSectors=!allSectors;sectorCards();}
 });
 // Retain all existing price chart news markers and their event handlers.
 const oldPriceChart=drawPriceChart;
 drawPriceChart=function(){
  oldPriceChart();
  const svg=document.getElementById('px-svg');if(!svg)return;
  const defs=el('defs');const grad=el('linearGradient',{id:'rt-etf-line',x1:'0',x2:'1'});
  grad.append(el('stop',{offset:'0','stop-color':'#5f94aa'}),el('stop',{offset:'1','stop-color':'#ab8841'}));defs.append(grad);svg.prepend(defs);
  const path=svg.querySelector('path[fill="none"]');if(path){path.setAttribute('stroke','url(#rt-etf-line)');path.setAttribute('stroke-width','2.2');}
 };
 const oldGoto=goto;
 goto=function(view){oldGoto(view);if(view==='home'&&D)hero();};
 if(D)drawHome();
 const jump=new URLSearchParams(location.search).get('view');
 if(['home','coin','dash','news','comm'].includes(jump)){goto(jump);if(jump==='news'&&!N)loadNews();if(jump==='comm')loadPosts(true);}
})();

