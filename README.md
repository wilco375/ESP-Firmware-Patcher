# ESP firmware file patcher
Can be used to apply a binary patch to ESP8266/ESP32 firmware files and correct the checksum and hash of the modified partitions.  

## Usage
In `main.py`, replace the `CHIP_NAME` value with the correct ESP chip name, and add your find/replaces at `SIG_FIND` and `SIG_REPLACE`.  
Then run `pip install -r requirements.txt` to install all required packages.
Finally, run `python main.py <firmware_file>` to patch a firmware file. The patched firmware will be written to `<firmware_file>-patched.bin`.

## Credits
This code is based on [esp32knife](https://github.com/BlackVS/esp32knife/) by BlackVS.
