#!/usr/bin/env python3
"""
RS232 Hardware Verification Tool
Tests basic communication with the pan-tilt unit at a fundamental level.
"""

import serial
import time
import binascii
import sys
import argparse

def test_hardware(port, baudrate=9600):
    """Send test signals and monitor for any response."""
    print(f"Opening {port} at {baudrate} baud...")
    
    try:
        # Try to open the port with basic settings
        ser = serial.Serial(
            port=port,
            baudrate=baudrate,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=0.1
        )
        
        # Configure hardware lines
        if hasattr(ser, 'dtr'):
            ser.dtr = False
        if hasattr(ser, 'rts'):
            ser.rts = False
        
        print(f"Port opened successfully. Lines: DTR={ser.dtr if hasattr(ser, 'dtr') else 'N/A'}, "
              f"RTS={ser.rts if hasattr(ser, 'rts') else 'N/A'}")
        
        # Clear buffers
        ser.reset_input_buffer()
        ser.reset_output_buffer()
        
        # First test: monitor for any incoming data (device might be sending without prompting)
        print("\nTest 1: Monitoring for 5 seconds for any incoming data...")
        start_time = time.time()
        received_data = b''
        
        while (time.time() - start_time) < 5:
            if ser.in_waiting > 0:
                new_data = ser.read(ser.in_waiting)
                received_data += new_data
                hex_data = ' '.join([f"0x{b:02X}" for b in new_data])
                print(f"Received: {hex_data}")
            time.sleep(0.1)
            
        if received_data:
            print(f"Received {len(received_data)} bytes without sending anything")
            hex_data = ' '.join([f"0x{b:02X}" for b in received_data])
            print(f"Data: {hex_data}")
        else:
            print("No data received during passive monitoring")
        
        # Second test: Send ASCII characters and watch for response
        print("\nTest 2: Sending ASCII test string...")
        test_string = "HELLO\r\n"
        print(f"Sending: {test_string.encode()}")
        ser.write(test_string.encode())
        ser.flush()
        
        # Wait for response
        time.sleep(1)
        received_data = b''
        if ser.in_waiting > 0:
            received_data = ser.read(ser.in_waiting)
            hex_data = ' '.join([f"0x{b:02X}" for b in received_data])
            print(f"Received {len(received_data)} bytes: {hex_data}")
        else:
            print("No response to ASCII test string")
        
        # Third test: Send the start marker (0x3C) and watch for any response
        print("\nTest 3: Sending start marker (0x3C)...")
        ser.write(bytes([0x3C]))
        ser.flush()
        
        # Wait for response
        time.sleep(1)
        received_data = b''
        if ser.in_waiting > 0:
            received_data = ser.read(ser.in_waiting)
            hex_data = ' '.join([f"0x{b:02X}" for b in received_data])
            print(f"Received {len(received_data)} bytes: {hex_data}")
        else:
            print("No response to start marker")
        
        # Fourth test: Send known bytes from original TX capture
        print("\nTest 4: Sending individual bytes with delay...")
        test_bytes = [0x3C, 0x80, 0x5C, 0xC0, 0x5C]
        
        for b in test_bytes:
            print(f"Sending byte: 0x{b:02X}")
            ser.write(bytes([b]))
            ser.flush()
            time.sleep(0.1)
            
            if ser.in_waiting > 0:
                data = ser.read(ser.in_waiting)
                hex_data = ' '.join([f"0x{b:02X}" for b in data])
                print(f"  Response: {hex_data}")
            else:
                print("  No response")
        
        print("\nHardware tests completed")
        ser.close()
        
    except Exception as e:
        print(f"Error: {e}")
        return False
    
    return True

def main():
    parser = argparse.ArgumentParser(description='RS232 Hardware Verification Tool')
    parser.add_argument('--port', type=str, required=True, help='Serial port')
    parser.add_argument('--baudrate', type=int, default=9600, help='Baud rate')
    args = parser.parse_args()
    
    test_hardware(args.port, args.baudrate)

if __name__ == "__main__":
    main() 