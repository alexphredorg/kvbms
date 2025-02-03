import asyncio
from bleak import BleakScanner, BleakClient
import binascii
import struct

async def showDevices():
    devices = await BleakScanner.discover()
    for d in devices:
        print(d)

# This code is heavily based on 
# https://github.com/fancygaphtrn/esphome/tree/master/my_components/kilovault_bms_ble
#
#
# bytearray(b'3E350000000000009A91010013005C00690B00010000580D520D580D420D00000000000000000000000000000000000000000000000003FBRRRRRRRR')
# status: 256
# current: 0.0
# voltage: 13.63
# total_capacity: 102.81
# charge_cycles = 19.0
# state of charge: 0.92
# temperature = 18.950000000000045
# cell1voltage = 3.416
# cell2voltage = 3.41
# cell3voltage = 3.416
# cell4voltage = 3.394


class KilovaultBatteryBMS:
    MODEL_NBR_UUID = "2A24"
    KILOVAULT_BMS_SERVICE_UUID = "FFE0"
    KILOVAULT_BMS_NOTIFY_CHARACTERISTIC_UUID = "FFE4"
    KILOVAULT_BMS_CONTROL_CHARACTERISTIC_UUID = "FA02"
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

        # unpack the binary data
        unpacked_data = struct.unpack('<hhiIhhhhhhhhh', bytes(bindata))

        # process into output values
        i = (x for x in range(len(unpacked_data)))
        voltage = float(unpacked_data[next(i)]) * 0.001
        next(i) # unknown value at unpacked_data[1]
        current = float(unpacked_data[next(i)]) * 0.001
        total_capacity = float(unpacked_data[next(i)]) * 0.001
        charge_cycles = unpacked_data[next(i)]
        state_of_charge = float(unpacked_data[next(i)]) * 0.01
        temperature = float(unpacked_data[next(i)] * 0.1) - 273.15
        status = unpacked_data[next(i)]
        next(i) # unknown value at unpacked_data[8]
        cell1voltage = float(unpacked_data[next(i)]) * 0.001
        cell2voltage = float(unpacked_data[next(i)]) * 0.001
        cell3voltage = float(unpacked_data[next(i)]) * 0.001
        cell4voltage = float(unpacked_data[next(i)]) * 0.001

        self.callback(
            voltage, 
            current, 
            total_capacity, 
            charge_cycles, 
            state_of_charge, 
            status, 
            temperature, 
            cell1voltage, 
            cell2voltage, 
            cell3voltage, 
            cell4voltage)
    
        self.status_event.set()

    def decode_kilovault_16(self, data, i):
        i0 = int(chr(data[i+0]), 16)
        i1 = int(chr(data[i+1]), 16)
        i2 = int(chr(data[i+2]), 16)
        i3 = int(chr(data[i+3]), 16)
        #print(f"{i2} {i3} {i0} {i1}")
        return (i2 << 12) | (i3 << 8) | (i0 << 4) | i1

    def decode_kilovault_32(self, data, i):
        i0 = self.decode_kilovault_16(data, i+0)
        i4 = self.decode_kilovault_16(data, i+4)
        return (i4 << 16) | i0

    async def connect_and_readonce(self):
        async with BleakClient(self.address) as client:
            print("connected")
            # find the BMS service out of the list of services
            bmsService = client.services.get_service(self.KILOVAULT_BMS_SERVICE_UUID)
            # find the notification service that hangs off of the BMS
            notifyService = bmsService.get_characteristic(self.KILOVAULT_BMS_NOTIFY_CHARACTERISTIC_UUID)
            # turn on notifications.  Data is sent to notifyCallback
            await client.start_notify(notifyService, self.notifyCallback)
            # wait for a notification to be complete
            await self.status_event.wait()
            ## wait 3 seconds.  My battery sends status every second
            #await asyncio.sleep(timeout)
            await client.stop_notify(notifyService)


print("Bluetooth Devices:")
asyncio.run(showDevices())

def valuesUpdated(voltage, current, total_capacity, charge_cycles, state_of_charge, status, temperature, cell1voltage, cell2voltage, cell3voltage, cell4voltage):
    print(f"voltage: {voltage}")
    print(f"current: {current}")
    print(f"total_capacity: {total_capacity}")
    print(f"charge_cycles = {charge_cycles}")
    print(f"state of charge: {state_of_charge}")
    print(f"status: {status} {status:016b}")
    print(f"temperature = {temperature}")
    print(f"cell1voltage = {cell1voltage}")
    print(f"cell2voltage = {cell2voltage}")
    print(f"cell3voltage = {cell3voltage}")
    print(f"cell4voltage = {cell4voltage}\n")


bms = KilovaultBatteryBMS("D07CF327-2163-5D2D-BB12-89919983621E", valuesUpdated)
asyncio.run(bms.connect_and_readonce())
