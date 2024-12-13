# This code is based  on esp32knife by BlackVS
# https://github.com/BlackVS/esp32knife/

import sys
import hashlib
from os import path
import esp32partgen as esp32part
import esptool
from esptool import hexify

CHIP_NAME = "ESP32"  # One of "Espressif device", "ESP8266", "ESP32", "ESP32-S2"

# For each item in the array, the script searches for the first tuple value and replaces it with the second tuple value
# Make sure the find value uniquely identifies the code you want to patch in the binary and does not result in unintended matches
SIG_FIND_REPLACE = [
    (
        b"\xaa\xbb\xcc\xdd\xee\xff",
        b"\x00\x11\x22\x33\x44\x55"
    )
]

def read_firmware(filename):
    with open(filename, "rb") as f:
        return f.read()

def patch_binary(firmware_bin):
    for find, replace in SIG_FIND_REPLACE:
        if len(find) != len(replace):
            print("FATAL ERROR: Length of find and replace values must be equal since script does not support patching partition sizes")
            sys.exit(1)
        firmware_bin = firmware_bin.replace(find, replace)
    return firmware_bin

def locate_partition_table(firmware_bin):
    partition_table_offsets = [0x8000, 0x9000]
    for offset in partition_table_offsets:
        if firmware_bin[offset:offset + 2] == esp32part.PartitionDefinition.MAGIC_BYTES:
            return offset

    print("FATAL ERROR: Failed to find partitions table, exiting")
    sys.exit(1)

def load_partition_table(firmware_bin, offset):
    partition_table_size = 0xC00
    partitions_bin = firmware_bin[offset:offset + partition_table_size]
    partition_table = esp32part.PartitionTable.from_binary(partitions_bin)
    partition_table.verify()
    return partition_table

def process_partition(firmware_bin, partition):
    print("=" * 45)
    print(f"Validating hash and checksum of partition {partition}")

    patched_bin = firmware_bin[:]

    partition_data = firmware_bin[partition.offset:partition.offset + partition.size]
    try:
        image = esptool.LoadFirmwareImageFromBuffer(CHIP_NAME, partition_data)
    except Exception as e:
        print("Failed to parse partition:", e)
        return patched_bin

    # Calculate and patch checksum
    checksum_offset = image.image_size() + partition.offset - 1
    if image.append_digest:
        checksum_offset -= 32  # Subtract 256-bit digest

    calc_checksum = image.calculate_checksum()
    if image.checksum != calc_checksum:
        print(f"Checksum mismatch, calculated {calc_checksum:02x}, expected {image.checksum:02x}; patching")

        if firmware_bin[checksum_offset] != image.checksum:
            print(f"FATAL ERROR: Checksum offset {checksum_offset:x} does not match expected value {image.checksum:02x}")
            sys.exit(1)

        patched_bin = (
            patched_bin[:checksum_offset]
            + bytes([calc_checksum])
            + patched_bin[checksum_offset + 1:]
        )
    else:
        print("Checksum is valid, not patching.")

    # Calculate and patch hash
    hash_offset = image.image_size() + partition.offset - 32
    try:
        if image.append_digest:
            calc_digest = hashlib.sha256()
            calc_digest.update(patched_bin[partition.offset:hash_offset])
            calc_digest = calc_digest.digest()

            if image.stored_digest != calc_digest:
                print(
                    f"Digest {hexify(image.stored_digest)} does not match calculated value {hexify(calc_digest)}; patching"
                )

                if firmware_bin[hash_offset:hash_offset + 32] != image.stored_digest:
                    print(f"FATAL ERROR: Hash offset {hash_offset:x} does not match expected value {hexify(image.stored_digest)}")
                    sys.exit(1)

                patched_bin = (
                    patched_bin[:hash_offset]
                    + calc_digest
                    + patched_bin[hash_offset + 32:]
                )
            else:
                print(f"Hash {hexify(image.stored_digest)} is valid, not patching.")
    except AttributeError:
        pass  # ESP8266 image has no append_digest field

    return patched_bin

def write_patched_firmware(filename, patched_bin):
    output_filename = f"{path.splitext(filename)[0]}-patched{path.splitext(filename)[1]}"
    print(f"Writing patched firmware to {output_filename}")
    with open(output_filename, "wb") as f:
        f.write(patched_bin)

def main():
    firmware_file = sys.argv[1]
    firmware_bin = read_firmware(firmware_file)
    patched_bin = patch_binary(firmware_bin)

    partition_table_offset = locate_partition_table(patched_bin)

    partition_table = load_partition_table(patched_bin, partition_table_offset)

    for partition in partition_table:
        if partition.type == esp32part.APP_TYPE:
            patched_bin = process_partition(patched_bin, partition)

    if patched_bin != firmware_bin:
        write_patched_firmware(firmware_file, patched_bin)

if __name__ == "__main__":
    main()
