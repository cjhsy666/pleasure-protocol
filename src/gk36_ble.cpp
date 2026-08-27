#include "gk36_ble.h"

GK36BLE::GK36BLE() {
    memcpy(_lastShockPacket, SHOCK_PACKETS[0], PACKET_SIZE);
    memcpy(_lastVibrationPacket, VIBRATION_IDLE_PACKET, PACKET_SIZE);
}

GK36BLE::~GK36BLE() {
    stopHeartbeat();
    disconnect();
}

void GK36BLE::_setState(BLEState state) {
    _state = state;
    if (_callback) _callback->onStateChange(state);
}

bool GK36BLE::startScan(uint32_t durationSec) {
    _setState(BLE_SCANNING);

    NimBLEDevice::init("");
    _scan = NimBLEDevice::getScan();

    _scan->setAdvertisedDeviceCallbacks(new NimBLEAdvertisedDeviceCallbacks(), false);
    _scan->setInterval(100);
    _scan->setWindow(99);
    _scan->setActiveScan(true);

    Serial.printf("[BLE] 扫描中 (%u秒)...\n", durationSec);
    _scan->start(durationSec, false);
    _scan->stop();

    Serial.printf("[BLE] 扫描完成, 发现 %d 个设备\n",
                  _scan->getResults().getCount());
    return true;
}

void GK36BLE::stopScan() {
    if (_scan && _scan->isScanning()) {
        _scan->stop();
    }
}

int GK36BLE::getScanResults(String* names, String* addresses, int maxResults) {
    int count = 0;
    NimBLEScanResults results = _scan->getResults();

    for (int i = 0; i < results.getCount() && count < maxResults; i++) {
        NimBLEAdvertisedDevice dev = results.getDevice(i);
        String name = dev.getName().c_str();
        String addr = dev.getAddress().toString().c_str();

        if (name.indexOf(GK36_DEVICE_NAME) >= 0 || name.length() > 0) {
            names[count] = name;
            addresses[count] = addr;
            count++;
        }
    }
    return count;
}

bool GK36BLE::connect(int deviceIndex) {
    NimBLEScanResults results = _scan->getResults();
    if (deviceIndex < 0) {
        for (int i = 0; i < results.getCount(); i++) {
            NimBLEAdvertisedDevice dev = results.getDevice(i);
            String name = dev.getName().c_str();
            if (name.indexOf(GK36_DEVICE_NAME) >= 0) {
                deviceIndex = i;
                break;
            }
        }
        if (deviceIndex < 0 && results.getCount() > 0) {
            deviceIndex = 0;
        }
    }

    if (deviceIndex < 0 || deviceIndex >= results.getCount()) {
        Serial.println("[BLE] 无可连接设备");
        _setState(BLE_ERROR);
        return false;
    }

    NimBLEAdvertisedDevice dev = results.getDevice(deviceIndex);
    _deviceAddress = dev.getAddress().toString().c_str();
    _deviceName = dev.getName().c_str();

    Serial.printf("[BLE] 正在连接 %s (%s)...\n",
                  _deviceName.c_str(), _deviceAddress.c_str());

    return connectToAddress(_deviceAddress);
}

bool GK36BLE::connectToAddress(const String& address) {
    _setState(BLE_CONNECTING);

    _client = NimBLEDevice::createClient();
    _client->setConnectTimeout(10);
    _client->setMTU(512);

    if (!_client->connect(address.c_str())) {
        Serial.println("[BLE] 连接失败");
        _setState(BLE_ERROR);
        return false;
    }

    Serial.printf("[BLE] 已连接, MTU=%d\n", _client->getMTU());

    if (!_discoverCharacteristics()) {
        Serial.println("[BLE] 特征发现失败");
        _client->disconnect();
        _setState(BLE_ERROR);
        return false;
    }

    _setState(BLE_CONNECTED);
    if (_callback) _callback->onConnected();
    return true;
}

bool GK36BLE::_discoverCharacteristics() {
    NimBLERemoteService* service = nullptr;

    auto services = _client->getServices(true);
    for (auto* svc : services) {
        auto chars = svc->getCharacteristics(true);
        for (auto* ch : chars) {
            if (ch->canWrite() && !service) {
                service = svc;
                _writeChar = ch;
                Serial.printf("[BLE] 写入特征: %s\n", ch->getUUID().toString().c_str());
            }
            if (ch->canNotify() && !_notifyChar) {
                _notifyChar = ch;
                Serial.printf("[BLE] 通知特征: %s\n", ch->getUUID().toString().c_str());
            }
        }
    }

    if (!_writeChar) {
        Serial.println("[BLE] 未找到可写特征");
        return false;
    }

    if (_notifyChar) {
        _notifyChar->subscribe(true, [this](NimBLERemoteCharacteristic* pChar,
                                            uint8_t* pData, size_t len, bool isNotify) {
            if (_callback) _callback->onNotify(pData, len);
        });
    }

    return true;
}

