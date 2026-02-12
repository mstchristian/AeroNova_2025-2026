#include <Arduino.h>
#include <Wire.h>
#include <SPI.h>
#include <Adafruit_BME280.h>
#include <SoftwareSerial.h>
#include <TinyGPS.h>
#include <MPU6050.h>

Adafruit_BME280 bme;
TinyGPS gps;
SoftwareSerial gpsSerial(4, 3);
MPU6050 mpu;

float temperature, humidity, pressure;

bool gpsData = false;
float latitude = 0.0, longitude = 0.0;
int satellites = 0;

int ax, ay, az;
int gx, gy, gz;

const float accScale = 2.0 * 9.81 / 32768.0;
const float gyroScale = 250.0 / 32768.0;

unsigned long lastPrint = 0;
const unsigned long printInterval = 200;

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
    Serial.println(gz * gyroScale);
}

void setup() {
    Serial.begin(9600);
    gpsSerial.begin(9600);
    Wire.begin();

    if (!bme.begin(0x77)) {
        Serial.println("No se ha encontrado el BME280");
        while (1);
    }

    mpu.initialize();
    if (!mpu.testConnection()) {
        Serial.println("Error al conectar MPU6050");
        while (1);
    }

    Serial.println("Temp\tHum\tPres\tGPS\tLat\tLon\tSat\tax\tay\taz\tgx\tgy\tgz");
}

void loop() {
    temperature = bme.readTemperature();
    humidity = bme.readHumidity();
    pressure = bme.readPressure() / 100.0F;

    while (gpsSerial.available()) {
        char c = gpsSerial.read();
        if (gps.encode(c)) {
            gpsData = true;
        }
    }

    if (gpsData) {
        unsigned long age;
        gps.f_get_position(&latitude, &longitude, &age);

        if (latitude == TinyGPS::GPS_INVALID_F_ANGLE) latitude = 0.0;
        if (longitude == TinyGPS::GPS_INVALID_F_ANGLE) longitude = 0.0;

        satellites = gps.satellites();
        if (satellites == TinyGPS::GPS_INVALID_SATELLITES) satellites = 0;
    }

    mpu.getAcceleration(&ax, &ay, &az);
    mpu.getRotation(&gx, &gy, &gz);

    if (millis() - lastPrint >= printInterval) {
        printData();
        lastPrint = millis();
    }
}
