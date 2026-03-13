#include <Arduino.h>
#include <Wire.h>
#include <SPI.h>
#include <Adafruit_BME280.h>
#include <SoftwareSerial.h>
#include <TinyGPS.h>
#include <MPU6050.h>
#include <Adafruit_LTR390.h>
#include "Adafruit_SGP30.h"

Adafruit_BME280 bme;
TinyGPS gps;
SoftwareSerial gpsSerial(4, 3);
MPU6050 mpu;
Adafruit_LTR390 ltr = Adafruit_LTR390();
Adafruit_SGP30 sgp;

float temperature, humidity, pressure;
bool gpsData = false;
float latitude = 0.0, longitude = 0.0;
int satellites = 0;

int ax, ay, az, gx, gy, gz;

uint32_t uvRaw = 0;
uint16_t TVOC = 0;
uint16_t eCO2 = 0;

const float accScale = 2.0 * 9.81 / 32768.0;
const float gyroScale = 250.0 / 32768.0;

unsigned long lastPrint = 0;
const unsigned long printInterval = 200;

int counter = 0;

uint32_t getAbsoluteHumidity(float temperature, float humidity) {
    const float absoluteHumidity =
        216.7f * ((humidity / 100.0f) * 6.112f *
        exp((17.62f * temperature) / (243.12f + temperature)) /
        (273.15f + temperature));

    return (uint32_t)(1000.0f * absoluteHumidity);
}

void printData() {
    Serial.print(temperature); Serial.print("\t");
    Serial.print(humidity); Serial.print("\t");
    Serial.print(pressure); Serial.print("\t");

    Serial.print(gpsData ? "1" : "0"); Serial.print("\t");
    Serial.print(latitude, 6); Serial.print("\t");
    Serial.print(longitude, 6); Serial.print("\t");
    Serial.print(satellites); Serial.print("\t");

    Serial.print(ax * accScale); Serial.print("\t");
    Serial.print(ay * accScale); Serial.print("\t");
    Serial.print(az * accScale); Serial.print("\t");

    Serial.print(gx * gyroScale); Serial.print("\t");
    Serial.print(gy * gyroScale); Serial.print("\t");
    Serial.print(gz * gyroScale); Serial.print("\t");

    Serial.print(uvRaw); Serial.print("\t");

    Serial.print(TVOC); Serial.print("\t");
    Serial.println(eCO2);
}

void setup() {
    Serial.begin(9600);
    gpsSerial.begin(9600);
    Wire.begin();

    if (!bme.begin()) {
        Serial.println("Error: BME280 no detectado");
        while (1);
    }

    mpu.initialize();
    if (!mpu.testConnection()) {
        Serial.println("Error: MPU6050 no detectado");
        while (1);
    }

    if (!ltr.begin()) {
        Serial.println("Error: LTR390 no detectado");
        while (1);
    }

    ltr.setMode(LTR390_MODE_UVS);
    ltr.setGain(LTR390_GAIN_3);
    ltr.setResolution(LTR390_RESOLUTION_16BIT);

    if (!sgp.begin()) {
        Serial.println("Error: SGP30 no detectado");
        while (1);
    }

    Serial.println("Temp\tHum\tPres\tGPS\tLat\tLon\tSat\tax\tay\taz\tgx\tgy\tgz\tUV\tTVOC\teCO2");
}

void loop() {
    while (gpsSerial.available()) {
        char c = gpsSerial.read();
        if (gps.encode(c)) {
            gpsData = true;
        }
    }

    if (millis() - lastPrint >= printInterval) {

        lastPrint = millis();

        temperature = bme.readTemperature();
        humidity = bme.readHumidity();
        pressure = bme.readPressure() / 100.0F;

        mpu.getAcceleration(&ax, &ay, &az);
        mpu.getRotation(&gx, &gy, &gz);

        if (ltr.newDataAvailable()) {
            uvRaw = ltr.readUVS();
        }

        if (sgp.IAQmeasure()) {
            sgp.setHumidity(getAbsoluteHumidity(temperature, humidity));
            TVOC = sgp.TVOC;
            eCO2 = sgp.eCO2;
        }

        if (gpsData) {
            unsigned long age;
            gps.f_get_position(&latitude, &longitude, &age);
            satellites = gps.satellites();

            if (latitude == TinyGPS::GPS_INVALID_F_ANGLE) latitude = 0.0;
            if (longitude == TinyGPS::GPS_INVALID_F_ANGLE) longitude = 0.0;
            if (satellites == TinyGPS::GPS_INVALID_SATELLITES) satellites = 0;

            if (age > 2000) gpsData = false;
        }

        printData();

        counter++;
        if (counter == 30) {
            counter = 0;
            uint16_t TVOC_base, eCO2_base;
            sgp.getIAQBaseline(&eCO2_base, &TVOC_base);
        }
    }
}