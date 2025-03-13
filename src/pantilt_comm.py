#!/usr/bin/env python3
"""
Pan-Tilt Basic Communication Tester
Focuses on establishing communication with the pan-tilt unit
using only initialization and heartbeat commands.
"""

import serial
import time
import logging
import binascii
import argparse
import os
from datetime import datetime

class PanTiltConnector:
    def __init__(self, port, baudrate=9600, timeout=1, debug=False):
        """Initialize the connection tester."""
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.debug = debug
        self.ser = None
        
        # Create log directory
        os.makedirs("logs", exist_ok=True)
        
        # Set up logging
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = f"logs/pantilt_comm_{timestamp}.log"
        
        log_level = logging.DEBUG if debug else logging.INFO
        logging.basicConfig(
            level=log_level,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler()
            ]
        )
        
        # Create raw log file
        self.raw_log = open(f"logs/raw_comm_{timestamp}.bin", "wb")
        
        logging.info(f"=== Pan-Tilt Communication Tester ===")
        logging.info(f"Log files: {log_file} and raw_comm_{timestamp}.bin")
        
    def __del__(self):
        """Ensure resources are properly closed."""
        self.disconnect()
        if hasattr(self, 'raw_log') and self.raw_log:
            self.raw_log.close()
    
    def connect(self, parity=serial.PARITY_NONE, stopbits=serial.STOPBITS_ONE,
                bytesize=serial.EIGHTBITS, xonxoff=False, rtscts=False, dsrdtr=False):
        """Connect to the serial port with specified parameters."""
        try:
            if self.ser and self.ser.is_open:
                self.ser.close()
                
            self.ser = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                bytesize=bytesize,
                parity=parity,
                stopbits=stopbits,
                timeout=self.timeout,
                xonxoff=xonxoff,
                rtscts=rtscts,
                dsrdtr=dsrdtr
            )
            
            # Configure RTS/DTR lines
            if hasattr(self.ser, 'dtr'):
                self.ser.dtr = False  # Data Terminal Ready
            if hasattr(self.ser, 'rts'):
                self.ser.rts = False  # Request To Send
                
            config = f"{self.baudrate} baud, "
            config += f"{bytesize}"
            config += "N" if parity == serial.PARITY_NONE else "E" if parity == serial.PARITY_EVEN else "O"
            config += f"{stopbits}"
            
            logging.info(f"Connected to {self.port} ({config})")
            logging.info(f"DTR: {self.ser.dtr if hasattr(self.ser, 'dtr') else 'N/A'}, "
                        f"RTS: {self.ser.rts if hasattr(self.ser, 'rts') else 'N/A'}")
            
            # Flush any existing data
            self.ser.reset_input_buffer()
            self.ser.reset_output_buffer()
            
            return True
        except Exception as e:
            logging.error(f"Failed to connect: {e}")
            return False
    
    def disconnect(self):
        """Disconnect from the serial port."""
        if self.ser and self.ser.is_open:
            try:
                # Proper shutdown: reset lines
                if hasattr(self.ser, 'dtr'):
                    self.ser.dtr = True
                if hasattr(self.ser, 'rts'):
                    self.ser.rts = True
                    
                # Wait briefly for signals to stabilize
                time.sleep(0.1)
                
                # Close the port
                self.ser.close()
                logging.info(f"Disconnected from {self.port}")
            except Exception as e:
                logging.error(f"Error during disconnect: {e}")
    
    def hex_to_bytes(self, hex_string):
        """Convert a hex string in the format '0x3C 0x80 ...' to bytes."""
        clean_hex = hex_string.replace('0x', '').replace(' ', '')
        return bytes.fromhex(clean_hex)
    
    def bytes_to_hex_string(self, data):
        """Convert bytes to a formatted hex string."""
        return ' '.join([f"0x{b:02X}" for b in data])

    def send_bytes_with_delay(self, command_name, hex_command, delay_ms=5):
        """Send a command byte by byte with delay between bytes for timing-sensitive devices."""
        try:
            # Convert the hex string to bytes
            command_bytes = self.hex_to_bytes(hex_command)
            
            # Log the command
            logging.info(f"Sending {command_name} byte-by-byte (delay: {delay_ms}ms): {hex_command}")
            
            # Send each byte with a delay
            for i, byte in enumerate(command_bytes):
                self.ser.write(bytes([byte]))
                self.ser.flush()
                
                # Log to raw log
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
                self.raw_log.write(f"TX {timestamp} BYTE {i+1}/{len(command_bytes)}: ".encode() + bytes([byte]) + b"\n")
                
                if i < len(command_bytes) - 1:  # Don't delay after the last byte
                    time.sleep(delay_ms / 1000.0)
            
            # Small delay after command is complete
            time.sleep(0.02)
            
            return True
        except Exception as e:
            logging.error(f"Error sending {command_name}: {e}")
            return False
    
    def send_command(self, command_name, hex_command):
        """Send a command as a single block."""
        try:
            # Convert the hex string to bytes
            command_bytes = self.hex_to_bytes(hex_command)
            
            # Log the command
            logging.info(f"Sending {command_name} (block): {hex_command}")
            
            # Write timestamp and direction to raw log
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
            self.raw_log.write(f"TX {timestamp}: ".encode() + command_bytes + b"\n")
            
            # Send the command
            bytes_written = self.ser.write(command_bytes)
            self.ser.flush()
            
            logging.debug(f"Wrote {bytes_written} bytes")
            
            return True
        except Exception as e:
            logging.error(f"Error sending {command_name}: {e}")
            return False
    
    def receive_response(self, timeout=1.0, min_bytes=1, expected_end=None):
        """Receive response from the device and log it."""
        response = b''
        start_time = time.time()
        
        logging.debug(f"Waiting for response (timeout: {timeout}s, min bytes: {min_bytes})")
        
        # Keep reading until timeout or we get enough data
        while (time.time() - start_time) < timeout:
            if self.ser.in_waiting > 0:
                new_data = self.ser.read(self.ser.in_waiting)
                if new_data:
                    response += new_data
                    
                    # If we have the expected end marker, check if we're done
                    if expected_end and expected_end in response and len(response) >= min_bytes:
                        # Give a small delay to see if more data arrives
                        time.sleep(0.05)
                        # Read any remaining data
                        if self.ser.in_waiting > 0:
                            response += self.ser.read(self.ser.in_waiting)
                        break
            
            # Small delay to prevent CPU hogging
            time.sleep(0.01)
        
        # Log the response
        if response:
            response_hex = self.bytes_to_hex_string(response)
            logging.info(f"RX: [{len(response)} bytes] {response_hex}")
            
            # Write timestamp and direction to raw log
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
            self.raw_log.write(f"RX {timestamp}: ".encode() + response + b"\n")
        else:
            logging.warning(f"No response received within {timeout}s")
        
        return response
    
    def try_sync(self, sync_command="0x3C", attempts=5, timeout=1.0):
        """Try to sync with the device by sending start marker."""
        logging.info(f"Attempting to sync with device ({attempts} attempts)...")
        
        for i in range(attempts):
            logging.info(f"Sync attempt {i+1}/{attempts}")
            self.send_command(f"SYNC_{i+1}", sync_command)
            response = self.receive_response(timeout)
            
            if response:
                logging.info(f"Received response to sync command: {self.bytes_to_hex_string(response)}")
                return True
            
            # Wait between attempts
            time.sleep(0.5)
        
        logging.warning("Failed to sync with device")
        return False
    
    def clear_buffers(self):
        """Clear serial buffers."""
        if self.ser and self.ser.is_open:
            self.ser.reset_input_buffer()
            self.ser.reset_output_buffer()
            logging.debug("Serial buffers cleared")
    
    def toggle_rts_dtr(self):
        """Toggle RTS/DTR lines to reset the device."""
        if not self.ser or not self.ser.is_open:
            return
        
        logging.info("Toggling RTS/DTR lines...")
        
        # Save current states
        old_rts = self.ser.rts if hasattr(self.ser, 'rts') else None
        old_dtr = self.ser.dtr if hasattr(self.ser, 'dtr') else None
        
        # Toggle RTS
        if hasattr(self.ser, 'rts'):
            self.ser.rts = True
            time.sleep(0.2)
            self.ser.rts = False
            time.sleep(0.2)
            self.ser.rts = old_rts
        
        # Toggle DTR
        if hasattr(self.ser, 'dtr'):
            self.ser.dtr = True
            time.sleep(0.2)
            self.ser.dtr = False
            time.sleep(0.2)
            self.ser.dtr = old_dtr
        
        logging.info(f"RTS/DTR toggled, now at DTR={self.ser.dtr if hasattr(self.ser, 'dtr') else 'N/A'}, "
                    f"RTS={self.ser.rts if hasattr(self.ser, 'rts') else 'N/A'}")
    
    def run_test_sequence(self, send_style="normal"):
        """Run a basic test sequence - initialization and heartbeat only."""
        if not self.ser or not self.ser.is_open:
            logging.error("Serial port not open. Call connect() first.")
            return False
        
        # Commands from our analysis
        init_cmd = "0x3C 0x80 0x5C 0xC0 0x5C 0x70 0x5C 0x60 0x5C 0x82 0xCA 0xF8 0xF8 0x0C 0x0C 0x9C 0xCC 0xAC 0x9C 0x8C 0x8C 0x5C 0x78 0x5C 0xE2 0x7C"
        heartbeat_cmd = "0x3C 0x80 0x5C 0xC0 0x5C 0xB0 0x5C 0x60 0x5C 0xCA 0x2A 0x18 0x00 0x00 0x0C 0x0C 0x9C 0xCC 0xAC 0x9C 0x5C 0x08 0x5C 0xE2 0x7C"
        
        # Alternative format commands to try
        alt_init_cmd = "0x3C 0xC0 0x5C 0x80 0x5C 0xC0 0x5C 0x82 0xCA 0x5C 0x5C 0xC8 0x5C 0xE2 0x7C"
        
        logging.info("=========================================")
        logging.info("STARTING BASIC COMMUNICATION TEST")
        logging.info("=========================================")
        
        # Try to sync first
        self.try_sync()
        
        # Clear buffers before starting
        self.clear_buffers()
        
        # 1. Try initialization command
        logging.info("Step 1: Sending initialization command")
        
        if send_style == "byte_by_byte":
            success = self.send_bytes_with_delay("INIT", init_cmd)
        else:
            success = self.send_command("INIT", init_cmd)
            
        if not success:
            logging.error("Failed to send initialization command")
            return False
            
        # Wait for response with longer timeout
        init_response = self.receive_response(timeout=3.0, expected_end=b'\x7C')
        
        if not init_response:
            logging.warning("No response to initialization, trying alternative command...")
            
            # Try alternative initialization command
            if send_style == "byte_by_byte":
                success = self.send_bytes_with_delay("ALT_INIT", alt_init_cmd)
            else:
                success = self.send_command("ALT_INIT", alt_init_cmd)
                
            if not success:
                logging.error("Failed to send alternative initialization command")
                return False
                
            # Wait for response
            init_response = self.receive_response(timeout=3.0, expected_end=b'\x7C')
            
            if not init_response:
                logging.error("No response to alternative initialization command")
                
                # Try toggling control lines
                self.toggle_rts_dtr()
                time.sleep(1.0)
                
                # Last attempt - heartbeat command
                logging.info("Last attempt: Sending heartbeat command directly")
                if send_style == "byte_by_byte":
                    self.send_bytes_with_delay("HEARTBEAT", heartbeat_cmd)
                else:
                    self.send_command("HEARTBEAT", heartbeat_cmd)
                    
                heartbeat_response = self.receive_response(timeout=3.0, expected_end=b'\x7C')
                
                if not heartbeat_response:
                    logging.error("No response to direct heartbeat command")
                    return False
        
        # 2. Send a few heartbeat commands
        logging.info("Step 2: Sending heartbeat commands")
        
        for i in range(3):
            logging.info(f"Heartbeat {i+1}/3")
            
            if send_style == "byte_by_byte":
                success = self.send_bytes_with_delay("HEARTBEAT", heartbeat_cmd)
            else:
                success = self.send_command("HEARTBEAT", heartbeat_cmd)
                
            if not success:
                logging.error(f"Failed to send heartbeat command {i+1}")
                continue
                
            # Wait for response
            heartbeat_response = self.receive_response(timeout=2.0, expected_end=b'\x7C')
            
            if not heartbeat_response:
                logging.warning(f"No response to heartbeat {i+1}")
            
            # Wait longer between heartbeats to allow device to process
            time.sleep(1.5)
        
        logging.info("=========================================")
        logging.info("TEST SEQUENCE COMPLETED")
        logging.info("=========================================")
        
        return True