void GK36BLE::disconnect() {
    stopHeartbeat();

    if (_client && _client->isConnected()) {
        _client->disconnect();
    }

    _writeChar = nullptr;
    _notifyChar = nullptr;
    _deviceAddress = "";
    _deviceName = "";

    _setState(BLE_DISCONNECTED);
    if (_callback) _callback->onDisconnected();

    Serial.println("[BLE] 已断开");
}

bool GK36BLE::isConnected() {
    return _client && _client->isConnected();
}

bool GK36BLE::_sendPacket(const uint8_t* packet, size_t len) {
    if (!isConnected() || !_writeChar) {
        Serial.println("[BLE] 未连接");
        return false;
    }
    return _writeChar->writeValue(packet, len, false);
}

bool GK36BLE::sendShockOff() {
    memcpy(_lastShockPacket, SHOCK_PACKETS[0], PACKET_SIZE);
    return _sendPacket(_lastShockPacket, PACKET_SIZE);
}

bool GK36BLE::sendShockLevel(uint8_t level) {
    if (level > 7) level = 7;
    memcpy(_lastShockPacket, SHOCK_PACKETS[level], PACKET_SIZE);
    return _sendPacket(_lastShockPacket, PACKET_SIZE);
}

bool GK36BLE::sendVibrationOff() {
    memcpy(_lastVibrationPacket, VIBRATION_IDLE_PACKET, PACKET_SIZE);
    return _sendPacket(_lastVibrationPacket, PACKET_SIZE);
}

bool GK36BLE::sendVibrationLevel(int percent) {
    if (percent <= 0) return sendVibrationOff();

    uint8_t b6 = vibrationPositionToB6(percent);
    const uint8_t* pkt = vibrationGetPacket(b6);
    if (!pkt) {
        Serial.printf("[BLE] 无对应数据包: b6=0x%02X\n", b6);
        return false;
    }
    memcpy(_lastVibrationPacket, pkt, PACKET_SIZE);
    return _sendPacket(_lastVibrationPacket, PACKET_SIZE);
}

bool GK36BLE::sendVibrationRaw(uint8_t b6) {
    const uint8_t* pkt = vibrationGetPacket(b6);
    if (!pkt) {
        Serial.printf("[BLE] 无对应数据包: b6=0x%02X\n", b6);
        return false;
    }
    memcpy(_lastVibrationPacket, pkt, PACKET_SIZE);
    return _sendPacket(_lastVibrationPacket, PACKET_SIZE);
}

bool GK36BLE::sendLightToggle() {
    _lightState = !_lightState;
    const uint8_t* pkt = _lightState ? LIGHT_STATE_B : LIGHT_STATE_A;
    return _sendPacket(pkt, PACKET_SIZE);
}

bool GK36BLE::sendRawPacket(const uint8_t* packet, size_t len) {
    return _sendPacket(packet, len);
}

void GK36BLE::_heartbeatTaskFunc(void* param) {
    GK36BLE* ble = (GK36BLE*)param;

    while (true) {
        if (ble->isConnected()) {
            ble->_sendPacket(ble->_lastShockPacket, PACKET_SIZE);
            vTaskDelay(pdMS_TO_TICKS(ble->_heartbeatIntervalMs / 2));
            ble->_sendPacket(ble->_lastVibrationPacket, PACKET_SIZE);
            vTaskDelay(pdMS_TO_TICKS(ble->_heartbeatIntervalMs / 2));
        } else {
            vTaskDelay(pdMS_TO_TICKS(1000));
        }
    }
}

void GK36BLE::startHeartbeat(uint32_t intervalMs) {
    if (_heartbeatTask) return;

    _heartbeatIntervalMs = intervalMs;
    xTaskCreatePinnedToCore(
        _heartbeatTaskFunc,
        "heartbeat",
        4096,
        this,
        1,
        &_heartbeatTask,
        1
    );

    Serial.printf("[BLE] 心跳已启动 (间隔 %u ms)\n", intervalMs);
}

void GK36BLE::stopHeartbeat() {
    if (_heartbeatTask) {
        vTaskDelete(_heartbeatTask);
        _heartbeatTask = nullptr;
        Serial.println("[BLE] 心跳已停止");
    }
}
