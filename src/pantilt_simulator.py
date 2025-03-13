#!/usr/bin/env python3
"""
Pan-Tilt Control Simulator - Initialization and Heartbeat
-------------------------------------------------------
This tool implements the initialization and heartbeat protocol for the pan-tilt unit
based on the analysis in analysis.md. It sends the commands and verifies responses
against the expected patterns from our measurements.
"""

import serial
import time
import logging
import binascii
import argparse
from datetime import datetime

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("pantilt_simulator.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Command definitions - simplified initialization sequence
COMMANDS = {
    "sync": bytes.fromhex("3C"),  # Just send the start marker
    "initialization": bytes.fromhex("3C 80 5C C0 5C 70 5C 60 5C 82 CA F8 F8 0C 0C 9C CC AC 9C 8C 8C 5C 78 5C E2 7C".replace(" ", "")),
    "heartbeat": bytes.fromhex("3C 80 5C C0 5C B0 5C 60 5C CA 2A 18 00 00 0C 0C 9C CC AC 9C 5C 08 5C E2 7C".replace(" ", ""))
}

# Expected responses from analysis.md - RESPONSES WE EXPECT
EXPECTED_RESPONSES = {
    "sync": bytes.fromhex("3C"),  # Just expect the start marker back
    "initialization": bytes.fromhex("3C C0 5C 80 5C C0 5C 82 CA 5C 5C C8 5C E2 7C".replace(" ", "")),
    "heartbeat": bytes.fromhex("3C C0 5C 80 5C C0 5C CA 2A 5C 5C 60 5C E2 7C".replace(" ", ""))
}

class PanTiltController:
    """Controller class for pan-tilt unit communication"""
    
    def __init__(self, port='/dev/ttyUSB0', baudrate=9600, timeout=1, parity=serial.PARITY_NONE, stopbits=serial.STOPBITS_ONE):
        """Initialize the controller with communication parameters"""
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.parity = parity
        self.stopbits = stopbits
        self.ser = None
        self.transaction_log = []
    
    def hex_dump(self, data):
        """Convert binary data to readable hex string"""
        return ' '.join([f"0x{b:02X}" for b in data])
    
    def connect(self):
        """Establish serial connection to the pan-tilt unit"""
        try:
            self.ser = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                bytesize=serial.EIGHTBITS,
                parity=self.parity,
                stopbits=self.stopbits,
                timeout=self.timeout,
                rtscts=False,  # Disable hardware flow control
                dsrdtr=False
            )
            
            # Flush any stale data
            self.ser.reset_input_buffer()
            self.ser.reset_output_buffer()
            
            # Try to read any existing data
            if self.ser.in_waiting > 0:
                stale_data = self.ser.read(self.ser.in_waiting)
                logger.info(f"Cleared {len(stale_data)} bytes of stale data: {self.hex_dump(stale_data)}")
            
            logger.info(f"Connected to {self.port} at {self.baudrate} baud")
            
            # Try to sync with device by sending start marker
            logger.info("Attempting to sync with device...")
            for _ in range(3):  # Try 3 times
                self.send_command("sync")
                response = self.read_response("sync", timeout=0.5)
                if response:
                    logger.info("Successfully synced with device")
                    break
                time.sleep(0.5)
            
            # Wait for device to stabilize
            time.sleep(2)
            logger.info("Waited 2 seconds for device to stabilize")
            
            return True
        except serial.SerialException as e:
            logger.error(f"Failed to connect to {self.port}: {e}")
            return False
    
    def disconnect(self):
        """Close serial connection"""
        if self.ser and self.ser.is_open:
            self.ser.close()
            logger.info(f"Disconnected from {self.port}")
    
    def send_command(self, command_type):
        """
        Send a command to the pan-tilt unit
        
        Args:
            command_type: Type of command ('initialization' or 'heartbeat')
            
        Returns:
            bool: Success status
        """
        if command_type not in COMMANDS:
            logger.error(f"Unknown command type: {command_type}")
            return False
        
        command = COMMANDS[command_type]
        timestamp = datetime.now()
        logger.info(f"Sending {command_type} command: {self.hex_dump(command)}")
        
        # Log the transaction
        transaction = {
            'timestamp': timestamp,
            'direction': 'TX',
            'command_type': command_type,
            'data': command
        }
        self.transaction_log.append(transaction)
        
        try:
            # Flush any stale data before sending
            if self.ser.in_waiting > 0:
                stale_data = self.ser.read(self.ser.in_waiting)
                logger.info(f"Cleared {len(stale_data)} bytes of stale data before sending: {self.hex_dump(stale_data)}")
            
            bytes_written = self.ser.write(command)
            self.ser.flush()
            logger.debug(f"Wrote {bytes_written} bytes")
            return True
        except Exception as e:
            logger.error(f"Error sending command: {e}")
            return False
    
    def read_response(self, expected_type=None, timeout=2.0, max_bytes=50):
        """
        Read and validate a response from the pan-tilt unit
        
        Args:
            expected_type: Type of expected response for validation
            timeout: Time to wait for response in seconds
            max_bytes: Maximum bytes to read
            
        Returns:
            bytes: Response data
        """
        start_time = time.time()
        buffer = b''
        found_start = False
        raw_buffer = b''  # Store all received bytes
        
        logger.debug("Waiting for response...")
        
        while time.time() - start_time < timeout and len(buffer) < max_bytes:
            if self.ser.in_waiting > 0:
                byte = self.ser.read(1)
                raw_buffer += byte  # Store every byte we receive
                
                # Look for start marker
                if not found_start and byte == b'\x3C':
                    found_start = True
                    buffer = byte  # Start fresh with the start marker
                    logger.debug(f"Found start marker at {time.time() - start_time:.4f}s")
                elif found_start:
                    buffer += byte
                    
                    # End the read when we find the end marker
                    if byte == b'\x7C':
                        logger.debug(f"Found end marker at {time.time() - start_time:.4f}s")
                        break
            else:
                # Small sleep to prevent CPU-hogging
                time.sleep(0.001)
        
        elapsed = time.time() - start_time
        
        # Log all received data, even if it doesn't match our pattern
        if raw_buffer:
            logger.info(f"Raw data received: {self.hex_dump(raw_buffer)} ({len(raw_buffer)} bytes)")
        
        if not buffer:
            if raw_buffer:
                logger.warning(f"Received data but no valid message pattern found within {elapsed:.4f}s")
            else:
                logger.warning(f"No response received within {elapsed:.4f}s")
            return raw_buffer if raw_buffer else b''  # Return raw data if we have it
        
        if not buffer.endswith(b'\x7C'):
            logger.warning(f"Response incomplete after {elapsed:.4f}s")
        
        logger.info(f"Received response: {self.hex_dump(buffer)} ({len(buffer)} bytes) in {elapsed:.4f}s")
        
        # Log the transaction
        self.transaction_log.append({
            'timestamp': datetime.now(),
            'direction': 'RX',
            'command_type': expected_type if expected_type else 'unknown',
            'data': buffer
        })
        
        # Validate against expected response
        if expected_type and expected_type in EXPECTED_RESPONSES:
            self.compare_response(buffer, EXPECTED_RESPONSES[expected_type], expected_type)
        
        return buffer
    
    def compare_response(self, actual, expected, label="Response"):
        """
        Compare actual and expected responses with detailed logging
        
        Args:
            actual: Actual received bytes
            expected: Expected bytes
            label: Label for logging
        
        Returns:
            bool: True if match, False otherwise
        """
        if actual == expected:
            logger.info(f"{label} matches expected pattern exactly")
            return True
        
        # Data doesn't match, provide detailed comparison
        logger.warning(f"{label} does not match expected pattern")
        logger.info(f"  Actual  : {self.hex_dump(actual)} ({len(actual)} bytes)")
        logger.info(f"  Expected: {self.hex_dump(expected)} ({len(expected)} bytes)")
        
        # Length comparison
        if len(actual) != len(expected):
            logger.warning(f"  Length mismatch: Actual={len(actual)}, Expected={len(expected)}")
        
        # Find positions of differences
        min_len = min(len(actual), len(expected))
        differences = []
        
        for i in range(min_len):
            if actual[i] != expected[i]:
                differences.append(i)
        
        if differences:
            logger.warning(f"  Differences at positions: {differences}")
            for pos in differences:
                logger.info(f"    Position {pos}: Actual=0x{actual[pos]:02X}, Expected=0x{expected[pos]:02X}")
        
        return False

