import sys
import time
import threading
import asyncio
import json
from bleak import BleakScanner
from PyQt5.QtWidgets import *
from PyQt5.QtCore import QThread, QTimer, pyqtSignal, Qt

import bluetooth


class MainWindow(QMainWindow):
    def __init__(self):
        QMainWindow.__init__(self)

        self.tab1instance = Tab1()


        self.device_info_file = 'BT_Devices.json'
        try:
            with open(self.device_info_file, 'r') as file:
                self.active_device_info = json.load(file)
        except (IOError, ValueError):
            self.active_device_info = {}






        self.setWindowTitle("Bluetooth Scanner")
        self.setGeometry(100, 100, 600, 600)

        # Setup the tab widget
        self.tabs = QTabWidget()
        self.tab1 = QWidget()
        self.tab2 = QWidget()

        # Add tabs
        self.tabs.addTab(self.tab1, "Bluetooth Scanner")
        self.tabs.addTab(self.tab2, "Bluetooth Devices")





        self.table = Tab1()
        self.start_button = QPushButton("Start")
        self.start_button.clicked.connect(self.start_scanning)
        self.stop_button = QPushButton("Stop")
        self.stop_button.clicked.connect(self.stop_scanning)
        self.stop_button.setEnabled(False)
        button_layout = QHBoxLayout()
        button_layout.addWidget(self.start_button)
        button_layout.addWidget(self.stop_button)

        self.tab1_layout = QVBoxLayout()
        self.tab1.setLayout(self.tab1_layout)

        self.tab1_layout.addWidget(self.table)
        self.tab1_layout.addLayout(button_layout)

        #central_widget = QWidget()
        #central_widget.setLayout(self.tab1_layout)
        self.setCentralWidget(self.tabs)

        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

        self.scan_thread = ScanThread()
        self.scan_thread.device_found.connect(self.device_found)

        self.setup_bluetooth_tab()


    def setup_bluetooth_tab(self):
        main_layout = QVBoxLayout(self.tab2)  # Main layout for the tab

        # Initialize the QTableWidget
        self.device_table = QTableWidget()
        self.device_table.setColumnCount(5)
        self.device_table.setHorizontalHeaderLabels(["Enabled", "Highlight", "Address", "Name", "RSSI"])

        # Allow user to adjust column widths manually
        self.device_table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.device_table.setColumnWidth(0, 65)  # Initial width for the "Enabled" checkbox column
        self.device_table.setColumnWidth(1, 65)  # Initial width for the "Highlight" checkbox column
        self.device_table.setColumnWidth(2, 130)  # Initial width for the Address column
        self.device_table.setColumnWidth(3, 130)  # Initial width for the Name column
        self.device_table.setColumnWidth(4, 60)  # Initial width for the RSSI column



        self.device_table.setSortingEnabled(True)

        # Load JSON data
        with open('BT_Devices.json', 'r') as file:
            devices = json.load(file)

        # Populate the table with devices
        for address, info in devices.items():
            row_count = self.device_table.rowCount()
            self.device_table.insertRow(row_count)

            # Create the checkbox for "Enabled"
            enabled_checkbox = QCheckBox()
            enabled_checkbox.setChecked(info.get('enabled', False))
            enabled_checkbox.stateChanged.connect(lambda state, addr=address:
                                                  self.update_json_file(addr, 'enabled', state == Qt.Checked))

            # Create the checkbox for "Highlight"
            highlight_checkbox = QCheckBox()
            highlight_checkbox.setChecked(info.get('highlight', False))
            highlight_checkbox.stateChanged.connect(lambda state, addr=address:
                                                    self.update_json_file(addr, 'highlight', state == Qt.Checked))

            # Add checkboxes to the table
            self.device_table.setCellWidget(row_count, 0, enabled_checkbox)
            self.device_table.setCellWidget(row_count, 1, highlight_checkbox)
            self.device_table.setItem(row_count, 2, QTableWidgetItem(address))
            self.device_table.setItem(row_count, 3, QTableWidgetItem(info.get('bt_name', '')))
            self.device_table.setItem(row_count, 4, QTableWidgetItem(str(info.get('rssi', ''))))

        # Add table to the layout
        main_layout.addWidget(self.device_table)

        # Clear button setup
        clear_button = QPushButton("Clear")
        clear_button.clicked.connect(self.confirm_clear)
        bottom_button_layout = QHBoxLayout()
        bottom_button_layout.addStretch(1)
        bottom_button_layout.addWidget(clear_button)
        main_layout.addLayout(bottom_button_layout)

        self.tab2.setLayout(main_layout)



    def update_json_file(self, address, key, value):
        """ Update the JSON file when checkbox states change """
        if address in self.active_device_info:
            self.active_device_info[address][key] = value
            with open(self.device_info_file, 'w') as file:
                json.dump(self.active_device_info, file, indent=4)





    def confirm_clear(self):
        reply = QMessageBox.question(self, 'Confirm Clear',
                                     'Are you sure you want to clear all active device information?',
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.MainWindowInstance.clear_active_devices()



    def start_scanning(self):
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.status_bar.showMessage("Scanning...")
        self.scan_thread.start_scanning()
        self.scan_thread.start()

    def stop_scanning(self):
        self.stop_button.setEnabled(False)
        self.start_button.setEnabled(True)
        self.status_bar.showMessage("Stopped")
        self.scan_thread.stop_scanning()

    def device_found(self, bt_addr, bt_name, rssi, error, data, uuid):
        if error:
            self.status_bar.showMessage(f"Scan error: {error}")
            return

        # Check if the device is in the JSON loaded dictionary
        if bt_addr in self.active_device_info:
            if bt_addr in self.table.devices:
                self.table.update_device(bt_addr, rssi if rssi is not None else 'N/A')
            else:
                # If the device is not in the dictionary, add it to the table and JSON
                self.table.add_device_to_tab1(bt_addr, bt_name, rssi if rssi is not None else 'N/A')
        else:
            self.table.add_device_to_JSON(bt_addr, bt_name, rssi)
            #self.setup_bluetooth_tab()




class Tab1(QTableWidget):

    lock = threading.RLock()

    def __init__(self):
        QTableWidget.__init__(self, 0, 4)  # Increase the number of columns to 4
        self.setHorizontalHeaderLabels(["BT Address", "BT Name", "Timer", "RSSI"])
        self.devices = {}
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_timers)
        self.timer.start(1000)


        self.device_info_file = 'BT_Devices.json'
        try:
            with open(self.device_info_file, 'r') as file:
                self.active_device_info = json.load(file)
        except (IOError, ValueError):
            self.active_device_info = {}

    def add_device_to_tab1(self, bt_addr, bt_name, rssi):
        if bt_addr not in self.devices:
            row = self.rowCount()
            self.insertRow(row)
            self.setItem(row, 0, QTableWidgetItem(bt_addr))
            self.setItem(row, 1, QTableWidgetItem(bt_name))
            self.setItem(row, 2, QTableWidgetItem("0"))  # Timer reset to 0
            self.setItem(row, 3, QTableWidgetItem(str(rssi)))  # Add RSSI value
            self.devices[bt_addr] = [bt_name, 0, row, rssi]






        else:
            # Update RSSI and timer if device already exists
            self.update_device(bt_addr, rssi)

    def add_device_to_JSON(self, bt_addr, bt_name, rssi):
        self.active_device_info[bt_addr] = {
            'bt_name': bt_name,
            'rssi': rssi,
            # 'data': data,
            # 'uuid': uuid,
            'enabled': True,
            'highlight': False
        }

        self.save_device_info()
        print("Saved")


    def update_device(self, bt_addr, rssi):
        self.devices[bt_addr][1] += 1  # Increment timer
        self.devices[bt_addr][3] = rssi  # Update RSSI
        self.item(self.devices[bt_addr][2], 2).setText(str(self.devices[bt_addr][1]))
        self.item(self.devices[bt_addr][2], 3).setText(str(rssi))

    def remove_device(self, bt_addr):
        row = self.devices[bt_addr][2]
        self.removeRow(row)
        del self.devices[bt_addr]

    def update_timers(self):
        for bt_addr in self.devices:
            self.devices[bt_addr][1] += 1
            self.item(self.devices[bt_addr][2], 2).setText(str(self.devices[bt_addr][1]))

    def save_device_info(self, assume_locked=False):
        if not assume_locked:
            with self.lock:
                self._save_device_info_contents()
        else:
            self._save_device_info_contents()

    def _save_device_info_contents(self):
        with open(self.device_info_file, 'w') as file:
            json.dump(self.active_device_info, file, indent=4)



    def clear_active_devices(self):
        """
        Clears the active device information.
        """
        with self.lock:  # Assuming this lock is used for thread-safe file access
            self.active_device_info = {}  # Resetting the active device information
            # Saving the empty state to the file
            with open(self.device_info_file, 'w') as file:
                json.dump(self.active_device_info, file, indent=4)




