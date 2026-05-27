#include <ESP8266WiFi.h>
#include <ESP8266HTTPClient.h>
#include <WiFiClient.h>
#include <ArduinoJson.h>
#include <MD_Parola.h>
#include <MD_MAX72xx.h>
#include <SPI.h>

// ================= DISPLAY SETTINGS =================
#define HARDWARE_TYPE MD_MAX72XX::FC16_HW
#define MAX_DEVICES 4

#define DATA_PIN D7
#define CS_PIN   D8
#define CLK_PIN  D4

MD_Parola display = MD_Parola(HARDWARE_TYPE, DATA_PIN, CLK_PIN, CS_PIN, MAX_DEVICES);

// ================= SENSOR & BUZZER =================
#define SENSOR_PIN D5
#define BUZZER_PIN D6

// ================= WIFI =================
const char* ssid = "GANESH";
const char* password = "ganesh1234";
const char* serverURL = "http://10.144.71.76:8000/alert";

// ================= STATE VARIABLES =================
bool objectDetected = false;
bool showingMessage = false;
unsigned long messageStartTime = 0;

void setup() {

  pinMode(SENSOR_PIN, INPUT);
  pinMode(BUZZER_PIN, OUTPUT);
  digitalWrite(BUZZER_PIN, LOW);

  Serial.begin(115200);

  // Initialize Display
  display.begin();
  display.setIntensity(5);
  display.displayClear();

  // Static SAFE AREA
  display.displayText("SAFE AREA", PA_CENTER, 0, 0, PA_PRINT, PA_NO_EFFECT);

  // Connect WiFi
  WiFi.begin(ssid, password);
  Serial.print("Connecting");

  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }

  Serial.println("\nWiFi Connected");
  Serial.println(WiFi.localIP());
}

void loop() {

  display.displayAnimate();

  int sensorValue = digitalRead(SENSOR_PIN);

  // 🔴 Object Detected
  if (sensorValue == LOW && !objectDetected && !showingMessage) {

    objectDetected = true;
    showingMessage = true;

    Serial.println("Object Detected");

    display.displayClear();
    display.displayText("CHECKING...", PA_CENTER, 25, 1000, PA_SCROLL_LEFT, PA_NO_EFFECT);

    if (WiFi.status() == WL_CONNECTED) {

      WiFiClient client;
      HTTPClient http;

      http.begin(client, serverURL);
      http.addHeader("Content-Type", "application/json");

      String jsonData = "{\"zone\":\"Lab-Entrance\"}";
      int httpCode = http.POST(jsonData);

      Serial.print("HTTP Code: ");
      Serial.println(httpCode);

      if (httpCode == 200) {

        String payload = http.getString();
        Serial.println(payload);

        DynamicJsonDocument doc(512);
        deserializeJson(doc, payload);

        String status = doc["status"];
        String name = doc["name"];

        display.displayClear();

        // ================= INTRUDER =================
        if (status == "INTRUDER") {

          Serial.println("INTRUDER ALERT");
          digitalWrite(BUZZER_PIN, HIGH);

          display.displayText("INTRUDER ALERT", PA_CENTER, 30, 0, PA_SCROLL_LEFT, PA_SCROLL_LEFT);
        }

        // ================= SAFE =================
        else if (status == "SAFE") {

          digitalWrite(BUZZER_PIN, LOW);

          String finalMessage = "SAFE";

          if (name.length() > 0) {
            finalMessage += " " + name;
          }

          Serial.println(finalMessage);

          display.displayText(finalMessage.c_str(), PA_CENTER, 0, 0, PA_PRINT, PA_NO_EFFECT);
        }

        // ================= NO FACE =================
        else {

          digitalWrite(BUZZER_PIN, LOW);
          display.displayText("NO FACE", PA_CENTER, 0, 0, PA_PRINT, PA_NO_EFFECT);
        }

        messageStartTime = millis();
      }

      http.end();
    }
  }

  // 🔥 Return to SAFE AREA after 5 seconds
  if (showingMessage && millis() - messageStartTime > 5000) {

    digitalWrite(BUZZER_PIN, LOW);

    display.displayClear();
    display.displayText("SAFE AREA", PA_CENTER, 0, 0, PA_PRINT, PA_NO_EFFECT);

    showingMessage = false;
    objectDetected = false;
  }
}
