import asyncio
from bleak import BleakScanner, BleakClient
import binascii
import struct
import argparse

async def showDevices():
    devices = await BleakScanner.discover()
    for d in devices:
        print(d)

# This code is heavily based on 
# https://github.com/fancygaphtrn/esphome/tree/master/my_components/kilovault_bms_ble
class KilovaultBatteryBMS:
    MODEL_NBR_UUID = "2A24"
    KILOVAULT_BMS_SERVICE_UUID = "FFE0"
    KILOVAULT_BMS_NOTIFY_CHARACTERISTIC_UUID = "FFE4"
    #KILOVAULT_BMS_CONTROL_CHARACTERISTIC_UUID = "FA02"
    KILOVAULT_START_END_BYTE = 0xB0

    def __init__(self, address, callback):
        self.address = address
        self.callback = callback
        # we get many notifications for one status update, this accumulates them
        self.status_buffer = bytearray()
        # signalled when we've received status
        self.status_event = asyncio.Event()

    # this is called for each frame from the BMS.  We assemble
    # the frames until we get a full status block.  Status
    # starts and ends with 0xB0
    def notifyCallback(self, sender, data):
        #print(f"{sender}: {data}")
        if data[0] == self.KILOVAULT_START_END_BYTE:
            if len(self.status_buffer) > 0 and self.status_buffer[0] == self.KILOVAULT_START_END_BYTE:
                print(f'buffer = {self.status_buffer}')
                print(f'length = {len(self.status_buffer)}')
                self.decode_status_buffer(self.status_buffer[1:])
            self.status_buffer = data
        else:
            self.status_buffer.extend(data)

    # This function decodes status
    #
    # This is gross.  The buffer contains a hex string, except for the first
    # byte which is b0.  We have to manually process that back to useful 
    # numbers and that is what this function does.
    #
    # offsets in here are nibbles (4 bits)
    def decode_status_buffer(self, data):
        # convert the hex string back into binary
        bindata = binascii.unhexlify(data[0:60])
        print(data)

        # unpack the binary data
        unpacked_data = struct.unpack('<hhiIhhhhhhhhh', bytes(bindata))
        print(unpacked_data)

        # process into output values
        i = (x for x in range(len(unpacked_data)))
        voltage = float(unpacked_data[next(i)]) * 0.001                     # offset 0
        print(unpacked_data[next(i)]) # unknown value at unpacked_data[1]   # offset 2
        current = float(unpacked_data[next(i)]) * 0.001                     # offset 4
        total_capacity = float(unpacked_data[next(i)]) * 0.001              # offset 8
        charge_cycles = unpacked_data[next(i)]                              # offset 12
        state_of_charge = float(unpacked_data[next(i)]) * 0.01              # offset 14
        temperature = float(unpacked_data[next(i)] * 0.1) - 273.15          # offset 16
        status1 = unpacked_data[next(i)]                                    # offset 18
        status2 = unpacked_data[next(i)]                                    # offset 20
        cell1voltage = float(unpacked_data[next(i)]) * 0.001                # offset 22
        cell2voltage = float(unpacked_data[next(i)]) * 0.001                # offset 24
        cell3voltage = float(unpacked_data[next(i)]) * 0.001                # offset 26
        cell4voltage = float(unpacked_data[next(i)]) * 0.001                # offset 28

        self.callback(
            voltage, 
            current, 
            total_capacity, 
            charge_cycles, 
            state_of_charge, 
            status1, 
            status2,
            temperature, 
            cell1voltage, 
            cell2voltage, 
            cell3voltage, 
            cell4voltage)
    
        self.status_event.set()

    async def connect_and_readonce(self):
        async with BleakClient(self.address) as client:
            print("connected")
            # find the BMS service out of the list of services
            bmsService = client.services.get_service(self.KILOVAULT_BMS_SERVICE_UUID)
            print(bmsService)
            # find the notification service that hangs off of the BMS
            notifyService = bmsService.get_characteristic(self.KILOVAULT_BMS_NOTIFY_CHARACTERISTIC_UUID)
            print(notifyService)
            # turn on notifications.  Data is sent to notifyCallback
            await client.start_notify(notifyService, self.notifyCallback)
            # wait for a notification to be complete
            await self.status_event.wait()
            ## wait 3 seconds.  My battery sends status every second
            #await asyncio.sleep(timeout)
            await client.stop_notify(notifyService)


def valuesUpdated(voltage, current, total_capacity, charge_cycles, state_of_charge, status1, status2, temperature, cell1voltage, cell2voltage, cell3voltage, cell4voltage):
    print(f"voltage: {voltage}")
    print(f"current: {current}")
    print(f"total_capacity: {total_capacity}")
    print(f"charge_cycles = {charge_cycles}")
    print(f"state of charge: {state_of_charge}")
    print(f"status1: {status1} {status1:016b}")
    print(f"status2: {status2} {status2:016b}")
    print(f"temperature = {temperature}")
    print(f"cell1voltage = {cell1voltage}")
    print(f"cell2voltage = {cell2voltage}")
    print(f"cell3voltage = {cell3voltage}")
    print(f"cell4voltage = {cell4voltage}\n")

# status1 notes
# 256 what I normally see (CAN is also off, might be standby)
# 0 after turning on CAN
# 3348 occasionally

# status2 notes
# 3352 when status1 is 3348, otherwise 0

# discharging:
# status1: 256 0000000100000000
# status2: 0 0000000000000000

parser = argparse.ArgumentParser(
    prog="Kilovault BLE Test Client",
    description="This program can get status information from a Kilovault HLX+ battery")
parser.add_argument("--address", type=str, default=None, help="Address of BLE device to probe")
args = parser.parse_args()
if (args.address == None):
    print("Bluetooth Devices:")
    asyncio.run(showDevices())
else:
    bms = KilovaultBatteryBMS(args.address, valuesUpdated)
    asyncio.run(bms.connect_and_readonce())
