import customtkinter as ctk
import serial
import serial.tools.list_ports
import threading
import csv
from datetime import datetime
import tkintermapview

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
            self.map_widget.set_position(lat, lon)
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

        self.lbl_status = ctk.CTkLabel(top_frame, text="Estado: Desconectado", font=("Roboto",14), text_color="#ff5555")
        self.lbl_status.grid(row=1, column=0, columnspan=5, pady=5)

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
        port = self.port_selector.get()
        if not port:
            self.lbl_status.configure(text="Selecciona un puerto", text_color="#ffbb33")
            return

        try:
            self.serial_connection = serial.Serial(port, 9600, timeout=1)
            self.reading = True
            self.lbl_status.configure(text=f"Conectado a {port}", text_color="#4cff4c")
            threading.Thread(target=self.read_serial, daemon=True).start()
        except Exception as e:
            self.lbl_status.configure(text=f"Error: {e}", text_color="#ff5555")

    def disconnect_serial(self):
        self.reading = False
        self.logging = False

        if self.serial_connection:
            try:
                self.serial_connection.close()
            except:
                pass

        self.lbl_status.configure(text="Estado: Desconectado", text_color="#ff5555")
        self.toggle_logging.configure(text="Grabar Datos", fg_color="#2196f3")

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

    # ---------------- Leer Serial ---------------- #
    def read_serial(self):
        sensor_keys = [
            "Temp (°C)", "Hum (%)", "Pres (hPa)", "Alt (m)",
            "Lat (°)", "Lon (°)", "Sat (#)", "ax (m/s²)",
            "ay (m/s²)", "az (m/s²)", "gx (°/s)", "gy (°/s)",
            "gz (°/s)", "UV", "TVOC (ppb)", "eCO2 (ppm)", "GPS (bool)"
        ]

        while self.reading:
            try:
                if self.serial_connection.in_waiting:
                    line = self.serial_connection.readline().decode().strip()
                    values = line.split("\t")

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
        self.lbl_status.configure(text="Puerto desconectado", text_color="#ffaa33")
        self.toggle_logging.configure(text="Grabar Datos", fg_color="#2196f3")

# ---------------- MAIN ---------------- #
if __name__ == "__main__":
    app = GroundStationUI()
    app.mainloop()