#!/usr/bin/env python3
"""
Interactive Hex Terminal for Pan-Tilt Unit
Allows direct hex command entry and monitoring of responses.
"""

import serial
import time
import binascii
import threading
import argparse

class HexTerminal:
    def __init__(self, port, baudrate=9600):
        self.port = port
        self.baudrate = baudrate
        self.ser = None
        self.running = False
        self.monitor_thread = None
    
    def connect(self):
        try:
            self.ser = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=0.1
            )
            
            # Configure hardware lines
            if hasattr(self.ser, 'dtr'):
                self.ser.dtr = False
            if hasattr(self.ser, 'rts'):
                self.ser.rts = False
            
            print(f"Connected to {self.port} at {self.baudrate} baud")
            print(f"DTR: {self.ser.dtr if hasattr(self.ser, 'dtr') else 'N/A'}, "
                  f"RTS: {self.ser.rts if hasattr(self.ser, 'rts') else 'N/A'}")
            
            return True
        except Exception as e:
            print(f"Connection error: {e}")
            return False
    
    def disconnect(self):
        if self.ser and self.ser.is_open:
            self.ser.close()
            print(f"Disconnected from {self.port}")
    
    def monitor_port(self):
        """Monitor the serial port for incoming data."""
        self.running = True
        while self.running:
            if self.ser and self.ser.is_open and self.ser.in_waiting > 0:
                data = self.ser.read(self.ser.in_waiting)
                hex_data = ' '.join([f"0x{b:02X}" for b in data])
                print(f"\nRX: {hex_data}")
            time.sleep(0.05)
    
    def start_monitoring(self):
        """Start the monitoring thread."""
        self.monitor_thread = threading.Thread(target=self.monitor_port)
        self.monitor_thread.daemon = True
        self.monitor_thread.start()
    
    def stop_monitoring(self):
        """Stop the monitoring thread."""
        self.running = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=1.0)
    
    def send_hex(self, hex_string):
        """Send a hex string to the device."""
        try:
            # Convert hex string to bytes
            if hex_string.startswith("0x"):
                # Format: "0x3C 0x80 0x5C..."
                hex_bytes = bytes([int(h, 16) for h in hex_string.split()])
            else:
                # Format: "3C805C..."
                hex_string = hex_string.replace(" ", "")
                hex_bytes = bytes.fromhex(hex_string)
            
            # Send the bytes
            self.ser.write(hex_bytes)
            self.ser.flush()
            
            hex_display = ' '.join([f"0x{b:02X}" for b in hex_bytes])
            print(f"TX: {hex_display}")
            
            return True
        except Exception as e:
            print(f"Error sending hex: {e}")
            return False
    
    def send_byte(self, byte_value):
        """Send a single byte."""
        try:
            byte_int = int(byte_value, 16) if isinstance(byte_value, str) else byte_value
            self.ser.write(bytes([byte_int]))
            self.ser.flush()
            print(f"TX: 0x{byte_int:02X}")
            return True
        except Exception as e:
            print(f"Error sending byte: {e}")
            return False
    
    def interactive_mode(self):
        """Run interactive hex terminal mode."""
        if not self.ser or not self.ser.is_open:
            print("Not connected to serial port")
            return
        
        # Start monitoring thread
        self.start_monitoring()
        
        print("\n=== Interactive Hex Terminal ===")
        print("Enter hex values to send (e.g., '3C805C' or '0x3C 0x80 0x5C')")
        print("Special commands:")
        print("  q, quit - Exit the terminal")
        print("  clear - Clear input/output buffers")
        print("  status - Show port status")
        print("  init - Send initialization command")
        print("  hb - Send heartbeat command")
        print("  byte XX - Send a single byte (XX in hex)")
        print("  seq - Send predefined sequence (init, heartbeat)")
        print("===================================")
        
        # Predefined commands
        init_cmd = "0x3C 0x80 0x5C 0xC0 0x5C 0x70 0x5C 0x60 0x5C 0x82 0xCA 0xF8 0xF8 0x0C 0x0C 0x9C 0xCC 0xAC 0x9C 0x8C 0x8C 0x5C 0x78 0x5C 0xE2 0x7C"
        alt_init_cmd = "0x3C 0xC0 0x5C 0x80 0x5C 0xC0 0x5C 0x82 0xCA 0x5C 0x5C 0xC8 0x5C 0xE2 0x7C"
        heartbeat_cmd = "0x3C 0x80 0x5C 0xC0 0x5C 0xB0 0x5C 0x60 0x5C 0xCA 0x2A 0x18 0x00 0x00 0x0C 0x0C 0x9C 0xCC 0xAC 0x9C 0x5C 0x08 0x5C 0xE2 0x7C"
        
        while True:
            try:
                cmd = input("\nCommand> ").strip()
                
                if cmd.lower() in ('q', 'quit', 'exit'):
                    break
                elif cmd.lower() == 'clear':
                    self.ser.reset_input_buffer()
                    self.ser.reset_output_buffer()
                    print("Buffers cleared")
                elif cmd.lower() == 'status':
                    print(f"Port: {self.port}, Baud: {self.baudrate}, Open: {self.ser.is_open}")
                    print(f"DTR: {self.ser.dtr if hasattr(self.ser, 'dtr') else 'N/A'}, "
                          f"RTS: {self.ser.rts if hasattr(self.ser, 'rts') else 'N/A'}")
                elif cmd.lower() == 'init':
                    print("Sending initialization command...")
                    self.send_hex(init_cmd)
                elif cmd.lower() == 'alt_init':
                    print("Sending alternative initialization command...")
                    self.send_hex(alt_init_cmd)
                elif cmd.lower() == 'hb':
                    print("Sending heartbeat command...")
                    self.send_hex(heartbeat_cmd)
                elif cmd.lower().startswith('byte '):
                    byte_val = cmd.split()[1]
                    self.send_byte(byte_val)
                elif cmd.lower() == 'seq':
                    print("Sending initialization...")
                    self.send_hex(init_cmd)
                    time.sleep(2)
                    print("Sending heartbeat...")
                    self.send_hex(heartbeat_cmd)
                elif cmd:
                    self.send_hex(cmd)
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"Error: {e}")
        
        self.stop_monitoring()
        print("Terminal closed")

def main():
    parser = argparse.ArgumentParser(description='Interactive Hex Terminal for Pan-Tilt Unit')
    parser.add_argument('--port', type=str, required=True, help='Serial port')
    parser.add_argument('--baudrate', type=int, default=9600, help='Baud rate')
    args = parser.parse_args()
    
    terminal = HexTerminal(args.port, args.baudrate)
    
    try:
        if terminal.connect():
            terminal.interactive_mode()
        terminal.disconnect()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()