class ScanThread(QThread):
    device_found = pyqtSignal(str, str, int, str, str, str)

    def __init__(self):
        QThread.__init__(self)
        self.running = False



    async def scan_btle_devices(self):
        try:
            # Create a scanner instance and start the scan within a controlled async context
            #scanner = BleakScanner()
            devices = await BleakScanner.discover(timeout=5, return_adv=True)

            ##

            ##


            #print("Devices: \n", devices)

            i=0

            for device, adv in devices.values():
                ##   Possible Values can be:
                ##   device.name    or device.address    or device.details
                ##   adv.rssi     adv.BLEDevice    adv.LocalName
                ##   adv.service_uuids       adv.manufacturer_data

                #print(f"Metadata: {device}", flush=True)
                #print(f"Metadata: {adv}", flush=True)

                name = device.name or "Unknown"
                rssi = adv.rssi
                man_data = adv.manufacturer_data or ""
                service_uuid = adv.service_uuids or ""

                i=i+1

                print(f"{i:2} device address: {device.address}  ({name})  ({rssi})  ({man_data})  ({service_uuid})")

                self.device_found.emit(device.address, name, rssi, "", str(man_data), str(service_uuid))



        except Exception as e:
            # Handle and log any errors that occur during scanning
            print(f"Error during BTLE scanning: {e}")
            self.device_found.emit("", "", 0, str(e), "", "")



    def run(self):
        self.running = True
        while self.running:
            try:
                # Classic Bluetooth scanning
                nearby_devices = bluetooth.discover_devices(lookup_names=True)
                for bt_addr, bt_name in nearby_devices:
                    # Emit without RSSI; no error message
                    rssi = -1
                    self.device_found.emit(bt_addr, bt_name, rssi, "", "", "")
            except Exception as e:
                print(f"Error during Bluetooth scanning: {e}")

            # BTLE scanning with error handling
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(self.scan_btle_devices())
            finally:
                loop.close()


            time.sleep(1)

    def start_scanning(self):
        self.running = True

    def stop_scanning(self):
        self.running = False



if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