def try_all_configurations(port, commands_style="normal", debug=False):
    """Try multiple serial configurations to find one that works."""
    connector = PanTiltConnector(port, debug=debug)
    
    # Common baud rates to try
    baud_rates = [9600, 4800, 2400, 19200, 38400, 57600, 115200]
    
    # Try each baud rate with different parity/stop bit configurations
    for baud in baud_rates:
        logging.info(f"\n===========================================")
        logging.info(f"Testing with {baud} baud")
        logging.info(f"===========================================")
        
        # Try 8N1 (most common)
        connector.baudrate = baud
        connector.connect(parity=serial.PARITY_NONE, stopbits=serial.STOPBITS_ONE)
        connector.run_test_sequence(send_style=commands_style)
        connector.disconnect()
        
        # Try with RTS/CTS flow control
        connector.baudrate = baud
        connector.connect(parity=serial.PARITY_NONE, stopbits=serial.STOPBITS_ONE,
                         rtscts=True)
        connector.run_test_sequence(send_style=commands_style)
        connector.disconnect()
        
        # Try 8E1
        connector.baudrate = baud
        connector.connect(parity=serial.PARITY_EVEN, stopbits=serial.STOPBITS_ONE)
        connector.run_test_sequence(send_style=commands_style)
        connector.disconnect()
        
        # Try 8O1
        connector.baudrate = baud
        connector.connect(parity=serial.PARITY_ODD, stopbits=serial.STOPBITS_ONE)
        connector.run_test_sequence(send_style=commands_style)
        connector.disconnect()
        
        # If the user interrupts, stop testing
        if input("Continue testing? (y/n): ").lower() != 'y':
            break
    
    logging.info("Completed testing all configurations")


