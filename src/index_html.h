#ifndef INDEX_HTML_H
#define INDEX_HTML_H

#include <pgmspace.h>

const char INDEX_HTML[] PROGMEM = R"rawliteral(
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>pleasure-protocol — 为 AI 控制铺路</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,system-ui,sans-serif;background:#0a0a1a;color:#e0e0e0;min-height:100vh;overflow-x:hidden}
.header{background:linear-gradient(135deg,#1a1a3e,#0f2027);padding:16px 20px;display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid #2a2a4a}
.header h1{font-size:20px;font-weight:600}
.status-bar{display:flex;gap:12px;align-items:center;font-size:13px}
.status-dot{width:10px;height:10px;border-radius:50%;display:inline-block}
.status-dot.on{background:#00e676;box-shadow:0 0 8px #00e676}
.status-dot.off{background:#ff5252}
.container{max-width:600px;margin:0 auto;padding:16px}
.card{background:#12122a;border:1px solid #2a2a4a;border-radius:12px;padding:20px;margin-bottom:16px}
.card-title{font-size:16px;font-weight:600;margin-bottom:12px;display:flex;align-items:center;gap:8px}
.card-title .icon{font-size:20px}
.btn{border:none;border-radius:8px;padding:10px 20px;font-size:14px;font-weight:500;cursor:pointer;transition:all 0.2s;color:#fff}
.btn:active{transform:scale(0.96)}
.btn-primary{background:linear-gradient(135deg,#0f3460,#16213e)}
.btn-primary:hover{background:linear-gradient(135deg,#1a4a7a,#1e2d50)}
.btn-danger{background:linear-gradient(135deg,#8b0000,#5c0000)}
.btn-danger:hover{background:linear-gradient(135deg,#a50000,#700000)}
.btn-success{background:linear-gradient(135deg,#006400,#004d00)}
.btn-success:hover{background:linear-gradient(135deg,#008000,#006000)}
.btn-secondary{background:#2a2a4a;color:#aaa}
.btn-secondary:hover{background:#3a3a5a}
.btn:disabled{opacity:0.4;cursor:not-allowed}
.btn-row{display:flex;gap:8px;flex-wrap:wrap}
.shock-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin-top:12px}
.shock-btn{padding:12px 8px;border:2px solid #2a2a4a;border-radius:10px;background:#1a1a3e;color:#e0e0e0;font-size:13px;font-weight:600;cursor:pointer;transition:all 0.2s;text-align:center}
.shock-btn:hover{border-color:#0f3460}
.shock-btn.active{border-color:#ff6b35;background:#2a1a10;color:#ff6b35}
.shock-btn.danger{border-color:#ff5252}
.shock-btn.danger.active{background:#3a1010;color:#ff5252;border-color:#ff0000}
.vib-slider-wrap{margin:16px 0}
.vib-slider{width:100%;height:8px;-webkit-appearance:none;appearance:none;background:linear-gradient(90deg,#1a1a3e,#0f3460);border-radius:4px;outline:none}
.vib-slider::-webkit-slider-thumb{-webkit-appearance:none;width:24px;height:24px;border-radius:50%;background:#0f3460;border:3px solid #e0e0e0;cursor:pointer}
.vib-value{text-align:center;font-size:28px;font-weight:700;margin:8px 0;color:#0f8cf0}
.vib-labels{display:flex;justify-content:space-between;font-size:11px;color:#666}
.light-btn{width:60px;height:60px;border-radius:50%;border:3px solid #2a2a4a;background:#1a1a3e;cursor:pointer;transition:all 0.3s;font-size:24px}
.light-btn.on{background:#ffd700;border-color:#ffd700;box-shadow:0 0 20px #ffd70066}
.conn-input{flex:1;background:#1a1a3e;border:1px solid #2a2a4a;border-radius:8px;padding:10px 12px;color:#e0e0e0;font-size:13px}
.conn-input::placeholder{color:#555}
.device-list{max-height:200px;overflow-y:auto;margin-top:12px}
.device-item{display:flex;justify-content:space-between;align-items:center;padding:10px 12px;border:1px solid #2a2a4a;border-radius:8px;margin-bottom:6px;cursor:pointer;transition:all 0.2s}
.device-item:hover{border-color:#0f3460;background:#1a1a3e}
.device-item .name{font-weight:500;font-size:14px}
.device-item .addr{font-size:11px;color:#888}
.log-box{background:#0a0a15;border:1px solid #2a2a4a;border-radius:8px;padding:10px;font-family:monospace;font-size:12px;max-height:120px;overflow-y:auto;margin-top:10px;color:#888}
.log-entry{padding:2px 0}
.log-entry.sent{color:#00e676}
.log-entry.recv{color:#0f8cf0}
.log-entry.err{color:#ff5252}
</style>
</head>
<body>
<div class="header">
  <h1>pleasure-protocol</h1>
  <div class="status-bar">
    <span style="font-size:11px;color:#888;margin-right:8px">为 AI 控制铺路</span>
    <span class="status-dot" id="wsDot"></span><span id="wsLabel">WS:--</span>
    <span class="status-dot" id="bleDot"></span><span id="bleLabel">蓝牙:--</span>
  </div>
</div>
<div class="container">
  <div class="card">
    <div class="card-title"><span class="icon">&#128225;</span>连接</div>
    <div class="btn-row">
      <button class="btn btn-primary" onclick="doScan()">扫描</button>
      <button class="btn btn-danger" onclick="doDisconnect()">断开</button>
      <button class="btn btn-secondary" onclick="doHeartbeat()">心跳</button>
    </div>
    <div style="display:flex;gap:8px;align-items:center;margin-top:10px">
      <input class="conn-input" id="addrInput" placeholder="MAC 地址（扫描自动填入）">
      <button class="btn btn-success" onclick="doConnectAddr()">连接</button>
    </div>
    <div class="device-list" id="deviceList"></div>
  </div>
  <div class="card">
    <div class="card-title"><span class="icon">&#9889;</span>电击</div>
    <div class="btn-row"><button class="btn btn-danger" onclick="doShockOff()">关闭</button></div>
    <div class="shock-grid" id="shockGrid"></div>
  </div>
  <div class="card">
    <div class="card-title"><span class="icon">&#128316;</span>震动</div>
    <div class="vib-value" id="vibValue">0</div>
    <div class="vib-slider-wrap">
      <input type="range" class="vib-slider" id="vibSlider" min="0" max="100" value="0">
      <div class="vib-labels"><span>关闭</span><span>最低</span><span>最高</span></div>
    </div>
    <div class="btn-row">
      <button class="btn btn-secondary" onclick="setVib(0)">关闭</button>
      <button class="btn btn-secondary" onclick="setVib(25)">25%</button>
      <button class="btn btn-secondary" onclick="setVib(50)">50%</button>
      <button class="btn btn-secondary" onclick="setVib(75)">75%</button>
      <button class="btn btn-primary" onclick="setVib(100)">100%</button>
    </div>
  </div>
  <div class="card" style="text-align:center">
    <div class="card-title" style="justify-content:center"><span class="icon">&#128161;</span>灯光</div>
    <button class="light-btn" id="lightBtn" onclick="doLightToggle()">&#9790;</button>
  </div>
  <div class="card">
    <div class="card-title"><span class="icon">&#9881;</span>设置</div>
    <div class="btn-row">
      <button class="btn btn-secondary" onclick="setHB(3000)">心跳 3s</button>
      <button class="btn btn-secondary" onclick="setHB(5000)">心跳 5s</button>
      <button class="btn btn-secondary" onclick="setHB(10000)">心跳 10s</button>
      <button class="btn btn-secondary" onclick="openOTA()">固件升级</button>
    </div>
  </div>
  <div class="card">
    <div class="card-title"><span class="icon">&#128196;</span>日志</div>
    <div class="log-box" id="logBox"></div>
    <button class="btn btn-secondary" style="margin-top:8px" onclick="document.getElementById('logBox').innerHTML=''">清空</button>
  </div>
</div>
<script>
var ws,wsOK=false;
function connectWS(){
  var h=location.hostname||'192.168.4.1';
  ws=new WebSocket('ws://'+h+':81/');
  ws.onopen=function(){wsOK=true;updWS(true);log('WebSocket 已连接','recv');};
  ws.onclose=function(){wsOK=false;updWS(false);setTimeout(connectWS,3000);};
  ws.onmessage=function(e){handle(JSON.parse(e.data));};
  ws.onerror=function(){log('WebSocket 错误','err');};
}
function send(o){if(!ws||ws.readyState!==1)return;var j=JSON.stringify(o);ws.send(j);log('>> '+j,'sent');}
function updWS(ok){document.getElementById('wsDot').className='status-dot '+(ok?'on':'off');document.getElementById('wsLabel').textContent='WS:'+(ok?'OK':'--');}
function updBLE(ok){document.getElementById('bleDot').className='status-dot '+(ok?'on':'off');document.getElementById('bleLabel').textContent='蓝牙:'+(ok?'已连接':'--');}
function handle(m){
  if(m.type==='status'){updBLE(m.ble_connected);log('状态: BLE='+(m.ble_connected?'已连接':'未连接')+' 心跳='+(m.heartbeat?'开':'关'),'recv');}
  if(m.type==='scan_result'){var l=document.getElementById('deviceList');l.innerHTML='';m.devices.forEach(function(d){var div=document.createElement('div');div.className='device-item';div.innerHTML='<div><div class="name">'+d.name+'</div><div class="addr">'+d.address+'</div></div>';div.onclick=function(){document.getElementById('addrInput').value=d.address;doConnectAddr();};l.appendChild(div);});log('发现 '+m.devices.length+' 个设备','recv');}
  if(m.type==='response'){log('<< '+m.action+': '+(m.success?'成功':'失败'),m.success?'recv':'err');}
}
function doScan(){send({action:'scan'});}
function doConnectAddr(){var a=document.getElementById('addrInput').value.trim();if(a)send({action:'connect',address:a});}
function doDisconnect(){send({action:'disconnect'});}
function doShockOff(){send({action:'shock_off'});document.querySelectorAll('.shock-btn').forEach(function(b){b.classList.remove('active');});}
function doShockLevel(lv){send({action:'shock_level',level:lv});document.querySelectorAll('.shock-btn').forEach(function(b){b.classList.remove('active');});document.getElementById('sb'+lv).classList.add('active');}
var vibT;
document.getElementById('vibSlider').oninput=function(){document.getElementById('vibValue').textContent=this.value;};
document.getElementById('vibSlider').onchange=function(){var v=parseInt(this.value);clearTimeout(vibT);vibT=setTimeout(function(){setVib(v);},100);};
function setVib(p){send({action:'vibration_level',percent:p});document.getElementById('vibSlider').value=p;document.getElementById('vibValue').textContent=p;}
function doLightToggle(){send({action:'light_toggle'});document.getElementById('lightBtn').classList.toggle('on');}
var hbOn=false;
function doHeartbeat(){hbOn=!hbOn;send({action:hbOn?'heartbeat_start':'heartbeat_stop',interval:5000});}
function setHB(ms){hbOn=true;send({action:'heartbeat_start',interval:ms});}
function openOTA(){var h=location.hostname||'192.168.4.1';window.open('http://'+h+'/ota','_blank');}
(function(){var g=document.getElementById('shockGrid');var lb=['关闭','空闲','1档','2档','3档','4档','5档','6档'];for(var i=0;i<8;i++){var b=document.createElement('button');b.className='shock-btn'+(i>=4?' danger':'');b.id='sb'+i;b.textContent=lb[i];b.onclick=(function(l){return function(){if(l===0)doShockOff();else doShockLevel(l);};})(i);g.appendChild(b);}})();
function log(m,c){var b=document.getElementById('logBox');var d=document.createElement('div');d.className='log-entry '+(c||'');d.textContent='['+new Date().toLocaleTimeString()+'] '+m;b.appendChild(d);b.scrollTop=b.scrollHeight;while(b.children.length>100)b.removeChild(b.firstChild);}
connectWS();
</script>
</body>
</html>
)rawliteral";

#endif // INDEX_HTML_H
