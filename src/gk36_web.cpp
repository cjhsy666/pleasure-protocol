#include "gk36_web.h"
#include "index_html.h"

GK36Web::GK36Web(GK36BLE* ble) : _ble(ble) {}

GK36Web::~GK36Web() {
    stop();
}

bool GK36Web::beginAP(const char* ssid, const char* pass) {
    _apMode = true;
    WiFi.mode(WIFI_AP);
    WiFi.softAP(ssid, pass);

    Serial.printf("[WEB] 热点已启动: %s\n", ssid);
    Serial.printf("[WEB] IP: %s\n", WiFi.softAPIP().toString().c_str());

    MDNS.begin("pleasure-protocol");

    _server = new WebServer(WEB_PORT);
    _ws = new WebSocketsServer(WS_PORT);

    _server->on("/", [this]() { _handleRoot(); });
    _server->on("/api", HTTP_GET, [this]() { _handleAPI(); });
    _server->on("/ota", HTTP_GET, [this]() { _handleOTA(); });
    _server->on("/update", HTTP_POST, [this]() { _handleOTAUpdate(); },
                [this]() { _handleOTAUpdate(); });

    _server->begin();

    _ws->begin();
    _ws->onEvent([this](uint8_t num, WStype_t type, uint8_t* payload, size_t length) {
        _webSocketEvent(num, type, payload, length);
    });

    Serial.println("[WEB] HTTP 服务已启动 (端口 80)");
    Serial.println("[WEB] WebSocket 服务已启动 (端口 81)");

    return true;
}

bool GK36Web::beginSTA(const char* ssid, const char* pass) {
    _apMode = false;
    WiFi.mode(WIFI_STA);
    WiFi.begin(ssid, pass);

    Serial.printf("[WEB] 正在连接 %s", ssid);
    int attempts = 0;
    while (WiFi.status() != WL_CONNECTED && attempts < 20) {
        delay(500);
        Serial.print(".");
        attempts++;
    }

    if (WiFi.status() != WL_CONNECTED) {
        Serial.println(" 失败");
        return false;
    }

    Serial.printf("\n[WEB] 已连接, IP: %s\n", WiFi.localIP().toString().c_str());

    MDNS.begin("pleasure-protocol");

    _server = new WebServer(WEB_PORT);
    _ws = new WebSocketsServer(WS_PORT);

    _server->on("/", [this]() { _handleRoot(); });
    _server->on("/api", HTTP_GET, [this]() { _handleAPI(); });
    _server->on("/ota", HTTP_GET, [this]() { _handleOTA(); });
    _server->on("/update", HTTP_POST, [this]() { _handleOTAUpdate(); },
                [this]() { _handleOTAUpdate(); });

    _server->begin();
    _ws->begin();
    _ws->onEvent([this](uint8_t num, WStype_t type, uint8_t* payload, size_t length) {
        _webSocketEvent(num, type, payload, length);
    });

    return true;
}

void GK36Web::stop() {
    if (_server) { _server->stop(); delete _server; _server = nullptr; }
    if (_ws) { _ws->stop(); delete _ws; _ws = nullptr; }
    MDNS.end();
    WiFi.disconnect(true);
}

String GK36Web::getIPAddress() {
    if (_apMode) return WiFi.softAPIP().toString();
    return WiFi.localIP().toString();
}

void GK36Web::handleClient() {
    if (_server) _server->handleClient();
}

void GK36Web::handleWebSocket() {
    if (_ws) _ws->loop();
}

// ---- HTTP ----

void GK36Web::_handleRoot() {
    _server->send_P(200, "text/html", INDEX_HTML);
}

void GK36Web::_handleAPI() {
    StaticJsonDocument<512> doc;

    doc["ble_state"] = _ble->getState();
    doc["ble_connected"] = _ble->isConnected();
    doc["device_address"] = _ble->getDeviceAddress();
    doc["device_name"] = _ble->getDeviceName();
    doc["heartbeat"] = _ble->isHeartbeatRunning();
    doc["ip"] = getIPAddress();
    doc["ap_mode"] = _apMode;
    doc["uptime"] = millis() / 1000;

    String json;
    serializeJson(doc, json);
    _server->send(200, "application/json", json);
}

void GK36Web::_handleOTA() {
    String html = R"rawliteral(
<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>固件升级 — pleasure-protocol</title>
<style>body{font-family:monospace;background:#1a1a2e;color:#eee;text-align:center;padding:40px;}
input[type=file]{margin:20px;}button{padding:10px 30px;font-size:16px;cursor:pointer;}
#progress{width:80%;margin:20px auto;height:20px;background:#333;border-radius:10px;display:none;}
#bar{height:100%;background:#0f3460;width:0%;border-radius:10px;transition:width 0.3s;}
</style></head><body>
<h1>固件升级</h1>
<input type="file" id="file" accept=".bin">
<button onclick="upload()">上传</button>
<div id="progress"><div id="bar"></div></div>
<div id="status"></div>
<script>
function upload(){
  var f=document.getElementById('file').files[0];if(!f){alert('请选择固件文件');return;}
  var fd=new FormData();fd.append('update',f);
  var xhr=new XMLHttpRequest();
  document.getElementById('progress').style.display='block';
  xhr.upload.onprogress=function(e){if(e.lengthComputable)
    document.getElementById('bar').style.width=(e.loaded/e.total*100)+'%';};
  xhr.onload=function(){document.getElementById('status').innerText='完成！正在重启...';setTimeout(()=>location.reload(),3000);};
  xhr.onerror=function(){document.getElementById('status').innerText='上传失败！';};
  xhr.open('POST','/update');xhr.send(fd);
}
</script></body></html>
)rawliteral";
    _server->send(200, "text/html", html);
}