def main():
    """Main function to run the pan-tilt simulator"""
    parser = argparse.ArgumentParser(description='Pan-Tilt Control Simulator')
    parser.add_argument('--port', default='/dev/ttyUSB0', help='Serial port to use')
    parser.add_argument('--baudrate', type=int, default=9600, help='Baud rate for serial communication')
    parser.add_argument('--parity', choices=['N', 'E', 'O'], default='N', help='Parity (N=None, E=Even, O=Odd)')
    parser.add_argument('--stopbits', type=float, choices=[1, 1.5, 2], default=1, help='Stop bits (1, 1.5, or 2)')
    parser.add_argument('--debug', action='store_true', help='Enable debug logging')
    args = parser.parse_args()
    
    if args.debug:
        logger.setLevel(logging.DEBUG)
    
    logger.info("=" * 60)
    logger.info("Pan-Tilt Control Simulator - Initialization and Heartbeat")
    logger.info("=" * 60)
    logger.info(f"Version: 1.0.0 (Raspberry Pi 5)")
    logger.info(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Convert parity string to serial.PARITY_* constant
    parity_map = {
        'N': serial.PARITY_NONE,
        'E': serial.PARITY_EVEN,
        'O': serial.PARITY_ODD
    }
    
    # Convert stop bits to serial.STOPBITS_* constant
    stopbits_map = {
        1: serial.STOPBITS_ONE,
        1.5: serial.STOPBITS_ONE_POINT_FIVE,
        2: serial.STOPBITS_TWO
    }
    
    # Try different configurations
    configs_to_try = [
        # (parity, stop bits)
        ('N', 1),  # 8N1 (most common)
        ('E', 1),  # 8E1
        ('O', 1),  # 8O1
        ('N', 2),  # 8N2
        ('E', 2),  # 8E2
        ('O', 2),  # 8O2
    ]
    
    for parity, stopbits in configs_to_try:
        logger.info("\n" + "=" * 60)
        logger.info(f"Trying configuration: {args.baudrate} baud, 8{parity}{stopbits}")
        logger.info("=" * 60)
        
        controller = PanTiltController(
            port=args.port,
            baudrate=args.baudrate,
            parity=parity_map[parity],
            stopbits=stopbits_map[stopbits]
        )
        
        if not controller.connect():
            logger.error("Failed to connect to pan-tilt unit")
            continue
        
        try:
            # Step 1: Send initialization command
            logger.info("Step 1: Sending initialization command")
            if not controller.send_command("initialization"):
                logger.error("Failed to send initialization command")
                continue
            
            # Wait for and verify initialization response
            response = controller.read_response("initialization")
            if not response:
                logger.error("No response to initialization command")
                continue
            
            # If we got a response, try the heartbeat sequence
            logger.info("\nStep 2: Sending heartbeat commands")
            success = True
            for i in range(3):
                logger.info(f"Heartbeat {i+1}/3")
                if not controller.send_command("heartbeat"):
                    logger.error(f"Failed to send heartbeat command {i+1}")
                    success = False
                    break
                
                response = controller.read_response("heartbeat")
                if not response:
                    logger.error(f"No response to heartbeat command {i+1}")
                    success = False
                    break
                
                time.sleep(1)
            
            if success:
                logger.info("\nFound working configuration!")
                break
            
        except KeyboardInterrupt:
            logger.info("\nProgram interrupted by user")
            break
        finally:
            controller.disconnect()
    
    logger.info("Program terminated")

if __name__ == "__main__":
    main()