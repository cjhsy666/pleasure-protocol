/**
 * pleasure-protocol: ESP32 BLE bridge for GK36 devices
 *
 * Features:
 *   - BLE Central role: scan, connect, control GK36 device
 *   - Web UI: real-time control via WebSocket
 *   - WiFi AP mode (default) or STA mode
 *   - Heartbeat: keeps BLE connection alive
 *   - OTA firmware update
 *
 * Hardware: ESP32 (any dev board)
 * Framework: Arduino + NimBLE-Arduino
 */

#include <Arduino.h>
#include "gk36_protocol.h"
#include "gk36_ble.h"
#include "gk36_web.h"
#include "index_html.h"

// ---- Configuration ----
// Change these for your setup
#define WIFI_AP_SSID     "pleasure-protocol"
#define WIFI_AP_PASS     "12345678"
// #define WIFI_STA_SSID  "YourWiFi"
// #define WIFI_STA_PASS  "YourPassword"

// If you know the GK36 MAC address, set it here for auto-connect
// Leave empty for manual scan+connect
#define GK36_AUTO_ADDRESS ""

// ---- Global Objects ----
GK36BLE ble;
GK36Web web(&ble);

// Status tracking
unsigned long lastStatusBroadcast = 0;
#define STATUS_INTERVAL 2000  // broadcast status every 2s

// ---- BLE Callback ----
class WebCallback : public GK36BLECallback {
public:
    void onConnected() override {
        Serial.println("[MAIN] BLE device connected");
        web.broadcastStatus();
    }

    void onDisconnected() override {
        Serial.println("[MAIN] BLE device disconnected");
        web.broadcastStatus();
    }

    void onNotify(const uint8_t* data, size_t len) override {
        Serial.print("[MAIN] BLE notify: ");
        for (size_t i = 0; i < len; i++) {
            Serial.printf("%02x ", data[i]);
        }
        Serial.println();
    }

    void onStateChange(BLEState state) override {
        const char* stateNames[] = {"IDLE", "SCANNING", "CONNECTING", "CONNECTED", "DISCONNECTED", "ERROR"};
        Serial.printf("[MAIN] BLE state: %s\n", stateNames[state]);
    }
};

WebCallback bleCallback;

// ---- Setup ----
void setup() {
    Serial.begin(115200);
    delay(1000);

    Serial.println();
    Serial.println("========================================");
    Serial.println("  pleasure-protocol");
    Serial.println("  为 AI 控制铺路");
    Serial.println("========================================");
    Serial.printf("  Firmware: %s %s\n", __DATE__, __TIME__);
    Serial.println("========================================");

    // Initialize BLE
    ble.setCallback(&bleCallback);
    Serial.println("[MAIN] BLE initialized");

    // Start WiFi + Web Server
#ifdef WIFI_STA_SSID
    Serial.printf("[MAIN] Connecting to WiFi: %s\n", WIFI_STA_SSID);
    if (!web.beginSTA(WIFI_STA_SSID, WIFI_STA_PASS)) {
        Serial.println("[MAIN] STA failed, falling back to AP mode");
        web.beginAP(WIFI_AP_SSID, WIFI_AP_PASS);
    }
#else
    Serial.printf("[MAIN] Starting AP: %s\n", WIFI_AP_SSID);
    web.beginAP(WIFI_AP_SSID, WIFI_AP_PASS);
#endif

    Serial.println();
    Serial.printf("[MAIN] Web UI: http://%s\n", web.getIPAddress().c_str());
    Serial.printf("[MAIN] API:    http://%s/api\n", web.getIPAddress().c_str());
    Serial.printf("[MAIN] OTA:    http://%s/ota\n", web.getIPAddress().c_str());
    Serial.println();

    // Auto-connect if address is configured
#ifdef GK36_AUTO_ADDRESS
    if (strlen(GK36_AUTO_ADDRESS) > 0) {
        Serial.printf("[MAIN] Auto-connecting to %s...\n", GK36_AUTO_ADDRESS);
        ble.startScan(5);
        if (ble.connectToAddress(GK36_AUTO_ADDRESS)) {
            Serial.println("[MAIN] Auto-connected! Starting heartbeat...");
            ble.startHeartbeat(5000);
        } else {
            Serial.println("[MAIN] Auto-connect failed");
        }
    }
#endif
}

// ---- Main Loop ----
void loop() {
    // Handle web server and WebSocket
    web.handleClient();
    web.handleWebSocket();

    // Broadcast BLE status periodically
    unsigned long now = millis();
    if (now - lastStatusBroadcast > STATUS_INTERVAL) {
        web.broadcastStatus();
        lastStatusBroadcast = now;
    }

    // Small yield to FreeRTOS
    yield();
}