void GK36Web::_handleOTAUpdate() {
    if (_server->method() == HTTP_POST) {
        HTTPUpload& upload = _server->upload();

        if (upload.status == UPLOAD_FILE_START) {
            Serial.printf("[OTA] 开始升级: %s\n", upload.filename.c_str());
            Update.begin(UPDATE_SIZE_UNKNOWN);
        } else if (upload.status == UPLOAD_FILE_WRITE) {
            if (Update.write(upload.buf, upload.currentSize) != upload.currentSize) {
                Serial.println("[OTA] 写入错误");
            }
        } else if (upload.status == UPLOAD_FILE_END) {
            if (Update.end(true)) {
                Serial.printf("[OTA] 完成: %u 字节\n", upload.totalSize);
            } else {
                Update.printError(Serial);
            }
        }
    } else {
        _server->send(200, "text/plain",
                      Update.hasError() ? "FAIL" : "OK");
    }
}

// ---- WebSocket ----

void GK36Web::_webSocketEvent(uint8_t num, WStype_t type, uint8_t* payload, size_t length) {
    switch (type) {
        case WStype_DISCONNECTED:
            _wsClientCount--;
            Serial.printf("[WS] 客户端 #%u 已断开\n", num);
            break;

        case WStype_CONNECTED:
            _wsClientCount++;
            Serial.printf("[WS] 客户端 #%u 已连接\n", num);
            {
                StaticJsonDocument<256> doc;
                doc["type"] = "status";
                doc["ble_connected"] = _ble->isConnected();
                doc["heartbeat"] = _ble->isHeartbeatRunning();
                String json;
                serializeJson(doc, json);
                _ws->sendTXT(num, json);
            }
            break;

        case WStype_TEXT: {
            StaticJsonDocument<512> doc;
            DeserializationError err = deserializeJson(doc, payload, length);
            if (err) {
                Serial.printf("[WS] JSON 解析错误: %s\n", err.c_str());
                return;
            }
            _processCommand(String((char*)payload), doc);
            break;
        }

        default:
            break;
    }
}

void GK36Web::_processCommand(const String& cmd, JsonDocument& doc) {
    const char* action = doc["action"];
    if (!action) return;

    String act = String(action);
    bool success = false;

    if (act == "scan") {
        _ble->startScan(10);
        String names[20], addrs[20];
        int count = _ble->getScanResults(names, addrs, 20);

        StaticJsonDocument<1024> result;
        result["type"] = "scan_result";
        JsonArray arr = result.createNestedArray("devices");
        for (int i = 0; i < count; i++) {
            JsonObject dev = arr.createNestedObject();
            dev["index"] = i;
            dev["name"] = names[i];
            dev["address"] = addrs[i];
        }
        String json;
        serializeJson(result, json);
        _ws->broadcastTXT(json);
        return;
    }

    if (act == "connect") {
        int index = doc["index"] | -1;
        String address = doc["address"] | "";
        if (address.length() > 0) {
            success = _ble->connectToAddress(address);
        } else {
            success = _ble->connect(index);
        }
    }

    if (act == "disconnect") {
        _ble->disconnect();
        success = true;
    }

    if (act == "shock_off") {
        success = _ble->sendShockOff();
    }

    if (act == "shock_level") {
        int level = doc["level"] | 0;
        success = _ble->sendShockLevel(level);
    }

    if (act == "vibration_off") {
        success = _ble->sendVibrationOff();
    }

    if (act == "vibration_level") {
        int percent = doc["percent"] | 0;
        success = _ble->sendVibrationLevel(percent);
    }

    if (act == "vibration_raw") {
        int b6 = doc["b6"] | 0x3B;
        success = _ble->sendVibrationRaw(b6);
    }

    if (act == "light_toggle") {
        success = _ble->sendLightToggle();
    }

    if (act == "heartbeat_start") {
        int interval = doc["interval"] | 5000;
        _ble->startHeartbeat(interval);
        success = true;
    }

    if (act == "heartbeat_stop") {
        _ble->stopHeartbeat();
        success = true;
    }

    StaticJsonDocument<128> resp;
    resp["type"] = "response";
    resp["action"] = act;
    resp["success"] = success;
    String json;
    serializeJson(resp, json);
    _ws->broadcastTXT(json);
}

void GK36Web::broadcastStatus() {
    if (_wsClientCount == 0) return;

    StaticJsonDocument<256> doc;
    doc["type"] = "status";
    doc["ble_connected"] = _ble->isConnected();
    doc["heartbeat"] = _ble->isHeartbeatRunning();
    doc["device"] = _ble->getDeviceName();
    doc["rssi"] = 0;

    String json;
    serializeJson(doc, json);
    _ws->broadcastTXT(json);
}
