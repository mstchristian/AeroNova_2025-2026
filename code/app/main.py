import customtkinter as ctk
import serial
import serial.tools.list_ports
import threading
import csv
from datetime import datetime
import tkintermapview
import random
import time
import math

# ---------------- Configuración general ---------------- #
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")

# ---------------- Clase Mapa ---------------- #
class MapFrame(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, corner_radius=15)
        self.map_widget = tkintermapview.TkinterMapView(self, width=700, height=700, corner_radius=15)
        self.map_widget.pack(fill="both", expand=True)
        self.map_widget.set_position(0, 0)
        self.map_widget.set_zoom(2)
        self.marker = self.map_widget.set_marker(0, 0, text="CanSat")

    def update_position(self, lat, lon):
        try:
            self.marker.set_position(lat, lon)
        except:
            pass

# ---------------- Clase Principal ---------------- #
class GroundStationUI(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("AeroNova Mission Control")
        self.geometry("1400x800")
        self.serial_connection = None
        self.reading = False
        self.logging = False
        self.csv_file = None
        self.csv_writer = None
        self.sensor_labels = {}
        self.simulation_mode = False
        self.packet_counter = 2000  # Starting packet number
        self.simulation_time = 0  # Time in seconds since start
        self.phase = 'ascent'  # 'ascent', 'coast', 'descent'
        self.altitude = 700  # Starting altitude in meters
        self.velocity = 0  # Vertical velocity m/s
        self.lat = 40.5021
        self.lon = -3.99317
        self.g = 9.81  # Gravity m/s²
        self.terminal_velocity = 8  # m/s

        self.create_ui()
        self.update_ports()

    # ---------------- Clasificación ---------------- #
    def classify_values(self, uv, co2):
        # UV
        try:
            uv = float(uv)
            if uv < 10:
                uv_status = "UV muy bajo"
            elif uv < 50:
                uv_status = "UV bajo"
            elif uv < 150:
                uv_status = "UV medio"
            elif uv < 300:
                uv_status = "UV alto"
            else:
                uv_status = "UV muy alto"
        except:
            uv_status = "N/A"

        # CO2
        try:
            co2 = float(co2)
            if co2 < 600:
                co2_status = "Aire muy limpio"
            elif co2 < 800:
                co2_status = "Aire bueno"
            elif co2 < 1200:
                co2_status = "Aire aceptable"
            elif co2 < 2000:
                co2_status = "Aire cargado"
            else:
                co2_status = "Aire malo"
        except:
            co2_status = "N/A"

        return uv_status, co2_status

    # ---------------- UI ---------------- #
    def create_ui(self):
        top_frame = ctk.CTkFrame(self, corner_radius=15)
        top_frame.pack(fill="x", padx=10, pady=10)

        self.port_selector = ctk.CTkComboBox(top_frame)
        self.port_selector.grid(row=0, column=0, padx=5, pady=5)

        ctk.CTkButton(top_frame, text="Actualizar Puertos", command=self.update_ports).grid(row=0, column=1, padx=5)
        ctk.CTkButton(top_frame, text="Conectar", fg_color="#4caf50", command=self.connect_serial).grid(row=0, column=2, padx=5)
        ctk.CTkButton(top_frame, text="Desconectar", fg_color="#f44336", command=self.disconnect_serial).grid(row=0, column=3, padx=5)

        self.toggle_logging = ctk.CTkButton(top_frame, text="Grabar Datos", fg_color="#2196f3", command=self.toggle_logging_fn)
        self.toggle_logging.grid(row=0, column=4, padx=5)

        self.simulation_checkbox = ctk.CTkCheckBox(top_frame, text="Modo Simulación", command=self.toggle_simulation)
        self.simulation_checkbox.grid(row=0, column=5, padx=5)

        self.lbl_status = ctk.CTkLabel(top_frame, text="Estado: Desconectado", font=("Roboto",14), text_color="#ff5555")
        self.lbl_status.grid(row=1, column=0, columnspan=6, pady=5)

        main_frame = ctk.CTkFrame(self, corner_radius=15)
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)
        main_frame.grid_columnconfigure(0, weight=3)
        main_frame.grid_columnconfigure(1, weight=2)

        self.map_frame = MapFrame(main_frame)
        self.map_frame.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")

        values_container = ctk.CTkScrollableFrame(main_frame, corner_radius=15)
        values_container.grid(row=0, column=1, padx=10, pady=10, sticky="nsew")
        values_container.grid_columnconfigure((0,1), weight=1)

        self.sensor_groups = {
            "Mediciones ambientales": ["Temp (°C)", "Hum (%)", "Pres (hPa)", "Alt (m)"],
            "GPS": ["Lat (°)", "Lon (°)", "Sat (#)", "GPS (bool)"],
            "Aceleración (m/s²)": ["ax (m/s²)", "ay (m/s²)", "az (m/s²)"],
            "Giroscopio (°/s)": ["gx (°/s)", "gy (°/s)", "gz (°/s)"],
            "Otros sensores": ["UV", "TVOC (ppb)", "eCO2 (ppm)"]
        }

        row = 0
        col = 0
        max_cols = 2

        for group, sensors in self.sensor_groups.items():
            lbl_group = ctk.CTkLabel(values_container, text=group, font=("Roboto",14,"bold"))
            lbl_group.grid(row=row, column=0, columnspan=max_cols, pady=(10,2), sticky="w")
            row +=1

            for sensor in sensors:
                card = ctk.CTkFrame(values_container, corner_radius=10, fg_color="#2b2b2b")
                card.grid(row=row, column=col, padx=5, pady=5, sticky="nsew")

                card.grid_columnconfigure(1, weight=1)

                lbl_name = ctk.CTkLabel(card, text=f"{sensor}:", font=("Roboto",12))
                lbl_name.grid(row=0, column=0, padx=5, pady=5, sticky="w")

                lbl_value = ctk.CTkLabel(card, text="-", font=("Roboto",12,"bold"), text_color="#00ffcc")
                lbl_value.grid(row=0, column=1, padx=5, pady=5, sticky="e")

                self.sensor_labels[sensor] = lbl_value

                col +=1
                if col >= max_cols:
                    col = 0
                    row +=1

            if col !=0:
                col=0
                row +=1

    # ---------------- Serial y CSV ---------------- #
    def update_ports(self):
        ports = serial.tools.list_ports.comports()
        port_list = [port.device for port in ports]
        self.port_selector.configure(values=port_list)
        if port_list:
            self.port_selector.set(port_list[0])

    def connect_serial(self):
        if self.simulation_mode:
            # Reset simulation parameters
            self.simulation_time = 0
            self.phase = 'ascent'
            self.altitude = 700
            self.velocity = 0
            self.lat = 40.5021
            self.lon = -3.99317
            self.reading = True
            self.lbl_status.configure(text="Simulación Iniciada", text_color="#4cff4c")
            threading.Thread(target=self.read_data, daemon=True).start()
            return

        port = self.port_selector.get()
        if not port:
            self.lbl_status.configure(text="Selecciona un puerto", text_color="#ffbb33")
            return

        try:
            self.serial_connection = serial.Serial(port, 9600, timeout=1)
            self.reading = True
            self.lbl_status.configure(text=f"Conectado a {port}", text_color="#4cff4c")
            threading.Thread(target=self.read_data, daemon=True).start()
        except Exception as e:
            self.lbl_status.configure(text=f"Error: {e}", text_color="#ff5555")

    def disconnect_serial(self):
        self.reading = False
        self.logging = False

        if not self.simulation_mode and self.serial_connection:
            try:
                self.serial_connection.close()
            except:
                pass

        status_text = "Simulación Detenida" if self.simulation_mode else "Estado: Desconectado"
        self.lbl_status.configure(text=status_text, text_color="#ff5555")
        self.toggle_logging.configure(text="Grabar Datos", fg_color="#2196f3")

    def toggle_simulation(self):
        self.simulation_mode = self.simulation_checkbox.get()
        if self.simulation_mode:
            self.lbl_status.configure(text="Modo Simulación Activado", text_color="#ffa500")
        else:
            self.lbl_status.configure(text="Modo Simulación Desactivado", text_color="#ff5555")

    def toggle_logging_fn(self):
        if not self.logging:
            now = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            filename = f"aeronova_{now}.csv"

            self.csv_file = open(filename, mode='w', newline='')
            self.csv_writer = csv.writer(self.csv_file)

            header = ["Team","Packet","Temp (°C)","Hum (%)","Pres (hPa)","Alt (m)",
                      "Lat (°)","Lon (°)","Sat (#)","ax (m/s²)","ay (m/s²)","az (m/s²)",
                      "gx (°/s)","gy (°/s)","gz (°/s)","UV (raw)","TVOC (ppb)","eCO2 (ppm)",
                      "GPS (bool)", "UV_status", "CO2_status"]

            self.csv_writer.writerow(header)

            self.logging = True
            self.toggle_logging.configure(text="Detener Grabación", fg_color="#f44336")
            self.lbl_status.configure(text=f"Grabando en {filename}", text_color="#4cff4c")

        else:
            self.logging = False

            if self.csv_file:
                self.csv_file.close()
                self.csv_file = None
                self.csv_writer = None

            self.toggle_logging.configure(text="Grabar Datos", fg_color="#2196f3")
            self.lbl_status.configure(text="Grabación detenida", text_color="#ffaa33")

    def generate_simulated_data(self):
        self.packet_counter += 1
        self.simulation_time += 1

        # Simular fases del vuelo: cohete asciende a 1km, suelta CanSat en apogeo
        if self.altitude < 1700:  # Ascenso del cohete hasta 1km (desde 700m base)
            self.phase = 'ascent'
            acceleration = 20.0  # m/s² hacia arriba (motor del cohete)
        elif self.velocity > 0:  # Coast: motor apagado, gravedad
            self.phase = 'coast'
            acceleration = -self.g  # Solo gravedad
        else:  # Apogeo alcanzado, CanSat suelto, descenso con paracaídas
            self.phase = 'descent'
            acceleration = -5.0  # m/s² hacia abajo (paracaídas)

        # Actualizar velocidad con límite de velocidad terminal en descenso
        self.velocity += acceleration * 1  # dt = 1s
        if self.phase == 'descent':
            self.velocity = max(self.velocity, -self.terminal_velocity)

        # Actualizar altitud
        self.altitude += self.velocity * 1 + 0.5 * acceleration * 1**2

        # Evitar altitud negativa
        if self.altitude < 0:
            self.altitude = 0
            self.velocity = 0

        # Calcular presión (fórmula barométrica simplificada)
        p0 = 1013.25  # hPa at sea level
        if self.altitude > 0:
            self.pressure = p0 * math.exp(-self.altitude / 8000)
        else:
            self.pressure = p0

        # Temperatura (gradiente adiabático -6.5°C/km, con ruido)
        t0 = 20  # °C at ground
        lapse_rate = -6.5 / 1000  # °C/m
        self.temperature = t0 + lapse_rate * self.altitude + random.gauss(0, 1)

        # Humedad relativa (disminuye con altitud, con ruido)
        base_humidity = 80
        humidity_decay = 0.02  # por metro
        self.humidity = max(10, base_humidity * math.exp(-humidity_decay * self.altitude) + random.gauss(0, 5))

        # GPS: simular movimiento horizontal con viento (más realista)
        wind_speed_ns = 3  # m/s norte-sur
        wind_speed_ew = 1  # m/s este-oeste
        lat_change = wind_speed_ns * 1 / 111000  # grados por metro
        lon_change = wind_speed_ew * 1 / (111000 * math.cos(math.radians(self.lat)))
        self.lat += lat_change + random.gauss(0, 0.00001)
        self.lon += lon_change + random.gauss(0, 0.00001)

        # Satélites GPS (más en altura, con variabilidad)
        base_sat = 4
        alt_bonus = min(8, int(self.altitude / 200))
        self.satellites = base_sat + alt_bonus + random.randint(-1, 1)
        self.satellites = max(0, min(12, self.satellites))

        # Aceleración (basada en fase, con ruido)
        if self.phase == 'ascent':
            ax = acceleration + random.gauss(0, 1)
            ay = random.gauss(0, 0.5)
            az = -self.g + random.gauss(0, 0.5)
        elif self.phase == 'coast':
            ax = random.gauss(0, 0.1)
            ay = random.gauss(0, 0.1)
            az = -self.g + random.gauss(0, 0.1)
        else:  # descent
            ax = random.gauss(0, 0.5)
            ay = random.gauss(0, 0.5)
            az = -self.g + acceleration + random.gauss(0, 0.5)

        # Giroscopio (más movimiento en ascenso, con ruido)
        gyro_scale = 10 if self.phase == 'ascent' else 1
        gx = random.gauss(0, gyro_scale)
        gy = random.gauss(0, gyro_scale)
        gz = random.gauss(0, gyro_scale)

        # Otros sensores con variación realista
        # UV: más alto en altura, con ruido
        uv_base = 20 + self.altitude / 50
        uv = max(0, min(200, uv_base + random.gauss(0, 10)))

        # TVOC y eCO2: varían con altitud y condiciones
        tvoc_base = 100 - self.altitude / 100
        tvoc = max(0, tvoc_base + random.gauss(0, 20))

        eco2_base = 450 - self.altitude / 100
        eco2 = max(350, eco2_base + random.gauss(0, 30))

        gps_bool = 1 if self.satellites >= 4 else 0

        return ["AeroNova", str(self.packet_counter), 
                f"{self.temperature:.2f}", f"{self.humidity:.2f}", f"{self.pressure:.2f}", f"{self.altitude:.2f}",
                f"{self.lat:.6f}", f"{self.lon:.6f}", str(self.satellites), 
                f"{ax:.2f}", f"{ay:.2f}", f"{az:.2f}",
                f"{gx:.2f}", f"{gy:.2f}", f"{gz:.2f}", 
                str(int(uv)), str(int(tvoc)), str(int(eco2)), str(gps_bool)]

    # ---------------- Leer Datos ---------------- #
    def read_data(self):
        sensor_keys = [
            "Temp (°C)", "Hum (%)", "Pres (hPa)", "Alt (m)",
            "Lat (°)", "Lon (°)", "Sat (#)", "ax (m/s²)",
            "ay (m/s²)", "az (m/s²)", "gx (°/s)", "gy (°/s)",
            "gz (°/s)", "UV", "TVOC (ppb)", "eCO2 (ppm)", "GPS (bool)"
        ]

        while self.reading:
            try:
                if self.simulation_mode:
                    # Generar datos simulados
                    values = self.generate_simulated_data()
                    time.sleep(1)  # Simular intervalo de 1 segundo
                else:
                    if self.serial_connection.in_waiting:
                        line = self.serial_connection.readline().decode().strip()
                        print(line)
                        values = line.split("\t")
                    else:
                        continue

                if len(values) >= 19:
                        uv_value = values[15]
                        co2_value = values[17]

                        uv_status, co2_status = self.classify_values(uv_value, co2_value)

                        if self.logging and self.csv_writer:
                            self.csv_writer.writerow(values + [uv_status, co2_status])

                        try:
                            lat = float(values[6])
                            lon = float(values[7])
                            if lat != 0.0 and lon != 0.0:
                                self.map_frame.update_position(lat, lon)
                        except:
                            pass

                        for i, key in enumerate(sensor_keys):
                            val = values[i+2]

                            if key == "UV":
                                val = f"{val} ({uv_status})"
                            elif key == "eCO2 (ppm)":
                                val = f"{val} ({co2_status})"

                            self.after(0, lambda k=key, v=val: self.sensor_labels[k].configure(text=v))

            except:
                self.after(0, self.handle_disconnect)
                break

    def handle_disconnect(self):
        self.disconnect_serial()
        status_text = "Simulación desconectada" if self.simulation_mode else "Puerto desconectado"
        self.lbl_status.configure(text=status_text, text_color="#ffaa33")
        self.toggle_logging.configure(text="Grabar Datos", fg_color="#2196f3")

# ---------------- MAIN ---------------- #
if __name__ == "__main__":
    app = GroundStationUI()
    app.mainloop()