def main():
    """Main function to run the communication test."""
    parser = argparse.ArgumentParser(description='Pan-Tilt Unit Communication Tester')
    parser.add_argument('--port', type=str, required=True, help='Serial port (e.g., /dev/ttyUSB0)')
    parser.add_argument('--baudrate', type=int, default=9600, help='Baud rate (default: 9600)')
    parser.add_argument('--test-all', action='store_true', help='Test all configurations')
    parser.add_argument('--byte-by-byte', action='store_true', help='Send commands byte by byte with delays')
    parser.add_argument('--debug', action='store_true', help='Enable debug logging')
    args = parser.parse_args()
    
    try:
        if args.test_all:
            cmd_style = "byte_by_byte" if args.byte_by_byte else "normal"
            try_all_configurations(args.port, commands_style=cmd_style, debug=args.debug)
        else:
            connector = PanTiltConnector(args.port, args.baudrate, debug=args.debug)
            
            if connector.connect():
                cmd_style = "byte_by_byte" if args.byte_by_byte else "normal"
                connector.run_test_sequence(send_style=cmd_style)
            else:
                logging.error("Failed to connect to serial port. Exiting.")
    except KeyboardInterrupt:
        logging.info("Program interrupted by user")
    except Exception as e:
        logging.error(f"Error: {e}", exc_info=True)


if __name__ == "__main__":
    main()