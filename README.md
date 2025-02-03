# kvbms
Scripts to query/manage Kilovault batteries

This is a set of test Python scripts to talk to Kilovault (Topband) HLX+ batteries via BLE and oneday CAN.

My goal in sharing these simple samples is to let others figure out how to integrate them into their own projects.  I plan to incorporate this into Venus OS to run on the Victron Cerbo GX.

Right now functionality is limited to reporting data and not all fields are parsed (specifically I haven't figured out the status field).  I'd love help there.

This is based on the great work found in https://github.com/fancygaphtrn/esphome/tree/master/my_components/kilovault_bms_ble