const bleno = require('@abandonware/bleno');
const { clearInterval } = require('timers');
const util = require('util');
const readline = require('readline');

var BlenoCharacteristic = bleno.Characteristic;

//
// This emulates the BLE peripheral service a Kilovault HLX+ battery.  I wrote this
// to send artificial data to the iPhone client to see how it behaved so that I could
// fully decode the status bits.
//

// This turns most of the characteristics into one liners.  Very few are queried by
// the phone app, but I didn't know which ones I needed for this to work.
class SimpleBMSCharacteristic extends BlenoCharacteristic
{
    constructor(uuid, value)
    { 
        super({ uuid: uuid, properties: ['read', 'write'] }) 
        this._value = value
    }

    onReadRequest(offset, callback) 
    { 
      console.log('SimpleBMSCharacteristic - onReadRequest: uuid = ' + this.uuid.toString() + ' value = ' + this._value.toString('hex'));
      callback(this.RESULT_SUCCESS, this._value) 
    }

    onWriteRequest(data, offset, withoutResponse, callback) 
    {
        if (offset) {
            callback(this.RESULT_ATTR_NOT_LONG);
        } else if (data.length !== this._value.length) {
            callback(this.RESULT_INVALID_ATTRIBUTE_LENGTH);
        } else {
            for (i = 0; i < this._value.length; i++)
                this._value[i] = data.readUInt8(i);
            callback(this.RESULT_SUCCESS);
            console.log('SimpleBMSCharacteristic - onWriteRequest: uuid = ' + this.uuid.toString() + ' value = ' + this._value.toString('hex'));
        }
    }
}

// Under service FFE0
class Handle17Characteristic extends SimpleBMSCharacteristic { constructor() { super("FFE1", Buffer.alloc(1, 0x00)) }}
class Handle19Characteristic extends SimpleBMSCharacteristic { constructor() { super("FFE2", Buffer.alloc(1, 0x00)) }}
class Handle21Characteristic extends SimpleBMSCharacteristic { constructor() { super("FFE3", Buffer.from('12345')) }}
// FFE4 is BMSNotificationCharacteristic
class Handle26Characteristic extends SimpleBMSCharacteristic { constructor() { super("FFE5", Buffer.from('12345')) }}
class Handle28Characteristic extends SimpleBMSCharacteristic { constructor() { super("FFE6", Buffer.from('MockBattery')) }}

// Under Service 180A (device information)
class SystemIdCharacteristic extends SimpleBMSCharacteristic { constructor() { super("2A23", Buffer.alloc(8, 0)) }}
class ModelNumberCharacteristic extends SimpleBMSCharacteristic { constructor() { super("2A24", Buffer.from('ImageA')) }}
class SerialNumberCharacteristic extends SimpleBMSCharacteristic { constructor() { super("2A25", Buffer.from('1500')) }}
class FirmwareRevCharacteristic extends SimpleBMSCharacteristic { constructor() { super("2A26", Buffer.from('V2.0')) }}
class HardwareRevCharacteristic extends SimpleBMSCharacteristic { constructor() { super("2A27", Buffer.alloc(1, 0)) }}
class SoftwareRevCharacteristic extends SimpleBMSCharacteristic { constructor() { super("2A28", Buffer.alloc(1, 0)) }}
class ManufacturerNameCharacteristic extends SimpleBMSCharacteristic { constructor() { super("2A29", Buffer.alloc(1, 0)) }}
class RegulatoryCertCharacteristic extends SimpleBMSCharacteristic { constructor() { super("2A2A", Buffer.alloc(1, 0)) }}
class PnpCharacteristic extends SimpleBMSCharacteristic { constructor() { super("2A50", Buffer.alloc(1, 0)) }}

// Under service FFC0
// These are completely wrong, but I don't think they get used
class FFC1Characteristic extends SimpleBMSCharacteristic { constructor() { super("FFC1", Buffer.alloc(8, 0)) }}
class FFC2Characteristic extends SimpleBMSCharacteristic { constructor() { super("FFC2", Buffer.alloc(8, 0)) }}

// This is the BLE characteristic that actually matters for us.  It generates an
// update once a second with battery status.
class BMSNotificationCharacteristic extends BlenoCharacteristic
{
    constructor()
    {
        super({
            uuid: 'FFE4',
            properties: ['notify'],
            value: null
        });

        this._updateValueCallback = null;
        this._intervalId = null;
        this._buffer = Buffer.alloc(60, 0x0);

        this.status = 0;

        this.computeSendBuffer();
    }

