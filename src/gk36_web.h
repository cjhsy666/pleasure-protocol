#ifndef GK36_WEB_H
#define GK36_WEB_H

#include <Arduino.h>
#include <WiFi.h>
#include <WebServer.h>
#include <WebSocketsServer.h>
#include <ArduinoJson.h>
#include <ESPmDNS.h>
#include <Update.h>
#include "gk36_ble.h"

#define DEFAULT_AP_SSID "pleasure-protocol"
#define DEFAULT_AP_PASS "12345678"
#define WEB_PORT 80
#define WS_PORT 81

class GK36Web {
public:
    GK36Web(GK36BLE* ble);
    ~GK36Web();

    bool beginAP(const char* ssid = DEFAULT_AP_SSID, const char* pass = DEFAULT_AP_PASS);
    bool beginSTA(const char* ssid, const char* pass);
    void stop();

    void handleClient();
    void handleWebSocket();
    void broadcastStatus();

    bool isAPMode() { return _apMode; }
    String getIPAddress();

private:
    GK36BLE* _ble;
    WebServer* _server = nullptr;
    WebSocketsServer* _ws = nullptr;
    bool _apMode = true;
    int _wsClientCount = 0;

    void _handleRoot();
    void _handleAPI();
    void _handleOTA();
    void _handleOTAUpdate();
    void _webSocketEvent(uint8_t num, WStype_t type, uint8_t* payload, size_t length);
    void _processCommand(const String& cmd, JsonDocument& doc);
};

#endif // GK36_WEB_H
