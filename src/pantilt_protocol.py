#!/usr/bin/env python3
"""
Pan-Tilt Protocol Analyzer
Focuses on implementation details that might be missing from our analysis
"""

import serial
import time
import binascii
import argparse
import os
from datetime import datetime

class PanTiltProtocol:
    def __init__(self, port, baudrate=9600, debug=True):
        self.port = port
        self.baudrate = baudrate
        self.ser = None
        self.debug = debug

        # Set up logging
        self.log_file = f"pantilt_protocol_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        self.log(f"Pan-Tilt Protocol Analyzer started", level="INFO")
        
    def log(self, message, level="DEBUG"):
        """Log message to file and console."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        log_entry = f"{timestamp} - {level} - {message}"
        
        print(log_entry)
        with open(self.log_file, 'a') as f:
            f.write(log_entry + "\n")
    
    def connect(self):
        """Connect to the serial port with protocol-specific settings."""
        try:
            self.log("Opening serial port...", "INFO")
            self.ser = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=0.1
            )
            
            # Configure control lines - IMPORTANT
            # Some devices require specific control line settings to activate
            self.log("Setting control lines to inactive state", "INFO")
            if hasattr(self.ser, 'dtr'):
                self.ser.dtr = False  # Data Terminal Ready - OFF
            if hasattr(self.ser, 'rts'):
                self.ser.rts = False  # Request To Send - OFF
            
            self.log(f"Connected to {self.port} at {self.baudrate} baud", "INFO")
            self.log(f"DTR: {self.ser.dtr if hasattr(self.ser, 'dtr') else 'N/A'}, "
                    f"RTS: {self.ser.rts if hasattr(self.ser, 'rts') else 'N/A'}")
            
            # Clear buffers
            self.ser.reset_input_buffer()
            self.ser.reset_output_buffer()
            
            # Wait for device stabilization
            time.sleep(1.0)
            
            return True
        except Exception as e:
            self.log(f"Connection error: {e}", "ERROR")
            return False
    
    def disconnect(self):
        """Properly disconnect from the serial port."""
        if self.ser and self.ser.is_open:
            # Restore control line state before closing
            if hasattr(self.ser, 'dtr'):
                self.ser.dtr = True
            if hasattr(self.ser, 'rts'):
                self.ser.rts = True
                
            time.sleep(0.1)  # Allow control lines to stabilize
            
            self.ser.close()
            self.log(f"Disconnected from {self.port}", "INFO")
    
    def hex_to_bytes(self, hex_string):
        """Convert a hex string to bytes, handling different formats."""
        if hex_string.startswith("0x"):
            # Format: "0x3C 0x80 0x5C..."
            return bytes([int(h, 16) for h in hex_string.split()])
        else:
            # Format: "3C805C..."
            return bytes.fromhex(hex_string.replace(" ", ""))
    
    def bytes_to_hex_string(self, data):
        """Convert bytes to a formatted hex string."""
        return ' '.join([f"0x{b:02X}" for b in data])
    
    def send_command_with_precise_timing(self, command_bytes, byte_delay_ms=5):
        """Send command with precise byte-by-byte timing, handling escape sequences."""
        if not self.ser or not self.ser.is_open:
            self.log("Serial port not open", "ERROR")
            return False
        
        self.log(f"Sending command with {byte_delay_ms}ms byte delay: {self.bytes_to_hex_string(command_bytes)}")
        
        # Special handling for start byte
        # Some devices need extra time after the start marker
        if command_bytes and command_bytes[0] == 0x3C:
            self.log("Sending start marker with extended delay")
            self.ser.write(bytes([command_bytes[0]]))
            self.ser.flush()
            time.sleep(0.02)  # 20ms delay after start marker
            command_bytes = command_bytes[1:]  # Remove start marker from bytes to send

        # Send remaining bytes with precise timing
        for i, byte in enumerate(command_bytes):
            # Special handling for escape character 0x5C
            # In the analyzed protocol, 0x5C appears to be special
            is_escape = byte == 0x5C
            
            self.ser.write(bytes([byte]))
            self.ser.flush()
            
            # Use longer delay after escape character
            if is_escape:
                self.log(f"Sent escape character 0x5C, using extended delay")
                time.sleep(0.01)  # 10ms for escape character
            else:
                time.sleep(byte_delay_ms / 1000.0)
        
        # Additional delay after full command
        time.sleep(0.02)  # 20ms settling time
        
        return True
    
    def receive_response(self, timeout=1.0, min_bytes=1, expected_end=None):
        """Receive and process response, handling potential protocol-specific formatting."""
        if not self.ser or not self.ser.is_open:
            self.log("Serial port not open", "ERROR")
            return None
        
        self.log(f"Waiting for response (timeout: {timeout}s)")
        
        response = b''
        start_time = time.time()
        
        while (time.time() - start_time) < timeout:
            if self.ser.in_waiting > 0:
                new_data = self.ser.read(self.ser.in_waiting)
                if new_data:
                    self.log(f"Read {len(new_data)} bytes: {self.bytes_to_hex_string(new_data)}")
                    response += new_data
                    
                    # If we have the expected end marker and minimum bytes, check if we're done
                    if expected_end and expected_end in response and len(response) >= min_bytes:
                        # Give a small delay to see if more data arrives
                        time.sleep(0.05)
                        # Read any remaining data
                        if self.ser.in_waiting > 0:
                            additional = self.ser.read(self.ser.in_waiting)
                            self.log(f"Read additional {len(additional)} bytes: {self.bytes_to_hex_string(additional)}")
                            response += additional
                        break
            
            # Small delay to prevent CPU hogging
            time.sleep(0.01)
        
        if response:
            self.log(f"Received total of {len(response)} bytes: {self.bytes_to_hex_string(response)}")
        else:
            self.log(f"No response received within {timeout}s", "WARNING")
        
        return response
    
    def execute_initialization_sequence(self):
        """Execute a comprehensive initialization sequence with all possible permutations."""
        self.log("Beginning initialization sequence attempts", "INFO")
        
        # --------- ATTEMPT 1: Original Initialization Command ---------
        init_cmd = "0x3C 0x80 0x5C 0xC0 0x5C 0x70 0x5C 0x60 0x5C 0x82 0xCA 0xF8 0xF8 0x0C 0x0C 0x9C 0xCC 0xAC 0x9C 0x8C 0x8C 0x5C 0x78 0x5C 0xE2 0x7C"
        self.log("\nAttempt 1: Sending original initialization command", "INFO")
        
        # Try with precise timing
        cmd_bytes = self.hex_to_bytes(init_cmd)
        
        # IMPORTANT: The original protocol likely has a pre-initialization sequence
        # Let's add a wake-up pattern that might be missing from our capture
        self.log("Sending wake-up sequence (not in capture, but may be required)")
        for _ in range(3):
            self.ser.write(bytes([0x00]))  # Send NULL byte
            self.ser.flush()
            time.sleep(0.1)
            
            # Check for any response
            if self.ser.in_waiting > 0:
                data = self.ser.read(self.ser.in_waiting)
                self.log(f"Response to NULL byte: {self.bytes_to_hex_string(data)}")
        
        # Now send the initialization command with precise timing
        self.send_command_with_precise_timing(cmd_bytes)
        response = self.receive_response(timeout=2.0, expected_end=bytes([0x7C]))
        
        if response:
            self.log("Successfully received response to initialization", "INFO")
            return True
            
        # --------- ATTEMPT 2: RTS/DTR Line Toggling ---------
        self.log("\nAttempt 2: Toggling RTS/DTR lines before initialization", "INFO")
        
        # Some devices need control line manipulation to "wake up"
        if hasattr(self.ser, 'rts') and hasattr(self.ser, 'dtr'):
            # Toggle RTS
            self.log("Toggling RTS line")
            self.ser.rts = True
            time.sleep(0.5)
            self.ser.rts = False
            time.sleep(0.5)
            
            # Toggle DTR
            self.log("Toggling DTR line")
            self.ser.dtr = True
            time.sleep(0.5)
            self.ser.dtr = False
            time.sleep(0.5)
            
            # Send start marker after line toggle
            self.log("Sending start marker (0x3C) after line toggle")
            self.ser.write(bytes([0x3C]))
            self.ser.flush()
            time.sleep(0.5)
            
            if self.ser.in_waiting > 0:
                data = self.ser.read(self.ser.in_waiting)
                self.log(f"Response to start marker: {self.bytes_to_hex_string(data)}")
        
        # Try initialization again
        self.send_command_with_precise_timing(cmd_bytes)
        response = self.receive_response(timeout=2.0, expected_end=bytes([0x7C]))
        
        if response:
            self.log("Successfully received response after RTS/DTR toggle", "INFO")
            return True
            
        # --------- ATTEMPT 3: Alternative Command Format ---------
        alt_init_cmd = "0x3C 0xC0 0x5C 0x80 0x5C 0xC0 0x5C 0x82 0xCA 0x5C 0x5C 0xC8 0x5C 0xE2 0x7C"
        self.log("\nAttempt 3: Sending alternative initialization command", "INFO")
        
        alt_cmd_bytes = self.hex_to_bytes(alt_init_cmd)
        self.send_command_with_precise_timing(alt_cmd_bytes)
        response = self.receive_response(timeout=2.0, expected_end=bytes([0x7C]))
        
        if response:
            self.log("Successfully received response to alternative command", "INFO")
            return True
        
        # --------- ATTEMPT 4: Byte-by-Byte with Very Slow Timing ---------
        self.log("\nAttempt 4: Very slow byte-by-byte transmission", "INFO")
        
        # Some older devices need very slow communication
        self.log("Sending initialization bytes with 50ms delay between bytes")
        for i, byte in enumerate(cmd_bytes):
            self.log(f"Sending byte {i+1}/{len(cmd_bytes)}: 0x{byte:02X}")
            self.ser.write(bytes([byte]))
            self.ser.flush()
            time.sleep(0.05)  # 50ms between bytes
            
            # Check if there's any response after each byte
            if self.ser.in_waiting > 0:
                data = self.ser.read(self.ser.in_waiting)
                self.log(f"Response after byte {i+1}: {self.bytes_to_hex_string(data)}")
                
                # If we got a response, process it
                if data:
                    # Continue reading to get full response
                    time.sleep(0.1)
                    while self.ser.in_waiting > 0:
                        data += self.ser.read(self.ser.in_waiting)
                        time.sleep(0.05)
                    
                    self.log(f"Complete response: {self.bytes_to_hex_string(data)}")
                    return True
        
        # Look for any delayed response
        response = self.receive_response(timeout=2.0, expected_end=bytes([0x7C]))
        
        if response:
            self.log("Successfully received response to slow transmission", "INFO")
            return True
            
        # --------- ATTEMPT 5: Raw Sync Character Stream ---------
        self.log("\nAttempt 5: Sending stream of sync characters", "INFO")
        
        # Some devices need a stream of sync characters to establish communication
        sync_char = 0x3C  # Start marker
        self.log(f"Sending 10 sync characters (0x{sync_char:02X})")
        
        for i in range(10):
            self.log(f"Sending sync {i+1}/10")
            self.ser.write(bytes([sync_char]))
            self.ser.flush()
            time.sleep(0.2)
            
            # Check for response
            if self.ser.in_waiting > 0:
                data = self.ser.read(self.ser.in_waiting)
                self.log(f"Response to sync: {self.bytes_to_hex_string(data)}")
                
                if data:
                    self.log("Got response to sync character", "INFO")
                    return True
        
        self.log("All initialization attempts failed", "WARNING")
        return False
    
    def send_heartbeat(self):
        """Send heartbeat command with protocol-specific handling."""
        heartbeat_cmd = "0x3C 0x80 0x5C 0xC0 0x5C 0xB0 0x5C 0x60 0x5C 0xCA 0x2A 0x18 0x00 0x00 0x0C 0x0C 0x9C 0xCC 0xAC 0x9C 0x5C 0x08 0x5C 0xE2 0x7C"
        self.log("\nSending heartbeat command", "INFO")
        
        cmd_bytes = self.hex_to_bytes(heartbeat_cmd)
        self.send_command_with_precise_timing(cmd_bytes)
        
        response = self.receive_response(timeout=2.0, expected_end=bytes([0x7C]))
        
        if response:
            self.log("Successfully received response to heartbeat", "INFO")
            return True
        else:
            self.log("No response to heartbeat", "WARNING")
            return False
    
    def run_protocol_sequence(self):
        """Run the complete protocol sequence with careful attention to details."""
        if not self.ser or not self.ser.is_open:
            self.log("Serial port not open", "ERROR")
            return False
        
        self.log("======================================", "INFO")
        self.log("RUNNING PROTOCOL SEQUENCE", "INFO")
        self.log("======================================", "INFO")
        
        # Step 1: Execute initialization sequence
        if not self.execute_initialization_sequence():
            self.log("Failed to initialize device", "ERROR")
            
            # Check if there was any data at all on the port
            self.log("Checking for any activity on serial port...")
            time.sleep(2.0)
            
            if self.ser.in_waiting > 0:
                data = self.ser.read(self.ser.in_waiting)
                self.log(f"Detected {len(data)} bytes: {self.bytes_to_hex_string(data)}")
            else:
                self.log("No data detected on port", "WARNING")
                
            return False
        
        # Step 2: Send heartbeat commands
        self.log("\nSending heartbeat sequence", "INFO")
        
        for i in range(3):
            self.log(f"Heartbeat {i+1}/3")
            self.send_heartbeat()
            time.sleep(1.0)  # Wait between heartbeats
        
        self.log("======================================", "INFO")
        self.log("PROTOCOL SEQUENCE COMPLETED", "INFO")
        self.log("======================================", "INFO")
        
        return True


def main():
    parser = argparse.ArgumentParser(description='Pan-Tilt Protocol Analyzer')
    parser.add_argument('--port', type=str, required=True, help='Serial port')
    parser.add_argument('--baudrate', type=int, default=9600, help='Baud rate')
    parser.add_argument('--debug', action='store_true', help='Enable debug logging')
    args = parser.parse_args()
    
    protocol = PanTiltProtocol(args.port, args.baudrate, debug=args.debug)
    
    try:
        if protocol.connect():
            protocol.run_protocol_sequence()
        protocol.disconnect()
    except Exception as e:
        protocol.log(f"Error: {e}", "ERROR")


if __name__ == "__main__":
    main()