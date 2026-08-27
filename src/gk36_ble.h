#ifndef GK36_BLE_H
#define GK36_BLE_H

#include <Arduino.h>
#include <NimBLEDevice.h>
#include "gk36_protocol.h"

#define GK36_DEVICE_NAME "GK36"

enum BLEState {
    BLE_IDLE,
    BLE_SCANNING,
    BLE_CONNECTING,
    BLE_CONNECTED,
    BLE_DISCONNECTED,
    BLE_ERROR
};

class GK36BLECallback {
public:
    virtual ~GK36BLECallback() {}
    virtual void onConnected() {}
    virtual void onDisconnected() {}
    virtual void onNotify(const uint8_t* data, size_t len) {}
    virtual void onStateChange(BLEState state) {}
};

class GK36BLE {
public:
    GK36BLE();
    ~GK36BLE();

    void setCallback(GK36BLECallback* cb) { _callback = cb; }

    bool startScan(uint32_t durationSec = 10);
    void stopScan();
    int getScanResults(String* names, String* addresses, int maxResults);

    bool connect(int deviceIndex = -1);
    bool connectToAddress(const String& address);
    void disconnect();
    bool isConnected();

    bool sendShockOff();
    bool sendShockLevel(uint8_t level);
    bool sendVibrationOff();
    bool sendVibrationLevel(int percent);
    bool sendVibrationRaw(uint8_t b6);
    bool sendLightToggle();
    bool sendRawPacket(const uint8_t* packet, size_t len);

    void startHeartbeat(uint32_t intervalMs = 5000);
    void stopHeartbeat();
    bool isHeartbeatRunning() { return _heartbeatTask != nullptr; }

    BLEState getState() { return _state; }
    String getDeviceAddress() { return _deviceAddress; }
    String getDeviceName() { return _deviceName; }
    const uint8_t* getLastShockPacket() { return _lastShockPacket; }
    const uint8_t* getLastVibrationPacket() { return _lastVibrationPacket; }

private:
    NimBLEClient* _client = nullptr;
    NimBLERemoteCharacteristic* _writeChar = nullptr;
    NimBLERemoteCharacteristic* _notifyChar = nullptr;
    NimBLEScan* _scan = nullptr;

    BLEState _state = BLE_IDLE;
    String _deviceAddress;
    String _deviceName;
    GK36BLECallback* _callback = nullptr;

    uint8_t _lastShockPacket[PACKET_SIZE];
    uint8_t _lastVibrationPacket[PACKET_SIZE];
    bool _lightState = false;

    TaskHandle_t _heartbeatTask = nullptr;
    uint32_t _heartbeatIntervalMs = 5000;

    bool _sendPacket(const uint8_t* packet, size_t len);
    void _setState(BLEState state);
    bool _discoverCharacteristics();
    static void _heartbeatTaskFunc(void* param);
};

#endif // GK36_BLE_H