    computeSendBuffer()
    {
        // _buffer is a binary representation of the data to send 
        // in notifications
        var o = 0;
        this._buffer.writeUInt16LE(13310, o);         o += 2; // voltage
        this._buffer.writeUInt16LE(0, o);             o += 2; // unknown
        this._buffer.writeInt32LE(0, o);              o += 4; // current
        this._buffer.writeUInt32LE(102810, o);        o += 4; // total capacity (32-bit)
        this._buffer.writeUInt16LE(19, o);            o += 2; // charge cycles (32-bit)
        this._buffer.writeUInt16LE(91, o);            o += 2; // state of charge
        this._buffer.writeUInt16LE(2921, o);          o += 2; // temperature 
        this._buffer.writeUInt32LE(this.status, o);   o += 4; // status
        this._buffer.writeUint16LE(3327, o);          o += 2; // cell1 voltage
        this._buffer.writeUint16LE(3330, o);          o += 2; // cell2 voltage
        this._buffer.writeUint16LE(3329, o);          o += 2; // cell3 voltage
        this._buffer.writeUint16LE(3327, o);          o += 2; // cell4 voltage
        this._buffer.writeUint16LE(0, o);             o += 2; // cell5 voltage
        this._buffer.writeUint16LE(0, o);             o += 2; // cell6 voltage
        this._buffer.writeUint16LE(0, o);             o += 2; // cell7 voltage
        this._buffer.writeUint16LE(0, o);             o += 2; // cell8 voltage
        this._buffer.writeUint16LE(0, o);             o += 2; // cell9 voltage
        this._buffer.writeUint16LE(0, o);             o += 2; // cell10 voltage
        this._buffer.writeUint16LE(0, o);             o += 2; // cell11 voltage
        this._buffer.writeUint16LE(0, o);             o += 2; // cell12 voltage
        this._buffer.writeUint16LE(0, o);             o += 2; // cell13 voltage
        this._buffer.writeUint16LE(0, o);             o += 2; // cell14 voltage
        this._buffer.writeUint16LE(0, o);             o += 2; // cell15 voltage
        this._buffer.writeUint16LE(0, o);             o += 2; // cell16 voltage
        
        var checksum = 0x00;
        for (var i = 0; i < o; i += 2)
        {
            var word = this._buffer.readUint8(i);
            word = word * 0x100 + this._buffer.readUint8(i + 1);
            checksum += word;
            // If overflow occurs, wrap around
            if (checksum > 0xFFFF) {
                checksum = (checksum & 0xFFFF) + 1;
            }
        }
        console.log(checksum);

        // Final wrap around for any remaining overflow
        checksum = (checksum & 0xFFFF) + (checksum >> 16);

        this._buffer.writeUint16LE(checksum, o);        // unknown (checksum?)
    }

    onReadRequest(offset, callback) 
    {
        console.log('BMSNotificationCharacteristic - onReadRequest: uuid = ' + this.uuid.toString() + ' value = ' + this._value.toString('hex'));
      
        callback(this.RESULT_SUCCESS, this._value);
    }

    onSubscribe(maxValueSize, updateValueCallback) 
    {
        console.log('BMSNotificationCharacteristic - onSubscribe');
      
        this._updateValueCallback = updateValueCallback;

        this._intervalId = setInterval(() => {     
            // The actual buffer sent is hex encoded except for the first byte which
            // is 0xB0, and the final 8 bytes which are RRRRRRR. 
            var b = Buffer.alloc(121, 0);
            b.writeUint8(0xB0, 0);                                  // starting byte
            b.write(this._buffer.toString("hex").toUpperCase(), 1); // contents in hex
            b.write("RRRRRRRR", 113);                               // ending
            //console.log("Sending: %s", b.toString());

            this._value = b;
            var callback = this._updateValueCallback;
            if (callback != null) 
                callback(this._value);
        }, 1000);
   };
      
    onUnsubscribe() 
    {
        console.log('BMSNotificationCharacteristic - onUnsubscribe');

        if (this._intervalId != null)
        {
            clearInterval(this._intervalId);
            this._intervalId = null;
        }
      
        this._updateValueCallback = null;
    };
}

var BlenoPrimaryService = bleno.PrimaryService;

console.log('bleno - kilovault bms');

bleno.on('stateChange', function(state) {
  console.log('on -> stateChange: ' + state);

  if (state === 'poweredOn') {
    bleno.startAdvertising('MockBattery', ['FFE0']);
  } else {
    bleno.stopAdvertising();
  }
});

var notificationCharacteristic = new BMSNotificationCharacteristic();
bleno.on('advertisingStart', function(error) {
  console.log('on -> advertisingStart: ' + (error ? 'error ' + error : 'success'));

  if (!error) {
    bleno.setServices([
      new BlenoPrimaryService({
        uuid: 'FFE0',
        characteristics: [
          new Handle17Characteristic(),
          new Handle19Characteristic(),
          new Handle21Characteristic(),
          notificationCharacteristic,
          new Handle26Characteristic(),
          new Handle28Characteristic()
        ]
      }),
      new BlenoPrimaryService({
        uuid: '180A',
        characteristics: [
          new SystemIdCharacteristic(),
          new ModelNumberCharacteristic(),
          new SerialNumberCharacteristic(),
          new FirmwareRevCharacteristic(),
          new HardwareRevCharacteristic(),
          new SoftwareRevCharacteristic(),
          new ManufacturerNameCharacteristic(),
          new RegulatoryCertCharacteristic(),
          new PnpCharacteristic()
        ]
      }),
      new BlenoPrimaryService({
        uuid: 'FFC0',
        characteristics: [
          new FFC1Characteristic(),
          new FFC2Characteristic()
        ]
      })
    ]);
  }
});

var rl = readline.createInterface({input: process.stdin, output: process.stdout});
const prompt = (query) => new Promise((resolve) => rl.question(query, resolve));

(async() => {
  while (true)
    {
      const status = notificationCharacteristic.status;
      console.log("Status is 0x%s, %d", status.toString(16), status);
      const statusString = await prompt("New value in hex?");
      if (statusString == "exit")
      {
          rl.close();
      }
      else
      {
        notificationCharacteristic.status = parseInt(statusString, 16);
        notificationCharacteristic.computeSendBuffer();
      }
    }
})();

// When done reading prompt, exit program 
rl.on('close', () => process.exit(0));


/* status values
0x1 = HTC high temp charging
0x2 = HTD high temp discharging
0x4 = LTC low temp charging
0x8 = LTD low temp discharging
0x10 = OCD over current discharging
0x20 = OCC over current charging
0x40 = LV low voltage
0x80 = HV high voltage
0x200000 = short circuit


*/